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

    const match = await Match.findOne({ fixture_id: 552095 });

    if (match) {
      console.log('Match details from DB:');
      console.log(JSON.stringify(match, null, 2));
    } else {
      console.log('Specific Arsenal vs Atleti match for today not found in DB.');
    }
  } catch (error: any) {
    console.error('Connection failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

findMatch();
