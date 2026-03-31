# E3: Member Targeting Quality — 멤버 타겟팅 품질

## 원칙
태그는 **해당 멤버가 스크롤을 멈출 만한 이유가 있을 때만** 사용한다.
False positive (무의미한 태그) > False negative (누락) 보다 나쁘다.

## 검증 방법

### Step 1: Load Member Context
context-bundle.json에서 태그된 멤버의 프로젝트 기술을 로드.

### Step 2: Relevance Assessment
각 `:dart:` 라인에 대해:

| Score | Criteria | Test Question |
|-------|----------|---------------|
| **0** | 관련 없음 (false positive) | "이 논문이 이 멤버의 어떤 프로젝트와도 연결되지 않는다" |
| **1** | 약한 관련 | "같은 분야이지만 이 멤버의 구체적 질문과는 다르다" |
| **2** | 강한 관련 | "이 멤버의 특정 프로젝트/실험/모델에 직접 연결된다" |
| **3** | 즉각 행동 유발 | "이번 주/이번 달 실험/분석 방향에 영향을 준다" |

### Step 3: Member Advocate Simulation
태그된 각 멤버 관점에서 자문:

1. **"이 추천을 받으면 무엇을 하겠는가?"**
   - 3: 즉시 읽고 분석 방법을 변경
   - 2: 이번 주 안에 읽겠다
   - 1: 나중에 읽을 수도 있다
   - 0: 왜 태그했는지 모르겠다

2. **"타겟팅 라인이 WHY를 1문장으로 전달하는가?"**
   - YES: 프로젝트명 + 구체적 연결 명시
   - NO: "serial dependence 관련" 같은 모호한 연결

3. **"과장된 연결인가?"**
   - Logical leaps 수: 0-1 = OK, 2 = borderline, 3+ = overstated

## Per-Member Relevance Matrix

| Member | Projects | Key Topics (태그 적합 신호) |
|--------|----------|--------------------------|
| JOP | RingRepSca, Time, Time2Dist, GranRDT, GranNMDS | estimation-only paradigm, BMBU, CDF normalization, granularity, DV space |
| MSY | CatVsMag | categorical vs magnitude SD, gambler's fallacy, StyleGAN2, hierarchical Bayesian |
| JYK | RNN | drift-diffusion dynamics, persistent vs sequential coding, non-normal connectivity |
| MJC | SeqVWM | sequential VWM, contrast-dependent bias, SOB model, energy field, serial position |
| SK | WMRepresentation | EVC sensory vs WM code, orthogonal subspace, dPCA, geometry-preserving re-embedding |
| JHR | SpatialExtent, FC_orientation | pRF anisotropy, radial/co-axial, orientation-specific FC, V1-V4 hierarchy |
| SMJ | Concentricity, V1toPercept | co-circularity, saccadic strategy, natural image statistics, saliency |
| JSL | SerialDep_Spatial, Attraction_asymmetry, Passive_navigation | relative/object-centered SD, comparative judgment, ISC, passive navigation |

## Aggregation
```
E3_score = mean(all_member_scores) / 3.0   # normalize to 0-1
```

## Anti-patterns (감점 요인)
- 같은 논문에 5명 이상 태그 → 실제로 모두에게 가치 있는지 재검토
- D score < 5 인데 태그됨 → false positive 의심
- 프로젝트명 누락 → 구체성 부족
- "~에 관련될 수 있음" → 확신 부족한 태그
