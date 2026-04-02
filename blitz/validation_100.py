#!/usr/bin/env python3
"""
100-Figure Blind Validation — tests generalization of style knowledge.

Generates 100 figures via templates (using random params within learned ranges),
blind-reviews each, reports aggregate pass rate.

This is the final quality gate — proves the style system works at scale.
"""

import json
import os
import random
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

from blitz.style_templates import render_data_grid, render_paradigm, render_schematic, PALETTE
from blitz.style_gan_test import review_figure, _load_credentials, SCORE_WEIGHTS

VALIDATION_DIR = REPO_DIR / "blitz" / "style_knowledge" / "validation_100"


# ── Random Param Generators ───────────────────────────────────

def random_data_grid():
    n_rows = random.choice([1, 1, 2, 2, 2])
    n_cols = random.choice([2, 2, 3, 3, 4])
    plot_types = ["line", "scatter", "bar", "violin", "heatmap"]
    n_panels = n_rows * n_cols

    panels = []
    for i in range(n_panels):
        nc = random.randint(2, 4)
        pt = random.choice(plot_types)
        labels = [random.choice([
            "Low", "Med", "High", "Pre", "Post", "Control", "Test",
            "Cond A", "Cond B", "Cond C", "Group 1", "Group 2",
            "Baseline", "Treatment", "Early", "Late",
        ]) for _ in range(nc)]
        panels.append({
            "label": chr(65 + i),
            "title": random.choice([
                "Accuracy", "Response Time", "Neural Activity",
                "BOLD Signal", "Decoding Accuracy", "Error Rate",
                "Psychometric Function", "Tuning Curve", "Correlation",
                "Population Activity", "Firing Rate", "Power Spectrum",
            ]),
            "plot_type": pt,
            "n_conditions": nc,
            "condition_labels": labels[:nc],
            "x_label": random.choice(["Time (s)", "Stimulus", "Trial", "Frequency (Hz)", ""]),
            "y_label": random.choice(["Response", "Accuracy (%)", "Signal (a.u.)", "Rate (Hz)", ""]),
        })

    return {"template": "data_grid", "n_rows": n_rows, "n_cols": n_cols, "panels": panels}


def random_paradigm():
    n_epochs = random.randint(3, 6)
    icons = ["cross", "grating", "dot", "arrow_keys", "checkmark", "question", "screen", "circle"]
    pastel_colors = ["#F0F0F0", "#E0E8F0", "#E8E8E8", "#D8E8D8", "#E8D8E8",
                     "#F0E8E0", "#E0F0E8", "#F8F0F0"]

    epochs = []
    for i in range(n_epochs):
        epochs.append({
            "label": random.choice([
                "Fixation", "Stimulus", "Delay", "Response", "Feedback",
                "Cue", "Target", "Mask", "ISI", "ITI", "Probe",
                "Encoding", "Retention", "Retrieval", "Decision",
            ]),
            "duration": random.choice(["200ms", "500ms", "1s", "1-2s", "2s", "until", "300ms", "100ms"]),
            "color": random.choice(pastel_colors),
            "icon": random.choice(icons),
        })

    bottom = None
    if random.random() > 0.3:
        bottom = {
            "type": random.choice(["distribution", "bar"]),
            "title": random.choice(["Stimulus Distribution", "Design Structure",
                                     "Condition Breakdown", "Difficulty Levels"]),
            "items": [
                {"label": random.choice(["Easy", "Hard", "Short", "Long", "Low", "High"]),
                 "value": random.uniform(2, 8)}
                for _ in range(random.randint(2, 4))
            ],
            "x_label": random.choice(["Value", "Level", "Condition"]),
        }

    return {
        "template": "paradigm",
        "title": random.choice([
            "Single Trial Flow", "Experimental Paradigm", "Task Design",
            "Trial Sequence", "Behavioral Paradigm",
        ]),
        "epochs": epochs,
        "show_timeline": True,
        "bottom_panel": bottom,
    }


def random_schematic():
    n_stages = random.randint(3, 5)
    stage_colors = ["#E8F0F8", "#F0F0E8", "#F0E8F0", "#E8F8E8", "#F8E8E8", "#E8E8F8"]

    stages = []
    stage_labels = random.sample([
        "Input", "Encoding", "Representation", "Integration", "Decision",
        "Measurement", "Likelihood", "Prior", "Posterior", "Estimate",
        "Sensory", "Hidden", "Output", "Memory", "Attention",
    ], min(n_stages, 10))

    for i in range(n_stages):
        stages.append({
            "label": stage_labels[i] if i < len(stage_labels) else f"Stage {i+1}",
            "sublabel": random.choice(["f(x)", "p(s|x)", "h_t", "y = Wx", ""]),
            "color": random.choice(stage_colors),
        })

    right_panels = []
    for j in range(random.randint(1, 2)):
        right_panels.append({
            "title": random.choice(["Model Fit", "Predictions", "Parameter Recovery",
                                     "Comparison", "Latent Space"]),
            "plot_type": random.choice(["line", "bar", "scatter"]),
            "n_conditions": random.randint(2, 4),
            "x_label": random.choice(["Input", "Trial", "Condition"]),
            "y_label": random.choice(["Output", "Error", "Response"]),
        })

    return {
        "template": "schematic",
        "title": random.choice([
            "Computational Model", "Bayesian Framework", "Network Architecture",
            "Observer Model", "Processing Pipeline",
        ]),
        "left_panel": {
            "title": random.choice(["Model Architecture", "Processing Stages",
                                     "Computational Graph"]),
            "stages": stages,
            "feedback": random.random() > 0.5,
            "feedback_label": random.choice(["learning", "feedback", "update"]),
        },
        "right_panels": right_panels,
    }


