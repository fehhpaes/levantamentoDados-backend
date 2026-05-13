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
  formPoints: number; // Weighted sum of points in last 5 matches
  avgXG: number;     // Proxy Expected Goals
}

export interface H2HStats {
  homeWins: number;
  draws: number;
  awayWins: number;
  avgGoals: number;
  totalMatches: number;
}

/**
 * Calculates a proxy xG based on shots on target and possession.
 * This is a simplified model: xG = (ShotsOnTarget * 0.15) + (Possession * 0.01)
 */
const calculateProxyXG = (shots: number, possession: number): number => {
  return (shots * 0.15) + (possession * 0.01);
};

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
      formPoints: 5,
      avgXG: 1.1
    };
  }

  const last5Matches = last10Matches.slice(0, 5);

  let totalPossession = 0;
  let totalShots = 0;
  let totalGoalsScored = 0;
  let totalGoalsConceded = 0;
  let totalXG = 0;
  
  let homeMatches = 0;
  let totalHomeGoalsScored = 0;
  let totalHomeGoalsConceded = 0;
  
  let awayMatches = 0;
  let totalAwayGoalsScored = 0;
  let totalAwayGoalsConceded = 0;

  let weightedPoints = 0;
  const weights = [5, 4, 3, 2, 1]; // Weights for last 5 matches (newest to oldest)

  // Stats over 10 matches for stability
  last10Matches.forEach(match => {
    const isHome = match.homeTeam.id === teamId;
    const possession = (isHome ? match.stats?.home_possession : match.stats?.away_possession) || 50;
    const shots = (isHome ? match.stats?.home_shots_on_target : match.stats?.away_shots_on_target) || 4;
    
    totalPossession += possession;
    totalShots += shots;
    totalXG += calculateProxyXG(shots, possession);
    
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

  // Weighted Form over last 5 matches for "momentum"
  last5Matches.forEach((match, index) => {
    const isHome = match.homeTeam.id === teamId;
    const goalsScored = isHome ? match.score.home : match.score.away;
    const goalsConceded = isHome ? match.score.away : match.score.home;
    
    let pts = 0;
    if (goalsScored > goalsConceded) pts = 3;
    else if (goalsScored === goalsConceded) pts = 1;

    // Apply weight based on recency
    weightedPoints += pts * (weights[index] || 1);
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
    formPoints: weightedPoints / 3, // Normalized to keep scale similar
    avgXG: totalXG / last10Matches.length
  };
}

/**
 * Calculates Head-to-Head stats between two teams.
 */
export async function getH2HStats(homeId: number, awayId: number): Promise<H2HStats> {
  const matches = await Match.find({
    status: 'FINISHED',
    $or: [
      { 'homeTeam.id': homeId, 'awayTeam.id': awayId },
      { 'homeTeam.id': awayId, 'awayTeam.id': homeId }
    ]
  }).sort({ date: -1 }).limit(10);

  if (matches.length === 0) {
    return { homeWins: 0, draws: 0, awayWins: 0, avgGoals: 0, totalMatches: 0 };
  }

  let homeWins = 0;
  let draws = 0;
  let awayWins = 0;
  let totalGoals = 0;

  matches.forEach(m => {
    totalGoals += (m.score.home + m.score.away);
    
    // Outcome from homeId perspective (not necessarily the match.homeTeam)
    const isHomeIdActuallyHome = m.homeTeam.id === homeId;
    const homeScore = isHomeIdActuallyHome ? m.score.home : m.score.away;
    const awayScore = isHomeIdActuallyHome ? m.score.away : m.score.home;

    if (homeScore > awayScore) homeWins++;
    else if (homeScore === awayScore) draws++;
    else awayWins++;
  });

  return {
    homeWins,
    draws,
    awayWins,
    avgGoals: totalGoals / matches.length,
    totalMatches: matches.length
  };
}
