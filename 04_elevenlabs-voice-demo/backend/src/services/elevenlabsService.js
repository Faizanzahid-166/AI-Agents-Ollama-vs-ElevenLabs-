import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';

if (!process.env.ELEVENLABS_API_KEY) {
  console.error('Missing ELEVENLABS_API_KEY in .env');
  throw new Error('Missing ELEVENLABS_API_KEY in .env');
}


// The SDK reads ELEVENLABS_API_KEY from the environment automatically, but
// we pass it explicitly so a misconfigured .env fails with a clear error
// instead of a confusing 401 on the first request.
const elevenlabs = new ElevenLabsClient({ apiKey: process.env.ELEVENLABS_API_KEY });

/**
 * This demo has "no database" by design, so we can't persist an agent ID
 * across server restarts. But recreating a brand-new agent on every single
 * click of "Start Talking" would litter your ElevenLabs workspace with
 * duplicate agents on every page reload. As a middle ground: cache the
 * created agent in memory for the lifetime of this Node process. Restart
 * the server and it creates a fresh one; within a single run, repeated
 * clicks reuse the same agent.
 */
let cachedAgent = null;

const AGENT_NAME = 'Demo Voice Agent';
const SYSTEM_PROMPT =
  'You are a friendly, upbeat AI assistant having a real-time voice conversation. ' +
  'Keep answers conversational and reasonably brief, since this is spoken aloud. ' +
  'Be helpful, curious, and personable.';
const FIRST_MESSAGE = "Hi there! I'm your AI assistant — what's on your mind?";

/**
 * Creates the demo agent if one hasn't been created yet this run, otherwise
 * returns the cached one. Returns { agentId, name, cached }.
 */
export const getOrCreateAgent = async () => {
  if (cachedAgent) {
    return { ...cachedAgent, cached: true };
  }

  const agent = await elevenlabs.conversationalAi.agents.create({
    name: AGENT_NAME,
    conversationConfig: {
      agent: {
        prompt: {
          prompt: SYSTEM_PROMPT,
        },
        firstMessage: FIRST_MESSAGE,
      },
    },
  });

  cachedAgent = { agentId: agent.agentId, name: AGENT_NAME };
  return { ...cachedAgent, cached: false };
};
