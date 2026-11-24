"""Make "Sofer Stam Sefarad" and "Sofer Stam Ashkenaz": Sefer Torah scripts with nikud and
ta'amim (Mordy, 2026-10-21: no Sefardi one existed - Culmus' Stam fonts have empty marks; and
the Ashkenazi Shlomo Stam's file says it may not be used commercially, so it was replaced).
Stam Ashkenaz CLM's letters: ``git show ac810ada^:fonts/StamAshkenazCLM.ttf``, made with
``--ashkenaz`` into fonts/SoferStamAshkenaz.ttf.

Both sources are GPL-2 with the font exception:
  * Frank Sofer (fonts/FrankSofer.ttf: Taamey D, Ben Denckla's, with Sofer's changes -
    scripts/make_frank_sofer.py; Taamey Frank CLM until 2026-10-21) - every nikud and ta'am,
    and the layout logic that places them;
  * Stam Sefarad CLM (in git history: ``git show ac810ada^:fonts/StamSefaradCLM.ttf``) - the
    letters.
Taamey Frank is kept whole - its marks, its GSUB and GPOS - and each letter's outline is
replaced by Stam Sefarad's; the letters joined with a mark (בּ, שׁ, וֹ ...) are rebuilt as the
Stam letter with Taamey Frank's mark where it was on the Frank letter; and every anchor the
marks attach to is moved from the Frank letter to the Stam one (inside the letter: in
proportion to its size; above or below it: as far from its top / bottom as before).

    python scripts/make_stam_sefarad.py <StamSefaradCLM.ttf>   ->  fonts/SoferStamSefarad.ttf
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FRANK = ROOT / "fonts" / "FrankSofer.ttf"        # (Taamey D with our kamatz katan; Taamey Frank CLM until 2026-10-21)
OUT = ROOT / "fonts" / "SoferStamSefarad.ttf"
FAMILY = "Sofer Stam Sefarad"
SOURCE = "Stam Sefarad CLM"
LETTERS = range(0x5D0, 0x5EB)
PAD = 50                         # more room on each side of every letter, font units (of 2048)


def contours(font, name):
    """A glyph's contours, each a tuple of its points (composites decomposed)."""
    pen = DecomposingRecordingPen(font.getGlyphSet())
    font.getGlyphSet()[name].draw(pen)
    out, cur = [], []
    for op, args in pen.value:
        if op == "moveTo":
            cur = [args[0]]
        elif op in ("lineTo", "qCurveTo", "curveTo"):
            cur.extend(args)
        elif op in ("closePath", "endPath"):
            out.append(tuple(cur))
            cur = []
    return out


def bbox(points):
    xs = [p[0] for c in points for p in c if p is not None]
    ys = [p[1] for c in points for p in c if p is not None]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


class Mapping:
    """From a place on / around the Frank letter to the same place on the Stam letter."""

    def __init__(self, f, s, fbody=0, sbody=0):
        self.f, self.s = f, s           # (xMin, yMin, xMax, yMax)
        self.fbody, self.sbody = fbody, sbody     # the letters' bodies' height (their roofs, no crowns)

    def x(self, x):
        (fx0, _, fx1, _), (sx0, _, sx1, _) = self.f, self.s
        return sx0 + (x - fx0) * (sx1 - sx0) / max(1, fx1 - fx0)

    def y(self, y):
        (_, fy0, _, fy1), (_, sy0, _, sy1) = self.f, self.s
        if y >= fy1:
            return sy1 + (y - fy1)
        # (under the line the letters stand on: as far under it as in Taamey Frank, whatever the
        #  letter's tail - the Stam ק's longer tail took its vowel lower than the others': Mordy,
        #  2026-10-21; both fonts' letters stand on the same line, their bodies as tall)
        if y <= 0:
            return y
        # (inside the letter - a dagesh: by its body, the crowns not counted; measured with the
        #  crowns it came too high and touched the roof - Mordy, 2026-10-21)
        if self.fbody and 0 < y <= self.fbody:
            return y * self.sbody / self.fbody
        if self.fbody and y < fy1:
            return self.sbody + (y - self.fbody) * (sy1 - self.sbody) / max(1, fy1 - self.fbody)
        fy0, sy0 = max(fy0, 0), max(sy0, 0)
        return sy0 + (y - fy0) * (sy1 - sy0) / max(1, fy1 - fy0)


