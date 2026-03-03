# Clawdbot

PDF editing tool with support for merging, splitting, rotating, text extraction, watermarking, and page extraction.

## Installation

```bash
pip install -r requirements.txt
```

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
```