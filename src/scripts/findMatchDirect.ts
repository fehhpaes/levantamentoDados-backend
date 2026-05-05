import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

// Try direct connection to one of the shards if SRV fails
const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";

async function findMatch() {
  try {
    console.log('Connecting to MongoDB (Direct Shard)...');
    await mongoose.connect(directUrl);
    console.log('Connected!');

    const matches = await Match.find({
      'league.id': 2152, // Copa Libertadores
      date: {
        $gte: new Date('2026-05-05T00:00:00Z'),
        $lte: new Date('2026-05-06T23:59:59Z') // Include tomorrow as well
      }
    }).sort({ date: 1 });

    if (matches.length > 0) {
      console.log(`Found ${matches.length} Libertadores matches:`);
      matches.forEach(m => {
        console.log(`${m.date.toISOString()} - ${m.homeTeam.name} vs ${m.awayTeam.name} [${m.status}]`);
        if (m.prediction && m.prediction.analysis) {
          console.log(`  Prediction: ${m.prediction.analysis}`);
        } else {
          console.log('  No prediction analysis found.');
        }
      });
    } else {
      console.log('No Libertadores matches found in DB for the specified range.');
    }
  } catch (error: any) {
    console.error('Connection failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

findMatch();
