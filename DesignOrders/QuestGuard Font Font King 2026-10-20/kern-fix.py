
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

FONT_NAME = "QuestGuard-Regular"
LOWERCASE_SCALE = 0.80

KERNING = {
    "Ga": -65,
    "ro": -50,
    "oc": -35,
    "og": -45,
    "co": -30,
    "ql": -65,
    "oj": -65,
    "gh": -30,
    "hg": -35,
    "pa": -85,
    "av": -150,
    "va": -170,
    "au": -35,
    "ua": -55,
    "ug": 20,
    "ag": -45,
    "ga": -55,
    "ay": -105,
    "ya": -105,
    "ad": -55,
    "da": -55,
}


def make_pair_subtable(pairs):
    subtable = otTables.PairPos()
    subtable.Format = 1
    subtable.ValueFormat1 = 4
    subtable.ValueFormat2 = 0

    subtable.Coverage = otTables.Coverage()
    subtable.Coverage.glyphs = sorted(set(a for a, b in pairs))

    subtable.PairSet = []

    for left in subtable.Coverage.glyphs:
        pair_set = otTables.PairSet()
        pair_set.PairValueRecord = []

        for (a, b), amount in sorted(pairs.items()):
            if a != left:
                continue

            record = otTables.PairValueRecord()
            record.SecondGlyph = b

            value = otTables.ValueRecord()
            value.XAdvance = amount

            record.Value1 = value
            record.Value2 = None

            pair_set.PairValueRecord.append(record)

        pair_set.PairValueCount = len(pair_set.PairValueRecord)
        subtable.PairSet.append(pair_set)

    subtable.PairSetCount = len(subtable.PairSet)
    return subtable


def apply_kerning(font, cmap):
    pairs = {}

    for pair, amount in KERNING.items():
        left = cmap.get(ord(pair[0]))
        right = cmap.get(ord(pair[1]))

        if left is None or right is None:
            print("Skipping kerning:", pair)
            continue

        # Scale lowercase-to-lowercase kerning
        # to match the eventual smaller glyphs.
        if pair[0].islower() and pair[1].islower():
            amount = round(amount * LOWERCASE_SCALE)

        pairs[(left, right)] = amount
        print("Kerning {}: {} units".format(pair, amount))

    if not pairs:
        return

    gpos = font["GPOS"].table

    lookup = None
    for candidate in gpos.LookupList.Lookup:
        if candidate.LookupType == 2:
            lookup = candidate
            break

    if lookup is None:
        raise RuntimeError("No GPOS PairPos lookup found")

    subtable = make_pair_subtable(pairs)

    lookup.SubTable.insert(0, subtable)
    lookup.SubTableCount = len(lookup.SubTable)


def scale_lowercase(font, cmap):
    if "glyf" not in font:
        raise RuntimeError(
            "Font must contain TrueType glyf outlines."
        )

    glyph_set = font.getGlyphSet()
    replacements = {}

    uppercase_glyphs = set(
        cmap.get(ord(c))
        for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    )

    for char in "abcdefghijklmnopqrstuvwxyz":
        glyph_name = cmap.get(ord(char))

        if glyph_name is None:
            continue

        # Avoid changing uppercase if glyphs are shared.
        if glyph_name in uppercase_glyphs:
            print("Skipping shared glyph:", glyph_name)
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

        print("Scaled lowercase:", glyph_name)


def main():
    folder = Path(__file__).resolve().parent

    source = None
    for ext in (".otf", ".ttf"):
        candidate = folder / (FONT_NAME + ext)
        if candidate.exists():
            source = candidate
            break

    if source is None:
        raise FileNotFoundError("Font not found")

    font = TTFont(source)
    cmap = font.getBestCmap()

    print("Applying kerning...")
    apply_kerning(font, cmap)

    print("\nScaling lowercase glyphs...")
    scale_lowercase(font, cmap)

    output = folder / (
        FONT_NAME + "-Fixed" + source.suffix
    )

    font.save(output)

    print("\nSaved:", output)


if __name__ == "__main__":
    main()
