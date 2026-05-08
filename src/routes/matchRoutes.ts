import { Router } from 'express';
import { Match } from '../models/Match.js';
import { getTodayMatches, getMatchById, getMatchHistory, getTeamStats, triggerManualSync, getLeagues, getSyncStatus, testDatabaseWrite, clearDatabase, getTopPredictions, getBacktestStats, getBetsReport } from '../controllers/matchController.js';

const router = Router();

router.get('/today', getTodayMatches);
router.get('/top', getTopPredictions);
router.get('/report', getBetsReport);
router.get('/backtest', getBacktestStats);
router.get('/leagues', getLeagues);
router.get('/history', getMatchHistory);
router.get('/team/:team_id', getTeamStats);
router.get('/sync', triggerManualSync); 
router.get('/sync-status', getSyncStatus); 
router.get('/db-test', testDatabaseWrite); 
router.get('/clear', clearDatabase); 
router.get('/ping', async (req, res) => { 
  try {
    // Basic DB check to keep the connection and instance alive
    const count = await Match.countDocuments().limit(1);
    res.json({ 
      status: 'online', 
      db: 'connected', 
      count,
      time: new Date() 
    }); 
  } catch (e) {
    res.json({ status: 'online', db: 'error', time: new Date() });
  }
});
router.get('/debug/clear-cache', async (req, res) => {
  const { clearAllCache } = await import('../services/redis.js');
  await clearAllCache();
  res.json({ success: true, message: 'All cache cleared for debugging' });
});
router.get('/debug/force-backtest', async (req, res) => {
  const { syncQueue } = await import('../queues/syncQueue.js');
  await syncQueue.add('force-backtest-all', { type: 'force-backtest' });
  res.json({ success: true, message: 'Full backtest process added to queue' });
});
router.get('/debug/force-sync-past', async (req, res) => {
  const { syncQueue } = await import('../queues/syncQueue.js');
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const dateStr = yesterday.toISOString().split('T')[0];
  await syncQueue.add('force-sync-yesterday', { type: 'sync-today', date: dateStr });
  res.json({ success: true, message: `Sync for ${dateStr} added to queue` });
});
router.get('/:fixture_id', getMatchById);

export default router;
