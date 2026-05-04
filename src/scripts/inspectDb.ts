import { connectDB } from '../config/database.js';
import { Match } from '../models/Match.js';
import mongoose from 'mongoose';

async function inspect() {
  await connectDB();
  const match = await Match.findOne();
  console.log('Sample Match:', JSON.stringify(match, null, 2));
  
  const leagues = await Match.aggregate([
    {
      $group: {
        _id: '$league.id',
        name: { $first: '$league.name' }
      }
    }
  ]);
  console.log('Leagues found:', leagues);
  
  await mongoose.connection.close();
}

inspect();
