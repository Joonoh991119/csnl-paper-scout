"""
Blind Evaluator Harness v2 — adversarial self-improvement loop.

A blind agent (simulating a CSNL member) reads the post + figure cold,
evaluates comprehension with strict scoring, then feeds back revision instructions.
Auto-escalation: if all posts pass too easily, raises the bar and re-evaluates.

Usage:
    python harness/blind_eval.py [--paper NAME] [--max-rounds 3]
"""

import json
import os
import sys
import base64
import argparse
import copy
from pathlib import Path
from datetime import datetime

import requests

REPO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_DIR))

# ── Config ──────────────────────────────────────────────────────

MAX_ROUNDS = 3
PASS_THRESHOLD = 6  # out of 8
LENIENCY_THRESHOLD = 0.85  # if avg score / max > this, evaluator is too soft
EVAL_MODEL = "anthropic/claude-sonnet-4"
REVISE_MODEL = "anthropic/claude-sonnet-4"


def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)

def load_context_bundle():
    with open(REPO_DIR / "data" / "context-bundle.json") as f:
        return json.load(f)

def load_posts():
    path = REPO_DIR / "runs" / "paper-scout-posts-v2-revised.json"
    if not path.exists():
        path = REPO_DIR / "runs" / "paper-scout-posts-v2.json"
    with open(path) as f:
        return json.load(f)

def save_posts(papers: list, suffix: str = "revised"):
    path = REPO_DIR / "runs" / f"paper-scout-posts-v2-{suffix}.json"
    with open(path, "w") as f:
        json.dump(papers, f, indent=2, ensure_ascii=False)
    return path

def load_agent_prompt():
    with open(REPO_DIR / "agents" / "blind_evaluator.md") as f:
        return f.read()

def load_ranking():
    with open(REPO_DIR / "runs" / "figures" / "ranking_results.json") as f:
        return json.load(f)

def encode_image_base64(path: str) -> str:
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/png;base64,{data}"


# ── Post rendering ──────────────────────────────────────────────

def render_post_for_eval(paper: dict) -> str:
    """Render the post as it would appear in Slack."""
    lines = []
    lines.append(f":fire: {paper['hook']}")
    lines.append("")
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


def get_member_context(paper: dict, context_bundle: dict) -> list[dict]:
    """Get research context for each targeted member."""
    members = []
    seen = set()
    for t in paper.get("targeting_lines", []):
        name = t["name"]
        if name in seen:
            continue
        seen.add(name)
        for group_key, group in context_bundle.get("member_groups", {}).items():
            projects = group.get("projects", {})
            if name in projects:
                members.append({
                    "name": name,
                    "slack_id": t["slack_id"],
                    "projects": projects[name],
                    "group_focus": group.get("focus", ""),
                })
                break
    return members


# ── LLM calls ───────────────────────────────────────────────────

def call_openrouter(messages: list, model: str, api_key: str, max_tokens: int = 2000) -> str:
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
            "temperature": 0.4,
        },
        timeout=90,
    )
    d = r.json()
    if "error" in d:
        raise RuntimeError(f"OpenRouter error: {d['error']}")
    return d["choices"][0]["message"]["content"]


def parse_scores(response: str) -> dict:
    """Extract B1-B4 scores from evaluator response."""
    scores = {}
    for dim in ["B1", "B2", "B3", "B4"]:
        for line in response.split("\n"):
            if f"**{dim}" in line and dim not in scores:
                # Try patterns: "**: 2", "**: {2}", ": 2", etc.
                import re
                m = re.search(r'\*\*:\s*(\d)', line)
                if m:
                    scores[dim] = int(m.group(1))
                else:
                    # Fallback: find isolated digit
                    tokens = line.replace("*", " ").replace(":", " ").split()
                    for tok in tokens:
                        if tok in ("0", "1", "2"):
                            scores[dim] = int(tok)
                            break
    return scores


