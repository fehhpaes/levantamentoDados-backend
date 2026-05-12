import { EventEmitter } from 'events';
import { PredictionEngine } from '../services/predictionEngine.js';
import { OddsApiService } from '../services/oddsApi.js';
import { clearAllCache } from '../services/redis.js';
import { updateSyncStatus } from '../services/syncState.js';

const predictionEngine = new PredictionEngine();
const oddsApiService = new OddsApiService();

// Memory Queue Implementation
class MemoryQueue extends EventEmitter {
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
      console.error(`[PredictionQueue] Error processing job ${job.name}:`, err);
    } finally {
      this.processing = false;
      this.process();
    }
  }

  private async worker(job: any) {
    console.log(`[PredictionWorker] Processing job...`);

    try {
      updateSyncStatus({ progress: 75, currentTask: 'Treinando IA...' });

      // 1. Train Model
      console.log('[PredictionWorker] Training AI model...');
      await predictionEngine.trainModel();

      updateSyncStatus({ progress: 85, currentTask: 'Processando palpites...' });

      // 2. Predict Scheduled Matches
      console.log('[PredictionWorker] Running predictions for scheduled matches...');
      await predictionEngine.predictScheduledMatches();

      updateSyncStatus({ progress: 95, currentTask: 'Atualizando Odds...' });

      // 3. Sync Odds
      console.log('[PredictionWorker] Syncing odds...');
      await oddsApiService.syncAllOdds();

      // 4. Clear Cache
      await clearAllCache();

      updateSyncStatus({ 
        isSyncing: false, 
        progress: 100, 
        currentTask: 'Concluído',
        lastSync: new Date()
      });

      console.log(`[PredictionWorker] Job completed successfully.`);
    } catch (error) {
      updateSyncStatus({ isSyncing: false, currentTask: 'Erro nas previsões' });
      console.error(`[PredictionWorker] Job failed:`, error);
      throw error;
    }
  }
}

export const predictionQueue = new MemoryQueue();
export const predictionWorker = { name: 'memory-worker' }; // Mock for compatibility
