import { Queue, Worker, Job } from 'bullmq';
import { redisUrl } from '../services/redis.js';
import { FootballDataService } from '../services/footballData.js';
import { SportmonksService } from '../services/sportmonks.js';
import { Match } from '../models/Match.js';
import { predictionQueue } from './predictionQueue.js';
import { resolveBetsForMatch } from '../services/betService.js';
import { updateSyncStatus } from '../services/syncState.js';

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

  updateSyncStatus({ 
    isSyncing: true, 
    progress: 10, 
    currentTask: `Sincronizando ${competitionCode || 'Jogos de Hoje'}...` 
  });

  try {
    if (type === 'sync-competition') {
      await footballDataService.syncCompetitionMatches(competitionCode, date, date);
    } else if (type === 'sync-today') {
      if (date) {
        // If a specific date is provided (like yesterday for self-healing)
        await footballDataService.fetchAndSyncMatches(date, date);
      } else {
        await footballDataService.syncTodayMatches();
      }
    } else if (type === 'force-backtest') {
      await runFullBacktestAnalysis();
    }

    // ALWAYS sync stats and resolve bets after any match sync process
    await syncStatsForFinishedMatches();

    updateSyncStatus({ progress: 40, currentTask: 'Sincronizando estatísticas...' });

    // Remove the redundant call below if it was there

    updateSyncStatus({ progress: 70, currentTask: 'Gerando previsões IA...' });

    // Trigger Prediction Job
    await predictionQueue.add('run-predictions', { source: type });
    
    console.log(`[SyncWorker] Job ${job.id} completed successfully.`);
  } catch (error) {
    updateSyncStatus({ isSyncing: false, currentTask: 'Erro na sincronização' });
    console.error(`[SyncWorker] Job ${job.id} failed:`, error);
    throw error;
  }
}, { connection });

async function runFullBacktestAnalysis() {
  const { PredictionEngine } = await import('../services/predictionEngine.js');
  const engine = new PredictionEngine();
  
  updateSyncStatus({ progress: 15, currentTask: 'Treinando modelos para Backtest...' });
  await engine.trainModel();

  const finishedMatches = await Match.find({ status: 'FINISHED' });
  console.log(`[Backtest] Re-analyzing ${finishedMatches.length} matches...`);

  let count = 0;
  for (const match of finishedMatches) {
    const prediction = await engine.generatePrediction(match);
    if (prediction) {
      match.prediction = prediction;
      await match.save();
    }
    count++;
    if (count % 10 === 0) {
      const progress = Math.min(15 + Math.floor((count / finishedMatches.length) * 20), 35);
      updateSyncStatus({ progress, currentTask: `Analisando: ${count}/${finishedMatches.length}` });
    }
  }
}

async function syncStatsForFinishedMatches() {
  const now = new Date();
  const threeDaysAgo = new Date();
  threeDaysAgo.setDate(threeDaysAgo.getDate() - 3);

  // 1. Find matches that are finished but missing stats
  // 2. ALSO find matches that should have finished by now (past start time + 3 hours) but are still marked as SCHEDULED
  const matchesToUpdate = await Match.find({ 
    $or: [
      { 
        status: 'FINISHED',
        date: { $gte: threeDaysAgo },
        $or: [
          { stats: { $exists: false } },
          { 'stats.home_possession': { $exists: false } },
          { 'stats.home_possession': 0 }
        ]
      },
      {
        status: 'SCHEDULED',
        date: { $gte: threeDaysAgo, $lt: new Date(now.getTime() - (3 * 60 * 60 * 1000)) }
      }
    ]
  }).limit(50);
  
  console.log(`[SyncWorker] Syncing results/stats for ${matchesToUpdate.length} matches...`);
  for (const m of matchesToUpdate) {
    await sportmonksService.syncStatsByMatch(m);
    await resolveBetsForMatch(m);
    // Increase delay slightly to be safer with rate limits
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}
