---
name: paper-scout-score
description: >
  Phase 2 of CSNL Paper Scout: value-dimension scoring with semantic grounding. Replaces arbitrary
  weight-based scoring with 5 research-value dimensions + Zotero semantic distance as objective gate.
  Triggers on: 'score papers', 'rank papers', 'paper scout score', '논문 평가', '논문 스코어링',
  'relevance scoring', 'value dimension scoring', '가치 평가'. Use after paper-scout-scan.
---

# Paper Scout — Phase 2: Value Dimension Scoring

Score candidates not by arbitrary weights, but by the *type of value* each paper offers to specific
CSNL researchers.

## Why Value Dimensions, Not Weighted Averages

The old system (0.5 × project + 0.5 × GRM) was arbitrary and redundant — GRM topics are the members'
projects. More fundamentally, a researcher decides to read a paper because of one strong reason, not
an average of weak ones. The scoring must reflect this.

## Prerequisites

1. Candidates from Phase 1: `paper-scout-candidates-[DATE].md`
2. Enriched contexts: `paper-scout-enriched-contexts-v3.md`
3. Context bundle: `../paper-scout/context-bundle.json`
4. Researcher reading profiles: `csnl-pi-network/data/researcher_reading_profiles.json`

## The 5 Value Dimensions

Score each candidate paper on each dimension (0-10) **per matched member**.

| Dim | Name | Core Question | Example (score 8+) |
|-----|------|---------------|---------------------|
| D1 | **Direct Advance** | "이 논문의 결과/방법이 내 실험/모델에 바로 쓸 수 있나?" | Time 프로젝트에 새 duration estimation Bayesian model 등장 |
| D2 | **Hypothesis Tension** | "내 가설을 지지하거나 도전하는 증거인가?" | RingRepSca H1에 대한 반증 데이터 |
| D3 | **Methodological Import** | "빌려올 수 있는 새 분석/패러다임이 있나?" | 새 dPCA 변형을 SK가 채택 가능 |
| D4 | **Competitive Signal** | "같은 질문을 다른 그룹이 추격하고 있나?" | JOP의 estimation-only paradigm을 다른 랩이 독립 발표 |
| D5 | **Reframing Power** | "내 문제를 새로운 프레임으로 볼 수 있게 해주나?" | Rate-distortion theory를 WM bias에 적용 |

### Scoring Rubric Per Dimension

| Score | Meaning |
|-------|---------|
| 0-2 | 이 차원에서 가치 없음 |
| 3-4 | 약한 연결 — 같은 분야이나 직접적이지 않음 |
| 5-6 | 의미 있는 연결 — 방법 OR 현상 하나가 겹침 |
| 7-8 | 강한 연결 — 해당 차원에서 직접적 가치 |
| 9-10 | 즉각적 행동 유발 — 읽고 바로 뭔가를 바꾸거나 시작해야 함 |

## Composite Score: Max, Not Average

```
member_score = max(D1, D2, D3, D4, D5)
```

연구자가 논문을 "이건 꼭 읽어야 해"라고 느끼는 건 하나의 강한 이유 때문이다.
여러 약한 이유의 합산이 아니다.

**Tie-breaking**: `mean(D1..D5)` — 같은 max를 가진 논문 중 더 다양한 차원에서 가치 있는 것이 우선.

**Paper-level score**: 모든 matched member의 `member_score` 중 최대값.

## Semantic Gate (from Phase 1)

Phase 1에서 이미 semantic distance ≥ 0.4인 논문만 넘어왔지만, 스코어링 시 이 값을 활용:

- `semantic_distance ≥ 0.6`: "우리 논문과 가까움" → D1-D5 점수에 대한 신뢰도 높음
- `semantic_distance 0.4-0.6`: "경계 영역" → D5 (Reframing) 외에는 보수적으로 scoring
- 어떤 dimension에서든 7+ 점수를 주려면, abstract에서 구체적 근거를 인용해야 함

## Embedding-Based Reranking (Optional)

After D1-D5 scoring, optionally use the OpenRouter rerank model to validate member-paper matches:

### Reranking Protocol

For each candidate × each scored member (composite ≥ 5):

