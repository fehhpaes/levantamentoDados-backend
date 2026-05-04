import { Router } from 'express';
import { getTodayMatches, getMatchById, getMatchHistory, getTeamStats, triggerManualSync, getLeagues, getSyncStatus } from '../controllers/matchController.js';

const router = Router();

router.get('/today', getTodayMatches);
router.get('/leagues', getLeagues);
router.get('/history', getMatchHistory);
router.get('/team/:team_id', getTeamStats);
router.get('/sync', triggerManualSync); 
router.get('/sync-status', getSyncStatus); 
router.get('/ping', (req, res) => { res.json({ status: 'online', time: new Date() }); });
router.get('/:fixture_id', getMatchById);

export default router;
