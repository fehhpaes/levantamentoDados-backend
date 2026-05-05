import { Queue, Worker, Job } from 'bullmq';
import { redisUrl } from '../services/redis.js';
import { FootballDataService } from '../services/footballData.js';
import { SportmonksService } from '../services/sportmonks.js';
import { Match } from '../models/Match.js';
import { predictionQueue } from './predictionQueue.js';
import { resolveBetsForMatch } from '../services/betService.js';

const footballDataService = new FootballDataService();
const sportmonksService = new SportmonksService();

// BullMQ connection options (parsed from redisUrl if needed, but BullMQ supports URL strings in some contexts)
// For robustness, we'll try to pass the connection as an object if possible or just the URL.
const connection = {
  url: redisUrl
};

export const syncQueue = new Queue('sync-matches', { connection });

/**
 * Worker for Syncing Matches and Statistics
 */
export const syncWorker = new Worker('sync-matches', async (job: Job) => {
  const { type, competitionCode, date } = job.data;
  console.log(`[SyncWorker] Processing job ${job.id} of type ${type}...`);

  try {
    if (type === 'sync-competition') {
      await footballDataService.syncCompetitionMatches(competitionCode, date, date);
    } else if (type === 'sync-today') {
      await footballDataService.syncTodayMatches();
    }

    // After syncing matches, sync stats for finished ones
    await syncStatsForFinishedMatches();

    // Trigger Prediction Job
    await predictionQueue.add('run-predictions', { source: type });
    
    console.log(`[SyncWorker] Job ${job.id} completed successfully.`);
  } catch (error) {
    console.error(`[SyncWorker] Job ${job.id} failed:`, error);
    throw error;
  }
}, { connection });

async function syncStatsForFinishedMatches() {
  const matchesToUpdate = await Match.find({ 
    status: 'FINISHED', 
    $or: [
      { 'stats.home_possession': { $exists: false } },
      { 'stats.home_possession': 0 }
    ] 
  }).limit(30);
  
  console.log(`[SyncWorker] Syncing statistics and resolving bets for ${matchesToUpdate.length} matches...`);
  for (const m of matchesToUpdate) {
    await sportmonksService.syncStatsByMatch(m);
    await resolveBetsForMatch(m);
    await new Promise(resolve => setTimeout(resolve, 500));
  }
}
