
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

FONT_NAME = "QuestGuard-Kerned"
LOWERCASE_SCALE = 0.80

def main():
    folder = Path(__file__).resolve().parent

    source = None
    for ext in (".ttf", ".otf"):
        candidate = folder / (FONT_NAME + ext)
        if candidate.exists():
            source = candidate
            break

    if source is None:
        raise FileNotFoundError("Font not found")

    font = TTFont(source)

    if "glyf" not in font:
        raise RuntimeError(
            "This script requires TrueType outlines (glyf table)."
        )

    cmap = font.getBestCmap()
    glyph_set = font.getGlyphSet()

    # Build replacements before modifying the font.
    replacements = {}

    for char in "abcdefghijklmnopqrstuvwxyz":
        glyph_name = cmap.get(ord(char))

        if glyph_name is None:
            continue

        pen = TTGlyphPen(glyph_set)

        transform_pen = TransformPen(
            pen,
            (
                LOWERCASE_SCALE, 0,
                0, LOWERCASE_SCALE,
                0, 0
            )
        )

        glyph_set[glyph_name].draw(transform_pen)
        replacements[glyph_name] = pen.glyph()

    for glyph_name, glyph in replacements.items():
        font["glyf"][glyph_name] = glyph

        width, lsb = font["hmtx"][glyph_name]

        font["hmtx"][glyph_name] = (
            round(width * LOWERCASE_SCALE),
            round(lsb * LOWERCASE_SCALE)
        )

        print("Scaled:", glyph_name)

    output = folder / (
        FONT_NAME + "-Scaled" + source.suffix
    )

    font.save(output)

    print("\nSaved:", output)


if __name__ == "__main__":
    main()