def main(stam_path: str) -> None:
    T, S = TTFont(FRANK), TTFont(stam_path)
    # (the base's letter-pair spacing - kerning - is for its own letters, not the Stam ones)
    if "GPOS" in T:
        for fr in T["GPOS"].table.FeatureList.FeatureRecord:
            if fr.FeatureTag == "kern":
                fr.Feature.LookupListIndex = []
                fr.Feature.LookupCount = 0
    tcmap, scmap = T.getBestCmap(), S.getBestCmap()
    tglyf, sglyf = T["glyf"], S["glyf"]

    # 1. the letters: Stam outlines and widths, under Taamey Frank's glyph names - each with a
    #    little more room on both sides (PAD: in a Sefer Torah no letter touches another; the
    #    Stam fonts' own spacing left about 6% of a letter between them - א and ל looked joined:
    #    Mordy, 2026-10-21)
    try:
        from sofer.fonts import hebrew_body_height
    except ImportError:                     # (outside Sofer: body_height.py beside this script)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from body_height import hebrew_body_height
    upm = T["head"].unitsPerEm
    fbody, sbody = hebrew_body_height(str(FRANK)) * upm, hebrew_body_height(str(Path(stam_path).resolve())) * upm
    letter_of: dict[str, str] = {}          # any Frank glyph standing for a letter -> its letter glyph
    maps: dict[str, Mapping] = {}           # letter glyph -> Frank-to-Stam mapping
    frank_letter_contours: dict[str, list] = {}
    for cp in LETTERS:
        f, s = tcmap.get(cp), scmap.get(cp)
        if not f or not s:
            continue
        frank_letter_contours[f] = contours(T, f)
        fb = bbox(frank_letter_contours[f])
        pen = TTGlyphPen(S.getGlyphSet())
        S.getGlyphSet()[s].draw(pen)
        g = pen.glyph()
        if g.numberOfContours:
            g.coordinates.translate((PAD, 0))
        g.recalcBounds(sglyf)
        tglyf[f] = g
        T["hmtx"][f] = (S["hmtx"][s][0] + 2 * PAD, g.xMin)
        maps[f] = Mapping(fb, (g.xMin, g.yMin, g.xMax, g.yMax), fbody, sbody)
        letter_of[f] = f
    # the letters' other forms (wide letters for justifying, alternates): the plain Stam letter
    for name in T.getGlyphOrder():
        base, _, suffix = name.partition(".")
        g0 = T["glyf"][name]
        if g0.isComposite() and any(c.glyphName.split(".")[0] not in maps for c in g0.components):
            continue                    # (a form drawn with a mark - alef.xolam, the holam of the ל before it: step 2)
        if suffix and base in maps:
            tglyf[name] = tglyf[base]
            T["hmtx"][name] = T["hmtx"][base]
            maps[name] = maps[base]
            letter_of[name] = base

    # 2. the letters joined with a mark (בּ, שׁ, וֹ ... - Taamey Frank draws them as the letter
    #    and the mark together): the Stam letter, and the mark where it was on Frank's letter
    F = TTFont(FRANK)
    done: set[str] = set()
    report: list[str] = []
    for name in T.getGlyphOrder():
        g = F["glyf"][name]
        if not g.isComposite() or name in maps:
            continue
        letters = [c for c in g.components if c.glyphName in maps]
        if len(letters) != 1:
            continue
        lc = letters[0]
        m = maps[lc.glyphName]
        new = T["glyf"][name]
        for c in new.components:
            if c.glyphName == lc.glyphName:
                c.x, c.y = 0, 0
                continue
            mb = bbox(contours(F, c.glyphName))
            if not mb:
                continue
            # the mark's centre on Frank's letter, then on Stam's
            cx = c.x - lc.x + (mb[0] + mb[2]) / 2
            cy = c.y - lc.y + (mb[1] + mb[3]) / 2
            c.x = round(m.x(cx) - (mb[0] + mb[2]) / 2)
            c.y = round(m.y(cy) - (mb[1] + mb[3]) / 2)
        T["hmtx"][name] = (T["hmtx"][lc.glyphName][0], T["hmtx"][lc.glyphName][1])
        maps[name] = m
        letter_of[name] = lc.glyphName
        done.add(name)
    for name in done:
        T["glyf"][name].recalcBounds(T["glyf"])
    # (anything else drawn with a Frank letter in it)
    for name in T.getGlyphOrder():
        g = F["glyf"][name]
        if name not in maps and not g.isComposite() and name.split(".")[0] in maps:
            report.append(f"{name}: drawn on its own in Taamey Frank, kept")

    # 3. the anchors the marks attach to, moved from the Frank letter to the Stam one
    def move(anchor, m: Mapping):
        if anchor is None:
            return
        anchor.XCoordinate = round(m.x(anchor.XCoordinate))
        anchor.YCoordinate = round(m.y(anchor.YCoordinate))
        if anchor.Format != 1:
            anchor.Format = 1                # (contour-point / device anchors: plain)

    moved = 0
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            if type(st).__name__ == "MarkBasePos":
                for base, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                    m = maps.get(base)
                    if m is None:
                        continue
                    for a in rec.BaseAnchor:
                        move(a, m)
                        moved += 1

    # 3b. where the mapping above misses on a Stam letter's own shape (Mordy, 2026-10-21: the
    #     sin dot over the middle head, the kamatz touching the פ's tail, the צ's dagesh off)
    report += by_shape(T, sbody)
    report += holam_beside(T, F, fbody, sbody)
    report += clear_of_ink(T, sbody)
    report += apart_below(T)

    # 4. its own name
    base_family = next(r.toUnicode() for r in T["name"].names if r.nameID == 1)
    for rec in T["name"].names:
        if rec.nameID in (1, 3, 4, 6, 16, 17):
            text = rec.toUnicode()
            rec.string = (text.replace(base_family, FAMILY).replace(base_family.replace(" ", ""), FAMILY.replace(" ", ""))
                          .replace("Taamey Frank CLM", FAMILY).replace("TaameyFrankCLM", FAMILY.replace(" ", "")))
            if rec.nameID in (1, 16):
                rec.string = FAMILY
    for rec in T["name"].names:
        if rec.nameID == 0:
            rec.string = (rec.toUnicode() + f"\n\n{FAMILY}: the letters of {SOURCE}, copyright "
                          "2008-2010 by Yoram Gnat (GPL-2, with the font exception above), put into "
                          f"{base_family} by Sofer, 2026: its marks and their placement kept, each moved "
                          "to the same place on the Stam letter.")
    T.save(OUT)
    print(f"{OUT.name}: {len(maps)} letter glyphs, {len(done)} joined glyphs rebuilt, {moved} anchors moved")
    _shva_na(OUT)
    _under_the_leg(OUT)
    print("  " + clear_between(OUT))
    print("  " + fix_by_shaping(OUT, tanach_words()))
    _check_marks(OUT)
    for line in report:
        print("  ", line)



# letters whose dagesh sits in an open counter: nudged into the open; the צ's into its bay
COUNTER = ("bet", "gimel", "tet", "kaf", "lamed", "mem", "nun", "samekh", "pe", "finalpe", "qof",
           "shin", "tav")


