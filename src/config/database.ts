import mongoose from 'mongoose';
import dotenv from 'dotenv';

dotenv.config();

const MONGODB_URL = process.env.MONGODB_URL;
const MONGODB_DATABASE = process.env.MONGODB_DATABASE || 'sports_data';

export const connectDB = async () => {
  if (!MONGODB_URL) {
    console.error('MONGODB_URL is not defined in .env');
    process.exit(1);
  }

  try {
    await mongoose.connect(MONGODB_URL, {
      dbName: MONGODB_DATABASE
    });
    console.log(`MongoDB connected to cluster: ${MONGODB_DATABASE}`);
  } catch (error) {
    console.error('MongoDB connection error:', error);
    process.exit(1);
  }
};
