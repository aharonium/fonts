"""Give every font a shva na (Mordy, 2026-10-21: "I want shva nas on our fonts"): the shva with
its two dots drawn as small squares, as Taamey D (Frank Sofer) draws it.

The text marks a shva na with U+05C8 (Unicode's, 2026: Phonetic MAM's) - or with a varika after it (U+FB1E, as Wikitext's Miqra according to the
Masorah does where the Aleppo Codex has a chataf); each font gets a "shevana" glyph placed like
its shva, and a rule (ccmp, a ligature that looks past the other marks on the letter) that turns
the shva and the varika after it into the shva na.  A font without a varika of its own gets an
empty one.  Frank Sofer and the Sefer Torah fonts keep Taamey D's own shva na glyph.

Not Ezra SIL: its licence reserves its name for the unchanged font (its varika is hidden by the
templates instead, so it prints a plain shva).

    python scripts/add_shva_na.py        (changes the files in fonts/; a font done already is left)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from fontTools.otlLib import builder as otl
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables as ot

FONTS = Path(__file__).resolve().parents[1] / "fonts"
SKIP = {"SILEOT.ttf", "DejaVuSans.ttf"}
SQUARE = 1.0             # (a square's side, by the dot's width: the dot squared, not enlarged - Mordy,
                         #  2026-10-21; Taamey D's are bigger, 192 for a dot of 140, redrawn by resquare)


def files() -> list[str]:
    reg = json.loads((FONTS / "fonts.json").read_text(encoding="utf-8"))["fonts"]
    out = []
    for e in reg.values():
        for k in ("regular", "bold", "italic", "bolditalic"):
            f = e.get(k)
            if f and f.endswith(".ttf") and f not in SKIP and f not in out:
                if 0x05B0 in TTFont(FONTS / f).getBestCmap():
                    out.append(f)
    return out


def _squares(t: TTFont, sheva: str):
    """The shva's dots as squares, each about its dot's centre."""
    glyf = t["glyf"]
    coords, ends, _ = glyf[sheva].getCoordinates(glyf)
    pen, start = TTGlyphPen(None), 0
    for end in ends:
        pts = coords[start:end + 1]
        start = end + 1
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        h = (max(xs) - min(xs)) * SQUARE / 2
        # (clockwise, as TrueType's outer contours)
        for i, (x, y) in enumerate(((cx - h, cy - h), (cx - h, cy + h), (cx + h, cy + h), (cx + h, cy - h))):
            (pen.moveTo if i == 0 else pen.lineTo)((round(x), round(y)))
        pen.closePath()
    return pen.glyph()


def _add_glyph(t: TTFont, name: str, glyph, advance: tuple[int, int]) -> None:
    order = t.getGlyphOrder() + [name]
    t["glyf"].glyphs[name] = glyph
    t["glyf"].glyphOrder = order
    t["hmtx"].metrics[name] = advance
    t.setGlyphOrder(order)
    t["maxp"].numGlyphs = len(order)


def _as_mark_like(t: TTFont, new: str, like: str) -> None:
    """Give ``new`` the shva's mark class and its place in every mark lookup."""
    gdef = t["GDEF"].table
    gdef.GlyphClassDef.classDefs[new] = 3
    if gdef.MarkAttachClassDef and like in gdef.MarkAttachClassDef.classDefs:
        gdef.MarkAttachClassDef.classDefs[new] = gdef.MarkAttachClassDef.classDefs[like]
    gid = t.getGlyphID
    for lookup in t["GPOS"].table.LookupList.Lookup:
        for st in lookup.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for cov_attr, arr_attr, rec_attr in (("MarkCoverage", "MarkArray", "MarkRecord"),
                                                 ("Mark1Coverage", "Mark1Array", "MarkRecord"),
                                                 ("Mark2Coverage", "Mark2Array", "Mark2Record")):
                cov = getattr(st, cov_attr, None)
                if cov is None or like not in cov.glyphs or new in cov.glyphs:
                    continue
                arr = getattr(st, arr_attr)
                recs = getattr(arr, rec_attr)
                pairs = list(zip(cov.glyphs, recs)) + [(new, copy.deepcopy(recs[cov.glyphs.index(like)]))]
                pairs.sort(key=lambda p: gid(p[0]))
                cov.glyphs = [p[0] for p in pairs]
                setattr(arr, rec_attr, [p[1] for p in pairs])
                setattr(arr, rec_attr.replace("Record", "Count"), len(pairs))


