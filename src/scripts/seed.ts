import { connectDB } from '../config/database.js';
import { ApiFootballService } from '../services/apiFootball.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import mongoose from 'mongoose';

const footballService = new ApiFootballService();
const predictionEngine = new PredictionEngine();

async function runSeed() {
  await connectDB();

  console.log('--- Seeding Historical Data ---');
  
  // Premier League (39) - 2023 Season
  await footballService.syncLeagueSeason(39, 2023, 50);
  
  // Brasileirão (71) - 2023 Season
  await footballService.syncLeagueSeason(71, 2023, 50);

  console.log('--- Seeding Completed ---');
  
  console.log('--- Training Model with New Data ---');
  await predictionEngine.trainModel();
  
  console.log('--- Generating New Predictions ---');
  await predictionEngine.predictScheduledMatches();

  console.log('All set! Closing connection...');
  await mongoose.connection.close();
}

runSeed().catch(err => {
  console.error('Seed script failed:', err);
  process.exit(1);
});
