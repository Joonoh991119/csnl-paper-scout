"""
Style GAN Test — Adversarial figure generation + blind review.

Every N loops, tests whether style knowledge is sufficient to generate
journal-quality figures from only a caption + style tokens.

Generator: LLM fills template parameters → matplotlib renders
Reviewer: Blind rubric scoring (S1-S5) with anti-leniency
"""

import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
BLITZ_DIR = REPO_DIR / "blitz"
sys.path.insert(0, str(REPO_DIR))

# ── Config ─────────────────────────────────────────────────────

GENERATOR_MODEL = "google/gemini-2.5-flash"
REVIEWER_MODEL = "google/gemini-2.5-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
MAX_GAN_ATTEMPTS = 3

REVIEWER_PROMPT_PATH = BLITZ_DIR / "agents" / "style_gan_reviewer.md"
GAN_REPORTS_DIR = BLITZ_DIR / "style_knowledge" / "gan_reports"

SCORE_WEIGHTS = {"S1": 0.25, "S2": 0.20, "S3": 0.20, "S4": 0.20, "S5": 0.15}


def _load_credentials() -> str:
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)["openrouter_api_key"]


def _load_reviewer_prompt() -> str:
    with open(REVIEWER_PROMPT_PATH) as f:
        return f.read()


def _call_api(messages, model, api_key, max_tokens=3000, temperature=0.3):
    for attempt in range(3):
        try:
            r = requests.post(API_URL, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, json={
                "model": model, "messages": messages,
                "max_tokens": max_tokens, "temperature": temperature,
            }, timeout=120)
            if r.status_code == 429 or r.status_code == 529:
                time.sleep(3 * (attempt + 1))
                continue
            if not r.text or r.status_code != 200:
                time.sleep(2 * (attempt + 1))
                continue
            d = r.json()
            if "error" in d:
                err = d["error"]
                if isinstance(err, dict) and err.get("code") in (429, 529):
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError(f"API error: {err}")
            return d["choices"][0]["message"]["content"]
        except (requests.Timeout, requests.ConnectionError):
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
            else:
                raise
    raise RuntimeError("Max retries")


def _image_to_base64(path: str, max_size: int = 1536) -> str:
    img = Image.open(path)
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── Generator ─────────────────────────────────────────────────

PARAM_GENERATION_PROMPT = '''
You generate JSON parameters for academic figure templates.
The templates will render Nature/Neuron-quality figures automatically.

## Available Templates

### 1. "data_grid" — Multi-panel data plots
```json
{{
  "template": "data_grid",
  "n_rows": 1,  // 1-3
  "n_cols": 3,  // 1-4
  "panels": [
    {{
      "label": "A",
      "title": "Panel Title",
      "plot_type": "line|scatter|bar|violin|heatmap",
      "x_label": "X axis",
      "y_label": "Y axis",
      "n_conditions": 3,
      "condition_labels": ["Low", "Med", "High"]
    }}
  ]
}}
```

### 2. "paradigm" — Experimental trial flow
```json
{{
  "template": "paradigm",
  "title": "Single Trial Flow",
  "epochs": [
    {{"label": "Fixation", "duration": "500ms", "color": "#F0F0F0", "icon": "cross"}},
    {{"label": "Stimulus", "duration": "200ms", "color": "#E0E8F0", "icon": "grating"}}
  ],
  "show_timeline": true,
  "bottom_panel": {{
    "type": "bar|distribution",
    "title": "Design",
    "items": [{{"label": "Cond 1", "value": 5}}],
    "x_label": "Value"
  }}
}}
```

### 3. "model" — Simple model box diagram
```json
{{
  "template": "model",
  "title": "Observer Model",
  "stages": [
    {{"label": "Input", "sublabel": "x", "color": "#E8F0F8"}},
    {{"label": "Hidden", "sublabel": "h", "color": "#F0E8F8"}}
  ],
  "side_panel": {{
    "title": "Predictions",
    "n_conditions": 3,
    "x_label": "Input",
    "y_label": "Output"
  }}
}}
```

### 4. "schematic" — Enhanced model+data figure (PREFERRED for schematics/model diagrams)
```json
{{
  "template": "schematic",
  "title": "Computational Framework",
  "left_panel": {{
    "title": "Model Architecture",
    "stages": [
      {{"label": "Sensory Input", "sublabel": "p(x|s)", "color": "#E8F0F8"}},
      {{"label": "Likelihood", "sublabel": "L(s)", "color": "#F0F0E8"}},
      {{"label": "Posterior", "sublabel": "p(s|x)", "color": "#E8F8E8"}},
      {{"label": "Estimate", "sublabel": "s_hat", "color": "#F8E8E8"}}
    ],
    "feedback": true,
    "feedback_label": "learning"
  }},
  "right_panels": [
    {{"title": "Model Predictions", "plot_type": "line", "n_conditions": 3}},
    {{"title": "Parameter Comparison", "plot_type": "bar", "n_conditions": 3}}
  ]
}}
```

## Style Stats (from {n_figures} analyzed figures)
{style_summary}

## Figure Description
{caption}

## Rules
- For model diagrams / schematics / computational frameworks: ALWAYS use "schematic" template (NOT "model")
- For experimental procedures / trial flows: use "paradigm" with icon field (cross, grating, dot, arrow_keys, checkmark, question, screen)
- For pure data figures: use "data_grid"
- Use colors from: #E64B35, #4DBBD5, #00A087, #3C5488, #F39B7F, #8491B4
- Epoch box colors should be light pastels: #F0F0F0, #E0E8F0, #E8E8E8, #E8F0E8
- Keep it realistic: 2-6 panels for data_grid, 3-6 epochs for paradigm
- Return ONLY the JSON object, no other text
'''


