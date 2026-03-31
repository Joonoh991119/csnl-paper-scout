"""
Pooled Blind Evaluation — evaluate all posts as a batch.

Simulates a CSNL member scrolling through Slack and seeing ALL posts.
Evaluates: which posts catch my eye? Which figures are readable?
Which hooks stop my scrolling? Overall batch quality.

Then runs individual revision loops on failing posts.

Usage:
    python harness/pooled_eval.py [--max-rounds 3]
"""

import json
import os
import sys
import base64
import copy
from pathlib import Path
from datetime import datetime

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

MAX_ROUNDS = 3
EVAL_MODEL = "anthropic/claude-sonnet-4"
REVISE_MODEL = "anthropic/claude-sonnet-4"

POOLED_SYSTEM_PROMPT = """# Pooled Blind Evaluator

You are a CSNL lab member scrolling through Slack. You see 5 Paper Scout posts
in sequence — each has a figure with a hook caption, plus a thread with details.

You are BUSY. You scroll fast. You are skeptical of recommendations.

## Your Task

Evaluate ALL posts together as a batch. For each post, you see:
1. The figure (image)
2. The hook caption (:fire: line)
3. The thread detail (metadata, figure guide, summary, targeting, tags)

## Per-Post Evaluation

For each of the 5 posts, score:

### V1: Visual Stop Power (시각적 멈춤력) — 0/1/2
"Does the figure make me STOP scrolling?"
- 2: Yes — the figure is clear, self-explanatory, and visually distinct
- 1: Partially — I notice it but need to read text to understand
- 0: No — generic, cluttered, or too small to read on mobile

### V2: Hook Clarity (훅 명확성) — 0/1/2
"In 3 seconds, do I know what this paper found and why it matters to someone in the lab?"
- 2: Yes — finding + relevance in one glance
- 1: Topic is clear but finding is vague
- 0: I need to read the thread to understand the hook

### V3: Figure-Text Coherence (그림-텍스트 일관성) — 0/1/2
"Does the figure guide (:mag:) help me understand the figure?"
- 2: Yes — guide points to specific visual element, I can verify the claim
- 1: Guide exists but the figure doesn't clearly show what it claims
- 0: Mismatch between guide and figure, or no guide

### V4: Action Trigger (행동 유발) — 0/1/2
"Would I DO something after reading this post?"
- 2: Yes — I know exactly what to check/read/compare this week
- 1: Maybe — interesting but vague action
- 0: No — passive information, no urgency

## Batch-Level Evaluation

After scoring all 5 posts individually:

### P1: Visual Variety (시각적 다양성) — 0/1/2
"Do the 5 figures look distinct, or do they blur together?"
- 2: Each figure is visually distinct (different chart types, colors, layouts)
- 1: Some variety but 2-3 figures look similar
- 0: All figures look the same (all page renders, all boxplots, etc.)

### P2: Information Load (정보 부하) — 0/1/2
"If I read all 5, do I feel informed or overwhelmed?"
- 2: Each post adds distinct value, no redundancy
- 1: Some overlap in content or style
- 0: Fatiguing — too similar in format, too much text per post

### P3: Worst Post Drag (최약 포스트) — identify
"Which post would I skip? Why?"

## Output Format

```
## Post-by-Post Scores

### {paper_name_1}
V1={0|1|2} V2={0|1|2} V3={0|1|2} V4={0|1|2} → {total}/8

### {paper_name_2}
V1={0|1|2} V2={0|1|2} V3={0|1|2} V4={0|1|2} → {total}/8

... (all 5)

## Batch Scores
P1 Visual Variety: {0|1|2}
P2 Information Load: {0|1|2}
P3 Worst Post: {paper_name} — {reason}

## Revision Needed (for posts scoring < 6/8)
{paper_name}: {specific changes}
```

## Rules
- Default to 1, not 2. Score 2 means genuinely excellent.
- You MUST identify at least one post that could improve.
- Compare posts against each other — relative quality matters.
"""


def load_all():
    with open(REPO_DIR / "credentials.json") as f:
        creds = json.load(f)
    with open(REPO_DIR / "data" / "context-bundle.json") as f:
        ctx = json.load(f)
    with open(REPO_DIR / "runs" / "paper-scout-posts-v2-revised.json") as f:
        papers = json.load(f)
    with open(REPO_DIR / "runs" / "figures" / "ranking_results.json") as f:
        ranking = json.load(f)
    return creds, ctx, papers, ranking


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return f"data:image/png;base64,{base64.b64encode(f.read()).decode()}"


