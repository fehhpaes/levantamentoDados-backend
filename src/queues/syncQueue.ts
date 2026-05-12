import { EventEmitter } from 'events';
import { FootballDataService } from '../services/footballData.js';
import { SportmonksService } from '../services/sportmonks.js';
import { Match } from '../models/Match.js';
import { predictionQueue } from './predictionQueue.js';
import { resolveBetsForMatch } from '../services/betService.js';
import { updateSyncStatus } from '../services/syncState.js';

const footballDataService = new FootballDataService();
const sportmonksService = new SportmonksService();

class MemorySyncQueue extends EventEmitter {
  private processing = false;
  private queue: any[] = [];

  async add(name: string, data: any) {
    this.queue.push({ name, data });
    this.process();
    return { id: Date.now().toString() };
  }

  private async process() {
    if (this.processing || this.queue.length === 0) return;
    
    this.processing = true;
    const job = this.queue.shift();
    
    try {
      await this.worker(job);
    } catch (err) {
      console.error(`[SyncQueue] Error processing job ${job.name}:`, err);
    } finally {
      this.processing = false;
      this.process();
    }
  }

  private async worker(job: any) {
    const { type, competitionCode, date } = job.data;
    console.log(`[SyncWorker] Processing job of type ${type}...`);

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
          await footballDataService.fetchAndSyncMatches(date, date);
        } else {
          await footballDataService.syncTodayMatches();
        }
      } else if (type === 'force-backtest') {
        await runFullBacktestAnalysis();
      }

      await syncStatsForFinishedMatches();
      updateSyncStatus({ progress: 40, currentTask: 'Sincronizando estatísticas...' });
      updateSyncStatus({ progress: 70, currentTask: 'Gerando previsões IA...' });

      // Trigger Prediction Job directly in memory
      await predictionQueue.add('run-predictions', { source: type });
      
      console.log(`[SyncWorker] Job completed successfully.`);
    } catch (error) {
      updateSyncStatus({ isSyncing: false, currentTask: 'Erro na sincronização' });
      console.error(`[SyncWorker] Job failed:`, error);
      throw error;
    }
  }
}

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
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
}

export const syncQueue = new MemorySyncQueue();
export const syncWorker = { name: 'memory-worker' }; // Mock
