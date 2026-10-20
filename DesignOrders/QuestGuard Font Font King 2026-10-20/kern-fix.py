
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables

FONT_NAME = "QuestGuard-Regular"


KERNING = {
    "Ga": -65,
    "ro": -25,
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

    pairs = {}

    for pair, amount in KERNING.items():
        left = cmap.get(ord(pair[0]))
        right = cmap.get(ord(pair[1]))

        if left and right:
            pairs[(left, right)] = amount
            print("{}: {} units".format(pair, amount))

    gpos = font["GPOS"].table

    # Insert our pair adjustments into the existing
    # GPOS lookup, before its existing subtables.
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

    output = folder / ("QuestGuard-Kerned" + source.suffix)
    font.save(output)

    print("\nSaved:", output)


if __name__ == "__main__":
    main()
