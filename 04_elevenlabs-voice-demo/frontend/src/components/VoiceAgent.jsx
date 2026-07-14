import { useEffect, useRef, useState, useCallback } from 'react';
import { useConversation } from '@elevenlabs/react';
import { fetchAgent } from '../services/api.js';
import StatusCard from './StatusCard.jsx';
import Controls from './Controls.jsx';

const SILENCE_THRESHOLD = 4; // getInputVolume() is roughly 0-100; below this counts as quiet
const SILENCE_TO_THINKING_MS = 550;

const MicIcon = ({ className, style }) => (
  <svg viewBox="0 0 24 24" fill="none" className={className} style={style} aria-hidden="true">
    <path
      d="M12 15a3.5 3.5 0 0 0 3.5-3.5V6a3.5 3.5 0 0 0-7 0v5.5A3.5 3.5 0 0 0 12 15Z"
      stroke="currentColor"
      strokeWidth="1.6"
    />
    <path
      d="M6 11a6 6 0 0 0 12 0M12 19v2"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
    />
  </svg>
);

const PHASE_RING_COLOR = {
  idle: 'var(--color-fog)',
  connecting: 'var(--color-fog)',
  listening: 'var(--color-signal-listen)',
  thinking: 'var(--color-signal-think)',
  speaking: 'var(--color-signal-speak)',
  error: 'var(--color-signal-error)',
};

