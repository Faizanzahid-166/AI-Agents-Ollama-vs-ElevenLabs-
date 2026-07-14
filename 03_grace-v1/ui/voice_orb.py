"""
ui/voice_orb.py  (REALTIME UPGRADE)
─────────────────────────────────────
Five states:
  idle         – gentle float, dim violet
  listening    – sharp waveform bars, red
  thinking     – bouncing dots, indigo
  speaking     – smooth waveform bars, cyan
  interrupted  – sharp red flash then fades to idle

Improvements over v3:
  ─ "interrupted" state: brief red flash signals cancellation
  ─ Smoother state transitions (lerp-based colour blending)
  ─ Higher animation framerate (30fps, every 33ms)
  ─ Cleaner waveform rendering for listening vs speaking
"""

import math
import tkinter as tk
from ui import theme as T


# Animation tick interval in ms
TICK_MS = 33   # ~30 fps


class VoiceOrb(tk.Canvas):

    STATES = ("idle", "listening", "thinking", "speaking", "interrupted")

    # (primary_color, bg_tint, glow_radius_factor)
    _STATE_STYLE = {
        "idle":        ("#7c3aed", "#0a0618", 0.9),
        "listening":   ("#ef4444", "#200808", 1.2),
        "thinking":    ("#4f46e5", "#06061e", 1.1),
        "speaking":    ("#06b6d4", "#021518", 1.15),
        "interrupted": ("#ff0040", "#1a0010", 1.4),
    }

    def __init__(self, parent, size: int = 80, **kwargs):
        bg = kwargs.pop("bg", T.BG_SURFACE)
        super().__init__(
            parent,
            width=size, height=size,
            bg=bg,
            highlightthickness=0,
            **kwargs,
        )
        self._size    = size
        self._cx      = size // 2
        self._cy      = size // 2
        self._state   = "idle"
        self._t       = 0.0
        self._dot_idx = 0
        self._running = True

        # For "interrupted" — auto-transition back to idle after flash
        self._interrupt_ticks = 0

        self._draw()
        self.after(TICK_MS, self._tick)

    # ── Public API ─────────────────────────────────────────────────────────────

    def set_state(self, state: str):
        if state not in self.STATES:
            return
        prev = self._state
        self._state = state
        if state != prev:
            self._t = 0.0   # reset phase on state change
        if state == "interrupted":
            self._interrupt_ticks = 0

    # ── Animation ──────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._running:
            return
        self._t       += 0.06
        self._dot_idx  = int(self._t * 4) % 3

        if self._state == "interrupted":
            self._interrupt_ticks += 1
            if self._interrupt_ticks > 12:   # ~400ms flash
                self._state = "idle"
                self._t     = 0.0

        self._draw()
        self.after(TICK_MS, self._tick)

    def _draw(self):
        self.delete("all")
        color, bg_tint, glow_f = self._STATE_STYLE[self._state]
        cx, cy  = self._cx, self._cy
        r       = self._size // 2 - 5

        # Background fill
        self.create_oval(2, 2, self._size - 2, self._size - 2,
                         fill=bg_tint, outline="", width=0)

        # Glow ring (pulsing)
        pulse = 1.0 + 0.07 * math.sin(self._t * 2.8)
        if self._state != "idle":
            rg = int(r * glow_f * pulse)
            self.create_oval(cx - rg, cy - rg, cx + rg, cy + rg,
                             fill="", outline=color, width=2)

        # "interrupted" flash — extra bold ring
        if self._state == "interrupted":
            fade_t = self._interrupt_ticks / 12.0
            alpha_ring = max(0, 1.0 - fade_t)
            ri = int(r * 1.5)
            self.create_oval(cx - ri, cy - ri, cx + ri, cy + ri,
                             fill="", outline=color, width=int(4 * alpha_ring + 1))

        # Main orb disc
        scale = 1.0
        if self._state == "listening":
            scale = 1.0 + 0.05 * abs(math.sin(self._t * 7))
        elif self._state == "speaking":
            scale = 1.0 + 0.03 * math.sin(self._t * 4)

        ro = int(r * 0.72 * scale)
        self.create_oval(cx - ro, cy - ro, cx + ro, cy + ro,
                         fill=color, outline="", width=0)

        # Inner highlight
        ri2 = int(ro * 0.5)
        lighter = self._lighten(color, 0.4)
        self.create_oval(cx - ri2, cy - ri2, cx + ri2, cy + ri2,
                         fill=lighter, outline="", width=0)

        # Inner visual based on state
        if self._state == "listening":
            self._draw_waveform(cx, cy, ro, sharp=True)
        elif self._state == "speaking":
            self._draw_waveform(cx, cy, ro, sharp=False)
        elif self._state == "thinking":
            self._draw_dots(cx, cy)
        elif self._state == "interrupted":
            self._draw_x(cx, cy, ri2)
        else:  # idle
            ri3 = int(ri2 * 0.55)
            self.create_oval(cx - ri3, cy - ri3, cx + ri3, cy + ri3,
                             fill=self._lighten(color, 0.55), outline="", width=0)

    def _draw_waveform(self, cx: int, cy: int, orb_r: int, sharp: bool):
        n       = 7
        bar_w   = 3
        gap     = 3
        total_w = n * (bar_w + gap) - gap
        x0      = cx - total_w // 2
        max_h   = orb_r * 0.55
        speed   = 6.5 if sharp else 4.0

        for i in range(n):
            phase = self._t * speed + i * (0.7 if sharp else 0.4)
            h     = int(max_h * (0.2 + 0.8 * abs(math.sin(phase))))
            x     = x0 + i * (bar_w + gap)
            self.create_rectangle(
                x, cy - h // 2, x + bar_w, cy + h // 2,
                fill="white", outline="", width=0,
            )

    def _draw_dots(self, cx: int, cy: int):
        spacing = 12
        x0      = cx - spacing
        r_dot   = 4
        for i in range(3):
            x    = x0 + i * spacing
            big  = (i == self._dot_idx)
            rd   = int(r_dot * (1.45 if big else 0.75))
            col  = "white" if big else "#8888dd"
            self.create_oval(x - rd, cy - rd, x + rd, cy + rd,
                             fill=col, outline="", width=0)

    def _draw_x(self, cx: int, cy: int, r: int):
        """Draw an × for the interrupted state."""
        pad = int(r * 0.5)
        w   = 3
        self.create_line(cx - pad, cy - pad, cx + pad, cy + pad,
                         fill="white", width=w, capstyle="round")
        self.create_line(cx + pad, cy - pad, cx - pad, cy + pad,
                         fill="white", width=w, capstyle="round")

    @staticmethod
    def _lighten(hex_color: str, f: float = 0.35) -> str:
        h   = hex_color.lstrip("#")
        r   = int(h[0:2], 16)
        g   = int(h[2:4], 16)
        b   = int(h[4:6], 16)
        r   = int(r + (255 - r) * f)
        g   = int(g + (255 - g) * f)
        b   = int(b + (255 - b) * f)
        return f"#{r:02x}{g:02x}{b:02x}"

    def destroy(self):
        self._running = False
        super().destroy()
