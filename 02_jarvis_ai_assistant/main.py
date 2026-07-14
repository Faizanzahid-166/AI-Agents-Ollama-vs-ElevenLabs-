"""
JARVIS AI ASSISTANT — FULLY OFFLINE
====================================
Main entry point. Boots all subsystems, starts command loop.
No internet. No external APIs. 100% local.
"""

import sys
import logging
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings
from database.db import Database
from core.ai_engine import AIEngine
from core.speech_to_text import SpeechToText
from core.memory import MemorySystem
from core.task_manager import TaskManager
from agents.file_manager import FileManager
from utils.logger import setup_logger
from core.text_to_speech import TextToSpeech

logger = setup_logger("jarvis.main")


class Jarvis:
    """
    Central orchestrator — boots subsystems, routes commands,
    manages the conversation loop.
    """

    def __init__(self):
        logger.info("🚀 Booting JARVIS Offline AI Assistant...")
        self.settings = Settings()
        try:
            self.db = Database(self.settings.DATABASE_URL)
            self.db.initialize_schema()
        except Exception as e:
            logger.error(f"FATAL: Database connection failed. {e}")
            logger.info(f"Please ensure PostgreSQL is running and the database '{self.settings.DB_NAME}' exists.")
            sys.exit(1)

        self.memory = MemorySystem(self.db, self.settings)
        self.task_manager = TaskManager(self.db)
        self.file_manager = FileManager(self.db, self.settings)
        self.ai_engine = AIEngine(self.memory, self.task_manager, self.settings)
        self.stt = SpeechToText(self.settings)
        self.tts = TextToSpeech()

        logger.info("✅ All subsystems online. Jarvis is ready.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def process_text_command(self, text: str) -> str:
        """Route a text command and return a response string."""
        
        if not text or not text.strip():
            return ""

        # ✔ FILTER BAD INPUT BEFORE MEMORY
        if "warning" in text.lower():
            return ""
        if "deprecated" in text.lower():
            return ""

        # Persist raw command
        self.memory.store_interaction(role="user", content=text)

        intent = self.ai_engine.classify_intent(text)
        logger.debug(f"Intent detected: {intent['type']} | confidence={intent['confidence']:.2f}")

        response = self._dispatch(intent, text)

        self.memory.store_interaction(role="assistant", content=response)
        return response

    def process_voice_command(self) -> str:
        """Listen on mic, transcribe, process, return response."""

        print("\n🎙️  Listening... (speak now)")

        transcript = self.stt.listen_and_transcribe()

        # Ignore empty
        if not transcript:
            return ""

        transcript = transcript.strip()

        # Ignore garbage
        blocked_words = [
            "warning",
            "deprecated",
            "here's what i recall related to that"
        ]

        if any(b in transcript.lower() for b in blocked_words):
            return ""

        print(f"📝 You said: {transcript}")

        response = self.process_text_command(transcript)

        print(f"\nJARVIS: {response}\n")

        # 🔥 SPEAK SYNCHRONOUSLY
        # Prevent mic loop
        self.tts.speak(response)

        return response

    # ------------------------------------------------------------------
    # Intent dispatcher
    # ------------------------------------------------------------------

    def _dispatch(self, intent: dict, raw_text: str) -> str:
        intent_type = intent["type"]
        handlers = {
            "file_operation":   self._handle_file,
            "task_query":       self._handle_task,
            "memory_query":     self._handle_memory,
            "schedule_query":   self._handle_schedule,
            "system_organize":  self._handle_organize,
            "general":          self._handle_general,
        }
        handler = handlers.get(intent_type, self._handle_general)
        return handler(intent, raw_text)

    def _handle_file(self, intent: dict, text: str) -> str:
        return self.file_manager.execute(intent, text)

    def _handle_task(self, intent: dict, text: str) -> str:
        return self.task_manager.handle_query(text)

    def _handle_memory(self, intent: dict, text: str) -> str:
        return self.memory.semantic_search_response(text)

    def _handle_schedule(self, intent: dict, text: str) -> str:
        return self.task_manager.get_schedule_summary()

    def _handle_organize(self, intent: dict, text: str) -> str:
        return self.file_manager.auto_organize(text)

    def _handle_general(self, intent: dict, text: str) -> str:
        return self.ai_engine.respond(text)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run_text_mode(self):
        """Interactive text REPL."""
        print("\n" + "=" * 60)
        print("  JARVIS — Offline AI Assistant  (text mode)")
        print("  Type 'exit' to quit | 'voice' for mic input")
        print("=" * 60 + "\n")

        # Boot greeting
        greeting = self.task_manager.get_daily_greeting()
        print(f"JARVIS: {greeting}\n")

        while True:
            try:
                user_input = input("You: ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ("exit", "quit", "bye"):
                    print("JARVIS: Goodbye. Shutting down.")
                    break
                if user_input.lower() == "voice":
                    response = self.process_voice_command()
                else:
                    response = self.process_text_command(user_input)
                print(f"\nJARVIS: {response}\n")
            except KeyboardInterrupt:
                print("\nJARVIS: Interrupted. Goodbye.")
                break

    def run_voice_mode(self):
        """Continuous voice loop with proper silence handling."""
        print("\n🎙️  JARVIS Voice Mode — say 'stop' to exit\n")

        while True:
            response = self.process_voice_command()

            # ✔ IGNORE EMPTY RESPONSES
            if not response or response.strip() == "I didn't catch that. Please try again.":
                continue

            print(f"\nJARVIS: {response}\n")

            # ✔ STOP CONDITION
            if "goodbye" in response.lower() or "shutting down" in response.lower():
                break

# -----------------------------------------------------------------------
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "text"
    jarvis = Jarvis()
    if mode == "voice":
        jarvis.run_voice_mode()
    else:
        jarvis.run_text_mode()
