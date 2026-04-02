---
name: consensus-arbiter
role: 판사 합의 도출 및 최종 결정
model: rule-based (non-LLM)
---

# Consensus Arbiter

## 역할
3명의 Relevance Judge 판결을 종합하여 최종 TRASH/KEEP 결정을 내리는 규칙 기반 arbiter.

## 합의 규칙

### 만장일치 (3/3)
- 3명 모두 IRRELEVANT → **TRASH** (confidence: HIGH)
- 3명 모두 RELEVANT → **KEEP** (confidence: HIGH)

### 다수결 (2/3)
- 2명 IRRELEVANT + 1명 기타 → **TRASH** (confidence: MEDIUM)
- 2명 RELEVANT + 1명 기타 → **KEEP** (confidence: MEDIUM)

### 불일치 (1/1/1)
- 3명 모두 다른 판결 → **KEEP** (conservative default)

### 특수 규칙
- BORDERLINE은 KEEP으로 집계
- ERROR는 무시 (유효 판결만 집계)
- 유효 판결이 1개 이하 → **KEEP** (판단 불가)

## 출력
```json
{
  "decision": "TRASH|KEEP",
  "agreement": 3,  // 다수파 인원수
  "confidence": "HIGH|MEDIUM|LOW"
}
```
