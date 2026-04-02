"""
Style Segmenter — Extract visual elements from academic figures using SAM2.

Uses HuggingFace Inference API (free) for segmentation, with local fallback.
Builds a reusable visual asset library from real paper figures.
"""

import base64
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
BLITZ_DIR = REPO_DIR / "blitz"
ASSETS_DIR = BLITZ_DIR / "style_knowledge" / "assets"

# Asset categories
CATEGORIES = {
    "stimuli": ["grating", "gabor", "dot pattern", "number", "face", "orientation", "color patch"],
    "icons": ["brain", "eye", "screen", "monitor", "clock", "timer", "hand", "mouse", "keyboard"],
    "feedback": ["checkmark", "cross mark", "reward", "score", "green circle", "red circle"],
    "elements": ["fixation cross", "arrow", "plus sign", "question mark", "cue"],
}

# HuggingFace free inference API
HF_API_URL = "https://router.huggingface.co/hf-inference/models/facebook/sam2.1-hiera-large"


def _load_hf_token() -> str | None:
    """Try to load HF token from env or credentials."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN")
    if token:
        return token
    creds_path = REPO_DIR / "credentials.json"
    if creds_path.exists():
        with open(creds_path) as f:
            creds = json.load(f)
            return creds.get("hf_token")
    return None


# ── Automatic Grid-Based Segmentation ─────────────────────────

def segment_figure_grid(image_path: str, grid_size: int = 3) -> list[dict]:
    """Segment figure into a grid of regions and identify interesting ones.

    Simpler than SAM — just crops figure into grid cells and checks
    which cells contain non-white content. Good for extracting
    individual panels from multi-panel figures.
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    cell_w = w // grid_size
    cell_h = h // grid_size

    segments = []
    for row in range(grid_size):
        for col in range(grid_size):
            x0 = col * cell_w
            y0 = row * cell_h
            x1 = min(x0 + cell_w, w)
            y1 = min(y0 + cell_h, h)

            crop = img.crop((x0, y0, x1, y1))
            arr = np.array(crop)

            # Check if cell has meaningful content (not mostly white)
            white_ratio = np.mean(arr > 240) if arr.size > 0 else 1.0
            if white_ratio < 0.85:  # More than 15% non-white
                segments.append({
                    "bbox": [x0, y0, x1, y1],
                    "row": row,
                    "col": col,
                    "white_ratio": float(white_ratio),
                    "crop": crop,
                })

    return segments


# ── Color-Based Element Extraction ────────────────────────────

def extract_colored_regions(image_path: str, min_area_ratio: float = 0.005) -> list[dict]:
    """Extract distinctly colored regions from a figure.

    Good for finding colored boxes, bars, data points, etc.
    """
    img = Image.open(image_path).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]
    total_pixels = h * w

    # Quantize to find dominant colors
    img_small = img.resize((200, 200), Image.LANCZOS)
    quantized = img_small.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()[:36]  # 12 colors * 3 channels

    regions = []
    for i in range(0, len(palette), 3):
        r, g, b = palette[i], palette[i+1], palette[i+2]

        # Skip near-white and near-black
        if r > 230 and g > 230 and b > 230:
            continue
        if r < 30 and g < 30 and b < 30:
            continue
        # Skip grays
        if abs(r - g) < 20 and abs(g - b) < 20 and abs(r - b) < 20:
            continue

        # Find pixels matching this color (with tolerance)
        tol = 40
        mask = (
            (np.abs(arr[:,:,0].astype(int) - r) < tol) &
            (np.abs(arr[:,:,1].astype(int) - g) < tol) &
            (np.abs(arr[:,:,2].astype(int) - b) < tol)
        )

        area_ratio = mask.sum() / total_pixels
        if area_ratio < min_area_ratio:
            continue

        # Find bounding box of this color region
        ys, xs = np.where(mask)
        if len(ys) == 0:
            continue

        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        bbox_w = bbox[2] - bbox[0]
        bbox_h = bbox[3] - bbox[1]

        # Skip very thin regions (likely lines/borders)
        if bbox_w < 20 or bbox_h < 20:
            continue

        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        crop = img.crop(bbox)

        regions.append({
            "color": hex_color,
            "bbox": bbox,
            "area_ratio": float(area_ratio),
            "crop": crop,
        })

    return regions


# ── Paradigm Element Extraction ───────────────────────────────

