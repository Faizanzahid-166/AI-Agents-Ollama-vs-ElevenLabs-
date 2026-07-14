// src/components/Waveform.jsx
import React from 'react';

export function Waveform({ color = '#f87171' }) {
  return (
    <div className="flex items-center gap-[3px] h-5">
      {[1, 2, 3, 4, 5].map((i) => (
        <div
          key={i}
          className="wave-bar rounded-full w-[3px]"
          style={{
            height: '100%',
            background: color,
            animationDelay: `${(i - 1) * 0.15}s`,
          }}
        />
      ))}
    </div>
  );
}
