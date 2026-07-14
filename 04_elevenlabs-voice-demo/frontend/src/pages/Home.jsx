import { ConversationProvider } from '@elevenlabs/react';
import VoiceAgent from '../components/VoiceAgent.jsx';

export default function Home() {
  return (
    <main className="relative flex min-h-screen items-center justify-center px-6 py-16">
      <div className="ambient-bg" aria-hidden="true" />

      <div className="relative z-10 flex w-full max-w-lg flex-col items-center gap-10 rounded-[28px] border border-white/10 bg-white/[0.04] p-10 text-center shadow-[0_8px_60px_-15px_rgba(0,0,0,0.6)] backdrop-blur-2xl sm:p-14">
        <div className="flex flex-col items-center gap-4">
          <span className="font-mono text-[11px] tracking-[0.3em] text-fog uppercase">
            Voice Agent Demo
          </span>
          <h1 className="font-display text-4xl font-semibold leading-[1.05] tracking-tight text-mist sm:text-5xl">
            ElevenLabs AI
            <br />
            Voice Assistant
          </h1>
          <p className="max-w-xs font-body text-base text-fog">
            Talk with an AI in real time.
          </p>
        </div>

        <ConversationProvider>
          <VoiceAgent />
        </ConversationProvider>
      </div>
    </main>
  );
}
