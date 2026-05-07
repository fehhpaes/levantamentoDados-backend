import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { connectDB } from './config/database.js';
import matchRoutes from './routes/matchRoutes.js';
import betRoutes from './routes/betRoutes.js';
import { startUpdateWorker } from './workers/updateMatches.js';
import { initSocket } from './services/socket.js';
import { connectRedis } from './services/redis.js';

// Import workers to initialize them
import './queues/syncQueue.js';
import './queues/predictionQueue.js';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors({
  origin: '*', // Permite que seu frontend acesse a API de qualquer lugar
  methods: ['GET', 'POST'],
  credentials: true
}));
app.use(express.json());

// Routes
app.use('/api/matches', matchRoutes);
app.use('/api/bets', betRoutes);

const httpServer = createServer(app);
initSocket(httpServer);

// Start Server immediately to allow /ping and keep-alive
httpServer.listen(PORT, () => {
  console.log(`🚀 Server is running on port ${PORT}`);
  
  // Initialize services in background
  connectDB();
  connectRedis().then(() => {
    startUpdateWorker();
  }).catch(err => {
    console.error('Failed to connect to Redis, worker not started:', err.message);
  });
});
