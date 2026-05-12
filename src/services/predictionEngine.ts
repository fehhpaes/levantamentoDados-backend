import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
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
      nEstimators: 200,
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
    const trainingFeatures: number[][] = [];
    const labels1X2: number[] = [];
    const labelsOU: number[] = [];
    const labelsBTTS: number[] = [];

    for (const match of matches) {
      const homeStats = await getTeamMovingAverage(match.homeTeam.id);
      const awayStats = await getTeamMovingAverage(match.awayTeam.id);

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

      const features = [
        match.stats?.home_possession || homeStats.avgPossession,
        match.stats?.away_possession || awayStats.avgPossession,
        match.stats?.home_shots_on_target || homeStats.avgShotsOnTarget,
        match.stats?.away_shots_on_target || awayStats.avgShotsOnTarget,
        homeStats.avgGoalsScored,
        homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored,
        awayStats.avgGoalsConceded,
        homeStats.avgHomeGoalsScored,
        homeStats.avgHomeGoalsConceded,
        awayStats.avgAwayGoalsScored,
        awayStats.avgAwayGoalsConceded,
        homeStats.formPoints,
        awayStats.formPoints
      ];

      trainingFeatures.push(features);

      // Label 1X2: 0=Home, 1=Draw, 2=Away
      if (match.score.home > match.score.away) labels1X2.push(0);
      else if (match.score.home === match.score.away) labels1X2.push(1);
      else labels1X2.push(2);

      // Label Over/Under 2.5: 0=Under, 1=Over
      labelsOU.push((match.score.home + match.score.away) > 2.5 ? 1 : 0);

      // Label BTTS: 0=No, 1=Yes
      labelsBTTS.push((match.score.home > 0 && match.score.away > 0) ? 1 : 0);
    }

    models.classifier1X2.train(trainingFeatures, labels1X2);
    models.classifierOverUnder.train(trainingFeatures, labelsOU);
    models.classifierBTTS.train(trainingFeatures, labelsBTTS);
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

      const predictionInput = [
        homeStats.avgPossession,
        awayStats.avgPossession,
        homeStats.avgShotsOnTarget,
        awayStats.avgShotsOnTarget,
        homeStats.avgGoalsScored,
        homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored,
        awayStats.avgGoalsConceded,
        homeStats.avgHomeGoalsScored,
        homeStats.avgHomeGoalsConceded,
        awayStats.avgAwayGoalsScored,
        awayStats.avgAwayGoalsConceded,
        homeStats.formPoints,
        awayStats.formPoints
      ];

      // Select model (League-specific or Global)
      const models = this.leagueModels.get(match.league.id) || this.globalModels;

      // 1. ML Predictions (Random Forest)
      // We need to handle cases where the model might not return all 3 probabilities (0, 1, 2)
      // because it might not have seen all outcomes during training.
      const rfProbs1X2_raw = models.classifier1X2.predictProbability([predictionInput], 3)[0] as any;
      const rfProbsOU_raw = models.classifierOverUnder.predictProbability([predictionInput], 2)[0] as any;
      const rfProbsBTTS_raw = models.classifierBTTS.predictProbability([predictionInput], 2)[0] as any;

      // Helper to safely get probability for a specific label
      // Random Forest model in ml-random-forest stores unique labels seen in training.
      // If trained only on [0, 2], index 0 is Home, index 1 is Away.
      // This is complex to map without knowing the internal labels.
      // For now, we'll assume standard [0, 1, 2] and use 0 as fallback if missing/NaN.
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

      // 2. Poisson Predictions
      const homeExpGoals = (homeStats.avgHomeGoalsScored + awayStats.avgAwayGoalsConceded) / 2;
      const awayExpGoals = (awayStats.avgAwayGoalsScored + homeStats.avgHomeGoalsConceded) / 2;
      const poissonResult = calculatePoisson(homeExpGoals, awayExpGoals);

      // 3. Blending (Weighted Average)
      const rfWeight = 0.6;
      const poissonWeight = 0.4;

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

      // Double check for any remaining NaNs in blendedProbs
      Object.keys(blendedProbs).forEach(key => {
        const k = key as keyof typeof blendedProbs;
        if (isNaN(blendedProbs[k])) {
           // @ts-ignore
          blendedProbs[k] = 0.5; // Final safe fallback
        }
      });

      // Determine Outcome from Blended Probs
      let outcome = 1; // Default Draw
      const maxProb = Math.max(blendedProbs.homeWin, blendedProbs.draw, blendedProbs.awayWin);
      if (maxProb === blendedProbs.homeWin) outcome = 0;
      else if (maxProb === blendedProbs.awayWin) outcome = 2;

      // Generate Analysis Text
      let analysis: string;
      if (outcome === 0) {
        analysis = `${match.homeTeam.name} é favorito em casa com ${homeStats.avgHomeGoalsScored.toFixed(1)} gols/jogo em casa. `;
      } else if (outcome === 2) {
        analysis = `${match.awayTeam.name} tem melhor momentum como visitante. `;
      } else {
        analysis = "Confronto equilibrado com forte tendência ao empate. ";
      }

      if (blendedProbs.over25 > 0.6) analysis += "Grande probabilidade de um jogo aberto (+2.5). ";
      if (blendedProbs.bttsYes > 0.6) analysis += "Ambas as equipes devem marcar. ";

      return {
        outcome: outcome,
        probabilities: blendedProbs,
        analysis: analysis,
        exactScores: poissonResult.exactScores
      };
    } catch (error) {
      console.error('[PredictionEngine] Error generating prediction:', error);
      return null;
    }
  }
}
