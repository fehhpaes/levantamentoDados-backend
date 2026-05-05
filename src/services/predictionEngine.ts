import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { calculatePoisson } from '../utils/poisson.js';
import { getIO } from './socket.js';

export class PredictionEngine {
  private classifier1X2: RandomForestClassifier;
  private classifierOverUnder: RandomForestClassifier;
  private classifierBTTS: RandomForestClassifier;

  constructor() {
    const config = {
      nEstimators: 200, // Increased for better stability
      seed: 42
    };
    this.classifier1X2 = new RandomForestClassifier(config);
    this.classifierOverUnder = new RandomForestClassifier(config);
    this.classifierBTTS = new RandomForestClassifier(config);
  }

  /**
   * Trains the models using finished matches from the database.
   */
  async trainModel() {
    const historicalData = await Match.find({ status: 'FINISHED' }).sort({ date: 1 });

    if (historicalData.length < 20) {
      console.warn('Insufficient data (need at least 20 finished matches) to train the models.');
      return;
    }

    const trainingFeatures: number[][] = [];
    const labels1X2: number[] = [];
    const labelsOU: number[] = [];
    const labelsBTTS: number[] = [];

    for (let i = 0; i < historicalData.length; i++) {
      const match = historicalData[i];
      const homeStats = await getTeamMovingAverage(match.homeTeam.id);
      const awayStats = await getTeamMovingAverage(match.awayTeam.id);

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

    this.classifier1X2.train(trainingFeatures, labels1X2);
    this.classifierOverUnder.train(trainingFeatures, labelsOU);
    this.classifierBTTS.train(trainingFeatures, labelsBTTS);
    
    console.log(`Models trained with ${trainingFeatures.length} matches.`);
  }

  /**
   * Predicts outcomes for scheduled matches.
   */
  async predictScheduledMatches() {
    const scheduledMatches = await Match.find({ status: 'SCHEDULED' });

    for (const match of scheduledMatches) {
      const homeStats = await getTeamMovingAverage(match.homeTeam.id);
      const awayStats = await getTeamMovingAverage(match.awayTeam.id);

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

      // 1. ML Predictions (Random Forest)
      const rfProbs1X2 = (this.classifier1X2.predictProbability([predictionInput], 3)[0] as unknown) as number[];
      const rfProbsOU = (this.classifierOverUnder.predictProbability([predictionInput], 2)[0] as unknown) as number[];
      const rfProbsBTTS = (this.classifierBTTS.predictProbability([predictionInput], 2)[0] as unknown) as number[];

      // 2. Poisson Predictions
      // Simplified xG: Avg Goals Scored by Home + Avg Goals Conceded by Away / 2
      const homeExpGoals = (homeStats.avgHomeGoalsScored + awayStats.avgAwayGoalsConceded) / 2;
      const awayExpGoals = (awayStats.avgAwayGoalsScored + homeStats.avgHomeGoalsConceded) / 2;
      const poissonProbs = calculatePoisson(homeExpGoals, awayExpGoals);

      // 3. Blending (Weighted Average)
      const rfWeight = 0.6;
      const poissonWeight = 0.4;

      const blendedProbs = {
        homeWin: (rfProbs1X2[0] * rfWeight) + (poissonProbs.homeWin * poissonWeight),
        draw: (rfProbs1X2[1] * rfWeight) + (poissonProbs.draw * poissonWeight),
        awayWin: (rfProbs1X2[2] * rfWeight) + (poissonProbs.awayWin * poissonWeight),
        over25: (rfProbsOU[1] * rfWeight) + (poissonProbs.over25 * poissonWeight),
        under25: (rfProbsOU[0] * rfWeight) + (poissonProbs.under25 * poissonWeight),
        bttsYes: (rfProbsBTTS[1] * rfWeight) + (poissonProbs.bttsYes * poissonWeight),
        bttsNo: (rfProbsBTTS[0] * rfWeight) + (poissonProbs.bttsNo * poissonWeight),
      };

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

      match.prediction = {
        outcome: outcome,
        probabilities: {
          homeWin: blendedProbs.homeWin,
          draw: blendedProbs.draw,
          awayWin: blendedProbs.awayWin,
          over25: blendedProbs.over25,
          under25: blendedProbs.under25,
          bttsYes: blendedProbs.bttsYes,
          bttsNo: blendedProbs.bttsNo
        },
        analysis: analysis
      };

      await match.save();

      try {
        const io = getIO();
        io.emit('matchUpdated', match);
      } catch (socketError) {
        console.error('[PredictionEngine] Socket emit error:', socketError);
      }
    }
    console.log(`Blended AI predictions updated for ${scheduledMatches.length} matches.`);
  }
}
