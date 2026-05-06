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
      'homeTeam.name': { $regex: /Cristal/i },
      'awayTeam.name': { $regex: /Palmeiras/i }
    });

    if (match) {
      console.log(`Updating match: ${match.homeTeam.name} vs ${match.awayTeam.name}`);
      
      match.status = 'FINISHED';
      match.score = { home: 0, away: 2 }; // Sporting Cristal 0 x 2 Palmeiras
      match.stats = {
        home_possession: 42,
        away_possession: 58,
        home_shots_on_target: 3,
        away_shots_on_target: 7
      };

      await match.save();
      console.log('✅ Match updated successfully to FINISHED (0-2)');
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
