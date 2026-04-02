"""
Paradigm Diagram Skill — generates horizontal (L→R) experimental procedure diagrams.

Uses style.py for all font sizes and colors. Designed for SLIDE placement,
not journal print — fonts are intentionally large.

Convention: time flows left-to-right, following psychophysics literature.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_DIR))
from blitz.skills.style import FigureFont, MATPLOTLIB_STYLE, Color


def apply_style():
    plt.rcParams.update(MATPLOTLIB_STYLE)


def draw_trial_flow(ax, epochs, y_center=0.5, box_height=0.55):
    """Horizontal L→R trial flow."""
    n = len(epochs)
    gap = 0.12
    box_w = 1.6
    total = n * box_w + (n - 1) * gap
    start_x = 0.3

    ax.set_xlim(0, total + 0.8)
    ax.set_ylim(-0.05, 1.05)
    ax.axis('off')

    for i, ep in enumerate(epochs):
        x = start_x + i * (box_w + gap)
        y = y_center - box_height / 2

        rect = patches.FancyBboxPatch(
            (x, y), box_w, box_height,
            boxstyle="round,pad=0.04",
            facecolor=ep.get('color', '#E8F0F8'),
            edgecolor='#333333', linewidth=1.2,
        )
        ax.add_patch(rect)

        ax.text(x + box_w / 2, y_center + 0.1, ep['label'],
                ha='center', va='center',
                fontsize=FigureFont.LABEL, fontweight='bold', color='#1a1a1a')

        if ep.get('duration'):
            ax.text(x + box_w / 2, y_center - 0.1, ep['duration'],
                    ha='center', va='center',
                    fontsize=FigureFont.ANNOTATION, color='#333333')

        if i < n - 1:
            ax.annotate('', xy=(x + box_w + gap, y_center),
                        xytext=(x + box_w + 0.02, y_center),
                        arrowprops=dict(arrowstyle='->', color='#555555', lw=1.5))

    # Time arrow at bottom
    ax.annotate('', xy=(total + 0.5, -0.02), xytext=(0.3, -0.02),
                arrowprops=dict(arrowstyle='->', color='#AAAAAA', lw=2))
    ax.text(total / 2 + 0.3, -0.06, 'Time',
            ha='center', fontsize=FigureFont.ANNOTATION, color='#555555')


def draw_bimodal(ax, mu1, mu2, sigma, x_label, y_label):
    """Bimodal distribution plot."""
    x = np.linspace(mu1 - 4 * sigma, mu2 + 4 * sigma, 500)
    y = 0.5 * np.exp(-(x - mu1)**2 / (2 * sigma**2)) + \
        0.5 * np.exp(-(x - mu2)**2 / (2 * sigma**2))
    y /= y.max()

    ax.fill_between(x, y, alpha=0.12, color=Color.OI_BLUE)
    ax.plot(x, y, color=Color.OI_BLUE, linewidth=2.5)
    ax.axvline(mu1, color=Color.OI_BLUE, linestyle='--', alpha=0.4, linewidth=1)
    ax.axvline(mu2, color=Color.OI_BLUE, linestyle='--', alpha=0.4, linewidth=1)

    ax.text(mu1, 1.08, f'{mu1} cm', ha='center',
            fontsize=FigureFont.LABEL, color=Color.OI_BLUE, fontweight='bold')
    ax.text(mu2, 1.08, f'{mu2} cm', ha='center',
            fontsize=FigureFont.LABEL, color=Color.OI_BLUE, fontweight='bold')

    ax.set_xlabel(x_label, fontsize=FigureFont.LABEL)
    ax.set_ylabel(y_label, fontsize=FigureFont.LABEL)
    ax.tick_params(labelsize=FigureFont.TICK)
    ax.set_ylim(0, 1.25)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.2)
    ax.spines['bottom'].set_linewidth(1.2)


def draw_design_table(ax, rows):
    """Compact design structure — single line per row, no detail sub-text."""
    ax.axis('off')
    n = len(rows)
    row_h = 0.9 / n

    for i, row in enumerate(rows):
        y = 0.95 - (i + 0.5) * row_h

        rect = patches.FancyBboxPatch(
            (0.02, y - row_h * 0.38), 0.96, row_h * 0.76,
            boxstyle="round,pad=0.02",
            facecolor=row.get('color', '#F5F5F5'),
            edgecolor=row.get('edge', '#999999'),
            linewidth=1.2,
        )
        ax.add_patch(rect)

        # Single line: label + detail combined
        label = row['label']
        detail = row.get('detail', '')
        display = f"{label}  ({detail})" if detail else label

        ax.text(0.5, y, display,
                ha='center', va='center',
                fontsize=FigureFont.TICK, fontweight='bold',
                color=row.get('text_color', '#1a1a1a'))

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)


def generate_zahno2026_paradigm(out_path: str):
    """Generate paradigm diagram for Zahno et al. 2026."""
    apply_style()

    fig = plt.figure(figsize=(14, 5.5))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.2], width_ratios=[1.3, 1],
                          hspace=0.3, wspace=0.25)

    # Top: Trial flow
    ax_trial = fig.add_subplot(gs[0, :])
    ax_trial.set_title('Single Trial Flow', fontsize=FigureFont.TITLE_LARGE,
                       fontweight='bold', pad=12, loc='left')

    epochs = [
        {'label': 'Fixation\n+ Cue', 'duration': '', 'color': '#F0F0F0'},
        {'label': 'Delay', 'duration': '1-2 s', 'color': '#E8E8E8'},
        {'label': 'Avatar\nServe', 'duration': 'uninformative', 'color': '#E0E8F0'},
        {'label': 'Ball\nApproach', 'duration': 'speed varies', 'color': '#D0E0F0'},
        {'label': 'Swing\n+ Contact', 'duration': '400 ms', 'color': '#B8D4F0'},
        {'label': 'Feedback', 'duration': '0-100 pts', 'color': '#A0C8F0'},
    ]
    draw_trial_flow(ax_trial, epochs)

    # Bottom-left: Distribution
    ax_dist = fig.add_subplot(gs[1, 0])
    ax_dist.set_title('Serve Location Distribution',
                      fontsize=FigureFont.TITLE, fontweight='bold', pad=10, loc='left')
    draw_bimodal(ax_dist, 50, 90, 5, 'Ball Position (cm)', 'Probability')

    # Bottom-right: Design structure
    ax_design = fig.add_subplot(gs[1, 1])
    ax_design.set_title('Design',
                        fontsize=FigureFont.TITLE, fontweight='bold', pad=10, loc='left')

    rows = [
        {'label': 'Day 1 — 480 trials', 'detail': 'Initial (no prior effect)',
         'color': '#FFF0F0', 'edge': '#DDAAAA'},
        {'label': 'Day 2 — 480 trials', 'detail': 'Post-consolidation',
         'color': '#F0FFF0', 'edge': '#AADDAA'},
        {'label': 'Day 3 — 480 trials', 'detail': 'Post-consolidation',
         'color': '#F0FFF0', 'edge': '#AADDAA'},
        {'label': 'Slow 108 km/h', 'detail': 'Low uncertainty',
         'color': '#FFF', 'edge': Color.SLOW, 'text_color': Color.SLOW},
        {'label': 'Moderate 180 km/h', 'detail': 'Med uncertainty',
         'color': '#FFF', 'edge': Color.MODERATE, 'text_color': Color.MODERATE},
        {'label': 'Fast 252 km/h', 'detail': 'High uncertainty',
         'color': '#FFF', 'edge': Color.FAST, 'text_color': Color.FAST},
    ]
    draw_design_table(ax_design, rows)

    plt.savefig(out_path, dpi=200, bbox_inches='tight', facecolor='white', pad_inches=0.2)
    plt.close()
    print(f"Paradigm diagram saved: {out_path}")


if __name__ == "__main__":
    generate_zahno2026_paradigm(
        "blitz/output/zahno2026_test/tmp/figures/paradigm_v3.png"
    )
