import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";

async function analyzeAccuracy() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(directUrl);
    
    const finishedMatches = await Match.find({
      status: 'FINISHED',
      date: {
        $gte: new Date('2026-05-05T00:00:00Z'),
        $lte: new Date('2026-05-05T23:59:59Z')
      }
    });

    if (finishedMatches.length === 0) {
      console.log('No finished matches found for today.');
      return;
    }

    console.log(`\n--- Prediction Accuracy Analysis (${finishedMatches.length} matches) ---\n`);

    finishedMatches.forEach(m => {
      const homeScore = m.score.home;
      const awayScore = m.score.away;
      
      let actualOutcome; // 0: Home, 1: Draw, 2: Away
      if (homeScore > awayScore) actualOutcome = 0;
      else if (homeScore === awayScore) actualOutcome = 1;
      else actualOutcome = 2;

      const predictedOutcome = m.prediction?.outcome;
      const analysis = m.prediction?.analysis || 'No analysis';
      const probs = m.prediction?.probabilities;

      const isHit = predictedOutcome === actualOutcome;

      console.log(`Match: ${m.homeTeam.name} ${homeScore} x ${awayScore} ${m.awayTeam.name}`);
      console.log(`Actual Outcome: ${actualOutcome === 0 ? 'HOME' : actualOutcome === 1 ? 'DRAW' : 'AWAY'}`);
      console.log(`Predicted Outcome: ${predictedOutcome === 0 ? 'HOME' : predictedOutcome === 1 ? 'DRAW' : 'AWAY'}`);
      console.log(`Status: ${isHit ? '✅ ACERTOU' : '❌ ERROU'}`);
      console.log(`Analysis: ${analysis}`);
      if (probs) {
        console.log(`Probabilities: H:${(probs.homeWin*100).toFixed(1)}% D:${(probs.draw*100).toFixed(1)}% A:${(probs.awayWin*100).toFixed(1)}%`);
      }
      console.log('-------------------------------------------\n');
    });

  } catch (e: any) {
    console.error(e.message);
  } finally {
    await mongoose.connection.close();
  }
}

analyzeAccuracy();