def extract_paradigm_elements(image_path: str, figure_analysis: dict) -> list[dict]:
    """Extract visual elements from a paradigm diagram figure.

    Uses the analysis JSON to guide extraction — looks for boxes,
    stimulus regions, etc.
    """
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    elements = []

    # Strategy 1: Grid segmentation for multi-panel figures
    n_panels = figure_analysis.get("layout", {}).get("n_panels", 1)
    if n_panels > 1:
        grid_size = min(n_panels, 4)
        grid_segments = segment_figure_grid(image_path, grid_size)
        for seg in grid_segments:
            elements.append({
                "type": "panel_crop",
                "bbox": seg["bbox"],
                "crop": seg["crop"],
                "content_ratio": 1 - seg["white_ratio"],
            })

    # Strategy 2: Color-based region extraction
    color_regions = extract_colored_regions(image_path)
    for region in color_regions[:8]:  # Top 8 colored regions
        elements.append({
            "type": "colored_element",
            "color": region["color"],
            "bbox": region["bbox"],
            "crop": region["crop"],
            "area_ratio": region["area_ratio"],
        })

    # Strategy 3: Central region crop (often contains the key stimulus)
    center_crop = img.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    elements.append({
        "type": "center_region",
        "bbox": [w // 4, h // 4, 3 * w // 4, 3 * h // 4],
        "crop": center_crop,
    })

    return elements


# ── Asset Library Builder ─────────────────────────────────────

def build_asset_library(analysis_log_path: Path = None, max_figures: int = 50):
    """Build visual asset library from analyzed figures.

    Reads analysis_log.jsonl, finds paradigm diagrams and graphical abstracts,
    extracts elements, saves as transparent PNGs.
    """
    if analysis_log_path is None:
        analysis_log_path = BLITZ_DIR / "style_knowledge" / "analysis_log.jsonl"

    if not analysis_log_path.exists():
        print("No analysis log found.")
        return

    # Create asset directories
    for cat in ["panels", "colored_elements", "paradigm_crops", "stimuli"]:
        (ASSETS_DIR / cat).mkdir(parents=True, exist_ok=True)

    # Read analysis log
    entries = []
    with open(analysis_log_path) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("figure_type") in ("paradigm_diagram", "graphical_abstract",
                                                  "model_diagram", "schematic", "data_plot"):
                    src = entry.get("source_path", "")
                    if src and os.path.exists(src):
                        entries.append(entry)
            except json.JSONDecodeError:
                continue

    print(f"Found {len(entries)} figures with source files")

    asset_count = 0
    for i, entry in enumerate(entries[:max_figures]):
        src_path = entry["source_path"]
        fig_type = entry.get("figure_type", "unknown")
        fig_id = entry.get("figure_id", f"fig_{i}")

        try:
            elements = extract_paradigm_elements(src_path, entry)

            for j, elem in enumerate(elements):
                crop = elem.get("crop")
                if crop is None:
                    continue

                # Determine output category
                elem_type = elem.get("type", "unknown")
                if elem_type == "panel_crop":
                    out_dir = ASSETS_DIR / "panels"
                elif elem_type == "colored_element":
                    out_dir = ASSETS_DIR / "colored_elements"
                else:
                    out_dir = ASSETS_DIR / "paradigm_crops"

                out_path = out_dir / f"{fig_type}_{fig_id}_{j}.png"
                crop.save(str(out_path))
                asset_count += 1

        except Exception as e:
            print(f"  [WARN] Failed on {fig_id}: {e}")
            continue

    print(f"Extracted {asset_count} assets to {ASSETS_DIR}")

    # Generate asset index
    index = {"total_assets": asset_count, "categories": {}}
    for cat_dir in ASSETS_DIR.iterdir():
        if cat_dir.is_dir():
            files = list(cat_dir.glob("*.png"))
            index["categories"][cat_dir.name] = len(files)

    with open(ASSETS_DIR / "index.json", "w") as f:
        json.dump(index, f, indent=2)

    return index


# ── SAM2 API Segmentation (when available) ────────────────────

def segment_with_sam2(image_path: str, points: list[list[int]] = None) -> list[dict]:
    """Segment figure using SAM2 via HuggingFace Inference API.

    Args:
        image_path: path to figure PNG
        points: optional list of [x, y] points to segment around

    Returns list of mask dicts.
    """
    hf_token = _load_hf_token()
    if not hf_token:
        print("  [SAM2] No HF token available, using grid segmentation fallback")
        return segment_figure_grid(image_path)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    headers = {"Authorization": f"Bearer {hf_token}"}

    # SAM2 expects image + optional input points
    payload = {"inputs": {}}
    if points:
        payload["inputs"]["input_points"] = points

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            data=image_bytes,
            timeout=60,
        )
        if response.status_code == 200:
            masks = response.json()
            return masks
        else:
            print(f"  [SAM2] API returned {response.status_code}: {response.text[:200]}")
            return segment_figure_grid(image_path)
    except Exception as e:
        print(f"  [SAM2] API error: {e}")
        return segment_figure_grid(image_path)


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build visual asset library")
    parser.add_argument("--max-figures", type=int, default=50)
    parser.add_argument("--test-single", type=str, default=None,
                        help="Test on single figure path")
    args = parser.parse_args()

    if args.test_single:
        print(f"Testing on: {args.test_single}")
        # Grid segmentation
        segments = segment_figure_grid(args.test_single)
        print(f"  Grid segments: {len(segments)}")
        # Color extraction
        colors = extract_colored_regions(args.test_single)
        print(f"  Colored regions: {len(colors)}")
        for c in colors[:5]:
            print(f"    {c['color']} area={c['area_ratio']:.3f}")
    else:
        index = build_asset_library(max_figures=args.max_figures)
        if index:
            print(f"\nAsset library built: {index}")
