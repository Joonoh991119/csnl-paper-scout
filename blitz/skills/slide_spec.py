"""
Slide Spec — Coordinate-based visualization specifications.

Instead of vague text instructions ("draw paradigm here"),
this module defines explicit spatial relationships:
  - Every element has absolute coordinates (inches from top-left)
  - Parent-child relationships are explicit (arrow connects box_0 to box_1)
  - Sizes are computed from content, not guessed

This eliminates text-to-visualization uncertainty.
"""

from dataclasses import dataclass, field
from pptx.util import Inches, Pt


# ── Coordinate System ──────────────────────────────────────────
# All values in inches. Origin = top-left of slide.
# Slide: 13.333" x 7.5" (16:9)

SLIDE_W = 13.333
SLIDE_H = 7.5
MARGIN = 0.5

# Zones (pre-computed, no guessing)
ZONES = {
    "title": {"x": MARGIN, "y": 0.2, "w": 12.0, "h": 0.85},
    "title_rule": {"x": MARGIN, "y": 1.05, "w": 12.0, "h": 0.02},

    # Figure-left / text-right layout (academic-pptx-skill §5)
    "fig_left": {"x": MARGIN, "y": 1.2, "w": 7.5, "h": 5.5},
    "text_right": {"x": 8.5, "y": 1.2, "w": 4.3, "h": 5.5},
    "text_right_header": {"x": 8.5, "y": 1.2, "w": 4.3, "h": 0.4},
    "text_right_body": {"x": 8.5, "y": 1.7, "w": 4.3, "h": 4.5},

    # Full-width exhibit
    "fig_full": {"x": MARGIN, "y": 1.2, "w": 12.3, "h": 5.8},

    # Paradigm zone (top) + detail zone (bottom)
    "paradigm_flow": {"x": MARGIN + 0.2, "y": 1.2, "w": 12.0, "h": 2.8},
    "paradigm_detail": {"x": MARGIN, "y": 4.3, "w": 12.3, "h": 2.8},

    # Model: schematic left + charts right
    "model_left": {"x": MARGIN, "y": 1.2, "w": 4.5, "h": 5.5},
    "model_right": {"x": 5.5, "y": 1.2, "w": 7.3, "h": 5.5},

    # Conclusions: full-width text
    "conclusions_body": {"x": MARGIN, "y": 0.9, "w": 12.0, "h": 4.0},

    # Citation
    "citation": {"x": MARGIN, "y": 7.0, "w": 12.0, "h": 0.3},
}


@dataclass
class ElementSpec:
    """Explicit specification for one visual element."""
    id: str                    # unique name (e.g., "paradigm_epoch_0")
    type: str                  # "rect", "textbox", "arrow", "figure", "chart", "icon_strip"
    x: float                   # left (inches)
    y: float                   # top (inches)
    w: float                   # width (inches)
    h: float                   # height (inches)
    properties: dict = field(default_factory=dict)
    # properties examples:
    #   rect: {"fill": "#F0F0F0", "border": "#333333", "radius": 0.04}
    #   textbox: {"text": "...", "font_size": 20, "bold": True, "color": "#1F4E79"}
    #   arrow: {"end_x": 5.0, "end_y": 2.0, "color": "#555555"}
    #   figure: {"path": "/abs/path.png"}
    #   chart: {"chart_type": "bar", "data": {...}}
    #   icon_strip: {"color": "#CC0000", "symbol": "+"}
    children: list = field(default_factory=list)  # child element IDs
    parent: str = None         # parent element ID


@dataclass
class SlideSpec:
    """Complete specification for one slide. No ambiguity."""
    slide_type: str            # "title", "results", "methods", etc.
    background: str = "FFFFFF" # hex
    elements: list = field(default_factory=list)  # list of ElementSpec


# ── Spec Builders ──────────────────────────────────────────────

