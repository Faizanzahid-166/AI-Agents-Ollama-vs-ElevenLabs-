// src/components/VoiceOrb.jsx – Animated orb with waveform
import { motion, AnimatePresence } from 'framer-motion'
import clsx from 'clsx'

export default function VoiceOrb({ isRecording, isSpeaking, isStreaming }) {
  const state = isRecording ? 'recording' : isSpeaking ? 'speaking' : isStreaming ? 'thinking' : 'idle'

  const orbColors = {
    idle:      'from-accent-violet/20 to-accent-indigo/10',
    thinking:  'from-accent-indigo/40 to-accent-violet/30',
    recording: 'from-red-500/40 to-rose-600/30',
    speaking:  'from-accent-cyan/40 to-accent-violet/30',
  }

  const glowColors = {
    idle:      'rgba(124, 58, 237, 0.15)',
    thinking:  'rgba(79, 70, 229, 0.4)',
    recording: 'rgba(239, 68, 68, 0.5)',
    speaking:  'rgba(6, 182, 212, 0.4)',
  }

  return (
    <div className="relative flex items-center justify-center w-20 h-20">
      {/* Outer glow */}
      <motion.div
        className="absolute inset-0 rounded-full"
        animate={{
          boxShadow: `0 0 ${state === 'idle' ? 20 : 40}px ${glowColors[state]}`,
          scale: state !== 'idle' ? [1, 1.06, 1] : 1,
        }}
        transition={{ duration: 2, repeat: state !== 'idle' ? Infinity : 0, ease: 'easeInOut' }}
      />

      {/* Orb body */}
      <motion.div
        className={clsx('w-16 h-16 rounded-full bg-gradient-to-br', orbColors[state], 'border border-white/10 flex items-center justify-center backdrop-blur-sm')}
        animate={{ scale: state === 'recording' ? [1, 1.05, 1] : 1 }}
        transition={{ duration: 0.6, repeat: state === 'recording' ? Infinity : 0 }}
      >
        {/* Waveform bars */}
        <AnimatePresence>
          {(state === 'recording' || state === 'speaking') && (
            <div className="flex items-center gap-[3px]">
              {[0.4, 0.7, 1, 0.8, 0.5, 0.9, 0.6].map((h, i) => (
                <motion.div
                  key={i}
                  className="w-[3px] rounded-full bg-white/80"
                  initial={{ scaleY: 0.2 }}
                  animate={{ scaleY: [0.2, h, 0.2] }}
                  transition={{
                    duration: 0.6,
                    delay: i * 0.07,
                    repeat: Infinity,
                    ease: 'easeInOut',
                  }}
                  style={{ height: 20 }}
                />
              ))}
            </div>
          )}
          {state === 'thinking' && (
            <div className="flex items-center gap-1">
              {[0, 1, 2].map(i => (
                <motion.div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-white/70"
                  animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
                  transition={{ duration: 0.9, delay: i * 0.2, repeat: Infinity }}
                />
              ))}
            </div>
          )}
          {state === 'idle' && (
            <motion.div
              className="w-6 h-6 rounded-full bg-white/20"
              animate={{ scale: [1, 1.1, 1] }}
              transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
            />
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
