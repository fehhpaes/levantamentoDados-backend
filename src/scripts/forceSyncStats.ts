import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';
import { SportmonksService } from '../services/sportmonks.js';

dotenv.config();

const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";

async function forceSyncStats() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(directUrl);
    console.log('Connected!');

    const sportmonksService = new SportmonksService();

    // Buscar partidas de ontem e hoje que estão finalizadas mas sem stats
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0,0,0,0);

    const matches = await Match.find({
      status: 'FINISHED',
      date: { $gte: yesterday },
      $or: [
        { stats: { $exists: false } },
        { 'stats.home_possession': 0 }
      ]
    });

    console.log(`Found ${matches.length} matches to update stats for.`);

    for (const match of matches) {
      console.log(`Processing: ${match.homeTeam.name} vs ${match.awayTeam.name} (${match.date.toISOString()})`);
      await sportmonksService.syncStatsByMatch(match);
      // Pequeno delay para evitar rate limit se houver muitos
      await new Promise(resolve => setTimeout(resolve, 1000));
    }

    console.log('--- Force Sync Stats Finished ---');
  } catch (error: any) {
    console.error('Failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

forceSyncStats();