def spec_paradigm_flow(epochs: list[dict], zone: dict = None) -> list[ElementSpec]:
    """Generate precise coordinates for paradigm trial flow.

    Each epoch gets exact (x, y, w, h) computed from:
      - Number of epochs
      - Available zone width
      - Fixed height and gap ratios

    Returns list of ElementSpecs with absolute coordinates.
    """
    z = zone or ZONES["paradigm_flow"]
    n = len(epochs)
    if n == 0:
        return []

    # Compute box dimensions from available space
    total_gap = z["w"] * 0.15  # 15% of width for gaps
    total_box = z["w"] - total_gap
    box_w = total_box / n
    gap = total_gap / max(n - 1, 1)
    box_h = min(z["h"] * 0.6, 1.2)  # max 1.2" tall
    box_y = z["y"] + (z["h"] - box_h) / 2  # vertically centered

    # Icon strip height
    strip_h = 0.15

    specs = []
    for i, ep in enumerate(epochs):
        x = z["x"] + i * (box_w + gap)

        # Main box
        specs.append(ElementSpec(
            id=f"paradigm_epoch_{i}",
            type="rect",
            x=x, y=box_y, w=box_w, h=box_h,
            properties={
                "fill": ep.get("color", "#F0F0F0"),
                "border": "#333333",
                "border_width": 1.0,
                "radius": 0.04,
            },
        ))

        # Icon strip (top of box)
        icon = ep.get("icon", "none")
        icon_colors = {
            "cross": "#CC0000", "grating": "#3C5488", "dot": "#333333",
            "arrow_keys": "#00A087", "checkmark": "#009E73",
            "question": "#888888", "screen": "#4DBBD5", "circle": "#555555",
        }
        if icon in icon_colors:
            specs.append(ElementSpec(
                id=f"paradigm_icon_{i}",
                type="icon_strip",
                x=x, y=box_y, w=box_w, h=strip_h,
                properties={
                    "color": icon_colors[icon],
                    "symbol": {"cross": "+", "grating": "≡", "dot": "●",
                               "arrow_keys": "↕", "checkmark": "✓",
                               "question": "?", "screen": "▢", "circle": "○"}.get(icon, ""),
                },
                parent=f"paradigm_epoch_{i}",
            ))

        # Label (centered in box)
        label_y = box_y + strip_h + 0.1 if icon in icon_colors else box_y + 0.15
        specs.append(ElementSpec(
            id=f"paradigm_label_{i}",
            type="textbox",
            x=x + 0.05, y=label_y, w=box_w - 0.1, h=0.5,
            properties={
                "text": ep.get("label", ""),
                "font_size": 16, "bold": True,
                "color": "#1A1A1A", "align": "center",
            },
            parent=f"paradigm_epoch_{i}",
        ))

        # Duration (bottom of box)
        duration = ep.get("duration", "")
        if duration:
            specs.append(ElementSpec(
                id=f"paradigm_duration_{i}",
                type="textbox",
                x=x + 0.05, y=box_y + box_h - 0.35, w=box_w - 0.1, h=0.3,
                properties={
                    "text": duration,
                    "font_size": 12, "bold": False,
                    "color": "#555555", "align": "center",
                },
                parent=f"paradigm_epoch_{i}",
            ))

        # Arrow to next box
        if i < n - 1:
            arrow_start_x = x + box_w
            arrow_end_x = x + box_w + gap
            arrow_y = box_y + box_h / 2
            specs.append(ElementSpec(
                id=f"paradigm_arrow_{i}",
                type="arrow",
                x=arrow_start_x, y=arrow_y, w=gap, h=0,
                properties={
                    "end_x": arrow_end_x,
                    "end_y": arrow_y,
                    "color": "#555555",
                    "width": 1.2,
                },
            ))

    # Timeline
    tl_y = box_y + box_h + 0.3
    tl_start_x = z["x"]
    tl_end_x = z["x"] + z["w"]
    specs.append(ElementSpec(
        id="paradigm_timeline",
        type="arrow",
        x=tl_start_x, y=tl_y, w=z["w"], h=0,
        properties={
            "end_x": tl_end_x, "end_y": tl_y,
            "color": "#AAAAAA", "width": 1.5,
        },
    ))
    specs.append(ElementSpec(
        id="paradigm_timeline_label",
        type="textbox",
        x=(tl_start_x + tl_end_x) / 2 - 0.3, y=tl_y + 0.05, w=0.6, h=0.25,
        properties={
            "text": "Time →", "font_size": 11,
            "color": "#888888", "align": "center",
        },
    ))

    return specs


