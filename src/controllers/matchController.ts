import { Request, Response } from 'express';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { FootballDataService } from '../services/footballData.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import { getCache, setCache, clearAllCache } from '../services/redis.js';

const footballDataService = new FootballDataService();
const predictionEngine = new PredictionEngine();

import { TeamTest } from '../models/TeamTest.js';

// Global state to track sync progress (in-memory)
let syncState = {
  isSyncing: false,
  progress: 0,
  currentTask: '',
  lastSync: null as Date | null,
  leaguesProcessed: [] as string[]
};

export const testDatabaseWrite = async (req: Request, res: Response) => {
  try {
    const testId = `test_${Date.now()}`;
    const newEntry = new TeamTest({
      name: 'Teste de Conexão',
      code: testId
    });
    
    await newEntry.save();
    res.json({ 
      success: true, 
      message: 'Escrita no banco de dados realizada com sucesso!',
      data: newEntry 
    });
  } catch (error: any) {
    console.error('[DB Test] Write failed:', error);
    res.status(500).json({ 
      success: false, 
      message: 'Falha ao escrever no banco de dados', 
      error: error.message 
    });
  }
};

export const clearDatabase = async (req: Request, res: Response) => {
  try {
    await Match.deleteMany({});
    // Also clear TeamTest just in case
    await TeamTest.deleteMany({});
    
    res.json({ 
      success: true, 
      message: 'Banco de dados de partidas limpo com sucesso! Você pode iniciar uma nova sincronização.' 
    });
  } catch (error: any) {
    res.status(500).json({ success: false, error: error.message });
  }
};

export const getSyncStatus = async (req: Request, res: Response) => {
  res.json(syncState);
};

export const getTodayMatches = async (req: Request, res: Response) => {
  try {
    const { league_id, date_type } = req.query;
    const cacheKey = `matches:${date_type || 'today'}:${league_id || 'all'}`;
    
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }

    const now = new Date();
    
    let startTime = new Date(now.setHours(0, 0, 0, 0));
    let endTime = new Date(now.setHours(23, 59, 59, 999));

    if (date_type === 'yesterday') {
      startTime.setDate(startTime.getDate() - 1);
      endTime.setDate(endTime.getDate() - 1);
    } else if (date_type === 'tomorrow') {
      startTime.setDate(startTime.getDate() + 1);
      endTime.setDate(endTime.getDate() + 1);
    }

    const query: any = {
      date: { $gte: startTime, $lt: endTime }
    };

    if (league_id) {
      query['league.id'] = Number(league_id);
    }

    const matches = await Match.find(query).sort({ date: 1 });

    await setCache(cacheKey, JSON.stringify(matches), 300); // 5 min cache
    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch matches' });
  }
};

export const getTopPredictions = async (req: Request, res: Response) => {
  try {
    const cacheKey = 'matches:top';
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }

    const now = new Date();
    const startTime = new Date(now.setHours(0, 0, 0, 0));
    // Look for matches from today onwards
    
    const matches = await Match.find({
      status: 'SCHEDULED',
      date: { $gte: startTime },
      'prediction.probabilities': { $exists: true }
    });

    const sortedMatches = matches.sort((a, b) => {
      const aMaxProb = Math.max(a.prediction!.probabilities.homeWin, a.prediction!.probabilities.awayWin);
      const bMaxProb = Math.max(b.prediction!.probabilities.homeWin, b.prediction!.probabilities.awayWin);
      return bMaxProb - aMaxProb;
    }).slice(0, 5);

    await setCache(cacheKey, JSON.stringify(sortedMatches), 600); // 10 min cache
    res.json(sortedMatches);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch top predictions' });
  }
};

