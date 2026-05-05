import { SportmonksService } from '../services/sportmonks.js';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

const sportmonksService = new SportmonksService();

async function testSportmonks() {
  try {
    const MONGODB_URL = process.env.MONGODB_URL || 'mongodb://localhost:27017/sports_data';
    await mongoose.connect(MONGODB_URL);
    console.log('Connected to MongoDB');

    const today = new Date().toISOString().split('T')[0];
    console.log(`Testing Sportmonks sync for date: ${today}`);
    
    await sportmonksService.fetchAndSyncMatchesByDate(today);
    
    console.log('Test completed successfully');
  } catch (error) {
    console.error('Test failed:', error);
  } finally {
    await mongoose.disconnect();
  }
}

testSportmonks();
