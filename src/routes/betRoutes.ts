import { Router } from 'express';
import { placeBet, getUserBets } from '../controllers/betController.js';

const router = Router();

router.post('/', placeBet);
router.get('/user/:userId', getUserBets);

export default router;
