import { Request, Response } from 'express';
import { Match } from '../models/Match.js';
import { getTeamMovingAverage } from '../utils/statsCalculator.js';
import { FootballDataService } from '../services/footballData.js';
import { ApiFootballService } from '../services/apiFootball.js';
import { PredictionEngine } from '../services/predictionEngine.js';
import { getCache, setCache } from '../services/redis.js';
import { syncQueue } from '../queues/syncQueue.js';

import { TeamTest } from '../models/TeamTest.js';

// Global state to track sync progress (in-memory)
export const syncState = {
  isSyncing: false,
  progress: 0,
  currentTask: '',
  lastSync: null as Date | null,
  leaguesProcessed: [] as string[]
};

export const updateSyncStatus = (data: Partial<typeof syncState>) => {
  Object.assign(syncState, data);
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
    
    // Disable cache for troubleshooting
    /*
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }
    */

    const now = new Date();
    
    // Use a slightly wider range (30 hours) to account for timezones
    const startTime = new Date(now);
    startTime.setHours(startTime.getHours() - 15, 0, 0, 0);
    
    const endTime = new Date(now);
    endTime.setHours(endTime.getHours() + 15, 59, 59, 999);

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

    console.log(`[Matches] Fetching for ${date_type || 'today'}. Range: ${startTime.toISOString()} to ${endTime.toISOString()}`);
    const matches = await Match.find(query).sort({ date: 1 });
    console.log(`[Matches] Found ${matches.length} matches.`);
    
    if (matches.length > 0) {
      console.log(`[Matches] Sample match: ${matches[0].homeTeam.name} vs ${matches[0].awayTeam.name} at ${matches[0].date.toISOString()}`);
    }

    await setCache(cacheKey, JSON.stringify(matches), 300); // 5 min cache
    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch matches' });
  }
};

export const getTopPredictions = async (req: Request, res: Response) => {
  try {
    const cacheKey = 'matches:top';
    // Disable cache for troubleshooting
    /*
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }
    */

    const now = new Date();
    const startTime = new Date(now.setHours(0, 0, 0, 0));
    const endTime = new Date(now.setHours(23, 59, 59, 999));
    
    const matches = await Match.find({
      status: 'SCHEDULED',
      date: { $gte: startTime, $lt: endTime },
      'prediction.probabilities': { $exists: true }
    });

    const sortedMatches = matches.sort((a, b) => {
      const aMaxProb = Math.max(a.prediction!.probabilities.homeWin, a.prediction!.probabilities.awayWin, a.prediction!.probabilities.draw);
      const bMaxProb = Math.max(b.prediction!.probabilities.homeWin, b.prediction!.probabilities.awayWin, b.prediction!.probabilities.draw);
      return bMaxProb - aMaxProb;
    }).slice(0, 5);

    await setCache(cacheKey, JSON.stringify(sortedMatches), 600); // 10 min cache
    res.json(sortedMatches);
  } catch (error) {
    res.status(500).json({ error: 'Failed to fetch top predictions' });
  }
};

