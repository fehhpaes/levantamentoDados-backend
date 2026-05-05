import mongoose, { Schema, Document } from 'mongoose';

export interface IVirtualBet extends Document {
  userId: string; // Anonymous device ID or User ID
  fixtureId: number;
  matchInfo: {
    homeTeam: string;
    awayTeam: string;
    league: string;
    date: Date;
  };
  market: '1X2' | 'OVER_UNDER_2.5' | 'BTTS';
  selection: 'HOME' | 'DRAW' | 'AWAY' | 'OVER' | 'UNDER' | 'YES' | 'NO';
  odds: number;
  stake: number;
  potentialReturn: number;
  status: 'PENDING' | 'WON' | 'LOST' | 'REFUNDED';
  result?: {
    homeScore: number;
    awayScore: number;
  };
  createdAt: Date;
}

const VirtualBetSchema: Schema = new Schema({
  userId: { type: String, required: true, index: true },
  fixtureId: { type: Number, required: true },
  matchInfo: {
    homeTeam: { type: String, required: true },
    awayTeam: { type: String, required: true },
    league: { type: String, required: true },
    date: { type: Date, required: true }
  },
  market: { type: String, enum: ['1X2', 'OVER_UNDER_2.5', 'BTTS'], required: true },
  selection: { type: String, required: true },
  odds: { type: Number, required: true },
  stake: { type: Number, required: true },
  potentialReturn: { type: Number, required: true },
  status: { type: String, enum: ['PENDING', 'WON', 'LOST', 'REFUNDED'], default: 'PENDING' },
  result: {
    homeScore: Number,
    awayScore: Number
  },
  createdAt: { type: Date, default: Date.now }
});

export const VirtualBet = mongoose.model<IVirtualBet>('VirtualBet', VirtualBetSchema);
