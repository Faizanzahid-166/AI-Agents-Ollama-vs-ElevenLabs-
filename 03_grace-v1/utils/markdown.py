"""
utils/markdown.py
Very lightweight markdown parser that produces a list of (text, tags) tuples
suitable for inserting into a tkinter Text widget with tag_add().

Supported:
  **bold**, *italic*, `inline code`,
  # headers, ```code blocks```, - bullet lists
"""

import re
from typing import List, Tuple

# Each item: (text_to_insert, list_of_tag_names)
Segment = Tuple[str, List[str]]


def parse(text: str) -> List[Segment]:
    """Parse markdown text into a list of (text, tags) segments."""
    segments: List[Segment] = []
    lines = text.split("\n")
    in_code_block = False
    code_block_lines = []

    for line in lines:
        # ── Fenced code block ─────────────────────────────────────────────────
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_block_lines = []
                lang = line.strip()[3:].strip()
                continue
            else:
                # Close code block
                in_code_block = False
                code_text = "\n".join(code_block_lines)
                segments.append((code_text + "\n", ["code_block"]))
                continue

        if in_code_block:
            code_block_lines.append(line)
            continue

        # ── Heading ───────────────────────────────────────────────────────────
        if line.startswith("### "):
            _parse_inline(line[4:], segments, base_tags=["h3"])
            segments.append(("\n", []))
            continue
        if line.startswith("## "):
            _parse_inline(line[3:], segments, base_tags=["h2"])
            segments.append(("\n", []))
            continue
        if line.startswith("# "):
            _parse_inline(line[2:], segments, base_tags=["h1"])
            segments.append(("\n", []))
            continue

        # ── Bullet list item ──────────────────────────────────────────────────
        if re.match(r"^[\-\*] ", line):
            segments.append(("  • ", ["bullet"]))
            _parse_inline(line[2:], segments)
            segments.append(("\n", []))
            continue

        # ── Numbered list ─────────────────────────────────────────────────────
        m = re.match(r"^(\d+)\. (.+)", line)
        if m:
            segments.append((f"  {m.group(1)}. ", ["bullet"]))
            _parse_inline(m.group(2), segments)
            segments.append(("\n", []))
            continue

        # ── Normal line ───────────────────────────────────────────────────────
        if line == "":
            segments.append(("\n", []))
        else:
            _parse_inline(line, segments)
            segments.append(("\n", []))

    return segments


def _parse_inline(text: str, out: List[Segment], base_tags: List[str] = None):
    """
    Parse inline markdown (bold, italic, inline code) and append to out.
    """
    base = base_tags or []
    # Tokenise by inline patterns
    # Order matters: code first, then bold, then italic
    pattern = re.compile(
        r"(`[^`]+`)"            # inline code
        r"|(\*\*[^*]+\*\*)"    # bold
        r"|(\*[^*]+\*)"        # italic
        r"|([^`*]+)"           # plain text
    )
    for m in pattern.finditer(text):
        if m.group(1):  # inline code
            out.append((m.group(1)[1:-1], base + ["inline_code"]))
        elif m.group(2):  # bold
            out.append((m.group(2)[2:-2], base + ["bold"]))
        elif m.group(3):  # italic
            out.append((m.group(3)[1:-1], base + ["italic"]))
        elif m.group(4):  # plain
            out.append((m.group(4), base))