def _ink_grid(T, name, step=12):
    """{(x, y): inside the outline} over the glyph's box (and a little around it)."""
    from fontTools.pens.pointInsidePen import PointInsidePen
    gs, g = T.getGlyphSet(), T["glyf"][name]
    g.recalcBounds(T["glyf"])
    pts = {}
    for y in range(g.yMin - 3 * step, g.yMax + 3 * step, step):
        for x in range(g.xMin - 3 * step, g.xMax + 3 * step, step):
            pen = PointInsidePen(gs, (x, y))
            gs[name].draw(pen)
            pts[(x, y)] = pen.getResult()
    return g, pts


def _roomy(pts, start, r, body, cap, pull, inside=False):
    """The spot near ``start`` with the most room around it, inside the letter (ink on both
    sides of it, across or up and down), within its body."""
    import math
    ink = [p for p, v in pts.items() if v]
    xs, ys = sorted({p[0] for p in pts}), sorted({p[1] for p in pts})
    x0, x1 = min(p[0] for p in ink), max(p[0] for p in ink)
    best, score = start, -1e9
    for (x, y), v in pts.items():
        if v or not 0.08 * body <= y <= 0.92 * body:
            continue
        dist = math.hypot(x - start[0], y - start[1])
        if dist > r * 10:
            continue
        across = any(pts[(a, y)] for a in xs if a < x) and any(pts[(a, y)] for a in xs if a > x)
        updown = any(pts[(x, b)] for b in ys if b > y) and any(pts[(x, b)] for b in ys if b < y)
        if not (across or updown):
            continue
        clear = min(math.hypot(x - a, y - b) for a, b in ink)
        if inside:                          # (the letter's open side counts as its edge)
            clear = min(clear, x - x0, x1 - x)
        s = min(clear, cap) - pull * dist
        if s > score:
            best, score = (x, y), s
    return best


def by_shape(T, body: float) -> list[str]:
    G, notes = T["glyf"], []
    box = {}
    for n in ("dagesh", "dageshxazaq", "shindot", "sindot"):
        if n in G.glyphs:
            G[n].recalcBounds(G)
            box[n] = (G[n].xMin, G[n].yMin, G[n].xMax, G[n].yMax)
    grids = {}

    def grid(name):
        if name not in grids:
            grids[name] = _ink_grid(T, name)
        return grids[name]
    # the dagesh, and the shin's and sin's dots, in the letters drawn with them
    for name in T.getGlyphOrder():
        g = G[name]
        if not g.isComposite():
            continue
        letter = next((c for c in g.components if c.glyphName in COUNTER + ("tsadi",)), None)
        if letter is None:
            continue
        for c in g.components:
            if c.glyphName not in box:
                continue
            bx0, by0, bx1, by1 = box[c.glyphName]
            cx, cy = c.x - letter.x + (bx0 + bx1) / 2, c.y - letter.y + (by0 + by1) / 2
            lg, pts = grid(letter.glyphName)
            if c.glyphName.startswith("dagesh"):
                strong = letter.glyphName == "tsadi"
                r = (bx1 - bx0) / 2
                nx, ny = _roomy(pts, (cx, cy), r, body, r * (4 if strong else 2), 0.15 if strong else 0.25, strong)
            elif letter.glyphName == "shin":
                # over the right head (shin) or the left one (sin): the heads where the body's top is cut
                y = max(p[1] for p in pts if p[1] <= body * 0.9)
                row = sorted(p[0] for p, v in pts.items() if v and p[1] == y)
                runs, run = [], [row[0]]
                for x in row[1:]:
                    if x - run[-1] > 13:
                        runs.append(run)
                        run = [x]
                    else:
                        run.append(x)
                runs.append(run)
                head = runs[-1] if c.glyphName == "shindot" else runs[0]
                nx, ny = (head[0] + head[-1]) / 2, cy
                if c.glyphName == "shindot":    # (just over its head, which has no crown: not up by the crowns)
                    top = max(p[1] for p, v in pts.items() if v and head[0] <= p[0] <= head[-1])
                    ny = min(cy, top + 90 + (by1 - by0) / 2)
            else:
                continue
            c.x, c.y = round(c.x + nx - cx), round(c.y + ny - cy)
        g.recalcBounds(G)
    # the marks below: clear of any part of the letter reaching under the line (the פ's tail)
    lookups = T["GPOS"].table.LookupList.Lookup
    for lk in lookups:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for n, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if n in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            G["qamats"].recalcBounds(G)
            half = (G["qamats"].xMax - G["qamats"].xMin) / 2 + 20
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                a = rec.BaseAnchor[c]
                if a is None or name.startswith(("final", "qof")):
                    continue
                G[name].recalcBounds(G)
                if G[name].yMin >= -40:
                    continue
                _, pts = grid(name)

                def depth(x):
                    return max([-p[1] for p, v in pts.items() if v and p[1] < 0 and abs(p[0] - x) <= half], default=0)
                if depth(a.XCoordinate) <= 40:
                    continue
                w = G[name].xMax - G[name].xMin
                for dx in sorted(range(-int(w * 0.4), int(w * 0.4) + 1, 12), key=abs):
                    if depth(a.XCoordinate + dx) <= 40:
                        notes.append(f"{name}: the marks below moved {dx:+d} (clear of its tail)")
                        a.XCoordinate += dx
                        break
                else:
                    a.YCoordinate -= depth(a.XCoordinate) - 20
                    notes.append(f"{name}: the marks below lowered (under its tail)")
    return notes


def _left_edge(font, name, y0, y1, step=12):
    """The leftmost ink of a glyph between two heights."""
    from fontTools.pens.pointInsidePen import PointInsidePen
    gs, g = font.getGlyphSet(), font["glyf"][name]
    g.recalcBounds(font["glyf"])
    best = None
    for y in range(int(y0), int(y1) + 1, step):
        for x in range(g.xMin, g.xMax + 1, step):
            pen = PointInsidePen(gs, (x, y))
            gs[name].draw(pen)
            if pen.getResult():
                best = x if best is None else min(best, x)
                break
    return best


