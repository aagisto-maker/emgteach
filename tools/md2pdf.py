#!/usr/bin/env python3
"""Render the project's Markdown docs to PDF — no external tools, no new deps.

Uses **reportlab** (already a project dependency for the PDF reports) plus the
**DejaVu** TrueType fonts bundled with **matplotlib** (also a dependency), so it
runs anywhere the app's virtual environment runs — without pandoc, wkhtmltopdf
or a LaTeX install. It is intentionally small: it handles the Markdown subset the
docs in ``docs/`` actually use (headings, bold/italic, inline code, fenced code,
ordered/unordered lists with continuation lines, tables, block quotes, figure
notes, horizontal rules and links).

Usage
-----
Regenerate **all** ``docs/*.md`` to ``docs/*.pdf`` (the common case)::

    python tools/md2pdf.py

Convert specific files (paths relative to ``docs/`` or absolute)::

    python tools/md2pdf.py manual_emgteach_es.md cheatsheet.md

The generated ``docs/*.pdf`` are git-ignored (the ``.md`` files are the source).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib.colors import HexColor, grey
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------- fonts
FDIR = os.path.join(os.path.dirname(matplotlib.__file__),
                    "mpl-data", "fonts", "ttf")
_FONTS = {
    "DejaVuSans": "DejaVuSans.ttf",
    "DejaVuSans-Bold": "DejaVuSans-Bold.ttf",
    "DejaVuSans-Oblique": "DejaVuSans-Oblique.ttf",
    "DejaVuSans-BoldOblique": "DejaVuSans-BoldOblique.ttf",
    "DejaVuSansMono": "DejaVuSansMono.ttf",
}
for _name, _fn in _FONTS.items():
    pdfmetrics.registerFont(TTFont(_name, os.path.join(FDIR, _fn)))
pdfmetrics.registerFontFamily(
    "DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
    italic="DejaVuSans-Oblique", boldItalic="DejaVuSans-BoldOblique")

BODY_FONT, BOLD_FONT, MONO_FONT = "DejaVuSans", "DejaVuSans-Bold", "DejaVuSansMono"
INK = HexColor("#1a1a1a")
BLUE = HexColor("#1f4e79")
LBLUE = HexColor("#e8f0fa")
LGREY = HexColor("#f4f4f4")

MARGIN = 2.0 * cm
AVAIL = A4[0] - 2 * MARGIN

# ---------------------------------------------------------------- styles
body = ParagraphStyle("body", fontName=BODY_FONT, fontSize=10.3, leading=14.5,
                      textColor=INK, alignment=TA_LEFT, spaceAfter=6)
h1 = ParagraphStyle("h1", parent=body, fontName=BOLD_FONT, fontSize=20,
                    leading=24, textColor=BLUE, spaceBefore=4, spaceAfter=12)
h2 = ParagraphStyle("h2", parent=body, fontName=BOLD_FONT, fontSize=15,
                    leading=19, textColor=BLUE, spaceBefore=16, spaceAfter=6)
h3 = ParagraphStyle("h3", parent=body, fontName=BOLD_FONT, fontSize=12.5,
                    leading=16, textColor=HexColor("#2c5f8a"),
                    spaceBefore=11, spaceAfter=4)
h4 = ParagraphStyle("h4", parent=body, fontName=BOLD_FONT, fontSize=11,
                    leading=14, textColor=INK, spaceBefore=8, spaceAfter=3)
HEADS = {1: h1, 2: h2, 3: h3, 4: h4}
li = ParagraphStyle("li", parent=body, leftIndent=18, bulletIndent=4,
                    spaceAfter=3)
note = ParagraphStyle("note", parent=body, fontName="DejaVuSans-Oblique",
                      textColor=grey, fontSize=9.3, leading=12.5,
                      leftIndent=8, spaceAfter=8)
bq = ParagraphStyle("bq", parent=body, leftIndent=4, spaceAfter=0)
cell = ParagraphStyle("cell", parent=body, fontSize=9.3, leading=12.5,
                      spaceAfter=0)
cellh = ParagraphStyle("cellh", parent=cell, fontName=BOLD_FONT,
                       textColor=HexColor("#143655"))
code = ParagraphStyle("code", fontName=MONO_FONT, fontSize=8.7, leading=11.5,
                      textColor=HexColor("#202020"))

# ---------------------------------------------------------------- inline
# Colour-circle emoji are the only glyphs the docs use that DejaVu lacks; map
# them to a coloured filled circle (U+25CF, which DejaVu has).
_CIRCLE = {"\U0001F534": "#cc0000", "\U0001F7E2": "#2e8b57",
           "\U0001F7E0": "#e67e22"}
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITAL = re.compile(r"(?<![\*\w])\*(?!\s)([^*\n]+?)\*(?!\w)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_PH = re.compile(r"\x00(\d+)\x00")


def inline(text: str) -> str:
    """Convert a Markdown span to reportlab mini-HTML markup."""
    stash: list[str] = []

    def grab(m):
        stash.append(m.group(1))
        return f"\x00{len(stash) - 1}\x00"

    text = _CODE.sub(grab, text)          # protect code spans from formatting
    text = escape(text)                   # then escape XML special chars
    text = _BOLD.sub(r"<b>\1</b>", text)
    text = _ITAL.sub(r"<i>\1</i>", text)
    text = _LINK.sub(r'<link href="\2" color="#0645ad">\1</link>', text)
    for ch, col in _CIRCLE.items():
        text = text.replace(ch, f'<font color="{col}">●</font>')

    def restore(m):
        return (f'<font face="{MONO_FONT}" color="#b0306a">'
                f'{escape(stash[int(m.group(1))])}</font>')

    return _PH.sub(restore, text)


# ---------------------------------------------------------------- helpers
def _row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_sep(cells: list[str]) -> bool:
    return all(set(c) <= set("-: ") and "-" in c for c in cells)


def make_table(rows: list[list[str]]) -> Table:
    head, body_rows = rows[0], rows[1:]
    ncol = len(head)
    weights = [max(1, len(head[i])) for i in range(ncol)]
    for r in body_rows:
        for i in range(min(ncol, len(r))):
            weights[i] = max(weights[i], min(len(r[i]), 60))
    tot = float(sum(weights))
    widths = [max(1.2 * cm, AVAIL * w / tot) for w in weights]
    scale = AVAIL / sum(widths)
    widths = [w * scale for w in widths]
    data = [[Paragraph(inline(c), cellh) for c in head]]
    for r in body_rows:
        r = (r + [""] * ncol)[:ncol]
        data.append([Paragraph(inline(c), cell) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#b9c6d4")),
        ("BACKGROUND", (0, 0), (-1, 0), LBLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [None, HexColor("#fafcfe")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def make_quote(text: str) -> Table:
    t = Table([[Paragraph(inline(text), bq)]], colWidths=[AVAIL])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 3, HexColor("#4a90d9")),
        ("BACKGROUND", (0, 0), (-1, -1), LBLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def make_code(lines: list[str]) -> Table:
    t = Table([[Preformatted("\n".join(lines), code)]], colWidths=[AVAIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LGREY),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#cccccc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ---------------------------------------------------------------- parser
def parse(md: str) -> list:
    lines = md.replace("﻿", "").split("\n")
    flow: list = []
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        s = ln.strip()

        if not s:
            i += 1
            continue

        if s.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            flow.append(make_code(buf))
            flow.append(Spacer(1, 6))
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            flow.append(Spacer(1, 2))
            flow.append(HRFlowable(width="100%", thickness=0.6,
                                   color=HexColor("#c5c5c5")))
            flow.append(Spacer(1, 6))
            i += 1
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            flow.append(Paragraph(inline(m.group(2).strip()), HEADS[lvl]))
            i += 1
            continue

        if s.startswith("|") and i + 1 < n and _is_sep(_row(lines[i + 1])):
            rows = [_row(lines[i])]
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                rows.append(_row(lines[i]))
                i += 1
            flow.append(make_table(rows))
            flow.append(Spacer(1, 8))
            continue

        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            flow.append(make_quote(" ".join(x.strip() for x in buf).strip()))
            flow.append(Spacer(1, 6))
            continue

        if re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", ln):
            while i < n:
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if mm:
                    indent = len(mm.group(1))
                    marker = mm.group(2)
                    txt = mm.group(3).strip()
                    i += 1
                    # continuation lines (indented, not a new marker)
                    while (i < n and lines[i].strip()
                           and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i])
                           and (len(lines[i]) - len(lines[i].lstrip())) >= 2):
                        txt += " " + lines[i].strip()
                        i += 1
                    bullet = "•" if marker in ("-", "*") else marker
                    st = ParagraphStyle("li_i", parent=li,
                                        leftIndent=18 + indent * 4)
                    flow.append(Paragraph(inline(txt), st, bulletText=bullet))
                elif not lines[i].strip():
                    break
                else:
                    break
            flow.append(Spacer(1, 4))
            continue

        # paragraph: gather until blank / a block start
        buf = [ln]
        i += 1
        while (i < n and lines[i].strip()
               and not re.match(r"^\s*(#{1,4}\s|[-*]\s|\d+\.\s|>|\||```|---)",
                                lines[i])):
            buf.append(lines[i])
            i += 1
        para = " ".join(x.strip() for x in buf).strip()
        if para.startswith("[") and para.endswith("]"):
            flow.append(Paragraph(inline(para), note))
        else:
            flow.append(Paragraph(inline(para), body))
    return flow


# ---------------------------------------------------------------- doc
def _footer(title: str):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(BODY_FONT, 8)
        canvas.setFillColor(grey)
        canvas.drawString(MARGIN, 1.15 * cm, title[:70])
        canvas.drawRightString(A4[0] - MARGIN, 1.15 * cm, f"pag. {doc.page}")
        canvas.setStrokeColor(HexColor("#dddddd"))
        canvas.line(MARGIN, 1.45 * cm, A4[0] - MARGIN, 1.45 * cm)
        canvas.restoreState()
    return draw


def build(src: str, dst: str) -> str:
    md = open(src, encoding="utf-8").read()
    m = re.search(r"^#\s+(.*)$", md, re.M)
    title = re.sub(r"\*", "", m.group(1).strip()) if m else os.path.basename(src)
    flow = parse(md)
    doc = BaseDocTemplate(
        dst, pagesize=A4, title=title, author="emgteach",
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm)
    frame = Frame(MARGIN, 2.0 * cm, AVAIL, A4[1] - 4.0 * cm, id="main")
    doc.addPageTemplates([PageTemplate(id="t", frames=[frame],
                                       onPage=_footer(title))])
    doc.build(flow)
    return title


def main(argv: list[str]) -> int:
    docs_dir = Path(__file__).resolve().parent.parent / "docs"
    if argv:
        targets = []
        for a in argv:
            p = Path(a)
            targets.append(p if p.is_absolute() else docs_dir / p)
    else:
        targets = sorted(docs_dir.glob("*.md"))
    if not targets:
        print("No .md files to convert in", docs_dir)
        return 1
    for src in targets:
        if not src.exists():
            print("SKIP (not found):", src)
            continue
        dst = src.with_suffix(".pdf")
        build(str(src), str(dst))
        print(f"OK  {src.name:<26} -> {dst.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
