// src/components/MessageBubble.jsx – Renders a single message with markdown + code highlighting
import { memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { motion } from 'framer-motion'
import { Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

const CodeBlock = memo(({ children, className }) => {
  const [copied, setCopied] = useState(false)
  const lang = /language-(\w+)/.exec(className || '')?.[1] || 'text'
  const code = String(children).replace(/\n$/, '')

  const copy = () => {
    navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative group rounded-xl overflow-hidden border border-border-default my-2">
      <div className="flex items-center justify-between px-4 py-2 bg-bg-overlay border-b border-border-subtle">
        <span className="text-xs font-mono text-text-muted">{lang}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-xs text-text-muted hover:text-text-secondary transition-colors"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <SyntaxHighlighter
        language={lang}
        style={oneDark}
        customStyle={{ margin: 0, background: '#0e0e1a', fontSize: '13px', padding: '16px' }}
        showLineNumbers={code.split('\n').length > 5}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
})

const mdComponents = {
  code({ node, inline, className, children, ...props }) {
    if (inline) return <code className={className} {...props}>{children}</code>
    return <CodeBlock className={className}>{children}</CodeBlock>
  },
}

export default memo(function MessageBubble({ message, isStreaming = false }) {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'

  if (isSystem) {
    return (
      <div className="text-center py-1">
        <span className="text-xs text-text-muted bg-bg-overlay px-3 py-1 rounded-full">{message.content}</span>
      </div>
    )
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={clsx('flex gap-3 px-4', isUser ? 'flex-row-reverse' : 'flex-row')}
    >
      {/* Avatar */}
      <div className={clsx(
        'w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold mt-1',
        isUser
          ? 'bg-accent-violet/30 text-accent-glow'
          : 'bg-gradient-to-br from-accent-violet to-accent-indigo text-white'
      )}>
        {isUser ? 'U' : 'G'}
      </div>

      {/* Bubble */}
      <div className={clsx(
        'max-w-[75%] rounded-2xl px-4 py-3',
        isUser
          ? 'bg-accent-violet/15 border border-accent-violet/20 rounded-tr-sm'
          : 'bg-bg-elevated border border-border-subtle rounded-tl-sm'
      )}>
        <div className={clsx('prose-grace text-sm', isStreaming && 'streaming-cursor')}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
            {message.content}
          </ReactMarkdown>
        </div>
        {message.timestamp && (
          <p className="text-[10px] text-text-muted mt-1.5 text-right">
            {formatDistanceToNow(new Date(message.timestamp), { addSuffix: true })}
          </p>
        )}
      </div>
    </motion.div>
  )
})
