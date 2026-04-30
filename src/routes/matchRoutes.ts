import { Router } from 'express';
import { getTodayMatches, getMatchById } from '../controllers/matchController.js';

const router = Router();

router.get('/today', getTodayMatches);
router.get('/:fixture_id', getMatchById);

export default router;
