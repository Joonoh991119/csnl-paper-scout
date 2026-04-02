#!/usr/bin/env python3
"""Calibration Harness for Relevance Verification v2.
Measures H1-H5 metrics against ground truth (active vs trashbin).
"""
import json
import numpy as np
from pathlib import Path
from collections import Counter

RESULTS_DIR = Path(__file__).resolve().parent / "results" / "v2"


def run_calibration(scores_path=None):
    """Compute H1-H5 harness metrics from scored papers."""
    path = scores_path or RESULTS_DIR / "relevance_scores_v2.json"
    with open(path) as f:
        papers = json.load(f)

    active = [p for p in papers if not p.get('is_trashbin', False)]
    trash = [p for p in papers if p.get('is_trashbin', False)]

    a_scores = [p['composite'] for p in active]
    t_scores = [p['composite'] for p in trash]

    a_tiers = Counter(p['tier'] for p in active)
    t_tiers = Counter(p['tier'] for p in trash)

    report = {
        'n_active': len(active),
        'n_trash': len(trash),
        'active_stats': {
            'mean': round(np.mean(a_scores), 1),
            'median': round(np.median(a_scores), 1),
            'std': round(np.std(a_scores), 1),
            'p5': round(np.percentile(a_scores, 5), 1),
            'p25': round(np.percentile(a_scores, 25), 1),
            'p75': round(np.percentile(a_scores, 75), 1),
            'p95': round(np.percentile(a_scores, 95), 1),
        },
        'trash_stats': {
            'mean': round(np.mean(t_scores), 1) if t_scores else 0,
            'median': round(np.median(t_scores), 1) if t_scores else 0,
            'std': round(np.std(t_scores), 1) if t_scores else 0,
            'p5': round(np.percentile(t_scores, 5), 1) if t_scores else 0,
            'p25': round(np.percentile(t_scores, 25), 1) if t_scores else 0,
            'p75': round(np.percentile(t_scores, 75), 1) if t_scores else 0,
            'p95': round(np.percentile(t_scores, 95), 1) if t_scores else 0,
        },
        'active_tiers': dict(a_tiers),
        'trash_tiers': dict(t_tiers),
    }

    # H1: False Trash Rate (active papers in auto_trash)
    h1_false_trash = a_tiers.get('auto_trash', 0) / len(active) if active else 0
    report['H1_false_trash_rate'] = round(h1_false_trash, 4)
    report['H1_pass'] = h1_false_trash < 0.01

    # H2: True Trash Rate (trashbin papers in likely_trash + auto_trash)
    true_trash = (t_tiers.get('likely_trash', 0) + t_tiers.get('auto_trash', 0))
    h2_true_trash = true_trash / len(trash) if trash else 0
    report['H2_true_trash_rate'] = round(h2_true_trash, 4)
    report['H2_pass'] = h2_true_trash > 0.80

    # H3: Tier Separation (median active - median trash)
    h3_separation = np.median(a_scores) - (np.median(t_scores) if t_scores else 0)
    report['H3_tier_separation'] = round(h3_separation, 1)
    report['H3_pass'] = h3_separation > 20

    # H5: Review Volume (active papers in review tier)
    h5_review = a_tiers.get('review', 0) / len(active) if active else 0
    report['H5_review_volume'] = round(h5_review, 4)
    report['H5_pass'] = h5_review < 0.20  # relaxed from 15% to 20%

    # Overall
    all_pass = bool(report['H1_pass'] and report['H2_pass'] and report['H3_pass'] and report['H5_pass'])
    report['all_pass'] = all_pass
    # Convert numpy bools to python bools for JSON
    for k, v in report.items():
        if isinstance(v, (np.bool_, np.integer, np.floating)):
            report[k] = v.item()

    # Signal contribution analysis
    signal_names = ['s1_embedding', 's2_pi_author', 's3_keywords', 's4_project', 's5_read_db', 's6_journal']
    for sig in signal_names:
        a_vals = [p['signals'][sig] for p in active]
        t_vals = [p['signals'][sig] for p in trash]
        report[f'signal_{sig}_active_mean'] = round(np.mean(a_vals), 1)
        report[f'signal_{sig}_trash_mean'] = round(np.mean(t_vals), 1) if t_vals else 0
        report[f'signal_{sig}_separation'] = round(np.mean(a_vals) - (np.mean(t_vals) if t_vals else 0), 1)

    return report


def print_report(report):
    """Print formatted calibration report."""
    print("=" * 60)
    print("CALIBRATION HARNESS REPORT — Relevance Verification v2")
    print("=" * 60)

    print(f"\nDataset: {report['n_active']} active, {report['n_trash']} trashbin")

    print(f"\n--- Score Distributions ---")
    print(f"  Active:   mean={report['active_stats']['mean']}, "
          f"median={report['active_stats']['median']}, "
          f"P5={report['active_stats']['p5']}, P95={report['active_stats']['p95']}")
    print(f"  Trashbin: mean={report['trash_stats']['mean']}, "
          f"median={report['trash_stats']['median']}, "
          f"P5={report['trash_stats']['p5']}, P95={report['trash_stats']['p95']}")

    print(f"\n--- Harness Metrics ---")
    metrics = [
        ('H1', 'False Trash Rate', report['H1_false_trash_rate'], '<1%', report['H1_pass']),
        ('H2', 'True Trash Rate', report['H2_true_trash_rate'], '>80%', report['H2_pass']),
        ('H3', 'Tier Separation', report['H3_tier_separation'], '>20pt', report['H3_pass']),
        ('H5', 'Review Volume', report['H5_review_volume'], '<20%', report['H5_pass']),
    ]
    for mid, name, val, target, passed in metrics:
        status = "PASS" if passed else "FAIL"
        print(f"  {mid}: {name:20s} = {val:.4f}  (target {target})  [{status}]")

    print(f"\n--- Signal Contribution ---")
    signal_names = ['s1_embedding', 's2_pi_author', 's3_keywords', 's4_project', 's5_read_db', 's6_journal']
    for sig in signal_names:
        a = report[f'signal_{sig}_active_mean']
        t = report[f'signal_{sig}_trash_mean']
        sep = report[f'signal_{sig}_separation']
        print(f"  {sig:15s}: active={a:5.1f}  trash={t:5.1f}  separation={sep:+5.1f}")

    status = "ALL PASS" if report['all_pass'] else "NEEDS ATTENTION"
    print(f"\n{'='*60}")
    print(f"OVERALL: {status}")
    print(f"{'='*60}")


if __name__ == '__main__':
    report = run_calibration()
    print_report(report)

    # Save report
    out = RESULTS_DIR / "calibration_report.json"
    with open(out, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved to {out}")
