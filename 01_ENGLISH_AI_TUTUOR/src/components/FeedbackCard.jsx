// src/components/FeedbackCard.jsx
import React, { useState } from 'react';
import { ScoreRing } from './ScoreRing';

/**
 * Highlights differences between original and corrected text.
 * Simple word-by-word diff for visual clarity.
 */
function DiffText({ original = '', corrected = '' }) {
  if (!original || original === corrected) {
    return <span className="text-accent">{corrected}</span>;
  }

  const origWords = original.toLowerCase().split(/\s+/);
  const corrWords = corrected.split(/\s+/);

  return (
    <span>
      {corrWords.map((word, i) => {
        const isChanged = origWords[i]?.replace(/[^a-z]/g, '') !== word.toLowerCase().replace(/[^a-z]/g, '');
        return (
          <span key={i}>
            {i > 0 && ' '}
            {isChanged ? (
              <mark className="bg-accent/20 text-accent rounded px-0.5 font-medium">
                {word}
              </mark>
            ) : (
              <span className="text-slate-300">{word}</span>
            )}
          </span>
        );
      })}
    </span>
  );
}

export function FeedbackCard({ data, originalText, onSpeak }) {
  const [expanded, setExpanded] = useState(true);
  const { corrected, mistakes = [], improved, score = 0, scoreFeedback } = data;

  return (
    <div className="bg-bg-700 border border-bg-600 rounded-2xl overflow-hidden msg-in">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-bg-600/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-muted">
            📝 Feedback
          </span>
          {mistakes.length > 0 && (
            <span className="text-xs bg-danger/20 text-danger px-2 py-0.5 rounded-full">
              {mistakes.length} correction{mistakes.length !== 1 ? 's' : ''}
            </span>
          )}
          {mistakes.length === 0 && (
            <span className="text-xs bg-accent/20 text-accent px-2 py-0.5 rounded-full">
              ✓ Perfect!
            </span>
          )}
        </div>
        <span className="text-muted text-xs">{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-4">
          {/* Score + Corrected side by side */}
          <div className="flex gap-4 items-start">
            <ScoreRing score={score} />
            <div className="flex-1 min-w-0">
              {/* Score feedback */}
              {scoreFeedback && (
                <p className="text-xs text-muted mb-2 italic">{scoreFeedback}</p>
              )}
              {/* Corrected sentence */}
              <div className="bg-bg-800 rounded-xl p-3">
                <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-1">
                  Corrected
                </p>
                <p className="text-sm leading-relaxed">
                  <DiffText original={originalText} corrected={corrected} />
                </p>
              </div>
            </div>
          </div>

          {/* Mistakes */}
          {mistakes.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                Mistakes Found
              </p>
              <ul className="space-y-1">
                {mistakes.map((m, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <span className="text-danger mt-0.5 shrink-0">✗</span>
                    <span className="text-slate-300">{m}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Improved version */}
          {improved && improved !== corrected && (
            <div className="bg-accent/5 border border-accent/20 rounded-xl p-3">
              <p className="text-xs font-semibold text-accent/70 uppercase tracking-wider mb-1">
                More Natural Phrasing
              </p>
              <p className="text-sm text-slate-200 leading-relaxed">{improved}</p>
              <button
                onClick={() => onSpeak?.(improved)}
                className="mt-2 text-xs text-accent hover:text-accent-dim transition-colors flex items-center gap-1"
              >
                🔊 Listen to improved version
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
