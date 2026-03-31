---
name: paper-scout-team
description: >
  CSNL Paper Scout drafting team orchestrator. Replaces separate draft (Phase 3) and review (Phase 4)
  with a unified multi-agent team + feedback loop. 6 specialized agents collaborate to produce
  verified Slack posts. Triggers on: 'draft team', 'paper scout team', '논문 포스트 팀', 'team draft',
  '드래프팅 팀', '포스트 생성', 'create posts', 'generate posts'. Use after paper-scout-score.
---

# Paper Scout — Team Drafting & Review Orchestrator

Replace sequential draft → review with a parallel team of 6 specialized agents and an iterative
feedback loop. The team produces posts that are verified from multiple angles before output.

## Why a Team, Not a Pipeline

The old flow: Drafter writes → 3 built-in reviewers check → 3 group-perspective reviewers check.
Problems: (1) built-in review is self-review (same context, same blind spots), (2) group review
happens too late to reshape the post, (3) no iteration — feedback is noted but not applied and re-checked.

The team model: 6 independent agents each own a quality dimension. The orchestrator runs them in parallel,
aggregates feedback, and iterates until convergence or max rounds. Every agent sees revisions from
previous rounds, preventing drift.

## Prerequisites

1. Scoring results: `paper-scout-scores-[DATE].md`
2. Enriched contexts: `paper-scout-enriched-contexts-v3.md`
3. Context bundle: `../paper-scout/context-bundle.json`
4. paper-scout-embed.py utility (for Visual Agent)
5. Chrome MCP or WebFetch (for figure/equation extraction)
6. Full paper access (DOI URLs)

## Team Architecture

```
                    ┌─────────────────┐
                    │  ORCHESTRATOR   │
                    │  (this skill)   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  DRAFTER AGENT  │
                    │  (initial post) │
                    └────────┬────────┘
                             │ draft v1
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼─────┐ ┌──────▼────────┐
     │ HOOK EVALUATOR│ │ VISUAL   │ │ ACCURACY      │
     │ (3-sec test)  │ │ AGENT    │ │ EVALUATOR     │
     └────────┬──────┘ └────┬─────┘ └──────┬────────┘
              │              │              │
     ┌────────▼──────┐ ┌────▼─────────────▼────────┐
     │ MEMBER        │ │     FEEDBACK AGGREGATOR   │
     │ ADVOCATE      │ │  (merge all verdicts)     │
     └────────┬──────┘ └────────────┬──────────────┘
              │                     │
              └──────────┬──────────┘
                         │
                    ┌────▼────┐
                    │ ALL     │──── Yes ──→ FINAL EDITOR → OUTPUT
                    │ PASS?   │
                    └────┬────┘
                         │ No (+ specific feedback)
                         │
                    ┌────▼────────────┐
                    │ DRAFTER AGENT   │
                    │ (revision v2)   │── loop back (max 3 rounds)
                    └─────────────────┘
```

## Agent Definitions

### Agent 1 — Drafter
**Role**: Generate the initial Slack post (or revise based on feedback).
**Input**: Paper metadata + scores + member contexts + (on revision) specific feedback from evaluators.
**Output**: Complete Slack post block.
**Prompt file**: `agents/drafter.md`

### Agent 2 — Hook Evaluator
**Role**: Judge if the first line passes the 3-second test.
**Criteria**:
- Does a busy researcher know within 3 seconds if this paper matters to them?
- Is a specific member/project/hypothesis mentioned?
- Is it NOT: title repetition, vague praise, journal-name-as-hook?
- Pattern match check: which of the 5 hook patterns was used? Is it the right one for the dominant dimension?
**Verdict**: PASS / REWRITE(reason, suggestion)
**Prompt file**: `agents/hook_evaluator.md`

### Agent 3 — Visual Agent
**Role**: Extract, evaluate, and rank visual elements (figures, equations).
**Steps**:
1. Navigate to paper URL via Chrome MCP or WebFetch
2. Extract all figure URLs + any LaTeX/MathJax equations
3. Embed figures via `embed_image()` from paper-scout-embed.py
4. Rank figures by cosine similarity to each tagged member's project description
5. Select best figure + decide if equation inclusion is warranted
**Verdict**: PASS(figure_url, cosine_score) / REPLACE(better_figure_url, reason) / ADD_EQUATION(equation, explanation)
**Prompt file**: `agents/visual_agent.md`

### Agent 4 — Accuracy Evaluator
**Role**: Verify all claims against the paper's abstract.
**Checks**:
- Every factual claim in the post → traceable to abstract text?
- Slack IDs → match context-bundle.json?
- Project names → match enriched-contexts-v3.md?
- Score dimensions → match paper-scout-scores file?
- No overstated connections (specificity test)
- No hallucinated findings
**Verdict**: PASS / FIX(claim, correction)
**Prompt file**: `agents/accuracy_evaluator.md`