def extract_b5(response: str) -> dict:
    """Extract B5 uncertainty audit from response."""
    b5 = {"unverifiable": "", "missing": "", "misleading": ""}
    in_b5 = False
    for line in response.split("\n"):
        if "**B5" in line:
            in_b5 = True
            continue
        if in_b5:
            if "**Total" in line or "**Revision" in line:
                break
            if "Unverifiable" in line or "unverifiable" in line:
                b5["unverifiable"] = line.split(":", 1)[-1].strip().strip('"')
            elif "Missing" in line or "missing" in line:
                b5["missing"] = line.split(":", 1)[-1].strip().strip('"')
            elif "misleading" in line or "Potentially" in line:
                b5["misleading"] = line.split(":", 1)[-1].strip().strip('"')
    return b5


# ── Eval + Revise ───────────────────────────────────────────────

def blind_eval(paper, member, figure_path, agent_prompt, api_key, escalation_note=""):
    """Run blind evaluation for one paper × one member."""
    post_text = render_post_for_eval(paper)

    member_ctx = (
        f"You are {member['name']}, a researcher at CSNL.\n"
        f"Your research group focus: {member['group_focus']}\n"
        f"Your projects:\n"
    )
    for proj_name, proj_desc in member["projects"].items():
        member_ctx += f"  - {proj_name}: {proj_desc}\n"

    extra = ""
    if escalation_note:
        extra = f"\n\nADDITIONAL INSTRUCTION: {escalation_note}\n"

    messages = [
        {"role": "system", "content": agent_prompt + extra},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": f"{member_ctx}\n---\n\nYou see this post in Slack:\n\n{post_text}\n\nThe post includes this figure:"},
                {"type": "image_url", "image_url": {"url": encode_image_base64(figure_path)}},
                {"type": "text", "text": "\nEvaluate this post. Follow the output format exactly. Remember: default to 1, not 2. Score 2 means genuinely excellent."},
            ],
        },
    ]

    response = call_openrouter(messages, EVAL_MODEL, api_key, max_tokens=2000)
    scores = parse_scores(response)
    b5 = extract_b5(response)
    total = sum(scores.values()) if len(scores) == 4 else -1
    verdict = "PASS" if total >= PASS_THRESHOLD else ("REVISE" if total >= 4 else "FAIL")

    return {
        "paper": paper["name"],
        "member": member["name"],
        "scores": scores,
        "b5": b5,
        "total": total,
        "verdict": verdict,
        "response": response,
    }


def revise_post(paper, eval_results, api_key):
    """Auto-revise a post based on blind eval feedback. Uses ALL eval results."""
    post_text = render_post_for_eval(paper)

    # Combine feedback from all evaluators
    all_feedback = "\n\n---\n\n".join([
        f"### {e['member']} (score: {e['total']}/8)\n{e['response']}"
        for e in eval_results
    ])

    prompt = (
        "You are the Paper Scout Drafter. Revise this post based on ALL blind evaluators' feedback.\n\n"
        "RULES:\n"
        "- Fix every issue flagged by any evaluator\n"
        "- Address B5 uncertainty audit items where possible (add specificity)\n"
        "- Make summary MORE specific (numbers, mechanisms, comparisons)\n"
        "- Make :dart: lines actionable (what to DO this week, not what to think about)\n"
        "- Keep the same structure: {hook, summary, targeting_lines}\n"
        "- targeting_lines: [{slack_id, name, project, description}]\n"
        "- Korean for hook/summary/description, English for technical terms\n"
        "- Do NOT change: title, authors, journal, year, doi_url, dimension_tags, anchor_paper\n\n"
        f"CURRENT POST:\n{post_text}\n\n"
        f"ALL EVALUATOR FEEDBACK:\n{all_feedback}\n\n"
        "Output ONLY valid JSON with revised fields. No markdown fences, no explanation."
    )

    messages = [{"role": "user", "content": prompt}]
    response = call_openrouter(messages, REVISE_MODEL, api_key, max_tokens=2000)

    # Parse JSON
    text = response.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = text[:-3]
    if text.startswith("json"):
        text = text[4:]

    try:
        revisions = json.loads(text.strip())
    except json.JSONDecodeError:
        print(f"    ⚠ JSON parse failed, keeping original")
        return paper

    revised = copy.deepcopy(paper)
    for key in ("hook", "summary", "targeting_lines"):
        if key in revisions:
            revised[key] = revisions[key]
    return revised


# ── Main loop with auto-escalation ──────────────────────────────

