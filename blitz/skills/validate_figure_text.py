"""
Figure-Internal Text Validator — detects text inside figures that's too small.

Two modes:
  1. Generated figures (matplotlib): checks rcParams / source font sizes
  2. Cropped figures (from PDF): estimates effective text size on slide
     based on source DPI, image dimensions, and placement size.

The key insight: a figure at 7pt text in a Nature paper (89mm wide)
is fine for print, but when placed on a slide at 50% width,
effective size is ~13pt — still readable.
At 30% width → ~8pt → marginal.
At 20% width → ~5pt → unreadable.
"""

import os
from PIL import Image
from pptx.util import Emu


# ═══════════════════════════════════════════════════════════════
# Method 1: Estimate figure text readability from placement size
# ═══════════════════════════════════════════════════════════════

def estimate_figure_text_readability(
    image_path: str,
    slide_placement_width_inches: float,
    source_min_font_pt: float = 7.0,  # Nature minimum
    source_figure_width_inches: float = None,  # original figure width
):
    """
    Estimate whether text inside a figure will be readable on a slide.

    For cropped paper figures:
      - source_min_font_pt = 7 (Nature minimum)
      - source_figure_width_inches ≈ 7.2 (double-column) or 3.5 (single)

    For matplotlib-generated figures:
      - source_min_font_pt = actual smallest font used
      - source_figure_width_inches = figsize[0]

    Returns:
      {
        "readable": bool,
        "effective_pt": float,  # estimated effective font size on slide
        "scale_factor": float,
        "recommendation": str,
      }
    """
    if not os.path.exists(image_path):
        return {"readable": False, "effective_pt": 0, "scale_factor": 0,
                "recommendation": f"File not found: {image_path}"}

    im = Image.open(image_path)
    img_w_px, img_h_px = im.size

    # Determine source figure width
    if source_figure_width_inches is None:
        # For cropped paper figures: DPI metadata is unreliable (PyMuPDF
        # crops at 4x matrix but PIL reports 96dpi). Use the actual paper
        # page width as reference. Most journals are A4 (~8.27") or
        # letter (~8.5"). Double-column text width is ~7.2".
        # Default to 7.0" (typical double-column figure width).
        source_figure_width_inches = 7.0

    # Scale factor: how much the figure is enlarged/shrunk on slide
    scale = slide_placement_width_inches / source_figure_width_inches

    # Effective font size on slide
    effective_pt = source_min_font_pt * scale

    # Readability judgment
    if effective_pt >= 10:
        readable = True
        rec = "Good readability"
    elif effective_pt >= 7:
        readable = True
        rec = "Acceptable (Nature print minimum)"
    elif effective_pt >= 5:
        readable = False
        rec = f"Marginal ({effective_pt:.1f}pt effective) — enlarge figure or use fewer panels"
    else:
        readable = False
        rec = f"Unreadable ({effective_pt:.1f}pt effective) — must enlarge significantly"

    return {
        "readable": readable,
        "effective_pt": round(effective_pt, 1),
        "scale_factor": round(scale, 2),
        "source_width_in": round(source_figure_width_inches, 1),
        "placement_width_in": slide_placement_width_inches,
        "recommendation": rec,
    }


# ═══════════════════════════════════════════════════════════════
# Method 2: Validate matplotlib-generated figure font sizes
# ═══════════════════════════════════════════════════════════════

def validate_matplotlib_params(rcparams: dict, min_font: float = 13.0):
    """
    Check that all font sizes in matplotlib rcParams are above minimum.

    For figures placed on slides, we need larger fonts than journal print.
    Minimum 13pt in matplotlib → ~7pt effective at 50% slide width.
    """
    violations = []
    font_keys = [
        'font.size', 'axes.labelsize', 'axes.titlesize',
        'xtick.labelsize', 'ytick.labelsize', 'legend.fontsize',
    ]
    for key in font_keys:
        val = rcparams.get(key)
        if val is not None and isinstance(val, (int, float)) and val < min_font:
            violations.append(
                f"FIGURE FONT TOO SMALL: {key}={val}pt, minimum {min_font}pt for slide placement"
            )
    return violations


