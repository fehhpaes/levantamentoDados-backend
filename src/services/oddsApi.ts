import axios from 'axios';
import dotenv from 'dotenv';
import { Match } from '../models/Match.js';

dotenv.config();

const API_KEY = process.env.ODDS_API_KEY;
const BASE_URL = 'https://api.the-odds-api.com/v4/sports';

const SPORT_MAPPING: Record<string, string> = {
  'BSA': 'soccer_brazil_campeonato',
  'PL': 'soccer_epl',
  'PD': 'soccer_spain_la_liga',
  'BL1': 'soccer_germany_bundesliga',
  'SA': 'soccer_italy_serie_a',
  'FL1': 'soccer_france_ligue_one'
};

export class OddsApiService {
  /**
   * Syncs odds for all supported competitions.
   */
  async syncAllOdds() {
    console.log('[Odds-API] Starting global odds sync...');
    for (const [compCode, sportKey] of Object.entries(SPORT_MAPPING)) {
      try {
        await this.syncCompetitionOdds(sportKey);
      } catch (error: any) {
        console.error(`[Odds-API] Error syncing ${compCode}:`, error.message);
      }
    }
  }

  /**
   * Syncs odds for a specific sport key.
   */
  async syncCompetitionOdds(sportKey: string) {
    if (!API_KEY) {
      console.warn('[Odds-API] API Key missing.');
      return;
    }

    const response = await axios.get(`${BASE_URL}/${sportKey}/odds`, {
      params: {
        apiKey: API_KEY,
        regions: 'eu', // Use 'eu' for most European and Brazilian bookmakers
        markets: 'h2h',
        oddsFormat: 'decimal'
      }
    });

    const oddsData = response.data;
    console.log(`[Odds-API] Received odds for ${oddsData.length} events in ${sportKey}`);

    for (const event of oddsData) {
      await this.updateMatchOdds(event);
    }
  }

  /**
   * Matches an event from Odds-API with a match in our database and updates odds.
   */
  private async updateMatchOdds(event: any) {
    const homeTeamName = event.home_team;
    const awayTeamName = event.away_team;
    const startTime = new Date(event.commence_time);

    // Find match in DB by teams and approximate time (within 24h)
    const match = await Match.findOne({
      status: 'SCHEDULED',
      date: {
        $gte: new Date(startTime.getTime() - 24 * 60 * 60 * 1000),
        $lte: new Date(startTime.getTime() + 24 * 60 * 60 * 1000)
      },
      $or: [
        { 'homeTeam.name': { $regex: new RegExp(homeTeamName, 'i') } },
        { 'awayTeam.name': { $regex: new RegExp(awayTeamName, 'i') } }
      ]
    });

    if (!match) return;

    // Get average odds from all bookmakers provided
    const h2hOdds = this.calculateAverageOdds(event.bookmakers);
    if (!h2hOdds) return;

    if (!match.prediction) {
      match.prediction = {
        outcome: 0,
        probabilities: { homeWin: 0, draw: 0, awayWin: 0 }
      };
    }

    match.prediction.odds = h2hOdds;

    // Calculate Value Bet
    this.calculateValueBet(match);

    await match.save();
    console.log(`[Odds-API] Odds updated for ${match.homeTeam.name} vs ${match.awayTeam.name}`);
  }

  private calculateAverageOdds(bookmakers: any[]) {
    if (!bookmakers || bookmakers.length === 0) return null;

    let homeSum = 0, drawSum = 0, awaySum = 0;
    let count = 0;

    bookmakers.forEach(bm => {
      const market = bm.markets.find((m: any) => m.key === 'h2h');
      if (market) {
        const h = market.outcomes.find((o: any) => o.name === bm.home_team || o.name === bm.away_team ? false : false); // Placeholder logic
        // The Odds API format: outcomes is an array of {name, price}
        const homePrice = market.outcomes.find((o: any) => o.name === bm.home_team)?.price;
        const awayPrice = market.outcomes.find((o: any) => o.name === bm.away_team)?.price;
        const drawPrice = market.outcomes.find((o: any) => o.name === 'Draw')?.price;

        if (homePrice && awayPrice && drawPrice) {
          homeSum += homePrice;
          drawSum += drawPrice;
          awaySum += awayPrice;
          count++;
        }
      }
    });

    if (count === 0) return null;

    return {
      homeWin: Number((homeSum / count).toFixed(2)),
      draw: Number((drawSum / count).toFixed(2)),
      awayWin: Number((awaySum / count).toFixed(2))
    };
  }

  private calculateValueBet(match: any) {
    if (!match.prediction?.probabilities || !match.prediction.odds) return;

    const probs = match.prediction.probabilities;
    const odds = match.prediction.odds;

    // Expected Value = (Probability * Odds) - 1
    const evHome = (probs.homeWin * odds.homeWin) - 1;
    const evDraw = (probs.draw * odds.draw) - 1;
    const evAway = (probs.awayWin * odds.awayWin) - 1;

    const values = [
      { target: 'HOME', ev: evHome },
      { target: 'DRAW', ev: evDraw },
      { target: 'AWAY', ev: evAway }
    ];

    // Find the highest positive EV
    const bestValue = values.sort((a, b) => b.ev - a.ev)[0];

    if (bestValue.ev > 0.15) { // 15% Edge threshold
      match.prediction.valueBet = {
        isFound: true,
        target: bestValue.target,
        expectedValue: Number((bestValue.ev * 100).toFixed(1))
      };
    } else {
      match.prediction.valueBet = { isFound: false, target: '', expectedValue: 0 };
    }
  }
}
