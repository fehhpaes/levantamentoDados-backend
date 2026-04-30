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
   * Handles percentage strings and null values.
   */
  private extractStat(statistics: ApiStatItem[], statName: string): number {
    const stat = statistics.find((s) => s.type === statName);
    
    if (!stat || stat.value === null) {
      return 0;
    }

    // Clean percentage values (e.g., "54%")
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
      console.log(`Fetching statistics for fixture: ${fixtureId}...`);
      const response = await api.get('/fixtures/statistics', {
        params: { fixture: fixtureId }
      });

      const teamStats: ApiTeamStats[] = response.data.response;

      // Ensure we have data for both teams
      if (!teamStats || teamStats.length < 2) {
        console.warn(`Insufficient statistics data for fixture ${fixtureId}`);
        return;
      }

      const homeStatsArray = teamStats[0].statistics;
      const awayStatsArray = teamStats[1].statistics;

      const extractedStats = {
        home_possession: this.extractStat(homeStatsArray, 'Ball Possession'),
        away_possession: this.extractStat(awayStatsArray, 'Ball Possession'),
        home_shots_on_target: this.extractStat(homeStatsArray, 'Shots on Goal'),
        away_shots_on_target: this.extractStat(awayStatsArray, 'Shots on Goal')
      };

      await Match.findOneAndUpdate(
        { fixture_id: fixtureId },
        { $set: { stats: extractedStats } }
      );

      console.log(`Statistics successfully updated for fixture ${fixtureId}`);
    } catch (error) {
      console.error(`Failed to sync statistics for fixture ${fixtureId}:`, error);
    }
  }

  /**
   * Fetches fixtures for a specific date and saves/updates them in MongoDB.
   * If a match is finished, it triggers the statistics sync.
   */
  async fetchAndSyncMatchesByDate(date: string): Promise<void> {
    try {
      console.log(`Fetching matches for date: ${date}...`);
      const response = await api.get('/fixtures', {
        params: { date }
      });

      const fixtures = response.data.response;

      for (const item of fixtures) {
        const fixtureId = item.fixture.id;
        const isFinished = item.fixture.status.short === 'FT';
        
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.fixture.date),
          status: isFinished ? 'FINISHED' : 'SCHEDULED',
          homeTeam: { 
            id: item.teams.home.id, 
            name: item.teams.home.name 
          },
          awayTeam: { 
            id: item.teams.away.id, 
            name: item.teams.away.name 
          },
          score: {
            home: item.goals.home ?? 0,
            away: item.goals.away ?? 0
          }
        };

        // Upsert the match base data
        await Match.findOneAndUpdate(
          { fixture_id: fixtureId },
          { $set: matchData },
          { upsert: true }
        );

        // If the match is finished, fetch and update real statistics
        if (isFinished) {
          await this.syncFixtureStats(fixtureId);
        }
      }

      console.log(`Daily sync completed for ${date}. Total fixtures: ${fixtures.length}`);
    } catch (error) {
      console.error(`Error during match sync for date ${date}:`, error);
    }
  }
}
