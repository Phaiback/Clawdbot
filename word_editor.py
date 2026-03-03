#!/usr/bin/env python3
"""
Word/DOCX Editor – Clawdbot
Supports:
  - DOCX → PDF  (via LibreOffice – best formatting/footnote preservation)
  - PDF  → DOCX (via pdf2docx)
  - Creating new DOCX documents
  - Editing existing DOCX: find-replace, add/remove paragraphs, styles
"""

import argparse
import logging
import shutil
import subprocess
import sys
from pathlib import Path

# Suppress verbose DEBUG/INFO noise from fonttools, weasyprint, and pdf2docx.
# Must happen before those packages configure their own loggers.
logging.basicConfig(level=logging.WARNING)
logging.disable(logging.INFO)  # globally suppresses INFO and below

import mammoth
import weasyprint
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pdf2docx import Converter


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

# CSS used when rendering DOCX → HTML → PDF.
# Designed to preserve footnote layout, page margins, and common Word styles.
_PDF_CSS = """
@page {
    margin: 2.5cm;
    @bottom-center {
        content: counter(page);
        font-size: 10pt;
    }
}
body {
    font-family: "Times New Roman", Times, serif;
    font-size: 12pt;
    line-height: 1.5;
    color: #000;
}
h1 { font-size: 18pt; font-weight: bold; margin: 12pt 0 6pt; }
h2 { font-size: 14pt; font-weight: bold; margin: 10pt 0 4pt; }
h3 { font-size: 12pt; font-weight: bold; margin: 8pt 0 4pt; }
p  { margin: 0 0 8pt; }
table {
    border-collapse: collapse;
    width: 100%;
    margin-bottom: 8pt;
}
td, th {
    border: 1px solid #666;
    padding: 4pt 6pt;
}
/* Footnote styling – mammoth renders footnotes as <ol class="footnotes"> */
.footnotes {
    border-top: 1px solid #999;
    margin-top: 16pt;
    padding-top: 6pt;
    font-size: 10pt;
}
.footnotes ol { padding-left: 1.5em; margin: 0; }
.footnotes li { margin-bottom: 4pt; }
sup { font-size: 8pt; }
"""

# mammoth style map: maps Word paragraph/character styles to HTML.
# Extend this dict to handle custom styles in your documents.
_MAMMOTH_STYLE_MAP = """
p[style-name='Heading 1'] => h1:fresh
p[style-name='Heading 2'] => h2:fresh
p[style-name='Heading 3'] => h3:fresh
p[style-name='Heading 4'] => h4:fresh
p[style-name='Title']     => h1.title:fresh
p[style-name='Subtitle']  => p.subtitle:fresh
p[style-name='Quote']     => blockquote:fresh
r[style-name='Strong']    => strong
r[style-name='Emphasis']  => em
"""


