# E5: Agent Convergence — 에이전트 수렴성

## 원칙
6-agent 팀은 **최소 라운드**에서 **구체적 피드백**으로 수렴해야 한다.

## Metrics

### M1: Iteration Count
| Rounds | Score | Interpretation |
|--------|-------|---------------|
| 1 | 3 | 최적 — 1라운드 전원 PASS |
| 2 | 2 | 정상 — 1라운드 피드백 → 2라운드 수렴 |
| 3 | 1 | 경고 — 최대 라운드까지 소요 |
| >3 / stalemate | 0 | 실패 — 미수렴 |

### M2: First-Round Pass Rate
```
pass_rate_r1 = (PASS agents in round 1) / (total evaluator agents)
```
- Evaluators: Hook, Visual, Accuracy, Member Advocate (4개)
- Final Editor는 제외 (항상 마지막에 실행)

| Rate | Interpretation |
|------|---------------|
| 4/4 (1.0) | 완벽 — 즉시 수렴 |
| 3/4 (0.75) | 양호 — 1개 에이전트만 수정 필요 |
| 2/4 (0.50) | 보통 — 반수 수정 필요 |
| 1/4 (0.25) | 문제 — 초기 드래프트 품질 낮음 |
| 0/4 (0.00) | 심각 — 전면 재작성 |

### M3: Feedback Specificity
각 REWRITE/FIX/STRENGTHEN 피드백의 구체성:

| Score | Criteria | Example |
|-------|----------|---------|
| 2 | 구체적 수정 지시 + 대안 제시 | "REWRITE: 'WM 관련'을 'SK의 orthogonal subspace 가설에 직접 증거'로 변경" |
| 1 | 문제 지적만 (대안 없음) | "Hook이 충분히 구체적이지 않음" |
| 0 | 모호한 불만 | "좀 더 좋게 해주세요" |

### M4: Revision Effectiveness
라운드 N의 수정이 라운드 N-1의 피드백을 실제로 해결했는가?

```
effectiveness = (resolved_issues / total_issues_from_previous_round)
```

## Composite E5 Score
```
E5_raw = (M1 / 3) × 0.4 + pass_rate_r1 × 0.2 + mean(M3) / 2 × 0.2 + M4 × 0.2
E5_score = E5_raw  # already 0-1
```

## Diagnostic Patterns

| Pattern | Diagnosis | Action |
|---------|-----------|--------|
| M1=3, M2=0 → stalemate | 에이전트 간 충돌 (모순 피드백) | 에이전트 rubric 조정 |
| M1=1, M3 low | 좋은 초기 드래프트지만 피드백이 vague | 피드백 template 개선 |
| M1=3, M4 low | 수렴은 했으나 이전 피드백 미반영 | Drafter의 revision 프로토콜 강화 |
| M2=0, M1=1 | 모든 에이전트가 문제 발견 → 즉시 수렴 | 이상적. 고품질 피드백 |
