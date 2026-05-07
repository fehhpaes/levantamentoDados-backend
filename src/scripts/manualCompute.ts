import { connectDB } from '../config/database.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

async function manualCompute() {
  const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";
  const competitions = ['BSA', 'PL', 'PD', 'BL1', 'SA', 'FL1', 'CL', 'CLI'];
  
  try {
    console.log('Connecting to MongoDB (Direct Shard)...');
    await mongoose.connect(directUrl);
    console.log('Connected!');
    
    const footballDataService = new FootballDataService();
    const predictionEngine = new PredictionEngine();
    const today = new Date().toISOString().split('T')[0];

    console.log('--- Starting Global Manual Sync ---');

    // 1. Sync all competitions
    for (const code of competitions) {
      console.log(`Step 1: Syncing ${code} for ${today}...`);
      await footballDataService.syncCompetitionMatches(code, today, today);
    }

    // 2. General sync for other leagues
    console.log('Step 2: Running general today sync...');
    await footballDataService.syncTodayMatches();

    // 3. Train Models
    console.log('Step 3: Training AI Models...');
    await predictionEngine.trainModel();

    // 4. Generate Predictions
    console.log('Step 4: Generating Predictions for all scheduled matches...');
    await predictionEngine.predictScheduledMatches();

    console.log('--- Global Manual Sync Finished Successfully ---');
  
  } catch (error: any) {
    console.error('Manual Compute failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

manualCompute();
