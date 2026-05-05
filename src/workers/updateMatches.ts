import cron from 'node-cron';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import { OddsApiService } from '../services/oddsApi.js';

const footballDataService = new FootballDataService();
const predictionEngine = new PredictionEngine();
const oddsApiService = new OddsApiService();

/**
 * Worker responsible for synchronizing data from the API and 
 * updating predictions automatically.
 */
export const startUpdateWorker = () => {
  console.log('--- Match Update Worker Started (Staggered Scheduling) ---');

  const competitions = [
    { name: 'Brasileirão Série A', code: 'BSA', cron: '0 3 * * *' }, // 03:00 AM
    { name: 'Premier League', code: 'PL', cron: '15 3 * * *' },     // 03:15 AM
    { name: 'La Liga', code: 'PD', cron: '30 3 * * *' },           // 03:30 AM
    { name: 'Bundesliga', code: 'BL1', cron: '45 3 * * *' },        // 03:45 AM
    { name: 'Serie A (Italy)', code: 'SA', cron: '0 4 * * *' },     // 04:00 AM
    { name: 'Ligue 1 (France)', code: 'FL1', cron: '15 4 * * *' }   // 04:15 AM
  ];

  // Register individual sync jobs for each competition
  competitions.forEach((comp) => {
    cron.schedule(comp.cron, async () => {
      const today = new Date().toISOString().split('T')[0];
      console.log(`[Worker] Starting scheduled sync for ${comp.name} (${today})...`);

      try {
        await footballDataService.syncCompetitionMatches(comp.code, today, today);
        
        // After syncing, run AI tasks
        console.log(`[Worker] Running AI engine after ${comp.name} sync...`);
        await predictionEngine.trainModel();
        await predictionEngine.predictScheduledMatches();
        await oddsApiService.syncAllOdds();
        
        console.log(`[Worker] Daily update for ${comp.name} completed.`);
      } catch (error) {
        console.error(`[Worker] Error during ${comp.name} update:`, error);
      }
    });
  });

  /**
   * General fallback sync for any other matches (Today)
   * Runs at 05:00 AM
   */
  cron.schedule('0 5 * * *', async () => {
    const today = new Date().toISOString().split('T')[0];
    console.log(`[Worker] Running general fallback sync for ${today}...`);
    try {
      await footballDataService.syncTodayMatches();
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();
      await oddsApiService.syncAllOdds();
    } catch (error) {
      console.error('[Worker] Error during general fallback sync:', error);
    }
  });

  /**
   * Initial sync on server startup to ensure data is current.
   */
  const startupSync = async () => {
    const today = new Date().toISOString().split('T')[0];
    console.log(`[Worker] Performing initial startup sync for all leagues...`);
    try {
      // On startup, we can run them sequentially with small delays to be safe
      for (const comp of competitions) {
        await footballDataService.syncCompetitionMatches(comp.code, today, today);
        await new Promise(resolve => setTimeout(resolve, 5000)); // 5s gap
      }
      
      await footballDataService.syncTodayMatches();
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();
      await oddsApiService.syncAllOdds();
      console.log('[Worker] Startup sync finished.');
    } catch (error) {
      console.error('[Worker] Error during startup sync:', error);
    }
  };

  startupSync();
};
