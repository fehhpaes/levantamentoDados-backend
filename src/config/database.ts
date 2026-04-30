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
    console.log('Attempting to connect to MongoDB Atlas...');
    await mongoose.connect(MONGODB_URL, {
      dbName: MONGODB_DATABASE,
      serverSelectionTimeoutMS: 5000, // Timeout after 5 seconds
    });
    console.log(`✅ MongoDB connected successfully to: ${MONGODB_DATABASE}`);
  } catch (error: any) {
    console.error('❌ MongoDB connection error:', error.message);
    if (error.message.includes('ECONNREFUSED')) {
      console.error('HINT: This is likely a DNS issue. Check if your network blocks SRV records or try a non-SRV connection string.');
    }
    process.exit(1);
  }
};
