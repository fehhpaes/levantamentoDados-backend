import { VirtualBet } from '../models/VirtualBet.js';
import { IMatch } from '../models/Match.js';

/**
 * Resolves all pending virtual bets for a specific match.
 */
export async function resolveBetsForMatch(match: IMatch) {
  if (match.status !== 'FINISHED') return;

  const pendingBets = await VirtualBet.find({ fixtureId: match.fixture_id, status: 'PENDING' });
  if (pendingBets.length === 0) return;

  console.log(`[BetService] Resolving ${pendingBets.length} bets for fixture ${match.fixture_id}`);

  const homeScore = match.score.home;
  const awayScore = match.score.away;
  const totalGoals = homeScore + awayScore;

  for (const bet of pendingBets) {
    let won = false;

    if (bet.market === '1X2') {
      if (bet.selection === 'HOME' && homeScore > awayScore) won = true;
      else if (bet.selection === 'DRAW' && homeScore === awayScore) won = true;
      else if (bet.selection === 'AWAY' && awayScore > homeScore) won = true;
    } else if (bet.market === 'OVER_UNDER_2.5') {
      if (bet.selection === 'OVER' && totalGoals > 2.5) won = true;
      else if (bet.selection === 'UNDER' && totalGoals < 2.5) won = true;
    } else if (bet.market === 'BTTS') {
      if (bet.selection === 'YES' && homeScore > 0 && awayScore > 0) won = true;
      else if (bet.selection === 'NO' && (homeScore === 0 || awayScore === 0)) won = true;
    }

    bet.status = won ? 'WON' : 'LOST';
    bet.result = { homeScore, awayScore };
    await bet.save();
  }
}