def _ligature(t: TTFont, sheva: str, varika: str, shevana: str) -> None:
    """ccmp: shva + varika -> shva na, looking past the letter's other marks."""
    gdef = t["GDEF"].table
    if gdef.Version < 0x00010002:
        gdef.Version = 0x00010002
    if getattr(gdef, "MarkGlyphSetsDef", None) is None:
        gdef.MarkGlyphSetsDef = ot.MarkGlyphSetsDef()
        gdef.MarkGlyphSetsDef.MarkSetTableFormat = 1
        gdef.MarkGlyphSetsDef.Coverage = []
    sets = gdef.MarkGlyphSetsDef
    sets.Coverage.append(otl.buildCoverage([sheva, varika], t.getReverseGlyphMap()))
    sets.MarkSetCount = len(sets.Coverage)
    lookup = otl.buildLookup([otl.buildLigatureSubstSubtable({(sheva, varika): shevana})],
                             flags=0x0010, markFilterSet=sets.MarkSetCount - 1, table="GSUB")
    gsub = t["GSUB"].table
    # (a rule before it that swaps the varika for something else - Simple CLM hides the ta'amim
    #  and the varika with them - would leave the shva plain: the varika is left out of it)
    for lk in gsub.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            if isinstance(getattr(st, "mapping", None), dict):
                st.mapping.pop(varika, None)
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    index = gsub.LookupList.LookupCount - 1
    feature = next((fr for fr in gsub.FeatureList.FeatureRecord if fr.FeatureTag == "ccmp"), None)
    if feature is None:                     # (a font without ccmp: one for every script and language)
        feature = ot.FeatureRecord()
        feature.FeatureTag = "ccmp"
        feature.Feature = ot.Feature()
        feature.Feature.LookupListIndex, feature.Feature.LookupCount = [], 0
        gsub.FeatureList.FeatureRecord.append(feature)
        gsub.FeatureList.FeatureCount = len(gsub.FeatureList.FeatureRecord)
        fi = gsub.FeatureList.FeatureCount - 1
        for sr in gsub.ScriptList.ScriptRecord:
            for ls in [sr.Script.DefaultLangSys] + [r.LangSys for r in sr.Script.LangSysRecord]:
                if ls is not None:
                    ls.FeatureIndex.append(fi)
                    ls.FeatureCount = len(ls.FeatureIndex)
    # (every ccmp record: a font may have one per script)
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == "ccmp":
            fr.Feature.LookupListIndex.append(index)
            fr.Feature.LookupCount = len(fr.Feature.LookupListIndex)


def _as_05c8(t: TTFont, sheva: str) -> None:
    """U+05C8 - the character Unicode approved for the shva na in 2026, which Phonetic MAM uses -
    drawn as the shva na, and counted as a shva by the font's placement rules (Taamey Ashkenaz
    sets a vowel aside for some marks)."""
    if 0x05C8 not in t.getBestCmap():
        for table in t["cmap"].tables:
            if table.isUnicode():
                table.cmap[0x05C8] = "shevana"
    import add_dagesh_hazaq
    add_dagesh_hazaq._alias_in_rules(t, sheva, "shevana")


def resquare(path: Path) -> str:
    """Draw the shva na and the dagesh chazak again from the font's own shva and dagesh, each dot
    squared at its own size (Frank Sofer and the Sefer Torah fonts: in place of Taamey D's bigger
    ones - their joined letters use the same glyph, so they change with it)."""
    t = TTFont(path)
    cmap = t.getBestCmap()
    glyf = t["glyf"]
    done = []
    if "shevana" in glyf.glyphs and 0x05B0 in cmap:
        glyf["shevana"] = _squares(t, cmap[0x05B0])
        done.append("shva na")
    if "dageshxazaq" in glyf.glyphs and 0x05BC in cmap:
        glyf["dageshxazaq"] = _squares(t, cmap[0x05BC])
        done.append("dagesh chazak")
    for n in ("shevana", "dageshxazaq"):
        if n in glyf.glyphs:
            glyf[n].recalcBounds(glyf)
    t.save(path)
    return f"{path.name}: {', '.join(done) or 'nothing'} drawn as its dots squared"


def _has_rule(t: TTFont, sheva: str, varika: str | None) -> bool:
    for lk in t["GSUB"].table.LookupList.Lookup:
        for st in lk.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for lig in (getattr(st, "ligatures", None) or {}).get(sheva, []):
                if lig.LigGlyph == "shevana" and lig.Component == [varika]:
                    return True
    return False


def make(path: Path) -> str:
    t = TTFont(path)
    cmap = t.getBestCmap()
    sheva = cmap[0x05B0]
    if _has_rule(t, sheva, cmap.get(0xFB1E)):
        if 0x05C8 in cmap:
            return f"{path.name}: done already"
        _as_05c8(t, sheva)
        t.save(path)
        return f"{path.name}: U+05C8 added"
    if "shevana" not in t.getGlyphOrder():
        _add_glyph(t, "shevana", _squares(t, sheva), t["hmtx"][sheva])
        _as_mark_like(t, "shevana", sheva)
    if 0xFB1E in cmap:
        varika = cmap[0xFB1E]
    else:                                   # (an empty one: nothing shows if a text has it alone)
        varika = "uniFB1E"
        _add_glyph(t, varika, TTGlyphPen(None).glyph(), (0, 0))
        t["GDEF"].table.GlyphClassDef.classDefs[varika] = 3
        for table in t["cmap"].tables:
            if table.isUnicode():
                table.cmap[0xFB1E] = varika
    _ligature(t, sheva, varika, "shevana")
    _as_05c8(t, sheva)
    t.save(path)
    return f"{path.name}: shva na added"


if __name__ == "__main__":
    for f in files():
        print(make(FONTS / f))
        print(resquare(FONTS / f))
