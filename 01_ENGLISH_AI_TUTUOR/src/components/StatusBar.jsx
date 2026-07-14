// src/components/StatusBar.jsx
import React from 'react';

export function StatusBar({ health, whisperHealth, sessionStats, isSpeaking, onStopSpeaking }) {
  const whisperOk = whisperHealth?.exeExists && whisperHealth?.modelExists;

  return (
    <div className="flex items-center justify-between px-5 py-2 border-b border-bg-700 bg-bg-800/80 backdrop-blur text-xs text-muted">
      <div className="flex items-center gap-4">
        {/* Ollama status */}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${health?.online ? 'bg-accent animate-pulse' : 'bg-danger'}`} />
          <span>
            {health?.online
              ? health.hasLlama3 ? 'Ollama · llama3:latest' : 'Ollama · no model'
              : 'Ollama offline'}
          </span>
        </div>

        {/* Whisper status */}
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${whisperOk ? 'bg-accent' : 'bg-danger'}`} />
          <span>
            {whisperOk ? 'Whisper ready' : 'Whisper missing'}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {isSpeaking && (
          <button
            onClick={onStopSpeaking}
            className="flex items-center gap-1 text-accent hover:text-accent-dim transition-colors"
          >
            ⏹ Stop speaking
          </button>
        )}
        <span>💬 {sessionStats.messages} turns</span>
        {sessionStats.avgScore > 0 && (
          <span>⭐ Avg {sessionStats.avgScore}</span>
        )}
      </div>
    </div>
  );
}