### Agent 5 — Member Advocate
**Role**: Simulate each tagged member's reaction. "Would I actually stop scrolling for this?"
**For each tagged member**:
- Load their full project description
- Load their reading profile (recurring_authors, research_themes)
- Ask: "Given my current research focus and what I'm working on RIGHT NOW, does this post give me something actionable?"
- Check: Is the :dart: line specific enough that I know what to do? (Read the paper? Change my model? Check a competing result?)
**Verdict per member**: KEEP / REMOVE_TAG(reason) / STRENGTHEN(suggestion)
**Prompt file**: `agents/member_advocate.md`

### Agent 6 — Final Editor
**Role**: Polish the final draft after all evaluators pass.
**Checks**:
- Korean/English consistency (Korean for recommendations, English for citations)
- Tone: declarative, no rhetorical questions, no vague praise
- Emoji: only :fire: :dart: :link: :label: — nothing else
- Length: hook ≤ 2 lines, targeting ≤ 200 chars per member, total post ≤ 500 words
- Formatting: mrkdwn compatibility for Slack
**Verdict**: POLISHED(final_text) — always produces output
**Prompt file**: `agents/final_editor.md`

## Orchestration Protocol

### Round 1: Initial Draft

1. **Orchestrator** loads paper data from scores file
2. **Orchestrator** spawns **Drafter Agent** with paper metadata + member contexts
3. Drafter produces `draft_v1`

### Round 1: Parallel Evaluation

4. **Orchestrator** spawns in parallel (all receive `draft_v1`):
   - Hook Evaluator
   - Visual Agent (also receives paper URL for figure extraction)
   - Accuracy Evaluator
   - Member Advocate

5. Collect all verdicts into `feedback_v1`:
   ```
   {
     "hook": {"verdict": "REWRITE", "reason": "...", "suggestion": "..."},
     "visual": {"verdict": "REPLACE", "better_figure": "...", "equation": "..."},
     "accuracy": {"verdict": "FIX", "fixes": [...]},
     "member_advocate": {"U06JA7D5XC7": "KEEP", "U06K5MX4GHE": "STRENGTHEN(...)", ...}
   }
   ```

### Round N: Revision (if any agent ≠ PASS)

6. **Orchestrator** formats feedback into structured revision instructions
7. **Orchestrator** spawns **Drafter Agent** with `draft_v(N-1)` + `feedback_v(N-1)`
8. Drafter produces `draft_vN`
9. **Re-run only the agents that didn't pass** (optimization: skip already-passed agents)
10. Repeat until all PASS or max_iterations (3) reached

### Final: Polish & Output

11. On all-PASS, spawn **Final Editor** with the converged draft
12. Final Editor returns polished post
13. Orchestrator saves to `paper-scout-draft-[DATE].md`

### Convergence Rules

- **Max iterations**: 3 (from context-bundle.json `drafting_team.feedback_loop.max_iterations`)
- **Early exit**: All agents PASS on first round → skip to Final Editor
- **Stalemate**: If iteration 3 still has failures, output the best version with warnings attached
- **Per-post**: Each paper gets its own independent feedback loop (no cross-contamination)

## Feedback Format

When an evaluator fails a post, it must provide **actionable, specific** feedback:

**Bad feedback**: "The hook is not specific enough"
**Good feedback**: "REWRITE: Hook mentions 'WM representation' but doesn't name SK or WMRepresentation project. Suggestion: '메모리 표상의 드리프트가 V3AB에서 V1으로 하향 전파된다 — SK의 orthogonal subspace 가설에 직접 증거'"

**Bad feedback**: "The accuracy could be improved"
**Good feedback**: "FIX: Post claims 'Fig 3에서 repulsive bias 소멸' but abstract only mentions 'drift toward errors'. Remove Fig 3 reference; replace with abstract quote 'shifted progressively toward memory-report errors'."

## Output Format

Save to: `paper-scout-draft-[YYYY-MM-DD].md`

```markdown
# CSNL Paper Scout — [DATE] Team Draft

## Generation Summary
- Papers processed: [N]
- Total iterations: [N per paper]
- Convergence: [all converged / N stalemates]

---

## Post 1 of [N] (Score: X — DY [DimName])

[Final polished Slack post]

### Team Verdict Log
| Agent | Round 1 | Round 2 | Round 3 | Final |
|-------|---------|---------|---------|-------|
| Hook | REWRITE | PASS | — | PASS |
| Visual | REPLACE | PASS | — | PASS |
| Accuracy | PASS | — | — | PASS |
| Member Advocate | STRENGTHEN(SK) | PASS | — | PASS |
| Final Editor | — | — | — | POLISHED |

### Iteration History
**v1 → v2 changes**: [what Drafter revised based on Round 1 feedback]
**v2 → final**: [Final Editor polish notes]

---
```

## Handoff

> "팀 드래프팅 완료: [N]편, 총 [M]회 피드백 루프. 모든 에이전트 합격. `paper-scout-post`로 게시하시겠습니까?"
