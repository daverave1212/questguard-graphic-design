
from pathlib import Path
from fontTools.ttLib import TTFont

folder = Path(__file__).resolve().parent
source = folder / "QuestGuard-Regular.ttf"

if not source.exists():
    source = folder / "QuestGuard-Regular.otf"

font = TTFont(str(source))

glyph = font.getBestCmap()[ord("A")]
width, bearing = font["hmtx"][glyph]

print("Original A width:", width)

font["hmtx"][glyph] = (max(0, width - 400), bearing)

# Give the test font a distinct internal family name.
for record in font["name"].names:
    if record.nameID in (1, 4, 6):
        names = {
            1: "QuestGuard Diagnostic",
            4: "QuestGuard Diagnostic Regular",
            6: "QuestGuardDiagnostic-Regular"
        }
        record.string = names[record.nameID].encode(
            record.getEncoding(), errors="replace"
        )

output = folder / ("QuestGuard-Diagnostic" + source.suffix)
font.save(str(output))

print("Saved:", output)
