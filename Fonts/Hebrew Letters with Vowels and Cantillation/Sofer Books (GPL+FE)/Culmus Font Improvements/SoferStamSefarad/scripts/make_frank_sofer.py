"""Make "Frank Sofer": Ben Denckla's Taamey D - the maintained successor of Taamey Frank CLM,
with better placement of the ta'amim (Mordy, 2026-10-21: use Taamey D wherever Taamey Frank was
used).  Taamey D reserves its name, so the changed font has its own.

Mordy's changes (2026-10-21): the marks below closer to the letters (as Frank Ruehl's); placed
by each letter's shape under ר, ד (the leg), ו (the stroke) and ת (the open space), the cholam
centred over a vav; the kamatz katan Sofer's bold drop, hanging a little lower ("the 3/5 mix",
chosen from five); the shva na.

Taamey D is GPL-2 with the font exception (its license.txt, kept as
fonts/licenses/TAAMEY-D-LICENSE.txt); downloaded 2026-10-21 from
https://bdenckla.github.io/hbofonts/downloads/ (snapshot 0.931-hbofonts-42ca46e82f78).

    python scripts/make_frank_sofer.py <Taamey_D.ttf>     ->  fonts/FrankSofer.ttf
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fonts" / "FrankSofer.ttf"
FAMILY = "Frank Sofer"


def main(src: str) -> None:
    shutil.copyfile(src, OUT)
    OUT.chmod(0o644)
    # its kamatz katan (Mordy, 2026-10-21, from five shown: "the 3/5 mix"): Sofer's - the drop
    # drawn fuller and bolder - hanging a little lower on a longer stem
    import importlib.util
    spec = importlib.util.spec_from_file_location("aq", ROOT / "scripts" / "add_qamats_qatan.py")
    aq = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aq)
    print("  " + aq.make(OUT, lower=KATAN_LOWER))
    t = TTFont(OUT)
    print(f"  marks below raised on {raise_below(t)} letters")
    for rec in t["name"].names:
        if rec.nameID in (1, 16):
            rec.string = FAMILY
        elif rec.nameID in (3, 4, 6):
            text = rec.toUnicode()
            rec.string = text.replace("Taamey D", FAMILY).replace("Taamey_D", FAMILY.replace(" ", "")) \
                .replace("TaameyD", FAMILY.replace(" ", ""))
        elif rec.nameID == 0:
            rec.string = rec.toUnicode() + ("\n\nFrank Sofer: Taamey D (Ben Denckla, GPL-2 with the font exception) "
                                            "with the marks below raised closer to the letters and placed by each letter's shape (resh, dalet, vav, tav, the vav's cholam) by Sofer, 2026; renamed, as Taamey D's "
                                            "licence reserves its name.")
    t.save(OUT)
    print(f"{OUT.name}: {FAMILY}")
    _shva_na(OUT)
    t = TTFont(OUT)
    print(f"  under the open space: {', '.join(under_open_space(t))}; cholam over the vav: {holam_male(t)}")
    print(f"  under the leg: {', '.join(under_the_leg(t))}")
    print(f"  clear of the cholam of וֹ: {clear_of_holam(t)}")
    print(f"  nothing touching: {', '.join(nothing_touching(t))}")
    t.save(OUT)
    _check_marks(OUT)



KATAN_LOWER = 0.18


# How much closer the marks below come to their letter (Mordy, 2026-10-21: "rather it closer"):
# Taamey D hangs them 0.095 em under the line, Frank Ruehl 0.058 - raised by the difference
RAISE = 0.035


def raise_below(t: TTFont) -> int:
    """Bring the marks below (nikud and ta'amim) up toward the letter, as close as Frank
    Ruehl's: each letter's anchor for them on the line (not the letters with a tail, whose
    anchors are elsewhere) goes up by RAISE."""
    dy = round(RAISE * t["head"].unitsPerEm)
    done = set()
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                a = rec.BaseAnchor[c]
                if a is not None and a.YCoordinate == 0:
                    a.YCoordinate = dy
                    done.add(name)
    return len(done)


# Where Frank Ruehl centres a mark under these letters: its share of the letter's ink width,
# from the right (measured with HarfBuzz, 2026-10-21; Taamey D: 0.5, the middle)
UNDER_LEG = {"resh": 0.20, "dalet": 0.30, "vav": None}     # (ו: under its stroke, measured - Mordy, 2026-10-21)


def _runs(t: TTFont, name: str, y: float, step: int = 4) -> list[tuple[int, int]]:
    """The stretches of ink across the glyph at height ``y``, right to left in x order."""
    from fontTools.pens.pointInsidePen import PointInsidePen
    gs, g = t.getGlyphSet(), t["glyf"][name]
    g.recalcBounds(t["glyf"])
    runs, start, last = [], None, None
    for x in range(g.xMin - step, g.xMax + 2 * step, step):
        pen = PointInsidePen(gs, (x, y))
        gs[name].draw(pen)
        if pen.getResult():
            start = x if start is None else start
            last = x
        elif start is not None:
            runs.append((start, last))
            start = None
    return runs


def _foot(t: TTFont, name: str) -> list[tuple[int, int]]:
    """The letter's ink just above the line it stands on."""
    g = t["glyf"][name]
    g.recalcBounds(t["glyf"])
    return _runs(t, name, max(g.yMin, 0) + 0.08 * (g.yMax - max(g.yMin, 0)))


def under_open_space(t: TTFont) -> list[str]:
    """The marks below ת (a vowel alone, or with its ta'am - they move together) centred under
    the open space between its legs, not under the whole letter (Mordy, 2026-10-21)."""
    done = []
    for lk in t["GPOS"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos":
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if not (name == "tav" or name.startswith(("tav.", "tavdagesh"))) or rec.BaseAnchor[c] is None:
                    continue
                runs = _foot(t, name)
                if len(runs) >= 2:
                    rec.BaseAnchor[c].XCoordinate = round((runs[0][1] + runs[-1][0]) / 2)
                    done.append(name)
    return done


def holam_male(t: TTFont) -> bool:
    """וֹ: the cholam centred over the vav, not over its stroke (Mordy, 2026-10-21)."""
    glyf = t["glyf"]
    if "vavxolam" not in glyf.glyphs or not glyf["vavxolam"].isComposite():
        return False
    comps = glyf["vavxolam"].components
    vav = next(c for c in comps if c.glyphName == "vav")
    dot = next(c for c in comps if c.glyphName == "xolam")
    glyf["vav"].recalcBounds(glyf)
    glyf["xolam"].recalcBounds(glyf)
    centre = vav.x + (glyf["vav"].xMin + glyf["vav"].xMax) / 2
    dot.x = round(centre - (glyf["xolam"].xMin + glyf["xolam"].xMax) / 2)
    glyf["vavxolam"].recalcBounds(glyf)
    return True


def under_the_leg(t: TTFont) -> list[str]:
    """A lone mark under ר or ד (and their forms with dagesh) moves from the middle to under
    the leg; a vowel and a ta'am under the same letter stay where Taamey D sets them, side by
    side (Mordy, 2026-10-21: moving them both made them touch).  A GPOS lookup run after the
    marks are attached: for each letter, "the letter, one mark below" moves the mark, and
    "the letter, two marks below" (tried first) leaves them.  Done again on a font that has it
    already (the Sefer Torah fonts get Frank Sofer's, measured on Frank's letters), it is
    replaced.  Returns the letters done."""
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot

    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    lookups = gpos.LookupList.Lookup
    # (the marks below, and each letter's anchor for them: Taamey D's mark-to-base lookup)
    below, anchors = None, {}
    for lk in lookups:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if not hasattr(st, "BaseCoverage") or below is not None and anchors:
                continue
            cls = {r.Class for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if g in ("qamats", "tipxa")}
            if len(cls) != 1:
                continue
            c = cls.pop()
            below = [g for g, r in zip(st.MarkCoverage.glyphs, st.MarkArray.MarkRecord) if r.Class == c]
            for name, rec in zip(st.BaseCoverage.glyphs, st.BaseArray.BaseRecord):
                if rec.BaseAnchor[c] is not None:
                    anchors[name] = rec.BaseAnchor[c].XCoordinate
    # (a font that has it already: its lookups are the last ones, taken out first)
    mark = [fr for fr in gpos.FeatureList.FeatureRecord if fr.FeatureTag == "mark"]
    def ours(lk):
        return lk.LookupType == 8 and all(
            getattr(st, "Format", 0) == 3 and st.BacktrackCoverage
            and all(g.startswith(tuple(UNDER_LEG)) for g in st.BacktrackCoverage[0].glyphs)
            for st in lk.SubTable)
    old = sorted({i for fr in mark for i in fr.Feature.LookupListIndex if ours(lookups[i])})
    if old:
        nested = [r.LookupListIndex for i in old for st in lookups[i].SubTable for r in st.PosLookupRecord]
        first = min(old + nested)
        drop = set(range(first, len(lookups)))
        for fr in gpos.FeatureList.FeatureRecord:
            fr.Feature.LookupListIndex = [i for i in fr.Feature.LookupListIndex if i not in drop]
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
        del lookups[first:]
    # the filtering set: the marks below only (the dagesh and the marks above are looked past)
    if gdef.Version < 0x00010002:
        gdef.Version = 0x00010002
    if getattr(gdef, "MarkGlyphSetsDef", None) is None:
        gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
        gdef.MarkGlyphSetsDef.Coverage = []
    rev = t.getReverseGlyphMap()
    # (every mark under the line, Taamey D's other ones too - the dehi, set apart at the
    #  letter's right: it is a second mark under the letter as much as a vowel's ta'am is;
    #  the hbofonts collision check found the vowel moved into it, Mordy 2026-10-22)
    glyph_class = getattr(gdef.GlyphClassDef, "classDefs", {}) if gdef.GlyphClassDef else {}
    under = sorted(set(below) | {g for g, c in glyph_class.items() if c == 3 and g in glyf.glyphs
                                 and _bottom(glyf, g) < 0 and _top(glyf, g) <= 0})
    taam_under = sorted({g for cp, g in t.getBestCmap().items() if 0x0591 <= cp <= 0x05AF and g in under})
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(under, rev))
    sets.MarkSetCount = len(sets.Coverage)
    fset = sets.MarkSetCount - 1
    shifts = {}
    for name, x in anchors.items():
        key = next((k for k in UNDER_LEG if name == k or name.startswith(k + "dagesh")), None)
        if key is None:
            continue
        g = glyf[name]
        g.recalcBounds(glyf)
        if UNDER_LEG[key] is None:          # (under the stroke: the middle of the ink at the foot)
            runs = _foot(t, name)
            if not runs:
                continue
            dx = round((runs[-1][0] + runs[-1][1]) / 2 - x)
        else:
            dx = round(g.xMax - UNDER_LEG[key] * (g.xMax - g.xMin) - x)
        if dx:
            shifts.setdefault(dx, []).append(name)
    if not shifts:
        return []
    subtables, moves = [], []
    for dx, bases in sorted(shifts.items()):
        single = otl.buildLookup([otl.buildSinglePosSubtable({g: otl.buildValue({"XPlacement": dx}) for g in below}, rev)],
                                 table="GPOS")
        lookups.append(single)
        moves.append((bases, len(lookups) - 1))
    for bases, _ in moves:              # (a vowel and a ta'am: left as they are)
        subtables.append(_chain(otl, ot, rev, bases, under, 2, None))
    for bases, _ in moves:              # (a ta'am under the letter before - the יּ's tevir in
        for back in (1, 2):             #  וַיֵּ֛רֶד: moved under the leg the vowel touched it; left)
            subtables.append(_chain(otl, ot, rev, bases, below, 1, None, [taam_under] + [under] * (back - 1)))
    for bases, index in moves:          # (one mark: under the leg)
        subtables.append(_chain(otl, ot, rev, bases, below, 1, index))
    chain = ot.Lookup()
    chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
    chain.SubTable, chain.SubTableCount = subtables, len(subtables)
    lookups.append(chain)
    gpos.LookupList.LookupCount = len(lookups)
    for fr in mark:
        fr.Feature.LookupListIndex.append(len(lookups) - 1)
        fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    return sorted(g for bases, _ in moves for g in bases)


CLEAR_OF_HOLAM = ("pashta", "tsinor")    # (the marks set at the top of a final וֹ)
HOLAM_GAP = 50                           # their least room from the centred cholam, font units


def clear_of_holam(t: TTFont) -> dict[str, int]:
    """A pashta or a zarka on וֹ moved left, just clear of the cholam - which is centred over the
    vav now (holam_male), right under where Taamey D puts them (the hbofonts collision check:
    אֹתוֹ֙, 300 words; Mordy, 2026-10-22).  A GPOS lookup after under_the_leg's (a rebuild drops
    both).  Returns each mark's move."""
    import math
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    if "vavxolam" not in glyf.glyphs or not glyf["vavxolam"].isComposite():
        return {}
    dot = next(c for c in glyf["vavxolam"].components if c.glyphName == "xolam")
    holam = [(x + dot.x, y + dot.y) for x, y in _points(t, "xolam")]
    moves = {}
    for lk in gpos.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if type(st).__name__ != "MarkBasePos" or "vavxolam" not in st.BaseCoverage.glyphs:
                continue
            base = st.BaseArray.BaseRecord[st.BaseCoverage.glyphs.index("vavxolam")]
            for m in CLEAR_OF_HOLAM:
                if m in moves or m not in st.MarkCoverage.glyphs:
                    continue
                rec = st.MarkArray.MarkRecord[st.MarkCoverage.glyphs.index(m)]
                a = base.BaseAnchor[rec.Class]
                if a is None:
                    continue
                ox, oy = a.XCoordinate - rec.MarkAnchor.XCoordinate, a.YCoordinate - rec.MarkAnchor.YCoordinate
                pts = _points(t, m)

                def room(dx):
                    return min(math.dist((x + ox + dx, y + oy), q) for x, y in pts for q in holam)
                dx = next((-d for d in range(0, 401, 8) if room(-d) >= HOLAM_GAP), 0)
                if dx:
                    moves[m] = dx
    if not moves:
        return {}
    rev = t.getReverseGlyphMap()
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage(list(moves), rev))
    sets.MarkSetCount = len(sets.Coverage)
    lookups = gpos.LookupList.Lookup
    subtables = []
    for m, dx in moves.items():
        lookups.append(otl.buildLookup([otl.buildSinglePosSubtable({m: otl.buildValue({"XPlacement": dx})}, rev)],
                                       table="GPOS"))
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage = [otl.buildCoverage(["vavxolam"], rev)]
        st.InputCoverage = [otl.buildCoverage([m], rev)]
        st.LookAheadCoverage = []
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 1, 1, 0
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, len(lookups) - 1
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
    return moves


