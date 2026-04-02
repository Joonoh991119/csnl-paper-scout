"""
Paper Blitz Style System — Nature/Neuron-grade academic design tokens.

All design decisions reference this single file. No magic numbers elsewhere.

Sources:
  - Automated analysis: 74 papers, 82 figures from CSNL Zotero library
    (Nature, Science, Cell, Neuron, Nat Neurosci, eLife, PNAS, etc.)
    via style_learner.py Find→Learn→Review→Record loop
  - Manual analysis: 6 key papers (Jazayeri & Shadlen 2010, Steel et al. 2024,
    Sheahan et al. 2021, Flesch et al. 2022, Gu et al. 2025, Fischer & Whitney 2014)
  - Nature Research Figure Guide (2026)
  - Cell Press Author Guidelines
  - NPG palette (ggsci), Okabe-Ito palette
  - WCAG 2.1 contrast requirements

Statistical findings (from 316 figures across 196 papers):
  - Layout: grid 51%, vertical 15%, horizontal 15%, hybrid 10%, nested 5%
  - Spines: two_spines 44%, no_spines 33%, four_spines 24%
  - Panel labels: uppercase_bold 58%, none 26%, lowercase_bold 15%
  - Whitespace: mean 44% ± 12% (generous margins are the norm)
  - Aesthetic: minimal 54%, rich 45%, cluttered <1%
  - Figure types: data_plot 45%, hybrid 17%, paradigm 13%, schematic 12%

See STYLE-GUIDE.md for full rationale and reference figures.
"""

from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt


# ═══════════════════════════════════════════════════════════════
# COLOR PALETTE
# ═══════════════════════════════════════════════════════════════

class Color:
    """Slide-level colors for text and backgrounds."""

    # ── Text hierarchy ──────────────────────────────────────
    BLACK = RGBColor(0x1A, 0x1A, 0x1A)       # primary: titles, body
    DARK = RGBColor(0x33, 0x33, 0x33)         # secondary: subtitles, captions
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)        # background (always)

    # ── Accent — single emphasis color ──────────────────────
    ACCENT = RGBColor(0x3C, 0x54, 0x88)       # NPG dark blue — restrained authority

    # ── Figure annotation only (≤10pt, axis labels) ─────────
    FIG_LABEL = RGBColor(0x55, 0x55, 0x55)    # darkened from old #777777

    # FORBIDDEN: anything with min(R,G,B) > 0x55 for body text.
    # Old #777777 is explicitly banned — fails WCAG 4.5:1 contrast.

    # ── Legacy aliases (backward compat with paradigm_diagram.py) ──
    OI_ORANGE = "#E69F00"
    OI_SKY_BLUE = "#56B4E9"
    OI_GREEN = "#009E73"
    OI_YELLOW = "#F0E442"
    OI_BLUE = "#0072B2"
    OI_VERMILLION = "#D55E00"
    OI_PURPLE = "#CC79A7"
    OI_BLACK = "#000000"
    SLOW = "#009E73"
    MODERATE = "#0072B2"
    FAST = "#D55E00"


class NPG:
    """Nature Publishing Group palette — primary data colors.

    Used across Nature, Nature Neuroscience, Nature Reviews.
    Source: ggsci R package, verified against published figures.
    """
    RED = "#E64B35"           # vermillion red — condition A / salient
    CYAN = "#4DBBD5"          # cyan — condition B / cool
    TEAL = "#00A087"          # teal — condition C / correct / positive
    DARK_BLUE = "#3C5488"     # dark blue — primary accent
    SALMON = "#F39B7F"        # salmon — secondary / error bars / light fill
    SLATE = "#8491B4"         # slate blue — tertiary / reference
    MINT = "#91D1C2"          # mint — light secondary
    PURE_RED = "#DC0000"      # pure red — strong negative
    BROWN = "#7E6148"         # brown — earth tone
    TAUPE = "#B09C85"         # taupe — neutral

    # Ordered for default cycling
    CYCLE = [RED, CYAN, TEAL, DARK_BLUE, SALMON, SLATE]


