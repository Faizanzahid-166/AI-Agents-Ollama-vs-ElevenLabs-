// src/App.jsx – Root component
import { useEffect } from 'react'
import { motion } from 'framer-motion'
import { useGraceStore } from './stores/graceStore'
import TitleBar from './components/TitleBar'
import Sidebar from './components/Sidebar'
import ChatWindow from './components/ChatWindow'
import ChatInput from './components/ChatInput'

export default function App() {
  const { connect, loadConversations, sidebarOpen } = useGraceStore()

  useEffect(() => {
    connect()
    loadConversations()
    return () => {
      // Keep WS alive — don't disconnect on hot reload
    }
  }, [])

  return (
    <div className="flex flex-col h-screen bg-bg-base overflow-hidden">
      {/* Custom titlebar */}
      <TitleBar />

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Chat area */}
        <motion.main
          layout
          className="flex flex-col flex-1 overflow-hidden"
        >
          <ChatWindow />
          <ChatInput />
        </motion.main>
      </div>
    </div>
  )
}
