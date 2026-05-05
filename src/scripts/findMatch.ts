import { connectDB } from '../config/database.js';
import { Match } from '../models/Match.js';
import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

async function findMatch() {
  await connectDB();
  console.log('Searching for Arsenal vs Atletico...');
  
  const matches = await Match.find({
    $or: [
      { 'homeTeam.name': { $regex: /Arsenal/i } },
      { 'awayTeam.name': { $regex: /Arsenal/i } },
      { 'homeTeam.name': { $regex: /Atletico/i } },
      { 'awayTeam.name': { $regex: /Atletico/i } }
    ]
  }).sort({ date: -1 }).limit(5);

  if (matches.length === 0) {
    console.log('No matches found for Arsenal or Atletico.');
  } else {
    console.log(`Found ${matches.length} matches:`);
    matches.forEach(m => {
      console.log(`${m.date.toISOString()} - ${m.homeTeam.name} vs ${m.awayTeam.name} [${m.status}]`);
      if (m.prediction) {
        console.log(`  Prediction: ${JSON.stringify(m.prediction.probabilities)}`);
      } else {
        console.log('  No prediction found.');
      }
    });
  }
  
  await mongoose.connection.close();
}

findMatch();
