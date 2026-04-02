"""
Fetch papers by DOI from open access sources.
Uses Unpaywall API (free) to find OA PDF links.
"""

import json
import os
import sys
import time
from pathlib import Path

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = REPO_DIR / "blitz" / "style_knowledge" / "extra_papers"

# Curated list of OA papers with excellent figures
DOIS = [
    # eLife
    "10.7554/eLife.79277",
    "10.7554/eLife.81511",
    "10.7554/eLife.86512",
    "10.7554/eLife.80281",
    "10.7554/eLife.73610",
    "10.7554/eLife.76101",
    "10.7554/eLife.84088",
    "10.7554/eLife.74068",
    # Nature Neuroscience
    "10.1038/s41593-022-01088-4",
    "10.1038/s41593-023-01304-9",
    "10.1038/s41593-022-01207-1",
    "10.1038/s41593-023-01460-y",
    # Nature Human Behaviour
    "10.1038/s41562-022-01467-6",
    "10.1038/s41562-023-01557-z",
    "10.1038/s41562-022-01510-6",
    # Neuron
    "10.1016/j.neuron.2022.09.001",
    "10.1016/j.neuron.2023.03.025",
    "10.1016/j.neuron.2022.12.008",
    # Current Biology
    "10.1016/j.cub.2022.09.012",
    "10.1016/j.cub.2023.01.032",
    "10.1016/j.cub.2023.06.060",
    "10.1016/j.cub.2022.05.053",
]

EMAIL = "joonoh@csnl.snu.ac.kr"  # Required by Unpaywall


def find_oa_pdf(doi: str) -> str | None:
    """Find open access PDF URL via Unpaywall API."""
    url = f"https://api.unpaywall.org/v2/{doi}?email={EMAIL}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        best = data.get("best_oa_location") or {}
        pdf_url = best.get("url_for_pdf") or best.get("url")
        return pdf_url
    except Exception:
        return None


def download_pdf(url: str, out_path: Path) -> bool:
    try:
        r = requests.get(url, timeout=60, allow_redirects=True,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 10000:
            with open(out_path, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False


def main():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for doi in DOIS:
        safe_name = doi.replace("/", "_").replace(".", "_")
        out_path = DOWNLOAD_DIR / f"{safe_name}.pdf"

        if out_path.exists():
            print(f"  [SKIP] {doi} (already exists)")
            results.append({"doi": doi, "path": str(out_path), "status": "exists"})
            continue

        print(f"  Finding OA link: {doi}...")
        pdf_url = find_oa_pdf(doi)
        if not pdf_url:
            print(f"    No OA PDF found")
            results.append({"doi": doi, "status": "no_oa"})
            time.sleep(0.5)
            continue

        print(f"    Downloading from {pdf_url[:60]}...")
        if download_pdf(pdf_url, out_path):
            size_kb = out_path.stat().st_size / 1024
            print(f"    OK ({size_kb:.0f} KB)")
            results.append({"doi": doi, "path": str(out_path), "status": "ok"})
        else:
            print(f"    Download failed")
            results.append({"doi": doi, "status": "download_failed"})

        time.sleep(1)  # Be nice

    ok = sum(1 for r in results if r["status"] in ("ok", "exists"))
    print(f"\nDownloaded: {ok}/{len(DOIS)}")

    with open(DOWNLOAD_DIR / "doi_index.json", "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
