# E6: Pipeline Coherence — 파이프라인 일관성

## 원칙
각 단계의 출력이 다음 단계의 입력으로 **무손실** 전달되어야 한다.

## 4 Transition Points

### T1: Scan → Score
**검증:** 모든 candidates가 scoring 대상에 포함

| Check | Method | Pass |
|-------|--------|------|
| Candidate count match | candidates 수 ≥ scored papers 수 | |
| DOI consistency | 모든 scored paper의 DOI가 candidates에 존재 | |
| Metadata preservation | title, authors, journal이 변형 없이 전달 | |
| Embedding score 전달 | semantic_distance가 scoring context에 반영 | |

### T2: Score → Team
**검증:** 점수와 차원이 draft에 정확히 반영

| Check | Method | Pass |
|-------|--------|------|
| Score accuracy | :label: 태그의 D{n} 점수 = scoring file의 해당 값 | |
| Member selection | 태그된 멤버 = scoring에서 threshold 이상인 멤버 | |
| Composite match | dominant dimension = max(D1..D5) | |
| Paper metadata | title, DOI가 scoring file과 일치 | |

### T3: Team → Review
**검증:** draft 내용이 review에 정확히 전달

| Check | Method | Pass |
|-------|--------|------|
| Draft content match | review에서 인용된 draft가 actual draft와 동일 | |
| Verdict log 전달 | review가 Team Verdict Log를 참조 가능 | |
| Paper identity | 같은 논문에 대한 review인지 확인 (DOI match) | |

### T4: Review → Post
**검증:** 수정 사항이 최종 포스트에 반영

| Check | Method | Pass |
|-------|--------|------|
| MODIFY edits applied | group MODIFY 의 구체적 수정이 final post에 반영 | |
| ESCALATE handling | ESCALATE된 paper가 재처리되었거나 제외 | |
| APPROVE preservation | APPROVE된 post가 변형 없이 유지 | |
| Safety re-check | review 후 새로 도입된 내용에 E7 위반 없음 | |

## Scoring
```
E6_score = (passed_transitions / 4)
```

## Common Failure Patterns

| Pattern | Symptom | Root Cause |
|---------|---------|------------|
| T1 fail | scored paper가 candidates에 없음 | 수동 추가된 paper (scan 우회) |
| T2 fail | :label: 점수 불일치 | Drafter가 scoring file을 잘못 참조 |
| T3 fail | review가 outdated draft 참조 | Team 재실행 후 Review 미갱신 |
| T4 fail | MODIFY 미반영 | Post가 review 전 draft를 사용 |