def _outline_points(font, name, step=8):
    """Points along a glyph's outline (its curves sampled), font units."""
    from fontTools.pens.basePen import BasePen

    class Pts(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.p, self.cur = [], (0, 0)

        def _moveTo(self, a):
            self.p.append(a)
            self.cur = a

        def _lineTo(self, a):
            x0, y0 = self.cur
            self.p += [(x0 + (a[0] - x0) * i / step, y0 + (a[1] - y0) * i / step) for i in range(1, step + 1)]
            self.cur = a

        def _curveToOne(self, a, b, c):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                m = 1 - s
                self.p.append((m ** 3 * x0 + 3 * m * m * s * a[0] + 3 * m * s * s * b[0] + s ** 3 * c[0],
                               m ** 3 * y0 + 3 * m * m * s * a[1] + 3 * m * s * s * b[1] + s ** 3 * c[1]))
            self.cur = c

        def _qCurveToOne(self, a, b):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                m = 1 - s
                self.p.append((m * m * x0 + 2 * m * s * a[0] + s * s * b[0], m * m * y0 + 2 * m * s * a[1] + s * s * b[1]))
            self.cur = b
    gs = font.getGlyphSet()
    pen = Pts(gs)
    gs[name].draw(pen)
    return pen.p


INK_GAP = 40            # the least room between a mark and its letter's ink, font units
_SC = 4                 # (font units to a pixel, for the check)


def _mask(font, name):
    """The glyph's ink as a picture: (left, top, image), font units / _SC."""
    from PIL import Image, ImageChops, ImageDraw
    polys = [c for c in _outline_polys(font, name) if len(c) >= 3]
    if not polys:
        return None
    xs = [p[0] for c in polys for p in c]
    ys = [p[1] for c in polys for p in c]
    x0, y1 = int(min(xs) // _SC) - 1, int(max(ys) // _SC) + 2
    w, h = int(max(xs) // _SC) + 2 - x0, y1 - int(min(ys) // _SC) + 1
    img = Image.new("1", (w, h), 0)
    for c in polys:
        one = Image.new("1", (w, h), 0)
        ImageDraw.Draw(one).polygon([(x / _SC - x0, y1 - y / _SC) for x, y in c], fill=1)
        img = ImageChops.logical_xor(img, one)
    return x0, y1, img


def _outline_polys(font, name, step=6):
    """The glyph's contours as polygons (its curves sampled), font units."""
    from fontTools.pens.basePen import BasePen

    class Polys(BasePen):
        def __init__(self, gs):
            super().__init__(gs)
            self.polys, self.cur = [], (0, 0)

        def _moveTo(self, a):
            self.polys.append([a])
            self.cur = a

        def _lineTo(self, a):
            self.polys[-1].append(a)
            self.cur = a

        def _qCurveToOne(self, a, b):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                self.polys[-1].append(((1 - s) ** 2 * x0 + 2 * (1 - s) * s * a[0] + s * s * b[0],
                                       (1 - s) ** 2 * y0 + 2 * (1 - s) * s * a[1] + s * s * b[1]))
            self.cur = b

        def _curveToOne(self, a, b, c):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s, m = i / step, 1 - i / step
                self.polys[-1].append((m ** 3 * x0 + 3 * m * m * s * a[0] + 3 * m * s * s * b[0] + s ** 3 * c[0],
                                       m ** 3 * y0 + 3 * m * m * s * a[1] + 3 * m * s * s * b[1] + s ** 3 * c[1]))
            self.cur = c
    gs = font.getGlyphSet()
    pen = Polys(gs)
    gs[name].draw(pen)
    return pen.polys


def _touch(a, b, dx, dy):
    """Do mask a and mask b, moved by (dx, dy) font units, share ink?"""
    from PIL import ImageChops
    ax, ay, am = a
    bx, by, bm = b
    bx, by = bx + round(dx / _SC), by + round(dy / _SC)
    x0, x1 = max(ax, bx), min(ax + am.size[0], bx + bm.size[0])
    top, bottom = min(ay, by), max(ay - am.size[1], by - bm.size[1])
    if x0 >= x1 or bottom >= top:
        return False
    sa = am.crop((x0 - ax, ay - top, x1 - ax, ay - bottom))
    sb = bm.crop((x0 - bx, by - top, x1 - bx, by - bottom))
    return ImageChops.logical_and(sa, sb).getbbox() is not None


def clear_of_ink(T, body: float) -> list[str]:
    """Every mark clear of its own letter's ink - the crowns of שעטנ״ז ג״ץ, the Ashkenazi א's
    tail, the corner of ה (Mordy, 2026-10-22: "remove all collisions"; a check of every word
    of Tanach found thousands, the marks being set where they sit on Frank Sofer's letters):
    a mark above moved up, one below moved down, until INK_GAP clear - the least move, for
    every mark its letter's anchor carries."""
    from PIL import Image, ImageFilter
    notes, masks, grown = [], {}, {}

    def mask(n):
        if n not in masks:
            masks[n] = _mask(T, n)
        return masks[n]

    def fat(n):                         # (the letter's ink grown by the gap)
        if n not in grown:
            m, g = mask(n), INK_GAP // _SC
            if m is None:
                grown[n] = None
            else:
                big = Image.new("L", (m[2].size[0] + 2 * g, m[2].size[1] + 2 * g), 0)
                big.paste(m[2].convert("L"), (g, g))
                grown[n] = (m[0] - g, m[1] + g, big.filter(ImageFilter.MaxFilter(2 * g + 1)).convert("1"))
        return grown[n]
    G = T["glyf"]
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            by_class = {}
            for m, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord):
                by_class.setdefault(r.Class, []).append((m, r.MarkAnchor))
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if fat(name) is None:
                    continue
                for c, marks in by_class.items():
                    a = rec.BaseAnchor[c]
                    if a is None:
                        continue
                    placed = []
                    for m, ma in marks:
                        if mask(m) is None:
                            continue
                        G[m].recalcBounds(G)
                        side = 1 if G[m].yMin >= body * 0.8 else -1 if G[m].yMax <= 0 else 0
                        placed.append((m, a.XCoordinate - ma.XCoordinate, a.YCoordinate - ma.YCoordinate, side))
                    # (an anchor serves marks of one kind - those above, or those below; a few
                    #  others listed with them never come on this letter)
                    sides = [s for *_, s in placed if s]
                    if not sides:
                        continue
                    up = max((1, -1), key=sides.count)
                    placed = [p for p in placed if p[3] == up]
                    if not any(_touch(fat(name), mask(m), ox, oy) for m, ox, oy, _ in placed):
                        continue
                    # (the least move: up or down; a mark below may go well to either side, past a
                    #  final letter's tail - one above only a little, so it stays over its letter)
                    side = 300 if up < 0 else 48
                    tries = sorted(((dx, up * dy) for dx in range(-side, side + 1, 12) for dy in range(0, 601, 12)),
                                   key=lambda d: (d[0] ** 2 + d[1] ** 2, abs(d[0])))
                    move = next((d for d in tries if not any(
                        _touch(fat(name), mask(m), ox + d[0], oy + d[1]) for m, ox, oy, _ in placed)), None)
                    if move is None:
                        notes.append(f"{name}: marks {'above' if up > 0 else 'below'} touch it; no room found")
                        continue
                    a.XCoordinate += move[0]
                    a.YCoordinate += move[1]
                    if a.Format != 1:
                        a.Format = 1
                    notes.append(f"{name}: marks {'above' if up > 0 else 'below'} moved {move[0]:+d}, {move[1]:+d}")
    return notes


HOLAM_CLEAR = 74        # the cholam's room from the letter's ink, font units: as in Frank Sofer (ל)


def holam_beside(T, F, fbody: float, sbody: float) -> list[str]:
    """A cholam at a letter's upper left (Mordy, 2026-10-21: too far from the ל, then touching its
    crowns): the ל's as far from the Stam ל's ink at the top of its body as from the Frank ל's -
    not by the whole letter's width, which its mast makes far wider; then every letter's moved out
    (left, then up) until it is as clear of the letter's ink, crowns and all, as Frank Sofer's."""
    import math
    notes = []
    flk = F["GPOS"].table.LookupList.Lookup
    dot = _outline_points(T, "xolam")
    for i, lk in enumerate(T["GPOS"].table.LookupList.Lookup):
        for j, st in enumerate(lk.SubTable):
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "xolam" not in st.MarkCoverage.glyphs:
                continue
            fst = getattr(flk[i].SubTable[j], "ExtSubTable", flk[i].SubTable[j])
            mrec = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index("xolam")]
            c, ma = mrec.Class, mrec.MarkAnchor
            frec = dict(zip(fst.BaseCoverage.glyphs, fst.BaseArray.BaseRecord))
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                a = rec.BaseAnchor[c]
                fa = frec[name].BaseAnchor[c] if name in frec else None
                if a is None:
                    continue
                if name.startswith("lamed") and fa is not None:
                    fl = _left_edge(F, name, fbody * 0.7, fbody)
                    sl = _left_edge(T, name, sbody * 0.7, sbody)
                    if fl is not None and sl is not None and fa.XCoordinate - ma.XCoordinate <= fl:
                        a.XCoordinate = round(sl - (fl - fa.XCoordinate))
                        a.YCoordinate = round(fa.YCoordinate + (sbody - fbody))
                ink = _outline_points(T, name)
                if not ink:
                    continue

                def room(dx, dy):
                    ox, oy = a.XCoordinate - ma.XCoordinate + dx, a.YCoordinate - ma.YCoordinate + dy
                    return min(math.dist((x + ox, y + oy), q) for x, y in dot[::2] for q in ink[::2])
                if room(0, 0) >= HOLAM_CLEAR:
                    continue
                # (out to the left first - where the dot is - then up, the least move that clears it)
                tries = sorted(((dx, dy) for dx in range(0, -301, -12) for dy in range(0, 241, 12)),
                               key=lambda d: math.hypot(*d))
                dx, dy = next((d for d in tries if room(*d) >= HOLAM_CLEAR), (0, 0))
                a.XCoordinate += dx
                a.YCoordinate += dy
                notes.append(f"{name}: the cholam moved {dx:+d}, {dy:+d} (clear of its ink)")
    return notes


PREPOSITIVE_BELOW = ("dexi", "yetiv")      # (set at a letter's right, beside its vowel)


NEIGHBOUR_GAP = 12      # between a mark and the letter beside its own: only clear of it


def _fat(m, gap: int = INK_GAP):
    """A glyph's picture grown by ``gap`` all round."""
    from PIL import Image, ImageFilter
    g = max(1, gap // _SC)
    big = Image.new("L", (m[2].size[0] + 2 * g, m[2].size[1] + 2 * g), 0)
    big.paste(m[2].convert("L"), (g, g))
    return m[0] - g, m[1] + g, big.filter(ImageFilter.MaxFilter(2 * g + 1)).convert("1")


def apart_below(T) -> list[str]:
    """A dehi or yetiv clear of the vowel under the same letter (Mordy, 2026-10-22: under ayin
    the vowel, moved clear of the tail, met the dehi): its anchor moved out to the right,
    the least that leaves INK_GAP."""
    notes, masks = [], {}

    def mask(n):
        if n not in masks:
            masks[n] = _mask(T, n)
        return masks[n]
    # (every letter's anchors for the vowels below and for the dehi / yetiv, wherever they are)
    vowels, pre = {}, {}
    for lk in T["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            marks = dict(zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord))
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if "qamats" in marks and rec.BaseAnchor[marks["qamats"].Class] is not None:
                    c = marks["qamats"].Class
                    vowels[name] = (rec.BaseAnchor[c], [(m, r.MarkAnchor) for m, r in marks.items()
                                                         if r.Class == c and m not in PREPOSITIVE_BELOW])
                for d in PREPOSITIVE_BELOW:
                    if d in marks and rec.BaseAnchor[marks[d].Class] is not None:
                        pre.setdefault(name, []).append((d, marks[d].MarkAnchor, rec.BaseAnchor[marks[d].Class]))
    for name, items in pre.items():
        if name not in vowels:
            continue
        va, vmarks = vowels[name]
        placed = [(m, va.XCoordinate - ma.XCoordinate, va.YCoordinate - ma.YCoordinate) for m, ma in vmarks
                  if mask(m) is not None]
        for d, dma, da in items:
            if mask(d) is None:
                continue
            ox, oy = da.XCoordinate - dma.XCoordinate, da.YCoordinate - dma.YCoordinate
            fd = _fat(mask(d))

            def touches(dx):
                return any(_touch(fd, mask(m), mx - (ox + dx), my - oy) for m, mx, my in placed)
            if not touches(0):
                continue
            dx = next((x for x in range(12, 601, 12) if not touches(x)), None)
            if dx:
                da.XCoordinate += dx
                if da.Format != 1:
                    da.Format = 1
                notes.append(f"{name}: the {d} {dx} further right (clear of the vowel)")
    return notes


def clear_between(path) -> str:
    """A mark clear of the letters beside its own (Mordy, 2026-10-22): the Ashkenazi lamed's flag
    reaches over the letter after it, the head of a final nun, gimel or shin over the cholam of
    the letter before it.  Where a letter's mark (above or below) would touch its neighbour, the
    two are set apart, by just enough, only when that mark is there: a GPOS lookup making the
    left-hand letter's advance larger (in a right-to-left line, the gap before the letter to its
    right).  Both ways: the mark on the left-hand letter (the lamed's flag), or on the right-hand
    one (the cholam before a final nun)."""
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    T = TTFont(path)
    gpos, gdef, G, hmtx = T["GPOS"].table, T["GDEF"].table, T["glyf"], T["hmtx"]
    rev = T.getReverseGlyphMap()
    classes = getattr(gdef.GlyphClassDef, "classDefs", {})
    letters = sorted(n for n, c in classes.items() if c == 1 and n in G.glyphs
                     and n.split(".")[0] not in ("space", "nbsp") and _mask(T, n) is not None)
    masks, fats = {}, {}

    def mask(n):
        if n not in masks:
            masks[n] = _mask(T, n)
        return masks[n]

    def fat(n):
        if n not in fats:
            fats[n] = _fat(mask(n), NEIGHBOUR_GAP)
        return fats[n]

    def box(m, dx=0, dy=0):
        x0, top, img = m
        return x0 * _SC + dx, (top - img.size[1]) * _SC + dy, (x0 + img.size[0]) * _SC + dx, top * _SC + dy
    # (each letter's marks where they sit: (mark, x, y) from the letter's origin)
    placed: dict = {}
    for lk in gpos.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            ms = [(m, r) for m, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if mask(m) is not None]
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if name not in letters:
                    continue
                for m, r in ms:
                    a = rec.BaseAnchor[r.Class]
                    if a is not None:
                        placed.setdefault(name, []).append(
                            (m, a.XCoordinate - r.MarkAnchor.XCoordinate, a.YCoordinate - r.MarkAnchor.YCoordinate))
    g = NEIGHBOUR_GAP

    def needed(left, right, mark_on_left):
        """How much further apart the left-hand letter (origin 0) and the right-hand one (origin at
        the left one's advance) must be for each of the marked letter's marks: {mark: d}."""
        adv = hmtx[left][0]
        out = {}
        if mark_on_left:
            other, ox = right, adv
            marks = placed.get(left, [])
        else:
            other, ox = left, -adv
            marks = placed.get(right, [])
        ob = box(mask(other))
        for m, mx, my in marks:
            mb = box(mask(m), mx, my)
            # (the right-hand letter moved right by d: the other letter, or the mark on it)
            sign = 1 if mark_on_left else -1
            if mb[1] > ob[3] + g or mb[3] < ob[1] - g:
                continue
            for d in range(0, 401, 12):
                shift = sign * (ox + d) if mark_on_left else ox - d
                if mark_on_left:
                    hit = _touch(fat(other), mask(m), mx - (ox + d), my)
                else:
                    hit = _touch(fat(other), mask(m), mx + adv + d, my)
                if not hit:
                    break
            if d:
                out[m] = d
        return out
    rules = {}          # (left, right, mark, mark on the left?) -> d
    for left in letters:
        for right in letters:
            for on_left in (True, False):
                for m, d in needed(left, right, on_left).items():
                    rules[(left, right, m, on_left)] = d
    if not rules:
        return "no mark reaches a letter beside it"
    marks = sorted({m for (_l, _r, m, _o) in rules})
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(marks, rev))
    sets.MarkSetCount = len(sets.Coverage)
    lookups = gpos.LookupList.Lookup
    singles, subtables = {}, []

    def single(d):
        if d not in singles:
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                {n: otl.buildValue({"XAdvance": d}) for n in letters}, rev)], table="GPOS"))
            singles[d] = len(lookups) - 1
        return singles[d]
    # grouped (a font allows only so many rules): one for each marked letter and amount, over all
    # its marks and neighbours that need it - the larger amount first
    groups: dict = {}
    for (left, right, m, on_left), d in rules.items():
        g_ = groups.setdefault((on_left, left if on_left else right, d), (set(), set()))
        g_[0].add(m)
        g_[1].add(right if on_left else left)
    for (on_left, marked, d), (ms, others) in sorted(groups.items(), key=lambda kv: -kv[0][2]):
        m = sorted(ms)
        st = ot.ChainContextPos()
        st.Format = 3
        if on_left:
            # (logical order: right-hand letter, then the marked left-hand one and its mark)
            st.BacktrackCoverage = [otl.buildCoverage(sorted(set(others)), rev)]
            st.InputCoverage = [otl.buildCoverage([marked], rev)]
            st.LookAheadCoverage = [otl.buildCoverage(m, rev)]
        else:
            # (the marked right-hand letter and its mark, then the left-hand letter)
            st.BacktrackCoverage = [otl.buildCoverage(m, rev), otl.buildCoverage([marked], rev)]
            st.InputCoverage = [otl.buildCoverage(sorted(set(others)), rev)]
            st.LookAheadCoverage = []
        st.BacktrackGlyphCount = len(st.BacktrackCoverage)
        st.InputGlyphCount, st.LookAheadGlyphCount = 1, len(st.LookAheadCoverage)
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, single(d)
        st.PosLookupRecord, st.PosCount = [r], 1
        subtables.append(st)
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, sets.MarkSetCount - 1
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in gpos.FeatureList.FeatureRecord:
        if fr.FeatureTag == "mark":
            fr.Feature.LookupListIndex.append(len(lookups) - 1)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    T.save(path)
    return f"{len(rules)} letter pairs set apart when a mark would touch the letter beside it (up to {max(rules.values())})"


