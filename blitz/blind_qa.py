"""
Blind QA Reviewer — adversarial evaluation with iterative feedback loop.

The reviewer NEVER sees the writer's intermediate reasoning. It receives only:
  A) Original paper full text
  B) Generated slide content + narration scripts

On failure, it provides specific revision instructions that feed back to the writer.
This creates a reinforcement loop: write → review → revise → re-review → ...

Usage:
    python blitz/blind_qa.py --parsed blitz/tmp/parsed.json --plan blitz/tmp/slide_plan.json
"""

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

# Use a DIFFERENT model than the writer to avoid systematic blind spots
QA_MODEL = os.environ.get("BLITZ_QA_MODEL", os.environ.get("BLITZ_MODEL", "qwen/qwen3.6-plus-preview:free"))
MAX_TOKENS = 6000
TEMPERATURE = 0.2  # Low temperature for strict evaluation

PASS_THRESHOLD = 4.0  # Weighted average must be >= 4.0
MIN_PER_DIM = 4       # Every dimension must be >= 4
MAX_ITERATIONS = 3    # Max revision cycles

WEIGHTS = {
    "F1": 0.30,  # Factual accuracy
    "F2": 0.20,  # Figure-text alignment
    "F3": 0.15,  # Slide parsimony
    "F4": 0.20,  # Scientific interpretation
    "F5": 0.15,  # Why-this-paper specificity
}


def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)


def load_agent_prompt():
    with open(REPO_DIR / "blitz" / "agents" / "blind_qa.md") as f:
        return f.read()


def call_openrouter(messages: list, model: str, api_key: str,
                    max_tokens: int = MAX_TOKENS) -> str:
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": TEMPERATURE,
        },
        timeout=120,
    )
    d = r.json()
    if "error" in d:
        raise RuntimeError(f"OpenRouter error: {d['error']}")
    return d["choices"][0]["message"]["content"]


# ── Score Parsing ───────────────────────────────────────────────

def parse_scores(response: str) -> dict:
    """Extract F1-F5 scores from reviewer response."""
    scores = {}
    for dim in ["F1", "F2", "F3", "F4", "F5"]:
        # Look for patterns like "F1: Factual Accuracy — 4/5" or "### F1: ... — 3/5"
        patterns = [
            rf'{dim}[^—\n]*—\s*(\d)/5',
            rf'{dim}[^:]*:\s*(\d)/5',
            rf'\*\*{dim}[^*]*\*\*[^0-9]*(\d)/5',
            rf'{dim}.*?(\d)\s*/\s*5',
        ]
        for pat in patterns:
            m = re.search(pat, response)
            if m:
                scores[dim] = int(m.group(1))
                break
    return scores


def compute_weighted_avg(scores: dict) -> float:
    """Compute weighted average score."""
    if not scores:
        return 0.0
    total = sum(scores.get(dim, 0) * w for dim, w in WEIGHTS.items())
    return total


def extract_revision_instructions(response: str) -> str:
    """Extract revision instructions from reviewer response."""
    # Look for revision section
    markers = [
        "### Revision instructions",
        "## Revision instructions",
        "**Revision instructions**",
        "Revision instructions",
    ]
    for marker in markers:
        idx = response.find(marker)
        if idx != -1:
            return response[idx:]

    # Fallback: extract everything after "REVISE" or "FAIL" verdict
    for verdict in ["REVISE", "FAIL"]:
        idx = response.find(f"**Verdict: {verdict}**")
        if idx != -1:
            return response[idx:]

    return ""


def extract_verdict(response: str) -> str:
    """Extract PASS/REVISE/FAIL verdict."""
    if "PASS" in response and "Verdict" in response:
        # Check it's the actual verdict, not just mentioning the word
        if re.search(r'Verdict:\s*\*?\*?PASS', response):
            return "PASS"
    if re.search(r'Verdict:\s*\*?\*?FAIL', response):
        return "FAIL"
    return "REVISE"  # Default to REVISE if unclear


# ── Automated Design Checks ────────────────────────────────────