def render_post_text(paper: dict) -> str:
    lines = [f":fire: {paper['hook']}", ""]
    lines.append(f"*{paper['title']}*")
    lines.append(f"_{paper['authors']} — {paper['journal']} ({paper['year']})_")
    lines.append(f":link: {paper['doi_url']}")
    lines.append("")
    if paper.get("figure_guide"):
        lines.append(f":mag: {paper['figure_guide']}")
        lines.append("")
    if paper.get("summary"):
        lines.append(paper["summary"])
        lines.append("")
    for t in paper.get("targeting_lines", []):
        lines.append(f":dart: *{t['name']}의 {t['project']}*: {t['description']}")
    lines.append("")
    lines.append(f":label: {paper['dimension_tags']} — anchor: {paper['anchor_paper']}")
    return "\n".join(lines)


def get_member_context(name: str, ctx: dict) -> str:
    for gk, g in ctx.get("member_groups", {}).items():
        if name in g.get("projects", {}):
            projs = g["projects"][name]
            lines = [f"You are {name}, CSNL researcher."]
            lines.append(f"Group focus: {g.get('focus', '')}")
            for pn, pd in projs.items():
                lines.append(f"  - {pn}: {pd}")
            return "\n".join(lines)
    return f"You are {name}, CSNL researcher."


def call_llm(messages, api_key, model=EVAL_MODEL, max_tokens=3000):
    r = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.4},
        timeout=120,
    )
    d = r.json()
    if "error" in d:
        raise RuntimeError(f"API error: {d['error']}")
    return d["choices"][0]["message"]["content"]


def parse_pooled_scores(response: str, paper_names: list) -> dict:
    """Parse V1-V4 scores per paper and P1-P2 batch scores."""
    import re
    result = {"papers": {}, "batch": {}, "worst": "", "response": response}

    for name in paper_names:
        scores = {}
        # Find section for this paper
        pattern = rf"###\s*{re.escape(name)}.*?V1\s*[=:]\s*(\d).*?V2\s*[=:]\s*(\d).*?V3\s*[=:]\s*(\d).*?V4\s*[=:]\s*(\d)"
        m = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if m:
            scores = {"V1": int(m.group(1)), "V2": int(m.group(2)),
                       "V3": int(m.group(3)), "V4": int(m.group(4))}
            scores["total"] = sum(scores.values())
        result["papers"][name] = scores

    # Batch scores
    for dim in ["P1", "P2"]:
        m = re.search(rf"{dim}[^:]*:\s*(\d)", response)
        if m:
            result["batch"][dim] = int(m.group(1))

    # Worst post
    m = re.search(r"P3[^:]*:\s*(\w+)", response)
    if m:
        result["worst"] = m.group(1)

    return result


def run_pooled_eval(papers, ranking, ctx, api_key, member_name="JOP"):
    """Run pooled evaluation from one member's perspective."""
    member_ctx = get_member_context(member_name, ctx)

    # Build message with all 5 figures + texts
    content_parts = [
        {"type": "text", "text": f"{member_ctx}\n\n---\n\nYou are scrolling through Slack and see these 5 Paper Scout posts:\n\n"}
    ]

    for i, paper in enumerate(papers):
        post_text = render_post_text(paper)
        fig_path = ranking.get(paper["name"], {}).get("path", "")
        if fig_path and not Path(fig_path).is_absolute():
            fig_path = str(REPO_DIR / fig_path)

        content_parts.append({"type": "text", "text": f"\n--- POST {i+1}: {paper['name']} ---\n{post_text}\n\nFigure for this post:"})
        if fig_path and Path(fig_path).exists():
            content_parts.append({"type": "image_url", "image_url": {"url": encode_image(fig_path)}})
        else:
            content_parts.append({"type": "text", "text": "[No figure available]"})

    content_parts.append({"type": "text", "text": "\n\nEvaluate ALL 5 posts. Follow the output format exactly."})

    messages = [
        {"role": "system", "content": POOLED_SYSTEM_PROMPT},
        {"role": "user", "content": content_parts},
    ]

    response = call_llm(messages, api_key, max_tokens=3000)
    paper_names = [p["name"] for p in papers]
    return parse_pooled_scores(response, paper_names)


