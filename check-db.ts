import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from './src/models/Match.js';

dotenv.config();

async function checkDatabase() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(process.env.MONGODB_URL!);
    console.log('Connected.');

    const count = await Match.countDocuments();
    console.log(`Total Matches in Database: ${count}`);

    const today = new Date();
    const startTime = new Date(today.getTime() - 3 * 60 * 60 * 1000);
    const endTime = new Date(today.getTime() + 21 * 60 * 60 * 1000);

    const todayMatches = await Match.find({
      date: { $gte: startTime, $lt: endTime }
    });
    console.log(`Matches for "Today" window: ${todayMatches.length}`);

    if (todayMatches.length > 0) {
      console.log('Sample match:', JSON.stringify(todayMatches[0], null, 2));
    }

    const leagues = await Match.distinct('league.name');
    console.log('Leagues available:', leagues);

    await mongoose.disconnect();
  } catch (error) {
    console.error('Error checking database:', error);
  }
}

checkDatabase();