def tanach_words() -> list[str]:
    """Every word of Tanach (Miqra according to the Masorah, from the library), as printed:
    letters, marks and the CGJ.  [] when the library is not here."""
    import json
    import re as _re
    root = ROOT / "data" / "sefaria-export" / "json" / "Tanakh"
    words = set()

    def walk(x):
        if isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, str):
            x = _re.sub(r'<sup class="footnote-marker">.*?</i>|<[^>]*>|&[a-z#0-9]+;', " ", x)
            for w in _re.split(r"[\s\u05be]+", x):
                w = _re.sub(r"[^\u0591-\u05c9\u05d0-\u05ea\ufb1e\u034f]", "", w)
                if _re.search("[\u05d0-\u05ea]", w):
                    words.add(w)
    for f in root.rglob("Miqra according to the Masorah.json") if root.is_dir() else ():
        walk(json.loads(f.read_text(encoding="utf-8"))["text"])
    return sorted(words)


def _shaped(hbfont, word):
    import uharfbuzz as hb
    buf = hb.Buffer()
    buf.add_str(word)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf)
    out, x = [], 0
    for i, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append((hbfont.glyph_to_string(i.codepoint), i.cluster, x + pos.x_offset, pos.y_offset))
        x += pos.x_advance
    return out          # (in the line's order, left to right)


