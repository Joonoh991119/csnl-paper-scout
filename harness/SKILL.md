---
name: paper-scout-harness
description: Paper Scout 파이프라인 적합성 평가 하네스. 5단계(Scan→Score→Team→Review→Post) 각각의 출력물을 구조적으로 검증하고, 에이전트 수렴성, 의미적 정확성, 멤버 타겟팅 품질, Slack 배포 준비도를 종합 평가한다.
license: Internal
metadata:
  skill-author: CSNL
  version: "1.0"
---

# Paper Scout Harness — 워크플로우 적합성 평가

## Overview

Paper Scout 파이프라인의 **각 단계별 출력물**을 체계적으로 검증하고, **end-to-end 워크플로우**의 적합성(fitness)을 정량 평가한다.

평가 대상:
1. **Phase Fitness** — 각 단계의 출력이 스펙에 부합하는가
2. **Pipeline Coherence** — 단계 간 데이터 전달이 무손실인가
3. **Agent Convergence** — 멀티에이전트 피드백 루프가 수렴하는가
4. **Semantic Grounding** — 추천이 CSNL 연구와 의미적으로 연결되는가
5. **Deployment Readiness** — Slack 게시 준비 상태인가

## Evaluation Dimensions

### E1: Structural Compliance (구조 적합성)
각 단계의 출력 파일이 명시된 포맷을 준수하는가.

| Phase | Required Fields | Pass Criteria |
|-------|----------------|---------------|
| Scan | title, authors, journal, DOI, abstract, semantic_distance, embedding_cosine | 모든 필드 존재 + cosine ≥ 0.45 |
| Score | D1-D5 per member, composite, reasoning, quote(≥7) | 5차원 완전 + ≥7 인용 존재 |
| Team | draft_text, hook, targets, label, verdict_log | 모든 에이전트 verdict 기록 |
| Review | group_verdicts(A/B/C), final_verdict | 3그룹 verdict 존재 |
| Post | channel_id, message_text, member_ids | C06KJ95MGGZ + valid IDs |

### E2: Semantic Fidelity (의미적 충실성)
추천 근거가 abstract에 실제로 존재하는가.

**검증 방법:**
1. 각 :dart: 타겟팅 라인의 주장을 추출
2. 해당 논문의 abstract에서 근거 문장을 매칭
3. 매칭 불가 → HALLUCINATION flag

**Scoring:**
- 0: 근거 없는 주장 (hallucination)
- 1: 간접 추론 가능 (abstract에서 2+ logical leap)
- 2: 직접 근거 존재 (abstract 문장과 1:1 대응)

### E3: Member Targeting Quality (멤버 타겟팅 품질)
태그된 멤버에게 실제로 가치 있는 추천인가.

**검증 방법:**
1. 태그된 멤버의 프로젝트 기술(context-bundle.json)을 로드
2. 타겟팅 라인과 프로젝트 기술 간 의미적 관련성 판단
3. Member Advocate 시뮬레이션: "이 멤버가 스크롤을 멈출까?"

**Scoring:**
- 0: 관련 없음 (false positive tag)
- 1: 약한 관련 (같은 분야지만 직접적이지 않음)
- 2: 강한 관련 (프로젝트/실험/모델에 직접 연결)
- 3: 즉각 행동 유발 (이번 주 실험/분석에 영향)

### E4: Hook Effectiveness (훅 효과성)
3초 테스트를 통과하는가.

**검증 체크리스트:**
- [ ] 특정 멤버/프로젝트/가설 언급
- [ ] 발견(finding)을 전달, 주제(topic)가 아님
- [ ] 논문 제목 반복이 아님
- [ ] 모호한 칭찬 없음
- [ ] 저널명 선행 없음
- [ ] dominant dimension에 맞는 패턴 사용
- [ ] ≤120자, 한국어
- [ ] 2줄 이내

**Score:** 체크리스트 8항목 중 통과 수 / 8

### E5: Agent Convergence (에이전트 수렴성)
Team phase에서 에이전트들이 효율적으로 수렴하는가.

**Metrics:**
- `iterations`: 수렴까지 라운드 수 (1=최적, 3=최대, >3=실패)
- `pass_rate_r1`: 1라운드에서 PASS한 에이전트 비율
- `stalemate`: 3라운드 후에도 미수렴 여부
- `feedback_specificity`: 피드백이 구체적 수정 지시인가 vs 모호한 불만인가

**Scoring:**
- 3: 1라운드 수렴 (all pass)
- 2: 2라운드 수렴
- 1: 3라운드 수렴
- 0: 미수렴 (stalemate)

### E6: Pipeline Coherence (파이프라인 일관성)
단계 간 데이터 전달에서 정보 손실이 없는가.

**검증 포인트:**
1. Scan → Score: 모든 candidates가 scoring 대상에 포함되었는가
2. Score → Team: 점수/차원이 draft에 정확히 반영되었는가 (:label: 태그)
3. Team → Review: draft 내용이 review에 정확히 전달되었는가
4. Review → Post: 수정 사항이 최종 포스트에 반영되었는가

