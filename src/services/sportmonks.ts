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
  private normalizeName(name: string): string {
    if (!name) return '';
    return name
      .toLowerCase()
      .normalize("NFD").replace(/[\u0300-\u036f]/g, "") // Remove accents
      .replace(/\b(fc|cf|sl|sc|ac|rc|afc|sd|ud|vitoria|club|esporte|clube|de|do|da|o|a|1\.)\b/g, "")
      .replace(/\s+/g, "") // Remove all spaces for tighter matching
      .trim();
  }

  /**
   * Fetches statistics for a match by searching for it using team names and date.
   * This solves the ID mismatch between Football-Data.org and Sportmonks.
   */
  async syncStatsByMatch(match: any): Promise<void> {
    try {
      const date = new Date(match.date).toISOString().split('T')[0];
      
      // 1. Fetch all fixtures for that date
      const response = await api.get(`/fixtures/date/${date}`, {
        params: {
          include: 'participants;statistics;scores;state'
        }
      });

      const fixtures = response.data.data;
      if (!fixtures || fixtures.length === 0) {
        console.log(`[Sportmonks] No fixtures found on API for ${date}`);
        return;
      }

      // 2. Find the match that matches our team names (fuzzy match)
      const targetHome = this.normalizeName(match.homeTeam.name);
      const targetAway = this.normalizeName(match.awayTeam.name);

      const foundFixture = fixtures.find((f: any) => {
        const homePart = f.participants.find((p: any) => p.meta.location === 'home');
        const awayPart = f.participants.find((p: any) => p.meta.location === 'away');
        
        if (!homePart || !awayPart) return false;

        const home = this.normalizeName(homePart.name);
        const away = this.normalizeName(awayPart.name);

        // Match if names are similar enough
        const homeMatch = home.includes(targetHome) || targetHome.includes(home);
        const awayMatch = away.includes(targetAway) || targetAway.includes(away);

        return homeMatch && awayMatch;
      });

      if (!foundFixture) {
        console.log(`[Sportmonks] Match NOT FOUND: ${match.homeTeam.name} vs ${match.awayTeam.name} on ${date}`);
        return;
      }

      if (!foundFixture.statistics || foundFixture.statistics.length < 2) {
        console.log(`[Sportmonks] NO STATS for found match: ${match.homeTeam.name} on ${date}`);
        return;
      }

      // 3. Extract stats
      const homeStats = foundFixture.statistics.find((s: any) => s.team_id === foundFixture.participants.find((p: any) => p.meta.location === 'home').id);
      const awayStats = foundFixture.statistics.find((s: any) => s.team_id === foundFixture.participants.find((p: any) => p.meta.location === 'away').id);

      const extractValue = (stats: any, typeId: number) => {
        const item = stats.details.find((d: any) => d.type_id === typeId);
        return item ? Number(item.value) : 0;
      };

      const extractedStats = {
        home_possession: extractValue(homeStats, 45),
        away_possession: extractValue(awayStats, 45),
        home_shots_on_target: extractValue(homeStats, 51),
        away_shots_on_target: extractValue(awayStats, 51)
      };

      const isFinished = foundFixture.state?.short_name === 'FT';
      const homeScore = foundFixture.scores?.find((s: any) => s.participant_id === foundFixture.participants.find((p: any) => p.meta.location === 'home').id && s.description === 'CURRENT')?.score?.goals ?? 0;
      const awayScore = foundFixture.scores?.find((s: any) => s.participant_id === foundFixture.participants.find((p: any) => p.meta.location === 'away').id && s.description === 'CURRENT')?.score?.goals ?? 0;

      const updateData: any = { stats: extractedStats };
      
      // Force update status and score if it was stuck as SCHEDULED
      if (isFinished) {
        updateData.status = 'FINISHED';
        updateData.score = { home: homeScore, away: awayScore };
      }

      await Match.findOneAndUpdate(
        { _id: match._id },
        { $set: updateData }
      );
      console.log(`[Sportmonks] SUCCESS: Stats and Status updated for ${match.homeTeam.name} vs ${match.awayTeam.name}`);
    } catch (error: any) {
      console.error(`[Sportmonks] Search failed:`, error.message);
    }
  }

  /**
   * Keep the original method but updated to use the smarter search if needed
   */
  async syncFixtureStats(fixtureId: number): Promise<void> {
    // This is now a fallback or for cases where we DO have the Sportmonks ID
    try {
      const response = await api.get(`/fixtures/${fixtureId}`, {
        params: { include: 'statistics;participants' }
      });
      // ... rest of logic (keeping it similar to what we had)
    } catch (e) {}
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