export default function VoiceAgent() {
  const [phase, setPhase] = useState('idle'); // idle | connecting | listening | thinking | speaking | error
  const [errorMessage, setErrorMessage] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const quietSinceRef = useRef(null);
  const pollRef = useRef(null);

  const conversation = useConversation({
    onConnect: () => setPhase('listening'),
    onDisconnect: () => setPhase('idle'),
    onError: (message) => {
      setErrorMessage(typeof message === 'string' ? message : 'Something went wrong with the connection.');
      setPhase('error');
    },
  });

  const { status, isSpeaking, isListening, startSession, endSession, getInputVolume } = conversation;

  // The SDK exposes only "listening" / "speaking" as a mode — there's no
  // distinct "thinking" event for the gap between the user finishing a
  // sentence and the agent starting to reply. We approximate it: while the
  // SDK still reports "listening", poll the mic's input volume, and once
  // it's been quiet for a short stretch, show "Thinking" instead. As soon
  // as the agent starts speaking (or the user speaks again), we clear it.
  useEffect(() => {
    if (status !== 'connected') return undefined;

    if (isSpeaking) {
      setPhase('speaking');
      quietSinceRef.current = null;
      return undefined;
    }

    if (!isListening) return undefined;

    pollRef.current = setInterval(() => {
      const volume = getInputVolume ? getInputVolume() : 0;
      const now = Date.now();

      if (volume > SILENCE_THRESHOLD) {
        quietSinceRef.current = null;
        setPhase((p) => (p === 'thinking' ? 'listening' : p));
        return;
      }

      if (!quietSinceRef.current) quietSinceRef.current = now;
      if (now - quietSinceRef.current > SILENCE_TO_THINKING_MS) {
        setPhase('thinking');
      } else {
        setPhase((p) => (p === 'thinking' ? p : 'listening'));
      }
    }, 150);

    return () => clearInterval(pollRef.current);
  }, [status, isSpeaking, isListening, getInputVolume]);

  const handleStart = useCallback(async () => {
    setErrorMessage(null);
    setConnecting(true);
    setPhase('connecting');
    try {
      const { agentId } = await fetchAgent();

      // Voice conversations need an explicit mic grant — request it up front
      // so a denial surfaces as our own friendly message, not a cryptic SDK error.
      await navigator.mediaDevices.getUserMedia({ audio: true });

      await startSession({ agentId });
    } catch (err) {
      const message =
        err?.name === 'NotAllowedError'
          ? 'Microphone permission denied. Please allow mic access and try again.'
          : err?.message?.includes('Network') || err?.code === 'ERR_NETWORK'
          ? 'Network error — could not reach the voice service.'
          : err?.message || 'Unable to connect. Please try again.';
      setErrorMessage(message);
      setPhase('error');
    } finally {
      setConnecting(false);
    }
  }, [startSession]);

  const handleEnd = useCallback(() => {
    endSession();
    setPhase('idle');
    quietSinceRef.current = null;
  }, [endSession]);

  const ringColor = PHASE_RING_COLOR[phase] || PHASE_RING_COLOR.idle;

  return (
    <div className="flex flex-col items-center gap-8">
      <div className="relative flex h-48 w-48 items-center justify-center sm:h-56 sm:w-56">
        {/* Idle: a single slow-breathing ring */}
        {phase === 'idle' && (
          <span
            data-anim
            className="absolute inset-2 rounded-full border"
            style={{ borderColor: ringColor, animation: 'idle-breathe 3.2s ease-in-out infinite' }}
          />
        )}

        {/* Connecting: a faint spinning arc */}
        {phase === 'connecting' && (
          <span
            data-anim
            className="absolute inset-3 rounded-full border-2 border-transparent"
            style={{ borderTopColor: ringColor, borderRightColor: ringColor, animation: 'sweep-think 0.9s linear infinite' }}
          />
        )}

        {/* Listening: rippling sonar rings */}
        {phase === 'listening' &&
          [0, 1, 2].map((i) => (
            <span
              key={i}
              data-anim
              className="absolute inset-2 rounded-full border-2"
              style={{
                borderColor: ringColor,
                animation: 'ripple-listen 2.1s ease-out infinite',
                animationDelay: `${i * 0.65}s`,
              }}
            />
          ))}

        {/* Thinking: a rotating dashed scan ring */}
        {phase === 'thinking' && (
          <span
            data-anim
            className="absolute inset-3 rounded-full border-2 border-dashed"
            style={{ borderColor: ringColor, animation: 'sweep-think 1.4s linear infinite' }}
          />
        )}

        {/* Speaking: radial equalizer bars */}
        {phase === 'speaking' &&
          Array.from({ length: 14 }).map((_, i) => (
            <span
              key={i}
              data-anim
              className="absolute h-6 w-[3px] rounded-full origin-bottom"
              style={{
                backgroundColor: ringColor,
                transform: `rotate(${(360 / 14) * i}deg) translateY(-92px)`,
                animation: `bar-speak ${0.5 + (i % 4) * 0.08}s ease-in-out infinite`,
                animationDelay: `${(i % 5) * 0.06}s`,
              }}
            />
          ))}

        {/* Error: soft static red glow */}
        {phase === 'error' && (
          <span className="absolute inset-2 rounded-full border" style={{ borderColor: ringColor, opacity: 0.5 }} />
        )}

        {/* The mic button itself */}
        <button
          type="button"
          onClick={phase === 'idle' || phase === 'error' ? handleStart : undefined}
          disabled={connecting || phase === 'connecting'}
          aria-label={phase === 'idle' || phase === 'error' ? 'Start talking' : 'Voice agent active'}
          className="relative z-10 flex h-28 w-28 items-center justify-center rounded-full
                     bg-surface/80 backdrop-blur-xl border border-white/10 shadow-2xl
                     transition-transform duration-200 disabled:cursor-not-allowed
                     enabled:hover:scale-105 enabled:active:scale-95"
          style={{ boxShadow: `0 0 50px -12px ${ringColor}` }}
        >
          <MicIcon className="h-10 w-10" style={{ color: ringColor }} />
        </button>
      </div>

      <StatusCard phase={phase} />

      {errorMessage && (
        <p className="max-w-xs text-center font-body text-sm text-signal-error/90">{errorMessage}</p>
      )}

      <Controls phase={phase} onStart={handleStart} onEnd={handleEnd} busy={connecting} />
    </div>
  );
}
