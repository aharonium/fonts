"""Give a font's kamatz katan (U+05C7) its own look (Mordy, 2026-10-21): the kamatz with a longer
stem ending in a round drop, as printed chumashim mark it (Keter YG, Ezra SIL and Taamey Frank
draw it so already; Frank Ruehl, Simple and Noto Rashi Hebrew drew it as a plain kamatz).

The fonts changed are free to change under their own names: Frank Ruehl CLM and Simple CLM
(Culmus, GPL-2 with the font exception) and Noto Rashi Hebrew (OFL, no reserved names).

    python scripts/add_qamats_qatan.py        (changes the files in fonts/; run once - a font
                                                done already is left as it is)
"""
from __future__ import annotations

import math
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[1] / "fonts"
FILES = ("FrankRuehlCLM-Medium.ttf", "FrankRuehlCLM-Bold.ttf", "FrankRuehlCLM-MediumOblique.ttf",
         "FrankRuehlCLM-BoldOblique.ttf", "SimpleCLM-Medium.ttf", "SimpleCLM-Bold.ttf",
         "SimpleCLM-MediumOblique.ttf", "SimpleCLM-BoldOblique.ttf",
         "NotoRashiHebrew-Regular.ttf", "NotoRashiHebrew-Bold.ttf",
         # (their own kamatz katan was barely different - Mordy, 2026-10-21: "someone who wants to
         #  see it will, but it won't look jarring to someone who doesn't know the difference")
         "KeterYG-Medium.ttf", "KeterYG-Bold.ttf", "KeterYG-MediumOblique.ttf", "KeterYG-BoldOblique.ttf",
         # (the fonts added 2026-10-21: Culmus' ta'amim fonts, GPL; Noto Serif Hebrew and David
         #  Libre, OFL with no reserved names of theirs.  Frank Sofer - Taamey D - is made by
         #  scripts/make_frank_sofer.py, which calls this with its drop a little lower)
         "ShofarRegular.ttf", "ShofarDemi-Bold.ttf", "TaameyAshkenaz-Medium.ttf", "TaameyAshkenaz-Bold.ttf",
         "TaameyDavidCLM-Medium.ttf", "TaameyDavidCLM-Bold.ttf", "KeterAramTsova.ttf",
         "NotoSerifHebrew-Regular.ttf", "NotoSerifHebrew-Bold.ttf", "DavidLibre-Regular.ttf", "DavidLibre-Bold.ttf")


def _area(points) -> float:
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1])) / 2


