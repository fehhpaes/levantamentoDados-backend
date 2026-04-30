import { Match } from '../models/Match.js';

export interface TeamStats {
  avgPossession: number;
  avgShotsOnTarget: number;
}

/**
 * Calculates the average stats (possession and shots on target) for a specific team
 * based on their last 5 finished matches.
 * 
 * @param teamId - The unique ID of the football team
 * @returns Promise<TeamStats>
 */
export async function getTeamMovingAverage(teamId: number): Promise<TeamStats> {
  const lastMatches = await Match.find({
    status: 'FINISHED',
    $or: [{ 'homeTeam.id': teamId }, { 'awayTeam.id': teamId }]
  })
    .sort({ date: -1 })
    .limit(5);

  if (lastMatches.length === 0) {
    return { avgPossession: 50, avgShotsOnTarget: 4 }; // Default baseline
  }

  let totalPossession = 0;
  let totalShots = 0;

  lastMatches.forEach(match => {
    if (match.homeTeam.id === teamId) {
      totalPossession += match.stats?.home_possession || 50;
      totalShots += match.stats?.home_shots_on_target || 4;
    } else {
      totalPossession += match.stats?.away_possession || 50;
      totalShots += match.stats?.away_shots_on_target || 4;
    }
  });

  return {
    avgPossession: totalPossession / lastMatches.length,
    avgShotsOnTarget: totalShots / lastMatches.length
  };
}
