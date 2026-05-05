import { Queue, Worker, Job } from 'bullmq';
import { redisUrl } from '../services/redis.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import { OddsApiService } from '../services/oddsApi.js';
import { clearAllCache } from '../services/redis.js';

const predictionEngine = new PredictionEngine();
const oddsApiService = new OddsApiService();

const connection = {
  url: redisUrl
};

export const predictionQueue = new Queue('prediction-queue', { connection });

/**
 * Worker for AI Model Training and Predictions
 */
export const predictionWorker = new Worker('prediction-queue', async (job: Job) => {
  console.log(`[PredictionWorker] Processing job ${job.id}...`);

  try {
    // 1. Train Model
    console.log('[PredictionWorker] Training AI model...');
    await predictionEngine.trainModel();

    // 2. Predict Scheduled Matches
    console.log('[PredictionWorker] Running predictions for scheduled matches...');
    await predictionEngine.predictScheduledMatches();

    // 3. Sync Odds
    console.log('[PredictionWorker] Syncing odds...');
    await oddsApiService.syncAllOdds();

    // 4. Clear Cache
    await clearAllCache();

    console.log(`[PredictionWorker] Job ${job.id} completed successfully.`);
  } catch (error) {
    console.error(`[PredictionWorker] Job ${job.id} failed:`, error);
    throw error;
  }
}, { connection });
