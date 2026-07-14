// src/components/Sidebar.jsx
import React from 'react';

function ScoreBar({ score, index }) {
  const color = score >= 90 ? '#6ee7b7' : score >= 70 ? '#60a5fa' : score >= 50 ? '#f5c842' : '#f87171';
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-muted w-4 text-right">{index + 1}</span>
      <div className="flex-1 bg-bg-700 rounded-full h-2 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700"
             style={{ width: `${score}%`, background: color }} />
      </div>
      <span className="text-[10px] w-6 text-right" style={{ color }}>{score}</span>
    </div>
  );
}

export function Sidebar({ open, onClose, onClear, sessionStats, sessionScores, health, whisperHealth }) {
  const whisperOk = whisperHealth?.exeExists && whisperHealth?.modelExists;

  return (
    <>
      {open && (
        <div className="fixed inset-0 bg-black/40 z-10 backdrop-blur-sm" onClick={onClose} />
      )}
      <div className={`
        fixed left-0 top-0 h-full w-72 z-20 bg-bg-800 border-r border-bg-700
        flex flex-col transition-transform duration-300 ease-in-out
        ${open ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-bg-700">
          <div>
            <p className="font-semibold text-sm gradient-text">SpeakWise</p>
            <p className="text-[10px] text-muted">English Practice Coach</p>
          </div>
          <button onClick={onClose}
            className="w-7 h-7 rounded-lg bg-bg-700 hover:bg-bg-600 flex items-center justify-center text-muted hover:text-white transition-colors">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* System */}
          <section>
            <p className="text-[10px] uppercase tracking-widest text-muted mb-2">System</p>
            <div className="bg-bg-700 rounded-xl p-3 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted">Ollama</span>
                <span className={health?.online ? 'text-accent' : 'text-danger'}>
                  {health?.online ? '● Online' : '○ Offline'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Model</span>
                <span className={health?.hasLlama3 ? 'text-accent' : 'text-gold'}> 
                  {health?.hasLlama3 ? 'llama3:latest ✓' : 'Not found'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Whisper CLI</span>
                <span className={whisperHealth?.exeExists ? 'text-accent' : 'text-danger'}>
                  {whisperHealth?.exeExists ? '✓ Found' : '✗ Missing'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Whisper Model</span>
                <span className={whisperHealth?.modelExists ? 'text-accent' : 'text-danger'}>
                  {whisperHealth?.modelExists ? '✓ Found' : '✗ Missing'}
                </span>
              </div>
              {(!whisperOk) && (
                <div className="pt-1 border-t border-bg-600 text-[10px] text-gold/80 leading-relaxed">
                  Place whisper-cli.exe and models/ in the <code>whisper/</code> folder
                </div>
              )}
            </div>
          </section>

          {/* Session stats */}
          <section>
            <p className="text-[10px] uppercase tracking-widest text-muted mb-2">Session</p>
            <div className="grid grid-cols-2 gap-2">
              {[
                { label: 'Turns',     value: sessionStats.messages },
                { label: 'Avg Score', value: sessionScores.length ? sessionStats.avgScore : '—' },
                { label: 'Best',      value: sessionScores.length ? Math.max(...sessionScores) : '—' },
                { label: 'Latest',    value: sessionScores.at(-1) ?? '—' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-bg-700 rounded-xl p-3 text-center">
                  <p className="text-lg font-semibold text-slate-200">{value}</p>
                  <p className="text-[10px] text-muted">{label}</p>
                </div>
              ))}
            </div>
          </section>

          {/* Score history */}
          {sessionScores.length > 0 && (
            <section>
              <p className="text-[10px] uppercase tracking-widest text-muted mb-2">Score History</p>
              <div className="bg-bg-700 rounded-xl p-3 space-y-2">
                {sessionScores.slice(-10).map((score, i) => (
                  <ScoreBar key={i} score={score} index={i} />
                ))}
              </div>
            </section>
          )}

          {/* Tips */}
          <section>
            <p className="text-[10px] uppercase tracking-widest text-muted mb-2">Tips</p>
            <div className="bg-bg-700 rounded-xl p-3 space-y-2 text-xs text-muted">
              {[
                '🎤 Tap mic → speak → tap again to transcribe',
                '⏳ Whisper runs locally — no internet needed',
                '📝 Read corrected sentences aloud',
                '🔊 Listen to the improved phrasing',
                '💬 Answer every follow-up question',
              ].map(tip => <p key={tip}>{tip}</p>)}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-bg-700 space-y-2">
          <button
            onClick={() => { onClear(); onClose(); }}
            className="w-full py-2 rounded-xl text-sm text-danger/80 hover:text-danger bg-danger/5 hover:bg-danger/10 border border-danger/20 transition-colors"
          >
            🗑 Clear Conversation
          </button>
          <p className="text-[10px] text-center text-muted/50">
            SpeakWise v1.0 · Whisper (local) · Ollama
          </p>
        </div>
      </div>
    </>
  );
}
