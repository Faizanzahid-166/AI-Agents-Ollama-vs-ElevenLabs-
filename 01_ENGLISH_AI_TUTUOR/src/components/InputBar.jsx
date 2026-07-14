// src/components/InputBar.jsx
import React, { useState, useRef, useEffect } from 'react';
import { Waveform } from './Waveform';

export function InputBar({
  onSend, isLoading, isRecording, isProcessing,
  isSpeaking, transcript, onStartRecording, onStopRecording, disabled,
}) {
  const [text, setText]   = useState('');
  const textareaRef       = useRef(null);

  // Show transcript in box while recording (so user sees it)
  useEffect(() => {
    if (transcript && transcript !== 'Transcribing…') setText(transcript);
  }, [transcript]);

  // Auto-grow textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 120) + 'px'; }
  }, [text]);

  const handleSend = () => {
    const msg = text.trim();
    if (!msg || isLoading || disabled) return;
    onSend(msg);
    setText('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // Tap mic once → start. Tap again → stop & transcribe.
  const handleMicClick = () => {
    if (isRecording) onStopRecording();   // stop → triggers Whisper in hook
    else             onStartRecording();
  };

  const micBusy = isLoading || isSpeaking || disabled || isProcessing;

  return (
    <div className="p-4 bg-bg-800 border-t border-bg-700">

      {/* Recording banner */}
      {isRecording && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <Waveform color="#f87171" />
          <span className="text-xs text-danger font-medium animate-pulse">Recording…</span>
          <span className="text-xs text-muted">tap ⏹ when done speaking</span>
        </div>
      )}

      {/* Whisper processing banner */}
      {isProcessing && (
        <div className="flex items-center gap-2 mb-3 px-1">
          <svg className="w-3.5 h-3.5 animate-spin text-accent shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
            <path  className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z"/>
          </svg>
          <span className="text-xs text-accent">Transcribing with Whisper…</span>
        </div>
      )}

      <div className="flex items-end gap-3">

        {/* Mic button */}
        <button
          onClick={handleMicClick}
          disabled={micBusy}
          title={isRecording ? 'Stop recording & transcribe' : 'Start recording'}
          className={[
            'btn-mic shrink-0 w-11 h-11 rounded-full flex items-center justify-center',
            'transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-800',
            isRecording
              ? 'bg-danger recording text-white focus:ring-danger'
              : 'bg-bg-600 hover:bg-bg-500 text-slate-300 hover:text-white focus:ring-accent',
            micBusy ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer',
          ].join(' ')}
        >
          {isRecording
            /* Stop square */
            ? <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <rect x="5" y="5" width="14" height="14" rx="2"/>
              </svg>
            /* Mic icon */
            : <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm6.5 9.5A6.5 6.5 0 0 1 5.5 10.5H4a8 8 0 0 0 7 7.938V21h-2v2h6v-2h-2v-2.062A8 8 0 0 0 20 10.5h-1.5z"/>
              </svg>
          }
        </button>

        {/* Text input */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder={
            disabled      ? 'Waiting for Ollama…'            :
            isProcessing  ? 'Transcribing your speech…'      :
            isRecording   ? 'Speaking… tap ⏹ when finished'  :
                            'Type or tap 🎤 to speak…'
          }
          disabled={isLoading || disabled || isProcessing}
          rows={1}
          className="
            flex-1 resize-none bg-bg-700 border border-bg-600
            rounded-2xl px-4 py-3 text-sm text-slate-200 placeholder-muted
            focus:outline-none focus:border-accent/50 transition-colors
            leading-relaxed disabled:opacity-50 disabled:cursor-not-allowed
          "
        />

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!text.trim() || isLoading || disabled}
          className="
            shrink-0 w-11 h-11 rounded-full flex items-center justify-center
            bg-accent text-bg-900 font-bold hover:bg-accent-dim
            transition-all duration-200 focus:outline-none
            disabled:opacity-30 disabled:cursor-not-allowed
          "
          title="Send (Enter)"
        >
          {isLoading
            ? <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path  className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.4 0 0 5.4 0 12h4z"/>
              </svg>
            : <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
          }
        </button>
      </div>

      <p className="text-center text-[10px] text-muted/40 mt-2">
        Enter to send · Shift+Enter new line · 🎤 tap to record, tap ⏹ to finish
      </p>
    </div>
  );
}