export const getLeagues = async (req: Request, res: Response) => {
  try {
    const cacheKey = 'leagues:list';
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }

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

    await setCache(cacheKey, JSON.stringify(leagues), 3600); // 1 hour cache
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

    // Get H2H history
    const h2h = await Match.find({
      status: 'FINISHED',
      $or: [
        { 'homeTeam.id': match.homeTeam.id, 'awayTeam.id': match.awayTeam.id },
        { 'homeTeam.id': match.awayTeam.id, 'awayTeam.id': match.homeTeam.id }
      ]
    }).sort({ date: -1 }).limit(5);

    // Get form for both teams
    const getTeamForm = async (teamId: number) => {
      const lastMatches = await Match.find({
        status: 'FINISHED',
        $or: [{ 'homeTeam.id': teamId }, { 'awayTeam.id': teamId }]
      }).sort({ date: -1 }).limit(5);

      return lastMatches.map(m => {
        const isHome = m.homeTeam.id === teamId;
        const goalsScored = isHome ? m.score.home : m.score.away;
        const goalsConceded = isHome ? m.score.away : m.score.home;
        let result: 'W' | 'D' | 'L';
        if (goalsScored > goalsConceded) result = 'W';
        else if (goalsScored === goalsConceded) result = 'D';
        else result = 'L';
        
        return {
          fixture_id: m.fixture_id,
          date: m.date,
          result,
          score: `${m.score.home}-${m.score.away}`,
          opponent: isHome ? m.awayTeam.name : m.homeTeam.name
        };
      });
    };

    const [homeForm, awayForm] = await Promise.all([
      getTeamForm(match.homeTeam.id),
      getTeamForm(match.awayTeam.id)
    ]);

    res.json({
      ...match.toObject(),
      h2h,
      form: {
        home: homeForm,
        away: awayForm
      }
    });
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

export const getBacktestStats = async (req: Request, res: Response) => {
  try {
    const cacheKey = 'stats:backtest';
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }

    // Get all finished matches that have a prediction
    const finishedMatches = await Match.find({
      status: 'FINISHED',
      prediction: { $exists: true },
      'prediction.outcome': { $ne: null }
    }).sort({ date: -1 });

    if (finishedMatches.length === 0) {
      return res.json({
        total: 0,
        hits: 0,
        accuracy: 0,
        leagueStats: [],
        recentMatches: []
      });
    }

    let totalHits = 0;
    const leagueMap: Record<number, { name: string; total: number; hits: number }> = {};

    const processedMatches = finishedMatches.map(match => {
      const homeScore = match.score.home;
      const awayScore = match.score.away;
      
      let actualOutcome: number;
      if (homeScore > awayScore) actualOutcome = 0; // Home
      else if (homeScore === awayScore) actualOutcome = 1; // Draw
      else actualOutcome = 2; // Away

      const isHit = match.prediction!.outcome === actualOutcome;
      if (isHit) totalHits++;

      // Update league stats
      if (!leagueMap[match.league.id]) {
        leagueMap[match.league.id] = { name: match.league.name, total: 0, hits: 0 };
      }
      leagueMap[match.league.id].total++;
      if (isHit) leagueMap[match.league.id].hits++;

      return {
        fixture_id: match.fixture_id,
        homeTeam: match.homeTeam.name,
        awayTeam: match.awayTeam.name,
        score: match.score,
        predictedOutcome: match.prediction!.outcome,
        actualOutcome,
        isHit,
        date: match.date,
        league: match.league.name
      };
    });

    const leagueStats = Object.values(leagueMap).map(l => ({
      ...l,
      accuracy: Math.round((l.hits / l.total) * 100)
    })).sort((a, b) => b.total - a.total);

    const result = {
      total: finishedMatches.length,
      hits: totalHits,
      accuracy: Math.round((totalHits / finishedMatches.length) * 100),
      leagueStats,
      recentMatches: processedMatches.slice(0, 10) // Top 10 recent for display
    };

    await setCache(cacheKey, JSON.stringify(result), 1800); // 30 min cache
    res.json(result);
  } catch (error) {
    console.error('[Backtest] Error:', error);
    res.status(500).json({ error: 'Failed to calculate backtest statistics' });
  }
};

export const triggerManualSync = async (req: Request, res: Response) => {
  if (syncState.isSyncing) {
    return res.status(409).json({ message: 'Sync already in progress' });
  }

  const { competitionCode } = req.query;
  const now = new Date();
  
  // Expand window for manual sync
  const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  
  res.json({ 
    message: `Sync process started. Target: ${competitionCode || 'All Leagues'}`,
    status: 'processing'
  });

  (async () => {
    try {
      syncState.isSyncing = true;
      syncState.progress = 0;
      syncState.leaguesProcessed = [];

      const competitions = [
        { name: 'Brasileirão Série A', code: 'BSA' },
        { name: 'Premier League', code: 'PL' },
        { name: 'La Liga', code: 'PD' },
        { name: 'Bundesliga', code: 'BL1' },
        { name: 'Serie A (Italy)', code: 'SA' },
        { name: 'Ligue 1 (France)', code: 'FL1' }
      ];

      // Filter competitions if a specific code was provided
      const targetCompetitions = competitionCode 
        ? competitions.filter(c => c.code === competitionCode)
        : competitions;

      if (targetCompetitions.length === 0 && competitionCode) {
        console.error(`[Manual Sync] Invalid competition code: ${competitionCode}`);
        syncState.isSyncing = false;
        syncState.currentTask = 'Código de liga inválido';
        return;
      }

      for (let i = 0; i < targetCompetitions.length; i++) {
        const comp = targetCompetitions[i];
        syncState.currentTask = `Sincronizando ${comp.name}...`;
        syncState.progress = Math.round(((i) / (targetCompetitions.length)) * 100);
        
        console.log(`[Manual Sync] Syncing ${comp.name} (${comp.code})...`);
        await footballDataService.syncCompetitionMatches(comp.code, yesterday, tomorrow);
        syncState.leaguesProcessed.push(comp.name);
        
        if (targetCompetitions.length > 1) {
          await new Promise(resolve => setTimeout(resolve, 3000));
        }
      }

      syncState.currentTask = 'Processando IA e Estatísticas...';
      syncState.progress = 95;
      
      await predictionEngine.trainModel();
      await predictionEngine.predictScheduledMatches();

      await clearAllCache(); // Limpa todo o cache após nova sincronização

      syncState.isSyncing = false;
      syncState.progress = 100;
      syncState.currentTask = 'Sincronização concluída!';
      syncState.lastSync = new Date();
    } catch (error) {
      syncState.isSyncing = false;
      syncState.currentTask = 'Erro na sincronização';
      console.error('[Manual Sync] Failed:', error);
    }
  })();
};
