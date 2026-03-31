---
name: paper-scout-draft
description: >
  Phase 3 of CSNL Paper Scout: draft high-quality Slack posts with visual evidence (graphical abstract
  or generated diagram), 3-second hook, and per-member targeting. Heavily optimized for readability and
  information density. Triggers on: 'draft posts', 'write paper posts', 'paper scout draft', 'Slack 포스트',
  '논문 추천 포스트', 'write recommendations', '포스트 작성', 'post draft'. Use after paper-scout-score.
---

# Paper Scout — Phase 3: Post Drafting (Visual + Hook Optimized, v3)

Create Slack posts that lab members actually stop scrolling for. Every post must pass the **3-second test**:
a busy researcher glancing at Slack should know within 3 seconds whether this paper matters to them.

## Why This Phase Gets Heavy Investment

A perfectly scored paper is worthless if the post gets scrolled past. The posting format is the product's
user interface. We invest heavily here so every future execution produces consistent, high-quality output
without re-learning.

## Prerequisites

1. Scoring results: `paper-scout-scores-[DATE].md`
2. Context bundle: `../paper-scout/context-bundle.json` (Slack IDs)
3. Full paper access for visual extraction (via Chrome MCP or WebFetch)
4. `paper-scout-embed.py` for figure ranking (embed-vl)

## Post Template v3

```
:fire: [한 줄 hook — 이 논문이 당신에게 왜 중요한지, 한 문장]

*[Paper Title]*
_[First Author] et al. — [Journal] ([Year])_
:link: [DOI URL]

[FIGURE — graphical abstract or best-match figure URL]

[KEY EQUATION — if applicable]
> `[equation]` — [1-line Korean explanation]

:dart: *<@SLACK_ID> [Name]의 [Project]*: [이 멤버에게 구체적으로 어떤 가치인지 1문장]
:dart: *<@SLACK_ID> [Name]의 [Project]*: [이 멤버에게 구체적으로 어떤 가치인지 1문장]

:label: [D1 Direct 8] · [D4 Competitive 9] — anchor: [nearest CSNL paper short title]
```

## The 3-Second Hook

The hook is the single most important line. It must answer: **"왜 내가 이걸 읽어야 하지?"**

### Hook Patterns (ranked by effectiveness):

**Pattern 1 — Competitive Alert** (D4 high):
> :fire: [PI name] 그룹이 estimation-only paradigm에서 history effect를 독립 발표 — JOP의 RingRepSca와 직접 비교 필요

**Pattern 2 — Hypothesis Tension** (D2 high):
> :fire: Attractor dynamics만으로 WM bias를 설명한 새 모델 — Gu et al. 2025의 drift-diffusion 가정에 도전

**Pattern 3 — Method Import** (D3 high):
> :fire: Layer-specific dPCA로 feedforward/feedback 코드를 분리한 첫 human fMRI 연구

**Pattern 4 — Direct Advance** (D1 high):
> :fire: Skewed duration distribution에서의 Bayesian updating — Time 프로젝트 fitting에 즉시 적용 가능한 모델

**Pattern 5 — Reframing** (D5 high):
> :fire: Rate-distortion framework으로 serial dependence를 재해석 — GranRDT의 관점을 SD 전체로 확장

### Hook Anti-Patterns (절대 금지):

- ❌ "흥미로운 연구가 나왔습니다" — 누구에게 왜 흥미로운지 없음
- ❌ "CSNL의 여러 프로젝트와 관련이 있습니다" — 어떤 프로젝트에 어떻게?
- ❌ "최근 Nature에 게재된..." — 저널 이름은 hook이 아님
- ❌ 논문 제목 반복 — 제목은 이미 아래에 있음

## Visual Strategy (v3: Figure Extraction via Chrome MCP + embed-vl Selection)

모든 포스트에 시각적 요소를 포함한다. 텍스트만 있는 포스트는 최종 게시 대상이 아니다.

### Step 1: Extract Candidate Figures from Full-Text Page

1. **Chrome MCP Navigation**: Use `navigate` to the paper's DOI URL (e.g., https://doi.org/10.1101/...)
2. **Figure URL Extraction**: Use `read_page` or `get_page_text` to identify figure URLs in the HTML
3. **Comprehensive Collection**: Extract ALL figure URLs:
   - Graphical abstract
   - Figure 1 through N
   - Supplementary figures
4. **Fallback Pattern Matching**: If Chrome MCP unavailable, use WebFetch on known patterns:
   - **eLife**: `https://iiif.elifesciences.org/lax:{id}%2Felife-{id}-fig{n}-v1.tif/full/1500,/0/default.jpg`
   - **bioRxiv**: Parse HTML for figure URLs in `/articles/` endpoint
   - **PNAS/Nature**: Extract from article HTML `<figure>` tags

