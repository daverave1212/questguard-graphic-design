"""Analyze page 1 of a two-column, text-based PDF. pip install pymupdf"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from statistics import median

import pymupdf

# -------- CONFIGURATION --------
PDF_NAME = "OwenPDF-Page1.pdf"
OUTPUT_NAME = "analysis.json"
SEARCH_TEXTS = ["learning the", "you want to try Questguard specifically and"]
# Exclude text outside this vertical portion when estimating columns/margins.
# Helps prevent running headers/footers from skewing body geometry.
BODY_TOP_FRACTION = 0.07
BODY_BOTTOM_FRACTION = 0.93
MIN_LINE_CHARS = 12
# --------------------------------

PT_TO_MM = 25.4 / 72


def dims(x):
    return {"pt": round(x, 2), "mm": round(x * PT_TO_MM, 2)}


def box_dict(b):
    return {"x0": round(b[0], 2), "y0": round(b[1], 2),
            "x1": round(b[2], 2), "y1": round(b[3], 2),
            "width": round(b[2]-b[0], 2), "height": round(b[3]-b[1], 2)}


def color_hex(rgb_int):
    return f"#{rgb_int & 0xFFFFFF:06X}"


def normalize(s):
    return re.sub(r"\s+", " ", s).casefold().strip()


def extract(page):
    lines, spans = [], []
    for block in page.get_text("dict", sort=False)["blocks"]:
        if "lines" not in block:
            continue
        for line in block["lines"]:
            parts = [s for s in line["spans"] if s["text"].strip()]
            if not parts:
                continue
            bbox = (min(s["bbox"][0] for s in parts),
                    min(s["bbox"][1] for s in parts),
                    max(s["bbox"][2] for s in parts),
                    max(s["bbox"][3] for s in parts))
            record = {"text": "".join(s["text"] for s in line["spans"]),
                      "bbox": bbox, "spans": parts}
            lines.append(record)
            for s in parts:
                spans.append({"text": s["text"], "font": s["font"],
                              "size_pt": round(s["size"], 2),
                              "color": color_hex(s["color"]),
                              "flags": s["flags"], "bbox": s["bbox"]})
    return lines, spans


def search_phrases(lines, queries):
    matches = {}
    # Search within each line, then across adjacent lines for wrapped headings.
    for query in queries:
        q = normalize(query)
        found = []
        for i, line in enumerate(lines):
            joined = normalize(line["text"])
            selected = [line]
            if q not in joined and i + 1 < len(lines):
                nxt = lines[i + 1]
                # Only join lines that are nearby vertically and horizontally.
                if (0 <= nxt["bbox"][1] - line["bbox"][3] < 25
                        and abs(nxt["bbox"][0] - line["bbox"][0]) < 35):
                    joined = normalize(line["text"] + " " + nxt["text"])
                    selected = [line, nxt]
            if q not in joined:
                continue
            unique_spans = [s for ln in selected for s in ln["spans"]]
            b = (min(ln["bbox"][0] for ln in selected),
                 min(ln["bbox"][1] for ln in selected),
                 max(ln["bbox"][2] for ln in selected),
                 max(ln["bbox"][3] for ln in selected))
            styles = Counter((s["font"], round(s["size"], 2), color_hex(s["color"]))
                             for s in unique_spans)
            dominant = styles.most_common(1)[0][0]
            entry = {"matched_line": " ".join(ln["text"].strip() for ln in selected),
                     "font": dominant[0], "font_size_pt": dominant[1],
                     "color": dominant[2], "bbox_pt": box_dict(b),
                     "all_span_styles": [{"font": f, "size_pt": z, "color": c}
                                         for f, z, c in styles]}
            if entry not in found:
                found.append(entry)
        matches[query] = found
    return matches


def analyze_columns(lines, page):
    w, h = page.rect.width, page.rect.height
    eligible = [ln for ln in lines if
                BODY_TOP_FRACTION*h <= (ln["bbox"][1]+ln["bbox"][3])/2 <= BODY_BOTTOM_FRACTION*h
                and len(ln["text"].strip()) >= MIN_LINE_CHARS
                and ln["bbox"][2]-ln["bbox"][0] <= w*0.60]
    if len(eligible) < 6:
        return {"status": "insufficient_body_lines", "body_line_count": len(eligible)}
    mid = w/2
    left = [ln for ln in eligible if (ln["bbox"][0]+ln["bbox"][2])/2 < mid]
    right = [ln for ln in eligible if (ln["bbox"][0]+ln["bbox"][2])/2 >= mid]
    if len(left) < 3 or len(right) < 3:
        return {"status": "could_not_identify_two_columns", "left_lines": len(left),
                "right_lines": len(right)}

    # Column left boundaries: frequent starts. Column right boundaries: long lines' right edges.
    def col_extent(group):
        starts = sorted(ln["bbox"][0] for ln in group)
        ends = sorted(ln["bbox"][2] for ln in group)
        # Left edge approximates normal paragraph start; right edge uses near-maximum
        # to avoid short last lines. These are content bounds, not layout frame bounds.
        x0 = starts[max(0, int(len(starts)*0.15))]
        x1 = ends[min(len(ends)-1, int(len(ends)*0.95))]
        return x0, x1
    l0, l1 = col_extent(left)
    r0, r1 = col_extent(right)
    body = left+right
    top = min(ln["bbox"][1] for ln in body)
    bottom = max(ln["bbox"][3] for ln in body)
    return {
        "status": "estimated_from_text_lines",
        "left_column": {"x_start_pt": round(l0, 2), "x_end_pt": round(l1, 2),
                        "width": dims(l1-l0), "line_count": len(left)},
        "right_column": {"x_start_pt": round(r0, 2), "x_end_pt": round(r1, 2),
                         "width": dims(r1-r0), "line_count": len(right)},
        "column_gap": dims(r0-l1),
        "body_margins": {"left": dims(l0), "right": dims(w-r1),
                         "top": dims(top), "bottom": dims(h-bottom)},
        "notes": "These are approximate text extents, not necessarily the original document's margin/column settings. Top and bottom exclude header/footer regions."
    }


def main():
    folder = Path(__file__).resolve().parent
    pdf_path = folder / PDF_NAME
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")
    with pymupdf.open(pdf_path) as doc:
        if doc.page_count < 1:
            raise SystemExit("PDF contains no pages")
        page = doc[0]
        lines, spans = extract(page)
        styles = Counter((s["font"], s["size_pt"], s["color"]) for s in spans)
        # Count by text characters, not just number of spans.
        chars = Counter()
        for s in spans:
            chars[(s["font"], s["size_pt"], s["color"])] += len(s["text"].strip())
        result = {
            "pdf": PDF_NAME,
            "page_analyzed": 1,
            "page_size": {"width": dims(page.rect.width), "height": dims(page.rect.height),
                          "orientation": "landscape" if page.rect.width > page.rect.height else "portrait"},
            "text_content_bounds_pt": box_dict((min((s["bbox"][0] for s in spans), default=0),
                                                 min((s["bbox"][1] for s in spans), default=0),
                                                 max((s["bbox"][2] for s in spans), default=0),
                                                 max((s["bbox"][3] for s in spans), default=0))),
            "two_column_layout": analyze_columns(lines, page),
            "searched_text": search_phrases(lines, SEARCH_TEXTS),
            "most_common_styles": [
                {"font": font, "size_pt": size, "color": color,
                 "character_count": count, "span_count": styles[(font, size, color)]}
                for (font, size, color), count in chars.most_common(25)
            ],
            "embedded_fonts": [{"xref": f[0], "base_font": f[3], "resource_name": f[4]}
                               for f in page.get_fonts(full=True)],
            "notes": ["All coordinates are in PDF points, origin at top-left of displayed page.",
                      "1 point = 1/72 inch. Margins and columns are estimated from text, not PDF layout metadata.",
                      "Phrase search is case-insensitive and can match adjacent lines; it is not OCR."]
        }
    out = folder / OUTPUT_NAME
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {out}")
    print(f"Page: {result['page_size']}")
    print(f"Columns: {result['two_column_layout']['status']}")
    for q, hits in result["searched_text"].items():
        print(f"{q!r}: " + (", ".join(f"{x['font_size_pt']} pt ({x['font']})" for x in hits) or "not found"))


if __name__ == "__main__":
    main()
