"""
Paper Blitz Pipeline — end-to-end orchestrator.

Runs: PARSE → WRITE → QA LOOP (write ↔ review) → BUILD → OUTPUT

Usage:
    python blitz/blitz_pipeline.py \
        --url "https://doi.org/10.1098/rspb.2025.2296" \
        --researcher JOP \
        --project "asymmetric prior in time estimation — normative model showing prior distribution shape transforms relative to absolute scale" \
        --connection "Both study how prior distribution shape (bimodal here, asymmetric in JOP) influences sensorimotor behavior under uncertainty; this paper validates Bayesian prior learning in naturalistic tasks, supporting JOP's normative model approach" \
        --max-iter 3
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))
os.chdir(REPO_DIR)

from blitz.parse_paper import parse_paper
from blitz.write_slides import write_slides
from blitz.blind_qa import run_qa_loop, automated_checks
from blitz.build_output import build_all
from blitz.build_hybrid import build_pptx_hybrid


def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)


def run_pipeline(url: str, researcher_context: dict, max_iterations: int = 3,
                 output_name: str = None):
    """Run the full Paper Blitz pipeline."""
    creds = load_credentials()
    api_key = creds["openrouter_api_key"]

    # Output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if output_name:
        run_dir = REPO_DIR / "blitz" / "output" / output_name
    else:
        run_dir = REPO_DIR / "blitz" / "output" / f"run_{timestamp}"
    tmp_dir = run_dir / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    log = {
        "url": url,
        "researcher": researcher_context,
        "start_time": datetime.now().isoformat(),
        "iterations": [],
    }

    # ── STAGE 1: PARSE ──────────────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 1: PARSING PAPER")
    print("=" * 70)

    parsed = parse_paper(url, str(tmp_dir))

    # ── STAGE 2+3: WRITE ↔ QA LOOP ─────────────────────────────
    revision_feedback = ""
    final_plan = None
    qa_result = None

    for iteration in range(max_iterations):
        print("\n" + "=" * 70)
        print(f"STAGE 2: WRITING SLIDES (iteration {iteration + 1}/{max_iterations})")
        print("=" * 70)

        write_result = write_slides(
            parsed,
            researcher_context,
            revision_feedback=revision_feedback,
        )
        current_plan = write_result["plan"]

        # Run automated checks first (fast, no LLM)
        auto = automated_checks(current_plan)
        if not auto["passed"]:
            print(f"\n  ⚠ Automated checks failed:")
            for issue in auto["issues"]:
                print(f"    - {issue}")

        print("\n" + "=" * 70)
        print(f"STAGE 3: BLIND QA REVIEW (iteration {iteration + 1}/{max_iterations})")
        print("=" * 70)

        qa_result = run_qa_loop(
            parsed["full_text"],
            current_plan,
            api_key,
            max_iterations=1,  # Single review per write iteration
        )

        log["iterations"].append({
            "iteration": iteration + 1,
            "plan": current_plan,
            "qa_scores": qa_result["iterations"][-1]["scores"] if qa_result["iterations"] else {},
            "qa_verdict": qa_result["final_verdict"],
            "auto_checks": auto,
        })

        if qa_result["final_verdict"] == "PASS":
            print(f"\n✓ PASSED on write-review iteration {iteration + 1}")
            final_plan = current_plan
            break

        if iteration < max_iterations - 1:
            revision_feedback = qa_result["revision_feedback"]
            if auto["issues"]:
                revision_feedback += "\n\nAUTOMATED FAILURES:\n"
                for issue in auto["issues"]:
                    revision_feedback += f"- {issue}\n"
            print(f"\n→ Revision feedback prepared ({len(revision_feedback)} chars)")
        else:
            print(f"\n✗ Max iterations reached. Proceeding with best available plan.")
            final_plan = current_plan

    if final_plan is None:
        final_plan = current_plan

    # ── STAGE 4: BUILD OUTPUT ───────────────────────────────────
    print("\n" + "=" * 70)
    print("STAGE 4: BUILDING OUTPUT")
    print("=" * 70)

    # Build hybrid PPTX first (native paradigm + paper crops)
    hybrid_pptx = run_dir / "paper_blitz.pptx"
    build_pptx_hybrid(final_plan, parsed["figures"], tmp_dir, hybrid_pptx)

    # Build rest (TTS, video) using original build_all
    build_result = build_all(
        final_plan,
        parsed["figures"],
        tmp_dir,
        run_dir,
    )
    # Override with hybrid PPTX path
    build_result["pptx_path"] = str(hybrid_pptx)
    build_result["pptx_hybrid"] = True

    # ── SAVE FINAL REPORT ───────────────────────────────────────
    log["end_time"] = datetime.now().isoformat()
    log["final_verdict"] = qa_result["final_verdict"] if qa_result else "N/A"
    log["total_iterations"] = len(log["iterations"])
    log["outputs"] = build_result

    report_path = run_dir / "pipeline_report.json"
    with open(report_path, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)

    # ── SUMMARY ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    print(f"  Output directory: {run_dir}")
    print(f"  PPTX: {build_result['pptx_path']}")
    print(f"  MP4:  {build_result['video_path']}")
    print(f"  Script: {build_result['script_path']}")
    print(f"  QA verdict: {log['final_verdict']}")
    print(f"  Iterations: {log['total_iterations']}")
    if qa_result and qa_result["iterations"]:
        last_scores = qa_result["iterations"][-1].get("scores", {})
        print(f"  Final scores: {last_scores}")
    print(f"  Report: {report_path}")

    return log


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CSNL Paper Blitz Pipeline")
    parser.add_argument("--url", required=True, help="Paper URL (DOI or direct link)")
    parser.add_argument("--researcher", default="JOP", help="Target researcher name")
    parser.add_argument("--project", default=(
        "asymmetric prior in time estimation — normative model showing "
        "prior distribution shape transforms relative scale to absolute scale"
    ))
    parser.add_argument("--connection", default=(
        "Both study how prior distribution shape (bimodal here, asymmetric in JOP) "
        "influences sensorimotor/perceptual behavior under uncertainty; "
        "this paper validates implicit Bayesian prior learning in naturalistic tasks, "
        "supporting JOP's normative model that prior shape qualitatively "
        "transforms scale-dependent estimation"
    ))
    parser.add_argument("--max-iter", type=int, default=3, help="Max write-review iterations")
    parser.add_argument("--name", default=None, help="Output run name")
    parser.add_argument("--fast", action="store_true",
                        help="Use faster paid model (google/gemini-2.5-flash) instead of free Qwen")
    args = parser.parse_args()

    if args.fast:
        os.environ["BLITZ_MODEL"] = "google/gemini-2.5-flash"
        print("[PIPELINE] Fast mode: using google/gemini-2.5-flash")

    researcher_context = {
        "name": args.researcher,
        "project": args.project,
        "connection": args.connection,
    }

    run_pipeline(args.url, researcher_context, args.max_iter, args.name)
