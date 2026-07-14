import { getOrCreateAgent } from '../services/elevenlabsService.js';

/**
 * POST /api/agent
 * Creates (or reuses, within this process's lifetime) the demo
 * ElevenLabs conversational agent and returns its ID so the frontend
 * can start a real-time voice session directly against ElevenLabs.
 * src/controllers/agentController.js
 */
export const createOrGetAgent = async (req, res) => {
  try {
    const result = await getOrCreateAgent();
    res.status(200).json({ success: true, ...result });
  } catch (err) {
    // Surface a specific, friendly message for the most common misconfiguration.
    // const status = err?.statusCode || err?.status;
    // if (status === 401) {
    //   return res.status(500).json({
    //     success: false,
    //     error: 'Invalid ElevenLabs API key. Check ELEVENLABS_API_KEY in backend/.env.',
    //   });
    // }
    console.error('Failed to create/get ElevenLabs agent:', err);
    res.status(500).json({
      success: false,
      error: 'Could not reach ElevenLabs to set up the voice agent. Please try again.',
    });
  }
};