def _word_collisions(T, hbfont, word, marks_set, masks):
    """[(i, j)]: the shaped glyphs (indices) whose ink meets - one of them a mark."""
    def mask(n):
        if n not in masks:
            masks[n] = _mask(T, n)
        return masks[n]
    g = _shaped(hbfont, word)
    out = []
    for i in range(len(g)):
        for j in range(i + 1, len(g)):
            a, b = g[i], g[j]
            if a[0] not in marks_set and b[0] not in marks_set:
                continue
            ma, mb = mask(a[0]), mask(b[0])
            if ma is None or mb is None:
                continue
            if _touch(ma, mb, b[2] - a[2], b[3] - a[3]):
                out.append((i, j))
    return g, out


def fix_by_shaping(path, words: list[str], rounds: int = 6) -> str:
    """What the rules above miss - a mark set by Taamey D's own context rules: every word of
    Tanach shaped (HarfBuzz) and, where a mark still meets another glyph (Mordy, 2026-10-22:
    "remove all collisions"), a rule for exactly that word's letters and marks - the letters
    moved apart (the left-hand one's advance larger), or a mark meeting its own letter moved
    aside - by the least that clears it.  Again on those words, a few rounds."""
    import uharfbuzz as hb
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    if not words:
        return "no Tanach text in the library: not checked"
    T = TTFont(path)
    classes = getattr(T["GDEF"].table.GlyphClassDef, "classDefs", {})
    marks_set = {n for n, c in classes.items() if c == 3}
    masks: dict = {}
    todo, fixed, total = list(words), 0, None
    for _round in range(rounds):
        hbfont = hb.Font(hb.Face(hb.Blob(Path(path).read_bytes())))  # (in memory: the file is written again)
        rules = {}              # (backtrack, input, lookahead, kind) -> amount
        left_words = []
        for w in todo:
            g, pairs = _word_collisions(T, hbfont, w, marks_set, masks)
            if not pairs:
                continue
            left_words.append(w)
            logical = list(reversed(range(len(g))))     # (a right-to-left word: its glyphs' own order)
            for i, j in pairs:
                ci, cj = g[i][1], g[j][1]
                seq = [g[k][0] for k in logical]
                pos = {k: n for n, k in enumerate(logical)}
                if ci == cj:
                    # (a mark meeting its own letter or the other mark on it: moved aside)
                    m = j if g[j][0] in marks_set else i
                    other = i if m == j else j
                    # (aside, or - two marks over one letter - up / down, away from the letter)
                    T["glyf"][g[m][0]].recalcBounds(T["glyf"])
                    up = 1 if getattr(T["glyf"][g[m][0]], "yMin", 0) > 0 else -1
                    best = next(((dx, up * dy) for dx, dy in sorted(
                        ((dx, dy) for dx in range(-300, 301, 6) for dy in range(0, 301, 6)),
                        key=lambda v: v[0] ** 2 + v[1] ** 2)
                        if not _touch(_fat(masks[g[other][0]], NEIGHBOUR_GAP), masks[g[m][0]],
                                      g[m][2] + dx - g[other][2], g[m][3] + up * dy - g[other][3])), None)
                    if best and best != (0, 0):
                        n = pos[m]
                        key = (tuple(seq[:n]), seq[n], tuple(seq[n + 1:]), "x")
                        old = rules.get(key, (0, 0))
                        rules[key] = best if best[0] ** 2 + best[1] ** 2 > old[0] ** 2 + old[1] ** 2 else old
                    continue
                # (two clusters: the left-hand letter's advance larger)
                bases = {c: k for k, (name, c, *_r) in enumerate(g) if name not in marks_set}
                if ci not in bases or cj not in bases:
                    continue
                left_c = ci if g[bases[ci]][2] < g[bases[cj]][2] else cj
                lb = bases[left_c]
                moving = [k for k in (i, j) if g[k][1] != left_c]
                still = [k for k in (i, j) if g[k][1] == left_c]
                if len(moving) != 1 or len(still) != 1:
                    continue
                mv, st_ = moving[0], still[0]
                d = next((d for d in range(6, 601, 6) if not _touch(
                    _fat(masks[g[st_][0]], NEIGHBOUR_GAP), masks[g[mv][0]],
                    g[mv][2] + d - g[st_][2], g[mv][3] - g[st_][3])), None)
                if d is None:
                    continue
                n = pos[lb]
                key = (tuple(seq[:n]), seq[n], tuple(seq[n + 1:]), "adv")
                rules[key] = (max(rules.get(key, (0,))[0], d),)
        if total is None:
            total = len(left_words)
        if not rules:
            todo = left_words
            break
        fixed += len(rules)
        gpos = T["GPOS"].table
        lookups = gpos.LookupList.Lookup
        rev = T.getReverseGlyphMap()
        singles, subtables = {}, []
        for (before, glyph, after, kind), d in sorted(rules.items(), key=lambda kv: -sum(abs(v) for v in kv[1])):
            k = (kind, d)
            if k not in singles:
                value = {"XAdvance": d[0]} if kind == "adv" else {"XPlacement": d[0], "YPlacement": d[1]}
                lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                    {n: otl.buildValue(value) for n in T.getGlyphOrder()}, rev)], table="GPOS"))
                singles[k] = len(lookups) - 1
            st = ot.ChainContextPos()
            st.Format = 3
            st.BacktrackCoverage = [otl.buildCoverage([n], rev) for n in reversed(before)]
            st.InputCoverage = [otl.buildCoverage([glyph], rev)]
            st.LookAheadCoverage = [otl.buildCoverage([n], rev) for n in after]
            st.BacktrackGlyphCount = len(st.BacktrackCoverage)
            st.InputGlyphCount, st.LookAheadGlyphCount = 1, len(st.LookAheadCoverage)
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = 0, singles[k]
            st.PosLookupRecord, st.PosCount = [r], 1
            subtables.append(st)
        for i in range(0, len(subtables), 500):     # (a lookup holds only so many)
            chain = ot.Lookup()
            chain.LookupType, chain.LookupFlag = 8, 0
            chain.SubTable = subtables[i:i + 500]
            chain.SubTableCount = len(chain.SubTable)
            lookups.append(chain)
            for fr in gpos.FeatureList.FeatureRecord:
                if fr.FeatureTag == "mark":
                    fr.Feature.LookupListIndex.append(len(lookups) - 1)
                    fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        gpos.LookupList.LookupCount = len(lookups)
        T.save(path)
        T = TTFont(path)
        todo = left_words
    hbfont = hb.Font(hb.Face(hb.Blob(Path(path).read_bytes())))  # (in memory: the file is written again)
    still = [w for w in words if _word_collisions(T, hbfont, w, marks_set, masks)[1]]
    return (f"shaped every word of Tanach: {total} with a collision, {fixed} rules added; "
            f"{len(still)} left" + (f" ({' '.join(still[:8])})" if still else ""))


