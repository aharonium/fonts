"""hebrew_body_height from Sofer's src/sofer/fonts.py, for running make_stam_sefarad.py on its own
(needs Pillow)."""
from pathlib import Path

_ROOF_LETTERS = "בדהכמפרתח"


def hebrew_body_height(font_file: str) -> float:
    """Median height of the body of roofed Hebrew letters, as a fraction of the em: from the
    line they stand on up to the roof - the highest row whose ink spans at least 40% of the
    letter's width - so a Sefer Torah font's crowns and serifs do not count (Mordy,
    2026-10-15)."""
    import statistics

    from PIL import Image, ImageDraw, ImageFont
    path = Path(font_file)
    size = 400
    font = ImageFont.truetype(str(path), size)
    heights = []
    for ch in _ROOF_LETTERS:
        img = Image.new("L", (size * 2, size * 2), 0)
        base = int(size * 1.5)
        ImageDraw.Draw(img).text((size // 2, base), ch, fill=255, font=font, anchor="ls")
        box = img.getbbox()
        if not box:
            continue
        width = box[2] - box[0]
        px = img.load()
        for y in range(box[1], base):
            if sum(1 for x in range(box[0], box[2]) if px[x, y] > 127) >= 0.4 * width:
                heights.append((base - y) / size)
                break
    if not heights:
        raise ValueError(f"The font {path.name} has no Hebrew letters to measure.")
    return statistics.median(heights)
