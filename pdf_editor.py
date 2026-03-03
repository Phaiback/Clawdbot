#!/usr/bin/env python3
"""
PDF Editor - Clawdbot PDF editing module.
Supports merging, splitting, rotating, extracting text, and adding watermarks.
"""

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io


def merge_pdfs(input_files: list[str], output_file: str) -> None:
    """Merge multiple PDF files into one."""
    writer = PdfWriter()
    for path in input_files:
        reader = PdfReader(path)
        for page in reader.pages:
            writer.add_page(page)
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Merged {len(input_files)} files into '{output_file}'")


def split_pdf(input_file: str, output_dir: str) -> None:
    """Split a PDF into individual pages."""
    reader = PdfReader(input_file)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    stem = Path(input_file).stem
    for i, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_file = out_path / f"{stem}_page{i}.pdf"
        with open(out_file, "wb") as f:
            writer.write(f)
    print(f"Split '{input_file}' into {len(reader.pages)} pages in '{output_dir}'")


def rotate_pages(input_file: str, output_file: str, degrees: int, pages: list[int] | None = None) -> None:
    """Rotate pages in a PDF (degrees must be 90, 180, or 270)."""
    if degrees not in (90, 180, 270):
        raise ValueError("Rotation must be 90, 180, or 270 degrees")
    reader = PdfReader(input_file)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if pages is None or i + 1 in pages:
            page.rotate(degrees)
        writer.add_page(page)
    with open(output_file, "wb") as f:
        writer.write(f)
    target = "all pages" if pages is None else f"pages {pages}"
    print(f"Rotated {target} by {degrees}° → '{output_file}'")


def extract_text(input_file: str, output_file: str | None = None) -> str:
    """Extract all text from a PDF."""
    reader = PdfReader(input_file)
    lines = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines.append(f"--- Page {i} ---\n{text}")
    result = "\n".join(lines)
    if output_file:
        Path(output_file).write_text(result, encoding="utf-8")
        print(f"Text extracted to '{output_file}'")
    else:
        print(result)
    return result


def add_watermark(input_file: str, output_file: str, text: str) -> None:
    """Overlay a diagonal text watermark on every page."""
    # Build watermark page with reportlab
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)
    c.setFont("Helvetica", 48)
    c.setFillColorRGB(0.7, 0.7, 0.7, alpha=0.4)
    c.saveState()
    c.translate(letter[0] / 2, letter[1] / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, text)
    c.restoreState()
    c.save()
    packet.seek(0)
    watermark_page = PdfReader(packet).pages[0]

    reader = PdfReader(input_file)
    writer = PdfWriter()
    for page in reader.pages:
        page.merge_page(watermark_page)
        writer.add_page(page)
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Watermark '{text}' added → '{output_file}'")


def extract_pages(input_file: str, output_file: str, pages: list[int]) -> None:
    """Extract specific pages (1-indexed) from a PDF."""
    reader = PdfReader(input_file)
    writer = PdfWriter()
    total = len(reader.pages)
    for p in pages:
        if p < 1 or p > total:
            raise ValueError(f"Page {p} out of range (1–{total})")
        writer.add_page(reader.pages[p - 1])
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Extracted pages {pages} from '{input_file}' → '{output_file}'")


def compress_pdf(input_file: str, output_file: str) -> None:
    """Compress a PDF by applying FlateDecode to each page's content streams."""
    reader = PdfReader(input_file)
    writer = PdfWriter()
    for page in reader.pages:
        page.compress_content_streams()
        writer.add_page(page)
    writer.compress_identical_objects()
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Compressed '{input_file}' → '{output_file}'")


def encrypt_pdf(
    input_file: str,
    output_file: str,
    user_password: str,
    owner_password: str | None = None,
) -> None:
    """Encrypt a PDF with a user password (and optional separate owner password)."""
    reader = PdfReader(input_file)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(user_password, owner_password)
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Encrypted '{input_file}' → '{output_file}'")


def decrypt_pdf(input_file: str, output_file: str, password: str) -> None:
    """Remove password protection from an encrypted PDF."""
    reader = PdfReader(input_file)
    if not reader.is_encrypted:
        raise ValueError(f"'{input_file}' is not encrypted")
    result = reader.decrypt(password)
    if result == 0:
        raise ValueError("Incorrect password; could not decrypt the PDF")
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    with open(output_file, "wb") as f:
        writer.write(f)
    print(f"Decrypted '{input_file}' → '{output_file}'")