def _shva_na(path) -> None:
    """The shva na rule (scripts/add_shva_na.py: shva + varika -> Taamey D's shva na)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("add_shva_na", ROOT / "scripts" / "add_shva_na.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("  " + mod.make(Path(path)))
    print("  " + mod.resquare(Path(path)))


def _under_the_leg(path) -> None:
    """A lone mark under ר / ד under the leg, measured on these letters (make_frank_sofer.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("make_frank_sofer", ROOT / "scripts" / "make_frank_sofer.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    t = TTFont(path)
    print(f"  under the open space: {', '.join(mod.under_open_space(t))}; cholam over the vav: {mod.holam_male(t)}")
    print("  under the leg: " + ", ".join(mod.under_the_leg(t)))
    print(f"  clear of the cholam of וֹ: {mod.clear_of_holam(t)}")
    print(f"  nothing touching: {', '.join(mod.nothing_touching(t))}")
    t.save(path)


def _check_marks(path) -> None:
    """Every ta'am in its place (fonts/CANTILLATION.md)?"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("check_font_marks", ROOT / "scripts" / "check_font_marks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    problems = mod.check_font(Path(path))
    print(f"  ta'amim placement: {'every one in its place' if not problems else str(len(problems)) + ' problem(s)'}")
    for p in problems[:20]:
        print("   ", p)

if __name__ == "__main__":
    # (--base FILE: the font whose marks and their placement are kept - Taamey Frank CLM, or
    #  Frank Sofer; --out FILE: where to write)
    if "--base" in sys.argv:
        FRANK = Path(sys.argv[sys.argv.index("--base") + 1]).resolve()
    if "--ashkenaz" in sys.argv:
        OUT, FAMILY, SOURCE = ROOT / "fonts" / "SoferStamAshkenaz.ttf", "Sofer Stam Ashkenaz", "Stam Ashkenaz CLM"
    if "--out" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--out") + 1]).resolve()
    main(sys.argv[1])
