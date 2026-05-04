import { connectDB } from '../config/database.js';
import { ApiFootballService } from '../services/apiFootball.js';
import mongoose from 'mongoose';

const footballService = new ApiFootballService();

async function testApi() {
  await connectDB();
  console.log('--- Testing API-Football Connectivity ---');
  
  try {
    const testDate = '2024-05-04';
    console.log(`Testing fetchAndSyncMatchesByDate for date: ${testDate}`);
    await footballService.fetchAndSyncMatchesByDate(testDate);
    
    console.log('--- API Test Completed ---');
  } catch (error) {
    console.error('API Test failed:', error);
  } finally {
    await mongoose.connection.close();
  }
}

testApi();