RAFE_GAP = 40                       # between a rafe and a ta'am set over it


def nothing_touching(t: TTFont) -> list[str]:
    """The collisions Taamey D has itself (Mordy, 2026-10-22: "remove all collisions"), found by
    shaping every word of Tanach: a ta'am over a rafe (בָֿ֝֗ם, Tehillim 68:18) raised above it.
    (The Ten Commandments' kamatz and patach under one letter, the two readings, are kept apart
    by Taamey D itself: MAM puts a CGJ, U+034F, between them.)  GPOS lookups after the others."""
    from fontTools.otlLib import builder as otl
    from fontTools.ttLib.tables import otTables as ot
    gpos, gdef, glyf = t["GPOS"].table, t["GDEF"].table, t["glyf"]
    rev = t.getReverseGlyphMap()
    lookups = gpos.LookupList.Lookup
    sets = gdef.MarkGlyphSetsDef
    done, chains = [], []

    def single(values):
        lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
            {g: otl.buildValue(v) for g, v in values.items()}, rev)], table="GPOS"))
        return len(lookups) - 1

    def rule(alternatives, fset):
        """One chained lookup: each (inputs, moves) tried in turn, the first that matches."""
        chain = ot.Lookup()
        chain.LookupType, chain.LookupFlag, chain.MarkFilteringSet = 8, 0x0010, fset
        chain.SubTable = [subtable(i, m) for i, m in alternatives]
        chain.SubTableCount = len(chain.SubTable)
        chains.append(chain)

    def subtable(inputs, moves):
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage, st.LookAheadCoverage = [], []
        st.InputCoverage = [otl.buildCoverage(c, rev) for c in inputs]
        st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = 0, len(inputs), 0
        st.PosLookupRecord = []
        for i, index in moves:
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = i, index
            st.PosLookupRecord.append(r)
        st.PosCount = len(st.PosLookupRecord)
        return st

    def filter_set(glyphs):
        sets.Coverage.append(otl.buildCoverage(sorted(glyphs), rev))
        sets.MarkSetCount = len(sets.Coverage)
        return sets.MarkSetCount - 1

    # a ta'am over a rafe: raised clear of it
    if "rafe" in glyf.glyphs:
        glyf["rafe"].recalcBounds(glyf)
        top = glyf["rafe"].yMax
        above = {}
        for cp, g in t.getBestCmap().items():
            if 0x0591 <= cp <= 0x05AF and g in glyf.glyphs and _bottom(glyf, g) > 900:
                dy = top + RAFE_GAP - _bottom(glyf, g)
                if dy > 0:
                    above.setdefault(dy, []).append(g)
        if above:
            marks = sorted(g for gs in above.values() for g in gs)
            fset = filter_set(["rafe"] + marks)
            up = single({g: {"YPlacement": dy} for dy, gs in above.items() for g in gs})
            # (a rafe and up to three ta'amim over one letter - בָֿ֝֗ם has a geresh muqdam too)
            rule([([["rafe"]] + [marks] * k, [(i, up) for i in range(1, k + 1)]) for k in (3, 2, 1)], fset)
            done.append(f"{sum(len(g) for g in above.values())} ta'amim raised over a rafe")
    for chain in chains:
        lookups.append(chain)
        for fr in gpos.FeatureList.FeatureRecord:
            if fr.FeatureTag == "mark":
                fr.Feature.LookupListIndex.append(len(lookups) - 1)
                fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)
    gpos.LookupList.LookupCount = len(lookups)
    return done


