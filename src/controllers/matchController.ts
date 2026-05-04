import { Request, Response } from 'express';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { ApiFootballService } from '../services/apiFootball.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';

const footballService = new ApiFootballService();
const footballDataService = new FootballDataService();
const predictionEngine = new PredictionEngine();

export const getTodayMatches = async (req: Request, res: Response) => {
  try {
    const { league_id } = req.query;
    const now = new Date();
    const startTime = new Date(now.getTime() - 3 * 60 * 60 * 1000);
    const endTime = new Date(now.getTime() + 21 * 60 * 60 * 1000);

    const query: any = {
      date: { $gte: startTime, $lt: endTime }
    };

    if (league_id) {
      query['league.id'] = Number(league_id);
    }

    const matches = await Match.find(query).sort({ date: 1 });

    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch matches' });
  }
};

export const getLeagues = async (req: Request, res: Response) => {
  try {
    // Get unique leagues from the Match collection
    const leagues = await Match.aggregate([
      {
        $match: {
          'league.id': { $ne: null }
        }
      },
      {
        $group: {
          _id: '$league.id',
          name: { $first: '$league.name' },
          logo: { $first: '$league.logo' }
        }
      },
      {
        $project: {
          id: '$_id',
          name: 1,
          logo: 1,
          _id: 0
        }
      },
      { $sort: { name: 1 } }
    ]);
    res.json(leagues);
  } catch {
    res.status(500).json({ error: 'Failed to fetch leagues' });
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
    message: `Sync process started for ${today}. Checking all leagues sequentially...`,
    status: 'processing'
  });

  // Run the staggered sync logic in background
  (async () => {
    try {
      console.log(`[Manual Sync] Starting staggered sync for ${today}...`);
      
      const competitions = [
        { name: 'Brasileirão Série A', code: 'BSA' },
        { name: 'Premier League', code: 'PL' },
        { name: 'La Liga', code: 'PD' },
        { name: 'Bundesliga', code: 'BL1' },
        { name: 'Serie A (Italy)', code: 'SA' },
        { name: 'Ligue 1 (France)', code: 'FL1' }
      ];

      for (const comp of competitions) {
        console.log(`[Manual Sync] Syncing ${comp.name}...`);
        await footballDataService.syncCompetitionMatches(comp.code, today, today);
        // Wait 5 seconds between competitions to be safe with the rate limit
        await new Promise(resolve => setTimeout(resolve, 5000));
      }

      // Final fallback and AI tasks
      console.log(`[Manual Sync] Running final fallback and AI processing...`);
      await footballDataService.syncTodayMatches();
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();

      console.log(`[Manual Sync] Manual sync completed successfully.`);
    } catch (error) {
      console.error('[Manual Sync] Background process failed:', error);
    }
  })();
};
