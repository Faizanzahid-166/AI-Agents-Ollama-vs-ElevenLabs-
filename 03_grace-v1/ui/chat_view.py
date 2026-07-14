"""
ui/chat_view.py
Scrollable chat message area.
Manages the list of MessageBubble widgets and handles live token appending.
"""

import tkinter as tk
import customtkinter as ctk
from ui import theme as T
from ui.message_bubble import MessageBubble
from datetime import datetime


def _fmt_time(ts) -> str:
    """Format a timestamp to a short human-readable string."""
    if ts is None:
        return ""
    try:
        if isinstance(ts, str):
            # Parse ISO string
            from datetime import timezone
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            dt = dt.astimezone()
        else:
            dt = ts
        return dt.strftime("%-I:%M %p") if hasattr(dt, 'strftime') else ""
    except Exception:
        return ""


class ChatView(ctk.CTkScrollableFrame):
    """
    Vertically scrollable container for all message bubbles.
    """

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            fg_color=T.BG_BASE,
            scrollbar_button_color=T.BORDER_DEFAULT,
            scrollbar_button_hover_color=T.BORDER_BRIGHT,
            corner_radius=0,
            **kwargs,
        )
        self._bubbles: list[MessageBubble] = []
        self._streaming_bubble: MessageBubble | None = None

        # Welcome message
        self._show_welcome()

    # ── Public API ─────────────────────────────────────────────────────────────

    def add_message(self, role: str, content: str, timestamp=None) -> MessageBubble:
        """Add a complete message bubble to the view."""
        self._hide_welcome()
        bubble = MessageBubble(
            self,
            role=role,
            content=content,
            timestamp=_fmt_time(timestamp),
        )
        bubble.pack(fill="x", pady=(0, T.PAD_SM))
        self._bubbles.append(bubble)
        self._scroll_bottom()
        return bubble

    def start_streaming(self) -> MessageBubble:
        """
        Add an empty assistant bubble that tokens will be appended to.
        Returns the bubble so the caller can keep a reference.
        """
        self._hide_welcome()
        bubble = MessageBubble(self, role="assistant", content="")
        bubble.pack(fill="x", pady=(0, T.PAD_SM))
        self._bubbles.append(bubble)
        self._streaming_bubble = bubble
        self._scroll_bottom()
        return bubble

    def append_token(self, token: str):
        """Append a streaming token to the current streaming bubble."""
        if self._streaming_bubble:
            self._streaming_bubble.append_token(token)
            self._scroll_bottom()

    def finalize_streaming(self):
        """Mark streaming as complete and re-render with full markdown."""
        if self._streaming_bubble:
            self._streaming_bubble.finalize()
            self._streaming_bubble = None

    def add_system_message(self, text: str):
        bubble = MessageBubble(self, role="system", content=text)
        bubble.pack(fill="x", pady=T.PAD_XS)
        self._scroll_bottom()

    def clear(self):
        """Remove all messages from the view."""
        for b in self._bubbles:
            b.destroy()
        self._bubbles.clear()
        self._streaming_bubble = None
        self._show_welcome()

    def load_messages(self, messages: list):
        """Populate view from a list of {role, content, timestamp} dicts."""
        self.clear()
        if not messages:
            return
        self._hide_welcome()
        for m in messages:
            self.add_message(m["role"], m["content"], m.get("timestamp"))

    # ── Welcome screen ─────────────────────────────────────────────────────────

    _welcome_frame: tk.Frame | None = None  # type: ignore

    def _show_welcome(self):
        if hasattr(self, "_wframe") and self._wframe:
            return
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(expand=True, pady=80, padx=40)

        # Orb preview
        from ui.voice_orb import VoiceOrb
        orb = VoiceOrb(frame, size=72)
        orb.configure(bg=T.BG_BASE)
        orb.pack(pady=(0, T.PAD_LG))

        ctk.CTkLabel(
            frame,
            text="Hey, I'm Grace 👋",
            font=ctk.CTkFont(family=T.FONT_FAMILY_TITLE, size=26, weight="bold"),
            text_color=T.TEXT_PRIMARY,
        ).pack()

        ctk.CTkLabel(
            frame,
            text="Your AI bestie for coding, life advice, and great conversation.\nWhat's on your mind?",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=13),
            text_color=T.TEXT_SECONDARY,
            justify="center",
        ).pack(pady=(T.PAD_SM, T.PAD_XL))

        # Suggestion chips
        chips_frame = ctk.CTkFrame(frame, fg_color="transparent")
        chips_frame.pack()
        chips = ["🐛 Debug my code", "💡 Explain async/await", "😄 Tell me a joke", "🎯 Help me focus"]
        for i, chip in enumerate(chips):
            col = i % 2
            row = i // 2
            btn = ctk.CTkButton(
                chips_frame,
                text=chip,
                font=ctk.CTkFont(family=T.FONT_FAMILY, size=12),
                fg_color=T.BG_ELEVATED,
                hover_color=T.BG_OVERLAY,
                text_color=T.TEXT_SECONDARY,
                border_color=T.BORDER_DEFAULT,
                border_width=1,
                corner_radius=T.CORNER_RADIUS,
                command=lambda c=chip: self._on_chip(c),
            )
            btn.grid(row=row, column=col, padx=T.PAD_SM, pady=T.PAD_XS, sticky="ew")

        self._wframe = frame

    def _hide_welcome(self):
        if hasattr(self, "_wframe") and self._wframe:
            self._wframe.destroy()
            self._wframe = None

    def _on_chip(self, chip: str):
        """Fire suggestion chip — post to parent app via event."""
        self.event_generate("<<SuggestionChip>>", data=chip)

    def _scroll_bottom(self):
        self.after(20, lambda: self._parent_canvas_scroll())

    def _parent_canvas_scroll(self):
        try:
            self._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass
