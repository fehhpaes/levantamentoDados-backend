import { Request, Response } from 'express';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { ApiFootballService } from '../services/apiFootball.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';

const footballService = new ApiFootballService();
const footballDataService = new FootballDataService();
const predictionEngine = new PredictionEngine();

// Global state to track sync progress (in-memory)
let syncState = {
  isSyncing: false,
  progress: 0,
  currentTask: '',
  lastSync: null as Date | null,
  leaguesProcessed: [] as string[]
};

export const getSyncStatus = async (req: Request, res: Response) => {
  res.json(syncState);
};

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
  if (syncState.isSyncing) {
    return res.status(409).json({ message: 'Sync already in progress' });
  }

  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];
  
  // Expand window for manual sync to catch recent and next day matches
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  
  res.json({ 
    message: `Sync process started. Populating matches for the current period...`,
    status: 'processing'
  });

  (async () => {
    try {
      syncState.isSyncing = true;
      syncState.progress = 0;
      syncState.currentTask = 'Iniciando sincronização (Janela de 3 dias)...';
      syncState.leaguesProcessed = [];

      const competitions = [
        { name: 'Brasileirão Série A', code: 'BSA' },
        { name: 'Premier League', code: 'PL' },
        { name: 'La Liga', code: 'PD' },
        { name: 'Bundesliga', code: 'BL1' },
        { name: 'Serie A (Italy)', code: 'SA' },
        { name: 'Ligue 1 (France)', code: 'FL1' }
      ];

      for (let i = 0; i < competitions.length; i++) {
        const comp = competitions[i];
        syncState.currentTask = `Sincronizando ${comp.name}...`;
        syncState.progress = Math.round(((i) / (competitions.length + 1)) * 100);
        
        // Sync yesterday, today and tomorrow for each competition
        await footballDataService.syncCompetitionMatches(comp.code, yesterday, tomorrow);
        syncState.leaguesProcessed.push(comp.name);
        await new Promise(resolve => setTimeout(resolve, 3000));
      }

      syncState.currentTask = 'Processando IA e Estatísticas...';
      syncState.progress = 95;
      
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();

      syncState.isSyncing = false;
      syncState.progress = 100;
      syncState.currentTask = 'Sincronização concluída!';
      syncState.lastSync = new Date();
    } catch (error) {
      syncState.isSyncing = false;
      syncState.currentTask = 'Erro na sincronização';
    }
  })();
};
