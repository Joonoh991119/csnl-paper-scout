---
name: paper-scout-review
description: "Phase 4 of CSNL Paper Scout pipeline (v2): Optional peer review after paper-scout-team has already evaluated and converged on candidate papers. Use when you want an additional external group-perspective review layer, or when paper scores are borderline (7-8 range). Triggers on: 'peer review', 'group review', 'additional review', 'cross-check papers', 'paper scout review', '피어 리뷰', 'check recommendations', 'quality check posts'."
---

# Paper Scout — Phase 4 (v2): Optional Peer Review

**NOTE**: paper-scout-team already includes 4 evaluator agents (Hook evaluator, Visual evaluator, Accuracy evaluator, Member Advocate) with an integrated feedback loop. This skill is for additional group-perspective review **AFTER the team has converged**, or when the user explicitly asks for deeper peer review.

Quality-check team verdict through 3 group-perspective agents that simulate how each research subgroup would independently validate the team's recommendations.

## Prerequisites

1. Load context bundle: `../.skills/skills/paper-scout/context-bundle.json`
2. Load enriched contexts: `paper-scout-enriched-contexts-v3.md`
3. Load team verdict: `paper-scout-team-draft-[DATE].md` (contains Team Verdict Log)

## When to Use This Skill

- **User explicitly requests** peer review after team drafting is complete
- **Paper scores are borderline** (7-8 range): need additional validation beyond team consensus
- **Paper spans multiple groups**: touches on JOP, RNN/WM, and visual cortex work — needs cross-group check
- **NOT needed for clear-cut high scores** (9+): papers that passed team review cleanly don't require this additional layer
- **Team feedback loop raised concerns**: the Team Verdict Log shows disagreement between evaluators — external group review can break ties

## Review Architecture

Launch 3 group agents in **parallel** (use Agent tool). Each reviews ALL team verdicts from their group's perspective, with specific attention to the feedback loop log.

### Group A Agent (JOP + MSY perspective)

**Expertise**: Bayesian observer models, serial dependence, history effects, magnitude normalization, CDF-based representation, gambler's fallacy

**Reviews from the angle of**: 
- Would someone deeply embedded in Bayesian estimation and serial dependence research find this recommendation genuinely useful? 
- Is the connection to our specific computational framework (BMBU, DV space belief dynamics, CDF normalization) substantive?
- Does the team's accuracy evaluator assessment align with what JOP-focused expert would expect?

### Group B Agent (JYK + MJC + SK perspective)

**Expertise**: RNN modeling, WM representation, attractor dynamics, neural geometry, orthogonal subspaces, drift-diffusion, dPCA, energy landscape

**Reviews from the angle of**: 
- Does this paper's computational or neural approach actually speak to our RNN/WM work? 
- Is the claimed connection to attractor dynamics or neural coding mechanistic or just at the level of shared buzzwords?
- Did the team's hook evaluator correctly assess appeal to WM researchers?

### Group C Agent (JHR + SMJ perspective)

**Expertise**: Visual cortex architecture, pRF anisotropy, orientation-specific FC, natural image statistics, contour integration, oculomotor strategies, V1-to-percept transformation

**Reviews from the angle of**: 
- Is the paper's relevance to visual cortex work genuine? 
- Does it connect to our specific questions about radial/co-axial transformation, or is it just "another vision paper"?
- Is the visual component secondary or central to the paper's contribution?

## Review Criteria

Each agent critiques every team verdict on:

1. **Team feedback alignment**: Does the Team Verdict Log show any concerning patterns? (e.g., accuracy agent passed but group expert strongly disagrees)
2. **Justification accuracy**: Is the recommendation justified or overstated? Are claims grounded in what the abstract actually says?
3. **Connection depth**: Is the connection to CSNL substantive or superficial? Does it go beyond shared topic area to shared intellectual approach?
4. **Cross-Check consistency**: Are there internal inconsistencies between different evaluator assessments in the team log?
5. **Tagging appropriateness**: Should any tagged member NOT be tagged? Should anyone be added based on group expertise?
6. **Verdict**: APPROVE / MODIFY (with specific edit) / ESCALATE-FOR-TEAM-REASSESSMENT (if team log shows red flags)

## Agent Prompt Template

```
You are reviewing CSNL Paper Scout team verdicts from the perspective of [Group X].

Your expertise covers: [group expertise list]
Members you represent: [member names and their projects]

Load the Team Verdict Log from the source file and examine:
1. Did the 4 evaluators (Hook, Visual, Accuracy, Member Advocate) converge or diverge?
2. Are there any concerning patterns (e.g., one evaluator flagged high concern but others passed)?

For each team verdict below, evaluate:
1. Does the team's feedback log show patterns your group would find concerning?
2. Is the recommendation justified or overstated?
3. Is the CSNL connection substantive or superficial?
4. Any methodological concerns from your group's perspective?
5. Tagging: anyone who shouldn't be tagged, or someone missing?
6. Verdict: APPROVE / MODIFY (specific edit) / ESCALATE-FOR-TEAM-REASSESSMENT (reason)

Be conservative. False positives waste lab members' time and erode trust in the system.

[Team verdict + feedback log]
```

## Applying Review Results

After collecting all 3 group reviews:

1. **ESCALATE**: If 2+ groups vote ESCALATE, send back to paper-scout-team with highlighted concerns. The team may refine their verdict or gather additional evidence.
2. **REMOVE**: If 2+ groups vote MODIFY with intent to remove, drop the paper. Replace with next-highest scorer from Phase 2.
3. **MODIFY**: Apply conservative edits — remove overstatements, add caveats, fix tagging.
4. **APPROVE**: Keep as-is.
5. **Conflict resolution**: If groups disagree (e.g., Group A says APPROVE, Group B says MODIFY), favor the group whose expertise is most relevant to the paper's topic. If still unresolved, escalate to user for final call.

## Output Format

Save to `paper-scout-review-[YYYY-MM-DD].md`:

```markdown
# Paper Scout Peer Review (v2) — [DATE]

## Review Summary

| Paper | Group A | Group B | Group C | Final Verdict |
|-------|---------|---------|---------|---------------|
| 1 | APPROVE | MODIFY | APPROVE | MODIFIED |
| 2 | APPROVE | APPROVE | APPROVE | APPROVED |
| 3 | ESCALATE | ESCALATE | MODIFY | ESCALATED TO TEAM |

## Detailed Reviews

### Paper [N]: [Title]

**Team Verdict**: [verdict from paper-scout-team draft]

**Team Feedback Log Key Points**: 
- Hook evaluator: [summary]
- Accuracy evaluator: [summary]
- Any divergence noted: [yes/no + explanation]

**Group A**: [verdict + reasoning]
**Group B**: [verdict + reasoning]
**Group C**: [verdict + reasoning]

**Applied changes**: [what was modified, or "none"]

---

## Summary Stats

- Approved: [N]
- Modified: [M]
- Escalated back to team: [K]
- Removed: [P]
```

## Handoff

After review, tell the user:

If no escalations:
> "피어 리뷰 완료: [N]편 승인, [M]편 수정, [P]편 교체. 최종 포스트를 확인 후 `paper-scout-post` 스킬로 게시할 수 있습니다."

If escalations occurred:
> "피어 리뷰 완료: [K]편이 팀 재검토가 필요합니다. 팀의 피드백 로그에 그룹 전문가의 우려사항을 포함하여 `paper-scout-team`을 다시 실행할까요?"
