#!/usr/bin/env python3
"""
Paper Scout Harness — Automated Fitness Evaluator
Usage:
    python run-harness.py eval-scan   outputs/paper-scout-candidates-2026-03-31.md
    python run-harness.py eval-score  outputs/paper-scout-scores-2026-03-31.md
    python run-harness.py eval-team   outputs/paper-scout-draft-2026-03-31.md
    python run-harness.py eval-safety outputs/paper-scout-draft-2026-03-31.md
    python run-harness.py eval-full   2026-03-31
    python run-harness.py dry-run
"""

import json
import re
import sys
import os
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_DIR / "runs"
RESULT_DIR = REPO_DIR / "harness" / "results"
EVALS_DIR = REPO_DIR / "harness" / "evals"
CONTEXT_BUNDLE = REPO_DIR / "data" / "context-bundle.json"

RESULT_DIR.mkdir(parents=True, exist_ok=True)

# --- Load context ---
with open(CONTEXT_BUNDLE) as f:
    CTX = json.load(f)

VALID_SLACK_IDS = set(CTX["slack"]["member_ids"].values())
MEMBER_ID_MAP = CTX["slack"]["member_ids"]
BANNED_TERMS = ["HSL", "김민아", "임채영"]
VALID_CHANNEL = "C06KJ95MGGZ"


def load_file(path: str) -> str:
    with open(path) as f:
        return f.read()


# --- E7: Safety Check ---
def eval_safety(content: str) -> dict:
    """Hard fail gate. Returns {pass, violations}."""
    violations = []

    for term in BANNED_TERMS:
        if term in content:
            violations.append(f"금지 멘션 감지: '{term}'")

    # Check Slack IDs
    slack_ids = re.findall(r"<@(U[A-Z0-9]+)>", content)
    for sid in slack_ids:
        if sid not in VALID_SLACK_IDS:
            violations.append(f"유효하지 않은 Slack ID: {sid}")

    # Check for P3/P4 mentions (broader pattern)
    if re.search(r"\bP3\b", content) and "P3" not in ["pattern"]:
        # Distinguish D3 pattern from P3 project
        p3_matches = re.findall(r"(?<!D)\bP3\b", content)
        if p3_matches:
            violations.append("P3 프로젝트 멘션 의심")

    if re.search(r"(?<!D)\bP4\b", content):
        violations.append("P4 프로젝트 멘션 의심")

    return {
        "pass": len(violations) == 0,
        "violations": violations,
    }


# --- E1: Structural Compliance ---
def eval_scan_structure(content: str) -> dict:
    """Check scan output structure."""
    issues = []
    score = 0
    total = 0

    # Check for DOIs
    dois = re.findall(r"10\.\d{4,}/[^\s]+", content)
    total += 1
    if dois:
        score += 1
    else:
        issues.append("DOI 패턴 없음")

    # Check for cosine scores
    cosines = re.findall(r"(?:cosine|cos|embedding)[:\s]*([0-9]\.[0-9]+)", content, re.I)
    total += 1
    if cosines:
        below_threshold = [float(c) for c in cosines if float(c) < 0.45]
        if below_threshold:
            issues.append(f"Threshold 미달 cosine 값: {below_threshold}")
        else:
            score += 1
    else:
        issues.append("Embedding cosine 값 없음")

    # Check for abstracts
    total += 1
    if re.search(r"(?:abstract|초록)", content, re.I):
        score += 1
    elif len(content) > 500:
        score += 1  # Likely has abstracts inline
    else:
        issues.append("Abstract 섹션 없음")

    # Check for required fields
    for field in ["title", "author", "journal"]:
        total += 1
        if re.search(field, content, re.I):
            score += 1
        else:
            issues.append(f"'{field}' 필드 없음")

    return {"score": score / total if total > 0 else 0, "issues": issues}


def eval_score_structure(content: str) -> dict:
    """Check score output structure."""
    issues = []
    checks_passed = 0
    total_checks = 0

    # D1-D5 presence
    for d in ["D1", "D2", "D3", "D4", "D5"]:
        total_checks += 1
        if d in content:
            checks_passed += 1
        else:
            issues.append(f"{d} 차원 없음")

    # Composite / max
    total_checks += 1
    if re.search(r"(?:composite|max|종합|최고)", content, re.I):
        checks_passed += 1
    else:
        issues.append("Composite score 표기 없음")

    # Quote evidence for >=7
    high_scores = re.findall(r"[D][1-5][:\s=]*([789]|10)", content)
    if high_scores:
        total_checks += 1
        if re.search(r'["\u201c\u201d]', content) or re.search(r"quote|인용|evidence", content, re.I):
            checks_passed += 1
        else:
            issues.append("D≥7 에 대한 quote 증거 없음")

    # Member names
    total_checks += 1
    members_found = sum(1 for m in MEMBER_ID_MAP if m in content)
    if members_found > 0:
        checks_passed += 1
    else:
        issues.append("멤버 이름 없음")

    return {"score": checks_passed / total_checks if total_checks > 0 else 0, "issues": issues}


def eval_team_structure(content: str) -> dict:
    """Check team/draft output structure."""
    issues = []
    checks = 0
    passed = 0

    # Hook (:fire:)
    checks += 1
    if ":fire:" in content:
        passed += 1
    else:
        issues.append(":fire: 훅 없음")

    # Targets (:dart:)
    checks += 1
    dart_count = content.count(":dart:")
    if dart_count > 0:
        passed += 1
    else:
        issues.append(":dart: 타겟팅 라인 없음")

    # Labels (:label:)
    checks += 1
    if ":label:" in content:
        passed += 1
    else:
        issues.append(":label: 차원 태그 없음")

    # Slack IDs
    checks += 1
    slack_ids = re.findall(r"<@U[A-Z0-9]+>", content)
    if slack_ids:
        passed += 1
    else:
        issues.append("Slack ID 없음")

    # DOI link
    checks += 1
    if ":link:" in content or "doi.org" in content or "10." in content:
        passed += 1
    else:
        issues.append("DOI 링크 없음")

    # Verdict log
    checks += 1
    verdict_keywords = ["PASS", "REWRITE", "FIX", "KEEP", "STRENGTHEN", "POLISHED"]
    if any(kw in content for kw in verdict_keywords):
        passed += 1
    else:
        issues.append("Verdict 로그 없음")

    # Korean content
    checks += 1
    korean = re.findall(r"[\uac00-\ud7a3]", content)
    if len(korean) > 10:
        passed += 1
    else:
        issues.append("한국어 컨텐츠 부족")

    return {"score": passed / checks if checks > 0 else 0, "issues": issues}


# --- E4: Hook Effectiveness ---
def eval_hook(content: str) -> dict:
    """Evaluate hook quality."""
    # Extract hook line (after :fire:)
    hook_match = re.search(r":fire:\s*(.+?)(?:\n\n|\n\*)", content, re.DOTALL)
    if not hook_match:
        return {"score": 0, "issues": ["Hook 추출 실패"]}

    hook = hook_match.group(1).strip()
    checks = 8
    passed = 0
    issues = []

    # 1. Specific member/project mention
    member_mentioned = any(m in hook for m in MEMBER_ID_MAP)
    project_keywords = ["RingRepSca", "CatVsMag", "RNN", "SeqVWM", "WMRepresentation",
                        "SpatialExtent", "FC_orientation", "Concentricity", "V1toPercept"]
    project_mentioned = any(p in hook for p in project_keywords)
    if member_mentioned or project_mentioned:
        passed += 1
    else:
        issues.append("특정 멤버/프로젝트 미언급")

    # 2. Finding (not topic)
    vague = ["연구", "에 대한", "관련된", "관한"]
    if not any(v in hook for v in vague) or len(hook) > 30:
        passed += 1
    else:
        issues.append("주제만 전달, 발견 미전달")

    # 3. Not title repeat (heuristic: hook != title)
    passed += 1  # Hard to check without title, give benefit

    # 4. No vague praise
    vague_praise = ["흥미로운", "중요한", "놀라운", "획기적인"]
    if not any(v in hook for v in vague_praise):
        passed += 1
    else:
        issues.append("모호한 칭찬 포함")

    # 5. No journal name leading
    journals = ["Nature", "Science", "Neuron", "PNAS", "bioRxiv", "NeuroImage"]
    if not any(hook.startswith(j) for j in journals):
        passed += 1
    else:
        issues.append("저널명 선행")

    # 6. Pattern matching (need scores to verify — give benefit)
    passed += 1

    # 7. Length
    if len(hook) <= 120:
        passed += 1
    else:
        issues.append(f"Hook 길이 초과: {len(hook)}자")

    # 8. Korean
    if re.search(r"[\uac00-\ud7a3]", hook):
        passed += 1
    else:
        issues.append("한국어 아님")

    return {"score": passed / checks, "hook_text": hook, "issues": issues}


