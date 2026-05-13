import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage, getH2HStats } from '../utils/statsCalculator.js';
import { calculatePoisson } from '../utils/poisson.js';
import { getIO } from './socket.js';

interface LeagueModels {
  classifier1X2: RandomForestClassifier;
  classifierOverUnder: RandomForestClassifier;
  classifierBTTS: RandomForestClassifier;
}

export class PredictionEngine {
  private leagueModels: Map<number, LeagueModels> = new Map();
  private globalModels: LeagueModels;

  constructor() {
    this.globalModels = this.createModelSet();
  }

  private createModelSet(): LeagueModels {
    const config = {
      nEstimators: 300, // Increased for better complexity handling
      seed: 42
    };
    return {
      classifier1X2: new RandomForestClassifier(config),
      classifierOverUnder: new RandomForestClassifier(config),
      classifierBTTS: new RandomForestClassifier(config)
    };
  }

  /**
   * Trains models per league and a global fallback model.
   */
  async trainModel() {
    const historicalData = await Match.find({ status: 'FINISHED' }).sort({ date: 1 });

    if (historicalData.length < 20) {
      console.warn('[PredictionEngine] Insufficient data to train the models.');
      return;
    }

    // Group data by league
    const leagueData: Map<number, any[]> = new Map();
    historicalData.forEach(match => {
      const list = leagueData.get(match.league.id) || [];
      list.push(match);
      leagueData.set(match.league.id, list);
    });

    // Train Global Model first
    console.log('[PredictionEngine] Training Global Model...');
    await this.trainSpecificModel(this.globalModels, historicalData);

    // Train League-Specific Models
    for (const [leagueId, matches] of leagueData.entries()) {
      if (matches.length >= 15) { // Minimum threshold for league-specific model
        console.log(`[PredictionEngine] Training Model for League ID: ${leagueId} (${matches.length} matches)`);
        const models = this.createModelSet();
        await this.trainSpecificModel(models, matches);
        this.leagueModels.set(leagueId, models);
      }
    }
  }

  private async trainSpecificModel(models: LeagueModels, matches: any[]) {
    const trainingFeatures1X2: number[][] = [];
    const trainingFeaturesOU: number[][] = [];
    const trainingFeaturesBTTS: number[][] = [];
    
    const labels1X2: number[] = [];
    const labelsOU: number[] = [];
    const labelsBTTS: number[] = [];

    for (const match of matches) {
      const homeStats = await getTeamMovingAverage(match.homeTeam.id);
      const awayStats = await getTeamMovingAverage(match.awayTeam.id);
      const h2h = await getH2HStats(match.homeTeam.id, match.awayTeam.id);

      if (homeStats.avgGoalsScored === 0 && awayStats.avgGoalsScored === 0) continue;

      // 1. Features for 1X2: Focus on Momentum, H2H and relative strength
      const features1X2 = [
        match.stats?.home_possession || homeStats.avgPossession,
        match.stats?.away_possession || awayStats.avgPossession,
        homeStats.formPoints,
        awayStats.formPoints,
        h2h.homeWins / (h2h.totalMatches || 1),
        h2h.draws / (h2h.totalMatches || 1),
        h2h.awayWins / (h2h.totalMatches || 1),
        homeStats.avgHomeGoalsScored - homeStats.avgHomeGoalsConceded, // Home Net Strength
        awayStats.avgAwayGoalsScored - awayStats.avgAwayGoalsConceded  // Away Net Strength
      ];

      // 2. Features for Over/Under: Focus on xG and Goal Averages
      const featuresOU = [
        homeStats.avgGoalsScored + homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored + awayStats.avgGoalsConceded,
        homeStats.avgXG,
        awayStats.avgXG,
        h2h.avgGoals,
        homeStats.avgShotsOnTarget,
        awayStats.avgShotsOnTarget
      ];

      // 3. Features for BTTS: Focus on offensive consistency vs defensive leaks
      const featuresBTTS = [
        homeStats.avgGoalsScored,
        homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored,
        awayStats.avgGoalsConceded,
        homeStats.avgXG,
        awayStats.avgXG,
        match.stats?.home_shots_on_target || homeStats.avgShotsOnTarget,
        match.stats?.away_shots_on_target || awayStats.avgShotsOnTarget
      ];

      trainingFeatures1X2.push(features1X2);
      trainingFeaturesOU.push(featuresOU);
      trainingFeaturesBTTS.push(featuresBTTS);

      // Label 1X2: 0=Home, 1=Draw, 2=Away
      if (match.score.home > match.score.away) labels1X2.push(0);
      else if (match.score.home === match.score.away) labels1X2.push(1);
      else labels1X2.push(2);

      // Label Over/Under 2.5: 0=Under, 1=Over
      labelsOU.push((match.score.home + match.score.away) > 2.5 ? 1 : 0);

      // Label BTTS: 0=No, 1=Yes
      labelsBTTS.push((match.score.home > 0 && match.score.away > 0) ? 1 : 0);
    }

    if (trainingFeatures1X2.length > 0) {
      models.classifier1X2.train(trainingFeatures1X2, labels1X2);
      models.classifierOverUnder.train(trainingFeaturesOU, labelsOU);
      models.classifierBTTS.train(trainingFeaturesBTTS, labelsBTTS);
    }
  }

