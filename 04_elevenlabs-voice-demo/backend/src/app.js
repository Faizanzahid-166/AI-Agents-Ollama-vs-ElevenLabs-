import express from 'express';
import cors from 'cors';
import agentRoutes from './routes/agent.js';

const app = express();

app.use(cors({ origin: process.env.FRONTEND_URL || 'http://localhost:5173' }));
app.use(express.json());

app.get('/api/health', (req, res) => res.json({ success: true, status: 'ok' }));
app.use('/api/agent', agentRoutes);

// Not-found handler
app.use((req, res) => {
  res.status(404).json({ success: false, error: `Route not found: ${req.method} ${req.originalUrl}` });
});

// Central error handler — keeps controllers free of repetitive try/catch boilerplate
// for anything that slips past a controller's own handling.
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  console.error(err);
  res.status(500).json({ success: false, error: 'Something went wrong. Please try again.' });
});

export default app;
