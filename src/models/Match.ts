import mongoose, { Schema, Document } from 'mongoose';

export interface IMatch extends Document {
  fixture_id: number;
  date: Date;
  status: 'SCHEDULED' | 'FINISHED';
  league: { id: number; name: string; logo?: string };
  homeTeam: { id: number; name: string };
  awayTeam: { id: number; name: string };
  score: { home: number; away: number };
  stats?: {
    home_possession: number;
    away_possession: number;
    home_shots_on_target: number;
    away_shots_on_target: number;
  };
  prediction?: {
    outcome: number;
    probabilities: {
      homeWin: number;
      draw: number;
      awayWin: number;
    };
    analysis?: string;
  };
}

const MatchSchema: Schema = new Schema({
  fixture_id: { type: Number, required: true, unique: true },
  date: { type: Date, required: true },
  status: { type: String, enum: ['SCHEDULED', 'FINISHED'], required: true },
  league: {
    id: { type: Number, required: true },
    name: { type: String, required: true },
    logo: String
  },
  homeTeam: {
    id: { type: Number, required: true },
    name: { type: String, required: true }
  },
  awayTeam: {
    id: { type: Number, required: true },
    name: { type: String, required: true }
  },
  score: {
    home: { type: Number, default: 0 },
    away: { type: Number, default: 0 }
  },
  stats: {
    home_possession: Number,
    away_possession: Number,
    home_shots_on_target: Number,
    away_shots_on_target: Number
  },
  prediction: {
    outcome: Number,
    probabilities: {
      homeWin: Number,
      draw: Number,
      awayWin: Number
    },
    analysis: String
  }
});

export const Match = mongoose.model<IMatch>('Match', MatchSchema);
