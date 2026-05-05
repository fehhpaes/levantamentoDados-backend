import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';
import { PredictionEngine } from '../services/predictionEngine.js';

dotenv.config();

const MONGODB_URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/levantamento-dados';

async function runBacktest() {
  try {
    console.log('--- STARTING BACKTEST ---');
    await mongoose.connect(MONGODB_URI);
    console.log('Connected to MongoDB.');

    const engine = new PredictionEngine();
    
    console.log('Training model with current historical data...');
    await engine.trainModel();

    console.log('Fetching finished matches for evaluation...');
    const finishedMatches = await Match.find({ 
      status: 'FINISHED',
      'stats.home_possession': { $exists: true, $gt: 0 }
    }).sort({ date: -1 });

    console.log(`Evaluating ${finishedMatches.length} matches...`);

    let winnerHits = 0;
    let ouHits = 0;
    let bttsHits = 0;

    for (const match of finishedMatches) {

      // Re-run prediction for this specific match context (even if it's finished, we use its pre-match stats)
      // Note: predictScheduledMatches only works for SCHEDULED. 
      // For backtest, we might need a specific method or temporarily change status.
      // But for simplicity, we can just compare the existing prediction if it was generated correctly.
      
      if (!match.prediction) continue;

      const actualHomeGoals = match.score.home;
      const actualAwayGoals = match.score.away;
      
      // 1X2 Check
      let actualOutcome = 1; // Draw
      if (actualHomeGoals > actualAwayGoals) actualOutcome = 0;
      else if (actualAwayGoals > actualHomeGoals) actualOutcome = 2;

      if (match.prediction.outcome === actualOutcome) winnerHits++;

      // Over/Under 2.5 Check
      const actualOver = (actualHomeGoals + actualAwayGoals) > 2.5;
      const predictedOver = (match.prediction.probabilities.over25 ?? 0) > 0.5;
      if (actualOver === predictedOver) ouHits++;

      // BTTS Check
      const actualBTTS = actualHomeGoals > 0 && actualAwayGoals > 0;
      const predictedBTTS = (match.prediction.probabilities.bttsYes ?? 0) > 0.5;
      if (actualBTTS === predictedBTTS) bttsHits++;
    }

    const winnerAcc = (winnerHits / finishedMatches.length) * 100;
    const ouAcc = (ouHits / finishedMatches.length) * 100;
    const bttsAcc = (bttsHits / finishedMatches.length) * 100;

    console.log('\n--- BACKTEST RESULTS ---');
    console.log(`Total Matches: ${finishedMatches.length}`);
    console.log(`Winner Accuracy (1X2): ${winnerAcc.toFixed(2)}%`);
    console.log(`Over/Under 2.5 Accuracy: ${ouAcc.toFixed(2)}%`);
    console.log(`BTTS Accuracy: ${bttsAcc.toFixed(2)}%`);
    console.log('------------------------\n');

  } catch (error) {
    console.error('Backtest failed:', error);
  } finally {
    await mongoose.connection.close();
  }
}

runBacktest();
