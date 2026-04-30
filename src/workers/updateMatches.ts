import cron from 'node-cron';
import { ApiFootballService } from '../services/apiFootball.js';
import { PredictionEngine } from '../services/predictionEngine.js';

const footballService = new ApiFootballService();
const predictionEngine = new PredictionEngine();

/**
 * Worker responsible for synchronizing data from the API and 
 * updating predictions automatically.
 */
export const startUpdateWorker = () => {
  console.log('--- Match Update Worker Started ---');

  /**
   * Schedule: Every day at 02:00 AM
   * This ensures we get results from late matches of the previous day 
   * and fixtures for the new day.
   */
  cron.schedule('0 2 * * *', async () => {
    const today = new Date().toISOString().split('T')[0];
    console.log(`[Worker] Starting scheduled sync for ${today}...`);

    try {
      // 1. Synchronize matches and their real statistics
      await footballService.fetchAndSyncMatchesByDate(today);

      // 2. Re-train the Machine Learning model with the latest results
      console.log('[Worker] Re-training Prediction Engine...');
      await predictionEngine.trainModel();

      // 3. Generate predictions for the upcoming matches
      console.log('[Worker] Generating predictions for scheduled matches...');
      await predictionEngine.predictScheduledMatches();

      console.log(`[Worker] Daily update for ${today} completed.`);
    } catch (error) {
      console.error('[Worker] Critical error during scheduled update:', error);
    }
  });

  /**
   * Initial sync on server startup to ensure data is current.
   */
  const startupSync = async () => {
    const today = new Date().toISOString().split('T')[0];
    console.log(`[Worker] Performing initial startup sync for ${today}...`);
    try {
      await footballService.fetchAndSyncMatchesByDate(today);
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();
    } catch (error) {
      console.error('[Worker] Error during startup sync:', error);
    }
  };

  startupSync();
};
