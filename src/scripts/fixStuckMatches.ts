import mongoose from 'mongoose';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';
import { FootballDataService } from '../services/footballData.js';

dotenv.config();

const directUrl = "mongodb://admin:admin@ac-wkmycvl-shard-00-00.8gassal.mongodb.net:27017/sports_data?authSource=admin&ssl=true";

async function fixStuckMatches() {
  try {
    console.log('Connecting to MongoDB...');
    await mongoose.connect(directUrl);
    console.log('Connected!');

    const footballDataService = new FootballDataService();
    
    // Yesterday range
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    const dateStr = yesterday.toISOString().split('T')[0];

    console.log(`Checking for stuck matches on date: ${dateStr}`);

    const stuckMatches = await Match.find({
      status: 'SCHEDULED',
      date: {
        $gte: new Date(dateStr + 'T00:00:00Z'),
        $lte: new Date(dateStr + 'T23:59:59Z')
      }
    });

    console.log(`Found ${stuckMatches.length} stuck matches from yesterday.`);

    if (stuckMatches.length > 0) {
      console.log('Syncing yesterday matches from API to fix status...');
      await footballDataService.fetchAndSyncMatches(dateStr, dateStr);
      
      // Verify again after sync
      const remaining = await Match.countDocuments({
        status: 'SCHEDULED',
        date: {
          $gte: new Date(dateStr + 'T00:00:00Z'),
          $lte: new Date(dateStr + 'T23:59:59Z')
        }
      });
      console.log(`Remaining stuck matches after sync: ${remaining}`);
    } else {
      console.log('No stuck matches found in the database for yesterday.');
      
      // Check for any match from yesterday to see if they exist at all
      const anyMatch = await Match.findOne({
         date: {
          $gte: new Date(dateStr + 'T00:00:00Z'),
          $lte: new Date(dateStr + 'T23:59:59Z')
        }
      });
      if (!anyMatch) {
        console.log('No matches at all found for yesterday. Running full sync for yesterday...');
        await footballDataService.fetchAndSyncMatches(dateStr, dateStr);
      }
    }

  } catch (error: any) {
    console.error('Fix failed:', error.message);
  } finally {
    await mongoose.connection.close();
  }
}

fixStuckMatches();
