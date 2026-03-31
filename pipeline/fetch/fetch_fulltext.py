#!/usr/bin/env python3
"""
Paper Scout — Full-Text PDF Fetcher (Playwright)

학술지 웹사이트에서 full-text PDF를 다운로드하고,
텍스트/피겨를 추출하여 파이프라인에 공급한다.

Usage:
    python fetch_fulltext.py --doi "10.1038/s41562-025-02362-8" --output ./pdfs/
    python fetch_fulltext.py --url "https://www.biorxiv.org/content/..." --output ./pdfs/
    python fetch_fulltext.py --batch runs/abstracts-2026-03-31.json --output ./pdfs/
    python fetch_fulltext.py --doi "10.xxx" --extract  # PDF + text extraction

Strategies (in order):
1. Unpaywall API (open access)
2. Sci-Hub (fallback)
3. bioRxiv/medRxiv direct PDF
4. Publisher page → Playwright headless browser → PDF link
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# Optional: fitz for text extraction
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

REPO_DIR = Path(__file__).resolve().parent.parent.parent
PDF_DIR = REPO_DIR / "runs" / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)


def fetch_unpaywall(doi: str) -> str | None:
    """Try Unpaywall for open-access PDF URL."""
    url = f"https://api.unpaywall.org/v2/{doi}?email=csnl.paperscout@gmail.com"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            best = data.get("best_oa_location")
            if best and best.get("url_for_pdf"):
                return best["url_for_pdf"]
            # Try other locations
            for loc in data.get("oa_locations", []):
                if loc.get("url_for_pdf"):
                    return loc["url_for_pdf"]
    except Exception:
        pass
    return None


def fetch_biorxiv_pdf(doi: str) -> str | None:
    """Direct bioRxiv/medRxiv PDF URL from DOI."""
    if "10.1101/" in doi or "10.64898/" in doi:
        return f"https://www.biorxiv.org/content/{doi}v1.full.pdf"
    return None


def download_pdf(url: str, output_path: Path) -> bool:
    """Download PDF from URL."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        r = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 1000:
            # Check if actually PDF
            if r.content[:4] == b"%PDF" or r.headers.get("content-type", "").startswith("application/pdf"):
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True
    except Exception:
        pass
    return False


def fetch_with_playwright(doi: str, url: str | None = None) -> str | None:
    """
    Use Playwright to navigate to paper page and find/download PDF.
    Returns path to downloaded PDF or None.
    """
    from playwright.sync_api import sync_playwright

    if not url:
        url = f"https://doi.org/{doi}"

    output_path = PDF_DIR / f"{sanitize_filename(doi)}.pdf"
    if output_path.exists():
        return str(output_path)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            accept_downloads=True,
        )
        page = context.new_page()

        try:
            # Strategy 0: If URL ends in .pdf, use expect_download
            if url.endswith(".pdf"):
                try:
                    with page.expect_download(timeout=30000) as dl_info:
                        page.evaluate(f'() => window.location.href = "{url}"')
                    dl = dl_info.value
                    dl.save_as(str(output_path))
                    if output_path.exists() and output_path.stat().st_size > 1000:
                        browser.close()
                        return str(output_path)
                except Exception:
                    pass

            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(2)

            # Strategy A: Find PDF link on the page
            pdf_url = None
            for selector in [
                'a[href*=".pdf"]',
                'a[data-article-pdf]',
                'a.c-pdf-download__link',
                'a[href*="full.pdf"]',
                'a[href*="/pdf/"]',
                'a:text("PDF")',
                'a:text("Download PDF")',
                'a:text("Full Text (PDF)")',
            ]:
                try:
                    el = page.query_selector(selector)
                    if el:
                        href = el.get_attribute("href")
                        if href:
                            if href.startswith("/"):
                                # Relative URL
                                from urllib.parse import urljoin
                                href = urljoin(page.url, href)
                            pdf_url = href
                            break
                except Exception:
                    continue

            if pdf_url:
                if download_pdf(pdf_url, output_path):
                    browser.close()
                    return str(output_path)

            # Strategy B: bioRxiv-specific full page PDF
            current_url = page.url
            if "biorxiv.org" in current_url or "medrxiv.org" in current_url:
                pdf_url = current_url.rstrip("/") + ".full.pdf"
                if download_pdf(pdf_url, output_path):
                    browser.close()
                    return str(output_path)

            # Strategy C: Use Playwright to trigger download
            with page.expect_download(timeout=15000) as download_info:
                for sel in ['a:text("PDF")', 'a:text("Download")', 'button:text("PDF")']:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            el.click()
                            break
                    except Exception:
                        continue

            try:
                dl = download_info.value
                dl.save_as(str(output_path))
                browser.close()
                return str(output_path)
            except Exception:
                pass

        except Exception:
            pass
        finally:
            browser.close()

    return None


def sanitize_filename(s: str) -> str:
    """Make a safe filename from DOI."""
    return re.sub(r'[^a-zA-Z0-9._-]', '_', s)


