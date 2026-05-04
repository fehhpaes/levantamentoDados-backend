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
    
    // If we have 1 or 0 requests left in the minute, wait to avoid 429
    if (requestsRemaining <= 1) {
      console.log('[Football-Data] Rate limit near. Waiting 10 seconds...');
      await new Promise(resolve => setTimeout(resolve, 10000));
    }
  }

  /**
   * Fetches matches for a specific date range and updates MongoDB.
   */
  async fetchAndSyncMatches(dateFrom: string, dateTo: string): Promise<void> {
    try {
      console.log(`[Football-Data] Fetching fixtures from ${dateFrom} to ${dateTo}...`);
      
      const response = await api.get('/matches', {
        params: { dateFrom, dateTo }
      });

      // Handle Throttling based on headers
      await this.handleRateLimit(response.headers);

      const matches = response.data.matches;
      if (!matches) {
        console.warn('[Football-Data] No matches found in response.');
        return;
      }

      console.log(`[Football-Data] Found ${matches.length} matches.`);

      for (const item of matches) {
        const fixtureId = item.id;
        const status = item.status === 'FINISHED' ? 'FINISHED' : 'SCHEDULED';
        
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.utcDate),
          status: status,
          league: {
            id: item.competition.id,
            name: item.competition.name,
            logo: item.competition.emblem
          },
          homeTeam: { 
            id: item.homeTeam.id, 
            name: item.homeTeam.shortName || item.homeTeam.name,
            logo: item.homeTeam.crest
          },
          awayTeam: { 
            id: item.awayTeam.id, 
            name: item.awayTeam.shortName || item.awayTeam.name,
            logo: item.awayTeam.crest
          },
          score: {
            home: item.score.fullTime.home ?? 0,
            away: item.score.fullTime.away ?? 0
          }
        };

        const result = await Match.findOneAndUpdate(
          { fixture_id: fixtureId },
          { $set: matchData },
          { upsert: true, new: true }
        );
        
        if (result) {
          console.log(`[Football-Data] Saved match: ${matchData.homeTeam.name} vs ${matchData.awayTeam.name} (ID: ${fixtureId})`);
        } else {
          console.error(`[Football-Data] Failed to save match ID: ${fixtureId}`);
        }
      }
      console.log('[Football-Data] Sync completed successfully.');
    } catch (error: any) {
      if (error.response?.status === 429) {
        console.error('[Football-Data] Rate limit exceeded (10 req/min).');
      } else {
        console.error(`[Football-Data] Sync failed:`, error.message);
      }
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
      if (!matches || matches.length === 0) {
        console.log(`[Football-Data] No matches found for ${competitionCode}.`);
        return;
      }

      for (const item of matches) {
        const fixtureId = item.id;
        const status = item.status === 'FINISHED' ? 'FINISHED' : 'SCHEDULED';
        
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.utcDate),
          status: status,
          league: {
            id: item.competition.id,
            name: item.competition.name,
            logo: item.competition.emblem
          },
          homeTeam: { 
            id: item.homeTeam.id, 
            name: item.homeTeam.shortName || item.homeTeam.name,
            logo: item.homeTeam.crest
          },
          awayTeam: { 
            id: item.awayTeam.id, 
            name: item.awayTeam.shortName || item.awayTeam.name,
            logo: item.awayTeam.crest
          },
          score: {
            home: item.score.fullTime.home ?? 0,
            away: item.score.fullTime.away ?? 0
          }
        };

        const result = await Match.findOneAndUpdate(
          { fixture_id: fixtureId },
          { $set: matchData },
          { upsert: true, new: true }
        );

        if (result) {
          console.log(`[Football-Data] [${competitionCode}] Saved: ${matchData.homeTeam.name} vs ${matchData.awayTeam.name} (ID: ${fixtureId})`);
        } else {
          console.error(`[Football-Data] [${competitionCode}] Failed to save ID: ${fixtureId}`);
        }
      }
      console.log(`[Football-Data] ${competitionCode} sync completed.`);
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
