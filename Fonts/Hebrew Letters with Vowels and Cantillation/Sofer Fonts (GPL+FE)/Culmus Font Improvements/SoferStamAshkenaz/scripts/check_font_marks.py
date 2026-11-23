"""Check that every ta'am sits where its class says, in every bundled font that has ta'amim
(fonts/CANTILLATION.md; Mordy, 2026-10-21).  Each ta'am is shaped on a few letters with
HarfBuzz (as Typst lays them out) and its place compared with the letter's: above or below it,
and for the prepositive / postpositive ones at the letter's right / left edge.

    .venv\\Scripts\\python scripts\\check_font_marks.py      (prints problems; exit 1 if any)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import uharfbuzz as hb

REPO = Path(__file__).resolve().parent.parent
FONTS = REPO / "fonts"

ABOVE_LEFT = (0x0599, 0x05A9, 0x05AE)
ABOVE_RIGHT = (0x059D, 0x05A0)
ABOVE = (0x0592, 0x0593, 0x0594, 0x0595, 0x0597, 0x0598, 0x059C, 0x059E, 0x059F, 0x05A1, 0x05A8, 0x05AB, 0x05AC)
BELOW = (0x0591, 0x0596, 0x059B, 0x05A2, 0x05A3, 0x05A4, 0x05A5, 0x05A6, 0x05A7, 0x05AA)
BELOW_RIGHT = (0x059A, 0x05AD)
GROUPS = {"above, left edge": ABOVE_LEFT, "above, right edge": ABOVE_RIGHT, "above": ABOVE,
          "below": BELOW, "below, right edge": BELOW_RIGHT}
LETTERS = "במר"        # a wide letter, a round one, one with a leg


def _shape(font: hb.Font, text: str):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return buf.glyph_infos, buf.glyph_positions


def _ink(font: hb.Font, letter: str, mark: int):
    """(letter's ink box, mark's ink box) as (x0, y0, x1, y1) in font units, placed as HarfBuzz
    places them; None when the font draws the two as one glyph."""
    base_gid = _shape(font, letter)[0][0].codepoint
    infos, positions = _shape(font, letter + chr(mark))
    pen, base, marks = 0, None, []
    for info, pos in zip(infos, positions):
        ext = font.get_glyph_extents(info.codepoint)
        x0 = pen + pos.x_offset + ext.x_bearing
        top = pos.y_offset + ext.y_bearing          # (y_bearing: the top; height: negative, downwards)
        box = (x0, top + ext.height, x0 + ext.width, top)
        if info.codepoint == base_gid and base is None:
            base = box
        else:
            marks.append(box)
        pen += pos.x_advance
    if base is None or len(marks) != 1:
        return None
    return base, marks[0]


def check_font(path: Path) -> list[str]:
    face = hb.Face(hb.Blob.from_file_path(str(path)))
    font = hb.Font(face)
    cmap = set(face.unicodes)
    problems = []
    for group, marks in GROUPS.items():
        for mark in marks:
            if mark not in cmap:
                continue
            for letter in LETTERS:
                got = _ink(font, letter, mark)
                if got is None:
                    continue
                (lx0, ly0, lx1, ly1), (mx0, my0, mx1, my1) = got
                if mx1 <= mx0:
                    continue                    # (an empty mark)
                w, mc = lx1 - lx0, (mx0 + mx1) / 2
                # (above: over the letter's middle - a Sefer Torah letter's crown may stand higher
                #  than a ta'am beside it)
                above = my0 >= ly0 + 0.6 * (ly1 - ly0)
                below = my1 <= max(ly0, 0) + 0.1 * (ly1 - ly0)
                ok = {
                    "above, left edge": above and mc <= lx0 + 0.4 * w,
                    "above, right edge": above and mc >= lx0 + 0.6 * w,
                    "above": above and lx0 - 0.15 * w <= mc <= lx1 + 0.15 * w,
                    "below": below and lx0 - 0.15 * w <= mc <= lx1 + 0.15 * w,
                    "below, right edge": below and mc >= lx0 + 0.6 * w,
                }[group]
                if not ok:
                    problems.append(f"{path.name}: U+{mark:04X} on {letter} is not {group}")
    return problems


def bundled_fonts_with_taamim() -> list[Path]:
    reg = json.loads((FONTS / "fonts.json").read_text(encoding="utf-8"))["fonts"]
    out = []
    for entry in reg.values():
        for key in ("regular", "bold"):
            f = entry.get(key)
            if f and f.lower().endswith((".ttf", ".otf")):
                face = hb.Face(hb.Blob.from_file_path(str(FONTS / f)))
                if 0x0591 in set(face.unicodes):
                    out.append(FONTS / f)
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    problems = [p for f in bundled_fonts_with_taamim() for p in check_font(f)]
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
