// src/hooks/useSpeech.js
//
// ROOT CAUSE OF BLACK SCREEN:
//   Any audio processing in the renderer thread blocks Electron's GPU compositor.
//   ScriptProcessorNode, decodeAudioData, even large IPC transfers — all cause it.
//
// SOLUTION:
//   MediaRecorder collects audio chunks (runs in browser internals, non-blocking).
//   On stop, we convert blob → Uint8Array and send raw bytes to main process.
//   Main process writes the file and runs whisper-cli. Renderer does ZERO processing.

import { useState, useRef, useCallback, useEffect } from 'react';

export function useSpeech({ onResult, onError } = {}) {
  const [isRecording,  setIsRecording]  = useState(false);
  const [isSpeaking,   setIsSpeaking]   = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript,   setTranscript]   = useState('');

  const recorderRef = useRef(null);
  const chunksRef   = useRef([]);
  const streamRef   = useRef(null);
  const synthRef    = useRef(window.speechSynthesis);
  const startTimeRef = useRef(null);

  // Pre-warm TTS voices (async in Electron)
  useEffect(() => {
    const s = window.speechSynthesis;
    if (!s) return;
    if (s.getVoices().length === 0) {
      s.addEventListener('voiceschanged', () => {}, { once: true });
    }
  }, []);

  // ── Start recording ──────────────────────────────────────────────────────
  const startListening = useCallback(async () => {
    if (isRecording || isProcessing) return;
    synthRef.current?.cancel();
    chunksRef.current = [];
    setTranscript('');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount:     1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl:  true,
        },
      });
      streamRef.current = stream;

      // Pick a mime type — whisper-cli supports: flac, mp3, ogg, wav
      // Prefer ogg/opus as it's well-supported and efficient
      const mime =
        MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')  ? 'audio/ogg;codecs=opus' :
        MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' :
        MediaRecorder.isTypeSupported('audio/webm')             ? 'audio/webm' :
        MediaRecorder.isTypeSupported('audio/wav')              ? 'audio/wav' :
        '';

      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : {});
      recorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunksRef.current.push(e.data);
      };

      // onstop fires after recorder.stop() — this is where we send to main
      recorder.onstop = async () => {
        // Stop mic tracks immediately so LED turns off
        streamRef.current?.getTracks().forEach(t => t.stop());
        streamRef.current = null;
        setIsRecording(false);

        const chunks = chunksRef.current;
        chunksRef.current = [];

        if (chunks.length === 0) {
          onError?.('No audio captured. Try again.');
          return;
        }

        // Merge chunks into one blob
        const blob     = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
        const mimeType = blob.type;
        const durationSec = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : 0;

        // Log audio info for debugging
        console.log('[Audio] Duration:', durationSec.toFixed(1) + 's', 'Chunks:', chunks.length, 'Blob size:', blob.size, 'bytes', 'Mime:', mimeType);

        if (blob.size < 44) {
          onError?.('Recording too short — hold the mic button and speak, then tap stop.');
          return;
        }

        // Warn if recording is very short (less than 1 second)
        if (durationSec < 1.0) {
          console.warn('[Speech] Very short recording:', durationSec.toFixed(1) + 's');
        }

        setIsProcessing(true);
        setTranscript('Transcribing…');

        try {
          // Convert blob → Uint8Array so it can cross the IPC bridge
          // We use a FileReader to avoid blocking — arrayBuffer() on large
          // blobs can stall the renderer, FileReader is truly async.
          const audioBytes = await readBlobAsync(blob);

          const result = await window.electronAPI.transcribeAudio(audioBytes, mimeType);

          if (result.success && result.transcript) {
            setTranscript(result.transcript);
            onResult?.(result.transcript);
          } else if (result.success) {
            setTranscript('');
            // Empty transcript usually means silence or background noise
            console.warn('[Speech] Whisper returned empty - likely silence or noise');
            onError?.('No speech detected. Please speak more clearly and closer to the microphone.');
          } else {
            setTranscript('');
            onError?.(result.error || 'Transcription failed.');
          }
        } catch (err) {
          console.error('[Whisper IPC]', err);
          setTranscript('');
          onError?.(`Transcription error: ${err.message}`);
        } finally {
          setIsProcessing(false);
        }
      };

      recorder.onerror = (e) => {
        console.error('[MediaRecorder]', e.error);
        streamRef.current?.getTracks().forEach(t => t.stop());
        streamRef.current = null;
        setIsRecording(false);
        setIsProcessing(false);
        onError?.(`Recorder error: ${e.error?.message || 'unknown'}`);
      };

      // Collect a chunk every 500ms so onstop has data quickly
      recorder.start(500);
      startTimeRef.current = Date.now();
      setIsRecording(true);

    } catch (err) {
      console.error('[Mic]', err);
      streamRef.current?.getTracks().forEach(t => t.stop());
      streamRef.current = null;
      setIsRecording(false);

      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        onError?.('Microphone access denied.\nWindows: Settings → Privacy → Microphone → allow Desktop apps.');
      } else if (err.name === 'NotFoundError') {
        onError?.('No microphone found. Plug in a mic and try again.');
      } else {
        onError?.(`Microphone error: ${err.message}`);
      }
    }
  }, [isRecording, isProcessing, onResult, onError]);

  // ── Stop recording ───────────────────────────────────────────────────────
  const stopListening = useCallback(() => {
    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop(); // triggers onstop above
    } else {
      streamRef.current?.getTracks().forEach(t => t.stop());
      streamRef.current = null;
      setIsRecording(false);
    }
  }, []);

  // ── TTS — SpeechSynthesis (offline, built into Electron) ────────────────
  const speak = useCallback((text) => {
    if (!synthRef.current || !text) return;
    synthRef.current.cancel();

    const utter   = new SpeechSynthesisUtterance(text);
    utter.lang    = 'en-US';
    utter.rate    = 0.92;
    utter.pitch   = 1.0;
    utter.volume  = 1.0;

    const voices = synthRef.current.getVoices();
    if (voices.length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null;
        speak(text);
      };
      return;
    }

    const preferred =
      voices.find(v => v.lang === 'en-US' && v.name.includes('Samantha')) ||
      voices.find(v => v.lang === 'en-US' && v.name.includes('Natural'))  ||
      voices.find(v => v.lang === 'en-US' && !v.name.includes('('))       ||
      voices.find(v => v.lang.startsWith('en'));

    if (preferred) utter.voice = preferred;

    utter.onstart = () => setIsSpeaking(true);
    utter.onend   = () => setIsSpeaking(false);
    utter.onerror = (e) => {
      if (e.error !== 'interrupted') console.warn('[TTS]', e.error);
      setIsSpeaking(false);
    };

    synthRef.current.speak(utter);
  }, []);

  const stopSpeaking = useCallback(() => {
    synthRef.current?.cancel();
    setIsSpeaking(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop());
      if (recorderRef.current?.state === 'recording') {
        recorderRef.current.stop();
      }
    };
  }, []);

  return {
    isRecording,
    isProcessing,
    isSpeaking,
    transcript,
    startListening,
    stopListening,
    speak,
    stopSpeaking,
    isSupported: !!navigator.mediaDevices?.getUserMedia,
  };
}

// ── Helper: read Blob as Uint8Array via FileReader (truly non-blocking) ──────
function readBlobAsync(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload  = () => resolve(new Uint8Array(reader.result));
    reader.onerror = () => reject(new Error('Failed to read audio blob'));
    reader.readAsArrayBuffer(blob);
  });
}