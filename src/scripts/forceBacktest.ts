import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import { connectDB } from '../config/database.js';

dotenv.config();

/**
 * Backtest Script: Runs AI predictions against ALL finished matches
 * to analyze historical accuracy.
 */
async function runFullBacktest() {
  try {
    console.log('--- Starting Full AI Backtest Analysis ---');
    await connectDB();

    const engine = new PredictionEngine();
    
    console.log('[Backtest] Training models with available data...');
    await engine.trainModel();

    const finishedMatches = await Match.find({ 
      status: 'FINISHED'
    }).sort({ date: -1 });

    console.log(`[Backtest] Found ${finishedMatches.length} finished matches to analyze.`);

    let hits1X2 = 0;
    let hitsOU = 0;
    let hitsBTTS = 0;
    let totalOU = 0;
    let totalBTTS = 0;

    for (const match of finishedMatches) {
      // Force run prediction logic
      const result = await engine.generatePrediction(match);
      
      if (result) {
        const homeScore = match.score.home;
        const awayScore = match.score.away;
        
        // 1X2 Check
        let actualOutcome: number;
        if (homeScore > awayScore) actualOutcome = 0;
        else if (homeScore === awayScore) actualOutcome = 1;
        else actualOutcome = 2;

        if (result.outcome === actualOutcome) hits1X2++;

        // OU Check
        if (result.probabilities.over25 !== undefined) {
          totalOU++;
          const predictedOver = result.probabilities.over25 > 0.5;
          const actualOver = (homeScore + awayScore) > 2.5;
          if (predictedOver === actualOver) hitsOU++;
        }

        // BTTS Check
        if (result.probabilities.bttsYes !== undefined) {
          totalBTTS++;
          const predictedBTTS = result.probabilities.bttsYes > 0.5;
          const actualBTTS = homeScore > 0 && awayScore > 0;
          if (predictedBTTS === actualBTTS) hitsBTTS++;
        }

        // Save back the prediction to the match so the History screen reflects it
        match.prediction = result;
        await match.save();
      }
    }

    console.log('\n--- Backtest Results ---');
    console.log(`Total Matches: ${finishedMatches.length}`);
    console.log(`1X2 Accuracy: ${((hits1X2 / finishedMatches.length) * 100).toFixed(2)}% (${hits1X2}/${finishedMatches.length})`);
    console.log(`O/U 2.5 Accuracy: ${((hitsOU / totalOU) * 100).toFixed(2)}% (${hitsOU}/${totalOU})`);
    console.log(`BTTS Accuracy: ${((hitsBTTS / totalBTTS) * 100).toFixed(2)}% (${hitsBTTS}/${totalBTTS})`);
    console.log('------------------------');
    console.log('All finished matches updated with new predictions. Refresh the History screen.');

    process.exit(0);
  } catch (error) {
    console.error('Backtest failed:', error);
    process.exit(1);
  }
}

runFullBacktest();