def run_single_paper(paper, context_bundle, ranking, agent_prompt, api_key, max_rounds, escalation_note=""):
    """Run blind eval → revise loop for one paper."""
    fig_info = ranking.get(paper["name"], {})
    fig_path = fig_info.get("path", "")
    if fig_path and not Path(fig_path).is_absolute():
        fig_path = str(REPO_DIR / fig_path)
    if not fig_path or not Path(fig_path).exists():
        print(f"  ⚠ No figure for {paper['name']}")
        return {"paper": paper["name"], "verdict": "SKIP", "reason": "no_figure"}

    members = get_member_context(paper, context_bundle)
    if not members:
        return {"paper": paper["name"], "verdict": "SKIP", "reason": "no_members"}

    current = copy.deepcopy(paper)
    history = []

    for rnd in range(1, max_rounds + 1):
        print(f"\n  Round {rnd}/{max_rounds}")
        evals = []
        for m in members:
            print(f"    {m['name']}...", end=" ", flush=True)
            ev = blind_eval(current, m, fig_path, agent_prompt, api_key, escalation_note)
            evals.append(ev)
            sc = ev["scores"]
            print(f"B1={sc.get('B1','?')} B2={sc.get('B2','?')} B3={sc.get('B3','?')} B4={sc.get('B4','?')} → {ev['total']}/8 {ev['verdict']}")

        history.append({"round": rnd, "evals": evals, "paper_state": copy.deepcopy(current)})

        all_pass = all(e["verdict"] == "PASS" for e in evals)
        if all_pass:
            print(f"  ✅ PASS at round {rnd}")
            break

        if rnd < max_rounds:
            # Revise using all feedback (not just worst)
            failing = [e for e in evals if e["verdict"] != "PASS"]
            print(f"    Revising ({len(failing)} evaluator(s) flagged issues)...")
            current = revise_post(current, failing if failing else evals, api_key)
            # Show what changed
            for key in ("hook", "summary"):
                if current.get(key) != paper.get(key):
                    print(f"    Δ {key}: {current[key][:80]}...")

    final_evals = history[-1]["evals"]
    min_score = min(e["total"] for e in final_evals)
    all_pass = all(e["verdict"] == "PASS" for e in final_evals)

    return {
        "paper": current["name"],
        "final_verdict": "PASS" if all_pass else "REVISE",
        "min_score": min_score,
        "rounds": len(history),
        "final_paper": current,
        "history": history,
    }


def run_full_pipeline(papers, context_bundle, ranking, agent_prompt, api_key, max_rounds):
    """Run all papers with auto-escalation if evaluator is too lenient."""

    escalation_notes = [
        "",  # Level 0: normal
        "In this round, you must find at least ONE dimension that scores 1 or below. "
        "If you gave all 2s in a previous round, you were too lenient. "
        "Look harder at: (1) whether the summary gives NUMBERS not just claims, "
        "(2) whether the figure is truly self-explanatory without text, "
        "(3) whether the :dart: action is something you'd write in a to-do app.",

        "MAXIMUM STRICTNESS. You are the harshest reviewer in the lab. "
        "Score 2 means this is publication-quality science communication. "
        "Ask yourself: does this post make me smarter about a specific mechanism, "
        "or does it just tell me a paper exists? Does the figure SHOW the finding, "
        "or just ACCOMPANY the text? Could I rewrite the :dart: line myself more specifically? "
        "If yes to any, that dimension is 1 at most.",
    ]

    level = 0
    all_results = []

    while level < len(escalation_notes):
        note = escalation_notes[level]
        level_label = f"Level {level}" + (" (escalated)" if level > 0 else "")
        print(f"\n{'#'*60}")
        print(f"  EVALUATION {level_label}")
        print(f"{'#'*60}")

        results = []
        for paper in papers:
            print(f"\n{'='*60}")
            print(f"📄 {paper['name']}")
            print(f"{'='*60}")
            r = run_single_paper(paper, context_bundle, ranking, agent_prompt, api_key, max_rounds, note)
            results.append(r)

        # Check leniency
        scored = [r for r in results if r.get("min_score") is not None and r["min_score"] >= 0]
        if not scored:
            break

        avg_score = sum(r["min_score"] for r in scored) / len(scored)
        max_possible = 8
        leniency = avg_score / max_possible

        print(f"\n  Leniency check: avg={avg_score:.1f}/8, ratio={leniency:.2f}, threshold={LENIENCY_THRESHOLD}")

        if leniency > LENIENCY_THRESHOLD and level < len(escalation_notes) - 1:
            print(f"  ⚡ Evaluator too lenient (ratio {leniency:.2f} > {LENIENCY_THRESHOLD}). Escalating...")
            # Use revised papers from this round as input for next
            for r in results:
                if r.get("final_paper"):
                    for i, p in enumerate(papers):
                        if p["name"] == r["final_paper"]["name"]:
                            papers[i] = r["final_paper"]
            level += 1
        else:
            all_results = results
            break

    return all_results, level


