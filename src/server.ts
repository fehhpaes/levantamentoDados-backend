import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { createServer } from 'http';
import { connectDB } from './config/database.js';
import matchRoutes from './routes/matchRoutes.js';
import { startUpdateWorker } from './workers/updateMatches.js';
import { initSocket } from './services/socket.js';
import { connectRedis } from './services/redis.js';

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

const httpServer = createServer(app);
initSocket(httpServer);

// Database connection and Server start
Promise.all([connectDB(), connectRedis()]).then(() => {
  httpServer.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
    startUpdateWorker();
  });
});
