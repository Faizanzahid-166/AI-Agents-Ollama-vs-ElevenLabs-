import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

const client = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

/**
 * Asks our backend to create (or reuse) the demo ElevenLabs agent and
 * returns its agentId. The frontend then talks to ElevenLabs directly for
 * the actual real-time voice session — the backend never touches audio.
 */
export const fetchAgent = async () => {
  const { data } = await client.post('/api/agent');
  if (!data.success) {
    throw new Error(data.error || 'Could not set up the voice agent.');
  }
  return data; // { agentId, name, cached }
};


export const HealthCheck = async () => {
  const { data } = await client.get('/api/health');
  if (!data.success) {
    throw new Error(data.error || 'Health check failed.');
  }
  return data; // { success: true }
};