class OkabeIto:
    """Okabe-Ito colorblind-safe palette — fallback for strict accessibility.

    Use when colorblind safety is the top priority (e.g., main result figure).
    """
    ORANGE = "#E69F00"
    SKY_BLUE = "#56B4E9"
    GREEN = "#009E73"
    YELLOW = "#F0E442"
    BLUE = "#0072B2"
    VERMILLION = "#D55E00"
    PURPLE = "#CC79A7"
    BLACK = "#000000"

    CYCLE = [BLUE, ORANGE, GREEN, VERMILLION, SKY_BLUE, PURPLE, YELLOW]


class LearnedStats:
    """Statistical findings from automated analysis of 316 figures across 196 papers.

    Journals: Nature, Science, Cell, Neuron, Nat Neurosci, eLife, PNAS,
    Nat Commun, JNeurosci, Trends Cogn Sci, etc.

    These are DATA-DRIVEN defaults derived from the style_learner.py pipeline.
    Use to validate that generated figures match real journal aesthetics.
    """
    # Layout distribution
    LAYOUT_GRID_PCT = 0.51
    LAYOUT_VERTICAL_PCT = 0.15
    LAYOUT_HORIZONTAL_PCT = 0.15
    LAYOUT_HYBRID_PCT = 0.10
    LAYOUT_NESTED_PCT = 0.05

    # Spine style
    TWO_SPINES_PCT = 0.44       # top+right removed (most common)
    NO_SPINES_PCT = 0.33        # all spines removed
    FOUR_SPINES_PCT = 0.24      # all spines visible (older style)

    # Panel labels
    UPPERCASE_BOLD_PCT = 0.58   # A, B, C — dominant across journals
    NONE_PCT = 0.26             # no panel labels (single-panel figures)
    LOWERCASE_BOLD_PCT = 0.15   # a, b, c — Nature house style

    # Whitespace
    WHITESPACE_MEAN = 0.44
    WHITESPACE_STD = 0.12
    WHITESPACE_MIN = 0.20
    WHITESPACE_MAX = 0.65

    # Aesthetic
    MINIMAL_PCT = 0.54          # clean, high data-ink ratio
    RICH_PCT = 0.45             # detailed with illustrations/icons
    CLUTTERED_PCT = 0.01        # effectively zero in top journals

    # Figure types
    DATA_PLOT_PCT = 0.45
    HYBRID_PCT = 0.17           # mixed paradigm+data
    PARADIGM_PCT = 0.13
    SCHEMATIC_PCT = 0.12
    MODEL_DIAGRAM_PCT = 0.10

    # Most frequent color clusters (from 89 clusters across 216 figures)
    TOP_COLORS = [
        "#808080",    # gray — reference lines, secondary elements
        "#bab0ac",    # warm gray — neutral fills
        "#f0f0f0",    # light gray — panel backgrounds
        "#a0d9f0",    # sky blue — highlights, fills
        "#4c78a8",    # steel blue — primary data (Vega/D3 default)
        "#e45756",    # red — secondary data, emphasis
        "#ee8c7c",    # salmon — tertiary
        "#f58518",    # orange — condition markers
        "#54a24b",    # green — positive/correct
    ]


class ParadigmColor:
    """Colors for experimental paradigm diagrams.

    Derived from patterns in Jazayeri & Shadlen 2010, Sheahan et al. 2021,
    Gu et al. 2025 paradigm figures + automated analysis of 7 paradigm diagrams.
    """
    # Screen/box elements
    SCREEN_BG = "#F5F5F5"         # light gray, simulates monitor
    BOX_BORDER = "#333333"        # thin dark border
    ACTIVE_TINT_ALPHA = 0.12      # palette color at 12% opacity for active epoch

    # Standard psychophysics elements
    FIXATION = "#CC0000"          # red fixation cross
    TIMELINE_ARROW = "#333333"    # thin timeline arrow
    DURATION_TEXT = "#555555"     # duration labels (small text)

    # Feedback
    CORRECT = "#009E73"           # green (Okabe-Ito)
    INCORRECT = "#D55E00"         # vermillion (Okabe-Ito)

    # Condition colors (paper-specific; override per paper)
    CONDITION_A = "#E64B35"       # NPG red
    CONDITION_B = "#4DBBD5"       # NPG cyan
    CONDITION_C = "#00A087"       # NPG teal


# ═══════════════════════════════════════════════════════════════
# TYPOGRAPHY — Slide text
# ═══════════════════════════════════════════════════════════════

