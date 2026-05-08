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
    // Use a timeout to avoid hanging if DB is not responding
    const dbPromise = Match.countDocuments().limit(1);
    const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 2000));
    
    await Promise.race([dbPromise, timeoutPromise]);
    
    res.json({ 
      status: 'online', 
      db: 'connected', 
      time: new Date() 
    }); 
  } catch (e) {
    // Still return 200/online even if DB is failing, to keep Render instance alive
    res.json({ status: 'online', db: 'connecting/error', time: new Date() });
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
