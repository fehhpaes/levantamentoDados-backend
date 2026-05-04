import { connectDB } from '../config/database.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import mongoose from 'mongoose';

const footballDataService = new FootballDataService();
const predictionEngine = new PredictionEngine();

async function runSeed() {
  await connectDB();

  console.log('--- Seeding Historical Data ---');
  
  const today = new Date();
  const dateTo = today.toISOString().split('T')[0];
  const pastDate = new Date(today.getTime() - 60 * 24 * 60 * 60 * 1000); // 60 days ago
  const dateFrom = pastDate.toISOString().split('T')[0];

  const competitions = ['PL', 'BSA', 'PD', 'BL1', 'SA', 'FL1'];
  
  for (const comp of competitions) {
    console.log(`Syncing ${comp} from ${dateFrom} to ${dateTo}...`);
    await footballDataService.syncCompetitionMatches(comp, dateFrom, dateTo);
    // Add a delay to respect API rate limits (10 requests per minute)
    await new Promise(resolve => setTimeout(resolve, 6500));
  }

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
