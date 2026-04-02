#!/usr/bin/env python3
"""
Style Learner — Main harness for Find→Learn→Review→Record loop.

Iterates through Zotero library extracting figure design parameters,
building a statistical style knowledge base, and periodically validating
with GAN-like adversarial tests.

Usage:
    python blitz/style_learner.py --max-loops 50
    python blitz/style_learner.py --max-loops 10 --batch-size 3 --tier 1,2
    python blitz/style_learner.py --dry-run
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from blitz.style_state import (
    load_state, save_state, build_queue, dequeue, find_pdf,
    mark_analyzed, append_to_log, update_pattern_stats,
    count_new_patterns, check_convergence, STATE_DIR,
)
from blitz.style_analyzer import analyze_paper
from blitz.style_gan_test import run_gan_test


def _load_credentials() -> str:
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)["openrouter_api_key"]


# ── Batch Validation (Phase C: Review) ────────────────────────

def validate_batch(results: list[dict], stats: dict) -> list[str]:
    """Check for outliers and inconsistencies in batch results."""
    warnings = []

    for r in results:
        # Whitespace outliers
        ws = r.get("whitespace_ratio")
        if ws is not None and (ws < 0.05 or ws > 0.60):
            warnings.append(
                f"  [OUTLIER] {r.get('figure_id')}: whitespace={ws:.2f} "
                f"(expected 0.10-0.50)"
            )

        # Color validation failures
        if r.get("_color_validation") == "mismatch":
            llm_c = r.get("colors", {}).get("dominant_palette", [])
            pix_c = r.get("_pixel_dominant_colors", [])
            warnings.append(
                f"  [COLOR MISMATCH] {r.get('figure_id')}: "
                f"LLM={llm_c[:2]} vs Pixel={pix_c[:2]}"
            )

        # Dense text warning
        if r.get("typography", {}).get("text_density") == "dense":
            warnings.append(
                f"  [DENSE] {r.get('figure_id')}: text_density=dense "
                f"(unusual for top journals)"
            )

    return warnings


# ── Report Generation ─────────────────────────────────────────

def print_batch_summary(loop_i: int, results: list[dict],
                        new_patterns: int, warnings: list[str]):
    """Print summary of one loop iteration."""
    n = len(results)
    types = {}
    for r in results:
        ft = r.get("figure_type", "unknown")
        types[ft] = types.get(ft, 0) + 1

    print(f"\n{'='*60}")
    print(f"Loop {loop_i + 1} — {n} figures analyzed")
    print(f"  Types: {types}")
    print(f"  New patterns: {new_patterns}")
    if warnings:
        print(f"  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    {w}")
    print(f"{'='*60}")


def generate_final_report(state: dict):
    """Generate markdown summary of all learned patterns."""
    stats = state["pattern_stats"]
    n = stats["n_figures_analyzed"]
    n_papers = len(state["papers_analyzed"])

    report = f"""# Style Learning Report
Generated: {datetime.now(timezone.utc).isoformat()}

## Summary
- Papers analyzed: {n_papers}
- Figures analyzed: {n}
- Loop iterations: {state['loop_count']}
- GAN tests: {len(state['convergence']['gan_pass_rates'])}

