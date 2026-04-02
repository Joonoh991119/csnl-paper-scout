"""
Apply Feedback — Automatically update style tokens based on user feedback.

Reads feedback JSON from pptx_feedback.py, aggregates repeated signals,
and updates style.py / pptx_native.py parameters.
"""

import json
import sys
from pathlib import Path
from collections import Counter

REPO_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_DIR))

FEEDBACK_DIR = REPO_DIR / "blitz" / "style_knowledge" / "feedback"
APPLIED_LOG = FEEDBACK_DIR / "applied_updates.jsonl"


def load_all_feedback() -> list[dict]:
    """Load all feedback files."""
    if not FEEDBACK_DIR.exists():
        return []
    feedbacks = []
    for f in sorted(FEEDBACK_DIR.glob("feedback_*.json")):
        with open(f) as fh:
            feedbacks.append(json.load(fh))
    return feedbacks


def aggregate_updates(feedbacks: list[dict]) -> dict:
    """Aggregate token updates across all feedback sessions.

    Returns dict of target → {action, count, avg_value, confidence}.
    """
    aggregated = {}

    for fb in feedbacks:
        for update in fb.get("token_updates", []):
            target = update["target"]
            action = update["action"]
            key = f"{target}::{action}"

            if key not in aggregated:
                aggregated[key] = {
                    "target": target,
                    "action": action,
                    "count": 0,
                    "values": [],
                    "confidence": update.get("confidence", "medium"),
                }

            aggregated[key]["count"] += 1

            if "pct_change" in update:
                aggregated[key]["values"].append(update["pct_change"])
            if "new" in update and update["new"]:
                aggregated[key]["values"].append(update["new"])

    return aggregated


def compute_recommendations(aggregated: dict, min_count: int = 1) -> list[dict]:
    """Convert aggregated feedback to concrete recommendations.

    Only recommends changes that appear consistently (count >= min_count).
    """
    recommendations = []

    for key, data in aggregated.items():
        if data["count"] < min_count:
            continue

        target = data["target"]
        action = data["action"]
        values = data["values"]

        rec = {
            "target": target,
            "action": action,
            "count": data["count"],
            "confidence": data["confidence"],
        }

        # Compute specific recommendation
        if "larger" in action and values:
            numeric_vals = [v for v in values if isinstance(v, (int, float))]
            if numeric_vals:
                avg_change = sum(numeric_vals) / len(numeric_vals)
                rec["recommendation"] = f"Increase by {avg_change:+.0%}"
                rec["avg_pct_change"] = avg_change
        elif "smaller" in action and values:
            numeric_vals = [v for v in values if isinstance(v, (int, float))]
            if numeric_vals:
                avg_change = sum(numeric_vals) / len(numeric_vals)
                rec["recommendation"] = f"Decrease by {avg_change:+.0%}"
                rec["avg_pct_change"] = avg_change
        elif "color" in action or "fill" in action:
            color_vals = [v for v in values if isinstance(v, str) and v.startswith("#")]
            if color_vals:
                # Most frequently chosen color
                most_common = Counter(color_vals).most_common(1)[0][0]
                rec["recommendation"] = f"Change to {most_common}"
                rec["new_color"] = most_common
        elif "removed" in action:
            rec["recommendation"] = "Consider removing this element by default"

        recommendations.append(rec)

    # Sort by count (most consistent feedback first)
    recommendations.sort(key=lambda r: -r["count"])
    return recommendations


def apply_recommendations(recommendations: list[dict], dry_run: bool = True) -> list[str]:
    """Apply recommendations to style tokens.

    Returns list of applied changes.
    """
    applied = []

    for rec in recommendations:
        target = rec["target"]
        action = rec["action"]

        if dry_run:
            applied.append(f"[DRY RUN] {target}: {rec.get('recommendation', action)}")
            continue

        # Apply to style.py
        if target.startswith("ParadigmLayout.BOX_"):
            prop = target.split(".")[-1]  # BOX_WIDTH or BOX_HEIGHT
            pct = rec.get("avg_pct_change", 0)
            if abs(pct) > 0.05:
                _update_paradigm_layout(prop, pct)
                applied.append(f"Updated {target}: {pct:+.0%}")

        elif target.startswith("ParadigmColor."):
            new_color = rec.get("new_color")
            if new_color:
                _update_paradigm_color(target.split(".")[-1], new_color)
                applied.append(f"Updated {target}: → {new_color}")

        elif "removed" in action and "icon" in target:
            applied.append(f"Noted: user prefers no icon strips (requires template change)")

    return applied


def _update_paradigm_layout(prop: str, pct_change: float):
    """Update ParadigmLayout in pptx_native.py defaults."""
    # Read current default values from style.py
    from blitz.skills.style import ParadigmLayout
    current = getattr(ParadigmLayout, prop, None)
    if current is not None:
        new_val = current * (1 + pct_change)
        # Log the update
        log_entry = {
            "target": f"ParadigmLayout.{prop}",
            "old": current,
            "new": new_val,
            "pct_change": pct_change,
        }
        APPLIED_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(APPLIED_LOG, "a") as f:
            f.write(json.dumps(log_entry) + "\n")


def _update_paradigm_color(prop: str, new_color: str):
    """Log color update."""
    log_entry = {
        "target": f"ParadigmColor.{prop}",
        "new": new_color,
    }
    APPLIED_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLIED_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


# ── Main ──────────────────────────────────────────────────────

def run_feedback_cycle(dry_run: bool = True):
    """Full feedback → analysis → recommendation cycle."""
    feedbacks = load_all_feedback()
    if not feedbacks:
        print("No feedback files found.")
        return

    print(f"Loaded {len(feedbacks)} feedback sessions")

    aggregated = aggregate_updates(feedbacks)
    print(f"Aggregated {len(aggregated)} unique signals")

    recommendations = compute_recommendations(aggregated)
    print(f"\n=== RECOMMENDATIONS ({len(recommendations)}) ===")
    for rec in recommendations:
        print(f"  [{rec['confidence']:6s}] {rec['target']}")
        print(f"         {rec.get('recommendation', rec['action'])} (seen {rec['count']}x)")

    print(f"\nApplying ({'DRY RUN' if dry_run else 'LIVE'}):")
    applied = apply_recommendations(recommendations, dry_run=dry_run)
    for a in applied:
        print(f"  {a}")

    return recommendations


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually apply changes (default: dry run)")
    args = parser.parse_args()
    run_feedback_cycle(dry_run=not args.apply)
