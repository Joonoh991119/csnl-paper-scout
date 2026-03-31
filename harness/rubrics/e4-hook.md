# E4: Hook Effectiveness — 3초 테스트

## 원칙
바쁜 연구자가 Slack 스크롤 중 **3초 이내에** "이건 나에게 중요하다"를 판단할 수 있어야 한다.

## 8-Item Checklist

| # | Criterion | Pass | Fail Example |
|---|-----------|------|-------------|
| 1 | 특정 멤버/프로젝트/가설 언급 | "SK의 orthogonal subspace 가설에..." | "CSNL의 여러 프로젝트와..." |
| 2 | 발견(finding) 전달, 주제(topic) 아님 | "drift가 V1→V3로 orthogonal 전파" | "working memory에 대한 연구" |
| 3 | 논문 제목 반복 아님 | 독립적 요약 | 제목 번역 |
| 4 | 모호한 칭찬 없음 | 구체적 주장 | "흥미로운 연구", "중요한 발견" |
| 5 | 저널명 선행 없음 | 발견으로 시작 | "최근 Nature에 발표된..." |
| 6 | Dominant dimension 패턴 매칭 | D4 high → Pattern 1 (Competitive) | D4 high인데 Pattern 4 사용 |
| 7 | ≤120자 | 간결 | 장문 |
| 8 | 한국어 | 한국어 | 영어 |

## Pattern-Dimension Matching

| Dominant D | Expected Pattern | Template |
|-----------|-----------------|----------|
| D1 (Direct Advance) | Pattern 4 | "[결과]는 [프로젝트]에 즉시 적용 가능한..." |
| D2 (Hypothesis Tension) | Pattern 2 | "[가설]에 도전/지지하는 새 모델..." |
| D3 (Method Import) | Pattern 3 | "최초로 [방법]으로 [현상]을..." |
| D4 (Competitive Signal) | Pattern 1 | "[PI name] 그룹이 [질문]에서 독립 발표..." |
| D5 (Reframing Power) | Pattern 5 | "[framework]로 [문제]를 재해석..." |

## Scoring
```
E4_score = (passed_items / 8)
```

## Edge Cases
- D1 = D4 (tie): 어느 패턴이든 acceptable, 한쪽이 더 구체적이면 그것 선택
- 모든 D가 비슷 (6-7): Pattern 4 (Direct Advance) default
