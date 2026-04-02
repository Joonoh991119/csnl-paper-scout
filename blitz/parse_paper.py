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

# Figure extraction DPI (4x = ~288 dpi, good balance of quality vs size)
FIGURE_DPI_SCALE = 4


# ── PDF Download ────────────────────────────────────────────────

def resolve_pdf_url(url: str) -> str:
    """Try to resolve a DOI or article URL to a direct PDF link."""
    if url.endswith(".pdf"):
        return url

    if "royalsocietypublishing.org" in url:
        r = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        r.raise_for_status()
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


# ── Figure QC ──────────────────────────────────────────────────

def _find_content_bbox(img: Image.Image, bg_thresh: int = 245) -> tuple[int, int, int, int]:
    """Find tight bounding box of non-white content in image.

    Returns (left, top, right, bottom) of the content region.
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape
    mask = arr < bg_thresh  # non-white pixels

    # Find content bounds
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not np.any(rows) or not np.any(cols):
        return (0, 0, w, h)

    top = int(np.argmax(rows))
    bottom = int(h - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(w - np.argmax(cols[::-1]))

    return (left, top, right, bottom)


def _strip_vertical_text(img: Image.Image, margin_frac: float = 0.06) -> Image.Image:
    """Remove vertical sidebar text (journal metadata) from right edge.

    Academic PDFs often have rotated text like "royalsocietypublishing.org/..."
    along the right margin. Detect and crop it out.
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape

    # Check right margin (last 6% of width)
    margin_w = max(20, int(w * margin_frac))
    right_strip = arr[:, w - margin_w:]

    # If the right strip has sparse dark pixels spread vertically = sidebar text
    dark_cols = np.mean(right_strip < 120, axis=0)
    # If any column in the strip has >5% dark pixels (text-like density)
    has_sidebar = np.any(dark_cols > 0.05)

    if has_sidebar:
        # Find where the sidebar starts (scan from right)
        for col_idx in range(w - 1, max(w - margin_w * 2, 0), -1):
            col = arr[:, col_idx]
            if np.mean(col < 120) > 0.03:
                # Found text column — crop everything to the right of it
                # But find the actual start of the sidebar region
                continue
            else:
                # Clean column — crop here (add small margin)
                crop_x = min(w, col_idx + 3)
                return img.crop((0, 0, crop_x, h))

    # Also check left margin for rare left-sidebar text
    left_strip = arr[:, :margin_w]
    dark_cols_left = np.mean(left_strip < 120, axis=0)
    has_left_sidebar = np.any(dark_cols_left > 0.05)

    if has_left_sidebar:
        for col_idx in range(0, min(margin_w * 2, w)):
            col = arr[:, col_idx]
            if np.mean(col < 120) > 0.03:
                continue
            else:
                crop_x = max(0, col_idx - 3)
                return img.crop((crop_x, 0, w, h))

    return img


def _trim_whitespace(img: Image.Image, padding: int = 10) -> Image.Image:
    """Trim excess whitespace borders from image, keeping small padding."""
    left, top, right, bottom = _find_content_bbox(img)
    h, w = img.size[1], img.size[0]

    # Add padding
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(w, right + padding)
    bottom = min(h, bottom + padding)

    # Only trim if we'd remove >5% of the image
    content_area = (right - left) * (bottom - top)
    total_area = w * h
    if content_area < total_area * 0.95:
        return img.crop((left, top, right, bottom))

    return img


