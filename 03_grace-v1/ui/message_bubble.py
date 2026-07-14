"""
ui/message_bubble.py
A CustomTkinter frame that renders a single chat message.
Supports markdown text formatting via a tk.Text widget with tags.
"""

import tkinter as tk
import customtkinter as ctk
from ui import theme as T
from utils.markdown import parse as md_parse


class MessageBubble(ctk.CTkFrame):
    """
    Single message bubble.
    role: "user" | "assistant" | "system"
    """

    def __init__(self, parent, role: str, content: str, timestamp: str = "", **kwargs):
        is_user = role == "user"
        is_system = role == "system"

        bg = T.BUBBLE_USER if is_user else T.BUBBLE_GRACE
        border = T.BUBBLE_USER_BORDER if is_user else T.BUBBLE_GRACE_BORDER

        super().__init__(
            parent,
            fg_color=T.BG_BASE,   # transparent outer frame
            corner_radius=0,
            **kwargs,
        )

        if is_system:
            self._build_system(content)
            return

        # ── Outer row ──────────────────────────────────────────────────────────
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_SM, 0))

        if is_user:
            row.columnconfigure(0, weight=1)
            row.columnconfigure(1, weight=0)
        else:
            row.columnconfigure(0, weight=0)
            row.columnconfigure(1, weight=1)

        # Avatar
        av_col = 1 if is_user else 0
        av_label = ctk.CTkLabel(
            row,
            text="U" if is_user else "G",
            width=T.AVATAR_SIZE,
            height=T.AVATAR_SIZE,
            corner_radius=T.AVATAR_SIZE // 2,
            fg_color=T.ACCENT_VIOLET if is_user else T.ACCENT_INDIGO,
            text_color=T.TEXT_PRIMARY,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=11, weight="bold"),
        )
        av_label.grid(row=0, column=av_col, padx=(0, T.PAD_SM) if is_user else (0, T.PAD_SM), sticky="n", pady=(2, 0))

        # Bubble card
        bubble_col = 0 if is_user else 1
        bubble_card = ctk.CTkFrame(
            row,
            fg_color=bg,
            corner_radius=T.CORNER_RADIUS,
            border_width=1,
            border_color=border,
        )
        bubble_card.grid(row=0, column=bubble_col, sticky="ew", padx=(T.PAD_SM, 0) if is_user else (0, T.PAD_SM))

        # Text widget for rich markdown rendering
        self._text_widget = self._make_text_widget(bubble_card)
        self._text_widget.pack(padx=T.PAD_MD, pady=T.PAD_SM, fill="both", expand=True)
        self._apply_content(content)

        # Timestamp
        if timestamp:
            ts_label = ctk.CTkLabel(
                self,
                text=timestamp,
                font=ctk.CTkFont(family=T.FONT_FAMILY, size=9),
                text_color=T.TEXT_MUTED,
            )
            ts_label.pack(
                anchor="e" if is_user else "w",
                padx=T.PAD_XL + T.AVATAR_SIZE,
                pady=(0, T.PAD_XS),
            )

        self._role = role

    def _build_system(self, content: str):
        label = ctk.CTkLabel(
            self,
            text=content,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=10),
            text_color=T.TEXT_MUTED,
            fg_color=T.BG_OVERLAY,
            corner_radius=T.CORNER_RADIUS,
            padx=T.PAD_MD,
            pady=T.PAD_XS,
        )
        label.pack(padx=T.PAD_XL, pady=T.PAD_SM)

    def _make_text_widget(self, parent) -> tk.Text:
        widget = tk.Text(
            parent,
            wrap="word",
            bg=T.BUBBLE_USER if self._parent_is_user(parent) else T.BUBBLE_GRACE,
            fg=T.TEXT_PRIMARY,
            font=T.FONT_BASE,
            insertbackground=T.ACCENT_GLOW,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            cursor="arrow",
            state="disabled",
            padx=0,
            pady=0,
        )
        # Configure tags
        widget.tag_config("bold",       font=T.FONT_BOLD)
        widget.tag_config("italic",     font=T.FONT_ITALIC)
        widget.tag_config("h1",         font=(T.FONT_FAMILY, 18, "bold"), foreground=T.TEXT_PRIMARY)
        widget.tag_config("h2",         font=(T.FONT_FAMILY, 15, "bold"), foreground=T.TEXT_PRIMARY)
        widget.tag_config("h3",         font=(T.FONT_FAMILY, 13, "bold"), foreground=T.TEXT_SECONDARY)
        widget.tag_config("inline_code",font=T.FONT_MONO_SM, foreground=T.TEXT_CODE, background=T.BG_OVERLAY)
        widget.tag_config("code_block", font=T.FONT_MONO_SM, foreground=T.TEXT_CODE,
                          background=T.BG_OVERLAY, lmargin1=8, lmargin2=8, rmargin=8,
                          spacing1=6, spacing3=6)
        widget.tag_config("bullet",     foreground=T.ACCENT_GLOW)
        return widget

    def _parent_is_user(self, parent) -> bool:
        """Peek at parent to determine bubble type — used for bg colour."""
        try:
            return parent.cget("fg_color") == T.BUBBLE_USER
        except Exception:
            return False

    def _apply_content(self, content: str):
        """Render markdown content into the text widget."""
        widget = self._text_widget
        widget.configure(state="normal")
        widget.delete("1.0", "end")

        segments = md_parse(content)
        for text, tags in segments:
            if tags:
                widget.insert("end", text, tuple(tags))
            else:
                widget.insert("end", text)

        # Measure height — limit to ~20 lines
        widget.update_idletasks()
        lines = int(widget.index("end-1c").split(".")[0])
        widget.configure(height=min(lines, 40), state="disabled")

    def append_token(self, token: str):
        """Stream a new token into this bubble (assistant only)."""
        widget = self._text_widget
        widget.configure(state="normal")
        widget.insert("end", token)
        widget.see("end")
        lines = int(widget.index("end-1c").split(".")[0])
        widget.configure(height=min(lines + 1, 40))
        widget.configure(state="disabled")

    def finalize(self):
        """Called when streaming is complete — re-render with full markdown."""
        widget = self._text_widget
        widget.configure(state="normal")
        content = widget.get("1.0", "end-1c")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")
        self._apply_content(content)
