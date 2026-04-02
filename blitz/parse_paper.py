"""
Paper Parser — fetch PDF, extract text + figures, produce structured JSON.

Usage:
    python blitz/parse_paper.py --url <doi_or_pdf_url> --out blitz/tmp/
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import fitz  # pymupdf
import numpy as np
from PIL import Image
import requests

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,text/html,*/*",
}


# ── PDF Download ────────────────────────────────────────────────

def resolve_pdf_url(url: str) -> str:
    """Try to resolve a DOI or article URL to a direct PDF link."""
    # If already a PDF URL
    if url.endswith(".pdf"):
        return url

    # Try common patterns
    # Royal Society
    if "royalsocietypublishing.org" in url:
        # Extract DOI from URL
        # Pattern: /doi/pdf/10.xxxx/xxxx or /rspb/article/...
        # Try fetching the page to find PDF link
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        r.raise_for_status()
        # Look for PDF link in HTML
        pdf_patterns = [
            r'href="([^"]*\.pdf[^"]*)"',
            r'href="(/doi/pdf/[^"]*)"',
            r'href="(/doi/epdf/[^"]*)"',
            r'content="([^"]*\.pdf[^"]*)"',
        ]
        for pat in pdf_patterns:
            m = re.search(pat, r.text)
            if m:
                pdf_path = m.group(1)
                if pdf_path.startswith("/"):
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    pdf_path = f"{parsed.scheme}://{parsed.netloc}{pdf_path}"
                return pdf_path

    # DOI redirect
    if "doi.org" in url or url.startswith("10."):
        doi = url
        if not doi.startswith("http"):
            doi = f"https://doi.org/{doi}"
        r = requests.get(doi, headers={**HEADERS, "Accept": "application/pdf"},
                         timeout=30, allow_redirects=True)
        if r.headers.get("content-type", "").startswith("application/pdf"):
            return r.url

    return url


def download_pdf(url: str, out_dir: Path) -> Path:
    """Download PDF to out_dir, return local path."""
    pdf_url = resolve_pdf_url(url)
    print(f"  Downloading PDF from: {pdf_url}")

    r = requests.get(pdf_url, headers=HEADERS, timeout=60, allow_redirects=True)
    r.raise_for_status()

    pdf_path = out_dir / "paper.pdf"
    pdf_path.write_bytes(r.content)
    print(f"  Saved: {pdf_path} ({len(r.content) / 1024:.0f} KB)")
    return pdf_path


# ── Text Extraction ─────────────────────────────────────────────

def extract_full_text(pdf_path: Path) -> str:
    """Extract full text from PDF using PyMuPDF."""
    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append(f"--- PAGE {i + 1} ---\n{text}")
    doc.close()
    return "\n\n".join(pages)


# ── Caption Removal ────────────────────────────────────────────

def _trim_caption(img_path: str, max_trim_frac: float = 0.25) -> bool:
    """Detect and trim figure caption from bottom of image.

    Scans from bottom up: rows that are mostly white (>92% white pixels)
    with occasional dark pixels (text) are likely caption. Trims them.

    Returns True if image was trimmed.
    """
    im = Image.open(img_path).convert("RGB")
    arr = np.array(im)
    h, w = arr.shape[:2]

    if h < 100 or w < 100:
        return False

    # Convert to grayscale for analysis
    gray = np.mean(arr, axis=2)

    # Scan from bottom: find where "mostly white with sparse text" ends
    # Caption rows: >85% pixels are white (>240) but not 100% (has text)
    max_trim = int(h * max_trim_frac)
    trim_to = h  # default: no trim

    # Look for caption region: contiguous bottom rows that are mostly white
    # with some dark pixels (text characters)
    caption_start = None
    for row_idx in range(h - 1, max(h - max_trim, 0), -1):
        row = gray[row_idx]
        white_frac = np.mean(row > 240)
        dark_frac = np.mean(row < 80)

        # Caption row: mostly white background with some text
        is_caption_row = white_frac > 0.85 and dark_frac < 0.15
        # Pure white row (gap between figure and caption)
        is_blank_row = white_frac > 0.98

        if is_caption_row or is_blank_row:
            caption_start = row_idx
        else:
            break

    if caption_start is not None and caption_start < h - 20:
        # Trim: keep everything above caption_start
        # Add small margin (5px) above the cut
        cut_y = max(0, caption_start - 5)
        trimmed = im.crop((0, 0, w, cut_y))

        # Only save if we trimmed a meaningful amount (>3% of height)
        if (h - cut_y) > h * 0.03:
            trimmed.save(img_path)
            return True

    return False


# ── Figure Extraction ───────────────────────────────────────────

def extract_figures(pdf_path: Path, out_dir: Path, min_area: int = 40000) -> list[dict]:
    """
    Extract figures from PDF.

    Strategy:
    1. Extract all embedded images with bounding boxes
    2. Filter by size (min_area) to exclude icons/logos
    3. Also render page 1 as a crop for the title slide
    """
    doc = fitz.open(str(pdf_path))
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    figures = []

    # Render page 1 full for title slide crop
    page1 = doc[0]
    pix = page1.get_pixmap(matrix=fitz.Matrix(3, 3))  # 3x zoom = ~300dpi
    p1_path = figures_dir / "page1_full.png"
    pix.save(str(p1_path))
    figures.append({
        "figure_id": "page1_full",
        "path": str(p1_path),
        "page": 1,
        "type": "page_render",
        "description": "Full page 1 render (for title slide crop)",
        "width": pix.width,
        "height": pix.height,
    })

    # Extract embedded images from all pages
    seen_xrefs = set()
    for page_num in range(len(doc)):
        page = doc[page_num]
        img_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                rects = page.get_image_rects(xref)
                if not rects:
                    continue

                rect = rects[0]
                area = rect.width * rect.height
                if area < min_area:
                    continue

                # Crop at high DPI using page render (better quality than raw extract)
                # Expand rect slightly for padding
                padded = fitz.Rect(
                    max(0, rect.x0 - 5),
                    max(0, rect.y0 - 5),
                    min(page.rect.width, rect.x1 + 5),
                    min(page.rect.height, rect.y1 + 5),
                )
                clip_pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=padded)

                fig_name = f"p{page_num + 1}_img{img_idx}"
                fig_path = figures_dir / f"{fig_name}.png"
                clip_pix.save(str(fig_path))

                # Tight crop: remove caption text from bottom
                trimmed = _trim_caption(str(fig_path))
                if trimmed:
                    # Re-read dimensions after trim
                    trim_im = Image.open(str(fig_path))
                    crop_w, crop_h = trim_im.size
                    print(f"    Caption trimmed: {fig_name} ({clip_pix.height}→{crop_h}px)")
                else:
                    crop_w, crop_h = clip_pix.width, clip_pix.height

                figures.append({
                    "figure_id": fig_name,
                    "path": str(fig_path),
                    "page": page_num + 1,
                    "type": "embedded_image",
                    "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                    "area": area,
                    "width": crop_w,
                    "height": crop_h,
                    "caption_trimmed": trimmed,
                })
            except Exception as e:
                print(f"  Warning: failed to extract image xref={xref}: {e}")

    doc.close()

    # Also do region-based extraction for large figure areas
    # Render each page and try to find large contiguous non-text regions
    _extract_page_regions(pdf_path, figures_dir, figures)

    # Sort by page then area (largest first)
    figures.sort(key=lambda f: (f["page"], -f.get("area", 0)))
    print(f"  Extracted {len(figures)} figures")
    return figures


def _extract_page_regions(pdf_path: Path, figures_dir: Path, figures: list):
    """
    Smart figure extraction from full pages.

    1. Find "Figure N" / "Fig. N" caption text positions via PyMuPDF
    2. Crop the figure region above each caption (tight crop)
    3. Fall back to full-page render if no captions found
    """
    doc = fitz.open(str(pdf_path))

    # Track which figure IDs we already extracted as embedded images
    existing_pages = {f["page"] for f in figures if f["type"] == "embedded_image"}

    for page_num in range(len(doc)):
        page = doc[page_num]
        pw, ph = page.rect.width, page.rect.height

        # Render full page at 3x
        full_pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        full_path = figures_dir / f"p{page_num + 1}_full.png"
        full_pix.save(str(full_path))

        # Try to find figure caption positions
        text_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        caption_rects = []

        for block in text_blocks:
            if block["type"] != 0:  # text blocks only
                continue
            for line in block.get("lines", []):
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                # Match "Figure 1", "Fig. 1", "FIGURE 1" etc.
                m = re.match(r'^(?:Figure|Fig\.?|FIGURE)\s+(\d+)', line_text)
                if m:
                    fig_num = int(m.group(1))
                    caption_bbox = fitz.Rect(line["bbox"])
                    caption_rects.append((fig_num, caption_bbox, line_text[:80]))

        if caption_rects:
            # Sort by y position (top to bottom)
            caption_rects.sort(key=lambda c: c[1].y0)

            for idx, (fig_num, cap_rect, cap_text) in enumerate(caption_rects):
                # Figure region: from previous caption bottom (or page top) to this caption top
                if idx == 0:
                    # First figure: from top margin to caption
                    top_y = min(block["bbox"][1] for block in text_blocks
                                if block["type"] == 0) if text_blocks else 0
                    top_y = max(0, top_y - 5)
                else:
                    # From previous caption bottom
                    top_y = caption_rects[idx - 1][1].y1 + 5

                bottom_y = cap_rect.y0 - 3  # Just above caption text

                # Skip if region is too small
                if bottom_y - top_y < ph * 0.1:
                    continue

                # Crop region with padding
                crop_rect = fitz.Rect(
                    max(0, page.rect.x0),
                    max(0, top_y),
                    min(pw, page.rect.x1),
                    min(ph, bottom_y),
                )

                crop_pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=crop_rect)
                fig_name = f"p{page_num + 1}_fig{fig_num}"
                fig_path = figures_dir / f"{fig_name}.png"
                crop_pix.save(str(fig_path))

                # Trim caption remnants
                trimmed = _trim_caption(str(fig_path))

                # Re-read dimensions if trimmed
                if trimmed:
                    trim_im = Image.open(str(fig_path))
                    crop_w, crop_h = trim_im.size
                else:
                    crop_w, crop_h = crop_pix.width, crop_pix.height

                area = crop_rect.width * crop_rect.height

                figures.append({
                    "figure_id": fig_name,
                    "path": str(fig_path),
                    "page": page_num + 1,
                    "type": "figure_region",
                    "figure_number": fig_num,
                    "caption": cap_text,
                    "rect": [crop_rect.x0, crop_rect.y0, crop_rect.x1, crop_rect.y1],
                    "area": area,
                    "width": crop_w,
                    "height": crop_h,
                    "caption_trimmed": trimmed,
                })
                print(f"    Fig {fig_num}: cropped from p.{page_num+1} "
                      f"({crop_w}x{crop_h}px, area={area:.0f})")

        # Always keep full-page as fallback
        figures.append({
            "figure_id": f"p{page_num + 1}_full",
            "path": str(full_path),
            "page": page_num + 1,
            "type": "full_page",
            "width": full_pix.width,
            "height": full_pix.height,
            "caption_trimmed": False,
        })
    doc.close()


# ── Metadata Extraction ─────────────────────────────────────────

def extract_metadata_from_text(text: str) -> dict:
    """Try to extract basic metadata from the first page text."""
    lines = text.split("\n")[:50]  # First 50 lines
    meta = {"title": "", "authors": "", "journal": "", "year": "", "doi": ""}

    # DOI
    for line in lines:
        doi_match = re.search(r'(10\.\d{4,}/[^\s]+)', line)
        if doi_match:
            meta["doi"] = doi_match.group(1).rstrip(".")
            break

    return meta


# ── Main ────────────────────────────────────────────────────────

def parse_paper(url: str, out_dir: str) -> dict:
    """Full parse pipeline: download → extract text → extract figures → return bundle.

    If url is a local file path (exists on disk), uses it directly instead of downloading.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Check if url is actually a local file
    if Path(url).exists():
        print(f"[PARSER] Using local PDF: {url}")
        import shutil
        pdf_path = out / "paper.pdf"
        if not pdf_path.exists() or str(Path(url).resolve()) != str(pdf_path.resolve()):
            shutil.copy2(url, pdf_path)
    else:
        print("[PARSER] Downloading paper...")
        pdf_path = download_pdf(url, out)

    print("[PARSER] Extracting full text...")
    full_text = extract_full_text(pdf_path)
    (out / "full_text.txt").write_text(full_text, encoding="utf-8")
    print(f"  Text length: {len(full_text)} chars, ~{len(full_text.split())} words")

    print("[PARSER] Extracting figures...")
    figures = extract_figures(pdf_path, out)

    print("[PARSER] Extracting metadata hints...")
    meta_hints = extract_metadata_from_text(full_text)

    result = {
        "pdf_path": str(pdf_path),
        "full_text_path": str(out / "full_text.txt"),
        "full_text": full_text,
        "figures": figures,
        "metadata_hints": meta_hints,
    }

    result_path = out / "parsed.json"
    # Save without full_text in JSON (too large), just the path
    save_result = {k: v for k, v in result.items() if k != "full_text"}
    with open(result_path, "w") as f:
        json.dump(save_result, f, indent=2, ensure_ascii=False)
    print(f"[PARSER] Done. Output: {result_path}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse academic paper for Paper Blitz")
    parser.add_argument("--url", required=True, help="DOI URL or direct PDF URL")
    parser.add_argument("--out", default="blitz/tmp", help="Output directory")
    args = parser.parse_args()

    os.chdir(REPO_DIR)
    result = parse_paper(args.url, args.out)
    print(f"\nFigures extracted: {len(result['figures'])}")
    for fig in result["figures"]:
        print(f"  {fig['figure_id']} — {fig['type']} — p.{fig['page']} — {fig['path']}")