class SlideFont:
    FAMILY = "Helvetica Neue"
    FALLBACK = "Arial"

    # Title
    TITLE = 28               # pt — default
    TITLE_MAX = 36           # pt — single-word emphasis titles

    # Body text
    BODY = 16                # pt — default body
    BODY_MIN = 14            # pt — hard minimum, validator enforced
    BODY_LARGE = 18          # pt — for emphasis

    # Captions (below figures)
    CAPTION = 13             # pt — slightly below body for hierarchy

    # Figure annotations (ONLY for axis/caption labels under figures)
    FIG_ANNOTATION = 10      # pt — the only exception to 14pt minimum

    # Line spacing
    BODY_LINE_SPACING = 1.35

    # Text density limits (from cognitive load research)
    MAX_BULLETS_PER_SLIDE = 3
    MAX_WORDS_PER_BULLET = 15


# ═══════════════════════════════════════════════════════════════
# TYPOGRAPHY — Generated figures (matplotlib)
# ═══════════════════════════════════════════════════════════════

class FigureFont:
    """Font sizes for matplotlib-generated diagrams placed on slides.

    Scale model:
      figsize=(14, h) at 200dpi, placed at ~10" on slide.
      Scale factor ≈ 10/14 = 0.71x
      So 20pt in matplotlib ≈ 14pt on slide (body minimum).

    For figsize=(18, h) placed at ~10": scale ≈ 0.56x
      28pt in matplotlib ≈ 16pt on slide.
    """
    # Standard figure (figsize ~14" wide, placed at ~10" on slide)
    TITLE = 24           # → ~17pt effective
    LABEL = 20           # → ~14pt effective (meets body minimum)
    TICK = 18            # → ~13pt effective
    ANNOTATION = 18      # → ~13pt effective
    LEGEND = 18          # → ~13pt effective
    PANEL_LABEL = 24     # → ~17pt effective, bold

    # Large figure (figsize ~18" wide, placed at ~10" on slide)
    TITLE_LARGE = 28     # → ~16pt effective
    LABEL_LARGE = 22     # → ~12pt effective
    TICK_LARGE = 20      # → ~11pt effective


# ═══════════════════════════════════════════════════════════════
# PARADIGM DIAGRAM — Layout tokens
# ═══════════════════════════════════════════════════════════════

class ParadigmLayout:
    """Design tokens for experimental paradigm diagrams.

    From analysis of Jazayeri & Shadlen 2010 (Fig 1a), Sheahan et al. 2021
    (Fig 1C), Gu et al. 2025 (Fig 1E), Flesch et al. 2022 (Fig 1B).
    """
    # Box dimensions (in figure-coordinate units, figsize=14")
    # Updated via user feedback: +17% width, +10% height (2 sessions, 13 signals)
    BOX_WIDTH = 1.87             # epoch box width (was 1.6)
    BOX_HEIGHT = 0.61            # epoch box height (was 0.55)
    BOX_GAP = 0.12               # gap between boxes
    BOX_CORNER_RADIUS = 0.04     # rounded corner pad

    # Stroke weights (points)
    BOX_STROKE_PT = 1.0          # epoch box border
    ARROW_STROKE_PT = 1.2        # temporal flow arrows
    TIMELINE_STROKE_PT = 1.5     # bottom timeline arrow
    THIN_LINE_PT = 0.75          # secondary lines

    # Arrow styles
    ARROW_STYLE = '->'           # simple arrowhead
    ARROW_COLOR = '#555555'      # subtle, not competing with content
    TIMELINE_COLOR = '#AAAAAA'   # very subtle baseline

    # Screen mockup (for showing actual stimuli)
    SCREEN_BORDER_PT = 1.5       # monitor-like border
    SCREEN_CORNER_RADIUS = 0.02  # slight rounding
    SCREEN_BG = '#F5F5F5'        # simulated display

    # Spacing
    LABEL_OFFSET_Y = 0.10        # label vertical offset from box center
    DURATION_OFFSET_Y = -0.10    # duration label below box center

    # Layout patterns
    # 'horizontal': L→R temporal flow (default)
    # 'vertical': top→bottom (for space-constrained layouts)
    # 'nested': outer block structure + inner trial flow
    # 'hybrid': 2-row layout for complex paradigms
    ALLOWED_LAYOUTS = ['horizontal', 'vertical', 'nested', 'hybrid']