def main():
    parser = argparse.ArgumentParser(description="Blind Evaluator Harness v2")
    parser.add_argument("--paper", type=str, help="Evaluate specific paper")
    parser.add_argument("--max-rounds", type=int, default=MAX_ROUNDS)
    args = parser.parse_args()

    creds = load_credentials()
    api_key = creds["openrouter_api_key"]
    context_bundle = load_context_bundle()
    ranking = load_ranking()
    agent_prompt = load_agent_prompt()
    papers = load_posts()

    if args.paper:
        papers = [p for p in papers if p["name"].lower() == args.paper.lower()]
        if not papers:
            print(f"Paper '{args.paper}' not found")
            sys.exit(1)

    results, final_level = run_full_pipeline(
        papers, context_bundle, ranking, agent_prompt, api_key, args.max_rounds
    )

    # Save
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = REPO_DIR / "harness" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Full results
    with open(out_dir / f"blind-eval-{timestamp}.json", "w") as f:
        json.dump(results, f, indent=2, default=str, ensure_ascii=False)

    # Summary
    summary = []
    for r in results:
        s = {
            "paper": r["paper"],
            "verdict": r.get("final_verdict", r.get("verdict")),
            "min_score": r.get("min_score"),
            "rounds": r.get("rounds"),
            "escalation_level": final_level,
        }
        if r.get("history"):
            s["scores_by_round"] = [
                {e["member"]: {"total": e["total"], **e["scores"]} for e in h["evals"]}
                for h in r["history"]
            ]
            # Extract B5 from last round
            s["b5_audit"] = [
                {"member": e["member"], **e.get("b5", {})}
                for e in r["history"][-1]["evals"]
            ]
        summary.append(s)

    with open(out_dir / f"blind-eval-{timestamp}.summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Save revised posts — merge into existing file (don't overwrite unrelated papers)
    revised = {r["final_paper"]["name"]: r["final_paper"] for r in results if r.get("final_paper")}
    if revised:
        existing_path = REPO_DIR / "runs" / "paper-scout-posts-v2-revised.json"
        if existing_path.exists():
            with open(existing_path) as f:
                all_papers = json.load(f)
            for i, p in enumerate(all_papers):
                if p["name"] in revised:
                    all_papers[i] = revised[p["name"]]
        else:
            all_papers = list(revised.values())
        rpath = save_posts(all_papers)
        print(f"\n📝 Revised posts: {rpath} ({len(revised)} updated, {len(all_papers)} total)")

    # Print summary
    print(f"\n{'='*60}")
    print(f"BLIND EVAL SUMMARY (escalation level: {final_level})")
    print(f"{'='*60}")
    for s in summary:
        icon = "✅" if s["verdict"] == "PASS" else "⚠️"
        print(f"  {icon} {s['paper']}: {s['verdict']} (min={s.get('min_score','?')}/8, rounds={s.get('rounds','?')})")
        if s.get("scores_by_round"):
            for i, sr in enumerate(s["scores_by_round"]):
                for member, scores in sr.items():
                    total = scores.pop("total", "?")
                    print(f"     R{i+1} {member}: {total}/8 {scores}")
        if s.get("b5_audit"):
            for b5 in s["b5_audit"]:
                if b5.get("missing"):
                    print(f"     B5 {b5['member']}: missing={b5['missing'][:60]}")


if __name__ == "__main__":
    main()