def _trim_text_regions(img: Image.Image, max_trim_frac: float = 0.40) -> Image.Image:
    """Remove body text / caption text from top and bottom of figure crop.

    Body text and captions appear as rows of evenly-spaced dark pixels
    spanning most of the image width. Figure content (plots, diagrams)
    has varied density patterns and doesn't span the full width uniformly.

    Strategy: scan from each edge inward, looking for contiguous blocks
    of "text-like" rows (dark pixels spanning >50% of width). Stop when
    we hit a blank gap followed by non-text content (the actual figure).
    """
    arr = np.array(img.convert("L"))
    h, w = arr.shape

    if h < 100 or w < 100:
        return img

    max_trim = int(h * max_trim_frac)

    def _is_text_row(row):
        """Check if a row looks like body text (dark pixels spanning wide)."""
        dark = row < 140
        n_dark = np.sum(dark)
        if n_dark == 0:
            return False, True  # blank row
        # Text: dark pixels span >50% of width
        indices = np.where(dark)[0]
        span = indices[-1] - indices[0]
        density = n_dark / max(span, 1)
        # Text has moderate density (0.02-0.3) spread across wide span
        is_text = span > w * 0.45 and 0.01 < density < 0.35
        return is_text, False

    # ── Top: find end of text block ──
    top_cut = 0
    in_text_block = False
    blank_run = 0

    for y in range(min(max_trim, h)):
        is_text, is_blank = _is_text_row(arr[y])

        if is_blank:
            blank_run += 1
            if in_text_block and blank_run > 8:
                # End of text block — check if what follows is also text or figure
                # Look ahead: if more text follows, continue; if figure, stop
                lookahead = min(y + 40, h)
                text_ahead = 0
                for ly in range(y, lookahead):
                    lt, lb = _is_text_row(arr[ly])
                    if lt:
                        text_ahead += 1
                if text_ahead > 5:
                    continue  # more text ahead, keep scanning
                else:
                    top_cut = y
                    break
            continue

        blank_run = 0
        if is_text:
            in_text_block = True
            top_cut = y + 1
        else:
            if in_text_block:
                # Transition from text to non-text content
                break
            else:
                break  # first content is already figure-like

    # ── Bottom: find start of caption/text ──
    bottom_cut = h
    in_text_block = False
    blank_run = 0

    for y in range(h - 1, max(h - max_trim, 0), -1):
        is_text, is_blank = _is_text_row(arr[y])

        if is_blank:
            blank_run += 1
            if in_text_block and blank_run > 8:
                bottom_cut = y + 1
                break
            continue

        blank_run = 0
        if is_text:
            in_text_block = True
            bottom_cut = y
        else:
            if in_text_block:
                break
            else:
                break

    # Only trim if meaningful
    did_trim = False
    if top_cut < h * 0.03:
        top_cut = 0
    else:
        did_trim = True

    if (h - bottom_cut) < h * 0.03:
        bottom_cut = h
    else:
        did_trim = True

    if did_trim:
        return img.crop((0, top_cut, w, bottom_cut))

    return img


def _qc_figure(img_path: str) -> dict:
    """Run quality checks on an extracted figure.

    Returns dict with:
      passed: bool
      issues: list of strings
      cleaned_path: str (may differ if cleaned)
    """
    issues = []
    im = Image.open(img_path).convert("RGB")
    orig_size = im.size

    # 1. Strip vertical sidebar text
    im = _strip_vertical_text(im)

    # 2. Trim body text / caption text from top/bottom
    im = _trim_text_regions(im)

    # 3. Trim excess whitespace
    im = _trim_whitespace(im, padding=8)

    # 4. Check minimum size
    w, h = im.size
    if w < 80 or h < 80:
        issues.append(f"too_small ({w}x{h})")
        return {"passed": False, "issues": issues, "cleaned_path": img_path}

    # 5. Check if image has enough content (not just whitespace)
    arr = np.array(im.convert("L"))
    content_frac = np.mean(arr < 240)
    if content_frac < 0.03:
        issues.append(f"mostly_blank (content={content_frac:.1%})")
        return {"passed": False, "issues": issues, "cleaned_path": img_path}

    # 6. Check aspect ratio (reject extremely thin strips)
    aspect = max(w, h) / max(min(w, h), 1)
    if aspect > 8:
        issues.append(f"bad_aspect ({aspect:.1f}:1)")
        return {"passed": False, "issues": issues, "cleaned_path": img_path}

    # Save cleaned version
    if im.size != orig_size:
        im.save(img_path, optimize=True)

    return {
        "passed": True,
        "issues": issues,
        "cleaned_path": img_path,
        "orig_size": orig_size,
        "clean_size": im.size,
    }


# ── Figure Extraction ───────────────────────────────────────────

