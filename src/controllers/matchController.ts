import { Request, Response } from 'express';
import { Match } from '../models/Match.js';

export const getTodayMatches = async (req: Request, res: Response) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(today.getDate() + 1);

    const matches = await Match.find({
      date: { $gte: today, $lt: tomorrow }
    }).sort({ date: 1 });

    res.json(matches);
  } catch {
    res.status(500).json({ error: 'Failed to fetch matches' });
  }
};

export const getMatchById = async (req: Request, res: Response) => {
  try {
    const { fixture_id } = req.params;
    const match = await Match.findOne({ fixture_id: Number(fixture_id) });

    if (!match) {
      return res.status(404).json({ error: 'Match not found' });
    }

    res.json(match);
  } catch {
    res.status(500).json({ error: 'Internal server error' });
  }
};
