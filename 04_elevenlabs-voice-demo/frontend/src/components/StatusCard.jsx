const STATE_META = {
  idle: { label: 'Idle', color: 'bg-fog' },
  connecting: { label: 'Connecting', color: 'bg-fog' },
  listening: { label: 'Listening', color: 'bg-signal-listen' },
  thinking: { label: 'Thinking', color: 'bg-signal-think' },
  speaking: { label: 'Speaking', color: 'bg-signal-speak' },
  error: { label: 'Disconnected', color: 'bg-signal-error' },
};

/**
 * Small pill showing the current conversation phase. The colored dot
 * mirrors the mic ring's color so the two always agree at a glance.
 */
export default function StatusCard({ phase }) {
  const meta = STATE_META[phase] || STATE_META.idle;
  const isLive = phase === 'listening' || phase === 'thinking' || phase === 'speaking';

  return (
    <div className="inline-flex items-center gap-2.5 rounded-full border border-white/10 bg-white/5 px-4 py-2 backdrop-blur-md">
      <span className="relative flex h-2 w-2">
        {isLive && (
          <span
            data-anim
            className={`absolute inline-flex h-full w-full animate-ping rounded-full ${meta.color} opacity-60`}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${meta.color}`} />
      </span>
      <span className="font-mono text-xs tracking-[0.15em] text-fog uppercase">
        {meta.label}
      </span>
    </div>
  );
}
