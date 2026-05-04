import { connectDB } from '../config/database.js';
import { FootballDataService } from '../services/footballData.js';
import mongoose from 'mongoose';

const footballDataService = new FootballDataService();

async function testFootballData() {
  await connectDB();
  console.log('--- Testing Football-Data.org Connectivity ---');
  
  try {
    const today = new Date();
    const dateTo = today.toISOString().split('T')[0];
    const pastDate = new Date(today.getTime() - 60 * 24 * 60 * 60 * 1000); // 60 days ago
    const dateFrom = pastDate.toISOString().split('T')[0];
    
    console.log(`Testing fetchAndSyncMatches from ${dateFrom} to ${dateTo}...`);
    // Testing specific competition, e.g., 'PL' (Premier League)
    await footballDataService.syncCompetitionMatches('PL', dateFrom, dateTo);
    
    console.log('--- Football-Data Test Completed ---');
  } catch (error: any) {
    console.error('Football-Data Test failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

testFootballData();