def _parse_page_list(value: str) -> list[int]:
    """Parse a comma-separated page list like '1,3,5-7'."""
    pages: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(part))
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pdf_editor",
        description="Clawdbot PDF Editor – merge, split, rotate, extract, watermark",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # merge
    p_merge = sub.add_parser("merge", help="Merge multiple PDFs into one")
    p_merge.add_argument("inputs", nargs="+", help="Input PDF files")
    p_merge.add_argument("-o", "--output", required=True, help="Output PDF file")

    # split
    p_split = sub.add_parser("split", help="Split PDF into individual pages")
    p_split.add_argument("input", help="Input PDF file")
    p_split.add_argument("-o", "--output-dir", default=".", help="Output directory")

    # rotate
    p_rotate = sub.add_parser("rotate", help="Rotate pages in a PDF")
    p_rotate.add_argument("input", help="Input PDF file")
    p_rotate.add_argument("-o", "--output", required=True, help="Output PDF file")
    p_rotate.add_argument("-d", "--degrees", type=int, choices=[90, 180, 270], required=True)
    p_rotate.add_argument("-p", "--pages", help="Pages to rotate, e.g. 1,3,5-7 (default: all)")

    # extract-text
    p_text = sub.add_parser("extract-text", help="Extract text from a PDF")
    p_text.add_argument("input", help="Input PDF file")
    p_text.add_argument("-o", "--output", help="Save text to file (default: stdout)")

    # watermark
    p_wm = sub.add_parser("watermark", help="Add a text watermark to every page")
    p_wm.add_argument("input", help="Input PDF file")
    p_wm.add_argument("-o", "--output", required=True, help="Output PDF file")
    p_wm.add_argument("-t", "--text", required=True, help="Watermark text")

    # extract-pages
    p_ep = sub.add_parser("extract-pages", help="Extract specific pages into a new PDF")
    p_ep.add_argument("input", help="Input PDF file")
    p_ep.add_argument("-o", "--output", required=True, help="Output PDF file")
    p_ep.add_argument("-p", "--pages", required=True, help="Pages to extract, e.g. 1,3,5-7")

    # compress
    p_compress = sub.add_parser("compress", help="Reduce PDF file size via stream compression")
    p_compress.add_argument("input", help="Input PDF file")
    p_compress.add_argument("-o", "--output", required=True, help="Output PDF file")

    # encrypt
    p_encrypt = sub.add_parser("encrypt", help="Password-protect a PDF")
    p_encrypt.add_argument("input", help="Input PDF file")
    p_encrypt.add_argument("-o", "--output", required=True, help="Output PDF file")
    p_encrypt.add_argument("-p", "--user-password", required=True, dest="user_password",
                           help="Password required to open the PDF")
    p_encrypt.add_argument("--owner-password", default=None, dest="owner_password",
                           help="Owner password (unrestricted access); defaults to user password if omitted")

    # decrypt
    p_decrypt = sub.add_parser("decrypt", help="Remove password protection from an encrypted PDF")
    p_decrypt.add_argument("input", help="Input PDF file")
    p_decrypt.add_argument("-o", "--output", required=True, help="Output PDF file")
    p_decrypt.add_argument("-p", "--password", required=True,
                           help="Password to unlock the PDF")

    args = parser.parse_args()

    try:
        if args.command == "merge":
            merge_pdfs(args.inputs, args.output)
        elif args.command == "split":
            split_pdf(args.input, args.output_dir)
        elif args.command == "rotate":
            pages = _parse_page_list(args.pages) if args.pages else None
            rotate_pages(args.input, args.output, args.degrees, pages)
        elif args.command == "extract-text":
            extract_text(args.input, args.output)
        elif args.command == "watermark":
            add_watermark(args.input, args.output, args.text)
        elif args.command == "extract-pages":
            pages = _parse_page_list(args.pages)
            extract_pages(args.input, args.output, pages)
        elif args.command == "compress":
            compress_pdf(args.input, args.output)
        elif args.command == "encrypt":
            encrypt_pdf(args.input, args.output, args.user_password, args.owner_password)
        elif args.command == "decrypt":
            decrypt_pdf(args.input, args.output, args.password)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
