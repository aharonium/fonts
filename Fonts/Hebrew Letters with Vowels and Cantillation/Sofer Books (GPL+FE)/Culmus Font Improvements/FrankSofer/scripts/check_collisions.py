"""Collisions Frank Sofer has and Taamey D has not, over every word of Tanach (HarfBuzz shaping,
each glyph's outline rasterised at 1/4 font unit scale, any two glyphs - one a mark - sharing ink)."""
import sys, json, re, collections
from pathlib import Path
import uharfbuzz as hb
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
from PIL import Image, ImageDraw, ImageChops, ImageFilter
SC = 4

class Poly(BasePen):
    def __init__(s, gs): super().__init__(gs); s.polys=[]; s.cur=None
    def _moveTo(s,a): s.polys.append([a]); s.cur=a
    def _lineTo(s,a): s.polys[-1].append(a); s.cur=a
    def _qCurveToOne(s,a,b):
        x0,y0=s.cur
        for i in range(1,7):
            u=i/6; s.polys[-1].append(((1-u)**2*x0+2*(1-u)*u*a[0]+u*u*b[0],(1-u)**2*y0+2*(1-u)*u*a[1]+u*u*b[1]))
        s.cur=b
    def _curveToOne(s,a,b,c):
        x0,y0=s.cur
        for i in range(1,7):
            u=i/6; m=1-u
            s.polys[-1].append((m**3*x0+3*m*m*u*a[0]+3*m*u*u*b[0]+u**3*c[0],m**3*y0+3*m*m*u*a[1]+3*m*u*u*b[1]+u**3*c[1]))
        s.cur=c

class Font:
    def __init__(s, path):
        s.t=TTFont(path); s.gs=s.t.getGlyphSet()
        s.hb=hb.Font(hb.Face(hb.Blob.from_file_path(path)))
        cd=s.t["GDEF"].table.GlyphClassDef.classDefs
        s.mark={g for g,c in cd.items() if c==3}; s.cache={}
    def mask(s, name):
        if name in s.cache: return s.cache[name]
        pen=Poly(s.gs); s.gs[name].draw(pen)
        pts=[p for poly in pen.polys for p in poly]
        if not pts: s.cache[name]=None; return None
        x0=int(min(p[0] for p in pts)//SC)-1; y0=int(min(p[1] for p in pts)//SC)-1
        x1=int(max(p[0] for p in pts)//SC)+2; y1=int(max(p[1] for p in pts)//SC)+2
        img=Image.new("1",(x1-x0,y1-y0),0)
        for poly in pen.polys:
            if len(poly)<3: continue
            one=Image.new("1",img.size,0)
            ImageDraw.Draw(one).polygon([(p[0]/SC-x0,y1-p[1]/SC) for p in poly],fill=1)
            img=ImageChops.logical_xor(img,one)
        # (shrink by a pixel: touching edges are not a collision)
        a=img.convert("L").filter(ImageFilter.MinFilter(3)).convert("1")
        s.cache[name]=(x0,y1,a); return s.cache[name]
    def collisions(s, word):
        b=hb.Buffer(); b.add_str(word); b.guess_segment_properties(); hb.shape(s.hb,b)
        placed=[]; x=0
        for i,p in zip(b.glyph_infos,b.glyph_positions):
            n=s.hb.glyph_to_string(i.codepoint)
            m=s.mask(n)
            if m: placed.append((n,i.cluster,(x+p.x_offset)//SC+m[0], m[1]+p.y_offset//SC, m[2]))
            x+=p.x_advance
        out=set()
        for i in range(len(placed)):
            for j in range(i+1,len(placed)):
                a,b2=placed[i],placed[j]
                if a[0] not in s.mark and b2[0] not in s.mark: continue
                ax,ay,am=a[2],a[3],a[4]; bx,by,bm=b2[2],b2[3],b2[4]
                # image coords: column = x - ax, row = ay - y
                X0=max(ax,bx); X1=min(ax+am.size[0],bx+bm.size[0])
                Ytop=min(ay,by); Ybot=max(ay-am.size[1],by-bm.size[1])
                if X0>=X1 or Ybot>=Ytop: continue
                sa=am.crop((X0-ax, ay-Ytop, X1-ax, ay-Ybot)); sb=bm.crop((X0-bx, by-Ytop, X1-bx, by-Ybot))
                if ImageChops.logical_and(sa,sb).getbbox(): out.add(tuple(sorted((a[0],b2[0]))))
        return out

if __name__=="__main__":
    old, new = Font(sys.argv[1]), Font(sys.argv[2])
    words=set()
    for f in Path("data/sefaria-export/json/Tanakh").rglob("Miqra according to the Masorah.json"):
        d=json.loads(f.read_text(encoding="utf-8"))
        def walk(x):
            if isinstance(x,list):
                for y in x: walk(y)
            elif isinstance(x,str):
                x=re.sub(r"<[^>]*>|&[a-z#0-9]+;"," ",x)
                for w in re.split(r"[\s־]+",x):
                    w=re.sub(r"[^֑-׉א-תﬞ]","",w)
                    if re.search("[א-ת]",w): words.add(w)
        walk(d["text"])
    print(len(words),"words", file=sys.stderr)
    found=collections.defaultdict(list)
    for w in words:
        c=new.collisions(w)
        if c:
            c-=old.collisions(w)
            for pair in c: found[pair].append(w)
    for pair,ws in sorted(found.items(), key=lambda x:-len(x[1])):
        print(len(ws), "/".join(pair), " ".join(ws[:8]))
    print("total", sum(len(v) for v in found.values()))