### Step 2: Embed-VL Figure Ranking per Member

Using `paper-scout-embed.py`:

```python
# For each figure extracted
fig_vecs = [embed_image(fig_url) for fig_url in figure_urls]

# For each tagged member, embed their project description
member_vec = embed_text(member_project_description)

# Find best figure for each member (cosine similarity)
best_fig_per_member = {
    member: max(fig_vecs, key=lambda v: cosine_similarity(v, member_vec))
    for member in tagged_members
}

# Rank globally by max cosine score
global_best_fig = max(fig_vecs, key=lambda v: max(
    cosine_similarity(v, embed_text(member.project_desc)) 
    for member in tagged_members
))
```

**Interpretation**:
- **Cosine ≥ 0.7**: Strong match (use as primary visual)
- **Cosine 0.3–0.7**: Moderate match (consider if graphical abstract unavailable)
- **Cosine < 0.3**: Weak match (skip unless no alternative)

### Step 3: Select Visual for Post

**Priority (updated for v3)**:

1. **Graphical abstract** (if available AND cosine ≥ 0.3 with any member)
   - Most journals now provide graphical abstract
   - Extract via Chrome MCP or WebFetch
   - Typically highest information density

2. **Best-matching figure per primary member** (highest cosine with member's project vector)
   - If graphical abstract cosine < 0.3
   - Use the figure with highest embed-vl similarity to the primary member's project description
   - Include figure caption in comment if not self-explanatory

3. **Key equation** (extract from full-text using Chrome MCP, screenshot or LaTeX render)
   - Only if equation is central to paper's main claim
   - See "Key Equation Extraction" subsection below
   - Include as separate visual element from main figure

4. **Mermaid/SVG diagram** (AI-generated, last resort)
   - Use only when figure extraction fails entirely
   - Generate conceptual diagram of paper's main contribution
   - Ensure accuracy and no hallucination

### Key Equation Extraction (New in v3)

Include equations when central to the paper's main contribution.

**Extraction Methods**:
1. **Chrome MCP Navigation**: Navigate to full-text PDF or HTML
2. **Screenshot Extraction**: Take screenshot of rendered equation
3. **LaTeX Source**: Extract from HTML source (many journals serve MathJax/KaTeX)
4. **OCR Fallback**: If visual only, use image-to-LaTeX tools

**Slack Formatting**:
- **LaTeX block** (preferred): `$$equation$$` for in-line rendering
- **Code block**: \```equation\``` if LaTeX rendering unavailable
- **Image URL**: If rendered equation image available
- **Korean explanation** (1 line): 이 방정식이 의미하는 바를 간단히 설명

**Example**:
```
> `Loss = MSE(y_pred, y_true) + λ·L1_regularization` 
> — Loss function이 prediction error와 model complexity를 균형 맞추는 방식
```

**Selection Rules**:
- Include only equations central to main claim (not every equation in paper)
- Avoid over-inclusion (max 1–2 equations per post)
- Always pair with Korean explanation
- Ensure LaTeX is correct (no hallucinated symbols)

### Visual Quality Checklist:
- [ ] 이미지가 논문의 핵심 기여를 1초 안에 전달하는가?
- [ ] 이미지 없이 텍스트만으로는 전달하기 어려운 정보를 담고 있는가?
- [ ] 해상도가 Slack에서 readable한가? (최소 600px 너비)
- [ ] (if included) 방정식이 논문의 주요 claim에 직접적 연관이 있는가?

## Per-Member Targeting Lines

각 tagged member에게 개별화된 1줄을 쓴다. "Why CSNL"이 아니라 "Why YOU".

### 좋은 예:
> :dart: *<@U06JGAX5HD5> JOP의 RingRepSca*: Different-hemisphere 조건에서 repulsive bias가 사라지지 않는다는 이 논문의 Fig 3 결과가, RingRepSca의 H1 (표상 독립성) 검증 전략과 정확히 일치

> :dart: *<@U06K5MX4GHE> SK의 WMRepresentation*: Encoding 시점의 noise correlation이 sensory-mnemonic 간 coupling을 예측한다는 결과가, SK의 "orthogonal but linked" 발견의 메커니즘적 설명이 될 수 있음

### 나쁜 예:
> :dart: *JOP*: serial dependence 관련 논문임  ← 너무 vague
> :dart: *SK*: fMRI 연구  ← 아무 정보 없음

### Targeting Rules:
1. **Member name + project name** 반드시 포함
2. **Slack ID** 사용 (`<@U06JGAX5HD5>` 형식)
3. **구체적 연결점**: 어떤 실험/결과/방법이 어떻게 연결되는지
4. **Dimension 표시**: 이 멤버에게 주로 어떤 가치 차원에서 유용한지
5. **태그하지 않을 멤버는 태그하지 않음**: 약한 연결은 태그 없이 본문에 "참고: ..." 수준으로

## Slack ID Reference

| Member | Slack ID | Active Projects |
|--------|----------|-----------------|
| JOP (박준오) | U06JGAX5HD5 | RingRepSca, Time, Time2Dist, GranRDT, GranNMDS |
| MSY (여민수) | U06JA7D5XC7 | CatVsMag |
| MJC (최민진) | U06JX0EGWKF | SeqVWM |
| SK (김성제) | U06K5MX4GHE | WMRepresentation |
| JHR (류주형) | U06QLKE5L1X | SpatialExtent, FC_orientation |
| JSL (임재섭) | U06QRFF10J1 | SerialDep_Spatial |
| SMJ (정새미) | U080KFS0TFZ | Concentricity |
| JYK (김정예) | U081CN9JVK3 | RNN |
| BYL (이보연) | U07728304R5 | Bayesian observer, VWM bias |
| BHL (이보현) | U09DQQFB4E4 | Serial dependence, feature binding, WM |
| PI (이상훈) | U06JQ1TA6SX | — |

**Target channel**: `study-paper-reading` (ID: `C06KJ95MGGZ`)

## Tone Guidelines

- **선언문 스타일**: "이 논문은 X를 보인다" — not "이 논문은 흥미롭게도..."
- **이모지**: :fire: (hook), :dart: (targeting), :link: (DOI), :label: (dimension tag)만 사용. 다른 이모지 금지.
- **수사적 질문 금지**: "여러분도 궁금하지 않으셨나요?" 같은 것 금지.
- **200자 이내** per member targeting line.
- **Korean for recommendations, English for citations.**

## Multi-Agent Review Pipeline (built-in)

드래프트 작성 후, 3개 review agent를 순차 실행하여 품질을 보장한다.
이 review는 Phase 4 (peer review)와 별개로, 포스트 자체의 품질에 집중한다.

### Agent 1 — Hook Evaluator
- 이 hook을 처음 보는 사람이 3초 안에 "이건 내 논문이다"라고 느끼는가?
- Hook이 논문 제목을 반복하고 있지 않은가?
- 구체적 멤버/프로젝트/가설을 언급하고 있는가?
- **Verdict**: PASS / REWRITE (with specific suggestion)

### Agent 2 — Visual Evaluator (Updated for v3)
- 시각적 요소가 텍스트만으로는 전달 불가한 정보를 담고 있는가?
- 이미지 URL이 유효한가? (broken link 체크)
- **(NEW)** 선택된 figure가 가장 member-relevant인가? (embed-vl cosine score 확인)
- **(NEW)** 방정식이 포함되어야 하는가? 포함되었다면 1줄 Korean explanation이 있는가?
- Mermaid/SVG 생성 시: 학술적으로 정확한가? 오해 소지가 없는가?
- **Verdict**: PASS / REPLACE (with better visual) / ADD (visual or equation missing)

### Agent 3 — Accuracy Evaluator
- 모든 claim이 abstract에 근거하는가?
- Member targeting line이 정확한 프로젝트에 매핑되는가?
- Slack ID가 올바른가?
- 과장된 연결이 있는가?
- **Verdict**: PASS / FIX (with specific correction)

모든 agent가 PASS일 때만 최종 드래프트로 확정.

## Output Format

Save to: `paper-scout-draft-[YYYY-MM-DD].md`

```markdown
# CSNL Paper Scout — [DATE] Draft Posts

아래 [N]편의 최종 포스트입니다. 컨펌 후 study-paper-reading에 게시됩니다.

---

## Post 1 of [N] (Score: X — D[N] [DimName])

[Full Slack-formatted post block]

### Review Results
- Hook: PASS
- Visual: PASS (graphical abstract from [source], cosine: 0.68)
- Equation: [INCLUDED / NOT APPLICABLE] — [reason if included]
- Accuracy: PASS

---

[Repeat for each post]

## Scoring Summary

| Rank | Paper | Best Member | Best Dim | Score | Semantic Dist |
|------|-------|-------------|----------|-------|---------------|
| ... | ... | ... | ... | ... | ... |
```

## Handoff

> "드래프트 완료: [N]편 (모든 internal review 통과, 모든 visual/equation 최적화 완료). 직접 검토하시거나 `paper-scout-review`로 group peer review를 추가 진행할 수 있습니다."
