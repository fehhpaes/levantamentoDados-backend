import cron from 'node-cron';
import axios from 'axios';
import { syncQueue } from '../queues/syncQueue.js';

/**
 * Keeps the server alive by pinging its own /ping endpoint.
 * This is crucial for free-tier hosting like Render.
 */
export const startKeepAlive = () => {
  console.log('--- Keep-Alive Monitor Started ---');
  cron.schedule('*/14 * * * *', async () => {
    try {
      const port = process.env.PORT || 3001;
      const url = process.env.RENDER_EXTERNAL_URL || `http://localhost:${port}`;
      console.log(`[Keep-Alive] Pinging server at ${url}/api/matches/ping...`);
      await axios.get(`${url}/api/matches/ping`);
    } catch (error: any) {
      console.error('[Keep-Alive] Ping failed:', error.message);
    }
  });
};

/**
 * Worker responsible for scheduling synchronization tasks.
 * Instead of running logic directly, it dispatches jobs to BullMQ.
 */
export const startUpdateWorker = () => {
  console.log('--- Match Update Scheduler Started (BullMQ + Cron) ---');

  const competitions = [
    { name: 'Brasileirão Série A', code: 'BSA', cron: '0 3 * * *' }, // 03:00 AM
    { name: 'Premier League', code: 'PL', cron: '15 3 * * *' },     // 03:15 AM
    { name: 'La Liga', code: 'PD', cron: '30 3 * * *' },           // 03:30 AM
    { name: 'Bundesliga', code: 'BL1', cron: '45 3 * * *' },        // 03:45 AM
    { name: 'Serie A (Italy)', code: 'SA', cron: '0 4 * * *' },     // 04:00 AM
    { name: 'Ligue 1 (France)', code: 'FL1', cron: '15 4 * * *' }   // 04:15 AM
  ];

  // Register scheduled jobs
  competitions.forEach((comp) => {
    cron.schedule(comp.cron, async () => {
      const today = new Date().toISOString().split('T')[0];
      console.log(`[Scheduler] Queueing scheduled sync for ${comp.name} (${today})...`);
      
      await syncQueue.add(`sync-${comp.code}-${today}`, {
        type: 'sync-competition',
        competitionCode: comp.code,
        date: today
      });
    });
  });

  /**
   * General fallback sync for any other matches (Today)
   * Runs at 05:00 AM
   */
  cron.schedule('0 5 * * *', async () => {
    console.log('[Scheduler] Queueing general fallback sync...');
    await syncQueue.add('sync-general-today', { type: 'sync-today' });
  });

  /**
   * Initial sync on server startup to ensure data is current.
   */
  const startupSync = async () => {
    console.log(`[Scheduler] Dispatching initial startup sync jobs...`);
    const today = new Date().toISOString().split('T')[0];
    
    // We can add them with a slight delay or just all at once to the queue
    for (const comp of competitions) {
      await syncQueue.add(`startup-sync-${comp.code}`, {
        type: 'sync-competition',
        competitionCode: comp.code,
        date: today
      }, { delay: 1000 });
    }
    
    await syncQueue.add('startup-sync-general', { type: 'sync-today' }, { delay: 5000 });
  };

  startupSync();
};