## Figure Type Distribution
"""
    for ft, count in sorted(stats.get("figure_type_counts", {}).items(),
                            key=lambda x: -x[1]):
        pct = count / n * 100 if n else 0
        report += f"- {ft}: {count} ({pct:.0f}%)\n"

    report += "\n## Layout Patterns\n"
    total_layouts = sum(stats.get("layout_counts", {}).values()) or 1
    for layout, count in sorted(stats.get("layout_counts", {}).items(),
                                key=lambda x: -x[1]):
        pct = count / total_layouts * 100
        report += f"- {layout}: {count} ({pct:.0f}%)\n"

    report += "\n## Spine Styles\n"
    total_spines = sum(stats.get("spine_counts", {}).values()) or 1
    for spine, count in sorted(stats.get("spine_counts", {}).items(),
                               key=lambda x: -x[1]):
        pct = count / total_spines * 100
        report += f"- {spine}: {count} ({pct:.0f}%)\n"

    report += "\n## Panel Label Styles\n"
    total_pl = sum(stats.get("panel_label_counts", {}).values()) or 1
    for pl, count in sorted(stats.get("panel_label_counts", {}).items(),
                            key=lambda x: -x[1]):
        pct = count / total_pl * 100
        report += f"- {pl}: {count} ({pct:.0f}%)\n"

    report += "\n## Color Clusters\n"
    for i, cluster in enumerate(stats.get("color_clusters", [])[:15]):
        colors = cluster.get("colors", [])
        count = cluster.get("count", 0)
        report += f"- Cluster {i+1}: {colors} (seen {count}x)\n"

    report += "\n## Whitespace\n"
    ws_vals = stats.get("whitespace_values", [])
    if ws_vals:
        avg = sum(ws_vals) / len(ws_vals)
        report += f"- Mean: {avg:.2f}\n"
        report += f"- Min: {min(ws_vals):.2f}, Max: {max(ws_vals):.2f}\n"

    report += "\n## Convergence\n"
    pats = state["convergence"]["patterns_per_batch"]
    if pats:
        report += f"- Patterns per batch: {pats}\n"
    gan_rates = state["convergence"]["gan_pass_rates"]
    if gan_rates:
        report += f"- GAN pass rates: {gan_rates}\n"

    report_path = STATE_DIR / "style_learning_report.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")


# ── Main Loop ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Style Learning Harness")
    parser.add_argument("--max-loops", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--gan-interval", type=int, default=5)
    parser.add_argument("--tier", type=str, default=None,
                        help="Comma-separated tiers, e.g. '1,2'")
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load state
    state = load_state()
    api_key = _load_credentials()

    # Build/rebuild queue if empty
    if not state["queue"]:
        print("Building paper queue from Zotero...")
        state["queue"] = build_queue(state)

    # Filter by tier if specified
    if args.tier:
        tiers = set(int(t) for t in args.tier.split(","))
        state["queue"] = [p for p in state["queue"] if p["tier"] in tiers]

    total_queued = len(state["queue"])
    print(f"Queue: {total_queued} papers")
    if args.dry_run:
        for t in [1, 2, 3]:
            tc = sum(1 for p in state["queue"] if p["tier"] == t)
            print(f"  Tier {t}: {tc}")
        est_loops = (total_queued + args.batch_size - 1) // args.batch_size
        est_cost = est_loops * 0.035 + (est_loops // args.gan_interval) * 0.17
        print(f"  Estimated loops: {est_loops}")
        print(f"  Estimated cost: ~${est_cost:.2f}")
        return

    save_state(state)

    for loop_i in range(args.max_loops):
        loop_start = time.time()
        state["loop_count"] += 1

        # ── Phase A: Find ──────────────────────────────────
        batch = dequeue(state, args.batch_size)
        if not batch:
            print("Queue exhausted.")
            break

        print(f"\n{'#'*60}")
        print(f"# LOOP {loop_i + 1} / {args.max_loops}")
        print(f"# Papers: {[p['title'][:40] for p in batch]}")
        print(f"{'#'*60}")

        # ── Phase B: Learn ─────────────────────────────────
        all_analyses = []
        for paper in batch:
            key = paper["storage_key"]
            pdf = find_pdf(key)
            if not pdf:
                print(f"  [SKIP] PDF not found: {key}")
                continue

            print(f"\n  Analyzing: {paper['title'][:60]}...")
            try:
                result = analyze_paper(key, pdf, api_key)
                analyses = result.get("analyses", [])
                all_analyses.extend(analyses)

                mark_analyzed(
                    state, key, paper,
                    n_figures=result["n_figures"],
                    n_analyzed=result["n_analyzed"],
                    new_patterns=0,  # updated below
                )
                print(f"    Extracted {result['n_figures']} figs, "
                      f"analyzed {result['n_analyzed']}")
            except Exception as e:
                print(f"    [ERROR] {e}")
                continue

        if not all_analyses:
            print("  No figures analyzed in this batch.")
            save_state(state)
            continue

        # ── Phase C: Review ────────────────────────────────
        warnings = validate_batch(all_analyses, state["pattern_stats"])
        new_patterns = count_new_patterns(all_analyses, state["pattern_stats"])
        state["convergence"]["patterns_per_batch"].append(new_patterns)

        # ── Phase D: Record ────────────────────────────────
        append_to_log(all_analyses)
        update_pattern_stats(state, all_analyses)
        save_state(state)

        elapsed = time.time() - loop_start
        print_batch_summary(loop_i, all_analyses, new_patterns, warnings)
        print(f"  Time: {elapsed:.1f}s")

        # ── Phase E: GAN Test ──────────────────────────────
        if (loop_i + 1) % args.gan_interval == 0:
            print(f"\n  {'*'*40}")
            print(f"  * GAN ADVERSARIAL TEST (loop {loop_i + 1})")
            print(f"  {'*'*40}")
            try:
                gan_result = run_gan_test(state, api_key, n_tests=3)
                state["convergence"]["gan_pass_rates"].append(
                    gan_result["pass_rate"]
                )
                save_state(state)
            except Exception as e:
                print(f"  [GAN ERROR] {e}")

        # ── Convergence Check ──────────────────────────────
        if check_convergence(state):
            print(f"\n*** CONVERGED after {loop_i + 1} loops ***")
            break

    # Final report
    generate_final_report(state)
    print(f"\nDone. {state['loop_count']} loops, "
          f"{state['pattern_stats']['n_figures_analyzed']} figures analyzed.")


if __name__ == "__main__":
    main()
