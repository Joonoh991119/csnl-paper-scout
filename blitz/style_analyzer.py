"""
Style Analyzer — Figure extraction + multimodal LLM design parameter analysis.

Two stages:
  1. Classify: heuristic + cheap LLM call to categorize figure types
  2. Extract: multimodal vision LLM for detailed design parameter extraction
"""

import base64
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
BLITZ_DIR = REPO_DIR / "blitz"
sys.path.insert(0, str(REPO_DIR))

from blitz.parse_paper import extract_figures, extract_full_text

# ── Config ─────────────────────────────────────────────────────

VISION_MODEL = "google/gemini-2.5-flash"
CLASSIFY_MODEL = "google/gemini-2.5-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_RETRIES = 3
RETRY_DELAY = 2.0

ANALYZER_PROMPT_PATH = BLITZ_DIR / "agents" / "style_analyzer.md"


def _load_credentials() -> str:
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)["openrouter_api_key"]


def _load_analyzer_prompt() -> str:
    with open(ANALYZER_PROMPT_PATH) as f:
        return f.read()


# ── API Call ───────────────────────────────────────────────────

def call_openrouter_vision(messages: list, model: str, api_key: str,
                           max_tokens: int = 2000, temperature: float = 0.2) -> str:
    """Call OpenRouter with vision-capable model. Handles retries."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
                timeout=120,
            )
            d = r.json()
            if "error" in d:
                err = d["error"]
                if isinstance(err, dict) and err.get("code") == 429:
                    time.sleep(RETRY_DELAY * (attempt + 1))
                    continue
                raise RuntimeError(f"OpenRouter error: {err}")
            return d["choices"][0]["message"]["content"]
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def _image_to_base64(image_path: str, max_size: int = 1024) -> str:
    """Convert image to base64, resizing if needed."""
    img = Image.open(image_path)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _image_to_base64_full(image_path: str, max_size: int = 2048) -> str:
    """Higher-res version for detailed analysis."""
    return _image_to_base64(image_path, max_size)


# ── Figure Classification ─────────────────────────────────────

def classify_figures(figures: list[dict], api_key: str) -> list[dict]:
    """Classify figure types using heuristics + LLM.

    Returns figures with added 'classification' field.
    """
    if not figures:
        return []

    # Heuristic pre-classification
    for fig in figures:
        fig["classification"] = "unknown"
        fig["priority"] = 0  # 0=skip, 1=high, 2=medium

        # Skip page renders and full-page images
        fig_id = fig.get("figure_id", "")
        if fig.get("type") == "page_render" or "_full" in fig_id or fig.get("type") == "full_page":
            fig["classification"] = "page_render"
            fig["priority"] = 0
            continue

        # Small images are likely icons/logos
        w = fig.get("width", 0)
        h = fig.get("height", 0)
        if w < 200 or h < 200:
            fig["classification"] = "icon"
            fig["priority"] = 0
            continue

        # Everything else gets LLM classification
        fig["priority"] = 1

    # Batch classify via LLM — send thumbnail grid
    to_classify = [f for f in figures if f["priority"] > 0]
    if not to_classify:
        return figures

    # Build grid image (2 columns)
    grid_b64_items = []
    for fig in to_classify[:12]:  # max 12 figures per paper
        path = fig.get("path", "")
        if path and os.path.exists(path):
            b64 = _image_to_base64(path, max_size=512)
            grid_b64_items.append((fig["figure_id"], b64))

    if not grid_b64_items:
        return figures

    # Send each image with ID for classification
    content = [{
        "type": "text",
        "text": (
            "Classify each figure. Return ONLY a JSON array like:\n"
            '[{"id": "fig_id", "type": "paradigm_diagram|data_plot|brain_image|'
            'model_diagram|graphical_abstract|schematic|other"}]\n\n'
            "Figures:"
        ),
    }]
    for fig_id, b64 in grid_b64_items:
        content.append({"type": "text", "text": f"\n--- Figure {fig_id} ---"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        })

    try:
        response = call_openrouter_vision(
            [{"role": "user", "content": content}],
            model=CLASSIFY_MODEL, api_key=api_key, max_tokens=1000,
        )
        # Parse JSON from response
        json_match = re.search(r'\[.*\]', response, re.DOTALL)
        if json_match:
            classifications = json.loads(json_match.group())
            cls_map = {c["id"]: c["type"] for c in classifications}
            for fig in to_classify:
                if fig["figure_id"] in cls_map:
                    fig["classification"] = cls_map[fig["figure_id"]]
                    # High priority for paradigm diagrams and graphical abstracts
                    if fig["classification"] in ("paradigm_diagram", "graphical_abstract", "model_diagram"):
                        fig["priority"] = 1
                    elif fig["classification"] in ("data_plot", "schematic"):
                        fig["priority"] = 2
                    else:
                        fig["priority"] = 0
    except Exception as e:
        print(f"  [WARN] Classification LLM failed: {e}")
        # Fallback: mark all as priority 2
        for fig in to_classify:
            fig["priority"] = 2

    return figures


def select_informative(figures: list[dict], max_per_paper: int = 3) -> list[dict]:
    """Select most informative figures for detailed analysis."""
    candidates = [f for f in figures if f.get("priority", 0) > 0]
    # Sort by priority (1 = highest), then by area (larger = more informative)
    candidates.sort(key=lambda f: (f["priority"], -(f.get("width", 0) * f.get("height", 0))))
    return candidates[:max_per_paper]


# ── Design Parameter Extraction ───────────────────────────────

def analyze_figure(fig: dict, api_key: str) -> dict:
    """Extract design parameters from a single figure via multimodal LLM."""
    path = fig.get("path", "")
    if not path or not os.path.exists(path):
        return {"error": "file_not_found", "figure_id": fig.get("figure_id")}

    b64 = _image_to_base64_full(path)
    prompt = _load_analyzer_prompt()

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "Analyze this academic figure and return the JSON:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    try:
        response = call_openrouter_vision(
            messages, model=VISION_MODEL, api_key=api_key, max_tokens=2000,
        )
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result["figure_id"] = fig.get("figure_id", "")
            result["source_path"] = path
            result["classification"] = fig.get("classification", "unknown")

            # Cross-validate colors with pixel sampling
            result = _validate_colors(result, path)
            return result
        else:
            return {
                "error": "no_json_in_response",
                "figure_id": fig.get("figure_id"),
                "raw_response": response[:500],
            }
    except Exception as e:
        return {
            "error": str(e),
            "figure_id": fig.get("figure_id"),
        }


# ── Pixel Validation ──────────────────────────────────────────

def _get_dominant_colors(image_path: str, n: int = 5) -> list[str]:
    """Extract dominant colors from image using quantization."""
    try:
        img = Image.open(image_path).convert("RGB")
        img = img.resize((100, 100), Image.LANCZOS)
        result = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
        palette = result.getpalette()[:n * 3]
        colors = []
        for i in range(0, len(palette), 3):
            r, g, b = palette[i], palette[i+1], palette[i+2]
            colors.append(f"#{r:02x}{g:02x}{b:02x}")
        return colors
    except Exception:
        return []


def _validate_colors(result: dict, image_path: str) -> dict:
    """Cross-validate LLM-reported colors against pixel sampling."""
    pixel_colors = _get_dominant_colors(image_path)
    if pixel_colors:
        result["_pixel_dominant_colors"] = pixel_colors
        # Flag if LLM colors are very different from pixel colors
        llm_colors = result.get("colors", {}).get("dominant_palette", [])
        if llm_colors:
            result["_color_validation"] = "ok"
            # Simple check: at least one LLM color should be close to pixel colors
            from blitz.style_state import _hex_distance
            any_close = False
            for lc in llm_colors:
                if not (lc and len(lc) == 7 and lc.startswith("#")):
                    continue
                for pc in pixel_colors:
                    if _hex_distance(lc, pc) < 60:
                        any_close = True
                        break
            if not any_close and len(llm_colors) > 0:
                result["_color_validation"] = "mismatch"
    return result


# ── Full Paper Analysis ───────────────────────────────────────

def analyze_paper(storage_key: str, pdf_path: Path, api_key: str,
                  tmp_dir: Path = None) -> dict:
    """Full analysis pipeline for one paper.

    Returns: {
        "storage_key": str,
        "n_figures": int,
        "n_analyzed": int,
        "analyses": [dict],
    }
    """
    if tmp_dir is None:
        tmp_dir = BLITZ_DIR / "style_knowledge" / "tmp" / storage_key
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Extract figures
    figures = extract_figures(pdf_path, tmp_dir)
    n_figures = len(figures)

    # Classify
    figures = classify_figures(figures, api_key)

    # Select informative figures
    selected = select_informative(figures)

    # Analyze each
    analyses = []
    for fig in selected:
        result = analyze_figure(fig, api_key)
        if "error" not in result:
            analyses.append(result)

    return {
        "storage_key": storage_key,
        "n_figures": n_figures,
        "n_analyzed": len(analyses),
        "analyses": analyses,
    }


# ── CLI test ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-paper", default="EECH87V2",
                        help="Zotero storage key to test")
    args = parser.parse_args()

    from blitz.style_state import find_pdf

    api_key = _load_credentials()
    pdf = find_pdf(args.test_paper)
    if not pdf:
        print(f"PDF not found for key: {args.test_paper}")
        sys.exit(1)

    print(f"Analyzing: {pdf.name}")
    result = analyze_paper(args.test_paper, pdf, api_key)
    print(f"  Figures extracted: {result['n_figures']}")
    print(f"  Figures analyzed: {result['n_analyzed']}")
    for a in result["analyses"]:
        ft = a.get("figure_type", "?")
        layout = a.get("layout", {}).get("pattern", "?")
        colors = a.get("colors", {}).get("dominant_palette", [])
        print(f"  [{ft}] layout={layout} colors={colors[:3]}")