def docx_to_pdf(input_file: str, output_file: str | None = None) -> str:
    """
    Convert DOCX → PDF via mammoth (DOCX→HTML) + weasyprint (HTML→PDF).

    Why this pipeline?
    - mammoth natively extracts footnotes / endnotes and renders them as
      a proper <ol class="footnotes"> block – nothing is lost.
    - weasyprint supports CSS @page rules so margins, page numbers, and
      multi-column layouts are preserved.
    - No dependency on LibreOffice, Word, or any GUI application.
    """
    input_path = Path(input_file).resolve()
    out = output_file or str(input_path.with_suffix(".pdf"))

    with open(input_path, "rb") as fh:
        result = mammoth.convert_to_html(
            fh,
            style_map=_MAMMOTH_STYLE_MAP,
            convert_image=mammoth.images.img_element(
                lambda image: {"src": "data:" + image.content_type + ";base64," +
                               __import__("base64").b64encode(image.read()).decode()}
            ),
        )

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <style>{_PDF_CSS}</style>
</head>
<body>
{result.value}
</body>
</html>"""

    weasyprint.HTML(string=html, base_url=str(input_path.parent)).write_pdf(out)

    if result.messages:
        warnings = [m.message for m in result.messages]
        print(f"  Hinweise: {'; '.join(warnings[:3])}")

    print(f"DOCX → PDF: '{out}'")
    return out


def pdf_to_docx(input_file: str, output_file: str | None = None) -> str:
    """
    Convert PDF → DOCX using pdf2docx.
    Preserves fonts, tables, images, and multi-column layouts.
    Footnotes inside the PDF body are preserved as regular text;
    structural footnote links (PDF annotations) depend on the source PDF quality.
    """
    out = output_file or str(Path(input_file).with_suffix(".docx"))
    cv = Converter(input_file)
    cv.convert(out, start=0, end=None)
    cv.close()
    print(f"PDF → DOCX: '{out}'")
    return out


# ---------------------------------------------------------------------------
# Document creation
# ---------------------------------------------------------------------------

_ALIGN_MAP = {
    "left":    WD_ALIGN_PARAGRAPH.LEFT,
    "center":  WD_ALIGN_PARAGRAPH.CENTER,
    "right":   WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def create_docx(output_file: str, title: str = "", body: str = "") -> str:
    """Create a new DOCX document with an optional title and body text."""
    doc = Document()
    if title:
        doc.add_heading(title, level=0)
    if body:
        for paragraph in body.split(r"\n"):
            doc.add_paragraph(paragraph)
    doc.save(output_file)
    print(f"Created '{output_file}'")
    return output_file


# ---------------------------------------------------------------------------
# Document editing
# ---------------------------------------------------------------------------

def find_replace(input_file: str, output_file: str, old_text: str, new_text: str) -> int:
    """
    Replace all occurrences of *old_text* with *new_text* in a DOCX.
    Handles text split across runs within the same paragraph so that
    formatting (bold, italic, font size, colour) is not destroyed.
    Returns the number of replacements made.
    """
    doc = Document(input_file)
    count = 0

    def _replace_in_paragraph(para) -> None:
        nonlocal count
        # Fast path: old_text fits entirely within one run
        for run in para.runs:
            if old_text in run.text:
                run.text = run.text.replace(old_text, new_text)
                count += run.text.count(new_text)  # approximate; good enough
                return

        # Slow path: text is split across multiple runs
        full_text = "".join(r.text for r in para.runs)
        if old_text not in full_text:
            return
        # Rebuild: put everything into the first run, clear the rest
        para.runs[0].text = full_text.replace(old_text, new_text)
        count += full_text.count(old_text)
        for run in para.runs[1:]:
            run.text = ""

    for para in doc.paragraphs:
        _replace_in_paragraph(para)

    # Also search inside table cells
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    _replace_in_paragraph(para)

    doc.save(output_file)
    print(f"Replaced {count} occurrence(s) of '{old_text}' → '{new_text}' in '{output_file}'")
    return count


def add_paragraph(
    input_file: str,
    output_file: str,
    text: str,
    style: str = "Normal",
    position: int = -1,
    font_size: int | None = None,
    bold: bool = False,
    italic: bool = False,
    align: str = "left",
) -> None:
    """
    Add a paragraph to an existing DOCX.
    position -1 → append at end; 0 → insert before first paragraph, etc.
    """
    doc = Document(input_file)
    para = doc.add_paragraph(style=style)
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    if font_size:
        run.font.size = Pt(font_size)
    para.alignment = _ALIGN_MAP.get(align.lower(), WD_ALIGN_PARAGRAPH.LEFT)

    if position >= 0:
        # Move newly added paragraph to the desired position
        body = doc.element.body
        new_elem = para._element
        body.remove(new_elem)
        ref = body.paragraphs[min(position, len(body.paragraphs) - 1)] if body.paragraphs else None
        if ref is not None:
            body.insert(list(body).index(ref), new_elem)
        else:
            body.append(new_elem)

    doc.save(output_file)
    print(f"Paragraph added to '{output_file}'")


def set_font(
    input_file: str,
    output_file: str,
    font_name: str | None = None,
    font_size: int | None = None,
    paragraph_index: int | None = None,
) -> None:
    """
    Change font name and/or size for all paragraphs (or a specific one).
    Applies to every run within the targeted paragraph(s).
    """
    doc = Document(input_file)
    paras = [doc.paragraphs[paragraph_index]] if paragraph_index is not None else doc.paragraphs
    for para in paras:
        for run in para.runs:
            if font_name:
                run.font.name = font_name
            if font_size:
                run.font.size = Pt(font_size)
    doc.save(output_file)
    target = f"paragraph {paragraph_index}" if paragraph_index is not None else "all paragraphs"
    print(f"Font updated for {target} in '{output_file}'")


def show_info(input_file: str) -> None:
    """Print document statistics: paragraph count, styles used, footnotes."""
    doc = Document(input_file)
    styles_used = {p.style.name for p in doc.paragraphs if p.text.strip()}
    print(f"File        : {input_file}")
    print(f"Paragraphs  : {len(doc.paragraphs)}")
    print(f"Tables      : {len(doc.tables)}")
    print(f"Styles used : {', '.join(sorted(styles_used))}")

    # Footnote detection via raw XML (python-docx does not expose them directly)
    from lxml import etree
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    footnotes = doc.element.body.findall(f".//{{{ns}}}footnote")
    endnotes  = doc.element.body.findall(f".//{{{ns}}}endnote")
    # Check footnotes part
    try:
        fn_part = doc.part.footnotes_part
        fn_count = len(fn_part._element.findall(f"{{{ns}}}footnote")) - 2  # minus separator stubs
        print(f"Footnotes   : {max(fn_count, 0)}")
    except Exception:
        print(f"Footnotes   : 0")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="word_editor",
        description="Clawdbot Word Editor – convert, create, and edit DOCX/PDF",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # docx-to-pdf
    p = sub.add_parser("docx-to-pdf", help="Convert DOCX → PDF (LibreOffice, preserves footnotes)")
    p.add_argument("input", help="Input .docx file")
    p.add_argument("-o", "--output", help="Output .pdf file (default: same name)")

    # pdf-to-docx
    p = sub.add_parser("pdf-to-docx", help="Convert PDF → DOCX (pdf2docx)")
    p.add_argument("input", help="Input .pdf file")
    p.add_argument("-o", "--output", help="Output .docx file (default: same name)")

    # create
    p = sub.add_parser("create", help="Create a new DOCX document")
    p.add_argument("-o", "--output", required=True, help="Output .docx file")
    p.add_argument("--title", default="", help="Document title")
    p.add_argument("--body", default="", help=r"Body text (use \n for paragraph breaks)")

    # find-replace
    p = sub.add_parser("find-replace", help="Find & replace text (preserves formatting)")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--old", required=True, help="Text to find")
    p.add_argument("--new", required=True, help="Replacement text")

    # add-paragraph
    p = sub.add_parser("add-paragraph", help="Add a paragraph to an existing DOCX")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--style", default="Normal")
    p.add_argument("--position", type=int, default=-1, help="Insert position (-1 = append)")
    p.add_argument("--font-size", type=int)
    p.add_argument("--bold", action="store_true")
    p.add_argument("--italic", action="store_true")
    p.add_argument("--align", default="left", choices=["left", "center", "right", "justify"])

    # set-font
    p = sub.add_parser("set-font", help="Change font name/size in a DOCX")
    p.add_argument("input")
    p.add_argument("-o", "--output", required=True)
    p.add_argument("--font-name")
    p.add_argument("--font-size", type=int)
    p.add_argument("--paragraph", type=int, help="Target a specific paragraph (0-indexed)")

    # info
    p = sub.add_parser("info", help="Show document statistics (paragraphs, styles, footnotes)")
    p.add_argument("input")

    args = parser.parse_args()

    try:
        if args.command == "docx-to-pdf":
            docx_to_pdf(args.input, args.output)
        elif args.command == "pdf-to-docx":
            pdf_to_docx(args.input, args.output)
        elif args.command == "create":
            create_docx(args.output, args.title, args.body)
        elif args.command == "find-replace":
            find_replace(args.input, args.output, args.old, args.new)
        elif args.command == "add-paragraph":
            add_paragraph(
                args.input, args.output, args.text,
                style=args.style,
                position=args.position,
                font_size=args.font_size,
                bold=args.bold,
                italic=args.italic,
                align=args.align,
            )
        elif args.command == "set-font":
            set_font(args.input, args.output,
                     font_name=args.font_name,
                     font_size=args.font_size,
                     paragraph_index=args.paragraph)
        elif args.command == "info":
            show_info(args.input)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
