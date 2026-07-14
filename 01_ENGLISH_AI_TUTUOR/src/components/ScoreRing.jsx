// src/components/ScoreRing.jsx
import React, { useEffect, useRef } from 'react';

const RADIUS = 36;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ~226

function getColor(score) {
  if (score >= 90) return '#6ee7b7'; // green
  if (score >= 70) return '#60a5fa'; // blue
  if (score >= 50) return '#f5c842'; // gold
  return '#f87171';                   // red
}

function getLabel(score) {
  if (score >= 90) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 50) return 'Fair';
  return 'Keep Going';
}

export function ScoreRing({ score = 0 }) {
  const ringRef = useRef(null);
  const offset  = CIRCUMFERENCE - (score / 100) * CIRCUMFERENCE;
  const color   = getColor(score);

  useEffect(() => {
    if (ringRef.current) {
      ringRef.current.style.setProperty('--target-offset', offset);
      ringRef.current.style.strokeDashoffset = offset;
    }
  }, [offset]);

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 88 88">
          {/* Track */}
          <circle
            cx="44" cy="44" r={RADIUS}
            fill="none"
            stroke="#1e2535"
            strokeWidth="8"
          />
          {/* Fill */}
          <circle
            ref={ringRef}
            cx="44" cy="44" r={RADIUS}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE}
            className="score-ring-fill transition-all duration-1000"
            style={{ '--target-offset': offset }}
          />
        </svg>
        {/* Score number in center */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-semibold" style={{ color }}>
            {score}
          </span>
        </div>
      </div>
      <span className="text-xs font-medium" style={{ color }}>
        {getLabel(score)}
      </span>
    </div>
  );
}
