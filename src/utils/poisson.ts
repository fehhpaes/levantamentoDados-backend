/**
 * Poisson Distribution Utility for Football Predictions
 */

export interface PoissonProbabilities {
  homeWin: number;
  draw: number;
  awayWin: number;
  over25: number;
  under25: number;
  bttsYes: number;
  bttsNo: number;
  exactScores: { score: string; probability: number }[];
}

/**
 * Calculates the Poisson probability of k events occurring given lambda.
 * P(k; λ) = (λ^k * e^-λ) / k!
 */
function poisson(k: number, lambda: number): number {
  if (lambda <= 0) return k === 0 ? 1 : 0;
  return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k);
}

function factorial(n: number): number {
  if (n === 0 || n === 1) return 1;
  let res = 1;
  for (let i = 2; i <= n; i++) res *= i;
  return res;
}

/**
 * Calculates match outcome probabilities using Poisson distribution.
 */
export function calculatePoisson(homeExpGoals: number, awayExpGoals: number): PoissonProbabilities {
  const maxGoals = 6;
  const scores: { score: string; probability: number }[] = [];

  let homeWin = 0;
  let draw = 0;
  let awayWin = 0;
  let over25 = 0;
  let under25 = 0;
  let bttsYes = 0;
  let bttsNo = 0;

  for (let h = 0; h <= maxGoals; h++) {
    for (let a = 0; a <= maxGoals; a++) {
      const prob = poisson(h, homeExpGoals) * poisson(a, awayExpGoals);
      
      scores.push({ score: `${h}-${a}`, probability: prob });

      if (h > a) homeWin += prob;
      else if (h === a) draw += prob;
      else awayWin += prob;

      if (h + a > 2.5) over25 += prob;
      else under25 += prob;

      if (h > 0 && a > 0) bttsYes += prob;
      else bttsNo += prob;
    }
  }

  // Get Top 5 Exact Scores
  const exactScores = scores
    .sort((a, b) => b.probability - a.probability)
    .slice(0, 5);

  // Normalize (ensure sum of 1X2 is 1)
  const total1X2 = homeWin + draw + awayWin;
  
  return {
    homeWin: homeWin / total1X2,
    draw: draw / total1X2,
    awayWin: awayWin / total1X2,
    over25,
    under25,
    bttsYes,
    bttsNo,
    exactScores
  };
}
