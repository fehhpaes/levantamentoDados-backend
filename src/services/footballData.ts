import axios from 'axios';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const API_KEY = process.env.FOOTBALL_DATA_KEY;
const BASE_URL = 'https://api.football-data.org/v4';

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    'X-Auth-Token': API_KEY || ''
  }
});

export class FootballDataService {
  /**
   * Utility to handle rate limiting based on response headers.
   */
  private async handleRateLimit(headers: any): Promise<void> {
    const requestsRemaining = parseInt(headers['x-requests-available-minute'] || '10', 10);
    if (requestsRemaining <= 1) {
      console.log('[Football-Data] Rate limit near. Waiting 10 seconds...');
      await new Promise(resolve => setTimeout(resolve, 10000));
    }
  }

  /**
   * Private helper to map and save match data consistently.
   */
  private async saveMatchData(item: any, competition?: any): Promise<boolean> {
    try {
      const fixtureId = Number(item.id || 0);
      if (fixtureId === 0) return false;

      const status = item.status === 'FINISHED' ? 'FINISHED' : 'SCHEDULED';
      
      // Use competition from item or fallback to provided competition object
      const compInfo = item.competition || competition || {};

      const matchData = {
        fixture_id: fixtureId,
        date: new Date(item.utcDate || new Date()),
        status: status,
        league: {
          id: Number(compInfo.id || 0),
          name: compInfo.name || 'Liga Desconhecida',
          logo: compInfo.emblem || ''
        },
        homeTeam: { 
          id: Number(item.homeTeam?.id || 0), 
          name: item.homeTeam?.shortName || item.homeTeam?.name || 'Time Casa',
          logo: item.homeTeam?.crest || ''
        },
        awayTeam: { 
          id: Number(item.awayTeam?.id || 0), 
          name: item.awayTeam?.shortName || item.awayTeam?.name || 'Time Fora',
          logo: item.awayTeam?.crest || ''
        },
        score: {
          home: Number(item.score?.fullTime?.home ?? 0),
          away: Number(item.score?.fullTime?.away ?? 0)
        }
      };

      const result = await Match.findOneAndUpdate(
        { fixture_id: fixtureId },
        { $set: matchData },
        { upsert: true, new: true, setDefaultsOnInsert: true }
      );
      
      if (result) {
        console.log(`[Football-Data] SAVED: ${matchData.homeTeam.name} vs ${matchData.awayTeam.name} (${fixtureId})`);
        return true;
      }
      return false;
    } catch (error: any) {
      console.error(`[Football-Data] ERROR SAVING ID ${item.id}:`, error.message);
      return false;
    }
  }

  /**
   * Fetches matches for a specific date range and updates MongoDB.
   */
  async fetchAndSyncMatches(dateFrom: string, dateTo: string): Promise<void> {
    try {
      console.log(`[Football-Data] Fetching ALL fixtures from ${dateFrom} to ${dateTo}...`);
      const response = await api.get('/matches', { params: { dateFrom, dateTo } });
      await this.handleRateLimit(response.headers);

      const matches = response.data.matches;
      if (!matches || matches.length === 0) {
        console.warn('[Football-Data] No matches found for the period.');
        return;
      }

      let savedCount = 0;
      for (const item of matches) {
        const success = await this.saveMatchData(item);
        if (success) savedCount++;
      }
      console.log(`[Football-Data] Sync finished. Total saved: ${savedCount}`);
    } catch (error: any) {
      console.error(`[Football-Data] Global sync failed:`, error.message);
    }
  }

  /**
   * Syncs matches for a specific competition and date range.
   */
  async syncCompetitionMatches(competitionCode: string, dateFrom: string, dateTo: string): Promise<void> {
    try {
      console.log(`[Football-Data] Syncing ${competitionCode} from ${dateFrom} to ${dateTo}...`);
      const response = await api.get(`/competitions/${competitionCode}/matches`, {
        params: { dateFrom, dateTo }
      });
      await this.handleRateLimit(response.headers);

      const matches = response.data.matches;
      const competition = response.data.competition; // Get root competition info

      if (!matches || matches.length === 0) {
        console.log(`[Football-Data] No matches found for ${competitionCode}.`);
        return;
      }

      let savedCount = 0;
      for (const item of matches) {
        const success = await this.saveMatchData(item, competition);
        if (success) savedCount++;
      }
      console.log(`[Football-Data] ${competitionCode} sync finished. Saved: ${savedCount}`);
    } catch (error: any) {
      console.error(`[Football-Data] ${competitionCode} sync failed:`, error.message);
    }
  }

  /**
   * Syncs matches for today.
   */
  async syncTodayMatches(): Promise<void> {
    const today = new Date().toISOString().split('T')[0];
    await this.fetchAndSyncMatches(today, today);
  }
}
