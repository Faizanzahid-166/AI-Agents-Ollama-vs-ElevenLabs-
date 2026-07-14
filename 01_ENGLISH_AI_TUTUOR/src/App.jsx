// src/App.jsx
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { ChatMessage }   from './components/ChatMessage';
import { InputBar }      from './components/InputBar';
import { StatusBar }     from './components/StatusBar';
import { WelcomeScreen } from './components/WelcomeScreen';
import { Sidebar }       from './components/Sidebar';
import { ErrorBanner }   from './components/ErrorBanner';
import { useSpeech }     from './hooks/useSpeech';
import { useOllama }     from './hooks/useOllama';

const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2);

export default function App() {
  const [messages,      setMessages]      = useState([]);
  const [history,       setHistory]       = useState([]);
  const [health,        setHealth]        = useState(null);
  const [whisperHealth, setWhisperHealth] = useState(null);
  const [error,         setError]         = useState(null);
  const [sidebarOpen,   setSidebarOpen]   = useState(false);
  const [sessionScores, setSessionScores] = useState([]);

  const bottomRef    = useRef(null);
  const streamBufRef = useRef(''); // accumulates raw streamed tokens

  const { generate, isLoading } = useOllama();

  // ── Speech ────────────────────────────────────────────────────────────────
  const {
    isRecording, isProcessing, isSpeaking,
    transcript,
    startListening, stopListening,
    speak, stopSpeaking,
    isSupported,
  } = useSpeech({
    onResult: (text) => { if (text.trim()) handleSend(text.trim()); },
    onError:  (msg)  => setError(msg),
  });

  // ── Health checks ─────────────────────────────────────────────────────────
  useEffect(() => {
    const checkAll = async () => {
      const [ollamaResult, whisperResult] = await Promise.all([
        window.electronAPI.checkHealth(),
        window.electronAPI.whisperHealth(),
      ]);
      setHealth(ollamaResult);
      setWhisperHealth(whisperResult);

      if (!ollamaResult.online) {
        setError('Ollama not running. Start with: ollama serve');
      } else if (!ollamaResult.hasLlama3) {
        setError('llama3:latest not found. Run: ollama pull llama3:latest');
      } else if (!whisperResult.exeExists || !whisperResult.modelExists) {
        setError(
          'Whisper files missing — voice input disabled.\n' +
          (!whisperResult.exeExists   ? `• whisper-cli.exe → ${whisperResult.exePath}\n`  : '') +
          (!whisperResult.modelExists ? `• model file     → ${whisperResult.modelPath}` : '')
        );
      } else {
        setError(null);
      }
    };
    checkAll();
    const t = setInterval(checkAll, 30000);
    return () => clearInterval(t);
  }, []);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ── Session stats ─────────────────────────────────────────────────────────
  const sessionStats = {
    messages: messages.filter(m => m.role === 'user').length,
    avgScore: sessionScores.length
      ? Math.round(sessionScores.reduce((a, b) => a + b, 0) / sessionScores.length)
      : 0,
  };

  // ── Send + stream ─────────────────────────────────────────────────────────
  const handleSend = useCallback(async (text) => {
    if (!text.trim() || isLoading) return;
    stopSpeaking();

    const userMsgId = uid();
    const aiMsgId   = uid();
    streamBufRef.current = '';

    // Add user bubble + empty AI bubble (streaming placeholder)
    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user',      content: text },
      { id: aiMsgId,   role: 'assistant', content: '', isLoading: true, isStreaming: true },
    ]);

    const updatedHistory = [...history, { role: 'user', content: text }];

    try {
      // generate() calls onToken for each streamed token
      const aiData = await generate(text, history, {
        onToken: (token) => {
          streamBufRef.current += token;
          // Update the AI bubble live with raw streamed text
          setMessages(prev => prev.map(m =>
            m.id === aiMsgId
              ? { ...m, content: streamBufRef.current, isLoading: false }
              : m
          ));
        },
      });

      // Stream finished — replace with final parsed data
      const responseText = [aiData.response, aiData.followUp]
        .filter(Boolean).join('\n\n');

      setMessages(prev => prev.map(m =>
        m.id === aiMsgId
          ? {
              id: aiMsgId, role: 'assistant',
              content: responseText,
              isLoading: false, isStreaming: false,
              feedback: { ...aiData, _original: text },
            }
          : m
      ));

      setHistory([...updatedHistory, { role: 'assistant', content: responseText }]);
      if (typeof aiData.score === 'number') {
        setSessionScores(prev => [...prev, aiData.score]);
      }

      speak(responseText);
      setError(null);

    } catch (err) {
      setMessages(prev => prev.map(m =>
        m.id === aiMsgId
          ? {
              id: aiMsgId, role: 'assistant',
              content: '⚠️ ' + (err.message || 'Failed to get a response.'),
              isLoading: false, isStreaming: false,
            }
          : m
      ));
      setError(err.message);
    }
  }, [isLoading, history, generate, speak, stopSpeaking]);

  const handleClear = () => {
    setMessages([]); setHistory([]); setSessionScores([]);
    stopSpeaking();
  };

  const isInputDisabled = !health?.online || !health?.hasLlama3;

  return (
    <div className="flex h-screen bg-bg-900 overflow-hidden select-none">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onClear={handleClear}
        sessionStats={sessionStats}
        sessionScores={sessionScores}
        health={health}
        whisperHealth={whisperHealth}
      />

      <div className="flex flex-col flex-1 min-w-0">
        {/* Title bar — drag region for frameless window */}
        <div className="drag-region flex items-center gap-3 px-5 py-3 bg-bg-800 border-b border-bg-700">
          <button
            onClick={() => setSidebarOpen(s => !s)}
            className="no-drag w-7 h-7 rounded-lg bg-bg-700 hover:bg-bg-600 flex items-center justify-center text-muted hover:text-slate-200 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16"/>
            </svg>
          </button>
          <span className="text-sm font-semibold gradient-text flex-1">SpeakWise</span>
          <span className="text-muted text-xs no-drag">AI English Coach</span>
          {isSpeaking && (
            <div className="no-drag flex items-center gap-1.5 text-xs text-accent animate-pulse">
              <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
              </svg>
              Speaking
            </div>
          )}
        </div>

        <StatusBar
          health={health}
          whisperHealth={whisperHealth}
          sessionStats={sessionStats}
          isSpeaking={isSpeaking}
          onStopSpeaking={stopSpeaking}
        />

        {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          {messages.length === 0
            ? <WelcomeScreen onSelectStarter={handleSend} />
            : messages.map(msg => (
                <ChatMessage key={msg.id} message={msg} onSpeak={speak} />
              ))
          }
          <div ref={bottomRef} />
        </div>

        <InputBar
          onSend={handleSend}
          isLoading={isLoading}
          isRecording={isRecording}
          isProcessing={isProcessing}
          isSpeaking={isSpeaking}
          transcript={transcript}
          onStartRecording={startListening}
          onStopRecording={stopListening}
          disabled={isInputDisabled}
        />

        {!isSupported && (
          <p className="text-center text-xs text-danger/70 py-1 bg-bg-800">
            ⚠️ Microphone API not available — text input only
          </p>
        )}
      </div>
    </div>
  );
}
