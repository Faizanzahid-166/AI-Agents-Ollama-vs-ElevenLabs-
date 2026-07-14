// src/stores/graceStore.js – Global state with Zustand
import { create } from 'zustand'

const API = 'http://localhost:8000/api'
const WS_URL = 'ws://localhost:8000/ws/chat'

let wsInstance = null
let reconnectTimer = null

export const useGraceStore = create((set, get) => ({
  // ── Connection ────────────────────────────────────────────────────────────
  wsStatus: 'disconnected',   // connected | connecting | disconnected | error
  userId: 'user_default',

  // ── Conversations ─────────────────────────────────────────────────────────
  conversations: [],
  activeConvId: null,

  // ── Messages ──────────────────────────────────────────────────────────────
  messages: [],               // { id, role, content, timestamp }
  streamingContent: '',       // accumulates live tokens
  isStreaming: false,
  isTTSSpeaking: false,

  // ── UI ────────────────────────────────────────────────────────────────────
  mode: 'chat',               // chat | code
  ttsEnabled: false,
  isRecording: false,
  sidebarOpen: true,

  // ── WebSocket ─────────────────────────────────────────────────────────────
  connect() {
    if (wsInstance?.readyState === WebSocket.OPEN) return
    set({ wsStatus: 'connecting' })

    wsInstance = new WebSocket(WS_URL)

    wsInstance.onopen = () => {
      set({ wsStatus: 'connected' })
      if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null }
      // Heartbeat
      const ping = setInterval(() => {
        if (wsInstance?.readyState === WebSocket.OPEN) {
          wsInstance.send(JSON.stringify({ type: 'ping' }))
        } else {
          clearInterval(ping)
        }
      }, 15000)
    }

    wsInstance.onmessage = (e) => {
      const data = JSON.parse(e.data)
      get()._handleMessage(data)
    }

    wsInstance.onclose = () => {
      set({ wsStatus: 'disconnected', isStreaming: false })
      // Auto-reconnect
      if (!reconnectTimer) {
        reconnectTimer = setInterval(() => {
          if (wsInstance?.readyState !== WebSocket.OPEN) get().connect()
        }, 3000)
      }
    }

    wsInstance.onerror = () => set({ wsStatus: 'error' })
  },

  disconnect() {
    if (reconnectTimer) { clearInterval(reconnectTimer); reconnectTimer = null }
    wsInstance?.close()
    wsInstance = null
    set({ wsStatus: 'disconnected' })
  },

  _handleMessage(data) {
    switch (data.type) {
      case 'token':
        set(s => ({ streamingContent: s.streamingContent + data.content }))
        break

      case 'tts_chunk':
        set(s => ({ streamingContent: s.streamingContent + data.sentence + ' ' }))
        if (data.audio_b64) get()._playPCM(data.audio_b64)
        break

      case 'done':
        set(s => ({
          messages: [...s.messages, {
            id: Date.now(),
            role: 'assistant',
            content: data.full_response,
            timestamp: new Date().toISOString(),
          }],
          streamingContent: '',
          isStreaming: false,
        }))
        if (data.conv_id && !get().activeConvId) {
          set({ activeConvId: data.conv_id })
        }
        break

      case 'title_update':
        set(s => ({
          conversations: s.conversations.map(c =>
            c.id === data.conv_id ? { ...c, title: data.title } : c
          )
        }))
        break

      case 'error':
        set({ isStreaming: false, streamingContent: '' })
        get()._addSystemMessage(`Error: ${data.message}`)
        break

      case 'pong':
        break
    }
  },

  _addSystemMessage(content) {
    set(s => ({
      messages: [...s.messages, {
        id: Date.now(),
        role: 'system',
        content,
        timestamp: new Date().toISOString(),
      }]
    }))
  },

  // ── PCM audio playback ────────────────────────────────────────────────────
  _playPCM(b64) {
    try {
      const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
      const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 22050 })
      const pcm = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(pcm.length)
      for (let i = 0; i < pcm.length; i++) float32[i] = pcm[i] / 32768
      const buffer = ctx.createBuffer(1, float32.length, 22050)
      buffer.getChannelData(0).set(float32)
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)
      source.start()
      set({ isTTSSpeaking: true })
      source.onended = () => set({ isTTSSpeaking: false })
    } catch (e) {
      console.warn('PCM playback failed:', e)
    }
  },

  // ── Send message ──────────────────────────────────────────────────────────
  sendMessage(text) {
    if (!text.trim() || get().isStreaming) return
    if (wsInstance?.readyState !== WebSocket.OPEN) {
      get().connect()
      return
    }

    const userMsg = { id: Date.now(), role: 'user', content: text, timestamp: new Date().toISOString() }
    set(s => ({
      messages: [...s.messages, userMsg],
      streamingContent: '',
      isStreaming: true,
    }))

    wsInstance.send(JSON.stringify({
      type: 'chat',
      user_id: get().userId,
      conv_id: get().activeConvId,
      message: text,
      mode: get().mode,
      tts: get().ttsEnabled,
    }))
  },

  stopGeneration() {
    if (wsInstance?.readyState === WebSocket.OPEN) {
      wsInstance.send(JSON.stringify({ type: 'stop' }))
    }
    // Commit whatever streamed so far
    const current = get().streamingContent
    if (current.trim()) {
      set(s => ({
        messages: [...s.messages, {
          id: Date.now(), role: 'assistant',
          content: current + ' *(stopped)*',
          timestamp: new Date().toISOString(),
        }],
        streamingContent: '',
        isStreaming: false,
      }))
    } else {
      set({ isStreaming: false, streamingContent: '' })
    }
  },

  // ── Conversations ─────────────────────────────────────────────────────────
  async loadConversations() {
    try {
      const r = await fetch(`${API}/conversations/${get().userId}`)
      const data = await r.json()
      set({ conversations: data.conversations })
    } catch (e) {
      console.error('loadConversations:', e)
    }
  },

  async selectConversation(convId) {
    try {
      const r = await fetch(`${API}/messages/${convId}`)
      const data = await r.json()
      set({ activeConvId: convId, messages: data.messages, streamingContent: '', isStreaming: false })
    } catch (e) {
      console.error('selectConversation:', e)
    }
  },

  async newConversation() {
    set({ activeConvId: null, messages: [], streamingContent: '', isStreaming: false })
  },

  async deleteConversation(convId) {
    await fetch(`${API}/conversations/${convId}`, { method: 'DELETE' })
    set(s => ({
      conversations: s.conversations.filter(c => c.id !== convId),
      ...(s.activeConvId === convId ? { activeConvId: null, messages: [] } : {}),
    }))
  },

  // ── UI helpers ────────────────────────────────────────────────────────────
  setMode: (mode) => set({ mode }),
  toggleTTS: () => set(s => ({ ttsEnabled: !s.ttsEnabled })),
  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),
  setRecording: (v) => set({ isRecording: v }),
}))