# --- Composite Fitness ---
def compute_fitness(e1, e2_est, e3_est, e4, e5_est, e6_est, e7) -> dict:
    """
    Compute weighted fitness score.
    e2, e3, e5, e6 are estimated (require manual/LLM verification for full accuracy).
    """
    if not e7["pass"]:
        return {"total": 0.0, "grade": "F", "reason": f"Safety FAIL: {e7['violations']}"}

    total = (
        e1 * 0.15 +
        e2_est * 0.20 +
        e3_est * 0.20 +
        e4 * 0.10 +
        e5_est * 0.15 +
        e6_est * 0.10 +
        1.0 * 0.10  # E7 pass = 1.0
    )

    if total >= 0.85:
        grade = "A"
    elif total >= 0.70:
        grade = "B"
    elif total >= 0.55:
        grade = "C"
    elif total >= 0.40:
        grade = "D"
    else:
        grade = "F"

    return {"total": round(total, 3), "grade": grade}


# --- Report Generator ---
def generate_report(phase: str, results: dict, filepath: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    report = f"""# Paper Scout Harness Report — {today}

## Phase: {phase}
## File: {filepath}

## Safety (E7)
- **Status:** {"PASS" if results['e7']['pass'] else "FAIL"}
- **Violations:** {results['e7']['violations'] if results['e7']['violations'] else "None"}

## Structural Compliance (E1)
- **Score:** {results['e1']['score']:.2f}
- **Issues:** {results['e1']['issues'] if results['e1']['issues'] else "None"}

"""
    if "e4" in results:
        report += f"""## Hook Effectiveness (E4)
- **Score:** {results['e4']['score']:.2f}
- **Hook:** {results['e4'].get('hook_text', 'N/A')}
- **Issues:** {results['e4']['issues'] if results['e4']['issues'] else "None"}

"""

    if "fitness" in results:
        report += f"""## Fitness Summary
- **Total Score:** {results['fitness']['total']}
- **Grade:** {results['fitness']['grade']}
"""
        if "reason" in results["fitness"]:
            report += f"- **Reason:** {results['fitness']['reason']}\n"

    report += f"""
## Notes
- E2 (Semantic), E3 (Targeting), E5 (Convergence), E6 (Coherence)는 LLM 기반 심층 평가 필요.
- 이 리포트는 자동화 가능한 구조적/안전성 검증 결과입니다.
- 전체 평가는 `claude -p "paper scout harness eval-full"` 로 실행하세요.

## Issues Summary
"""
    all_issues = results["e1"]["issues"] + results["e7"]["violations"]
    if "e4" in results:
        all_issues += results["e4"]["issues"]

    if all_issues:
        for i, issue in enumerate(all_issues, 1):
            report += f"{i}. {issue}\n"
    else:
        report += "No issues found.\n"

    return report


# --- CLI ---
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    today = datetime.now().strftime("%Y-%m-%d")

    if cmd == "eval-scan":
        filepath = sys.argv[2] if len(sys.argv) > 2 else str(OUTPUT_DIR / f"paper-scout-candidates-{today}.md")
        content = load_file(filepath)
        results = {
            "e1": eval_scan_structure(content),
            "e7": eval_safety(content),
        }
        results["fitness"] = compute_fitness(
            results["e1"]["score"], 0.7, 0.7, 0.7, 0.7, 0.7, results["e7"]
        )
        report = generate_report("Scan", results, filepath)

    elif cmd == "eval-score":
        filepath = sys.argv[2] if len(sys.argv) > 2 else str(OUTPUT_DIR / f"paper-scout-scores-{today}.md")
        content = load_file(filepath)
        results = {
            "e1": eval_score_structure(content),
            "e7": eval_safety(content),
        }
        results["fitness"] = compute_fitness(
            results["e1"]["score"], 0.7, 0.7, 0.7, 0.7, 0.7, results["e7"]
        )
        report = generate_report("Score", results, filepath)

    elif cmd == "eval-team":
        filepath = sys.argv[2] if len(sys.argv) > 2 else str(OUTPUT_DIR / f"paper-scout-draft-{today}.md")
        content = load_file(filepath)
        results = {
            "e1": eval_team_structure(content),
            "e4": eval_hook(content),
            "e7": eval_safety(content),
        }
        results["fitness"] = compute_fitness(
            results["e1"]["score"], 0.7, 0.7,
            results["e4"]["score"], 0.7, 0.7, results["e7"]
        )
        report = generate_report("Team/Draft", results, filepath)

    elif cmd == "eval-safety":
        filepath = sys.argv[2]
        content = load_file(filepath)
        results = {
            "e1": {"score": 1.0, "issues": []},
            "e7": eval_safety(content),
        }
        results["fitness"] = compute_fitness(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, results["e7"])
        report = generate_report("Safety", results, filepath)

    elif cmd == "eval-full":
        date = sys.argv[2] if len(sys.argv) > 2 else today
        report = f"# Paper Scout Full Pipeline Eval — {date}\n\n"
        phases = {
            "scan": f"paper-scout-candidates-{date}.md",
            "score": f"paper-scout-scores-{date}.md",
            "team": f"paper-scout-draft-{date}.md",
        }
        all_ok = True
        for phase, fname in phases.items():
            fpath = OUTPUT_DIR / fname
            if fpath.exists():
                content = load_file(str(fpath))
                safety = eval_safety(content)
                if not safety["pass"]:
                    all_ok = False
                if phase == "scan":
                    e1 = eval_scan_structure(content)
                elif phase == "score":
                    e1 = eval_score_structure(content)
                else:
                    e1 = eval_team_structure(content)
                report += f"## {phase.upper()}\n- E1: {e1['score']:.2f}\n- E7: {'PASS' if safety['pass'] else 'FAIL'}\n- Issues: {e1['issues']}\n\n"
            else:
                report += f"## {phase.upper()}\n- FILE NOT FOUND: {fname}\n\n"

        report += f"\n## Overall Safety: {'PASS' if all_ok else 'FAIL'}\n"

    elif cmd == "dry-run":
        tc_file = EVALS_DIR / "test-cases.json"
        with open(tc_file) as f:
            test_cases = json.load(f)
        report = f"# Paper Scout Harness Dry Run — {today}\n\n"
        report += f"## Test Cases: {len(test_cases)}\n\n"
        for tc in test_cases:
            report += f"### {tc['id']}: {tc['name']}\n"
            report += f"- Phase: {tc['phase']}\n"
            report += f"- Description: {tc['description']}\n"

            if tc["phase"] == "safety" and "mock_draft" in tc["input"]:
                safety = eval_safety(tc["input"]["mock_draft"])
                expected_pass = tc["expected"]["safety_pass"]
                match = safety["pass"] == expected_pass
                report += f"- Safety Result: {'PASS' if safety['pass'] else 'FAIL'}\n"
                report += f"- Expected: {'PASS' if expected_pass else 'FAIL'}\n"
                report += f"- **{'MATCH' if match else 'MISMATCH'}**\n"
                if safety["violations"]:
                    report += f"- Violations: {safety['violations']}\n"
            else:
                report += f"- Status: READY (requires Claude Code execution for full eval)\n"
                report += f"- Expected fitness: ≥{tc['expected'].get('min_fitness', 'N/A')}\n"
                if "key_checks" in tc["expected"]:
                    for check in tc["expected"]["key_checks"]:
                        report += f"  - [ ] {check}\n"

            report += "\n"
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    # Save report
    result_file = RESULT_DIR / f"eval-{cmd}-{today}.md"
    with open(result_file, "w") as f:
        f.write(report)

    print(report)
    print(f"\n--- Report saved to {result_file} ---")


if __name__ == "__main__":
    main()