def make(path: Path, lower: float = 0) -> str:
    """``lower``: the drop hangs this much lower (its share of the bar-to-foot height) on a
    longer stem - Frank Sofer: 0.18 (Mordy, 2026-10-21, "the 3/5 mix")."""
    t = TTFont(path)
    cmap, gs = t.getBestCmap(), t.getGlyphSet()
    qamats, qatan = cmap.get(0x05B8), cmap.get(0x05C7)
    if not qamats or not qatan:
        return f"{path.name}: no kamatz / kamatz katan"
    bp = BoundsPen(gs)
    gs[qamats].draw(bp)
    x0, y0, x1, y1 = bp.bounds
    h, bar = y1 - y0, x1 - x0
    # (always made from the kamatz, so running it again changes nothing)
    # the kamatz, decomposed, as plain points
    pen = TTGlyphPen(gs)
    gs[qamats].draw(pen)
    g = pen.glyph()
    pts = list(g.coordinates)
    # the bar: the points at its two ends; the stem: what hangs under the bar's underside
    edge = bar * 0.15
    under = min(y for x, y in pts if x <= x0 + edge or x >= x1 - edge)
    stem = [(x, y) for x, y in pts if y < under - h * 0.02]
    if not stem:
        # (Simple's bold oblique: its bar's ends sit lower than its stem's foot - the foot is
        #  what is lowest)
        under = y0 + h * 0.45
        stem = [(x, y) for x, y in pts if y < under - h * 0.02]
    # (Mordy, 2026-10-21, after his picture of a printed chumash: the katan is hardly longer -
    #  its drop is bolder, a fuller teardrop under the bar, where the kamatz has a small one or
    #  none).  A kamatz ending in a ball of its own (Taamey Frank, Keter YG: wide at its foot)
    #  has that ball made fuller - never a second ball; one ending straight (Frank Ruehl, Simple,
    #  Rashi script) gets a teardrop widening out of its stem.
    slant = math.tan(math.radians(t["post"].italicAngle or 0))
    low = [(x, y) for x, y in pts if y <= y0 + h * 0.3]
    lx0, lx1 = min(x for x, _ in low), max(x for x, _ in low)
    foot_w = lx1 - lx0
    has_ball = foot_w > bar * 0.4
    if has_ball:
        # the ball: the points of the foot, grown about its centre (a little lower, so it is
        # fuller below and still joined to the stem above)
        ball = [(x, y) for x, y in pts if y <= y0 + foot_w * 0.9]
        bx = (min(x for x, _ in ball) + max(x for x, _ in ball)) / 2
        by = (min(y for _, y in ball) + max(y for _, y in ball)) / 2
        grow = 1.45
        g.coordinates = type(g.coordinates)([
            (bx + (x - bx) * grow, by + (y - by) * grow - foot_w * 0.08) if y <= y0 + foot_w * 0.9 else (x, y)
            for x, y in pts])
        added = f", its ball x{grow}"
    else:
        # a teardrop: from the stem's foot it widens into a round drop, about twice the stem's width
        cx = (lx0 + lx1) / 2
        r = max(foot_w * 0.95, bar * 0.16)
        cy = y0 - r * 0.55
        circle = [(round(cx + r * math.cos(2 * math.pi * i / 20) + (cy - y0) * slant * -1),
                   round(cy + r * math.sin(2 * math.pi * i / 20))) for i in range(20)]
        neck = [(round(lx0 + 0.15 * foot_w), round(y0 + h * 0.05)), (round(lx1 - 0.15 * foot_w), round(y0 + h * 0.05)),
                (round(cx + r * 0.92), round(cy + r * 0.35)), (round(cx - r * 0.92), round(cy + r * 0.35))]
        outer = [pts[i] for i in range(g.endPtsOfContours[0] + 1)]
        pen2 = TTGlyphPen(gs)
        g.draw(pen2, t["glyf"])
        for shape in (neck, circle):
            if (_area(outer) < 0) != (_area(shape) < 0):
                shape.reverse()
            pen2.moveTo(shape[0])
            for q in shape[1:]:
                pen2.lineTo(q)
            pen2.closePath()
        g = pen2.glyph()
        added = f", a teardrop r {round(r)}"
    if lower:
        dy = round(lower * 0.55 * h)
        g.coordinates = type(g.coordinates)([(x, y - dy) if y < y0 + 0.2 * h else (x, y) for x, y in g.coordinates])
        added += f", hanging {dy} lower"
    t["glyf"][qatan] = g
    g.recalcBounds(t["glyf"])
    t["hmtx"][qatan] = (t["hmtx"][qamats][0], g.xMin)
    # a mark stacked under it (a ta'am) goes under the longer stem
    low = round(g.yMin - y0) * -1
    if "GPOS" in t:
        for lk in t["GPOS"].table.LookupList.Lookup:
            for st in lk.SubTable:
                if type(st).__name__ == "MarkMarkPos" and qatan in st.Mark2Coverage.glyphs:
                    rec2 = st.Mark2Array.Mark2Record[st.Mark2Coverage.glyphs.index(qatan)]
                    for a in rec2.Mark2Anchor:
                        if a is not None and a.YCoordinate < y0:
                            a.YCoordinate -= low
    t.save(path)
    return f"{path.name}: kamatz katan drawn{added}"


if __name__ == "__main__":
    for f in FILES:
        print(make(FONTS / f))
