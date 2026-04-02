"""
Fetch additional open-access papers from eLife for figure analysis.

eLife papers are fully open access — PDFs can be downloaded directly.
Uses eLife API to find cognitive neuroscience papers with figures.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = REPO_DIR / "blitz" / "style_knowledge" / "extra_papers"


def search_elife(query: str, per_page: int = 25) -> list[dict]:
    """Search eLife API for papers."""
    url = "https://api.elifesciences.org/search"
    params = {
        "for": query,
        "per-page": per_page,
        "page": 1,
        "sort": "date",
        "order": "desc",
        "type[]": "research-article",
    }
    r = requests.get(url, params=params, timeout=30)
    if r.status_code != 200:
        print(f"eLife API error: {r.status_code}")
        return []
    data = r.json()
    return data.get("items", [])


def download_pdf(article_id: str, out_dir: Path) -> Path | None:
    """Download eLife paper PDF."""
    pdf_url = f"https://elifesciences.org/download/aHR0cHM6Ly9jZG4uZWxpZmVzY2llbmNlcy5vcmcvYXJ0aWNsZXMve2lkfS9lbGlmZS17aWR9LXYxLnBkZg==/elife-{article_id}-v1.pdf"
    # Actually, eLife PDFs follow a simpler pattern
    pdf_url = f"https://cdn.elifesciences.org/articles/{article_id}/elife-{article_id}-v1.pdf"

    out_path = out_dir / f"elife-{article_id}.pdf"
    if out_path.exists():
        return out_path

    try:
        r = requests.get(pdf_url, timeout=60, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 10000:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        # Try v2, v3
        for v in [2, 3, 4]:
            pdf_url_v = f"https://cdn.elifesciences.org/articles/{article_id}/elife-{article_id}-v{v}.pdf"
            r = requests.get(pdf_url_v, timeout=60, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(out_path, "wb") as f:
                    f.write(r.content)
                return out_path
    except Exception as e:
        print(f"  Download failed for {article_id}: {e}")
    return None


def fetch_elife_batch(queries: list[str], max_per_query: int = 15) -> list[dict]:
    """Fetch papers from eLife for multiple search queries."""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    all_papers = []
    seen_ids = set()

    for query in queries:
        print(f"\nSearching eLife: '{query}'...")
        results = search_elife(query, per_page=max_per_query)
        print(f"  Found {len(results)} results")

        for item in results:
            article_id = str(item.get("id", ""))
            if not article_id or article_id in seen_ids:
                continue
            seen_ids.add(article_id)

            title = item.get("title", "")
            print(f"  Downloading: {title[:60]}...")

            pdf_path = download_pdf(article_id, DOWNLOAD_DIR)
            if pdf_path:
                all_papers.append({
                    "article_id": article_id,
                    "title": title,
                    "journal": "eLife",
                    "pdf_path": str(pdf_path),
                    "tier": 2,
                })
                print(f"    OK ({pdf_path.stat().st_size / 1024:.0f} KB)")
            else:
                print(f"    FAILED")

            time.sleep(0.5)  # Be nice to API

    # Save index
    index_path = DOWNLOAD_DIR / "index.json"
    with open(index_path, "w") as f:
        json.dump(all_papers, f, indent=2, ensure_ascii=False)

    print(f"\nTotal papers downloaded: {len(all_papers)}")
    return all_papers


if __name__ == "__main__":
    queries = [
        "visual perception psychophysics",
        "working memory fMRI",
        "decision making neural",
        "Bayesian brain computation",
        "sensory coding neural population",
        "attention EEG",
        "motor learning adaptation",
        "reinforcement learning human",
    ]
    papers = fetch_elife_batch(queries, max_per_query=10)
    print(f"\nDone. {len(papers)} papers saved to {DOWNLOAD_DIR}")
