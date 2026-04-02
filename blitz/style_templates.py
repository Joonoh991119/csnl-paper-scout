"""
Style Templates — Fixed matplotlib renderers for GAN figure generation.

LLM generates JSON params → these functions render the figure.
No LLM-generated code execution needed.
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path
from PIL import Image

# NPG + Okabe-Ito combined palette
PALETTE = [
    "#E64B35", "#4DBBD5", "#00A087", "#3C5488", "#F39B7F",
    "#8491B4", "#0072B2", "#E69F00", "#009E73", "#D55E00",
]

RCPARAMS = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica Neue', 'Helvetica', 'DejaVu Sans'],
    'font.size': 18,
    'axes.labelsize': 20,
    'axes.titlesize': 24,
    'xtick.labelsize': 18,
    'ytick.labelsize': 18,
    'legend.fontsize': 16,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 1.0,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.major.size': 5,
    'ytick.major.size': 5,
    'lines.linewidth': 2.0,
    'lines.markersize': 6,
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'pdf.fonttype': 42,
}


def _apply_style():
    plt.rcParams.update(RCPARAMS)


def _panel_label(ax, label, x=-0.08, y=1.08):
    """Add bold uppercase panel label (A, B, C...)."""
    ax.text(x, y, label, transform=ax.transAxes,
            fontsize=24, fontweight='bold', va='top', ha='left')


def _draw_epoch_icon(ax, icon_type: str, cx: float, cy: float,
                     image_path: str = None):
    """Draw a simple visual icon inside a paradigm epoch box."""
    if icon_type == "none" or not icon_type:
        return

    s = 0.08  # icon half-size

    if icon_type == "cross":
        # Fixation cross
        ax.plot([cx - s, cx + s], [cy, cy], color='#CC0000', lw=2.5, solid_capstyle='round')
        ax.plot([cx, cx], [cy - s, cy + s], color='#CC0000', lw=2.5, solid_capstyle='round')

    elif icon_type == "dot":
        circle = plt.Circle((cx, cy), s * 0.6, color='#333333', fill=True)
        ax.add_patch(circle)

    elif icon_type == "grating":
        # Simplified Gabor/grating pattern
        for offset in np.linspace(-s, s, 7):
            ax.plot([cx + offset, cx + offset], [cy - s, cy + s],
                    color='#333333', lw=1.2, alpha=0.6)

    elif icon_type == "circle":
        circle = plt.Circle((cx, cy), s, color='none', edgecolor='#333333', lw=1.5)
        ax.add_patch(circle)

    elif icon_type == "arrow_keys":
        # Up/down arrow for response
        ax.annotate('', xy=(cx, cy + s), xytext=(cx, cy - s),
                    arrowprops=dict(arrowstyle='<->', color='#333333', lw=1.5))

    elif icon_type == "question":
        ax.text(cx, cy, '?', ha='center', va='center',
                fontsize=22, fontweight='bold', color='#888888')

    elif icon_type == "screen":
        # Monitor/screen icon
        rect = patches.FancyBboxPatch(
            (cx - s * 1.2, cy - s * 0.8), s * 2.4, s * 1.6,
            boxstyle="round,pad=0.01",
            facecolor='#E8E8E8', edgecolor='#555555', linewidth=1.0,
        )
        ax.add_patch(rect)
        # Stand
        ax.plot([cx, cx], [cy - s * 0.8, cy - s * 1.1], color='#555555', lw=1.5)

    elif icon_type == "checkmark":
        ax.plot([cx - s * 0.5, cx, cx + s * 0.8],
                [cy, cy - s * 0.5, cy + s * 0.6],
                color='#009E73', lw=2.5, solid_capstyle='round')

    elif icon_type == "image" and image_path:
        # Insert actual image
        try:
            img = Image.open(image_path)
            extent = [cx - s * 1.5, cx + s * 1.5, cy - s, cy + s]
            ax.imshow(np.array(img), extent=extent, aspect='auto', zorder=3)
        except Exception:
            pass  # Silently fall back to no icon


def _save(fig, path):
    fig.savefig(path, dpi=200, bbox_inches='tight', facecolor='white', pad_inches=0.2)
    plt.close(fig)


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 1: Multi-panel data plot (grid layout)
# ═══════════════════════════════════════════════════════════════

def render_data_grid(params: dict, output_path: str) -> bool:
    """Render a multi-panel data plot from JSON params.

    params schema:
    {
        "n_rows": int (1-3),
        "n_cols": int (1-4),
        "panels": [
            {
                "label": "A",
                "title": "Panel title",
                "plot_type": "line|scatter|bar|violin|heatmap",
                "x_label": "X axis",
                "y_label": "Y axis",
                "n_conditions": int (1-5),
                "condition_labels": ["cond1", "cond2"],
            },
            ...
        ]
    }
    """
    _apply_style()
    np.random.seed(42)

    n_rows = params.get("n_rows", 1)
    n_cols = params.get("n_cols", 2)
    panels = params.get("panels", [])

    # S4 improvement: use width_ratios to emphasize first column if hero panel exists
    hero = params.get("hero_panel", None)  # index of emphasized panel
    if hero is not None and n_cols >= 2:
        ratios = [1.4 if c == (hero % n_cols) else 1.0 for c in range(n_cols)]
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4.2 * n_rows),
                                 gridspec_kw={'width_ratios': ratios},
                                 constrained_layout=True)
    else:
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4.2 * n_rows),
                                 constrained_layout=True)
    fig.patch.set_facecolor('white')

    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)

    for i, panel in enumerate(panels):
        r, c = divmod(i, n_cols)
        if r >= n_rows or c >= n_cols:
            break
        ax = axes[r, c]

        label = panel.get("label", chr(65 + i))
        title = panel.get("title", "")
        plot_type = panel.get("plot_type", "line")
        x_label = panel.get("x_label", "")
        y_label = panel.get("y_label", "")
        n_conds = panel.get("n_conditions", 2)
        cond_labels = panel.get("condition_labels", [f"Cond {j+1}" for j in range(n_conds)])

        _panel_label(ax, label)
        if title:
            ax.set_title(title, fontsize=20, fontweight='bold', loc='left', pad=8)

        x = np.linspace(0, 10, 50)

        if plot_type == "line":
            for j in range(n_conds):
                y = np.sin(x + j * 0.5) + np.random.normal(0, 0.1, len(x)) + j * 0.3
                sem = np.abs(np.random.normal(0.15, 0.05, len(x)))
                color = PALETTE[j % len(PALETTE)]
                ax.plot(x, y, color=color, lw=2.0,
                        label=cond_labels[j] if j < len(cond_labels) else f"C{j+1}")
                # SEM band (Nature standard for line plots)
                ax.fill_between(x, y - sem, y + sem, color=color, alpha=0.12)
            ax.legend(frameon=False, fontsize=14)

        elif plot_type == "scatter":
            for j in range(n_conds):
                sx = np.random.normal(5 + j, 1.5, 30)
                sy = 0.6 * sx + np.random.normal(j * 0.5, 0.8, 30)
                color = PALETTE[j % len(PALETTE)]
                ax.scatter(sx, sy, color=color, alpha=0.5, s=35,
                           label=cond_labels[j] if j < len(cond_labels) else f"C{j+1}")
                # Regression line (adds visual hierarchy — structure over noise)
                z = np.polyfit(sx, sy, 1)
                x_fit = np.linspace(sx.min(), sx.max(), 50)
                ax.plot(x_fit, np.polyval(z, x_fit), color=color, lw=1.5, alpha=0.7)
            ax.legend(frameon=False, fontsize=14)

        elif plot_type == "bar":
            positions = np.arange(n_conds)
            means = np.random.uniform(2, 8, n_conds)
            sems = np.random.uniform(0.3, 0.8, n_conds)
            colors = [PALETTE[j % len(PALETTE)] for j in range(n_conds)]
            ax.bar(positions, means, yerr=sems, color=colors,
                   capsize=4, alpha=0.85, edgecolor='none')
            # Add individual data points (Nature/Neuron standard)
            for j in range(n_conds):
                jitter = np.random.normal(0, 0.08, 15)
                points = np.random.normal(means[j], sems[j] * 2, 15)
                ax.scatter(positions[j] + jitter, points,
                           color=colors[j], alpha=0.3, s=20, zorder=3)
            ax.set_xticks(positions)
            ax.set_xticklabels(cond_labels[:n_conds])
            # Significance bracket (if applicable)
            if n_conds >= 2:
                y_max = max(means + sems) * 1.1
                ax.plot([0, 0, 1, 1], [y_max, y_max * 1.02, y_max * 1.02, y_max],
                        color='#333333', lw=0.8)
                ax.text(0.5, y_max * 1.03, '***', ha='center', fontsize=14)

        elif plot_type == "violin":
            data = [np.random.normal(5 + j, 1, 100) for j in range(n_conds)]
            parts = ax.violinplot(data, showmeans=True, showmedians=False)
            for j, pc in enumerate(parts['bodies']):
                pc.set_facecolor(PALETTE[j % len(PALETTE)])
                pc.set_alpha(0.7)
            ax.set_xticks(range(1, n_conds + 1))
            ax.set_xticklabels(cond_labels[:n_conds])

        elif plot_type == "heatmap":
            data = np.random.randn(8, 8)
            im = ax.imshow(data, cmap='RdBu_r', aspect='auto')
            fig.colorbar(im, ax=ax, shrink=0.8)

        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)

    # Hide unused axes
    total_panels = len(panels)
    for i in range(total_panels, n_rows * n_cols):
        r, c = divmod(i, n_cols)
        if r < n_rows and c < n_cols:
            axes[r, c].set_visible(False)

    _save(fig, output_path)
    return True


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 2: Paradigm diagram (trial flow)
# ═══════════════════════════════════════════════════════════════

def render_paradigm(params: dict, output_path: str) -> bool:
    """Render a paradigm/trial flow diagram from JSON params.

    params schema:
    {
        "layout": "horizontal|vertical",
        "epochs": [
            {"label": "Fixation", "duration": "500ms", "color": "#F5F5F5",
             "icon": "cross|dot|grating|circle|arrow_keys|question|screen|none",
             "image_path": null | "/path/to/stimulus.png"},
            ...
        ],
        "show_timeline": true,
        "title": "Single Trial Flow",
        "bottom_panel": null | {
            "type": "bar|distribution",
            "title": "Design Structure",
            "items": [{"label": "...", "value": ...}]
        }
    }
    """
    _apply_style()

    epochs = params.get("epochs", [])
    layout = params.get("layout", "horizontal")
    title = params.get("title", "Experimental Paradigm")
    show_timeline = params.get("show_timeline", True)
    bottom = params.get("bottom_panel")

    n_rows = 2 if bottom else 1
    fig, axes = plt.subplots(n_rows, 1, figsize=(14, 3.5 * n_rows),
                             gridspec_kw={'height_ratios': [1, 0.8] if bottom else [1]},
                             constrained_layout=True)
    fig.patch.set_facecolor('white')

    if n_rows == 1:
        ax_flow = axes
    else:
        ax_flow = axes[0]

    # Draw trial flow
    ax_flow.set_xlim(-0.2, len(epochs) * 2 + 0.5)
    ax_flow.set_ylim(-0.3, 1.3)
    ax_flow.axis('off')
    if title:
        ax_flow.set_title(title, fontsize=22, fontweight='bold', loc='left', pad=10)

    box_w = 1.5
    gap = 0.3
    y_center = 0.5
    box_h = 0.6

    for i, ep in enumerate(epochs):
        x = i * (box_w + gap)
        y = y_center - box_h / 2
        color = ep.get("color", "#F5F5F5")

        rect = patches.FancyBboxPatch(
            (x, y), box_w, box_h,
            boxstyle="round,pad=0.04",
            facecolor=color, edgecolor='#333333', linewidth=1.0,
        )
        ax_flow.add_patch(rect)

        # Draw icon inside box (above label)
        icon = ep.get("icon", "none")
        icon_y = y_center + 0.18
        cx = x + box_w / 2
        _draw_epoch_icon(ax_flow, icon, cx, icon_y, ep.get("image_path"))

        # Label below icon
        label_y = y_center - 0.02 if icon != "none" else y_center + 0.08
        ax_flow.text(cx, label_y, ep.get("label", ""),
                     ha='center', va='center', fontsize=16, fontweight='bold', color='#1a1a1a')

        duration = ep.get("duration", "")
        if duration:
            ax_flow.text(cx, y_center - 0.18, duration,
                         ha='center', va='center', fontsize=13, color='#555555')

        if i < len(epochs) - 1:
            ax_flow.annotate('', xy=(x + box_w + gap - 0.05, y_center),
                             xytext=(x + box_w + 0.05, y_center),
                             arrowprops=dict(arrowstyle='->', color='#555555', lw=1.2))

    if show_timeline:
        total_w = len(epochs) * (box_w + gap) - gap
        ax_flow.annotate('', xy=(total_w + 0.3, -0.15),
                         xytext=(-0.1, -0.15),
                         arrowprops=dict(arrowstyle='->', color='#AAAAAA', lw=1.5))
        ax_flow.text(total_w / 2, -0.25, 'Time', ha='center', fontsize=14, color='#888888')

    # Bottom panel
    if bottom and n_rows > 1:
        ax_bot = axes[1]
        bot_type = bottom.get("type", "bar")
        bot_title = bottom.get("title", "")
        items = bottom.get("items", [])

        if bot_title:
            ax_bot.set_title(bot_title, fontsize=20, fontweight='bold', loc='left', pad=8)

        if bot_type == "bar" and items:
            labels = [it.get("label", "") for it in items]
            values = [it.get("value", 1) for it in items]
            colors = [PALETTE[i % len(PALETTE)] for i in range(len(items))]
            ax_bot.barh(range(len(items)), values, color=colors, edgecolor='none', alpha=0.85)
            ax_bot.set_yticks(range(len(items)))
            ax_bot.set_yticklabels(labels)
            ax_bot.invert_yaxis()
            ax_bot.set_xlabel(bottom.get("x_label", ""))

        elif bot_type == "distribution":
            x = np.linspace(0, 10, 200)
            for i, it in enumerate(items[:3]):
                mu = it.get("value", 5)
                y = np.exp(-(x - mu)**2 / 2) / np.sqrt(2 * np.pi)
                ax_bot.fill_between(x, y, alpha=0.2, color=PALETTE[i % len(PALETTE)])
                ax_bot.plot(x, y, color=PALETTE[i % len(PALETTE)], lw=2,
                            label=it.get("label", ""))
            ax_bot.legend(frameon=False)
            ax_bot.set_xlabel(bottom.get("x_label", "Value"))
            ax_bot.set_ylabel("Density")

    _save(fig, output_path)
    return True


# ═══════════════════════════════════════════════════════════════
# TEMPLATE 3: Model/schematic diagram
# ═══════════════════════════════════════════════════════════════

def render_model(params: dict, output_path: str) -> bool:
    """Render a model/schematic diagram from JSON params.

    params schema:
    {
        "title": "Observer Model",
        "stages": [
            {"label": "Input", "sublabel": "x", "color": "#E8F0F8"},
            {"label": "Hidden", "sublabel": "h", "color": "#F0E8F8"},
            {"label": "Output", "sublabel": "y", "color": "#E8F8E8"},
        ],
        "connections": "sequential|all_to_all",
        "side_panel": null | {
            "title": "Predictions",
            "plot_type": "line",
            "n_conditions": 3,
        }
    }
    """
    _apply_style()
    np.random.seed(42)

    stages = params.get("stages", [])
    title = params.get("title", "Model Architecture")
    side = params.get("side_panel")

    n_cols = 2 if side else 1
    fig, axes = plt.subplots(1, n_cols, figsize=(14, 5),
                             gridspec_kw={'width_ratios': [1.2, 1] if side else [1]},
                             constrained_layout=True)
    fig.patch.set_facecolor('white')

    ax_model = axes[0] if n_cols > 1 else axes
    ax_model.axis('off')
    ax_model.set_title(title, fontsize=22, fontweight='bold', loc='left', pad=10)
    _panel_label(ax_model, 'A')

    # Draw stages as boxes with arrows
    n = len(stages)
    box_w = 2.0
    gap = 0.8
    y_center = 0.5
    box_h = 0.55
    total_w = n * (box_w + gap) - gap
    ax_model.set_xlim(-0.5, total_w + 0.5)
    ax_model.set_ylim(-0.2, 1.2)

    for i, stage in enumerate(stages):
        x = i * (box_w + gap)
        y = y_center - box_h / 2
        color = stage.get("color", "#F0F0F0")

        # Main box with subtle shadow effect (offset darker box behind)
        rect = patches.FancyBboxPatch(
            (x, y), box_w, box_h,
            boxstyle="round,pad=0.06",
            facecolor=color, edgecolor='#333333', linewidth=1.2,
        )
        ax_model.add_patch(rect)

        # Stage label
        ax_model.text(x + box_w / 2, y_center + 0.08,
                      stage.get("label", ""), ha='center', va='center',
                      fontsize=18, fontweight='bold', color='#1a1a1a')

        # Sublabel (equation or description)
        sublabel = stage.get("sublabel", "")
        if sublabel:
            ax_model.text(x + box_w / 2, y_center - 0.10,
                          sublabel, ha='center', va='center',
                          fontsize=14, fontstyle='italic', color='#555555')

        # Arrow to next stage
        if i < n - 1:
            mid_x = x + box_w + gap / 2
            ax_model.annotate('', xy=(x + box_w + gap - 0.15, y_center),
                              xytext=(x + box_w + 0.15, y_center),
                              arrowprops=dict(arrowstyle='->', color='#333333', lw=1.5,
                                              connectionstyle='arc3,rad=0'))
            # Optional: small label between stages
            between_label = stage.get("arrow_label", "")
            if between_label:
                ax_model.text(mid_x, y_center + 0.20, between_label,
                              ha='center', fontsize=12, color='#888888')

    # Add Gaussian/distribution annotations above first and last box if applicable
    for i, stage in enumerate(stages):
        if stage.get("show_distribution"):
            x = i * (box_w + gap)
            dist_x = np.linspace(x + 0.2, x + box_w - 0.2, 50)
            dist_y = np.exp(-((dist_x - x - box_w/2)**2) / (0.15)) * 0.25 + y_center + box_h/2 + 0.05
            ax_model.plot(dist_x, dist_y, color=PALETTE[i % len(PALETTE)], lw=1.5)
            ax_model.fill_between(dist_x, y_center + box_h/2 + 0.05, dist_y,
                                  color=PALETTE[i % len(PALETTE)], alpha=0.15)

    # Side panel
    if side and n_cols > 1:
        ax_side = axes[1]
        _panel_label(ax_side, 'B')
        st = side.get("title", "")
        if st:
            ax_side.set_title(st, fontsize=20, fontweight='bold', loc='left', pad=8)

        nc = side.get("n_conditions", 3)
        x = np.linspace(0, 10, 100)
        for j in range(nc):
            y = np.sin(x * (j + 1) * 0.3) + j * 0.5 + np.random.normal(0, 0.05, len(x))
            ax_side.plot(x, y, color=PALETTE[j % len(PALETTE)], lw=2,
                         label=f"Cond {j+1}")
        ax_side.legend(frameon=False)
        ax_side.set_xlabel(side.get("x_label", "Input"))
        ax_side.set_ylabel(side.get("y_label", "Output"))

    _save(fig, output_path)
    return True


# ═══════════════════════════════════════════════════════════════
# Dispatcher — route params to correct template
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# TEMPLATE 4: Enhanced schematic/model with multiple representations
# ═══════════════════════════════════════════════════════════════

def render_schematic(params: dict, output_path: str) -> bool:
    """Render a comprehensive schematic combining model + data visualization.

    This is the enhanced version for schematics that consistently score higher.
    Instead of just boxes-and-arrows, it pairs a model schematic (left) with
    quantitative panels (right), similar to Nature/Neuron review figures.

    params schema:
    {
        "template": "schematic",
        "title": "Computational Framework",
        "left_panel": {
            "title": "Model Architecture",
            "stages": [{"label": "...", "sublabel": "...", "color": "#..."}],
        },
        "right_panels": [
            {"title": "...", "plot_type": "line|bar|heatmap", "n_conditions": 2},
            {"title": "...", "plot_type": "scatter", "n_conditions": 3},
        ]
    }
    """
    _apply_style()
    np.random.seed(42)

    left = params.get("left_panel", {})
    right_panels = params.get("right_panels", [])
    main_title = params.get("title", "")

    n_right = max(len(right_panels), 1)
    fig = plt.figure(figsize=(14, 4 * max(n_right, 2) / 2), constrained_layout=True)
    fig.patch.set_facecolor('white')

    if main_title:
        fig.suptitle(main_title, fontsize=22, fontweight='bold', x=0.02, ha='left')

    # Create grid: left = model schematic, right = data panels
    gs = fig.add_gridspec(max(n_right, 1), 2, width_ratios=[1.3, 1])

    # Left panel: model schematic (spans all rows)
    ax_left = fig.add_subplot(gs[:, 0])
    ax_left.axis('off')
    _panel_label(ax_left, 'A')

    stages = left.get("stages", [
        {"label": "Input", "sublabel": "x", "color": "#E8F0F8"},
        {"label": "Process", "sublabel": "f(x)", "color": "#F0E8F8"},
        {"label": "Output", "sublabel": "y", "color": "#E8F8E8"},
    ])
    left_title = left.get("title", "")
    if left_title:
        ax_left.set_title(left_title, fontsize=20, fontweight='bold', loc='left', pad=8)

    # Draw stages vertically (top to bottom — better for schematics)
    n = len(stages)
    box_w = 0.6
    box_h = 0.12
    gap_y = 0.08
    start_y = 0.85
    cx = 0.5

    ax_left.set_xlim(0, 1)
    ax_left.set_ylim(0, 1)

    for i, stage in enumerate(stages):
        y = start_y - i * (box_h + gap_y)
        color = stage.get("color", "#F0F0F0")

        rect = patches.FancyBboxPatch(
            (cx - box_w / 2, y - box_h / 2), box_w, box_h,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor='#333333', linewidth=1.2,
            transform=ax_left.transAxes,
        )
        ax_left.add_patch(rect)

        ax_left.text(cx, y + 0.01, stage.get("label", ""),
                     ha='center', va='center', fontsize=16, fontweight='bold',
                     color='#1a1a1a', transform=ax_left.transAxes)

        sublabel = stage.get("sublabel", "")
        if sublabel:
            ax_left.text(cx, y - 0.035, sublabel,
                         ha='center', va='center', fontsize=12, fontstyle='italic',
                         color='#555555', transform=ax_left.transAxes)

        # Downward arrow
        if i < n - 1:
            next_y = start_y - (i + 1) * (box_h + gap_y)
            ax_left.annotate('',
                             xy=(cx, next_y + box_h / 2 + 0.01),
                             xytext=(cx, y - box_h / 2 - 0.01),
                             xycoords='axes fraction', textcoords='axes fraction',
                             arrowprops=dict(arrowstyle='->', color='#333333', lw=1.5))

    # Feedback arrow (if specified)
    if left.get("feedback", False) and n >= 2:
        y_top = start_y
        y_bot = start_y - (n - 1) * (box_h + gap_y)
        ax_left.annotate('',
                         xy=(cx + box_w / 2 + 0.08, y_top - box_h / 2),
                         xytext=(cx + box_w / 2 + 0.08, y_bot + box_h / 2),
                         xycoords='axes fraction', textcoords='axes fraction',
                         arrowprops=dict(arrowstyle='->', color='#8491B4', lw=1.5,
                                         connectionstyle='arc3,rad=-0.3'))
        ax_left.text(cx + box_w / 2 + 0.13, (y_top + y_bot) / 2,
                     left.get("feedback_label", "feedback"),
                     ha='left', va='center', fontsize=11, color='#8491B4',
                     fontstyle='italic', rotation=90, transform=ax_left.transAxes)

    # Right panels: quantitative visualizations
    panel_labels = 'BCDEFGH'
    for j, panel in enumerate(right_panels[:max(n_right, 1)]):
        ax = fig.add_subplot(gs[j, 1])
        _panel_label(ax, panel_labels[j] if j < len(panel_labels) else '')

        pt = panel.get("plot_type", "line")
        nc = panel.get("n_conditions", 3)
        ptitle = panel.get("title", "")
        if ptitle:
            ax.set_title(ptitle, fontsize=18, fontweight='bold', loc='left', pad=6)

        x = np.linspace(0, 10, 60)

        if pt == "line":
            for k in range(nc):
                y = np.sin(x * (k + 1) * 0.4) * (1 + k * 0.2) + np.random.normal(0, 0.08, len(x))
                ax.plot(x, y, color=PALETTE[k % len(PALETTE)], lw=2, label=f"Cond {k+1}")
                # Add SEM band
                ax.fill_between(x, y - 0.3, y + 0.3, color=PALETTE[k % len(PALETTE)], alpha=0.1)
            ax.legend(frameon=False, fontsize=14)
        elif pt == "bar":
            means = np.random.uniform(3, 8, nc)
            sems = np.random.uniform(0.3, 0.8, nc)
            colors = [PALETTE[k % len(PALETTE)] for k in range(nc)]
            ax.bar(range(nc), means, yerr=sems, color=colors, capsize=4, alpha=0.85)
            for k in range(nc):
                jitter = np.random.normal(0, 0.08, 12)
                pts = np.random.normal(means[k], sems[k] * 1.5, 12)
                ax.scatter(k + jitter, pts, color=colors[k], alpha=0.3, s=18, zorder=3)
            ax.set_xticks(range(nc))
            ax.set_xticklabels([f"C{k+1}" for k in range(nc)])
        elif pt == "scatter":
            for k in range(nc):
                sx = np.random.normal(5 + k, 1.5, 25)
                sy = np.random.normal(5 + k * 0.3, 1, 25)
                ax.scatter(sx, sy, color=PALETTE[k % len(PALETTE)], alpha=0.5, s=35)
        elif pt == "heatmap":
            data = np.random.randn(6, 8)
            ax.imshow(data, cmap='RdBu_r', aspect='auto')

        ax.set_xlabel(panel.get("x_label", ""))
        ax.set_ylabel(panel.get("y_label", ""))

    _save(fig, output_path)
    return True


TEMPLATES = {
    "data_grid": render_data_grid,
    "paradigm": render_paradigm,
    "model": render_model,
    "schematic": render_schematic,
}


def render_from_params(params: dict, output_path: str) -> bool:
    """Route to the correct template renderer.

    params must include "template": "data_grid|paradigm|model"
    """
    template_name = params.get("template", "data_grid")
    renderer = TEMPLATES.get(template_name)
    if not renderer:
        print(f"Unknown template: {template_name}")
        return False
    try:
        return renderer(params, output_path)
    except Exception as e:
        print(f"Render error: {e}")
        return False


# ── CLI test ──────────────────────────────────────────────────

if __name__ == "__main__":
    out_dir = Path("blitz/style_knowledge/template_test")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Test data grid
    ok1 = render_data_grid({
        "n_rows": 1, "n_cols": 3,
        "panels": [
            {"label": "A", "title": "Accuracy", "plot_type": "bar", "n_conditions": 3,
             "condition_labels": ["Low", "Med", "High"], "y_label": "% Correct"},
            {"label": "B", "title": "RT", "plot_type": "violin", "n_conditions": 3,
             "condition_labels": ["Low", "Med", "High"], "y_label": "RT (ms)"},
            {"label": "C", "title": "Psychometric", "plot_type": "line", "n_conditions": 2,
             "condition_labels": ["Pre", "Post"], "x_label": "Stimulus", "y_label": "P(correct)"},
        ]
    }, str(out_dir / "test_data_grid.png"))
    print(f"Data grid: {'OK' if ok1 else 'FAIL'}")

    # Test paradigm
    ok2 = render_paradigm({
        "title": "Single Trial Flow",
        "epochs": [
            {"label": "Fixation", "duration": "500ms", "color": "#F0F0F0"},
            {"label": "Stimulus", "duration": "200ms", "color": "#E0E8F0"},
            {"label": "Delay", "duration": "1-2s", "color": "#E8E8E8"},
            {"label": "Response", "duration": "until", "color": "#D8E8D8"},
            {"label": "Feedback", "duration": "500ms", "color": "#E8D8E8"},
        ],
        "show_timeline": True,
        "bottom_panel": {
            "type": "distribution",
            "title": "Stimulus Distribution",
            "items": [
                {"label": "Easy", "value": 3},
                {"label": "Medium", "value": 5},
                {"label": "Hard", "value": 7},
            ],
            "x_label": "Difficulty",
        }
    }, str(out_dir / "test_paradigm.png"))
    print(f"Paradigm: {'OK' if ok2 else 'FAIL'}")

    # Test model
    ok3 = render_model({
        "title": "Bayesian Observer Model",
        "stages": [
            {"label": "Measurement", "sublabel": "p(tm|ts)", "color": "#E8F0F8"},
            {"label": "Estimation", "sublabel": "f(tm)", "color": "#F0E8F8"},
            {"label": "Production", "sublabel": "p(tp|te)", "color": "#E8F8E8"},
        ],
        "side_panel": {
            "title": "Model Predictions",
            "n_conditions": 3,
            "x_label": "Sample interval",
            "y_label": "Production time",
        }
    }, str(out_dir / "test_model.png"))
    print(f"Model: {'OK' if ok3 else 'FAIL'}")
