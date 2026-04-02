"""
Slide Reviewer — Academic presentation quality assessment.

Uses slide_reviewer.md rubric (S1-S5) calibrated for SLIDES not figures.
"""

import base64
import json
import re
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

REVIEWER_MODEL = "google/gemini-2.5-flash"
API_URL = "https://openrouter.ai/api/v1/chat/completions"
PROMPT_PATH = REPO_DIR / "blitz" / "agents" / "slide_reviewer.md"

WEIGHTS = {"S1": 0.25, "S2": 0.25, "S3": 0.20, "S4": 0.15, "S5": 0.15}


def _load_credentials() -> str:
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)["openrouter_api_key"]


def _call_api(messages, api_key, max_tokens=2000):
    for attempt in range(3):
        try:
            r = requests.post(API_URL, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }, json={
                "model": REVIEWER_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            }, timeout=120)
            if r.status_code in (429, 529) or not r.text:
                time.sleep(3 * (attempt + 1))
                continue
            d = r.json()
            if "error" in d:
                time.sleep(2 * (attempt + 1))
                continue
            return d["choices"][0]["message"]["content"]
        except Exception:
            if attempt < 2:
                time.sleep(2)
            else:
                raise
    raise RuntimeError("Max retries")


def _img_b64(path: str) -> str:
    img = Image.open(path)
    if max(img.size) > 1536:
        img.thumbnail((1536, 1536), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def review_slide(image_path: str, slide_type: str, api_key: str) -> dict:
    """Review a single slide image."""
    with open(PROMPT_PATH) as f:
        prompt = f.read()

    b64 = _img_b64(image_path)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": [
            {"type": "text", "text": f"Review this {slide_type} slide:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
        ]},
    ]

    response = _call_api(messages, api_key)

    scores = {}
    for dim in ["S1", "S2", "S3", "S4", "S5"]:
        for p in [rf'{dim}[^—\n]*—\s*(\d)/5', rf'{dim}.*?(\d)\s*/\s*5']:
            m = re.search(p, response)
            if m:
                scores[dim] = int(m.group(1))
                break
        if dim not in scores:
            scores[dim] = 2

    weighted = sum(scores[d] * WEIGHTS[d] for d in WEIGHTS)
    all_above_3 = all(v >= 3 for v in scores.values())

    if weighted >= 3.5 and all_above_3:
        verdict = "PASS"
    elif weighted >= 2.5 or any(v == 2 for v in scores.values()):
        verdict = "REVISE"
    else:
        verdict = "FAIL"

    deficiencies = ""
    m = re.search(r'###\s*Deficiencies.*?(?=###|$)', response, re.DOTALL | re.IGNORECASE)
    if m:
        deficiencies = m.group().strip()

    return {
        "scores": scores,
        "weighted_avg": round(weighted, 2),
        "verdict": verdict,
        "deficiencies": deficiencies,
        "raw": response,
    }


def review_deck(slides_dir: str, slide_types: list[str] = None, api_key: str = None):
    """Review all slides in a directory."""
    if api_key is None:
        api_key = _load_credentials()

    slides_dir = Path(slides_dir)
    pngs = sorted(slides_dir.glob("slide_*.png"))

    if slide_types is None:
        slide_types = ["title", "motivation", "methods", "results", "model", "conclusions", "references"]

    results = []
    passes = 0
    for i, png in enumerate(pngs):
        stype = slide_types[i] if i < len(slide_types) else "content"
        r = review_slide(str(png), stype, api_key)
        s = r["scores"]
        passed = r["verdict"] == "PASS"
        if passed:
            passes += 1
        results.append(r)
        print(f"  Slide {i+1} ({stype:12s}): {r['verdict']:6s} avg={r['weighted_avg']} "
              f"S1={s['S1']} S2={s['S2']} S3={s['S3']} S4={s['S4']} S5={s['S5']}")

    total = len(pngs)
    print(f"\n  Deck: {passes}/{total} PASS ({passes/total*100:.0f}%)")
    avgs = [r["weighted_avg"] for r in results]
    print(f"  Mean: {sum(avgs)/len(avgs):.2f}")

    return {"results": results, "pass_rate": passes / total if total else 0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("slides_dir")
    parser.add_argument("--types", nargs="+", default=None)
    args = parser.parse_args()
    review_deck(args.slides_dir, args.types)