def revise_post(paper, feedback, api_key):
    """Revise a single post based on pooled eval feedback."""
    post_text = render_post_text(paper)
    prompt = (
        "Revise this Paper Scout post based on the evaluator feedback.\n\n"
        "RULES:\n"
        "- Fix ONLY the flagged issues\n"
        "- Output JSON with revised fields: {hook, summary, figure_guide, targeting_lines}\n"
        "- targeting_lines: [{slack_id, name, project, description}]\n"
        "- Korean for hook/summary/figure_guide/description, English for technical terms\n"
        "- Do NOT change: title, authors, journal, year, doi_url, dimension_tags, anchor_paper\n\n"
        f"CURRENT POST:\n{post_text}\n\n"
        f"FEEDBACK:\n{feedback}\n\n"
        "Output ONLY valid JSON. No markdown fences."
    )
    response = call_llm([{"role": "user", "content": prompt}], api_key, model=REVISE_MODEL)
    text = response.strip()
    for prefix in ["```json", "```"]:
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith("```"):
        text = text[:-3]
    try:
        revisions = json.loads(text.strip())
    except json.JSONDecodeError:
        print(f"    ⚠ JSON parse failed")
        return paper
    revised = copy.deepcopy(paper)
    for key in ("hook", "summary", "figure_guide", "targeting_lines"):
        if key in revisions:
            revised[key] = revisions[key]
    return revised


def run_loop(max_rounds=MAX_ROUNDS):
    creds, ctx, papers, ranking = load_all()
    api_key = creds["openrouter_api_key"]

    # Evaluate from multiple member perspectives
    members_to_eval = ["JOP", "SK", "MSY"]
    history = []

    for rnd in range(1, max_rounds + 1):
        print(f"\n{'='*60}")
        print(f"  POOLED EVAL — Round {rnd}/{max_rounds}")
        print(f"{'='*60}")

        round_results = []
        for member in members_to_eval:
            print(f"\n  Evaluating as {member}...", flush=True)
            result = run_pooled_eval(papers, ranking, ctx, api_key, member)
            round_results.append({"member": member, **result})

            # Print scores
            for name, scores in result["papers"].items():
                if scores:
                    print(f"    {name}: V1={scores.get('V1','?')} V2={scores.get('V2','?')} "
                          f"V3={scores.get('V3','?')} V4={scores.get('V4','?')} → {scores.get('total','?')}/8")
            batch = result.get("batch", {})
            print(f"    Batch: P1={batch.get('P1','?')} P2={batch.get('P2','?')} Worst={result.get('worst','?')}")

        history.append({"round": rnd, "results": round_results})

        # Aggregate: find papers that need revision (avg total < 6 across evaluators)
        paper_avg = {}
        for name in [p["name"] for p in papers]:
            totals = [r["papers"].get(name, {}).get("total", 8)
                      for r in round_results if r["papers"].get(name, {}).get("total") is not None]
            if totals:
                paper_avg[name] = sum(totals) / len(totals)

        needs_revision = [name for name, avg in paper_avg.items() if avg < 6]
        print(f"\n  Averages: {' | '.join(f'{n}={paper_avg.get(n,0):.1f}' for n in paper_avg)}")

        if not needs_revision:
            print(f"\n  ✅ All posts pass pooled eval at round {rnd}")
            break

        if rnd < max_rounds:
            print(f"\n  Revising {len(needs_revision)} posts: {needs_revision}")
            # Collect feedback for failing posts
            for name in needs_revision:
                feedback_parts = []
                for r in round_results:
                    scores = r["papers"].get(name, {})
                    if scores.get("total", 8) < 6:
                        # Extract relevant feedback from response
                        feedback_parts.append(f"{r['member']}: scores={scores}")
                        # Find revision section in response
                        resp = r.get("response", "")
                        if name in resp:
                            idx = resp.index(name)
                            snippet = resp[idx:idx+500]
                            feedback_parts.append(snippet)

                feedback = "\n".join(feedback_parts)
                for i, p in enumerate(papers):
                    if p["name"] == name:
                        print(f"    Revising {name}...")
                        papers[i] = revise_post(p, feedback, api_key)
                        break

    # Save results
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = REPO_DIR / "harness" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save summary
    summary = {
        "timestamp": timestamp,
        "rounds": len(history),
        "paper_averages": paper_avg,
        "all_pass": not needs_revision if 'needs_revision' in dir() else True,
    }
    for rnd_data in history:
        rnd_num = rnd_data["round"]
        for r in rnd_data["results"]:
            for name, scores in r["papers"].items():
                key = f"R{rnd_num}_{r['member']}_{name}"
                summary[key] = scores

    with open(out_dir / f"pooled-eval-{timestamp}.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Save revised posts
    existing_path = REPO_DIR / "runs" / "paper-scout-posts-v2-revised.json"
    with open(existing_path, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)

    print(f"\n📝 Results: {out_dir}/pooled-eval-{timestamp}.json")
    print(f"📝 Posts: {existing_path}")

    # Final summary
    print(f"\n{'='*60}")
    print("POOLED EVAL FINAL SUMMARY")
    print(f"{'='*60}")
    for name, avg in sorted(paper_avg.items(), key=lambda x: -x[1]):
        icon = "✅" if avg >= 6 else "⚠️"
        print(f"  {icon} {name}: avg={avg:.1f}/8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()
    run_loop(args.max_rounds)
