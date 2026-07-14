// src/components/ChatMessage.jsx
import React from 'react';
import { FeedbackCard } from './FeedbackCard';

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-3">
      <div className="typing-dot w-2 h-2 rounded-full bg-muted" />
      <div className="typing-dot w-2 h-2 rounded-full bg-muted" />
      <div className="typing-dot w-2 h-2 rounded-full bg-muted" />
    </div>
  );
}

export function ChatMessage({ message, onSpeak }) {
  const { role, content, feedback, isLoading } = message;
  const isUser = role === 'user';

  return (
    <div className={`flex gap-3 msg-in ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* Avatar */}
      <div
        className={`
          shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm
          ${isUser
            ? 'bg-accent/20 text-accent'
            : 'bg-bg-600 text-slate-300'}
        `}
      >
        {isUser ? '👤' : '🎓'}
      </div>

      {/* Content area */}
      <div className={`flex flex-col gap-2 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
        {/* Main bubble */}
        <div
          className={`
            rounded-2xl px-4 py-3 text-sm leading-relaxed
            ${isUser
              ? 'bg-accent/15 border border-accent/25 text-slate-100 rounded-tr-sm'
              : 'bg-bg-700 border border-bg-600 text-slate-200 rounded-tl-sm'}
          `}
        >
          {isLoading ? (
            <TypingIndicator />
          ) : (
            <div>
              <p className="whitespace-pre-wrap">{content}</p>
              {/* AI: speak button + follow-up */}
              {!isUser && (
                <div className="mt-2 flex items-center gap-3">
                  <button
                    onClick={() => onSpeak?.(content)}
                    className="text-xs text-muted hover:text-accent transition-colors flex items-center gap-1"
                    title="Listen to response"
                  >
                    🔊 <span>Listen</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Feedback card (AI messages with correction data) */}
        {!isUser && feedback && !isLoading && (
          <div className="w-full">
            <FeedbackCard
              data={feedback}
              originalText={feedback._original}
              onSpeak={onSpeak}
            />
          </div>
        )}
      </div>
    </div>
  );
}