# ── Main Validation Loop ──────────────────────────────────────

def main(n_figures: int = 100):
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    api_key = _load_credentials()

    # Distribution matching learned stats: 50% data, 30% paradigm, 20% schematic
    generators = (
        [("data_plot", random_data_grid)] * 50 +
        [("paradigm", random_paradigm)] * 30 +
        [("schematic", random_schematic)] * 20
    )
    random.shuffle(generators)
    generators = generators[:n_figures]

    results = []
    passes = 0
    type_results = {}

    print(f"Running {n_figures}-figure validation...")
    print(f"Distribution: {sum(1 for t,_ in generators if t=='data_plot')} data, "
          f"{sum(1 for t,_ in generators if t=='paradigm')} paradigm, "
          f"{sum(1 for t,_ in generators if t=='schematic')} schematic")

    for i, (fig_type, gen_fn) in enumerate(generators):
        params = gen_fn()
        output_path = str(VALIDATION_DIR / f"val_{i:03d}.png")

        try:
            # Render
            from blitz.style_templates import render_from_params
            success = render_from_params(params, output_path)
            if not success:
                results.append({"index": i, "type": fig_type, "error": "render_failed"})
                continue

            # Review
            review = review_figure(output_path, api_key)
            passed = review["verdict"] == "PASS"
            if passed:
                passes += 1

            type_results.setdefault(fig_type, []).append({
                "verdict": review["verdict"],
                "avg": review["weighted_avg"],
                "scores": review["scores"],
            })

            results.append({
                "index": i,
                "type": fig_type,
                "verdict": review["verdict"],
                "avg": review["weighted_avg"],
                "scores": review["scores"],
            })

            status = "PASS" if passed else "REVISE"
            if (i + 1) % 10 == 0:
                current_rate = passes / (i + 1)
                print(f"  [{i+1}/{n_figures}] Running rate: {passes}/{i+1} = {current_rate:.0%}")

        except Exception as e:
            results.append({"index": i, "type": fig_type, "error": str(e)})
            print(f"  [{i+1}] ERROR: {e}")
            time.sleep(1)
            continue

        time.sleep(0.3)  # Rate limiting

    # Final report
    total_reviewed = sum(1 for r in results if "verdict" in r)
    print(f"\n{'='*60}")
    print(f"VALIDATION COMPLETE: {passes}/{total_reviewed} = {passes/max(total_reviewed,1)*100:.0f}%")
    print(f"{'='*60}")

    for ft in sorted(type_results):
        items = type_results[ft]
        ft_passes = sum(1 for r in items if r["verdict"] == "PASS")
        ft_avg = sum(r["avg"] for r in items) / len(items)
        s4_avg = sum(r["scores"].get("S4", 0) for r in items) / len(items)
        print(f"  {ft}: {ft_passes}/{len(items)} PASS ({ft_passes/len(items)*100:.0f}%), "
              f"mean={ft_avg:.2f}, S4={s4_avg:.1f}")

    # Score distribution
    all_avgs = [r["avg"] for r in results if "avg" in r]
    if all_avgs:
        import statistics
        print(f"\n  Score distribution: mean={statistics.mean(all_avgs):.2f}, "
              f"std={statistics.stdev(all_avgs):.2f}, "
              f"min={min(all_avgs):.2f}, max={max(all_avgs):.2f}")

    # Save report
    report = {
        "timestamp": datetime.now().isoformat(),
        "n_figures": n_figures,
        "n_reviewed": total_reviewed,
        "passes": passes,
        "pass_rate": passes / max(total_reviewed, 1),
        "by_type": {ft: {
            "n": len(items),
            "passes": sum(1 for r in items if r["verdict"] == "PASS"),
            "mean_avg": sum(r["avg"] for r in items) / len(items),
        } for ft, items in type_results.items()},
        "results": results,
    }
    with open(VALIDATION_DIR / "report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nReport: {VALIDATION_DIR / 'report.json'}")
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=100)
    args = parser.parse_args()
    main(args.n)
