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

                figures.append({
                    "figure_id": fig_name,
                    "path": str(fig_path),
                    "page": page_num + 1,
                    "type": "embedded_image",
                    "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                    "area": area,
                    "width": clip_pix.width,
                    "height": clip_pix.height,
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
    For each page, render at high DPI and crop the top/bottom halves
    as fallback figure candidates (useful when images are vector/drawn).
    """
    doc = fitz.open(str(pdf_path))
    for page_num in range(len(doc)):
        page = doc[page_num]
        pw, ph = page.rect.width, page.rect.height

        # Render full page at 2x for region crops
        full_pix = page.get_pixmap(matrix=fitz.Matrix(3, 3))
        full_path = figures_dir / f"p{page_num + 1}_full.png"
        full_pix.save(str(full_path))

        figures.append({
            "figure_id": f"p{page_num + 1}_full",
            "path": str(full_path),
            "page": page_num + 1,
            "type": "full_page",
            "width": full_pix.width,
            "height": full_pix.height,
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
