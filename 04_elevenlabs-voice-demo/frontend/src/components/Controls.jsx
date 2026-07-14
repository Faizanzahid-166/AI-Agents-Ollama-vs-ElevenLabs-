/**
 * The one action available at any given time: start the conversation from
 * idle/error, or end it once connected. Deliberately never shows both at
 * once — a live call only has one thing you'd do next.
 */
export default function Controls({ phase, onStart, onEnd, busy }) {
  const isActive = phase === 'connecting' || phase === 'listening' || phase === 'thinking' || phase === 'speaking';

  if (isActive) {
    return (
      <button
        type="button"
        onClick={onEnd}
        className="group inline-flex items-center gap-2 rounded-full bg-signal-error/10 px-6 py-3
                   font-body text-sm font-medium text-signal-error border border-signal-error/30
                   transition-all duration-200 hover:bg-signal-error/20 hover:border-signal-error/50
                   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-error"
      >
        <span className="h-2 w-2 rounded-sm bg-signal-error" />
        End Conversation
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onStart}
      disabled={busy}
      className="inline-flex items-center gap-2 rounded-full bg-mist px-7 py-3 font-body text-sm
                 font-semibold text-void shadow-[0_0_30px_-8px_rgba(139,92,246,0.7)]
                 transition-all duration-200 hover:scale-[1.03] hover:shadow-[0_0_40px_-6px_rgba(139,92,246,0.9)]
                 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100
                 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal-speak"
    >
      {busy ? 'Connecting…' : 'Start Talking'}
    </button>
  );
}