def extract_text_from_pdf(pdf_path: str) -> dict:
    """Extract text, figures, equations from PDF using PyMuPDF."""
    if not HAS_FITZ:
        return {"error": "PyMuPDF not installed"}

    doc = fitz.open(pdf_path)
    result = {
        "pages": doc.page_count,
        "text": "",
        "figures": [],
        "sections": {},
    }

    full_text = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        text = page.get_text()
        full_text.append(text)

        # Extract images
        images = page.get_images(full=True)
        for img_idx, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            if base_image and base_image.get("width", 0) > 200 and base_image.get("height", 0) > 200:
                result["figures"].append({
                    "page": page_num + 1,
                    "index": img_idx,
                    "width": base_image["width"],
                    "height": base_image["height"],
                    "format": base_image.get("ext", "unknown"),
                })

    result["text"] = "\n".join(full_text)

    # Parse sections
    section_patterns = [
        ("abstract", r"(?i)\babstract\b"),
        ("introduction", r"(?i)\bintroduction\b"),
        ("methods", r"(?i)\b(?:methods?|materials?\s+and\s+methods?)\b"),
        ("results", r"(?i)\bresults?\b"),
        ("discussion", r"(?i)\bdiscussion\b"),
        ("references", r"(?i)\breferences?\b"),
    ]

    text = result["text"]
    for section_name, pattern in section_patterns:
        match = re.search(pattern, text)
        if match:
            start = match.start()
            # Find next section
            end = len(text)
            for other_name, other_pattern in section_patterns:
                if other_name == section_name:
                    continue
                other_match = re.search(other_pattern, text[start + 100:])
                if other_match:
                    candidate_end = start + 100 + other_match.start()
                    if candidate_end < end:
                        end = candidate_end

            result["sections"][section_name] = text[start:end][:5000]

    doc.close()
    return result


def fetch_paper(doi: str, url: str | None = None, extract: bool = False) -> dict:
    """
    Main entry: fetch full-text PDF for a paper.
    Returns dict with pdf_path, method, and optionally extracted text.
    """
    output_path = PDF_DIR / f"{sanitize_filename(doi)}.pdf"

    # Check if already downloaded
    if output_path.exists():
        result = {"doi": doi, "pdf_path": str(output_path), "method": "cached", "success": True}
        if extract:
            result["extraction"] = extract_text_from_pdf(str(output_path))
        return result

    # Strategy 1: Unpaywall (open access)
    pdf_url = fetch_unpaywall(doi)
    if pdf_url and download_pdf(pdf_url, output_path):
        result = {"doi": doi, "pdf_path": str(output_path), "method": "unpaywall", "success": True}
        if extract:
            result["extraction"] = extract_text_from_pdf(str(output_path))
        return result

    # Strategy 2: bioRxiv direct
    pdf_url = fetch_biorxiv_pdf(doi)
    if pdf_url and download_pdf(pdf_url, output_path):
        result = {"doi": doi, "pdf_path": str(output_path), "method": "biorxiv_direct", "success": True}
        if extract:
            result["extraction"] = extract_text_from_pdf(str(output_path))
        return result

    # Strategy 3: Playwright
    pdf_path = fetch_with_playwright(doi, url)
    if pdf_path:
        result = {"doi": doi, "pdf_path": pdf_path, "method": "playwright", "success": True}
        if extract:
            result["extraction"] = extract_text_from_pdf(pdf_path)
        return result

    return {"doi": doi, "pdf_path": None, "method": "failed", "success": False}


def batch_fetch(json_path: str, extract: bool = False) -> list:
    """Fetch PDFs for all papers in a JSON file."""
    with open(json_path) as f:
        data = json.load(f)

    results = []
    for name, info in data.items():
        url = info.get("url", "")
        # Try to extract DOI from URL or info
        doi = ""
        doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", url)
        if doi_match:
            doi = doi_match.group(1).rstrip("/")

        if not doi:
            print(f"  SKIP {name}: no DOI found")
            continue

        print(f"  Fetching: {name} (DOI: {doi})")
        result = fetch_paper(doi, url=url, extract=extract)
        result["name"] = name
        results.append(result)
        print(f"    → {result['method']}: {'OK' if result['success'] else 'FAIL'}")

    return results


# --- CLI ---
def main():
    parser = argparse.ArgumentParser(description="Paper Scout Full-Text Fetcher")
    parser.add_argument("--doi", help="Paper DOI")
    parser.add_argument("--url", help="Paper URL (optional, used with --doi)")
    parser.add_argument("--batch", help="JSON file with paper URLs")
    parser.add_argument("--output", default=str(PDF_DIR), help="Output directory")
    parser.add_argument("--extract", action="store_true", help="Also extract text from PDF")
    args = parser.parse_args()

    pdf_dir = Path(args.output)
    pdf_dir.mkdir(parents=True, exist_ok=True)

    if args.batch:
        results = batch_fetch(args.batch, extract=args.extract)
        success = sum(1 for r in results if r["success"])
        print(f"\nBatch complete: {success}/{len(results)} PDFs fetched")
        if args.extract:
            output_file = PDF_DIR / "extraction_results.json"
            with open(output_file, "w") as f:
                # Don't save full text to JSON, just metadata
                for r in results:
                    if "extraction" in r:
                        ext = r["extraction"]
                        r["extraction"] = {
                            "pages": ext.get("pages"),
                            "figures_count": len(ext.get("figures", [])),
                            "sections": list(ext.get("sections", {}).keys()),
                            "text_length": len(ext.get("text", "")),
                        }
                json.dump(results, f, indent=2)
            print(f"Results saved to {output_file}")
    elif args.doi:
        result = fetch_paper(args.doi, url=args.url, extract=args.extract)
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