def _points(t: TTFont, name: str, step: int = 6) -> list[tuple[float, float]]:
    """Points along a glyph's outline (its curves sampled)."""
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

        def _qCurveToOne(self, a, b):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s = i / step
                self.p.append(((1 - s) ** 2 * x0 + 2 * (1 - s) * s * a[0] + s * s * b[0],
                               (1 - s) ** 2 * y0 + 2 * (1 - s) * s * a[1] + s * s * b[1]))
            self.cur = b

        def _curveToOne(self, a, b, c):
            x0, y0 = self.cur
            for i in range(1, step + 1):
                s, m = i / step, 1 - i / step
                self.p.append((m ** 3 * x0 + 3 * m * m * s * a[0] + 3 * m * s * s * b[0] + s ** 3 * c[0],
                               m ** 3 * y0 + 3 * m * m * s * a[1] + 3 * m * s * s * b[1] + s ** 3 * c[1]))
            self.cur = c
    gs = t.getGlyphSet()
    pen = Pts(gs)
    gs[name].draw(pen)
    return pen.p


def _bottom(glyf, name):
    glyf[name].recalcBounds(glyf)
    return getattr(glyf[name], "yMin", 0)


def _top(glyf, name):
    glyf[name].recalcBounds(glyf)
    return getattr(glyf[name], "yMax", 0)


def _chain(otl, ot, rev, bases, below, count, index, before=()):
    """"the letter (after ``before``, nearest last), ``count`` marks below": move the first by
    lookup ``index`` (None: leave them)."""
    st = ot.ChainContextPos()
    st.Format = 3
    st.BacktrackCoverage = [otl.buildCoverage(bases, rev)] + [otl.buildCoverage(c, rev) for c in reversed(before)]
    st.InputCoverage = [otl.buildCoverage(below, rev)] * count
    st.LookAheadCoverage = []
    st.BacktrackGlyphCount, st.InputGlyphCount, st.LookAheadGlyphCount = len(st.BacktrackCoverage), count, 0
    recs = []
    if index is not None:
        r = ot.PosLookupRecord()
        r.SequenceIndex, r.LookupListIndex = 0, index
        recs.append(r)
    st.PosLookupRecord, st.PosCount = recs, len(recs)
    return st


def _shva_na(path) -> None:
    """The shva na rule (scripts/add_shva_na.py: shva + varika -> Taamey D's shva na)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("add_shva_na", ROOT / "scripts" / "add_shva_na.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print("  " + mod.make(Path(path)))
    print("  " + mod.resquare(Path(path)))


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
    main(sys.argv[1])
