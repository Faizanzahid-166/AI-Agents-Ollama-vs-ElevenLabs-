// src/hooks/useVoiceRecorder.js – MediaRecorder + STT upload
import { useRef, useCallback } from 'react'
import { useGraceStore } from '../stores/graceStore'

const API = 'http://localhost:8000/api'

export function useVoiceRecorder() {
  const mediaRecorder = useRef(null)
  const chunks = useRef([])
  const { setRecording, sendMessage } = useGraceStore()

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunks.current = []

      const options = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? { mimeType: 'audio/webm;codecs=opus' }
        : {}

      mediaRecorder.current = new MediaRecorder(stream, options)
      mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data)
      }

      mediaRecorder.current.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        const blob = new Blob(chunks.current, { type: 'audio/webm' })
        await uploadAndTranscribe(blob, sendMessage, setRecording)
      }

      mediaRecorder.current.start(250) // collect every 250ms
      setRecording(true)
    } catch (e) {
      console.error('Mic access denied:', e)
      alert('Microphone access required for voice chat.')
    }
  }, [sendMessage, setRecording])

  const stopRecording = useCallback(() => {
    if (mediaRecorder.current?.state === 'recording') {
      mediaRecorder.current.stop()
    }
    setRecording(false)
  }, [setRecording])

  const toggleRecording = useCallback(() => {
    const { isRecording } = useGraceStore.getState()
    if (isRecording) stopRecording()
    else startRecording()
  }, [startRecording, stopRecording])

  return { startRecording, stopRecording, toggleRecording }
}

async function uploadAndTranscribe(blob, sendMessage, setRecording) {
  try {
    const form = new FormData()
    form.append('audio', blob, 'recording.webm')
    form.append('language', 'en')

    const r = await fetch(`${API}/voice/transcribe`, { method: 'POST', body: form })
    if (!r.ok) throw new Error(`STT failed: ${r.status}`)
    const data = await r.json()
    if (data.transcript?.trim()) {
      sendMessage(data.transcript.trim())
    }
  } catch (e) {
    console.error('Transcription error:', e)
  } finally {
    setRecording(false)
  }
}