def _find_figure_captions(page) -> list[tuple[int, fitz.Rect, str]]:
    """Find all figure captions on a page.

    Returns list of (figure_number, full_caption_rect, caption_text).
    The rect covers the ENTIRE caption including continuation lines,
    not just the first "Figure N." line.
    """
    text_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    pw = page.rect.width
    captions = []

    for block in text_blocks:
        if block["type"] != 0:
            continue
        lines = block.get("lines", [])
        for li, line in enumerate(lines):
            if line.get("dir", (1, 0)) != (1, 0):
                continue
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            m = re.match(r'^(?:Figure|Fig\.?|FIGURE)\s+(\d+)', line_text)
            if m:
                fig_num = int(m.group(1))
                # Extend rect to cover ALL continuation lines of this caption
                # (lines in the same block after the "Figure N" line that are
                # full-width text, i.e., part of the caption paragraph)
                cap_top = line["bbox"][1]
                cap_bottom = line["bbox"][3]
                for cont_line in lines[li + 1:]:
                    if cont_line.get("dir", (1, 0)) != (1, 0):
                        break
                    cont_width = cont_line["bbox"][2] - cont_line["bbox"][0]
                    # Caption continuation: same-width text in same block
                    if cont_width > pw * 0.15:
                        cap_bottom = cont_line["bbox"][3]
                    else:
                        break
                caption_rect = fitz.Rect(
                    line["bbox"][0], cap_top,
                    line["bbox"][2], cap_bottom,
                )
                captions.append((fig_num, caption_rect, line_text[:100]))

    captions.sort(key=lambda c: c[1].y0)
    return captions


def _find_text_content_bounds(page) -> tuple[float, float]:
    """Find the left and right bounds of actual text content on the page.

    This excludes sidebar/margin metadata text (rotated text, page numbers, etc.).
    Returns (left_x, right_x) in page coordinates.
    """
    text_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    pw = page.rect.width

    # Collect x-bounds of horizontal text only
    lefts = []
    rights = []
    for block in text_blocks:
        if block["type"] != 0:
            continue
        for line in block.get("lines", []):
            if line.get("dir", (1, 0)) != (1, 0):
                continue  # skip rotated text
            bbox = line["bbox"]
            line_text = "".join(span["text"] for span in line["spans"]).strip()
            if len(line_text) < 3:
                continue
            lefts.append(bbox[0])
            rights.append(bbox[2])

    if not lefts:
        return (0, pw)

    # Use percentile to exclude outlier positions
    left_x = max(0, float(np.percentile(lefts, 5)) - 5)
    right_x = min(pw, float(np.percentile(rights, 95)) + 5)

    return (left_x, right_x)