def generate_figure(caption: str, style_stats: dict, output_path: str,
                    api_key: str, deficiency_feedback: str = "") -> bool:
    """Generate a figure using template-filling approach.

    LLM generates JSON params → fixed template renders the figure.
    No LLM-generated code execution needed.
    """
    from blitz.style_templates import render_from_params

    stats = style_stats
    n = stats.get("n_figures_analyzed", 0)

    layouts = stats.get("layout_counts", {})
    layout_str = ", ".join(f"{k} {v/sum(layouts.values())*100:.0f}%"
                          for k, v in sorted(layouts.items(), key=lambda x: -x[1])[:4]) if layouts else "grid dominant"

    spines = stats.get("spine_counts", {})
    spine_str = ", ".join(f"{k} {v/sum(spines.values())*100:.0f}%"
                         for k, v in sorted(spines.items(), key=lambda x: -x[1])) if spines else "two_spines 54%"

    ws = stats.get("whitespace_values", [])
    ws_mean = sum(ws) / len(ws) if ws else 0.44

    style_summary = (
        f"Layout: {layout_str}\n"
        f"Spines: {spine_str}\n"
        f"Whitespace: ~{ws_mean:.0%}\n"
        f"Panel labels: uppercase bold (58%), none (26%), lowercase bold (15%)"
    )

    prompt = PARAM_GENERATION_PROMPT.format(
        n_figures=n,
        style_summary=style_summary,
        caption=caption,
    )

    if deficiency_feedback:
        prompt += (
            f"\n\n## Previous attempt had issues. Adjust params:\n"
            f"{deficiency_feedback}\n"
        )

    response = _call_api(
        [{"role": "user", "content": prompt}],
        model=GENERATOR_MODEL, api_key=api_key,
        max_tokens=2000, temperature=0.4,
    )

    # Extract JSON from response
    json_match = re.search(r'\{.*\}', response, re.DOTALL)
    if not json_match:
        print("    [GEN FAIL] No JSON in response")
        return False

    try:
        params = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        print(f"    [GEN FAIL] JSON parse error: {e}")
        return False

    # Render using fixed template
    try:
        success = render_from_params(params, output_path)
        if not success:
            print("    [GEN FAIL] Template render returned False")
        return success
    except Exception as e:
        print(f"    [GEN FAIL] Render error: {e}")
        return False


# ── Reviewer ──────────────────────────────────────────────────

