"""
ui/input_bar.py  (REALTIME UPGRADE)
────────────────────────────────────
New features vs v3:
  ─ Live partial transcription display (grayed text while listening)
  ─ Interrupt button appears while Grace is speaking
  ─ All state mutations go through set_*() methods (thread-safe via .after())
  ─ Connection status LED in bottom-left
"""

import tkinter as tk
import customtkinter as ctk
from ui import theme as T
from ui.voice_orb import VoiceOrb
from typing import Callable, Optional


class InputBar(ctk.CTkFrame):

    def __init__(
        self,
        parent,
        on_send: Callable[[str], None],
        on_stop: Callable,
        on_voice_toggle: Callable,
        on_interrupt: Callable,
        on_tts_toggle: Callable,
        **kwargs,
    ):
        super().__init__(parent, fg_color=T.BG_BASE, corner_radius=0, **kwargs)
        self._on_send         = on_send
        self._on_stop         = on_stop
        self._on_voice_toggle = on_voice_toggle
        self._on_interrupt    = on_interrupt
        self._on_tts_toggle   = on_tts_toggle

        self._streaming  = False
        self._recording  = False
        self._speaking   = False
        self._tts_on     = False
        self._mode       = "chat"

        self._build()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build(self):
        # Status strip
        status_row = ctk.CTkFrame(self, fg_color="transparent", height=20)
        status_row.pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_XS, 0))
        status_row.pack_propagate(False)

        self._status_label = ctk.CTkLabel(
            status_row, text="",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=10),
            text_color=T.TEXT_MUTED, anchor="w",
        )
        self._status_label.pack(side="left")

        self._model_label = ctk.CTkLabel(
            status_row, text="llama3.2:3b",
            font=ctk.CTkFont(family=T.FONT_FAMILY_MONO, size=9),
            text_color=T.TEXT_MUTED, anchor="e",
        )
        self._model_label.pack(side="right")

        # ── Main input card ────────────────────────────────────────────────────
        self._input_card = ctk.CTkFrame(
            self,
            fg_color=T.BG_INPUT,
            corner_radius=14,
            border_width=1,
            border_color=T.BORDER_DEFAULT,
        )
        self._input_card.pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_XS, T.PAD_MD))

        # Voice orb — always in the frame, shown/hidden
        self._orb = VoiceOrb(self._input_card, size=44, bg=T.BG_INPUT)
        self._orb_visible = False

        # Partial transcription overlay (shown while listening)
        self._partial_label = ctk.CTkLabel(
            self._input_card,
            text="",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=12, slant="italic"),
            text_color=T.TEXT_MUTED,
            anchor="w",
            wraplength=500,
        )

        # Main text input
        self._textbox = tk.Text(
            self._input_card,
            height=2,
            wrap="word",
            bg=T.BG_INPUT,
            fg=T.TEXT_PRIMARY,
            insertbackground=T.ACCENT_GLOW,
            font=T.FONT_MD,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            padx=T.PAD_MD,
            pady=T.PAD_SM,
        )
        self._textbox.pack(
            side="left", fill="both", expand=True,
            padx=(T.PAD_SM, 0), pady=T.PAD_XS,
        )
        self._textbox.bind("<Return>",       self._on_return)
        self._textbox.bind("<Shift-Return>", lambda e: None)
        self._textbox.bind("<KeyRelease>",   self._auto_resize)

        # Placeholder
        self._placeholder     = "Message Grace..."
        self._placeholder_on  = True
        self._textbox.insert("1.0", self._placeholder)
        self._textbox.configure(fg=T.TEXT_MUTED)
        self._textbox.bind("<FocusIn>",  self._clear_ph)
        self._textbox.bind("<FocusOut>", self._restore_ph)

        # Right-side button column
        btn_col = ctk.CTkFrame(self._input_card, fg_color="transparent")
        btn_col.pack(side="right", padx=T.PAD_SM, pady=T.PAD_SM)

        # TTS toggle
        self._tts_btn = self._icon_btn(btn_col, "🔇", self._toggle_tts)
        self._tts_btn.pack(pady=(0, T.PAD_XS))

        # Mic / stop-recording button
        self._mic_btn = self._icon_btn(btn_col, "🎙", self._toggle_voice,
                                       text_color=T.TEXT_SECONDARY)
        self._mic_btn.pack(pady=(0, T.PAD_XS))

        # Interrupt button (hidden unless Grace is speaking)
        self._interrupt_btn = self._icon_btn(
            btn_col, "✋", self._on_interrupt,
            fg_color=T.ERROR, text_color="white",
        )
        # Don't pack yet — shown only when speaking

        # Send / stop-generation button
        self._send_btn = ctk.CTkButton(
            btn_col,
            text="↑",
            width=32, height=32,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=18, weight="bold"),
            fg_color=T.ACCENT_VIOLET,
            hover_color=T.ACCENT_PURPLE,
            text_color="white",
            corner_radius=8,
            command=self._handle_send_stop,
        )
        self._send_btn.pack()

    # ── State API (call from main thread or via .after()) ──────────────────────

    def set_streaming(self, streaming: bool):
        self._streaming = streaming
        if streaming:
            self._send_btn.configure(text="■", fg_color=T.ERROR, hover_color="#cc2222")
            self._set_status("⟳ Grace is thinking…")
        else:
            self._send_btn.configure(text="↑", fg_color=T.ACCENT_VIOLET,
                                     hover_color=T.ACCENT_PURPLE)
            if not self._recording:
                self._set_status("")

    def set_recording(self, recording: bool):
        self._recording = recording
        if recording:
            self._show_orb("listening")
            self._mic_btn.configure(text="⏹", fg_color=T.ERROR, text_color="white")
            self._set_status("🎙 Listening…")
            # Show partial label
            self._textbox.pack_forget()
            self._partial_label.configure(text="…")
            self._partial_label.pack(
                side="left", fill="both", expand=True,
                padx=(T.PAD_SM, 0), pady=T.PAD_XS,
            )
        else:
            self._hide_orb()
            self._mic_btn.configure(text="🎙", fg_color="transparent",
                                    text_color=T.TEXT_SECONDARY)
            self._partial_label.pack_forget()
            self._textbox.pack(
                side="left", fill="both", expand=True,
                padx=(T.PAD_SM, 0), pady=T.PAD_XS,
            )
            if not self._streaming:
                self._set_status("")

    def set_partial_transcript(self, text: str):
        """Update the live transcription preview while listening."""
        self._partial_label.configure(text=text if text else "…")

    def set_thinking(self, thinking: bool):
        if thinking:
            self._show_orb("thinking")
        elif not self._speaking:
            self._hide_orb()

    def set_speaking(self, speaking: bool):
        self._speaking = speaking
        if speaking:
            self._show_orb("speaking")
            self._interrupt_btn.pack(pady=(0, T.PAD_XS),
                                     before=self._send_btn)
        else:
            if not self._streaming:
                self._hide_orb()
            self._interrupt_btn.pack_forget()

    def set_interrupted(self):
        """Flash the orb red briefly."""
        self._show_orb("interrupted")
        self._speaking = False
        self._interrupt_btn.pack_forget()

    def set_mode(self, mode: str):
        self._mode = mode
        from core.config import cfg
        m = cfg.OLLAMA_CODE_MODEL if mode == "code" else cfg.OLLAMA_CHAT_MODEL
        self._model_label.configure(text=m.split(":")[0])

    def set_connection_status(self, status: str):
        colors = {"connected": T.SUCCESS, "disconnected": T.ERROR, "connecting": T.WARNING}
        self._status_label.configure(
            text=f"● {status}",
            text_color=colors.get(status, T.TEXT_MUTED),
        )

    def focus_input(self):
        self._textbox.focus_set()

    # ── Orb helpers ────────────────────────────────────────────────────────────

    def _show_orb(self, state: str):
        self._orb.set_state(state)
        if not self._orb_visible:
            self._orb.pack(
                side="left", padx=(T.PAD_SM, 0), pady=T.PAD_XS,
                before=self._textbox,
            )
            self._orb_visible = True

    def _hide_orb(self):
        if self._orb_visible:
            self._orb.pack_forget()
            self._orb_visible = False

    # ── Input helpers ──────────────────────────────────────────────────────────

    def _get_text(self) -> str:
        if self._placeholder_on:
            return ""
        return self._textbox.get("1.0", "end-1c").strip()

    def _clear(self):
        self._textbox.delete("1.0", "end")
        self._textbox.configure(fg=T.TEXT_PRIMARY)
        self._placeholder_on = False

    def _clear_ph(self, _=None):
        if self._placeholder_on:
            self._textbox.delete("1.0", "end")
            self._textbox.configure(fg=T.TEXT_PRIMARY)
            self._placeholder_on = False

    def _restore_ph(self, _=None):
        if not self._textbox.get("1.0", "end-1c").strip():
            self._textbox.configure(fg=T.TEXT_MUTED)
            self._textbox.insert("1.0", self._placeholder)
            self._placeholder_on = True

    def _on_return(self, e):
        self._handle_send_stop()
        return "break"

    def _auto_resize(self, _=None):
        lines = int(self._textbox.index("end-1c").split(".")[0])
        self._textbox.configure(height=min(lines, 5))

    def _set_status(self, text: str):
        self._status_label.configure(text=text)

    # ── Button actions ─────────────────────────────────────────────────────────

    def _handle_send_stop(self):
        if self._streaming:
            self._on_stop()
        else:
            t = self._get_text()
            if t:
                self._clear()
                self._on_send(t)

    def _toggle_voice(self):
        self._on_voice_toggle()

    def _toggle_tts(self):
        self._tts_on = not self._tts_on
        self._tts_btn.configure(
            text="🔊" if self._tts_on else "🔇",
            text_color=T.ACCENT_CYAN if self._tts_on else T.TEXT_MUTED,
        )
        self._on_tts_toggle(self._tts_on)

    # ── Factory ────────────────────────────────────────────────────────────────

    @staticmethod
    def _icon_btn(parent, text: str, command, fg_color="transparent",
                  text_color=T.TEXT_MUTED) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text=text,
            width=32, height=32,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=14),
            fg_color=fg_color,
            hover_color=T.BG_OVERLAY,
            text_color=text_color,
            corner_radius=8,
            command=command,
        )
