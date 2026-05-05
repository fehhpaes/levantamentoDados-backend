import { Match } from '../models/Match.js';

export interface TeamStats {
  avgPossession: number;
  avgShotsOnTarget: number;
  avgGoalsScored: number;
  avgGoalsConceded: number;
  avgHomeGoalsScored: number;
  avgHomeGoalsConceded: number;
  avgAwayGoalsScored: number;
  avgAwayGoalsConceded: number;
  formPoints: number; // Sum of points in last 5 matches (W=3, D=1, L=0)
}

/**
 * Calculates the average stats and form for a specific team
 * based on their last 10 finished matches.
 */
export async function getTeamMovingAverage(teamId: number): Promise<TeamStats> {
  const last10Matches = await Match.find({
    status: 'FINISHED',
    $or: [{ 'homeTeam.id': teamId }, { 'awayTeam.id': teamId }]
  })
    .sort({ date: -1 })
    .limit(10);

  if (last10Matches.length === 0) {
    return { 
      avgPossession: 50, 
      avgShotsOnTarget: 4,
      avgGoalsScored: 1,
      avgGoalsConceded: 1,
      avgHomeGoalsScored: 1,
      avgHomeGoalsConceded: 1,
      avgAwayGoalsScored: 1,
      avgAwayGoalsConceded: 1,
      formPoints: 5
    };
  }

  const last5Matches = last10Matches.slice(0, 5);

  let totalPossession = 0;
  let totalShots = 0;
  let totalGoalsScored = 0;
  let totalGoalsConceded = 0;
  
  let homeMatches = 0;
  let totalHomeGoalsScored = 0;
  let totalHomeGoalsConceded = 0;
  
  let awayMatches = 0;
  let totalAwayGoalsScored = 0;
  let totalAwayGoalsConceded = 0;

  let totalPoints = 0;

  // Stats over 10 matches for stability
  last10Matches.forEach(match => {
    const isHome = match.homeTeam.id === teamId;
    totalPossession += (isHome ? match.stats?.home_possession : match.stats?.away_possession) || 50;
    totalShots += (isHome ? match.stats?.home_shots_on_target : match.stats?.away_shots_on_target) || 4;
    
    const goalsScored = isHome ? match.score.home : match.score.away;
    const goalsConceded = isHome ? match.score.away : match.score.home;
    
    totalGoalsScored += goalsScored;
    totalGoalsConceded += goalsConceded;

    if (isHome) {
      homeMatches++;
      totalHomeGoalsScored += goalsScored;
      totalHomeGoalsConceded += goalsConceded;
    } else {
      awayMatches++;
      totalAwayGoalsScored += goalsScored;
      totalAwayGoalsConceded += goalsConceded;
    }
  });

  // Form over last 5 matches for "momentum"
  last5Matches.forEach(match => {
    const isHome = match.homeTeam.id === teamId;
    const goalsScored = isHome ? match.score.home : match.score.away;
    const goalsConceded = isHome ? match.score.away : match.score.home;
    if (goalsScored > goalsConceded) totalPoints += 3;
    else if (goalsScored === goalsConceded) totalPoints += 1;
  });

  return {
    avgPossession: totalPossession / last10Matches.length,
    avgShotsOnTarget: totalShots / last10Matches.length,
    avgGoalsScored: totalGoalsScored / last10Matches.length,
    avgGoalsConceded: totalGoalsConceded / last10Matches.length,
    avgHomeGoalsScored: homeMatches > 0 ? totalHomeGoalsScored / homeMatches : 1,
    avgHomeGoalsConceded: homeMatches > 0 ? totalHomeGoalsConceded / homeMatches : 1,
    avgAwayGoalsScored: awayMatches > 0 ? totalAwayGoalsScored / awayMatches : 1,
    avgAwayGoalsConceded: awayMatches > 0 ? totalAwayGoalsConceded / awayMatches : 1,
    formPoints: totalPoints
  };
}