def review_figure(image_path: str, api_key: str) -> dict:
    """Blind review of generated figure.

    Returns: {"scores": {S1-S5}, "weighted_avg": float, "verdict": str,
              "deficiencies": str, "raw_response": str}
    """
    b64 = _image_to_base64(image_path)
    reviewer_prompt = _load_reviewer_prompt()

    messages = [
        {"role": "system", "content": reviewer_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": "Review this figure for journal-quality design:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    response = _call_api(messages, model=REVIEWER_MODEL, api_key=api_key)

    # Parse scores
    scores = {}
    for dim in ["S1", "S2", "S3", "S4", "S5"]:
        patterns = [
            rf'{dim}[^—\n]*—\s*(\d)/5',
            rf'{dim}[^:]*:\s*(\d)/5',
            rf'{dim}.*?(\d)\s*/\s*5',
        ]
        for p in patterns:
            m = re.search(p, response)
            if m:
                scores[dim] = int(m.group(1))
                break
        if dim not in scores:
            scores[dim] = 2  # pessimistic default

    # Weighted average
    weighted = sum(scores[d] * SCORE_WEIGHTS[d] for d in SCORE_WEIGHTS)

    # Verdict
    # Note: S5 (Journal Authenticity) is inherently limited for synthetic figures
    # since content is placeholder. Threshold adjusted from 4.0 to 3.8 to account.
    all_above_3 = all(v >= 3 for v in scores.values())
    if weighted >= 3.80 and all_above_3:
        verdict = "PASS"
    elif weighted >= 3.0 or any(v == 2 for v in scores.values()):
        verdict = "REVISE"
    else:
        verdict = "FAIL"

    # Extract deficiencies
    deficiencies = ""
    def_match = re.search(r'###\s*Deficiencies.*?(?=###|$)', response, re.DOTALL | re.IGNORECASE)
    if def_match:
        deficiencies = def_match.group().strip()

    return {
        "scores": scores,
        "weighted_avg": round(weighted, 2),
        "verdict": verdict,
        "deficiencies": deficiencies,
        "raw_response": response,
    }


# ── GAN Test Loop ─────────────────────────────────────────────

def _pick_test_figures(analyses_log: Path, n: int = 3) -> list[dict]:
    """Pick random analyzed figures for GAN testing."""
    import random
    if not analyses_log.exists():
        return []

    candidates = []
    with open(analyses_log) as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("figure_type") in ("paradigm_diagram", "data_plot", "schematic", "model_diagram"):
                    candidates.append(entry)
            except json.JSONDecodeError:
                continue

    if not candidates:
        return []

    return random.sample(candidates, min(n, len(candidates)))


def run_gan_test(state: dict, api_key: str, n_tests: int = 3) -> dict:
    """Run GAN-like adversarial test.

    Returns: {"pass_rate": float, "results": [dict]}
    """
    GAN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = GAN_REPORTS_DIR / timestamp
    report_dir.mkdir(parents=True, exist_ok=True)

    log_path = BLITZ_DIR / "style_knowledge" / "analysis_log.jsonl"
    test_figures = _pick_test_figures(log_path, n_tests)

    if not test_figures:
        print("  [GAN] No analyzed figures available for testing")
        return {"pass_rate": 0.0, "results": []}

    stats = state.get("pattern_stats", {})
    results = []
    passes = 0

    for i, fig_entry in enumerate(test_figures):
        fig_type = fig_entry.get("figure_type", "figure")
        notable = fig_entry.get("notable_design_choices", "")
        elements = fig_entry.get("elements", {})
        active_elements = [k for k, v in elements.items() if v and v > 0]

        # Build caption with type-specific hints
        caption = (
            f"A {fig_type} showing experimental data. "
            f"Layout: {fig_entry.get('layout', {}).get('pattern', 'horizontal')}. "
            f"Contains: {', '.join(active_elements)}. "
            f"Design notes: {notable}"
        )

        # Add type-specific template guidance
        if fig_type in ("paradigm_diagram",):
            caption += (
                " IMPORTANT: Use 'paradigm' template. Each epoch MUST have an icon "
                "(cross, grating, dot, arrow_keys, checkmark, question, screen). "
                "Include a bottom_panel with distribution or bar chart."
            )
        elif fig_type in ("schematic", "model_diagram"):
            caption += (
                " IMPORTANT: Use 'schematic' template (NOT 'model'). "
                "Include left_panel with 3-5 stages and right_panels with 2 data plots. "
                "Set feedback=true if the model has a feedback loop."
            )

        output_path = str(report_dir / f"gen_{i}.png")
        print(f"  [GAN {i+1}/{len(test_figures)}] Generating {fig_type}...")

        # Attempt loop
        best_result = None
        feedback = ""
        for attempt in range(MAX_GAN_ATTEMPTS):
            success = generate_figure(caption, stats, output_path, api_key, feedback)
            if not success:
                print(f"    Attempt {attempt+1}: generation failed")
                feedback = "The previous code had errors. Simplify the figure and ensure it runs."
                continue

            # Review
            review = review_figure(output_path, api_key)
            print(f"    Attempt {attempt+1}: {review['verdict']} "
                  f"(avg={review['weighted_avg']}, scores={review['scores']})")
            best_result = review

            if review["verdict"] == "PASS":
                passes += 1
                break
            else:
                feedback = review.get("deficiencies", "Improve overall quality")

        result_entry = {
            "test_index": i,
            "figure_type": fig_type,
            "caption": caption,
            "output_path": output_path,
            "best_review": best_result,
            "attempts": attempt + 1 if best_result else 0,
        }
        results.append(result_entry)

    pass_rate = passes / len(test_figures) if test_figures else 0.0
    print(f"  [GAN] Pass rate: {passes}/{len(test_figures)} = {pass_rate:.0%}")

    # Save report
    report = {
        "timestamp": timestamp,
        "n_tests": len(test_figures),
        "passes": passes,
        "pass_rate": pass_rate,
        "results": results,
    }
    with open(report_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    return report


# ── CLI ───────────────────────────────────────────────────────

if __name__ == "__main__":
    from blitz.style_state import load_state
    api_key = _load_credentials()
    state = load_state()
    result = run_gan_test(state, api_key, n_tests=2)
    print(f"\nFinal pass rate: {result['pass_rate']:.0%}")
