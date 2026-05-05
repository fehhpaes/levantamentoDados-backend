import { connectDB } from '../config/database.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

async function manualCompute() {
  const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";
  const COMP_CODE = 'CLI'; // Copa Libertadores
  
  try {
    console.log('Connecting to MongoDB (Direct Shard)...');
    await mongoose.connect(directUrl);
    console.log('Connected!');
    
    console.log(`--- Manual Computation for ${COMP_CODE} ---`);
  
  const footballDataService = new FootballDataService();
  const predictionEngine = new PredictionEngine();

  const today = new Date().toISOString().split('T')[0];
  console.log(`Step 1: Syncing ${COMP_CODE} for ${today}...`);
  await footballDataService.syncCompetitionMatches(COMP_CODE, today, today);

  console.log('Step 2: Training Models (if possible)...');
  await predictionEngine.trainModel();

  console.log('Step 3: Generating Predictions for Scheduled matches...');
  await predictionEngine.predictScheduledMatches();

  console.log('--- Manual Computation Finished ---');
  
  } catch (error: any) {
    console.error('Manual Compute failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

manualCompute();
