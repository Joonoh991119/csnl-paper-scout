"""
Analyze extra papers (downloaded from eLife, etc.) through the style pipeline.
These papers are NOT in Zotero — they're in style_knowledge/extra_papers/.
"""

import json
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from blitz.style_state import load_state, save_state, append_to_log, update_pattern_stats, count_new_patterns
from blitz.style_analyzer import analyze_paper, _load_credentials


def main():
    extra_dir = REPO_DIR / "blitz" / "style_knowledge" / "extra_papers"
    index_path = extra_dir / "index.json"

    if not index_path.exists():
        # Just find all PDFs
        pdfs = list(extra_dir.glob("*.pdf"))
    else:
        with open(index_path) as f:
            papers = json.load(f)
        pdfs = [Path(p["pdf_path"]) for p in papers if Path(p["pdf_path"]).exists()]

    print(f"Found {len(pdfs)} extra PDFs to analyze")

    state = load_state()
    api_key = _load_credentials()
    analyzed_keys = set(state["papers_analyzed"].keys())

    total_new_figs = 0
    for i, pdf_path in enumerate(pdfs):
        key = f"extra_{pdf_path.stem}"
        if key in analyzed_keys:
            continue

        print(f"\n[{i+1}/{len(pdfs)}] {pdf_path.name[:60]}...")
        try:
            result = analyze_paper(key, pdf_path, api_key)
            analyses = result.get("analyses", [])

            if analyses:
                append_to_log(analyses)
                update_pattern_stats(state, analyses)
                total_new_figs += len(analyses)

            state["papers_analyzed"][key] = {
                "title": pdf_path.stem,
                "journal": "eLife",
                "tier": 2,
                "figures_extracted": result["n_figures"],
                "figures_analyzed": result["n_analyzed"],
            }
            state["loop_count"] += 1
            save_state(state)

            print(f"  Extracted {result['n_figures']} figs, analyzed {result['n_analyzed']}")

        except Exception as e:
            print(f"  [ERROR] {e}")
            continue

    print(f"\nDone. {total_new_figs} new figures analyzed.")
    print(f"Total: {state['pattern_stats']['n_figures_analyzed']} figures from {len(state['papers_analyzed'])} papers")


if __name__ == "__main__":
    main()
