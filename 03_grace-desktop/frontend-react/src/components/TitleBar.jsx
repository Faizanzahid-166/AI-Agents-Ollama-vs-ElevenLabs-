// src/components/TitleBar.jsx
import { motion } from 'framer-motion'
import { Wifi, WifiOff, PanelLeft } from 'lucide-react'
import { useGraceStore } from '../stores/graceStore'
import clsx from 'clsx'

export default function TitleBar() {
  const { wsStatus, mode, sidebarOpen, toggleSidebar } = useGraceStore()
  const isElectron = !!window.electron

  const statusColor = {
    connected: 'bg-emerald-400',
    connecting: 'bg-yellow-400 animate-pulse',
    disconnected: 'bg-red-400',
    error: 'bg-red-500',
  }[wsStatus]

  return (
    <div className="titlebar-drag flex items-center justify-between h-10 px-4 border-b border-border-subtle bg-bg-surface flex-shrink-0">
      {/* Left: sidebar toggle + title */}
      <div className="flex items-center gap-3 no-drag">
        {!sidebarOpen && (
          <button
            onClick={toggleSidebar}
            className="p-1.5 rounded-lg hover:bg-bg-overlay text-text-muted hover:text-text-secondary transition-colors"
          >
            <PanelLeft size={14} />
          </button>
        )}
        <span className="font-display font-semibold text-sm text-text-primary tracking-wide">
          Grace
        </span>
        <span className={clsx(
          'text-[10px] px-2 py-0.5 rounded-full font-medium',
          mode === 'code' ? 'bg-accent-cyan/10 text-accent-cyan' : 'bg-accent-violet/10 text-accent-glow'
        )}>
          {mode === 'code' ? 'Code Mode' : 'Chat Mode'}
        </span>
      </div>

      {/* Center drag region */}
      <div className="flex-1" />

      {/* Right: status + window controls */}
      <div className="flex items-center gap-3 no-drag">
        {/* Connection status */}
        <div className="flex items-center gap-1.5">
          <div className={clsx('w-1.5 h-1.5 rounded-full', statusColor)} />
          <span className="text-[10px] text-text-muted capitalize hidden sm:block">{wsStatus}</span>
        </div>

        {/* Window controls (Electron only) */}
        {isElectron && (
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => window.electron.minimize()}
              className="w-3 h-3 rounded-full bg-yellow-400/70 hover:bg-yellow-400 transition-colors"
              title="Minimize"
            />
            <button
              onClick={() => window.electron.maximize()}
              className="w-3 h-3 rounded-full bg-green-400/70 hover:bg-green-400 transition-colors"
              title="Maximize"
            />
            <button
              onClick={() => window.electron.close()}
              className="w-3 h-3 rounded-full bg-red-400/70 hover:bg-red-400 transition-colors"
              title="Close"
            />
          </div>
        )}
      </div>
    </div>
  )
}
