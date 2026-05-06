import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";

async function forceUpdate() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(directUrl);
    
    const match = await Match.findOne({
      'homeTeam.name': { $regex: /Rosario/i },
      'awayTeam.name': { $regex: /Libertad/i }
    });

    if (match) {
      console.log(`Updating match: ${match.homeTeam.name} vs ${match.awayTeam.name}`);
      
      match.status = 'FINISHED';
      match.score = { home: 1, away: 0 };
      match.stats = {
        home_possession: 55,
        away_possession: 45,
        home_shots_on_target: 4,
        away_shots_on_target: 2
      };

      await match.save();
      console.log('✅ Match updated successfully to FINISHED (1-0)');
    } else {
      console.log('Match not found.');
    }
  } catch (e: any) {
    console.error(e.message);
  } finally {
    await mongoose.connection.close();
  }
}

forceUpdate();
