// src/hooks/useOllama.js
// Calls Electron IPC → Ollama streaming API.
// Tokens arrive one-by-one via onToken so the UI updates live.

import { useState, useCallback } from 'react';

export function useOllama() {
  const [isLoading, setIsLoading] = useState(false);
  const [error,     setError]     = useState(null);

  /**
   * generate(userMessage, history, { onToken })
   *
   * @param {string}   userMessage  - what the user said
   * @param {Array}    history      - prior conversation turns for context
   * @param {Function} onToken      - called with each streaming token string
   * @returns {Promise<object>}     - final parsed feedback data object
   */
  const generate = useCallback(async (userMessage, history = [], { onToken } = {}) => {
    setIsLoading(true);
    setError(null);

    return new Promise((resolve, reject) => {
      // 1. Register streaming listeners BEFORE invoking
      window.electronAPI.onToken((token) => {
        onToken?.(token);
      });

      window.electronAPI.onDone((data) => {
        window.electronAPI.removeStreamListeners();
        setIsLoading(false);
        resolve(data);
      });

      window.electronAPI.onError((msg) => {
        window.electronAPI.removeStreamListeners();
        setIsLoading(false);
        setError(msg);
        reject(new Error(msg));
      });

      // 2. Kick off the generation (non-blocking — response arrives via events)
      window.electronAPI
        .generateResponse(userMessage, history)
        .catch((err) => {
          // IPC-level failure (e.g. main process crashed)
          window.electronAPI.removeStreamListeners();
          setIsLoading(false);
          const msg = err.message || 'IPC error';
          setError(msg);
          reject(new Error(msg));
        });
    });
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      return await window.electronAPI.checkHealth();
    } catch {
      return { online: false, models: [], hasLlama3: false };
    }
  }, []);

  return { generate, checkHealth, isLoading, error };
}