def automated_checks(plan: dict) -> dict:
    """Run automated design compliance checks (no LLM needed)."""
    issues = []
    slides = plan.get("slides", [])

    # Check 1: Total narration time
    total_dur = sum(s.get("estimated_duration_sec", 60) for s in slides)
    if total_dur > 330:  # 5.5 min with some buffer
        issues.append(f"TIMING: Total estimated duration {total_dur}s exceeds 5 minutes")

    # Check 2: Slide count
    if len(slides) < 3:
        issues.append(f"SLIDES: Only {len(slides)} slides (minimum 3)")
    if len(slides) > 7:
        issues.append(f"SLIDES: {len(slides)} slides (maximum 7)")

    # Check 3: Korean on slides
    korean_re = re.compile(r'[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]')
    for s in slides:
        for el in s.get("elements", []):
            if el.get("type") == "text_block":
                content = el.get("content", "")
                if korean_re.search(content):
                    issues.append(
                        f"KOREAN: Slide {s.get('slide_num')}: \"{content[:50]}...\""
                    )

    # Check 4: Complete sentences on slides
    for s in slides:
        for el in s.get("elements", []):
            if el.get("type") == "text_block":
                content = el.get("content", "")
                # Check for sentence-ending punctuation with subject-verb pattern
                if content.endswith(".") and len(content.split()) > 6:
                    issues.append(
                        f"SENTENCE: Slide {s.get('slide_num')}: \"{content[:60]}...\""
                    )

    # Check 5: Figure presence
    for s in slides:
        if s.get("slide_type") not in ("title",):
            has_fig = any(e.get("type") == "figure" for e in s.get("elements", []))
            if not has_fig:
                issues.append(
                    f"FIGURE: Slide {s.get('slide_num')} ({s.get('slide_type')}) has no figure"
                )

    # Check 6: Last slide must be "takeaway"
    if slides and slides[-1].get("slide_type") != "takeaway":
        issues.append("STRUCTURE: Last slide is not 'takeaway' type")

    # Check 7: First slide must be "title"
    if slides and slides[0].get("slide_type") != "title":
        issues.append("STRUCTURE: First slide is not 'title' type")

    # Check 8: Color palette (heuristic - check for hex colors in content)
    # This would require analyzing the actual PPTX, skip for plan-level check

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "num_slides": len(slides),
        "total_duration_sec": total_dur,
    }


# ── Main QA Review ──────────────────────────────────────────────

def blind_review(full_text: str, plan: dict, api_key: str,
                 escalation_note: str = "") -> dict:
    """Run one blind QA review cycle."""
    agent_prompt = load_agent_prompt()

    # Render slide content as the reviewer would see it
    slide_content = []
    for s in plan.get("slides", []):
        slide_content.append(f"\n--- SLIDE {s.get('slide_num', '?')}: {s.get('title_text', '')} ---")
        slide_content.append(f"Type: {s.get('slide_type', 'unknown')}")
        slide_content.append("Visual elements on slide:")
        for el in s.get("elements", []):
            if el.get("type") == "figure":
                slide_content.append(f"  [FIGURE: {el.get('figure_id', '?')}] {el.get('caption_label', '')}")
            elif el.get("type") == "text_block":
                slide_content.append(f"  [TEXT ({el.get('style', '?')})] \"{el.get('content', '')}\"")
        slide_content.append(f"\nNarration script:")
        slide_content.append(s.get("narration_script", "(none)"))
        slide_content.append(f"Estimated duration: {s.get('estimated_duration_sec', '?')}s")

    rendered_slides = "\n".join(slide_content)

    # Why-this-paper info
    wtp = plan.get("why_this_paper", {})
    wtp_text = (
        f"Researcher: {wtp.get('researcher', 'unknown')}\n"
        f"Project: {wtp.get('project', 'unknown')}\n"
        f"Connection: {wtp.get('connection', 'unknown')}"
    )

    extra = ""
    if escalation_note:
        extra = f"\n\nESCALATION: Previous review was too lenient. {escalation_note}"

    messages = [
        {"role": "system", "content": agent_prompt + extra},
        {"role": "user", "content": (
            f"## ORIGINAL PAPER (full text)\n\n{full_text[:60000]}\n\n"
            f"---\n\n"
            f"## GENERATED PAPER BLITZ OUTPUT\n\n"
            f"### Slides & Narration:\n{rendered_slides}\n\n"
            f"### Why This Paper:\n{wtp_text}\n\n"
            f"---\n\n"
            f"Evaluate this Paper Blitz output against the original paper. "
            f"Be strict. Follow the rubric exactly."
        )},
    ]

    print("[BLIND QA] Running review...")
    response = call_openrouter(messages, QA_MODEL, api_key, max_tokens=MAX_TOKENS)

    scores = parse_scores(response)
    weighted_avg = compute_weighted_avg(scores)
    verdict = extract_verdict(response)
    revision = extract_revision_instructions(response)
    auto_checks = automated_checks(plan)

    # Override verdict if automated checks fail
    if not auto_checks["passed"]:
        if verdict == "PASS":
            verdict = "REVISE"
            revision += "\n\n### Automated Check Failures:\n"
            for issue in auto_checks["issues"]:
                revision += f"- {issue}\n"

    # Anti-leniency check
    if scores and all(v >= 4 for v in scores.values()):
        # All high scores on first review is suspicious
        print("  ⚠ Anti-leniency: all scores ≥ 4, applying skepticism...")
        escalation = "You gave all dimensions ≥ 4. Re-examine more critically."

    result = {
        "scores": scores,
        "weighted_avg": round(weighted_avg, 2),
        "verdict": verdict,
        "revision_instructions": revision,
        "auto_checks": auto_checks,
        "full_response": response,
        "timestamp": datetime.now().isoformat(),
    }

    print(f"  Scores: {scores}")
    print(f"  Weighted avg: {weighted_avg:.2f}")
    print(f"  Verdict: {verdict}")
    if not auto_checks["passed"]:
        print(f"  Auto-check issues: {len(auto_checks['issues'])}")
        for issue in auto_checks["issues"]:
            print(f"    - {issue}")

    return result