# ═══════════════════════════════════════════════════════════════
# FIGURE STYLE — matplotlib rcParams
# ═══════════════════════════════════════════════════════════════

MATPLOTLIB_STYLE = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica Neue', 'Helvetica', 'DejaVu Sans'],
    'font.size': FigureFont.LABEL,

    'axes.labelsize': FigureFont.LABEL,
    'axes.titlesize': FigureFont.TITLE,
    'xtick.labelsize': FigureFont.TICK,
    'ytick.labelsize': FigureFont.TICK,
    'legend.fontsize': FigureFont.LEGEND,

    # Nature-style: remove top+right spines
    'axes.spines.top': False,
    'axes.spines.right': False,

    'axes.linewidth': 1.0,
    'grid.linewidth': 0.5,
    'lines.linewidth': 2.0,
    'lines.markersize': 6,

    # Ticks outward (universal in analyzed papers)
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.major.size': 5,
    'xtick.major.width': 1.0,
    'ytick.major.size': 5,
    'ytick.major.width': 1.0,

    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.15,
    'pdf.fonttype': 42,          # TrueType — required by Nature
}


# ═══════════════════════════════════════════════════════════════
# SLIDE LAYOUT — 16:9 dimensions and margins
# ═══════════════════════════════════════════════════════════════

class Layout:
    SLIDE_WIDTH = Inches(13.333)
    SLIDE_HEIGHT = Inches(7.5)

    # Margins
    MARGIN_LEFT = Inches(0.5)
    MARGIN_RIGHT = Inches(0.5)
    MARGIN_TOP = Inches(0.2)

    # Title position
    TITLE_LEFT = Inches(0.5)
    TITLE_TOP = Inches(0.2)
    TITLE_WIDTH = Inches(10)
    TITLE_HEIGHT = Inches(0.7)

    # Content area (below title)
    CONTENT_TOP = Inches(1.0)
    CONTENT_HEIGHT = Inches(6.3)

    # Usable width
    CONTENT_WIDTH = Inches(12.333)   # slide width - margins

    # Figure placement targets (from style guide)
    # Primary figure: 60-70% of content width
    PRIMARY_FIG_WIDTH_RATIO = 0.65
    # Secondary panel: remaining space
    SECONDARY_FIG_WIDTH_RATIO = 0.30


# ═══════════════════════════════════════════════════════════════
# VALIDATION THRESHOLDS
# ═══════════════════════════════════════════════════════════════

class Threshold:
    # Font sizes
    MIN_BODY_FONT = 14         # pt — hard floor
    MIN_TITLE_FONT = 24        # pt
    MIN_FIG_ANNOTATION = 10    # pt (only for figure labels)

    # Color darkness (RGB channels)
    # Body text must have min(R,G,B) ≤ this value
    MAX_GRAY_BODY = 0x55       # = #555555 max (old #777777 is banned)

    # Aspect ratio
    ASPECT_RATIO_TOL = 0.08    # 8% tolerance

    # Overlap
    OVERLAP_TOL_INCHES = 0.05  # inches

    # Figure-internal text
    MIN_FIGURE_TEXT_EFFECTIVE = 7   # pt — Nature print minimum
    MIN_GENERATED_FIG_FONT = 13    # pt in matplotlib source

    # Contrast ratio (WCAG AA)
    MIN_CONTRAST_RATIO = 4.5

    # Text density (soft warnings)
    MAX_BULLETS_PER_SLIDE = 3
    MAX_ACCENT_COLORS_PER_SLIDE = 3
    MIN_FIGURE_AREA_RATIO = 0.50   # figure should be ≥50% of content area


# ═══════════════════════════════════════════════════════════════
# CONVENIENCE — Palette selector
# ═══════════════════════════════════════════════════════════════

def get_condition_colors(n: int, palette: str = "npg") -> list[str]:
    """Return n distinct condition colors from the specified palette.

    Args:
        n: Number of conditions (1-7)
        palette: "npg" (default, Nature-style) or "oi" (Okabe-Ito, strict colorblind)

    Returns:
        List of hex color strings
    """
    if palette == "npg":
        return NPG.CYCLE[:n]
    elif palette == "oi":
        return OkabeIto.CYCLE[:n]
    else:
        raise ValueError(f"Unknown palette: {palette}. Use 'npg' or 'oi'.")