def extract_figures(pdf_path: Path, out_dir: Path, min_area: int = 40000) -> list[dict]:
    """Extract figures from PDF with QC.

    Strategy:
    1. Find figure captions on each page
    2. Crop figure regions using caption positions as delimiters
    3. Run QC: strip sidebars, trim captions, trim whitespace
    4. Only return figures that pass QC
    """
    doc = fitz.open(str(pdf_path))
    figures_dir = out_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    figures = []

    # Render page 1 for title slide
    page1 = doc[0]
    pix = page1.get_pixmap(matrix=fitz.Matrix(3, 3))
    p1_path = figures_dir / "page1_full.png"
    pix.save(str(p1_path))
    figures.append({
        "figure_id": "page1_full",
        "path": str(p1_path),
        "page": 1,
        "type": "page_render",
        "width": pix.width,
        "height": pix.height,
    })

    # ── Pass 1: Caption-based figure region extraction ──
    for page_num in range(len(doc)):
        page = doc[page_num]
        pw, ph = page.rect.width, page.rect.height
        captions = _find_figure_captions(page)

        if not captions:
            continue

        # Find text content bounds (exclude sidebar)
        content_left, content_right = _find_text_content_bounds(page)

        for idx, (fig_num, cap_rect, cap_text) in enumerate(captions):
            # Determine figure region: above the caption, below body text
            if idx == 0:
                raw_top = max(0, page.rect.y0 + 20)
            else:
                raw_top = captions[idx - 1][1].y1 + 3

            bottom_y = cap_rect.y0 - 2

            # ── Skip body text between previous caption and this figure ──
            # Find horizontal text blocks in the raw crop region and use
            # the bottom of the LAST full-width text block as actual top
            top_y = raw_top
            text_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
            body_text_bottom = raw_top

            for block in text_blocks:
                if block["type"] != 0:
                    continue
                bx0, by0, bx1, by1 = block["bbox"]
                # Block must be within our raw crop region
                if by0 < raw_top - 2 or by1 > bottom_y + 2:
                    continue
                # Check if this is a full-width text block (body text, not axis label)
                block_width = bx1 - bx0
                # Body text spans >40% of page width
                if block_width > pw * 0.40:
                    # Check it's horizontal text, not a figure sub-label
                    for line in block.get("lines", []):
                        if line.get("dir", (1, 0)) != (1, 0):
                            continue
                        line_text = "".join(s["text"] for s in line["spans"]).strip()
                        # Skip short labels that are part of figures
                        if len(line_text) < 20:
                            continue
                        line_bottom = line["bbox"][3]
                        if line_bottom > body_text_bottom and line_bottom < bottom_y:
                            body_text_bottom = line_bottom

            # Use the end of body text as actual top (add gap)
            if body_text_bottom > raw_top + 5:
                top_y = body_text_bottom + 3

            # Skip tiny regions
            if bottom_y - top_y < ph * 0.08:
                continue

            # Use content bounds to exclude sidebar
            crop_rect = fitz.Rect(
                content_left,
                max(0, top_y),
                content_right,
                min(ph, bottom_y),
            )

            crop_pix = page.get_pixmap(
                matrix=fitz.Matrix(FIGURE_DPI_SCALE, FIGURE_DPI_SCALE),
                clip=crop_rect,
            )

            fig_name = f"fig{fig_num}"
            fig_path = figures_dir / f"{fig_name}.png"
            crop_pix.save(str(fig_path))

            # Run QC
            qc = _qc_figure(str(fig_path))
            if not qc["passed"]:
                print(f"    Fig {fig_num} FAILED QC: {qc['issues']}")
                fig_path.unlink(missing_ok=True)
                continue

            # Read final dimensions
            final_im = Image.open(str(fig_path))
            fw, fh = final_im.size

            figures.append({
                "figure_id": fig_name,
                "path": str(fig_path),
                "page": page_num + 1,
                "type": "figure_region",
                "figure_number": fig_num,
                "caption": cap_text,
                "area": crop_rect.width * crop_rect.height,
                "width": fw,
                "height": fh,
                "qc": "passed",
            })
            orig = qc.get("orig_size", (0, 0))
            print(f"    Fig {fig_num}: p.{page_num+1} {orig[0]}x{orig[1]} → {fw}x{fh} ✓")

    # ── Pass 2: Embedded images (for pages without captions) ──
    pages_with_figures = {f["page"] for f in figures if f["type"] == "figure_region"}
    seen_xrefs = set()

    for page_num in range(len(doc)):
        if page_num + 1 in pages_with_figures:
            continue  # already have caption-based crops for this page

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
                if rect.width * rect.height < min_area:
                    continue

                padded = fitz.Rect(
                    max(0, rect.x0 - 3),
                    max(0, rect.y0 - 3),
                    min(page.rect.width, rect.x1 + 3),
                    min(page.rect.height, rect.y1 + 3),
                )
                clip_pix = page.get_pixmap(
                    matrix=fitz.Matrix(FIGURE_DPI_SCALE, FIGURE_DPI_SCALE),
                    clip=padded,
                )

                fig_name = f"p{page_num + 1}_img{img_idx}"
                fig_path = figures_dir / f"{fig_name}.png"
                clip_pix.save(str(fig_path))

                qc = _qc_figure(str(fig_path))
                if not qc["passed"]:
                    fig_path.unlink(missing_ok=True)
                    continue

                final_im = Image.open(str(fig_path))
                fw, fh = final_im.size

                figures.append({
                    "figure_id": fig_name,
                    "path": str(fig_path),
                    "page": page_num + 1,
                    "type": "embedded_image",
                    "area": rect.width * rect.height,
                    "width": fw,
                    "height": fh,
                    "qc": "passed",
                })
            except Exception as e:
                print(f"  Warning: failed to extract image xref={xref}: {e}")

    doc.close()

    # Sort: figure_region first (by figure number), then embedded
    figures.sort(key=lambda f: (
        0 if f["type"] == "page_render" else 1 if f["type"] == "figure_region" else 2,
        f.get("figure_number", 999),
        f.get("page", 0),
    ))

    qc_passed = sum(1 for f in figures if f.get("qc") == "passed")
    print(f"  Extracted {len(figures)} figures ({qc_passed} QC-passed)")
    return figures


# ── Metadata Extraction ─────────────────────────────────────────

def extract_metadata_from_text(text: str) -> dict:
    """Try to extract basic metadata from the first page text."""
    lines = text.split("\n")[:50]
    meta = {"title": "", "authors": "", "journal": "", "year": "", "doi": ""}

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

    print("[PARSER] Extracting figures with QC...")
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