def run_qa_loop(full_text: str, plan: dict, api_key: str,
                max_iterations: int = MAX_ITERATIONS) -> dict:
    """
    Run the full QA loop with iterative feedback.

    Returns:
        {
            "final_verdict": "PASS" | "REVISE" | "FAIL",
            "iterations": [...],
            "total_iterations": N,
            "final_plan": {...}  (if revised)
        }
    """
    iterations = []
    current_plan = plan
    escalation = ""

    for i in range(max_iterations):
        print(f"\n{'=' * 60}")
        print(f"[BLIND QA] Iteration {i + 1}/{max_iterations}")
        print(f"{'=' * 60}")

        result = blind_review(full_text, current_plan, api_key, escalation_note=escalation)
        result["iteration"] = i + 1
        iterations.append(result)

        if result["verdict"] == "PASS":
            print(f"\n✓ PASSED on iteration {i + 1}")
            return {
                "final_verdict": "PASS",
                "iterations": iterations,
                "total_iterations": i + 1,
                "final_plan": current_plan,
                "revision_feedback": "",
            }

        if i < max_iterations - 1:
            print(f"\n→ {result['verdict']} — feeding back for revision...")
            # Build comprehensive feedback from this iteration
            feedback = result["revision_instructions"]
            if result["auto_checks"]["issues"]:
                feedback += "\n\n### AUTOMATED CHECK FAILURES (MUST FIX):\n"
                for issue in result["auto_checks"]["issues"]:
                    feedback += f"- {issue}\n"

            # The revision_feedback will be passed back to the writer
            return {
                "final_verdict": result["verdict"],
                "iterations": iterations,
                "total_iterations": i + 1,
                "final_plan": current_plan,
                "revision_feedback": feedback,
            }

    # Max iterations reached
    final_verdict = iterations[-1]["verdict"] if iterations else "FAIL"
    print(f"\n✗ Max iterations reached. Final verdict: {final_verdict}")
    return {
        "final_verdict": final_verdict,
        "iterations": iterations,
        "total_iterations": max_iterations,
        "final_plan": current_plan,
        "revision_feedback": iterations[-1].get("revision_instructions", "") if iterations else "",
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--max-iter", type=int, default=MAX_ITERATIONS)
    args = parser.parse_args()

    os.chdir(REPO_DIR)
    creds = load_credentials()

    full_text = Path(json.load(open(args.parsed))["full_text_path"]).read_text()
    plan = json.load(open(args.plan))

    result = run_qa_loop(full_text, plan, creds["openrouter_api_key"], args.max_iter)

    # Save QA report
    out_path = Path(args.plan).parent / "qa_report.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nQA report saved: {out_path}")