# ═══════════════════════════════════════════════════════════════
# Method 3: Check all figures in a slide
# ═══════════════════════════════════════════════════════════════

def validate_slide_figures(slide, figure_metadata: list = None):
    """
    Validate all image shapes in a slide for text readability.

    figure_metadata: list of dicts with keys:
      - figure_id: str
      - source_min_font_pt: float (default 7)
      - source_width_inches: float (default: auto-detect)
      - is_generated: bool (if True, use stricter minimum)

    If no metadata provided, uses conservative defaults.
    """
    violations = []

    for shape in slide.shapes:
        if shape.shape_type != 13:  # Not a picture
            continue

        placement_w_inches = shape.width / 914400  # EMU to inches

        # Find matching metadata
        meta = None
        if figure_metadata:
            # Try to match by position (rough)
            for m in figure_metadata:
                meta = m
                break  # Use first available if can't match

        if meta and meta.get("is_generated"):
            # Generated figure: we should have used proper font sizes
            source_min = meta.get("source_min_font_pt", 13)
            source_w = meta.get("source_width_inches", 18)
        else:
            # Cropped paper figure: assume Nature 7pt minimum
            source_min = meta.get("source_min_font_pt", 7) if meta else 7
            source_w = meta.get("source_width_inches", None)

        result = estimate_figure_text_readability(
            image_path="<embedded>",  # Can't check embedded images directly
            slide_placement_width_inches=placement_w_inches,
            source_min_font_pt=source_min,
            source_figure_width_inches=source_w or placement_w_inches,
        )

        if not result["readable"]:
            violations.append(
                f"FIGURE TEXT TOO SMALL: placed at {placement_w_inches:.1f}\" wide, "
                f"effective ~{result['effective_pt']}pt — {result['recommendation']}"
            )

    return violations


# ═══════════════════════════════════════════════════════════════
# Convenience: check a figure file before placing it
# ═══════════════════════════════════════════════════════════════

def precheck_figure(
    image_path: str,
    target_width_inches: float,
    is_generated: bool = False,
    source_min_font_pt: float = None,
):
    """
    Pre-check whether a figure will be readable at the target placement size.
    Call this BEFORE adding the figure to the slide.

    Returns (readable: bool, report: dict)
    """
    if source_min_font_pt is None:
        source_min_font_pt = 13 if is_generated else 7

    result = estimate_figure_text_readability(
        image_path=image_path,
        slide_placement_width_inches=target_width_inches,
        source_min_font_pt=source_min_font_pt,
    )

    return result["readable"], result


if __name__ == "__main__":
    # Test with paradigm diagram
    fig_dir = "blitz/output/zahno2026_test/tmp/figures"

    print("=== Paradigm diagram (generated, 18\" wide, min font 8pt) ===")
    ok, report = precheck_figure(
        f"{fig_dir}/paradigm_v2.png",
        target_width_inches=9.0,
        is_generated=True,
        source_min_font_pt=8,  # smallest font in current diagram
    )
    print(f"  Readable: {ok}")
    print(f"  Effective: {report['effective_pt']}pt")
    print(f"  {report['recommendation']}")

    print("\n=== Fig 3 from paper (cropped, ~7.2\" source, 7pt min) ===")
    ok, report = precheck_figure(
        f"{fig_dir}/fig3_results.png",
        target_width_inches=9.0,
        is_generated=False,
        source_min_font_pt=7,
    )
    print(f"  Readable: {ok}")
    print(f"  Effective: {report['effective_pt']}pt")
    print(f"  {report['recommendation']}")

    print("\n=== Fig 1 from paper (placed at 6.5\") ===")
    ok, report = precheck_figure(
        f"{fig_dir}/fig1_full.png",
        target_width_inches=6.5,
        is_generated=False,
        source_min_font_pt=7,
    )
    print(f"  Readable: {ok}")
    print(f"  Effective: {report['effective_pt']}pt")
    print(f"  {report['recommendation']}")
