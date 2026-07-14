// src/components/WelcomeScreen.jsx
import React from 'react';

const STARTERS = [
  "Tell me about your weekend plans.",
  "What's your favorite hobby and why?",
  "Describe your dream travel destination.",
  "What did you do yesterday?",
  "Talk about a movie you recently watched.",
  "What are your goals for this year?",
];

export function WelcomeScreen({ onSelectStarter }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-6 py-12">
      {/* Logo / Hero */}
      <div className="text-center">
        <div className="text-5xl mb-4">🎓</div>
        <h1 className="text-3xl font-semibold gradient-text mb-2">SpeakWise</h1>
        <p className="text-muted text-sm max-w-sm leading-relaxed">
          Your AI English coach powered by{' '}
          <span className="text-slate-400 font-medium">llama3:latest</span>.
          Speak or type — get instant corrections, improvements, and encouragement.
        </p>
      </div>

      {/* Feature pills */}
      <div className="flex flex-wrap justify-center gap-2 max-w-md">
        {[
          '✅ Grammar correction',
          '💡 Better phrasing',
          '📊 Speaking score',
          '🔊 Voice feedback',
          '💬 Natural conversation',
          '🎯 Follow-up questions',
        ].map((f) => (
          <span
            key={f}
            className="text-xs bg-bg-700 border border-bg-600 text-slate-400 px-3 py-1.5 rounded-full"
          >
            {f}
          </span>
        ))}
      </div>

      {/* Conversation starters */}
      <div className="w-full max-w-md">
        <p className="text-xs text-muted uppercase tracking-wider text-center mb-3">
          Try a conversation starter
        </p>
        <div className="grid grid-cols-1 gap-2">
          {STARTERS.map((s) => (
            <button
              key={s}
              onClick={() => onSelectStarter(s)}
              className="
                text-left text-sm bg-bg-700 hover:bg-bg-600
                border border-bg-600 hover:border-accent/30
                text-slate-300 hover:text-slate-100
                px-4 py-2.5 rounded-xl transition-all duration-200
                group flex items-center gap-2
              "
            >
              <span className="text-muted group-hover:text-accent transition-colors">→</span>
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
