import { Router } from 'express';
import { createOrGetAgent } from '../controllers/agentController.js';

const router = Router();

router.post('/', createOrGetAgent);

export default router;