export const getBetsReport = async (req: Request, res: Response) => {
  try {
    const now = new Date();
    const startTime = new Date(now.setHours(0, 0, 0, 0));
    const endTime = new Date(now.setHours(23, 59, 59, 999));
    
    const matches = await Match.find({
      status: 'SCHEDULED',
      date: { $gte: startTime, $lt: endTime },
      'prediction.probabilities': { $exists: true }
    });

    const top5 = matches.sort((a, b) => {
      const aMaxProb = Math.max(a.prediction!.probabilities.homeWin, a.prediction!.probabilities.awayWin, a.prediction!.probabilities.draw);
      const bMaxProb = Math.max(b.prediction!.probabilities.homeWin, b.prediction!.probabilities.awayWin, b.prediction!.probabilities.draw);
      return bMaxProb - aMaxProb;
    }).slice(0, 5);

    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Relatório Top 5 Bets - ${now.toLocaleDateString('pt-BR')}</title>
        <style>
          body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; margin: 40px; }
          .header { text-align: center; border-bottom: 2px solid #22c55e; padding-bottom: 20px; margin-bottom: 30px; }
          .header h1 { margin: 0; color: #166534; text-transform: uppercase; letter-spacing: 2px; }
          .header p { margin: 5px 0 0; color: #666; font-weight: bold; }
          .match-card { border: 1px solid #ddd; border-radius: 12px; padding: 20px; margin-bottom: 20px; page-break-inside: avoid; background: #fafafa; }
          .match-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; border-bottom: 1px dashed #ccc; padding-bottom: 10px; }
          .league { font-size: 12px; font-weight: 900; color: #22c55e; text-transform: uppercase; }
          .date { font-size: 12px; color: #888; }
          .teams { display: flex; justify-content: space-around; align-items: center; font-size: 18px; font-weight: bold; margin: 20px 0; }
          .vs { color: #999; font-style: italic; font-size: 14px; }
          .prediction-box { background: #fff; border: 2px solid #22c55e; border-radius: 8px; padding: 15px; text-align: center; }
          .prediction-title { font-size: 10px; font-weight: 900; color: #666; text-transform: uppercase; margin-bottom: 5px; }
          .prediction-value { font-size: 24px; font-weight: 900; color: #166534; }
          .prob-grid { display: grid; grid-cols: 2; gap: 10px; margin-top: 15px; }
          .analysis { margin-top: 15px; font-size: 13px; color: #555; font-style: italic; line-height: 1.5; padding: 10px; background: #f0fdf4; border-left: 4px solid #22c55e; }
          .footer { text-align: center; margin-top: 50px; font-size: 10px; color: #aaa; text-transform: uppercase; }
          @media print {
            .no-print { display: none; }
            body { margin: 0; }
            .match-card { border: 1px solid #000; }
          }
          .print-btn { background: #22c55e; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-bottom: 20px; }
        </style>
      </head>
      <body>
        <div class="no-print" style="text-align: right;">
          <button class="print-btn" onclick="window.print()">IMPRIMIR RELATÓRIO</button>
        </div>
        <div class="header">
          <h1>Levantamento de Dados - Top 5 Bets</h1>
          <p>Relatório de Inteligência Artificial para ${now.toLocaleDateString('pt-BR')}</p>
        </div>

        ${top5.map((m, index) => {
          const probs = m.prediction!.probabilities;
          const bestProb = Math.max(probs.homeWin, probs.awayWin, probs.draw);
          
          let bestTarget = 'Empate';
          if (bestProb === probs.homeWin) bestTarget = m.homeTeam.name;
          else if (bestProb === probs.awayWin) bestTarget = m.awayTeam.name;

          return `
            <div class="match-card">
              <div class="match-header">
                <span class="league">#${index + 1} - ${m.league.name}</span>
                <span class="date">${new Date(m.date).toLocaleString('pt-BR')}</span>
              </div>
              <div class="teams">
                <div style="flex: 1; text-align: center;">${m.homeTeam.name}</div>
                <div class="vs">VS</div>
                <div style="flex: 1; text-align: center;">${m.awayTeam.name}</div>
              </div>
              <div class="prediction-box">
                <div class="prediction-title">Palpite Recomendado</div>
                <div class="prediction-value">${bestTarget} (${(bestProb * 100).toFixed(0)}%)</div>
              </div>
              ${m.prediction?.analysis ? `<div class="analysis">" ${m.prediction.analysis} "</div>` : ''}
              <div style="display: flex; justify-content: space-between; margin-top: 15px; font-size: 11px; font-weight: bold; color: #777;">
                <span>OVER 2.5: ${(probs.over25! * 100).toFixed(0)}%</span>
                <span>AMBAS MARCAM: ${(probs.bttsYes! * 100).toFixed(0)}%</span>
              </div>
            </div>
          `;
        }).join('')}

        <div class="footer">
          Gerado automaticamente pelo Sistema de Levantamento de Dados - ${now.toLocaleString('pt-BR')}
        </div>
      </body>
      </html>
    `;

    res.setHeader('Content-Type', 'text/html');
    res.send(html);
  } catch (error) {
    res.status(500).json({ error: 'Failed to generate report' });
  }
};

export const getLeagues = async (req: Request, res: Response) => {
  try {
    const cacheKey = 'leagues:list';
    // Disable cache for troubleshooting
    /*
    const cachedData = await getCache(cacheKey);
    if (cachedData) {
      return res.json(JSON.parse(cachedData));
    }
    */

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

    const finishedMatches = await Match.find({
      status: 'FINISHED',
      prediction: { $exists: true },
      'prediction.outcome': { $ne: null }
    }).sort({ date: -1 });

    if (finishedMatches.length === 0) {
      return res.json({
        total: 0,
        accuracy: 0,
        markets: { winner: 0, overUnder: 0, btts: 0 },
        leagueStats: [],
        recentMatches: []
      });
    }

    let winnerHits = 0;
    let ouHits = 0;
    let bttsHits = 0;
    let ouTotal = 0;
    let bttsTotal = 0;

    const leagueMap: Record<number, { name: string; total: number; hits: number }> = {};

    const processedMatches = finishedMatches.map(match => {
      const homeScore = match.score.home;
      const awayScore = match.score.away;
      const totalGoals = homeScore + awayScore;
      
      // 1X2 Winner
      let actualOutcome: number;
      if (homeScore > awayScore) actualOutcome = 0;
      else if (homeScore === awayScore) actualOutcome = 1;
      else actualOutcome = 2;

      const isWinnerHit = match.prediction!.outcome === actualOutcome;
      if (isWinnerHit) winnerHits++;

      // Over/Under 2.5
      let isOUHit = false;
      if (match.prediction!.probabilities.over25 !== undefined) {
        ouTotal++;
        const predictedOver = match.prediction!.probabilities.over25 > 0.5;
        const actualOver = totalGoals > 2.5;
        isOUHit = predictedOver === actualOver;
        if (isOUHit) ouHits++;
      }

      // BTTS
      let isBTTSHit = false;
      if (match.prediction!.probabilities.bttsYes !== undefined) {
        bttsTotal++;
        const predictedBTTS = match.prediction!.probabilities.bttsYes > 0.5;
        const actualBTTS = homeScore > 0 && awayScore > 0;
        isBTTSHit = predictedBTTS === actualBTTS;
        if (isBTTSHit) bttsHits++;
      }

      // Update league stats (using Winner as baseline)
      if (!leagueMap[match.league.id]) {
        leagueMap[match.league.id] = { name: match.league.name, total: 0, hits: 0 };
      }
      leagueMap[match.league.id].total++;
      if (isWinnerHit) leagueMap[match.league.id].hits++;

      return {
        fixture_id: match.fixture_id,
        homeTeam: match.homeTeam.name,
        awayTeam: match.awayTeam.name,
        score: match.score,
        prediction: match.prediction,
        isWinnerHit,
        isOUHit,
        isBTTSHit,
        date: match.date,
        league: match.league.name
      };
    });

    const result = {
      total: finishedMatches.length,
      accuracy: Math.round((winnerHits / finishedMatches.length) * 100),
      markets: {
        winner: Math.round((winnerHits / finishedMatches.length) * 100),
        overUnder: ouTotal > 0 ? Math.round((ouHits / ouTotal) * 100) : 0,
        btts: bttsTotal > 0 ? Math.round((bttsHits / bttsTotal) * 100) : 0
      },
      leagueStats: Object.values(leagueMap).map(l => ({
        ...l,
        accuracy: Math.round((l.hits / l.total) * 100)
      })).sort((a, b) => b.total - a.total),
      recentMatches: processedMatches.slice(0, 10)
    };

    await setCache(cacheKey, JSON.stringify(result), 1800);
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: 'Failed to calculate backtest statistics' });
  }
};

export const triggerManualSync = async (req: Request, res: Response) => {
  const { competitionCode } = req.query;
  
  const today = new Date().toISOString().split('T')[0];

  await syncQueue.add('manual-sync', {
    type: competitionCode ? 'sync-competition' : 'sync-today',
    competitionCode: competitionCode as string,
    date: today
  });

  res.json({ 
    success: true,
    message: 'Processo de sincronização adicionado à fila com sucesso.',
    status: 'queued'
  });
};
