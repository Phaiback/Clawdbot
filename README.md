# Clawdbot

PDF editing tool with support for merging, splitting, rotating, text extraction, watermarking, and page extraction.

## Installation

```bash
pip install -r requirements.txt
```

## Word/DOCX Editing (`word_editor.py`)

```bash
# DOCX → PDF  (footnotes, styles, tables all preserved)
python3 word_editor.py docx-to-pdf input.docx -o output.pdf

# PDF → DOCX
python3 word_editor.py pdf-to-docx input.pdf -o output.docx

# Create a new DOCX
python3 word_editor.py create -o new.docx --title "Titel" --body "Inhalt"

# Find & replace (formatting stays intact)
python3 word_editor.py find-replace input.docx -o output.docx --old "alt" --new "neu"

# Add paragraph (bold, centered, font size 14)
python3 word_editor.py add-paragraph input.docx -o output.docx \
    --text "Neuer Absatz" --bold --align center --font-size 14

# Change font throughout the document
python3 word_editor.py set-font input.docx -o output.docx --font-name "Arial" --font-size 12

# Document info (page count, styles, footnotes)
python3 word_editor.py info input.docx
```

> **Fußnoten & Formatierung**: `docx-to-pdf` nutzt mammoth + weasyprint.
> Fußnoten werden als nummerierte Liste am Seitenende korrekt übertragen.
> `find-replace` rekonstruiert bei split runs den vollen Text ohne Formatierungsverlust.

---

## PDF Editing (`pdf_editor.py`)

## Usage

```bash
# Merge multiple PDFs
python3 pdf_editor.py merge a.pdf b.pdf -o merged.pdf

# Split into individual pages
python3 pdf_editor.py split input.pdf -o ./pages/

# Rotate pages (90, 180, or 270 degrees)
python3 pdf_editor.py rotate input.pdf -o output.pdf -d 90
python3 pdf_editor.py rotate input.pdf -o output.pdf -d 180 -p 1,3,5-7

# Extract text
python3 pdf_editor.py extract-text input.pdf
python3 pdf_editor.py extract-text input.pdf -o text.txt

# Add watermark
python3 pdf_editor.py watermark input.pdf -o output.pdf -t "VERTRAULICH"

# Extract specific pages
python3 pdf_editor.py extract-pages input.pdf -o output.pdf -p 1,3,5-7

# Compress (reduce file size)
python3 pdf_editor.py compress input.pdf -o compressed.pdf

# Encrypt with a password
python3 pdf_editor.py encrypt input.pdf -o locked.pdf -p secret
python3 pdf_editor.py encrypt input.pdf -o locked.pdf -p userpass --owner-password ownerpass

# Decrypt (remove password protection)
python3 pdf_editor.py decrypt locked.pdf -o unlocked.pdf -p secret
```