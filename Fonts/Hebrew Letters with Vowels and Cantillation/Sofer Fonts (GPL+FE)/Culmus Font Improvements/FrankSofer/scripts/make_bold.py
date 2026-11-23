"""A bold weight for a font that has none (Mordy, 2026-10-26: "make bold for Frank Sofer"): every
outline thickened, as FreeType's emboldening does - each point moved out along the bisector of its
two edges' normals, so the strokes grow evenly on every side - letters by STRENGTH (of the em),
widened by as much, their outlines moved right by half of it; marks a little less, in place.

    python scripts/make_bold.py fonts/FrankSofer.ttf      ->  fonts/FrankSofer-Bold.ttf
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

STRENGTH = 0.034          # (of the em, in all: Frank Ruehl's bold is about this much heavier)
STRENGTH_Y = 0.024        # (less up and down: the letters' height kept close)
MARKS = 0.6               # (marks: this share of it)


def _embolden(coords, ends, sx, sy):
    out = list(coords)
    start = 0
    for end in ends:
        pts = coords[start:end + 1]
        n = len(pts)
        for i in range(n):
            p = pts[i]
            j = (i - 1) % n
            while j != i and pts[j] == p:
                j = (j - 1) % n
            k = (i + 1) % n
            while k != i and pts[k] == p:
                k = (k + 1) % n
            ax, ay = p[0] - pts[j][0], p[1] - pts[j][1]
            bx, by = pts[k][0] - p[0], pts[k][1] - p[1]
            la, lb = math.hypot(ax, ay), math.hypot(bx, by)
            if not la or not lb:
                continue
            ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
            # (the filled side is to the right of the outline's direction: out is to its left)
            nx, ny = -(ay + by), ax + bx
            d = ax * bx + ay * by
            if d < -0.9:
                continue
            f = 1.0 / (1.0 + d)
            out[start + i] = (round(p[0] + nx * f * sx / 2), round(p[1] + ny * f * sy / 2))
        start = end + 1
    return out


def make(src: Path, out: Path) -> str:
    t = TTFont(src)
    upem = t["head"].unitsPerEm
    glyf, hmtx = t["glyf"], t["hmtx"]
    classes = getattr(getattr(t["GDEF"].table, "GlyphClassDef", None), "classDefs", {}) if "GDEF" in t else {}
    sx, sy = STRENGTH * upem, STRENGTH_Y * upem
    for name in t.getGlyphOrder():
        g = glyf[name]
        if g.isComposite() or not getattr(g, "numberOfContours", 0):
            continue
        mark = classes.get(name) == 3 or hmtx[name][0] == 0
        k = MARKS if mark else 1.0
        coords = list(g.coordinates)
        new = _embolden(coords, list(g.endPtsOfContours), sx * k, sy * k)
        if not mark:
            new = [(x + round(sx / 2), y) for x, y in new]
        g.coordinates[:] = new
        g.recalcBounds(glyf)
        if not mark:
            adv, lsb = hmtx[name]
            hmtx[name] = (adv + round(sx), g.xMin)
    for name in t.getGlyphOrder():
        g = glyf[name]
        if g.isComposite():
            g.recalcBounds(glyf)
            adv, _ = hmtx[name]
            hmtx[name] = (adv + (round(sx) if adv else 0), g.xMin)
    # the names: the family's Bold
    family = t["name"].getDebugName(1)
    for r in t["name"].names:
        if r.nameID == 2:
            r.string = "Bold"
        elif r.nameID == 4:
            r.string = f"{family} Bold"
        elif r.nameID == 6:
            r.string = f"{family.replace(' ', '')}-Bold"
        elif r.nameID == 3:
            r.string = r.toUnicode() + " Bold"
    t["OS/2"].usWeightClass = 700
    t["OS/2"].fsSelection = (t["OS/2"].fsSelection | 0x20) & ~0x40
    t["head"].macStyle |= 1
    t.save(out)
    return f"{out.name}: {family} Bold"


if __name__ == "__main__":
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "fonts/FrankSofer.ttf")
    print(make(src, src.with_name(src.stem + "-Bold.ttf")))
