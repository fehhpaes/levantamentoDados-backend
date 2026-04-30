import { RandomForestClassifier } from 'ml-random-forest';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';

export class PredictionEngine {
  private classifier: RandomForestClassifier;

  constructor() {
    this.classifier = new RandomForestClassifier({
      nEstimators: 150, // Slightly more estimators for complexity
      seed: 42
    });
  }

  /**
   * Trains the model using finished matches from the database.
   * Enhances features with moving averages of goals and form.
   */
  async trainModel() {
    const historicalData = await Match.find({ status: 'FINISHED' }).sort({ date: 1 });

    if (historicalData.length < 20) {
      console.warn('Insufficient data (need at least 20 finished matches) to train the refined model.');
      return;
    }

    const trainingFeatures: number[][] = [];
    const labels: number[] = [];

    for (let i = 0; i < historicalData.length; i++) {
      const match = historicalData[i];
      
      // Get stats of the teams *before* this match was played
      // (This is an approximation using the current helper which looks at last 5)
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

      // Label: 0=Home, 1=Draw, 2=Away
      if (match.score.home > match.score.away) labels.push(0);
      else if (match.score.home === match.score.away) labels.push(1);
      else labels.push(2);
    }

    this.classifier.train(trainingFeatures, labels);
    console.log(`Refined model trained with ${trainingFeatures.length} matches and 10 features.`);
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
        awayStats.avgShotsOnTarget,
        homeStats.avgGoalsScored,
        homeStats.avgGoalsConceded,
        awayStats.avgGoalsScored,
        awayStats.avgGoalsConceded,
        homeStats.formPoints,
        awayStats.formPoints
      ];

      const prediction = this.classifier.predict([predictionInput])[0];
      
      // predictProbability expects (features, numberOfClasses)
      const probabilitiesArray = this.classifier.predictProbability([predictionInput], 3);
      const probabilities = (probabilitiesArray[0] as unknown) as number[];

      match.prediction = {
        outcome: Number(prediction),
        probabilities: {
          homeWin: probabilities[0] || 0,
          draw: probabilities[1] || 0,
          awayWin: probabilities[2] || 0
        }
      };

      await match.save();
    }
    console.log(`Predictions updated for ${scheduledMatches.length} matches.`);
  }
}
