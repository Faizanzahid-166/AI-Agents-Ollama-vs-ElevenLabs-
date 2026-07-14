"""
core/ai_engine.py
=================
The offline "brain" of Jarvis.

This module provides:
  1. Intent classification  — keyword + embedding-based NLU
  2. Response generation    — memory-augmented retrieval + rule templates
  3. Context assembly       — blending recent history + semantic memory

NO external LLM APIs. Everything runs locally using:
  - Sentence-transformer embeddings for semantic intent matching
  - A curated intent pattern library
  - Template-based response composition with dynamic memory injection
"""

import re
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.ai_engine")

# ─────────────────────────────────────────────────────────────────────────────
# Intent definitions
# Each intent has:
#   - keywords: simple word triggers (fast path)
#   - patterns: regex patterns (medium path)
#   - examples: used for embedding-based matching (slow path)
# ─────────────────────────────────────────────────────────────────────────────
INTENT_DEFINITIONS: Dict[str, Dict] = {
    "file_operation": {
        "keywords": [
            "create file", "make file", "new file", "write file",
            "delete file", "remove file", "open file", "read file",
            "move file", "copy file", "rename file", "update file",
            "create folder", "make folder", "new folder", "mkdir",
            "create word", "create excel", "create powerpoint",
            "docx", "xlsx", "pptx", "txt",
        ],
        "patterns": [
            r"\b(create|make|new|write)\b.{0,20}\b(file|document|folder|dir)\b",
            r"\b(delete|remove|trash)\b.{0,20}\b(file|folder)\b",
            r"\b(move|copy|rename)\b.{0,20}\b(file|folder|to)\b",
            r"\b(open|read|show|view)\b.{0,20}\b(file|document)\b",
        ],
        "examples": [
            "create a word document named report",
            "make a new excel spreadsheet",
            "delete the file old_notes.txt",
            "move all pdfs to the documents folder",
            "create a folder called projects",
        ],
    },
    "system_organize": {
        "keywords": [
            "organize", "sort files", "clean downloads", "tidy up",
            "auto organize", "organize files", "sort my downloads",
            "clean desktop", "move all", "sort all",
        ],
        "patterns": [
            r"\b(clean|tidy|sort|organize|arrange)\b.{0,30}\b(folder|files|desktop|downloads)\b",
        ],
        "examples": [
            "organize my downloads folder",
            "clean up my desktop",
            "sort all my files automatically",
        ],
    },
    "memory_query": {
        "keywords": [
            "what did i", "what have i", "what was i", "do you remember",
            "recall", "yesterday", "last week", "summarize my", "summary of",
            "what did we work", "what were we", "activities",
        ],
        "patterns": [
            r"what (did|have) i.{0,30}(work|do|say|create|make)",
            r"(recall|remember|history|summary).{0,30}(work|activity|yesterday|last)",
            r"(summarize|summary).{0,20}(activities|work|session)",
        ],
        "examples": [
            "what did I work on yesterday",
            "summarize my activities from last week",
            "what were we discussing earlier",
            "do you remember what I said about the project",
        ],
    },
    "task_query": {
        "keywords": [
            "what should i do", "what to do", "todo", "tasks", "task list",
            "add task", "create task", "new task", "reminder", "remind me",
            "pending tasks", "my tasks", "complete task", "done task",
            "mark complete", "finish task",
        ],
        "patterns": [
            r"\b(add|create|new)\b.{0,20}\b(task|todo|reminder)\b",
            r"\b(what|show).{0,20}\b(task|todo|should i do)\b",
            r"\b(complete|finish|done|mark)\b.{0,20}\b(task|todo)\b",
            r"remind me to",
        ],
        "examples": [
            "what should I do today",
            "add a task to call the client",
            "show me my pending tasks",
            "mark the report task as complete",
        ],
    },
    "schedule_query": {
        "keywords": [
            "schedule", "what is my schedule", "calendar", "today's plan",
            "what's planned", "agenda", "meetings today", "what is today",
        ],
        "patterns": [
            r"\b(schedule|calendar|agenda|plan)\b",
            r"what.{0,20}(today|planned|scheduled|agenda)",
        ],
        "examples": [
            "what is my schedule for today",
            "show me my agenda",
            "what's planned for this week",
        ],
    },
    "general": {
        "keywords": [],
        "patterns": [],
        "examples": [
            "hello",
            "how are you",
            "what can you do",
            "help",
            "tell me about yourself",
        ],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Response templates for general conversation
# ─────────────────────────────────────────────────────────────────────────────
RESPONSE_TEMPLATES: Dict[str, List[str]] = {
    "greeting": [
        "Hello! How can I assist you today?",
        "Hi there! I'm Jarvis, your offline assistant. What do you need?",
        "Good {time_of_day}! Ready to help.",
    ],
    "help": [
        (
            "Here's what I can do:\n"
            "  • File operations: create, read, update, delete, move files and folders\n"
            "  • Work with Word (.docx), Excel (.xlsx), PowerPoint (.pptx), and text files\n"
            "  • Organize your downloads and documents automatically\n"
            "  • Manage tasks and reminders\n"
            "  • Answer 'what did I work on today/yesterday?'\n"
            "  • Semantic memory: I remember your past conversations\n"
            "\nTry: 'Create a Word file named report' or 'What should I do today?'"
        )
    ],
    "unknown": [
        "I'm not sure what you mean. Try asking about tasks, files, or your schedule.",
        "Could you rephrase that? I work best with specific commands like 'create file' or 'show tasks'.",
        "I didn't fully understand that. Say 'help' to see what I can do.",
    ],
    "capabilities": [
        (
            "I'm Jarvis — a fully offline AI assistant. I can:\n"
            "  • Manage your files and folders\n"
            "  • Remember your conversations\n"
            "  • Track tasks and reminders\n"
            "  • Summarise what you've been working on\n"
            "All of this runs 100% on your local machine — no internet required."
        )
    ],
}


class AIEngine:
    """
    Offline reasoning engine.
    Combines embedding-based intent matching with template responses
    and memory-augmented context.
    """

    def __init__(self, memory, task_manager, settings):
        self.memory = memory
        self.task_manager = task_manager
        self.settings = settings
        self._intent_embeddings: Optional[Dict[str, List]] = None
        self._precompute_intent_embeddings()
        logger.info("AI Engine initialised (offline mode).")

    # ------------------------------------------------------------------ #
    # Intent classification
    # ------------------------------------------------------------------ #

    def classify_intent(self, text: str) -> Dict:
        """
        Three-tier classification:
          1. Fast keyword scan  (O(n) string search)
          2. Regex patterns     (O(n) regex match)
          3. Embedding cosine   (O(k) dot product)
        Returns {type, confidence, params}
        """
        text_lower = text.lower().strip()

        # Tier 1: keywords
        result = self._keyword_match(text_lower)
        if result and result["confidence"] >= 0.6:
            result["params"] = self._extract_params(text, result["type"])
            return result

        # Tier 2: regex
        result = self._regex_match(text_lower)
        if result and result["confidence"] >= 0.5:
            result["params"] = self._extract_params(text, result["type"])
            return result

        # Tier 3: embeddings (if model loaded)
        if self._intent_embeddings:
            result = self._embedding_match(text)
            if result and result["confidence"] >= self.settings.INTENT_CONFIDENCE_THRESHOLD:
                result["params"] = self._extract_params(text, result["type"])
                return result

        return {"type": "general", "confidence": 0.3, "params": {}}

    def _keyword_match(self, text: str) -> Optional[Dict]:
        best_intent = None
        best_score = 0.0
        for intent_name, defn in INTENT_DEFINITIONS.items():
            for kw in defn["keywords"]:
                if kw in text:
                    score = len(kw) / max(len(text), 1)  # longer match = more confident
                    if score > best_score:
                        best_score = score
                        best_intent = intent_name
        if best_intent:
            confidence = min(0.9, 0.5 + best_score * 3)
            return {"type": best_intent, "confidence": confidence}
        return None

    def _regex_match(self, text: str) -> Optional[Dict]:
        for intent_name, defn in INTENT_DEFINITIONS.items():
            for pattern in defn["patterns"]:
                if re.search(pattern, text, re.IGNORECASE):
                    return {"type": intent_name, "confidence": 0.75}
        return None

    def _embedding_match(self, text: str) -> Optional[Dict]:
        import numpy as np
        query_emb = self.memory.embed(text)
        if query_emb is None:
            return None
        q = np.array(query_emb)
        best_intent = "general"
        best_sim = 0.0
        for intent_name, emb_list in self._intent_embeddings.items():
            for emb in emb_list:
                e = np.array(emb)
                sim = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-9))
                if sim > best_sim:
                    best_sim = sim
                    best_intent = intent_name
        return {"type": best_intent, "confidence": round(best_sim, 3)}

    def _precompute_intent_embeddings(self):
        """Pre-embed all example sentences at startup for fast matching."""
        if self.memory._model is None:
            logger.debug("Skipping embedding pre-computation (model unavailable).")
            return
        self._intent_embeddings = {}
        for intent_name, defn in INTENT_DEFINITIONS.items():
            examples = defn.get("examples", [])
            if examples:
                embs = [self.memory.embed(ex) for ex in examples]
                self._intent_embeddings[intent_name] = [e for e in embs if e is not None]
        logger.debug(f"Pre-computed embeddings for {len(self._intent_embeddings)} intents.")

    # ------------------------------------------------------------------ #
    # Parameter extraction
    # ------------------------------------------------------------------ #

    def _extract_params(self, text: str, intent_type: str) -> Dict:
        """Extract structured params from raw text."""
        params: Dict = {}
        text_lower = text.lower()

        if intent_type == "file_operation":
            # Operation type
            for op in ["create", "delete", "move", "copy", "read", "update", "rename", "open"]:
                if op in text_lower:
                    params["operation"] = op
                    break

            # File type
            for ext in [".docx", ".xlsx", ".pptx", ".txt", ".pdf", ".py", ".csv"]:
                if ext in text_lower:
                    params["file_type"] = ext
                    break
            for label, ext in [("word", ".docx"), ("excel", ".xlsx"),
                                ("powerpoint", ".pptx"), ("text", ".txt")]:
                if label in text_lower:
                    params.setdefault("file_type", ext)

            # Filename — look for "named X" or "called X"
            m = re.search(r'(?:named?|called?)\s+["\']?(\w[\w\s\-\.]{1,50})["\']?', text, re.I)
            if m:
                params["filename"] = m.group(1).strip()

            # Source / destination path
            m = re.search(r'\bfrom\s+["\']?([^\'"]+)["\']?', text, re.I)
            if m:
                params["source"] = m.group(1).strip()
            m = re.search(r'\bto\s+["\']?([^\'"]+)["\']?', text, re.I)
            if m:
                params["destination"] = m.group(1).strip()

        elif intent_type == "task_query":
            for op in ["add", "create", "show", "list", "complete", "delete", "finish"]:
                if op in text_lower:
                    params["operation"] = op
                    break
            # Task title — everything after "task to" or "task:"
            m = re.search(r'(?:task\s+to|task:?|remind(?:er)?\s+to)\s+(.+)', text, re.I)
            if m:
                params["title"] = m.group(1).strip()

        elif intent_type == "memory_query":
            for period in ["today", "yesterday", "last week", "last month", "this week"]:
                if period in text_lower:
                    params["period"] = period
                    break
            params.setdefault("period", "today")

        return params

    # ------------------------------------------------------------------ #
    # Response generation
    # ------------------------------------------------------------------ #

    def respond(self, text: str) -> str:
        """
        Generate a contextual response for general queries.
        Injects relevant memory context.
        """
        text_lower = text.lower().strip()

        # Greetings
        if any(w in text_lower for w in ["hello", "hi", "hey", "good morning", "good evening"]):
            return self._template_response("greeting")

        # Help / capabilities
        if any(w in text_lower for w in ["help", "what can you", "capabilities", "commands"]):
            return self._template_response("help")

        if any(w in text_lower for w in ["who are you", "what are you", "tell me about yourself"]):
            return self._template_response("capabilities")

        # Memory-augmented fallback
        context = self.memory.get_context_for_ai(text)
        if context:
            last_user = next((c for c in reversed(context) if c["role"] == "user"), None)
            if last_user and last_user["content"].lower() != text_lower:
                snippet = last_user["content"][:100]
                return (
                    f"Based on our recent conversation, you were working on: \"{snippet}\".\n"
                    f"I don't have a specific answer for your current query, but I've logged it. "
                    f"Try rephrasing or check your task list."
                )

        return self._template_response("unknown")

    def _template_response(self, key: str) -> str:
        templates = RESPONSE_TEMPLATES.get(key, RESPONSE_TEMPLATES["unknown"])
        chosen = random.choice(templates)
        hour = datetime.now().hour
        time_of_day = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")
        return chosen.format(time_of_day=time_of_day)
