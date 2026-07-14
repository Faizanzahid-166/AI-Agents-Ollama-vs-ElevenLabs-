// src/components/ChatInput.jsx
import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import TextareaAutosize from 'react-textarea-autosize'
import { Send, Mic, MicOff, Square, Code2, MessageSquare, Volume2, VolumeX, PanelLeft } from 'lucide-react'
import { useGraceStore } from '../stores/graceStore'
import { useVoiceRecorder } from '../hooks/useVoiceRecorder'
import VoiceOrb from './VoiceOrb'
import clsx from 'clsx'

export default function ChatInput() {
  const [text, setText] = useState('')
  const textareaRef = useRef(null)

  const {
    isStreaming, isRecording, isTTSSpeaking,
    mode, ttsEnabled, sidebarOpen,
    sendMessage, stopGeneration,
    setMode, toggleTTS, toggleSidebar,
  } = useGraceStore()

  const { toggleRecording } = useVoiceRecorder()

  const handleSend = useCallback(() => {
    if (!text.trim() || isStreaming) return
    sendMessage(text.trim())
    setText('')
    textareaRef.current?.focus()
  }, [text, isStreaming, sendMessage])

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="px-4 pb-4 pt-2 border-t border-border-subtle bg-bg-base/80 backdrop-blur-sm">
      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-2 px-1">
        {/* Sidebar toggle */}
        {!sidebarOpen && (
          <button onClick={toggleSidebar} className="no-drag p-1.5 rounded-lg hover:bg-bg-overlay text-text-muted hover:text-text-secondary transition-colors">
            <PanelLeft size={15} />
          </button>
        )}

        {/* Mode switcher */}
        <div className="flex items-center bg-bg-overlay rounded-lg p-0.5 border border-border-subtle">
          {['chat', 'code'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={clsx(
                'no-drag flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all',
                mode === m
                  ? 'bg-bg-elevated text-text-primary shadow-card'
                  : 'text-text-muted hover:text-text-secondary'
              )}
            >
              {m === 'code' ? <Code2 size={11} /> : <MessageSquare size={11} />}
              {m === 'code' ? 'Code' : 'Chat'}
            </button>
          ))}
        </div>

        {/* TTS toggle */}
        <button
          onClick={toggleTTS}
          className={clsx(
            'no-drag flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all',
            ttsEnabled
              ? 'bg-accent-cyan/10 border-accent-cyan/30 text-accent-cyan'
              : 'bg-bg-overlay border-border-subtle text-text-muted hover:text-text-secondary'
          )}
        >
          {ttsEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
          Voice
        </button>

        <div className="flex-1" />

        {/* Model indicator */}
        <span className="text-[10px] text-text-muted font-mono">
          {mode === 'code' ? 'qwen3.5' : 'llama3'}
        </span>
      </div>

      {/* Input area */}
      <div className={clsx(
        'flex items-end gap-2 bg-bg-elevated rounded-2xl border transition-all',
        isRecording ? 'border-red-500/50' : 'border-border-default focus-within:border-accent-violet/50'
      )}>
        {/* Voice orb (when recording/speaking) */}
        <AnimatePresence>
          {(isRecording || isTTSSpeaking) && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 'auto', opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="pl-2 py-2"
            >
              <VoiceOrb isRecording={isRecording} isSpeaking={isTTSSpeaking} isStreaming={isStreaming} />
            </motion.div>
          )}
        </AnimatePresence>

        <TextareaAutosize
          ref={textareaRef}
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
          placeholder={isRecording ? 'Listening...' : mode === 'code' ? 'Ask Grace to write or debug code...' : 'Message Grace...'}
          disabled={isRecording}
          maxRows={8}
          minRows={1}
          className="no-drag flex-1 bg-transparent px-4 py-3 text-sm text-text-primary placeholder:text-text-muted resize-none outline-none leading-relaxed selectable"
        />

        <div className="flex items-center gap-1.5 pr-2 pb-2">
          {/* Mic button */}
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={toggleRecording}
            className={clsx(
              'no-drag p-2 rounded-xl transition-all',
              isRecording
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'hover:bg-bg-overlay text-text-muted hover:text-text-secondary'
            )}
          >
            {isRecording ? <MicOff size={16} /> : <Mic size={16} />}
          </motion.button>

          {/* Stop / Send */}
          {isStreaming ? (
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={stopGeneration}
              className="no-drag p-2 rounded-xl bg-accent-violet/20 hover:bg-accent-violet/30 text-accent-glow transition-all"
            >
              <Square size={16} />
            </motion.button>
          ) : (
            <motion.button
              whileTap={{ scale: 0.9 }}
              onClick={handleSend}
              disabled={!text.trim()}
              className={clsx(
                'no-drag p-2 rounded-xl transition-all',
                text.trim()
                  ? 'bg-accent-violet text-white hover:bg-accent-purple shadow-glow-violet'
                  : 'bg-bg-overlay text-text-muted cursor-not-allowed'
              )}
            >
              <Send size={16} />
            </motion.button>
          )}
        </div>
      </div>
    </div>
  )
}
