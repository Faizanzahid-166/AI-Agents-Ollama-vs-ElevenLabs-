"""
ui/app.py  (REALTIME UPGRADE)
──────────────────────────────
Replaces the sequential record→transcribe→generate→speak loop with
a fully event-driven, multi-threaded realtime pipeline.

Event flow:
  MicCapture (StreamingMicCapture)
      │ PCM chunks via VAD
      ▼
  STTWorker
      │ on_partial() → UI partial transcript
      │ on_final()   → triggers LLM
      ▼
  OllamaClient.stream_realtime()
      │ token_q  → UI appends tokens live
      │ sentence_q → TTSPipeline
      ▼
  TTSPipeline (TTSWorker + AudioPlayer)
      │ speaking callbacks → orb / input bar state

Interrupt path:
  User presses ✋ or mic button while speaking
      → pipeline.interrupt()
      → cancel_event.set()
      → audio stops in <50ms
      → new listening cycle begins
"""

import queue
import threading
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from core.config import cfg
from core.llm import llm
from core.memory import memory
from core import models as db
from core.database import check_connection
from core.models import init_schema
from core.stt import STTWorker, preload_model as preload_whisper
from core.tts import tts_pipeline
from ui import theme as T
from ui.sidebar import Sidebar
from ui.chat_view import ChatView
from ui.input_bar import InputBar
from utils.audio import StreamingMicCapture, AudioChunkQueue
from utils.logger import log

USER_ID = "user_default"


class GraceApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._init_state()
        self._build_ui()
        self._boot()

    # ── Window ─────────────────────────────────────────────────────────────────

    def _setup_window(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("Grace")
        self.geometry(f"{T.WINDOW_W}x{T.WINDOW_H}")
        self.minsize(T.WINDOW_MIN_W, T.WINDOW_MIN_H)
        self.configure(fg_color=T.BG_BASE)
        try:
            self.iconbitmap(str(cfg.ROOT_DIR / "assets" / "icon.ico"))
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── State ──────────────────────────────────────────────────────────────────

    def _init_state(self):
        self._active_conv_id: Optional[str] = None
        self._mode         = "chat"
        self._tts_enabled  = False

        # Realtime pipeline control
        self._cancel_event  = threading.Event()   # cancels LLM stream
        self._mic_active    = False
        self._streaming     = False

        # Queues that cross thread boundaries
        self._stt_in_queue: AudioChunkQueue   = queue.Queue()
        self._token_queue:  queue.Queue        = queue.Queue()
        self._sentence_q:   queue.Queue        = queue.Queue()  # alias into tts_pipeline

        # Accumulates partial STT text for display
        self._partial_transcript = ""

        # Full response accumulator
        self._response_parts: list[str] = []

        # Background worker handles
        self._mic_capture: Optional[StreamingMicCapture] = None
        self._stt_worker:  Optional[STTWorker]            = None

    # ── UI ─────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)

        # Header
        self._header = self._make_header()
        self._header.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Sidebar
        self._sidebar = Sidebar(
            self,
            on_new_chat=self._new_chat,
            on_select_conv=self._load_conversation,
            on_delete_conv=self._delete_conversation,
            on_mode_change=self._change_mode,
        )
        self._sidebar.grid(row=1, column=0, rowspan=2, sticky="ns")

        ctk.CTkFrame(self, width=1, fg_color=T.BORDER_SUBTLE).grid(
            row=1, column=0, rowspan=2, sticky="nse"
        )

        # Chat view
        self._chat = ChatView(self)
        self._chat.grid(row=1, column=1, sticky="nsew")

        # Input bar — wire all callbacks
        self._input = InputBar(
            self,
            on_send=self._send_text,
            on_stop=self._stop_generation,
            on_voice_toggle=self._toggle_mic,
            on_interrupt=self._interrupt_speech,
            on_tts_toggle=self._set_tts,
        )
        self._input.grid(row=2, column=1, sticky="ew")

    def _make_header(self) -> ctk.CTkFrame:
        hdr = ctk.CTkFrame(self, height=T.TITLEBAR_H, fg_color=T.BG_SURFACE, corner_radius=0)
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="Grace  ✦  Realtime AI Assistant",
            font=ctk.CTkFont(family=T.FONT_FAMILY_TITLE, size=13),
            text_color=T.TEXT_SECONDARY,
        ).pack(side="left", expand=True, padx=T.SIDEBAR_W)

        self._conn_label = ctk.CTkLabel(
            hdr, text="● starting",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=10),
            text_color=T.WARNING,
        )
        self._conn_label.pack(side="right", padx=T.PAD_LG)
        return hdr

    # ── Boot ───────────────────────────────────────────────────────────────────

    def _boot(self):
        def _init():
            # DB
            ok = check_connection()
            if ok:
                init_schema()
                self.after(0, self._on_db_ready)
            else:
                self.after(0, lambda: self._chat.add_system_message(
                    "⚠ Cannot connect to PostgreSQL. Check .env"
                ))

            # Ollama
            ollama_ok = llm.is_available()
            self.after(0, lambda: self._update_conn(ollama_ok))
            if ollama_ok:
                llm.preload("chat")
                llm.preload("code")

            # Preload faster-whisper
            preload_whisper()

            # Start TTS pipeline
            tts_pipeline.on_speaking_change = self._on_speaking_change
            tts_pipeline.start()

            # Embedder
            from core.memory import _get_embedder
            _get_embedder()

        threading.Thread(target=_init, daemon=True).start()

    def _on_db_ready(self):
        self._load_sidebar()

    def _update_conn(self, ok: bool):
        self._conn_label.configure(
            text="● connected" if ok else "● ollama offline",
            text_color=T.SUCCESS if ok else T.ERROR,
        )
        if not ok:
            self._chat.add_system_message(
                "⚠ Ollama not running. Start with: ollama serve"
            )

    # ── Mic / VAD / STT ────────────────────────────────────────────────────────

    def _toggle_mic(self):
        if self._mic_active:
            self._stop_mic()
        else:
            self._start_mic()

    def _start_mic(self):
        if self._mic_active:
            return

        # Interrupt any ongoing speech first
        if self._streaming or tts_pipeline._playing:
            self._interrupt_speech()

        self._mic_active = True
        self._partial_transcript = ""
        self._input.set_recording(True)

        # Spin up STT worker
        stop_ev = threading.Event()
        self._stt_stop = stop_ev
        self._stt_worker = STTWorker(
            in_queue   = self._stt_in_queue,
            on_partial = self._on_stt_partial,
            on_final   = self._on_stt_final,
            on_error   = self._on_stt_error,
            stop_event = stop_ev,
        )
        self._stt_worker.start()

        # Start mic capture
        self._mic_capture = StreamingMicCapture(
            out_queue          = self._stt_in_queue,
            vad_aggressiveness = 2,
            on_speech_start    = self._on_vad_speech_start,
            on_speech_end      = self._on_vad_speech_end,
        )
        self._mic_capture.start()

    def _stop_mic(self):
        self._mic_active = False
        if self._mic_capture:
            self._mic_capture.stop()
            self._mic_capture = None
        if hasattr(self, "_stt_stop"):
            self._stt_stop.set()
        self._input.set_recording(False)

    # ── VAD callbacks (called from audio thread — use .after()) ───────────────

    def _on_vad_speech_start(self):
        self.after(0, lambda: self._input._orb.set_state("listening"))

    def _on_vad_speech_end(self):
        self.after(0, lambda: self._input._orb.set_state("thinking"))

    # ── STT callbacks (from STTWorker thread — use .after()) ──────────────────

    def _on_stt_partial(self, text: str):
        self._partial_transcript += " " + text
        self.after(0, lambda t=self._partial_transcript.strip():
                   self._input.set_partial_transcript(t))

    def _on_stt_final(self, full_text: str):
        text = full_text.strip()
        if not text:
            return
        log.info(f"STT final: '{text}'")
        # Stop mic, show user message, start LLM
        self.after(0, lambda: self._on_transcription_complete(text))

    def _on_stt_error(self, err: str):
        log.error(f"STT error: {err}")
        self.after(0, lambda: self._chat.add_system_message(f"⚠ STT: {err}"))
        self.after(0, self._stop_mic)

    def _on_transcription_complete(self, text: str):
        self._stop_mic()
        self._partial_transcript = ""
        self._send_message(text)

    # ── Message sending ─────────────────────────────────────────────────────────

    def _send_text(self, text: str):
        """Called when user sends a typed message."""
        self._send_message(text)

    def _send_message(self, text: str):
        """Core: show user bubble + start realtime LLM stream."""
        if self._streaming:
            return
        if not text.strip():
            return

        conv_id = self._ensure_conversation()
        self._chat.add_message("user", text, datetime.now())

        self._streaming        = True
        self._response_parts   = []
        self._cancel_event.clear()
        self._input.set_streaming(True)
        self._input.set_thinking(True)

        def _prepare_and_stream():
            history, ctx = memory.build_context(conv_id, text)
            # Create streaming bubble on UI thread, then start LLM
            self.after(0, lambda: self._start_llm_stream(
                text, history, ctx, conv_id
            ))

        threading.Thread(target=_prepare_and_stream, daemon=True).start()

    def _start_llm_stream(
        self, user_text: str, history: list, ctx: str, conv_id: str
    ):
        self._input.set_thinking(False)
        self._chat.start_streaming()
        self._sentence_q = tts_pipeline.sentence_queue

        # Drain previous tokens from queue
        while not self._token_queue.empty():
            try:
                self._token_queue.get_nowait()
            except queue.Empty:
                break

        # Start polling the token queue
        self.after(16, self._poll_token_queue)

        # Fire LLM in background
        llm.stream_realtime(
            user_message   = user_text,
            history        = history,
            token_queue    = self._token_queue,
            sentence_queue = self._sentence_q if self._tts_enabled else queue.Queue(),
            cancel_event   = self._cancel_event,
            system_context = ctx,
            mode           = self._mode,
            on_done        = lambda full: self.after(0, lambda: self._on_llm_done(full, conv_id, user_text)),
            on_error       = lambda err: self.after(0, lambda: self._on_llm_error(err)),
        )


    def _poll_token_queue(self):
        """Drain the token queue into the UI — called every 16ms on main thread."""
        if not self._streaming:
            return
        try:
            while True:
                token = self._token_queue.get_nowait()
                if token is None:
                    return   # stream ended — handled by on_done
                self._response_parts.append(token)
                self._chat.append_token(token)
        except queue.Empty:
            pass
        self.after(16, self._poll_token_queue)   # schedule next poll

    def _on_llm_done(self, full_text: str, conv_id: str, user_text: str):
        self._chat.finalize_streaming()
        self._streaming = False
        self._input.set_streaming(False)

        if self._tts_enabled:
            tts_pipeline.signal_done()

        if not full_text.strip():
            return

        def _save():
            memory.save_turn(conv_id, user_text, full_text, self._mode)
            msgs = db.get_all_messages(conv_id)
            if len(msgs) <= 2:
                memory.auto_title(conv_id, user_text, llm.complete)
                self.after(600, lambda: self._load_sidebar())
            memory.maybe_summarize(conv_id, llm.complete)

        threading.Thread(target=_save, daemon=True).start()

    def _on_llm_error(self, err: str):
        self._chat.finalize_streaming()
        self._streaming = False
        self._input.set_streaming(False)
        self._chat.add_system_message(f"⚠ LLM error: {err}")

    # ── Stop / interrupt ───────────────────────────────────────────────────────

    def _stop_generation(self):
        """Stop LLM generation (⏹ button while streaming text)."""
        self._cancel_event.set()
        self._streaming = False
        self._input.set_streaming(False)
        partial = "".join(self._response_parts)
        if partial.strip():
            self._chat.finalize_streaming()
        self._response_parts = []

    def _interrupt_speech(self):
        """
        Interrupt Grace mid-speech — stops audio immediately.
        Arms the mic so the user can speak right away.
        """
        log.info("🛑 Interrupt")
        self._cancel_event.set()
        tts_pipeline.interrupt()
        self._streaming = False
        self._response_parts = []
        self._input.set_interrupted()
        # Brief delay then return to idle / ready state
        self.after(500, lambda: self._input.set_streaming(False))

    # ── TTS speaking callbacks ─────────────────────────────────────────────────

    def _on_speaking_change(self, speaking: bool):
        """Called from AudioPlayer thread — must use .after()."""
        self.after(0, lambda: self._input.set_speaking(speaking))

    # ── TTS toggle ─────────────────────────────────────────────────────────────

    def _set_tts(self, enabled: bool):
        self._tts_enabled = enabled

    # ── Conversation management ────────────────────────────────────────────────

    def _ensure_conversation(self) -> str:
        if not self._active_conv_id:
            cid = db.create_conversation(USER_ID, mode=self._mode)
            self._active_conv_id = cid
            self.after(0, self._load_sidebar)
            self.after(0, lambda: self._sidebar.select(cid))
        return self._active_conv_id

    def _new_chat(self):
        self._active_conv_id = None
        self._chat.clear()
        self._input.focus_input()

    def _load_conversation(self, conv_id: str):
        self._active_conv_id = conv_id
        self._chat.clear()
        def _fetch():
            msgs = db.get_all_messages(conv_id)
            self.after(0, lambda: self._chat.load_messages(msgs))
        threading.Thread(target=_fetch, daemon=True).start()

    def _delete_conversation(self, conv_id: str):
        threading.Thread(
            target=lambda: db.delete_conversation(conv_id), daemon=True
        ).start()
        if self._active_conv_id == conv_id:
            self._new_chat()

    def _load_sidebar(self):
        convs = db.list_conversations(USER_ID)
        self.after(0, lambda: self._sidebar.load_conversations(convs))

    def _change_mode(self, mode: str):
        self._mode = mode
        self._input.set_mode(mode)

    # ── Close ──────────────────────────────────────────────────────────────────

    def _on_close(self):
        self._cancel_event.set()
        tts_pipeline.shutdown()
        if self._mic_capture:
            self._mic_capture.stop()
        from core.database import close_pool
        try:
            close_pool()
        except Exception:
            pass
        self.destroy()
