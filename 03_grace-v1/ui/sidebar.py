"""
ui/sidebar.py
Left sidebar: conversation list, new chat button, mode toggle.
Communicates with the parent app via callback functions.
"""

import tkinter as tk
import customtkinter as ctk
from ui import theme as T
from typing import Callable, List, Dict, Optional


class Sidebar(ctk.CTkFrame):

    def __init__(
        self,
        parent,
        on_new_chat: Callable,
        on_select_conv: Callable[[str], None],
        on_delete_conv: Callable[[str], None],
        on_mode_change: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(
            parent,
            width=T.SIDEBAR_W,
            fg_color=T.BG_SURFACE,
            corner_radius=0,
            border_width=0,
            **kwargs,
        )
        self.pack_propagate(False)

        self._on_new_chat = on_new_chat
        self._on_select = on_select_conv
        self._on_delete = on_delete_conv
        self._on_mode_change = on_mode_change
        self._mode = "chat"
        self._selected_id: Optional[str] = None
        self._conv_buttons: Dict[str, ctk.CTkFrame] = {}

        self._build()

    def _build(self):
        # ── Header ────────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=T.TITLEBAR_H)
        hdr.pack(fill="x", padx=T.PAD_MD, pady=(T.PAD_MD, T.PAD_XS))
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="✦ Grace",
            font=ctk.CTkFont(family=T.FONT_FAMILY_TITLE, size=16, weight="bold"),
            text_color=T.ACCENT_GLOW,
            anchor="w",
        ).pack(side="left", padx=(T.PAD_XS, 0))

        # ── Mode toggle ───────────────────────────────────────────────────────
        mode_frame = ctk.CTkFrame(self, fg_color=T.BG_OVERLAY, corner_radius=T.CORNER_RADIUS)
        mode_frame.pack(fill="x", padx=T.PAD_MD, pady=T.PAD_XS)

        self._chat_btn = ctk.CTkButton(
            mode_frame, text="💬 Chat",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=11),
            height=30, corner_radius=8,
            command=lambda: self._switch_mode("chat"),
        )
        self._chat_btn.pack(side="left", expand=True, fill="x", padx=(T.PAD_XS, 2), pady=T.PAD_XS)

        self._code_btn = ctk.CTkButton(
            mode_frame, text="</> Code",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=11),
            height=30, corner_radius=8,
            command=lambda: self._switch_mode("code"),
        )
        self._code_btn.pack(side="left", expand=True, fill="x", padx=(2, T.PAD_XS), pady=T.PAD_XS)
        self._update_mode_btns()

        # ── New chat button ────────────────────────────────────────────────────
        ctk.CTkButton(
            self,
            text="＋  New conversation",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=12),
            height=36,
            fg_color=T.BG_ELEVATED,
            hover_color=T.BG_OVERLAY,
            text_color=T.TEXT_SECONDARY,
            border_color=T.BORDER_DEFAULT,
            border_width=1,
            corner_radius=T.CORNER_RADIUS,
            command=self._on_new_chat,
        ).pack(fill="x", padx=T.PAD_MD, pady=(T.PAD_XS, T.PAD_SM))

        # ── Divider ───────────────────────────────────────────────────────────
        ctk.CTkFrame(self, height=1, fg_color=T.BORDER_SUBTLE).pack(fill="x", padx=T.PAD_MD)

        # ── Conversation list label ───────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="RECENT",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=9, weight="bold"),
            text_color=T.TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", padx=T.PAD_LG, pady=(T.PAD_MD, T.PAD_XS))

        # ── Scrollable conversation list ──────────────────────────────────────
        self._list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=T.BORDER_DEFAULT,
            scrollbar_button_hover_color=T.BORDER_BRIGHT,
            corner_radius=0,
        )
        self._list_frame.pack(fill="both", expand=True, padx=T.PAD_XS)

        # ── Footer ────────────────────────────────────────────────────────────
        ctk.CTkLabel(
            self,
            text="Grace v3 · Local AI",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=9),
            text_color=T.TEXT_MUTED,
        ).pack(pady=T.PAD_SM)

    # ── Public API ─────────────────────────────────────────────────────────────

    def load_conversations(self, convs: List[Dict]):
        """Rebuild the conversation list from a list of {id, title, mode} dicts."""
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._conv_buttons.clear()

        if not convs:
            ctk.CTkLabel(
                self._list_frame,
                text="No conversations yet",
                font=ctk.CTkFont(family=T.FONT_FAMILY, size=11),
                text_color=T.TEXT_MUTED,
            ).pack(pady=T.PAD_XL)
            return

        for conv in convs:
            self._add_conv_row(conv)

    def add_conversation(self, conv: Dict):
        """Prepend a new conversation to the top of the list."""
        self._add_conv_row(conv, prepend=True)

    def update_title(self, conv_id: str, title: str):
        if conv_id in self._conv_buttons:
            row = self._conv_buttons[conv_id]
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("anchor") == "w":
                    child.configure(text=title[:40])
                    break

    def select(self, conv_id: str):
        self._selected_id = conv_id
        self._refresh_selection()

    def get_mode(self) -> str:
        return self._mode

    # ── Internal ──────────────────────────────────────────────────────────────

    def _add_conv_row(self, conv: Dict, prepend: bool = False):
        icon = "⌨" if conv.get("mode") == "code" else "💬"
        title = conv.get("title", "New conversation")[:36]
        conv_id = conv["id"]

        row = ctk.CTkFrame(
            self._list_frame,
            fg_color="transparent",
            corner_radius=8,
            cursor="hand2",
        )
        if prepend:
            row.pack(fill="x", padx=T.PAD_XS, pady=1, before=self._list_frame.winfo_children()[0] if self._list_frame.winfo_children() else None)
        else:
            row.pack(fill="x", padx=T.PAD_XS, pady=1)

        # Click area
        inner = ctk.CTkFrame(row, fg_color="transparent", corner_radius=8, cursor="hand2")
        inner.pack(fill="x")
        inner.bind("<Button-1>", lambda e, cid=conv_id: self._select_conv(cid))
        inner.bind("<Enter>", lambda e, r=row: self._hover_on(r))
        inner.bind("<Leave>", lambda e, r=row, cid=conv_id: self._hover_off(r, cid))

        ctk.CTkLabel(
            inner,
            text=f"{icon}",
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=12),
            text_color=T.ACCENT_GLOW if conv.get("mode") == "code" else T.TEXT_MUTED,
            width=20,
            anchor="center",
        ).pack(side="left", padx=(T.PAD_SM, T.PAD_XS), pady=T.PAD_SM)

        ctk.CTkLabel(
            inner,
            text=title,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=11),
            text_color=T.TEXT_SECONDARY,
            anchor="w",
        ).pack(side="left", fill="x", expand=True, pady=T.PAD_SM)

        # Delete button (hidden until hover)
        del_btn = ctk.CTkButton(
            inner,
            text="✕",
            width=22, height=22,
            font=ctk.CTkFont(family=T.FONT_FAMILY, size=10),
            fg_color="transparent",
            hover_color=T.BG_OVERLAY,
            text_color=T.TEXT_MUTED,
            corner_radius=4,
            command=lambda cid=conv_id: self._delete_conv(cid),
        )
        del_btn.pack(side="right", padx=T.PAD_XS)
        del_btn.pack_forget()   # hidden by default

        row._del_btn = del_btn
        self._conv_buttons[conv_id] = row
        self._refresh_selection()

    def _select_conv(self, conv_id: str):
        self._selected_id = conv_id
        self._refresh_selection()
        self._on_select(conv_id)

    def _delete_conv(self, conv_id: str):
        if conv_id in self._conv_buttons:
            self._conv_buttons[conv_id].destroy()
            del self._conv_buttons[conv_id]
        self._on_delete(conv_id)

    def _hover_on(self, row):
        row.configure(fg_color=T.BG_OVERLAY)
        if hasattr(row, "_del_btn"):
            row._del_btn.pack(side="right", padx=T.PAD_XS)

    def _hover_off(self, row, conv_id):
        is_sel = (conv_id == self._selected_id)
        row.configure(fg_color=T.BG_ELEVATED if is_sel else "transparent")
        if hasattr(row, "_del_btn") and not is_sel:
            row._del_btn.pack_forget()

    def _refresh_selection(self):
        for cid, row in self._conv_buttons.items():
            row.configure(fg_color=T.BG_ELEVATED if cid == self._selected_id else "transparent")

    def _switch_mode(self, mode: str):
        self._mode = mode
        self._update_mode_btns()
        self._on_mode_change(mode)

    def _update_mode_btns(self):
        active_fg    = T.ACCENT_VIOLET
        inactive_fg  = "transparent"
        active_text  = T.TEXT_PRIMARY
        inactive_text = T.TEXT_MUTED

        if self._mode == "chat":
            self._chat_btn.configure(fg_color=active_fg,   text_color=active_text)
            self._code_btn.configure(fg_color=inactive_fg, text_color=inactive_text)
        else:
            self._chat_btn.configure(fg_color=inactive_fg, text_color=inactive_text)
            self._code_btn.configure(fg_color=active_fg,   text_color=active_text)
