import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { connectDB } from './config/database.js';
import { initSocket } from './services/socket.js';
import { connectRedis } from './services/redis.js';
import { syncState } from './services/syncState.js';

// Specific routes for triggering sync manually (protected or internal)
import matchRoutes from './routes/matchRoutes.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// 1. Basic Middlewares
app.use(cors());
app.use(express.json());

// 2. Health and Monitoring Routes
app.get('/api/matches/ping', (req, res) => res.json({ status: 'worker-online', time: new Date() }));
app.get('/api/matches/sync-status', (req, res) => res.json(syncState));

// Keep standard match routes but they will mostly be for TRIGGERING jobs
app.use('/api/matches', matchRoutes);

const httpServer = createServer(app);
initSocket(httpServer);

// 3. Start Listening
httpServer.listen(Number(PORT), '0.0.0.0', () => {
  console.log(`👷 Worker Service listening on 0.0.0.0:${PORT}`);
  
  const initializeWorker = async () => {
    try {
      await connectDB();
      await connectRedis();
      
      const { startUpdateWorker, startKeepAlive } = await import('./workers/updateMatches.js');
      await import('./queues/syncQueue.js');
      await import('./queues/predictionQueue.js');
      
      startKeepAlive();
      startUpdateWorker();
      
      console.log('✅ Worker initialized and background jobs started');
    } catch (err: any) {
      console.error('[Worker] Fatal initialization error:', err.message);
    }
  };

  initializeWorker();
});
