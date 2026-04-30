import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';

export class PredictionEngine {
  private classifier: RandomForestClassifier;

  constructor() {
    this.classifier = new RandomForestClassifier({
      nEstimators: 100,
      maxDepth: 10,
      seed: 42
    });
  }

  /**
   * Trains the model using finished matches from the database.
   */
  async trainModel() {
    const historicalData = await Match.find({ status: 'FINISHED' });

    if (historicalData.length < 10) {
      console.warn('Insufficient data to train a robust model.');
      return;
    }

    const trainingFeatures = historicalData.map(m => [
      m.stats?.home_possession || 50,
      m.stats?.away_possession || 50,
      m.stats?.home_shots_on_target || 4,
      m.stats?.away_shots_on_target || 4
    ]);

    // Labels: 0 = Home Win, 1 = Draw, 2 = Away Win
    const labels = historicalData.map(m => {
      if (m.score.home > m.score.away) return 0;
      if (m.score.home === m.score.away) return 1;
      return 2;
    });

    this.classifier.train(trainingFeatures, labels);
    console.log('Model trained successfully.');
  }

  /**
   * Predicts outcome for scheduled matches using moving averages.
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
        awayStats.avgShotsOnTarget
      ];

      const prediction = this.classifier.predict([predictionInput])[0];
      const probabilities = this.classifier.predictProbability([predictionInput])[0] as number[];

      // Update match document with prediction
      match.prediction = {
        outcome: prediction as number,
        probabilities: {
          homeWin: probabilities[0] || 0,
          draw: probabilities[1] || 0,
          awayWin: probabilities[2] || 0
        }
      };

      await match.save();
    }
  }
}
