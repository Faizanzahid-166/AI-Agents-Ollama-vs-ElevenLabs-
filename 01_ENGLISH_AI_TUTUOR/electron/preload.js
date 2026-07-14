// electron/preload.js — CommonJS (Electron requirement)
'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {

  // ── Ollama AI ────────────────────────────────────────────────────────────
  generateResponse: (userMessage, history = []) =>
    ipcRenderer.invoke('ollama:generate', { userMessage, history }),

  // Streaming listeners
  onToken:               (cb) => ipcRenderer.on('ollama:token', (_e, token) => cb(token)),
  onDone:                (cb) => ipcRenderer.once('ollama:done',  (_e, data)  => cb(data)),
  onError:               (cb) => ipcRenderer.once('ollama:error', (_e, msg)   => cb(msg)),
  removeStreamListeners: ()   => {
    ipcRenderer.removeAllListeners('ollama:token');
    ipcRenderer.removeAllListeners('ollama:done');
    ipcRenderer.removeAllListeners('ollama:error');
  },

  checkHealth: () => ipcRenderer.invoke('ollama:health'),

  // ── Whisper STT ──────────────────────────────────────────────────────────
  // audioBytes : Uint8Array  — raw audio file bytes (webm/ogg/wav)
  // mimeType   : string      — e.g. 'audio/webm;codecs=opus'
  transcribeAudio: (audioBytes, mimeType) =>
    ipcRenderer.invoke('whisper:transcribeAudio', { audioBytes, mimeType }),

  whisperHealth: () => ipcRenderer.invoke('whisper:health'),

  // ── Platform ─────────────────────────────────────────────────────────────
  platform: process.platform,
});