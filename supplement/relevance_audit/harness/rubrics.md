---
name: relevance-audit-harness
description: Relevance Audit 품질 검증 rubric
---

# Relevance Audit Harness Rubrics

## H1: Precision (제거 정확도)
> 제거 대상으로 판정된 논문이 정말 CSNL과 무관한가?

- 방법: TRASH 판정 논문 중 랜덤 20건 수동 검증
- 기준: True Positive Rate ≥ 0.95
- False Positive (잘못 제거): 관련 논문인데 TRASH 판정
- 측정: `precision = true_irrelevant / total_trash`

## H2: Recall (포착율)
> 무관한 논문이 KEEP으로 남아있지 않은가?

- 방법: Task A + Task B 결합으로 보완
  - Task A: embedding distance로 수학적 이상치 포착
  - Task B: LLM 추론으로 embedding이 못 잡는 동명이인/분야 혼동 포착
- 보완 검증: KEEP 판정 논문 중 랜덤 20건 역검증
- 기준: False Negative Rate ≤ 0.05

## H3: Judge Agreement (판사 일치율)
> 3명의 독립 판사가 얼마나 일치하는가?

- 방법: 전체 판결에 대한 일치율 계산
- 기준:
  - 만장일치 비율 ≥ 0.60 (양호)
  - 평균 일치율 ≥ 0.75 (Fleiss' kappa 근사)
- 낮은 일치율 → prompt 개선 또는 판단 기준 명확화 필요

## H4: False Positive Audit (역검증)
> KEEP으로 남은 논문 중 실제로 무관한 것이 있는가?

- 방법: KEEP 판정 논문 중 하위 cosine similarity 20건 수동 검증
- 기준: 무관 논문 발견 시 Task B threshold 조정

## Harness Report Format

```markdown
# Relevance Audit Harness Report — {DATE}

## Summary
| Metric | Value | Grade |
|--------|-------|-------|
| H1 Precision | X/1.0 | PASS/WARN/FAIL |
| H2 Recall (complementary) | Task A+B coverage | PASS/WARN |
| H3 Judge Agreement | X.XX | PASS/WARN/FAIL |
| H4 False Positive Audit | X/20 clean | PASS/WARN/FAIL |

## Task A Results
- Outlier threshold: {cosine value}
- Candidates flagged: N
- After verification: N TRASH, N KEEP

## Task B Results
- Papers screened: N
- Candidates flagged: N
- After verification: N TRASH, N KEEP

## Judge Verdict Distribution
| Verdict Pattern | Count | % |
|----------------|-------|---|
| 3/3 IRRELEVANT | N | X% |
| 2/3 IRRELEVANT | N | X% |
| 3/3 RELEVANT | N | X% |
| Mixed | N | X% |

## Manual Verification Sample
[20건 랜덤 샘플 결과]
```
