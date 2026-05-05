import { Request, Response } from 'express';
import { VirtualBet } from '../models/VirtualBet.js';
import { Match } from '../models/Match.js';

/**
 * Places a new virtual bet.
 */
export const placeBet = async (req: Request, res: Response) => {
  try {
    const { userId, fixtureId, market, selection, odds, stake } = req.body;

    const match = await Match.findOne({ fixture_id: fixtureId });
    if (!match) {
      return res.status(404).json({ error: 'Match not found' });
    }

    if (match.status !== 'SCHEDULED') {
      return res.status(400).json({ error: 'Cannot bet on a match that has already started or finished.' });
    }

    const potentialReturn = stake * odds;

    const newBet = new VirtualBet({
      userId,
      fixtureId,
      matchInfo: {
        homeTeam: match.homeTeam.name,
        awayTeam: match.awayTeam.name,
        league: match.league.name,
        date: match.date
      },
      market,
      selection,
      odds,
      stake,
      potentialReturn,
      status: 'PENDING'
    });

    await newBet.save();
    res.status(201).json(newBet);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
};

/**
 * Fetches all bets and stats for a specific user.
 */
export const getUserBets = async (req: Request, res: Response) => {
  try {
    const { userId } = req.params;
    const bets = await VirtualBet.find({ userId }).sort({ createdAt: -1 });

    // Calculate Stats
    let totalStaked = 0;
    let totalReturned = 0;
    let wonCount = 0;
    let lostCount = 0;

    bets.forEach(bet => {
      totalStaked += bet.stake;
      if (bet.status === 'WON') {
        totalReturned += bet.potentialReturn;
        wonCount++;
      } else if (bet.status === 'LOST') {
        lostCount++;
      }
    });

    const profit = totalReturned - totalStaked;
    const roi = totalStaked > 0 ? (profit / totalStaked) * 100 : 0;
    const winRate = (wonCount + lostCount) > 0 ? (wonCount / (wonCount + lostCount)) * 100 : 0;

    res.json({
      bets,
      stats: {
        totalStaked,
        totalReturned,
        profit,
        roi,
        winRate,
        wonCount,
        lostCount,
        totalBets: bets.length
      }
    });
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
};
