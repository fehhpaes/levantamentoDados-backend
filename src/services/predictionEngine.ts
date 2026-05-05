import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { getIO } from './socket.js';

export class PredictionEngine {
  private classifier1X2: RandomForestClassifier;
  private classifierOverUnder: RandomForestClassifier;
  private classifierBTTS: RandomForestClassifier;

  constructor() {
    const config = {
      nEstimators: 150,
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
        homeStats.formPoints,
        awayStats.formPoints
      ];

      // Predict 1X2
      const outcome1X2 = Number(this.classifier1X2.predict([predictionInput])[0]);
      const probs1X2 = (this.classifier1X2.predictProbability([predictionInput], 3)[0] as unknown) as number[];

      // Predict Over/Under
      const probsOU = (this.classifierOverUnder.predictProbability([predictionInput], 2)[0] as unknown) as number[];

      // Predict BTTS
      const probsBTTS = (this.classifierBTTS.predictProbability([predictionInput], 2)[0] as unknown) as number[];

      // Generate Analysis Text
      let analysis = '';
      if (outcome1X2 === 0) {
        analysis = `${match.homeTeam.name} é favorito em casa com ${homeStats.avgGoalsScored.toFixed(1)} gols/jogo. `;
      } else if (outcome1X2 === 2) {
        analysis = `${match.awayTeam.name} tem melhor momentum como visitante. `;
      } else {
        analysis = "Confronto equilibrado com forte tendência ao empate. ";
      }

      if (probsOU[1] > 0.6) analysis += "Grande probabilidade de um jogo aberto com muitos gols (+2.5). ";
      if (probsBTTS[1] > 0.6) analysis += "Ambas as equipes devem marcar. ";

      match.prediction = {
        outcome: outcome1X2,
        probabilities: {
          homeWin: probs1X2[0] || 0,
          draw: probs1X2[1] || 0,
          awayWin: probs1X2[2] || 0,
          over25: probsOU[1] || 0,
          under25: probsOU[0] || 0,
          bttsYes: probsBTTS[1] || 0,
          bttsNo: probsBTTS[0] || 0
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
    console.log(`Multi-market predictions updated for ${scheduledMatches.length} matches.`);
  }
}
