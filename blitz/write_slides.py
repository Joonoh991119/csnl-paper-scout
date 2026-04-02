"""
Slide Writer — LLM-based slide planning + narration script generation.

Uses Qwen 3.6+ via OpenRouter to generate CSNL Paper Blitz slide plans.
"""

import json
import os
import sys
from pathlib import Path

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

WRITER_MODEL = "qwen/qwen3.6-plus-preview:free"
PARSER_MODEL = "qwen/qwen3.6-plus-preview:free"
MAX_TOKENS = 8000
TEMPERATURE = 0.3


def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)


def load_agent_prompt(name: str) -> str:
    with open(REPO_DIR / "blitz" / "agents" / f"{name}.md") as f:
        return f.read()


def call_openrouter(messages: list, model: str, api_key: str,
                    max_tokens: int = MAX_TOKENS, temperature: float = TEMPERATURE) -> str:
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
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
        raise RuntimeError(f"OpenRouter error: {d['error']}")
    return d["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """Extract JSON from LLM response that may contain markdown code blocks."""
    # Try to find JSON block
    import re
    # Try ```json ... ``` first
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # Try raw JSON
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        return json.loads(text[start:end + 1])
    raise ValueError(f"No JSON found in response:\n{text[:500]}")


# ── Step 1: Structured Paper Analysis ───────────────────────────

def analyze_paper(full_text: str, figures: list, api_key: str) -> dict:
    """Use LLM to extract structured content from paper text."""
    parser_prompt = load_agent_prompt("parser")

    # Build figure inventory for the LLM
    fig_inventory = "\n".join(
        f"- {f['figure_id']} (page {f['page']}, type: {f['type']})"
        for f in figures
        if f["type"] in ("embedded_image", "page_render")
    )

    messages = [
        {"role": "system", "content": parser_prompt},
        {"role": "user", "content": (
            f"Analyze this paper and return the structured JSON.\n\n"
            f"Available figures extracted from the PDF:\n{fig_inventory}\n\n"
            f"PAPER FULL TEXT:\n\n{full_text[:80000]}"  # Trim if very long
        )},
    ]

    print("[WRITER] Step 1: Analyzing paper with LLM...")
    response = call_openrouter(messages, PARSER_MODEL, api_key)
    analysis = extract_json(response)

    return analysis


# ── Step 2: Generate Slide Plan ─────────────────────────────────

def generate_slide_plan(analysis: dict, figures: list, researcher_context: dict,
                        api_key: str, revision_feedback: str = "") -> dict:
    """Generate slide plan + narration scripts."""
    writer_prompt = load_agent_prompt("writer")

    fig_inventory = "\n".join(
        f"- {f['figure_id']} (page {f['page']}, type: {f['type']}, "
        f"{'%.0f' % f.get('area', 0)} area)"
        for f in figures
    )

    researcher_info = (
        f"Target researcher: {researcher_context['name']}\n"
        f"Their project: {researcher_context['project']}\n"
        f"Connection to this paper: {researcher_context['connection']}\n"
    )

    revision_section = ""
    if revision_feedback:
        revision_section = (
            f"\n\n## REVISION REQUIRED\n"
            f"The Blind QA Reviewer found these problems. Fix ALL of them:\n\n"
            f"{revision_feedback}\n\n"
            f"Address every issue specifically. Do not just acknowledge — REWRITE."
        )

    messages = [
        {"role": "system", "content": writer_prompt + revision_section},
        {"role": "user", "content": (
            f"Create a CSNL Paper Blitz slide plan for this paper.\n\n"
            f"## Paper Analysis\n```json\n{json.dumps(analysis, indent=2, ensure_ascii=False)}\n```\n\n"
            f"## Available Figures\n{fig_inventory}\n\n"
            f"## Researcher Context\n{researcher_info}\n\n"
            f"Generate the slide plan JSON. Remember:\n"
            f"- NO complete sentences on slides\n"
            f"- NO Korean on slides\n"
            f"- Figures must occupy 50-70% of slide area\n"
            f"- Total narration under 5 minutes\n"
            f"- 'Why this paper?' must be specific to {researcher_context['name']}'s project"
        )},
    ]

    print("[WRITER] Step 2: Generating slide plan...")
    response = call_openrouter(messages, WRITER_MODEL, api_key, max_tokens=MAX_TOKENS)
    plan = extract_json(response)

    return plan


# ── Main ────────────────────────────────────────────────────────

def write_slides(parsed: dict, researcher_context: dict,
                 revision_feedback: str = "") -> dict:
    """Full write pipeline: analyze → plan slides → return plan."""
    creds = load_credentials()
    api_key = creds["openrouter_api_key"]

    # Step 1: Structured analysis
    analysis = analyze_paper(
        parsed["full_text"],
        parsed["figures"],
        api_key,
    )

    # Save analysis
    out_dir = Path(parsed["full_text_path"]).parent
    with open(out_dir / "analysis.json", "w") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print(f"  Analysis saved to {out_dir / 'analysis.json'}")

    # Step 2: Slide plan
    plan = generate_slide_plan(
        analysis,
        parsed["figures"],
        researcher_context,
        api_key,
        revision_feedback=revision_feedback,
    )

    # Save plan
    with open(out_dir / "slide_plan.json", "w") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    print(f"  Slide plan saved to {out_dir / 'slide_plan.json'}")

    return {"analysis": analysis, "plan": plan}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--parsed", required=True, help="Path to parsed.json")
    parser.add_argument("--researcher", default="JOP")
    parser.add_argument("--project", default="asymmetric prior in time estimation")
    parser.add_argument("--connection", default="prior distribution shape and normative model")
    args = parser.parse_args()

    os.chdir(REPO_DIR)

    with open(args.parsed) as f:
        parsed = json.load(f)
    # Reload full text
    parsed["full_text"] = Path(parsed["full_text_path"]).read_text()

    researcher_context = {
        "name": args.researcher,
        "project": args.project,
        "connection": args.connection,
    }

    result = write_slides(parsed, researcher_context)
    print(f"\nSlides planned: {len(result['plan'].get('slides', []))}")