def spec_model_stages(stages: list[dict], zone: dict = None) -> list[ElementSpec]:
    """Generate precise coordinates for model schematic (vertical layout)."""
    z = zone or ZONES["model_left"]
    n = len(stages)
    if n == 0:
        return []

    box_w = z["w"] * 0.7
    box_h = min(0.7, z["h"] / (n * 1.6))
    gap_y = box_h * 0.6
    x_center = z["x"] + (z["w"] - box_w) / 2
    start_y = z["y"] + 0.3

    specs = []
    for i, stage in enumerate(stages):
        y = start_y + i * (box_h + gap_y)

        specs.append(ElementSpec(
            id=f"model_stage_{i}",
            type="rect",
            x=x_center, y=y, w=box_w, h=box_h,
            properties={
                "fill": stage.get("color", "#F0F0F0"),
                "border": "#333333",
                "border_width": 1.2,
                "radius": 0.06,
            },
        ))

        specs.append(ElementSpec(
            id=f"model_label_{i}",
            type="textbox",
            x=x_center + 0.1, y=y + 0.05, w=box_w - 0.2, h=0.35,
            properties={
                "text": stage.get("label", ""),
                "font_size": 16, "bold": True,
                "color": "#1A1A1A", "align": "center",
            },
            parent=f"model_stage_{i}",
        ))

        sublabel = stage.get("sublabel", "")
        if sublabel:
            specs.append(ElementSpec(
                id=f"model_sublabel_{i}",
                type="textbox",
                x=x_center + 0.1, y=y + 0.38, w=box_w - 0.2, h=0.25,
                properties={
                    "text": sublabel,
                    "font_size": 12, "bold": False,
                    "color": "#555555", "align": "center",
                },
                parent=f"model_stage_{i}",
            ))

        if i < n - 1:
            arrow_x = x_center + box_w / 2
            specs.append(ElementSpec(
                id=f"model_arrow_{i}",
                type="arrow",
                x=arrow_x, y=y + box_h, w=0, h=gap_y,
                properties={
                    "end_x": arrow_x,
                    "end_y": y + box_h + gap_y,
                    "color": "#333333",
                    "width": 1.5,
                },
            ))

    return specs


def spec_to_summary(specs: list[ElementSpec]) -> str:
    """Convert specs to human-readable summary for debugging."""
    lines = []
    for s in specs:
        lines.append(f"  {s.id:30s} ({s.type:10s}) at ({s.x:.1f}, {s.y:.1f}) "
                     f"size ({s.w:.1f} x {s.h:.1f})")
        if s.parent:
            lines[-1] += f"  parent={s.parent}"
    return "\n".join(lines)


# ── Spec Validation ────────────────────────────────────────────

def validate_specs(specs: list[ElementSpec]) -> list[str]:
    """Check specs for spatial issues before rendering."""
    issues = []

    for s in specs:
        # Out of bounds
        if s.x < 0 or s.y < 0:
            issues.append(f"{s.id}: negative coordinates ({s.x}, {s.y})")
        if s.x + s.w > SLIDE_W + 0.1:
            issues.append(f"{s.id}: exceeds slide width ({s.x + s.w:.1f} > {SLIDE_W})")
        if s.y + s.h > SLIDE_H + 0.1:
            issues.append(f"{s.id}: exceeds slide height ({s.y + s.h:.1f} > {SLIDE_H})")

        # Zero-size elements
        if s.type in ("rect", "textbox", "figure") and (s.w <= 0 or s.h <= 0):
            issues.append(f"{s.id}: zero or negative size ({s.w}, {s.h})")

    # Overlap detection
    rects = [(s.id, s.x, s.y, s.x + s.w, s.y + s.h)
             for s in specs if s.type in ("rect", "figure", "chart")]
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a_id, ax1, ay1, ax2, ay2 = rects[i]
            b_id, bx1, by1, bx2, by2 = rects[j]
            # Check overlap (with 0.05" tolerance)
            if ax1 < bx2 - 0.05 and ax2 > bx1 + 0.05 and ay1 < by2 - 0.05 and ay2 > by1 + 0.05:
                # Check if parent-child (allowed)
                a_spec = next((s for s in specs if s.id == a_id), None)
                b_spec = next((s for s in specs if s.id == b_id), None)
                if a_spec and b_spec and (a_spec.parent == b_id or b_spec.parent == a_id):
                    continue
                issues.append(f"Overlap: {a_id} ↔ {b_id}")

    return issues