```python
from paper_scout_embed import rerank

# Query = member's project gist (from enriched-contexts-v3.md)
# Documents = [candidate abstract, anchor paper abstract, ...]
results = rerank(
    query=member_project_gist,
    documents=[candidate_abstract, *anchor_abstracts],
    top_k=5
)
# If candidate ranks #1-2 among documents → confirms high relevance
# If candidate ranks #3+ → flag for manual review
```

### Integration with Scoring

- Rerank score does NOT override D1-D5 dimensions
- It serves as a confidence signal: "does the embedding model agree with the LLM's assessment?"
- Log rerank position in the scoring output for transparency
- Use `nvidia/llama-nemotron-rerank-vl-1b-v2:free` via OpenRouter

### When to Use

- Always run for papers at the threshold boundary (composite 6-8)
- Skip for clearly high-scoring (9+) or clearly low-scoring (≤4) papers
- Useful when the semantic gate distance is in the 0.4-0.5 borderline range

## Scoring Agent Architecture

단일 agent가 모든 scoring을 수행하되, member별로 개별 평가:

For each candidate × each potentially relevant member:
1. Load the member's project description (enriched-contexts-v3.md)
2. Load the member's reading profile (researcher_reading_profiles.json) — 이 멤버가 어떤 저자를 추적하고, 어떤 주제에 관심이 있는지
3. Score D1-D5 with **mandatory reasoning** per dimension
4. Any score ≥ 7 requires a direct quote or specific claim from the abstract as evidence

## Anti-Hallucination Rules

1. **Abstract-only rule**: Scoring은 abstract에 명시된 내용만으로. "아마 본문에서..." 같은 추측 금지.
2. **Specificity test**: "이 논문은 serial dependence에 관련됨"은 scoring 근거가 아님. "이 논문이 Fig 2에서 보인 orientation estimation에서의 attractive bias가 Gu et al. 2025의 drift-to-attractor 예측과 일치/충돌"까지 구체화해야 함.
3. **Negative scoring**: 관련 없는 dimension은 0점을 줘야지, 3-4점으로 채우면 안 됨. "약간 관련 있을 수도"는 0점.
4. **Competing evidence rule**: D2 (Hypothesis Tension)에서 높은 점수를 줄 때, 어떤 가설에 대한 어떤 방향의 tension인지 명시.

## Output Format

Save to: `paper-scout-scores-[YYYY-MM-DD].md`

```markdown
# Paper Scout Scores — [DATE]

## Top [N] Selected

| Rank | Paper | Best Member | Best Dim | Max Score | Semantic Dist | Nearest Anchor |
|------|-------|-------------|----------|-----------|---------------|----------------|
| 1 | [Title] | JOP | D4 Competitive | 9 | 0.72 | Gu et al. 2025 |
| 2 | ... | ... | ... | ... | ... | ... |

## Detailed Scoring

### [Paper Title]
- **Semantic anchor**: [nearest CSNL paper] (distance: 0.XX)

#### For JOP (RingRepSca, Time):
| D1 | D2 | D3 | D4 | D5 | Max |
|----|----|----|----|----|-----|
| 3  | 8  | 0  | 9  | 2  | 9   |

- D2 (8): "[specific abstract quote] — 이 결과는 RingRepSca H1의 X 예측과 직접 비교 가능"
- D4 (9): "[PI name]이 estimation-only paradigm에서 유사 실험을 독립 수행"

#### For SK (WMRepresentation):
| D1 | D2 | D3 | D4 | D5 | Max |
|----|----|----|----|----|-----|
| 0  | 0  | 6  | 0  | 0  | 6   |

- D3 (6): "새로운 cross-decoding analysis를 제안하나, SK의 dPCA 접근과 직접 호환되려면 추가 검증 필요"
```

## Selection Criteria

1. **Top 3** by paper-level max score
2. **Group balance check**: 모든 Top 3가 같은 group이면, 차순위에서 다른 group 논문 검토
3. **Minimum threshold**: paper-level max score ≥ 7 미만이면 해당 주에는 추천하지 않음. "추천할 만한 논문이 없습니다"가 낫다.

## Handoff

> "스코어링 완료: [N]편 선정 (최고점 [X]). `paper-scout-draft`로 포스트를 작성할까요?"
