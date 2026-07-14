"""
ui/theme.py
Central design token file for Grace v3.
All colours, fonts, sizing, and spacing defined here.
Import from any UI module — never hardcode values elsewhere.
"""

# ── Colour palette ─────────────────────────────────────────────────────────────

BG_BASE      = "#080810"   # deepest background
BG_SURFACE   = "#0e0e1a"   # sidebar, panels
BG_ELEVATED  = "#13131f"   # message bubbles, cards
BG_OVERLAY   = "#1a1a2e"   # hover states, code blocks
BG_INPUT     = "#111120"   # input field background

ACCENT_VIOLET  = "#7c3aed"
ACCENT_PURPLE  = "#9333ea"
ACCENT_INDIGO  = "#4f46e5"
ACCENT_CYAN    = "#06b6d4"
ACCENT_GLOW    = "#a78bfa"

TEXT_PRIMARY   = "#f0eeff"
TEXT_SECONDARY = "#8b8aaa"
TEXT_MUTED     = "#4a4966"
TEXT_CODE      = "#c4b5fd"

BORDER_SUBTLE  = "#1e1e30"
BORDER_DEFAULT = "#2a2a40"
BORDER_BRIGHT  = "#3d3d58"

SUCCESS        = "#34d399"
ERROR          = "#f87171"
WARNING        = "#fbbf24"

# Conversation bubble colours
BUBBLE_USER    = "#1a1040"
BUBBLE_GRACE   = BG_ELEVATED
BUBBLE_USER_BORDER   = "#3b2080"
BUBBLE_GRACE_BORDER  = BORDER_DEFAULT

# Voice orb state colours
ORB_IDLE       = "#7c3aed"
ORB_RECORDING  = "#ef4444"
ORB_SPEAKING   = "#06b6d4"
ORB_THINKING   = "#4f46e5"

# ── Fonts ──────────────────────────────────────────────────────────────────────

FONT_FAMILY       = "Segoe UI"          # Windows; falls back gracefully
FONT_FAMILY_MONO  = "Consolas"          # monospace for code
FONT_FAMILY_TITLE = "Segoe UI Semibold"

FONT_XS    = (FONT_FAMILY, 10)
FONT_SM    = (FONT_FAMILY, 11)
FONT_BASE  = (FONT_FAMILY, 12)
FONT_MD    = (FONT_FAMILY, 13)
FONT_LG    = (FONT_FAMILY, 15)
FONT_XL    = (FONT_FAMILY, 18, "bold")
FONT_2XL   = (FONT_FAMILY_TITLE, 22, "bold")

FONT_MONO_SM   = (FONT_FAMILY_MONO, 11)
FONT_MONO_BASE = (FONT_FAMILY_MONO, 12)
FONT_BOLD      = (FONT_FAMILY, 12, "bold")
FONT_ITALIC    = (FONT_FAMILY, 12, "italic")

# ── Sizing ─────────────────────────────────────────────────────────────────────

WINDOW_W        = 1200
WINDOW_H        = 780
WINDOW_MIN_W    = 800
WINDOW_MIN_H    = 600

SIDEBAR_W       = 240
INPUT_HEIGHT    = 52
TITLEBAR_H      = 42
CORNER_RADIUS   = 10

PAD_XS = 4
PAD_SM = 8
PAD_MD = 12
PAD_LG = 16
PAD_XL = 24

BUBBLE_MAX_WIDTH_FRAC = 0.72   # fraction of chat area width
AVATAR_SIZE = 28
