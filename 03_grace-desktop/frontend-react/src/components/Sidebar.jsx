// src/components/Sidebar.jsx
import { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, Plus, Trash2, Code2, Zap, ChevronLeft } from 'lucide-react'
import { useGraceStore } from '../stores/graceStore'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

export default function Sidebar() {
  const {
    conversations, activeConvId, sidebarOpen,
    loadConversations, selectConversation, newConversation,
    deleteConversation, toggleSidebar,
  } = useGraceStore()

  useEffect(() => { loadConversations() }, [])

  return (
    <AnimatePresence>
      {sidebarOpen && (
        <motion.aside
          initial={{ width: 0, opacity: 0 }}
          animate={{ width: 260, opacity: 1 }}
          exit={{ width: 0, opacity: 0 }}
          transition={{ duration: 0.2, ease: 'easeInOut' }}
          className="relative flex flex-col h-full bg-bg-surface border-r border-border-subtle overflow-hidden flex-shrink-0"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-border-subtle">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-accent-violet to-accent-indigo flex items-center justify-center">
                <Zap size={14} className="text-white" />
              </div>
              <span className="font-display font-semibold text-text-primary text-sm">Grace</span>
            </div>
            <button
              onClick={toggleSidebar}
              className="no-drag p-1.5 rounded-lg hover:bg-bg-overlay text-text-muted hover:text-text-secondary transition-colors"
            >
              <ChevronLeft size={15} />
            </button>
          </div>

          {/* New chat button */}
          <div className="px-3 pt-3 pb-1">
            <button
              onClick={newConversation}
              className="no-drag w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-bg-overlay hover:bg-bg-elevated border border-border-default hover:border-border-bright text-text-secondary hover:text-text-primary transition-all text-sm font-medium"
            >
              <Plus size={15} />
              New conversation
            </button>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
            {conversations.length === 0 && (
              <p className="text-text-muted text-xs text-center py-8">No conversations yet</p>
            )}
            {conversations.map((conv) => (
              <ConvItem
                key={conv.id}
                conv={conv}
                isActive={conv.id === activeConvId}
                onSelect={() => selectConversation(conv.id)}
                onDelete={(e) => { e.stopPropagation(); deleteConversation(conv.id) }}
              />
            ))}
          </div>

          {/* Footer */}
          <div className="px-3 py-3 border-t border-border-subtle">
            <p className="text-text-muted text-xs text-center">Grace v2.0 · Local AI</p>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  )
}

function ConvItem({ conv, isActive, onSelect, onDelete }) {
  return (
    <motion.button
      onClick={onSelect}
      layout
      className={clsx(
        'no-drag group w-full flex items-start gap-2.5 px-3 py-2.5 rounded-xl text-left transition-all',
        isActive
          ? 'bg-bg-overlay border border-border-default text-text-primary'
          : 'hover:bg-bg-overlay text-text-secondary hover:text-text-primary border border-transparent'
      )}
    >
      <div className="mt-0.5 flex-shrink-0">
        {conv.mode === 'code'
          ? <Code2 size={14} className="text-accent-cyan" />
          : <MessageSquare size={14} className={isActive ? 'text-accent-glow' : 'text-text-muted'} />
        }
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium truncate leading-tight">{conv.title}</p>
        <p className="text-[10px] text-text-muted mt-0.5">
          {formatDistanceToNow(new Date(conv.updated_at), { addSuffix: true })}
        </p>
      </div>
      <button
        onClick={onDelete}
        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:text-red-400 text-text-muted transition-all flex-shrink-0"
      >
        <Trash2 size={11} />
      </button>
    </motion.button>
  )
}
