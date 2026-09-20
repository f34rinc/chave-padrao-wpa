#!/usr/bin/env python3
"""Render chave_padrao.py's interactive launcher panel into a self-contained SVG
'terminal screenshot' for the README.

Runs the tool's own _panel() with colour ON, captures the real ANSI output, and turns
it into a static SVG that renders inline on GitHub (no image host, no external assets).
The panel is pure UI -- title, drop hint, options, and the Mode/saving/fresh/hashcat
line -- so there is NOTHING sensitive in it (no BSSIDs, MACs, keys, or capture paths).
Regenerate whenever the panel text or palette changes:

    python scripts/render_panel_svg.py        # writes docs/terminal.svg
"""
import io
import os
import re
import sys
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import chave_padrao as k  # noqa: E402

OUT = os.path.join(ROOT, "docs", "terminal.svg")

# ---- dark-terminal palette (maps the tool's ANSI codes to hex) --------------
FG_DEFAULT = "#c9d1d9"
FG_BOLD    = "#e6edf3"
GRAY       = "#768390"                         # the tool's dim == ESC[90m (bright black)
COLORS = {"31": "#f47067", "32": "#57ab5a", "33": "#e3b341", "36": "#39c5cf"}

FS, CHARW, LINEH = 13, 7.81, 20
PADX, PADTOP, PADBOT, TITLEH = 20, 14, 18, 34
FONT = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"


def capture_panel():
    """The real launcher panel, colour on, with representative (non-sensitive) settings."""
    k.C = k._Palette(True)
    k.SAVE_CRACKS = True
    k.FRESH_POTFILE = None
    buf = io.StringIO()
    with redirect_stdout(buf):
        k._panel("ask", exe="hashcat")         # 'ask' = default mode; exe truthy -> "found"
    return buf.getvalue().rstrip("\n") + "\n> █"


def parse_ansi(text):
    state = {"fg": FG_DEFAULT, "bold": False}
    lines, cur = [], []
    for tok in re.split(r"(\x1b\[[0-9;]*m)", text):
        if not tok:
            continue
        if tok.startswith("\x1b["):
            for code in tok[2:-1].split(";"):
                if code in ("", "0"):
                    state.update(fg=FG_DEFAULT, bold=False)
                elif code == "1":
                    state["bold"] = True
                elif code == "90":
                    state["fg"] = GRAY
                elif code in COLORS:
                    state["fg"] = COLORS[code]
            continue
        parts = tok.split("\n")
        for i, part in enumerate(parts):
            if i:
                lines.append(cur)
                cur = []
            if part:
                cur.append((part, dict(state)))
    lines.append(cur)
    return lines


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_svg(lines):
    maxlen = max((sum(len(t) for t, _ in ln) for ln in lines), default=40)
    width = round(PADX * 2 + maxlen * CHARW)
    height = round(TITLEH + PADTOP + len(lines) * LINEH + PADBOT)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{FONT}" font-size="{FS}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="#1c2128" stroke="#30363d"/>',
        f'<rect x="1" y="1" width="{width - 2}" height="{TITLEH}" rx="9" fill="#161b22"/>',
        f'<rect x="1" y="{TITLEH - 9}" width="{width - 2}" height="10" fill="#161b22"/>',
        f'<line x1="0" y1="{TITLEH}" x2="{width}" y2="{TITLEH}" stroke="#30363d"/>',
    ]
    for cx, col in ((18, "#ff5f56"), (38, "#ffbd2e"), (58, "#27c93f")):
        out.append(f'<circle cx="{cx}" cy="{TITLEH // 2}" r="6" fill="{col}"/>')
    out.append(f'<text x="{width // 2}" y="{TITLEH // 2 + 4}" text-anchor="middle" '
               f'fill="{GRAY}" font-size="12">python chave_padrao.py</text>')

    for row, runs in enumerate(lines):
        y = TITLEH + PADTOP + (row + 1) * LINEH - 5
        spans = []
        for txt, s in runs:
            fill = (FG_BOLD if s["bold"] else FG_DEFAULT) if s["fg"] == FG_DEFAULT else s["fg"]
            attrs = f'fill="{fill}"' + (' font-weight="700"' if s["bold"] else "")
            spans.append(f'<tspan {attrs}>{esc(txt)}</tspan>')
        out.append(f'<text x="{PADX}" y="{y}" xml:space="preserve">{"".join(spans)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    svg = to_svg(parse_ansi(capture_panel()))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {OUT}  ({len(svg):,} bytes)")


if __name__ == "__main__":
    main()
