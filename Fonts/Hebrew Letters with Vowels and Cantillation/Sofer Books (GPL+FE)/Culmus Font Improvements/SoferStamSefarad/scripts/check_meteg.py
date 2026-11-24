"""Every meteg of the siddur (as Sofer prints it, with its metegs - tanach_marks.py) and of the
Tanach, shaped with HarfBuzz as Typst lays it out, in each font: does the meteg touch, or come
closer than CLEAR to, anything - its vowel, a ta'am, the letter's own leg, the next letter's
marks?  (Mordy, 2026-10-25: "check for collisions with the meteg".)

    .venv/Scripts/python scripts/check_meteg.py [font files ...]   (default: Frank Ruehl and Frank Sofer)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.pointInsidePen import PointInsidePen
from fontTools.ttLib import TTFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
FONTS = REPO / "fonts"
DATA = REPO / "data" / "sefaria-export"
CLEAR = 0.012          # (of the em: nearer than this is touching, to the eye)
STEP = 0.008           # (of the em: the grid the ink is read on)
_WORD = re.compile("[א-ת][֑-׉א-ת͏ﬞ]*")


def siddur_words() -> Counter:
    from sofer import word_layout
    folder = word_layout.folder_for(DATA) / "siddur-edot-hamizrach"
    sections = word_layout.with_reading_marks(word_layout.from_wikisource(folder), DATA)
    out = Counter()
    for sec in sections:
        for it in sec.items:
            paras = [it] if it[0] == "p" else it[2] if it[0] == "cols" else []
            for p in paras:
                for w in _WORD.findall("".join(r[0] for r in p[2])):
                    if "ֽ" in w:
                        out[w] += 1
    return out


def tanach_words() -> Counter:
    out = Counter()
    for f in DATA.glob("json/Tanakh/**/Hebrew/Miqra according to the Masorah.json"):
        def leaves(x):
            if isinstance(x, str):
                yield x
            elif isinstance(x, list):
                for y in x:
                    yield from leaves(y)
        for s in leaves(json.loads(f.read_text(encoding="utf-8"))["text"]):
            for w in _WORD.findall(re.sub(r"<[^>]+>|&[a-z]+;", " ", s)):
                if "ֽ" in w:
                    out[w] += 1
    return out


class Ink:
    """Each glyph's ink as grid cells (font units / step), read once."""

    def __init__(self, path: Path):
        self.t = TTFont(path)
        self.gs = self.t.getGlyphSet()
        self.order = self.t.getGlyphOrder()
        self.upem = self.t["head"].unitsPerEm
        self.step = max(4, round(STEP * self.upem))
        self.cache = {}

    def cells(self, gid: int) -> set:
        if gid in self.cache:
            return self.cache[gid]
        name = self.order[gid]
        g = self.t["glyf"][name] if "glyf" in self.t else None
        out = set()
        if g is not None and getattr(g, "numberOfContours", 0):
            g.recalcBounds(self.t["glyf"])
            s = self.step
            for y in range(g.yMin // s, g.yMax // s + 1):
                for x in range(g.xMin // s, g.xMax // s + 1):
                    pen = PointInsidePen(self.gs, (x * s + s / 2, y * s + s / 2))
                    self.gs[name].draw(pen)
                    if pen.getResult():
                        out.add((x, y))
        self.cache[gid] = out
        return out


def check(path: Path, words: Counter) -> tuple[int, int, list]:
    face = hb.Face(hb.Blob(path.read_bytes()))
    font = hb.Font(face)
    ink = Ink(path)
    meteg = font.get_nominal_glyph(0x05BD)
    near = max(1, round(CLEAR * ink.upem / ink.step))
    bad, bad_n, seen = [], 0, 0
    for w, n in words.most_common():
        buf = hb.Buffer()
        buf.add_str(w)
        buf.guess_segment_properties()
        hb.shape(font, buf)
        placed, pen = [], 0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            dx, dy = (pen + pos.x_offset) // ink.step, pos.y_offset // ink.step
            placed.append((info.codepoint, {(x + dx, y + dy) for x, y in ink.cells(info.codepoint)}))
            pen += pos.x_advance
        others = set()
        for gid, cells in placed:
            if gid != meteg:
                others |= cells
        grown = {(x + a, y + b) for x, y in others for a in range(-near, near + 1) for b in range(-near, near + 1)}
        seen += n
        if any(cells & grown for gid, cells in placed if gid == meteg):
            bad.append((w, n))
            bad_n += n
    return seen, bad_n, bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    fonts = sys.argv[1:] or ["FrankRuehlCLM-Medium.ttf", "FrankSofer.ttf"]
    words = siddur_words()
    words.update(tanach_words())
    print(f"{len(words):,} different words with a meteg ({sum(words.values()):,} in all)")
    for f in fonts:
        seen, bad_n, bad = check(FONTS / f, words)
        print(f"{f}: {bad_n:,} of {seen:,} metegs touch something ({len(bad)} different words)")
        for w, n in bad[:25]:
            print(f"   {w} ({n})")
