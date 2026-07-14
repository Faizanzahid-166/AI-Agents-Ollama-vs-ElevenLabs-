#  core/text_to_speech.py

"""
Offline Text-to-Speech (TTS)
Uses pyttsx3 for fully local voice output.
"""

import pyttsx3
import logging

logger = logging.getLogger("jarvis.tts")


class TextToSpeech:
    def __init__(self):
        self.engine = pyttsx3.init()

        # Speech settings
        self.engine.setProperty("rate", 170)   # speed
        self.engine.setProperty("volume", 1.0)

        # Optional: choose voice
        voices = self.engine.getProperty("voices")

        # voices[0] = male, voices[1] = female (usually)
        if voices:
            self.engine.setProperty("voice", voices[0].id)

        logger.info("TTS engine initialized.")

    def speak(self, text: str):
        if not text:
            return

        logger.info(f"Speaking: {text}")

        self.engine.say(text)
        self.engine.runAndWait()