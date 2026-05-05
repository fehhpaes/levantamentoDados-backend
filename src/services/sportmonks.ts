import axios from 'axios';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const API_KEY = process.env.SPORTMONKS_API_KEY;
const BASE_URL = 'https://api.sportmonks.com/v3/football';

const api = axios.create({
  baseURL: BASE_URL,
  params: {
    api_token: API_KEY
  }
});

export class SportmonksService {
  /**
   * Fetches statistics for a specific fixture and updates the database.
   * Note: Sportmonks uses 'statistics' include in fixtures or a separate endpoint.
   */
  async syncFixtureStats(fixtureId: number): Promise<void> {
    try {
      // In Sportmonks v3, we can get statistics by including them in the fixture call
      const response = await api.get(`/fixtures/${fixtureId}`, {
        params: {
          include: 'statistics'
        }
      });

      const fixtureData = response.data.data;
      const statistics = fixtureData.statistics;

      if (!statistics || statistics.length < 2) {
        console.log(`[Sportmonks] No stats found for fixture ${fixtureId}`);
        return;
      }

      // Sportmonks statistics are usually an array of objects per team
      // We need to map them to our internal format
      const homeStats = statistics.find((s: any) => s.team_id === fixtureData.participants.find((p: any) => p.meta.location === 'home').id);
      const awayStats = statistics.find((s: any) => s.team_id === fixtureData.participants.find((p: any) => p.meta.location === 'away').id);

      if (!homeStats || !awayStats) return;

      const extractValue = (stats: any, typeId: number) => {
        const item = stats.details.find((d: any) => d.type_id === typeId);
        return item ? Number(item.value) : 0;
      };

      // Type IDs for Sportmonks (these are common ones, but may vary):
      // Possession: 45, Shots on Target: 51
      const extractedStats = {
        home_possession: extractValue(homeStats, 45),
        away_possession: extractValue(awayStats, 45),
        home_shots_on_target: extractValue(homeStats, 51),
        away_shots_on_target: extractValue(awayStats, 51)
      };

      await Match.findOneAndUpdate(
        { fixture_id: fixtureId },
        { $set: { stats: extractedStats } }
      );
      console.log(`[Sportmonks] Stats updated for fixture ${fixtureId}`);
    } catch (error: any) {
      console.error(`[Sportmonks] Failed stats sync for ${fixtureId}:`, error.message);
    }
  }

  /**
   * Fetches fixtures for a specific date.
   * Sportmonks v3 uses /fixtures/date/{date}
   */
  async fetchAndSyncMatchesByDate(date: string): Promise<void> {
    try {
      console.log(`[Sportmonks] Fetching fixtures for ${date}...`);
      
      const response = await api.get(`/fixtures/date/${date}`, {
        params: {
          include: 'participants;league;scores'
        }
      });

      const fixtures = response.data.data;
      if (!fixtures) return;

      console.log(`[Sportmonks] Found ${fixtures.length} fixtures.`);

      for (const item of fixtures) {
        const fixtureId = item.id;
        const homeParticipant = item.participants.find((p: any) => p.meta.location === 'home');
        const awayParticipant = item.participants.find((p: any) => p.meta.location === 'away');
        
        const isFinished = item.state?.short_name === 'FT';
        
        const matchData = {
          fixture_id: fixtureId,
          date: new Date(item.starting_at),
          status: isFinished ? 'FINISHED' : 'SCHEDULED',
          league: {
            id: item.league.id,
            name: item.league.name,
            logo: item.league.image_path
          },
          homeTeam: { id: homeParticipant.id, name: homeParticipant.name },
          awayTeam: { id: awayParticipant.id, name: awayParticipant.name },
          score: {
            home: item.scores?.find((s: any) => s.participant_id === homeParticipant.id && s.description === 'CURRENT')?.score?.goals ?? 0,
            away: item.scores?.find((s: any) => s.participant_id === awayParticipant.id && s.description === 'CURRENT')?.score?.goals ?? 0
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
    } catch (error: any) {
      console.error(`[Sportmonks] Sync failed for ${date}:`, error.message);
    }
  }
}
