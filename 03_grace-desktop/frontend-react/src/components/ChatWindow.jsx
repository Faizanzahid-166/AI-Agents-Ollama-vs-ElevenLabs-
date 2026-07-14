// src/components/ChatWindow.jsx – Scrollable message list with live streaming
import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGraceStore } from '../stores/graceStore'
import MessageBubble from './MessageBubble'
import VoiceOrb from './VoiceOrb'

export default function ChatWindow() {
  const { messages, streamingContent, isStreaming, isTTSSpeaking, activeConvId } = useGraceStore()
  const bottomRef = useRef(null)
  const containerRef = useRef(null)

  // Auto-scroll to bottom on new content
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  const isEmpty = messages.length === 0 && !streamingContent

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto py-4 space-y-4 scroll-smooth">
      {/* Empty state */}
      <AnimatePresence>
        {isEmpty && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center justify-center h-full min-h-[400px] text-center px-8"
          >
            <motion.div
              animate={{ y: [0, -8, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            >
              <VoiceOrb isRecording={false} isSpeaking={false} isStreaming={false} />
            </motion.div>
            <h2 className="font-display font-semibold text-2xl text-text-primary mt-6 mb-2">
              Hey, I'm Grace 👋
            </h2>
            <p className="text-text-secondary text-sm max-w-sm">
              Your AI bestie for coding, life advice, deep conversations, or just a good laugh. What's on your mind?
            </p>
            <div className="mt-8 flex flex-wrap gap-2 justify-center">
              {[
                '🐛 Debug my code',
                '💡 Explain async/await',
                '😄 Tell me a joke',
                '🎯 Help me focus',
              ].map(s => (
                <SuggestionChip key={s} text={s} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Message list */}
      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}

      {/* Live streaming message */}
      <AnimatePresence>
        {isStreaming && streamingContent && (
          <MessageBubble
            message={{ role: 'assistant', content: streamingContent, timestamp: null }}
            isStreaming
          />
        )}

        {/* Thinking indicator (before first token) */}
        {isStreaming && !streamingContent && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex gap-3 px-4"
          >
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-accent-violet to-accent-indigo flex items-center justify-center text-xs font-bold text-white flex-shrink-0 mt-1">
              G
            </div>
            <div className="bg-bg-elevated border border-border-subtle rounded-2xl rounded-tl-sm px-4 py-3">
              <div className="flex items-center gap-1.5">
                {[0, 1, 2].map(i => (
                  <motion.div
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-accent-glow/60"
                    animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 0.8, delay: i * 0.2, repeat: Infinity }}
                  />
                ))}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <div ref={bottomRef} />
    </div>
  )
}

function SuggestionChip({ text }) {
  const { sendMessage } = useGraceStore()
  return (
    <button
      onClick={() => sendMessage(text.replace(/^[^\s]+\s/, ''))}
      className="no-drag px-4 py-2 rounded-xl bg-bg-elevated border border-border-default hover:border-accent-violet/40 text-text-secondary hover:text-text-primary text-sm transition-all"
    >
      {text}
    </button>
  )
}
