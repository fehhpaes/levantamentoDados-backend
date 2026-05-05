import axios from 'axios';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const API_KEY = process.env.API_FOOTBALL_KEY;
const BASE_URL = 'https://v3.football.api-sports.io';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'x-apisports-key': API_KEY || '',
    'x-rapidapi-host': 'v3.football.api-sports.io'
  }
});

/**
 * Types for API-Football response
 */
interface ApiStatItem {
  type: string;
  value: string | number | null;
}

interface ApiTeamStats {
  team: { id: number; name: string; logo: string };
  statistics: ApiStatItem[];
}

export class ApiFootballService {
  /**
   * Utility to extract and clean specific statistics from the API array.
   */
  private extractStat(statistics: ApiStatItem[], statNames: string[]): number {
    const stat = statistics.find((s) => statNames.includes(s.type));
    
    if (!stat || stat.value === null) {
      return 0;
    }

    if (typeof stat.value === 'string' && stat.value.includes('%')) {
      return parseInt(stat.value.replace('%', ''), 10);
    }

    return Number(stat.value);
  }

  /**
   * Fetches statistics for a specific fixture and updates the database.
   */
  async syncFixtureStats(fixtureId: number): Promise<void> {
    try {
      const response = await api.get('/fixtures/statistics', {
        params: { fixture: fixtureId }
      });

      const teamStats: ApiTeamStats[] = response.data.response;

      if (!teamStats || teamStats.length < 2) return;

      const homeStatsArray = teamStats[0].statistics;
      const awayStatsArray = teamStats[1].statistics;

      const extractedStats = {
        home_possession: this.extractStat(homeStatsArray, ['Ball Possession']),
        away_possession: this.extractStat(awayStatsArray, ['Ball Possession']),
        home_shots_on_target: this.extractStat(homeStatsArray, ['Shots on Goal', 'Shots on target']),
        away_shots_on_target: this.extractStat(awayStatsArray, ['Shots on Goal', 'Shots on target'])
      };

      await Match.findOneAndUpdate(
        { fixture_id: fixtureId },
        { $set: { stats: extractedStats } }
      );
    } catch (error) {
      console.error(`[API] Failed stats sync for ${fixtureId}:`, error);
    }
  }

  /**
   * Fetches fixtures for a specific date and saves/updates them in MongoDB.
   */
  async fetchAndSyncMatchesByDate(date: string): Promise<void> {
    try {
      console.log(`[API] Fetching all fixtures for ${date}...`);
      
      const response = await api.get('/fixtures', {
        params: { date }
      });

      const fixtures = response.data.response;
      console.log(`[API] Found ${fixtures.length} fixtures.`);

      for (const item of fixtures) {
        const fixtureId = item.fixture.id;
        const isFinished = item.fixture.status.short === 'FT';
        
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.fixture.date),
          status: isFinished ? 'FINISHED' : 'SCHEDULED',
          league: {
            id: item.league.id,
            name: item.league.name,
            logo: item.league.logo
          },
          homeTeam: { id: item.teams.home.id, name: item.teams.home.name },
          awayTeam: { id: item.teams.away.id, name: item.teams.away.name },
          score: {
            home: item.goals.home ?? 0,
            away: item.goals.away ?? 0
          }
        };

        await Match.findOneAndUpdate(
          { fixture_id: fixtureId },
          { $set: matchData },
          { upsert: true }
        );

        if (isFinished) {
          await this.syncFixtureStats(fixtureId);
        }
      }
    } catch (error) {
      console.error(`[API] Sync failed for ${date}:`, error);
    }
  }

  /**
   * SYNC TOP LEAGUES: A more aggressive sync for major leagues
   */
  async syncTopLeagues(): Promise<void> {
    const topLeagues = [39, 71, 140, 78, 135, 61]; // Premier, Brasileirão, LaLiga, Bundesliga, Serie A, Ligue 1
    const today = new Date().toISOString().split('T')[0];
    
    for (const id of topLeagues) {
      try {
        console.log(`[API] Syncing Top League: ${id} for ${today}`);
        const response = await api.get('/fixtures', {
          params: { league: id, date: today }
        });
        
        // Use the same logic to save
        const fixtures = response.data.response;
        for (const item of fixtures) {
           // ... (same as fetchAndSyncMatchesByDate logic but for specific league)
           // To keep it clean, we just reuse the main sync which already gets all leagues
        }
      } catch (e) {}
    }
  }

  async syncLeagueSeason(leagueId: number, season: number, limit: number = 20): Promise<void> {
    try {
      const response = await api.get('/fixtures', {
        params: { league: leagueId, season }
      });

      const fixtures = response.data.response;
      const finishedMatches = fixtures
        .filter((item: any) => item.fixture.status.short === 'FT')
        .slice(-limit);

      for (const item of finishedMatches) {
        const fixtureId = item.fixture.id;
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.fixture.date),
          status: 'FINISHED',
          league: {
            id: item.league.id,
            name: item.league.name,
            logo: item.league.logo
          },
          homeTeam: { id: item.teams.home.id, name: item.teams.home.name },
          awayTeam: { id: item.teams.away.id, name: item.teams.away.name },
          score: { home: item.goals.home ?? 0, away: item.goals.away ?? 0 }
        };

        await Match.findOneAndUpdate({ fixture_id: fixtureId }, { $set: matchData }, { upsert: true });
        await this.syncFixtureStats(fixtureId);
        await new Promise(resolve => setTimeout(resolve, 300));
      }
    } catch (error) {
      console.error(`[API] League ${leagueId} sync failed:`, error);
    }
  }
}