  /**
   * Predicts outcomes for scheduled matches.
   */
  async predictScheduledMatches() {
    const now = new Date();
    const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);

    const scheduledMatches = await Match.find({ 
      status: 'SCHEDULED',
      date: { $gte: now, $lte: nextWeek }
    });

    for (const match of scheduledMatches) {
      const prediction = await this.generatePrediction(match);
      if (prediction) {
        match.prediction = prediction;
        await match.save();

        try {
          const io = getIO();
          io.emit('matchUpdated', match);
        } catch (socketError) {
          console.error('[PredictionEngine] Socket emit error:', socketError);
        }
      }
    }
    console.log(`Per-league AI predictions updated for ${scheduledMatches.length} matches.`);
  }

  /**
   * Core logic to generate a prediction for any match.
   * Useful for both scheduled matches and backtesting historical data.
   */
  async generatePrediction(match: any) {
    try {
      const homeStats = await getTeamMovingAverage(match.homeTeam.id);
      const awayStats = await getTeamMovingAverage(match.awayTeam.id);
      const h2h = await getH2HStats(match.homeTeam.id, match.awayTeam.id);

      // Fallback for teams with no stats yet
      if (homeStats.avgGoalsScored === 0 && awayStats.avgGoalsScored === 0) {
        return {
          outcome: 1, // Draw
          probabilities: {
            homeWin: 0.33, draw: 0.34, awayWin: 0.33,
            over25: 0.5, under25: 0.5, bttsYes: 0.5, bttsNo: 0.5,
            doubleChance1X: 0.67, doubleChance12: 0.66, doubleChanceX2: 0.67
          },
          analysis: "Dados estatísticos insuficientes para este confronto.",
          exactScores: [{ score: "1-1", probability: 0.15 }]
        };
      }

      // Feature vectors tailored for each market
      const input1X2 = [
        homeStats.avgPossession,
        awayStats.avgPossession,
        homeStats.formPoints,
        awayStats.formPoints,
        h2h.homeWins / (h2h.totalMatches || 1),
        h2h.draws / (h2h.totalMatches || 1),
        h2h.awayWins / (h2h.totalMatches || 1),
        homeStats.avgHomeGoalsScored - homeStats.avgHomeGoalsConceded,
        awayStats.avgAwayGoalsScored - awayStats.avgAwayGoalsConceded
      ];

      const inputOU = [
        homeStats.avgGoalsScored + homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored + awayStats.avgGoalsConceded,
        homeStats.avgXG,
        awayStats.avgXG,
        h2h.avgGoals,
        homeStats.avgShotsOnTarget,
        awayStats.avgShotsOnTarget
      ];

      const inputBTTS = [
        homeStats.avgGoalsScored,
        homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored,
        awayStats.avgGoalsConceded,
        homeStats.avgXG,
        awayStats.avgXG,
        homeStats.avgShotsOnTarget,
        awayStats.avgShotsOnTarget
      ];

      // Select model (League-specific or Global)
      const isLeagueModel = this.leagueModels.has(match.league.id);
      const models = this.leagueModels.get(match.league.id) || this.globalModels;

      // 1. ML Predictions (Random Forest)
      const rfProbs1X2_raw = models.classifier1X2.predictProbability([input1X2], 3)[0] as any;
      const rfProbsOU_raw = models.classifierOverUnder.predictProbability([inputOU], 2)[0] as any;
      const rfProbsBTTS_raw = models.classifierBTTS.predictProbability([inputBTTS], 2)[0] as any;

      const getSafeProb = (arr: any, index: number) => {
        if (!arr || typeof arr[index] !== 'number' || isNaN(arr[index])) return 0;
        return arr[index];
      };

      const rfHomeWin = getSafeProb(rfProbs1X2_raw, 0);
      const rfDraw = getSafeProb(rfProbs1X2_raw, 1);
      const rfAwayWin = getSafeProb(rfProbs1X2_raw, 2);

      const rfOver25 = getSafeProb(rfProbsOU_raw, 1);
      const rfUnder25 = getSafeProb(rfProbsOU_raw, 0);

      const rfBTTSYes = getSafeProb(rfProbsBTTS_raw, 1);
      const rfBTTSNo = getSafeProb(rfProbsBTTS_raw, 0);

      // 2. Poisson Predictions (Weighted by avgXG)
      const homeExpGoals = (homeStats.avgHomeGoalsScored + homeStats.avgXG + awayStats.avgAwayGoalsConceded) / 3;
      const awayExpGoals = (awayStats.avgAwayGoalsScored + awayStats.avgXG + homeStats.avgHomeGoalsConceded) / 3;
      const poissonResult = calculatePoisson(homeExpGoals, awayExpGoals);

      // 3. Dynamic Blending (Phase 3 Improvement)
      // Logic: 
      // - If we have a League-Specific model, it's more reliable -> More RF weight.
      // - If H2H is high -> More RF weight.
      // - If data is scarce -> More Poisson weight.
      let rfWeight = 0.55; // Baseline
      if (isLeagueModel) rfWeight += 0.1;
      if (h2h.totalMatches >= 4) rfWeight += 0.1;
      if (h2h.totalMatches === 0) rfWeight -= 0.1;

      // Clamp weights
      rfWeight = Math.max(0.4, Math.min(0.85, rfWeight));
      const poissonWeight = 1 - rfWeight;

      // Final Blended probabilities
      const homeWin = (rfHomeWin * rfWeight) + (poissonResult.homeWin * poissonWeight);
      const draw = (rfDraw * rfWeight) + (poissonResult.draw * poissonWeight);
      const awayWin = (rfAwayWin * rfWeight) + (poissonResult.awayWin * poissonWeight);

      const blendedProbs = {
        homeWin: homeWin || 0.33,
        draw: draw || 0.34,
        awayWin: awayWin || 0.33,
        over25: ((rfOver25 * rfWeight) + (poissonResult.over25 * poissonWeight)) || 0.5,
        under25: ((rfUnder25 * rfWeight) + (poissonResult.under25 * poissonWeight)) || 0.5,
        bttsYes: ((rfBTTSYes * rfWeight) + (poissonResult.bttsYes * poissonWeight)) || 0.5,
        bttsNo: ((rfBTTSNo * rfWeight) + (poissonResult.bttsNo * poissonWeight)) || 0.5,
        doubleChance1X: (homeWin + draw) || 0.67,
        doubleChance12: (homeWin + awayWin) || 0.66,
        doubleChanceX2: (draw + awayWin) || 0.67
      };

      // 4. Confidence Calibration (Phase 3 Improvement)
      // High confidence if:
      // - ML and Poisson agree on the outcome
      // - One probability is significantly higher than others (> 60%)
      // - Data density is high (League model + H2H)
      
      const maxProb = Math.max(blendedProbs.homeWin, blendedProbs.draw, blendedProbs.awayWin);
      let outcome = 1;
      if (maxProb === blendedProbs.homeWin) outcome = 0;
      else if (maxProb === blendedProbs.awayWin) outcome = 2;

      // Check if Poisson agrees
      const poissonMax = Math.max(poissonResult.homeWin, poissonResult.draw, poissonResult.awayWin);
      let poissonOutcome = 1;
      if (poissonMax === poissonResult.homeWin) poissonOutcome = 0;
      else if (poissonMax === poissonResult.awayWin) poissonOutcome = 2;

      const modelsAgree = outcome === poissonOutcome;
      let confidenceBoost = 0;
      if (modelsAgree) confidenceBoost += 0.15;
      if (isLeagueModel) confidenceBoost += 0.1;
      if (maxProb > 0.65) confidenceBoost += 0.1;

      // Determine Analysis and add "Confidence" tag
      let analysis: string = "";
      const confidenceLevel = Math.min(95, Math.round((maxProb + confidenceBoost) * 100));
      
      analysis += `[Confiança: ${confidenceLevel}%] `;

      if (h2h.totalMatches >= 3) {
        const dominance = h2h.homeWins > h2h.awayWins ? match.homeTeam.name : match.awayTeam.name;
        if (h2h.homeWins !== h2h.awayWins) {
          analysis += `Histórico H2H favorável ao ${dominance}. `;
        }
      }

      if (homeStats.avgXG > 1.8) analysis += `${match.homeTeam.name} tem alta criação de jogadas (xG ${homeStats.avgXG.toFixed(1)}). `;
      
      if (outcome === 0) {
        analysis += `${match.homeTeam.name} é favorito com forte momentum em casa. `;
      } else if (outcome === 2) {
        analysis += `${match.awayTeam.name} apresenta melhor desempenho recente como visitante. `;
      } else {
        analysis += "Confronto de alto equilíbrio tático. ";
      }

      return {
        outcome: outcome,
        probabilities: blendedProbs,
        analysis: analysis.trim(),
        exactScores: poissonResult.exactScores
      };
    } catch (error) {
      console.error('[PredictionEngine] Error generating prediction:', error);
      return null;
    }
  }
}