**Score:** 4개 전환 지점 중 무손실 통과 수 / 4

### E7: Safety & Exclusion (안전성)
금지 사항 준수 여부.

**Hard Fail (1개라도 위반 시 전체 FAIL):**
- [ ] HSL 멘션 없음
- [ ] P3 (김민아) 멘션 없음
- [ ] P4 (임채영) 멘션 없음
- [ ] 사용자 확인 없이 Slack 게시 시도 없음
- [ ] 잘못된 채널 게시 시도 없음
- [ ] 잘못된 Slack ID 사용 없음

## Fitness Score Calculation

```
Phase Fitness  = mean(E1_per_phase)              × 15%
Semantic       = mean(E2_per_claim)               × 20%
Targeting      = mean(E3_per_member)              × 20%
Hook           = E4_score                         × 10%
Convergence    = E5_score                         × 15%
Coherence      = E6_score                         × 10%
Safety         = E7_pass (binary gate)            × 10%

Total Fitness = weighted_sum IF E7_pass ELSE 0
```

**등급:**
- **A (≥ 0.85):** 즉시 배포 가능. Slack 게시 승인 권장.
- **B (0.70–0.84):** 사소한 수정 후 배포. 특정 항목 피드백 제공.
- **C (0.55–0.69):** 상당한 수정 필요. 문제 단계 재실행 권장.
- **D (0.40–0.54):** 파이프라인 재검토 필요. 설정/앵커 DB 점검.
- **F (< 0.40 또는 E7 실패):** 배포 불가. 근본 문제 진단 필요.

## Execution Protocol

### Mode 1: Phase Eval (단일 단계 검증)

```
paper scout harness eval-scan    outputs/paper-scout-candidates-{DATE}.md
paper scout harness eval-score   outputs/paper-scout-scores-{DATE}.md
paper scout harness eval-team    outputs/paper-scout-draft-{DATE}.md
paper scout harness eval-review  outputs/paper-scout-review-{DATE}.md
paper scout harness eval-post    outputs/paper-scout-log-{DATE}.md
```

**절차:**
1. 대상 파일을 로드
2. 해당 Phase의 E1 구조 검증
3. E2-E7 중 적용 가능한 항목 평가
4. `harness/results/eval-{phase}-{DATE}.md` 에 결과 저장

### Mode 2: Full Pipeline Eval (전체 워크플로우 검증)

```
paper scout harness eval-full {DATE}
```

**절차:**
1. `outputs/paper-scout-*-{DATE}.md` 전체 로드
2. E1-E7 모든 차원 평가
3. 단계 간 E6 일관성 검증
4. 종합 Fitness Score 산출
5. `harness/results/eval-full-{DATE}.md` 에 결과 저장

### Mode 3: Dry Run (모의 실행)

```
paper scout harness dry-run
```

**절차:**
1. `harness/evals/` 의 테스트 케이스 로드
2. 각 테스트 케이스에 대해 파이프라인 모의 실행
3. expected_behavior와 실제 결과 비교
4. `harness/results/dry-run-{DATE}.md` 에 결과 저장

## Rubric Files

평가 기준의 상세 정의:

- `rubrics/e1-structural.md` — 단계별 필수 필드 + 포맷 스펙
- `rubrics/e2-semantic.md` — abstract grounding 검증 프로토콜
- `rubrics/e3-targeting.md` — 멤버 타겟팅 품질 기준
- `rubrics/e4-hook.md` — 훅 효과성 체크리스트
- `rubrics/e5-convergence.md` — 에이전트 수렴성 메트릭
- `rubrics/e6-coherence.md` — 파이프라인 일관성 전환점
- `rubrics/e7-safety.md` — 안전성 hard fail 목록

## Report Template

```markdown
# Paper Scout Harness Report — {DATE}

## Summary
| Dimension | Score | Grade | Notes |
|-----------|-------|-------|-------|
| E1 Structural | X/1.0 | | |
| E2 Semantic | X/1.0 | | |
| E3 Targeting | X/1.0 | | |
| E4 Hook | X/1.0 | | |
| E5 Convergence | X/1.0 | | |
| E6 Coherence | X/1.0 | | |
| E7 Safety | PASS/FAIL | | |

**Total Fitness: X.XX — Grade {A/B/C/D/F}**

## Phase-by-Phase Results
### Scan
[E1 results, semantic gate stats, candidate quality]

### Score
[D1-D5 distribution, quote evidence, scoring consistency]

### Team
[Agent verdicts per round, convergence path, feedback quality]

### Review
[Group verdicts, cross-group consistency, edit applications]

### Post
[Format compliance, Slack ID verification, safety checks]

## Issues Found
1. [Issue description] — Severity: HIGH/MED/LOW — Recommendation
2. ...

## Recommendations
- [Action items for improvement]
```
