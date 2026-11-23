"""Every meteg that still touches something (scripts/check_meteg.py: over the siddur and the
Tanach) moved clear of it, in the fonts offered for texts with ta'amim or metegs (Mordy,
2026-10-25: "can you fix the other ones?").  For each place a meteg touches, a rule for exactly
that meteg's letter and the letters beside it (with all their marks): the meteg moved aside or
down by the least that clears it, or else the two letters set apart.  Shaped again and checked,
a few rounds, until no meteg touches anything.

Run after scripts/place_meteg.py (it changes the fonts in place); the Sefer Torah fonts are
cleared by their builder (make_stam_sefarad.py) the same way.  Ezra SIL is never changed (its
licence reserves its name for the unchanged font).

    .venv/Scripts/python scripts/clear_meteg.py [font files ...]
"""
from __future__ import annotations

import io
import sys
from collections import Counter
from pathlib import Path

import uharfbuzz as hb
from fontTools.otlLib import builder as otl
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot

sys.path.insert(0, str(Path(__file__).parent))
from check_meteg import CLEAR, FONTS, Ink, siddur_words, tanach_words  # noqa: E402

DEFAULT = ["SoferStamSefarad.ttf", "SoferStamAshkenaz.ttf", "ShofarRegular.ttf", "ShofarDemi-Bold.ttf",
           "TaameyAshkenaz-Medium.ttf", "TaameyAshkenaz-Bold.ttf", "TaameyDavidCLM-Medium.ttf",
           "TaameyDavidCLM-Bold.ttf", "KeterYG-Medium.ttf", "KeterYG-Bold.ttf", "KeterAramTsova.ttf"]
MOVE_X = 0.16          # (of the em: the farthest a meteg is moved aside)
MOVE_Y = 0.10          # (of the em: the farthest it is moved down)


def _shape(font: hb.Font, word: str):
    buf = hb.Buffer()
    buf.add_str(word)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    out, pen = [], 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        out.append([info.codepoint, info.cluster, pen + pos.x_offset, pos.y_offset])
        pen += pos.x_advance
    return out      # (left to right on the line)


