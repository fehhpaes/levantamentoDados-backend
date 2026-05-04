import mongoose, { Schema, Document } from 'mongoose';

export interface ITeamTest extends Document {
  name: string;
  code: string;
  testDate: Date;
}

const TeamTestSchema: Schema = new Schema({
  name: { type: String, required: true },
  code: { type: String, required: true, unique: true },
  testDate: { type: Date, default: Date.now }
});

export const TeamTest = mongoose.model<ITeamTest>('TeamTest', TeamTestSchema);
