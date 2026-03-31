# E2: Semantic Fidelity — Abstract Grounding 검증

## 원칙
Paper Scout의 모든 주장은 **논문 abstract에서 직접 도출** 가능해야 한다.
Abstract를 넘어서는 추측(speculation)은 hallucination으로 처리.

## 검증 대상

### 1. :dart: 타겟팅 라인의 주장
각 `:dart:` 라인에서 주장(claim)을 추출하고, abstract에서 근거를 찾는다.

**예시:**
```
:dart: *<@U06K5MX4GHE> SK의 WMRepresentation*: Fig 3의 drift가 V1에서 orthogonal subspace를 따라 전파
```
→ Claim: "drift가 V1에서 orthogonal subspace를 따라 전파"
→ Abstract에서 검증: "We show that memory-related activity propagates through orthogonal subspaces in V1..." → MATCH (score 2)

### 2. :fire: 훅의 주장
훅이 특정 발견(finding)을 언급하면 abstract에서 확인.

### 3. :label: 차원 태그의 근거
D4 (Competitive Signal)이면 abstract에서 해당 연구 그룹/질문의 독립 발표 여부 확인.

## Scoring Protocol

### Step 1: Claim Extraction
각 포스트에서 검증 가능한 주장을 추출.
- 타겟팅 라인의 구체적 연결 (method, result, mechanism)
- 훅의 발견 진술
- 차원 근거

### Step 2: Abstract Matching
각 주장에 대해:
1. 해당 논문의 abstract를 로드
2. 주장과 abstract 문장을 비교
3. 매칭 수준 판정

### Step 3: Scoring
| Score | Criteria | Example |
|-------|----------|---------|
| **0** | 근거 없음 (hallucination) | Abstract에 언급되지 않은 특정 brain region을 주장 |
| **1** | 간접 추론 (2+ logical leaps) | Abstract의 "working memory"에서 "BMBU 모델에 직접 적용"을 추론 |
| **2** | 직접 근거 (1:1 대응) | Abstract 문장과 주장이 동일한 내용 |

### Step 4: Aggregation
```
E2_score = mean(all_claim_scores) / 2.0   # normalize to 0-1
```

## Red Flags (자동 감점)
- "아마도 본문에서..." — abstract 외 추측
- "이 방법론은 ~에 적용 가능할 것" — 논문이 주장하지 않은 응용
- 구체적 figure 번호 언급 but abstract에 없음 — 본문 참조
- 특정 수치 인용 but abstract에 없음

## Acceptable Exceptions
- CSNL 프로젝트와의 연결은 abstract 외 지식 허용 (context-bundle.json 기반)
- "anchor: Gu et al. 2025"는 검증 불필요 (시스템 생성)