def _cells(ink: Ink, g):
    s = ink.step
    return {(x + g[2] // s, y + g[3] // s) for x, y in ink.cells(g[0])}


def _touching(ink: Ink, placed, meteg: int, near: int) -> list[int]:
    """The metegs (indices) that touch, or come within ``near`` cells of, another glyph."""
    out = []
    for i, g in enumerate(placed):
        if g[0] != meteg:
            continue
        mine = _cells(ink, g)
        grown = {(x + a, y + b) for x, y in mine for a in range(-near, near + 1) for b in range(-near, near + 1)}
        if any(grown & _cells(ink, h) for j, h in enumerate(placed) if j != i):
            out.append(i)
    return out


def _classes(ink: Ink) -> dict:
    gdef = ink.t["GDEF"].table if "GDEF" in ink.t else None
    return getattr(getattr(gdef, "GlyphClassDef", None), "classDefs", {}) or {}


def _fix(ink: Ink, placed, i: int, meteg: int, near: int):
    """('x' | 'y' | 'adv', glyph index the rule is on, amount) clearing meteg i, or None."""
    s = ink.step
    others = [h for j, h in enumerate(placed) if j != i]
    other_cells = set().union(*(_cells(ink, h) for h in others)) if others else set()

    def clear(dx, dy):
        g = placed[i]
        mine = _cells(ink, [g[0], g[1], g[2] + dx, g[3] + dy])
        grown = {(x + a, y + b) for x, y in mine for a in range(-near, near + 1) for b in range(-near, near + 1)}
        return not grown & other_cells
    for d in sorted(range(s, round(MOVE_X * ink.upem) + 1, s), key=abs):
        for dx in (d, -d):
            if clear(dx, 0):
                return "x", i, dx
    for dy in range(s, round(MOVE_Y * ink.upem) + 1, s):
        if clear(0, -dy):
            return "y", i, -dy
    # (else the mark it touches on its own letter moved aside - the chirik after a CGJ, which
    #  Keter YG and Taamey David leave beside the meteg instead of under the letter)
    classes = _classes(ink)
    for j, h in enumerate(placed):
        if j == i or h[1] != placed[i][1] or classes.get(ink.order[h[0]]) != 3:
            continue
        rest = set().union(*(_cells(ink, x) for k, x in enumerate(placed) if k != j)) if len(placed) > 1 else set()
        for d in sorted(range(s, round(0.4 * ink.upem) + 1, s), key=abs):
            for dx in (-d, d):
                mine = _cells(ink, [h[0], h[1], h[2] + dx, h[3]])
                grown = {(x + a, y + b) for x, y in mine for a in range(-near, near + 1) for b in range(-near, near + 1)}
                if not grown & rest:
                    moved = [list(x) for x in placed]
                    moved[j][2] += dx
                    if i not in _touching(ink, moved, meteg, near):
                        return "x", j, dx
    # (else the two letters set apart: the cluster to the left - a higher cluster number, the
    #  line being right to left - and all after it moved left; the rule on its letter's advance)
    c = placed[i][1]
    left = min((h[1] for h in placed if h[1] > c), default=None)
    for c2 in (left, c):
        if c2 is None:
            continue
        base = next((j for j, h in enumerate(placed) if h[1] == c2 and h[0] != meteg
                     and _classes(ink).get(ink.order[h[0]]) != 3), None)
        if base is None:
            continue
        for d in range(s, round(0.25 * ink.upem) + 1, s):
            moved = [[h[0], h[1], h[2] - d if h[1] >= c2 else h[2], h[3]] for h in placed]
            if i not in _touching(ink, moved, meteg, near):
                return "adv", base, d
    return None


GAP = 0.045           # (of the em: between the marks under one letter, as place_meteg.py sets the meteg)
LEG = 0.03            # (of the em: the least room between those marks and the letter's own ink - ק's leg)


def arrange(path: Path, words: Counter, rounds: int = 4) -> str:
    """The marks under one letter set in a row (``_arrange``), again from where they land until
    each is in its place: a mark that hangs from the one before it (the meteg from its vowel,
    in some fonts the chirik from the meteg) moves with it."""
    total = 0
    for _ in range(rounds):
        n = _arrange(path, words)
        if not n:
            break
        total += n
    return f"{path.name}: the marks under one letter set in a row ({total} rules)"


def _arrange(path: Path, words: Counter) -> int:
    """The marks under one letter set in a row, as Frank Sofer sets them (Mordy, 2026-10-25:
    Keter YG lost the chirik of יְרוּשָׁלָֽ͏ִם under its kamatz and put the meteg on the kamatz's
    right; Keter Aram Tsova's meteg under ק stood past the leg): from right to left the vowel, the
    meteg, and a second vowel after a CGJ, GAP apart; the first vowel where the font puts it, the
    row moved right only as far as it must to clear the letter's own ink (ק's leg).  For every
    letter with a meteg and a vowel, or two vowels, under it (not with a ta'am below too) in the
    siddur and MAM: a rule for exactly that letter and its marks."""
    t = TTFont(io.BytesIO(path.read_bytes()))
    font = hb.Font(hb.Face(hb.Blob(path.read_bytes())))
    ink = Ink(path)
    order, cmap, glyf = ink.order, ink.t.getBestCmap(), t["glyf"]
    meteg = font.get_nominal_glyph(0x05BD)
    cgj = cmap.get(0x034F, "space")
    taamim = {cmap[c] for c in range(0x0591, 0x05B0) if c in cmap}
    classes = _classes(ink)
    s, upem = ink.step, ink.upem
    gap, leg = round(GAP * upem), round(LEG * upem)

    def bounds(name):
        g = glyf[name]
        g.recalcBounds(glyf)
        return (g.xMin, g.xMax) if getattr(g, "numberOfContours", 0) else None
    rules = {}
    for w, _n in words.most_common():
        placed = _shape(font, w)
        for c in sorted({g[1] for g in placed}):
            idx = [k for k in reversed(range(len(placed))) if placed[k][1] == c]     # (the word's order)
            names = [cgj if order[placed[k][0]] == "space" else order[placed[k][0]] for k in idx]
            base = [k for k in idx if classes.get(order[placed[k][0]]) != 3 and order[placed[k][0]] != "space"]
            below = [k for k in idx if classes.get(order[placed[k][0]]) == 3
                     and ink.cells(placed[k][0]) and max(y for _x, y in ink.cells(placed[k][0])) * s + placed[k][3] < 0]
            if len(base) != 1 or len(below) < 2 or any(order[placed[k][0]] in taamim for k in below):
                continue
            if placed[below[0]][0] == meteg or not any(placed[k][0] == meteg for k in below) and cgj not in names:
                continue
            key = tuple(names)
            if key in rules:
                continue
            # (the row, right to left; each mark's ink edges where it is now)
            now = {k: (placed[k][2] + bounds(order[placed[k][0]])[0], placed[k][2] + bounds(order[placed[k][0]])[1])
                   for k in below}
            want, right = {}, now[below[0]][1]
            for k in below:
                width = now[k][1] - now[k][0]
                want[k] = right - width
                right = want[k] - gap
            # (clear of the letter's own ink under the line, its leg - beside it, not under its
            #  tip either: the whole row moved right as far as it must)
            b = placed[base[0]]
            near = max(1, leg // s)
            legs = {x + b[2] // s + a for x, y in ink.cells(b[0]) if y * s < -0.1 * upem
                    for a in range(-near, near + 1)}     # (a leg going down, not a base's overshoot)
            shift = 0
            while shift < 0.3 * upem and any(
                    {x + (placed[k][2] + want[k] - now[k][0] + shift) // s for x, _y in ink.cells(placed[k][0])} & legs
                    for k in below):
                shift += s
            moves = [(idx.index(k), round(want[k] - now[k][0] + shift)) for k in below]
            moves = [(i, d) for i, d in moves if abs(d) >= 0.02 * upem]     # (a hair's difference left)
            if moves:
                rules[key] = moves
    if not rules:
        return 0
    gpos = t["GPOS"].table
    lookups = gpos.LookupList.Lookup
    rev = t.getReverseGlyphMap()
    singles, subtables = {}, []
    for key, moves in rules.items():
        st = ot.ChainContextPos()
        st.Format = 3
        st.BacktrackCoverage, st.LookAheadCoverage = [], []
        st.BacktrackGlyphCount = st.LookAheadGlyphCount = 0
        st.InputCoverage = [otl.buildCoverage([n], rev) for n in key]
        st.InputGlyphCount = len(key)
        st.PosLookupRecord = []
        for i, d in moves:
            k = (key[i], d)
            if k not in singles:
                lookups.append(otl.buildLookup([otl.buildSinglePosSubtable(
                    {key[i]: otl.buildValue({"XPlacement": d})}, rev)], table="GPOS"))
                singles[k] = len(lookups) - 1
            r = ot.PosLookupRecord()
            r.SequenceIndex, r.LookupListIndex = i, singles[k]
            st.PosLookupRecord.append(r)
        st.PosCount = len(st.PosLookupRecord)
        subtables.append(st)
    for i in range(0, len(subtables), 500):
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
    buf = io.BytesIO()
    t.save(buf)
    t.close()
    path.write_bytes(buf.getvalue())
    return len(rules)


def clear(path: Path, words: Counter, rounds: int = 6) -> str:
    """The rules added to the font at ``path``; what is left touching."""
    first, added = None, 0
    todo = list(words)
    for _ in range(rounds):
        font = hb.Font(hb.Face(hb.Blob(path.read_bytes())))
        ink = Ink(path)
        meteg = font.get_nominal_glyph(0x05BD)
        near = max(1, round(CLEAR * ink.upem / ink.step))
        cgj = ink.t.getBestCmap().get(0x034F, "space")
        rules, left = {}, []
        for w in todo:
            placed = _shape(font, w)
            bad = _touching(ink, placed, meteg, near)
            if not bad:
                continue
            left.append(w)
            n = len(placed)
            logical = list(reversed(range(n)))          # (the line's order back to the word's)
            names = [ink.order[placed[k][0]] for k in logical]
            if "͏" in w:
                # (a CGJ is shown as a blank glyph only after the positioning: the rule is on its own)
                names = [cgj if n == "space" else n for n in names]
            pos = {k: m for m, k in enumerate(logical)}
            clusters = sorted({g[1] for g in placed})
            for i in bad:
                got = _fix(ink, placed, i, meteg, near)
                if got is None:
                    continue
                kind, on, amount = got
                # (the context: the letters on either side of the meteg's own, with their marks)
                c = clusters.index(placed[i][1])
                keep = set(clusters[max(0, c - 1):c + 2])
                span = [m for m, k in enumerate(logical) if placed[k][1] in keep]
                lo, hi, at = span[0], span[-1], pos[on]
                key = (tuple(names[lo:at]), names[at], tuple(names[at + 1:hi + 1]), kind)
                if abs(amount) > abs(rules.get(key, 0)):
                    rules[key] = amount
        if first is None:
            first = len(left)
        todo = left
        if not rules:
            break
        added += len(rules)
        _add(path, rules)
    font = hb.Font(hb.Face(hb.Blob(path.read_bytes())))
    ink = Ink(path)
    meteg = font.get_nominal_glyph(0x05BD)
    near = max(1, round(CLEAR * ink.upem / ink.step))
    still = [w for w in todo if _touching(ink, _shape(font, w), meteg, near)]
    return (f"{path.name}: {first} words with a meteg touching, {added} rules; {len(still)} left"
            + (f" ({' '.join(still[:8])})" if still else ""))


def _add(path: Path, rules: dict) -> None:
    t = TTFont(io.BytesIO(path.read_bytes()))
    gpos = t["GPOS"].table
    lookups = gpos.LookupList.Lookup
    rev = t.getReverseGlyphMap()
    singles, subtables = {}, []
    for (before, glyph, after, kind), d in sorted(rules.items(), key=lambda kv: -abs(kv[1])):
        k = (kind, d, glyph)
        if k not in singles:
            value = {"x": {"XPlacement": d}, "y": {"YPlacement": d}, "adv": {"XAdvance": d}}[kind]
            lookups.append(otl.buildLookup([otl.buildSinglePosSubtable({glyph: otl.buildValue(value)}, rev)],
                                           table="GPOS"))
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
    for i in range(0, len(subtables), 500):         # (a lookup holds only so many)
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
    buf = io.BytesIO()
    t.save(buf)
    t.close()
    path.write_bytes(buf.getvalue())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    words = siddur_words()
    words.update(tanach_words())
    for f in sys.argv[1:] or DEFAULT:
        if f not in ("SoferStamSefarad.ttf", "SoferStamAshkenaz.ttf"):     # (Frank Sofer's own order kept)
            print(arrange(FONTS / f, words), flush=True)
        print(clear(FONTS / f, words), flush=True)
