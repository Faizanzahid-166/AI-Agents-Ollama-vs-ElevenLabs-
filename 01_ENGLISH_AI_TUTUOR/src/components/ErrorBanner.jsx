// src/components/ErrorBanner.jsx
import React from 'react';

export function ErrorBanner({ message, onDismiss }) {
  if (!message) return null;

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-danger/10 border-b border-danger/20 text-sm">
      <div className="flex items-center gap-2 text-danger/90">
        <span className="shrink-0">⚠️</span>
        <span>{message}</span>
      </div>
      <button
        onClick={onDismiss}
        className="shrink-0 text-danger/60 hover:text-danger transition-colors text-xs"
        title="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}
