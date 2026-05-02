import { Request, Response } from 'express';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { ApiFootballService } from '../services/apiFootball.js';
import { PredictionEngine } from '../services/predictionEngine.js';

const footballService = new ApiFootballService();
const predictionEngine = new PredictionEngine();

export const getTodayMatches = async (req: Request, res: Response) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    const matches = await Match.find({
      date: { $gte: today, $lt: tomorrow }
    }).sort({ date: 1 });

    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch matches' });
  }
};

export const getMatchById = async (req: Request, res: Response) => {
  try {
    const { fixture_id } = req.params;
    const match = await Match.findOne({ fixture_id: Number(fixture_id) });

    if (!match) {
      return res.status(404).json({ error: 'Match not found' });
    }

    res.json(match);
  } catch {
    res.status(500).json({ error: 'Internal server error' });
  }
};

export const getTeamStats = async (req: Request, res: Response) => {
  try {
    const { team_id } = req.params;
    const stats = await getTeamMovingAverage(Number(team_id));
    res.json(stats);
  } catch {
    res.status(500).json({ error: 'Failed to fetch team statistics' });
  }
};

export const getMatchHistory = async (req: Request, res: Response) => {
  try {
    const matches = await Match.find({ status: 'FINISHED' })
      .sort({ date: -1 })
      .limit(20);
    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch match history' });
  }
};

export const triggerManualSync = async (req: Request, res: Response) => {
  const today = new Date().toISOString().split('T')[0];
  
  // Respond immediately to prevent timeout
  res.json({ 
    message: `Sync process started in background for ${today}`,
    status: 'processing'
  });

  // Run the heavy tasks without 'awaiting' the response
  (async () => {
    try {
      console.log(`[Manual Sync] Background process started for ${today}...`);

      await footballService.fetchAndSyncMatchesByDate(today);
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();

      console.log(`[Manual Sync] Background process completed for ${today}`);
    } catch (error) {
      console.error('[Manual Sync] Background process failed:', error);
    }
  })();
};
