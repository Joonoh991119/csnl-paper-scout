# Paper Scout Scores — 2026-03-31 (v3: Full-Text + PI Network Crawl)

## Scan Summary
- Window: 2025-12-31 ~ 2026-03-31
- Method: PI network author crawl (17 PIs, 66 papers) + targeted search
- Full-text: Playwright PDF (all scored papers)
- Selected: **8 papers** (balanced across Group A/B/C)

---

## === GROUP B: RNN, Neural Geometry, WM Representation ===

### Paper 1: Memory recall errors reflect interacting sensory and mnemonic representations

**Serences lab — bioRxiv (2025-10-20)**
DOI: 10.1101/2025.10.20.683560

**Abstract:** VWM은 더 이상 환경에 존재하지 않는 정보를 유지. Abstract representation이 새로운 sensory input과 간섭하지 않는다는 설과, early sensory representations이 WM을 지원한다는 설이 대립. 이 연구는 sensory-evoked response가 mnemonic representation과 상호작용하여 recall error를 체계적으로 왜곡함을 보임. Sensory와 mnemonic representation의 interaction이 memory recall의 정확성을 결정.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **SK** | **9** | 6 | 6 | 5 | 5 | **9** | 6.2 |
| JYK | 6 | 4 | 5 | 4 | 5 | 6 | 4.8 |
| MJC | 5 | 4 | 4 | 3 | 3 | 5 | 3.8 |

**SK D1=9:** SK의 WMRepresentation 핵심 질문 = "EVC가 sensory input과 WM content를 geometry-preserving하되 orthogonal population subspace에 re-embedding". Serences의 결과는 sensory와 mnemonic representation이 **상호작용하여 recall error를 생성**함을 보임 — SK의 cross-generalization 실패 = different code 해석에 직접 증거이자, 그 interaction의 behavioral consequence를 제시.
> "sensory-evoked response interacts with mnemonic representation to systematically distort recall"

---

### Paper 2: Top-down feedback explains working memory traces in early visual cortex

**Rademaker lab — bioRxiv (2025-11-27)**
DOI: 10.1101/2025.11.27.690959

**Abstract:** EVC의 mnemonic content는 weak/latent state로 저장된다고 추정. 두 메커니즘 제안: top-down feedback vs short-term synaptic plasticity. 이 연구는 **top-down feedback이 EVC WM trace의 존재를 설명**할 수 있음을 보임. Anterior cortical sites에서의 feedback signal이 sensory cortex의 WM representation을 유지.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **SK** | **8** | **7** | 5 | 6 | 4 | **8** | 6.0 |
| JYK | 6 | 5 | 5 | 4 | 5 | 6 | 5.0 |

**SK D1=8:** "Top-down feedback → EVC WM trace" — SK의 중견 Grant 핵심 = "feedforward(sensory) vs feedback(memory) 신경적 분리". Rademaker가 feedback이 EVC의 WM trace를 설명한다는 결과는 SK의 dPCA sensory/mnemonic 분리에 메커니즘적 해석을 추가.
**SK D2=7:** SK는 "orthogonal subspace에 re-embedding"이라는 geometry 기반 설명을 제시하는데, Rademaker는 "top-down feedback" 메커니즘을 제시 — 같은 현상에 대한 두 competing explanation. SK의 가설이 지지되는지 아닌지 검토 필요.
> "Top-down feedback from anterior cortical sites can explain WM traces in EVC"

---

### Paper 3: An integrative approach to drift-diffusion dynamics in working memory

**Pascucci, D. — Neuron Preview (2025)**
DOI: 10.1016/j.neuron.2025.09.025

**Abstract:** Gu et al.의 Neuron 논문에 대한 preview. 두 canonical WM bias가 어떻게 emerge하고 interact하는지, behavior + neuroimaging + RNN modeling의 convergent evidence가 drift-diffusion dynamics가 memory state를 점진적으로 shape함을 보인다고 요약.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JYK** | **9** | 4 | 5 | **8** | 4 | **9** | 6.0 |
| MJC | 5 | 4 | 4 | 4 | 3 | 5 | 4.0 |

**JYK D1=9:** Pascucci의 이 preview는 JYK의 mentor Gu의 Neuron 논문에 대한 것. JYK의 RNN 프로젝트 = "Gu et al. 2025 확장". Pascucci(relevance-5 PI)가 Neuron에서 이 연구의 의의를 공식 인정. JYK의 연구 방향이 필드에서 중심에 있음을 확인.
**JYK D4=8:** Pascucci가 직접 comment를 쓴 것은 이 연구가 SD/WM bias 커뮤니티에서 landmark로 인정받았음을 의미. JYK의 확장 연구에 대한 경쟁적 관심이 높아질 것.

---

### Paper 4: Distributed and drifting signals for working memory load in human cortex

**Serences lab — bioRxiv (2025-09-15)**
DOI: 10.1101/2025.09.15.676305

**Abstract:** WM load 증가에 따른 behavioral cost가 IPS에 localized되는지 cortex 전체에 distributed되는지 논쟁. Pre-registered fMRI (N=12). WM load signal이 cortex 전체에 distributed되며, **load가 증가할수록 representation이 drift**하는 것을 발견.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **SK** | **7** | 4 | 6 | 5 | 5 | **7** | 5.4 |
| JYK | 6 | 3 | 5 | 4 | 4 | 6 | 4.4 |

**SK D1=7:** "Load 증가 → representation drift + distributed signal" — SK의 WMRepresentation에서 50 subjects fMRI로 EVC sensory/mnemonic code 분리를 연구하는데, Serences의 결과는 load에 따른 drift가 cortex-wide임을 보임. SK의 실험에서 set size 조건을 추가할 때 참고.

---

## === GROUP C: Visual Cortex, pRF, Natural Image Statistics ===

### Paper 5: A retinotopic reference frame for space throughout human visual cortex

**Dumoulin lab — bioRxiv (2025)**
DOI: 10.1101/2024.02.05.578862

**Abstract:** Eye movement에도 불구하고 안정적 지각. Spatiotopic (external) reference frame이 제안되었으나 retinotopy와 모순. 이 연구는 **human visual cortex 전체에서 retinotopic reference frame이 공간 표상에 사용**됨을 보임. Visual hierarchy를 통해 spatiotopic representation이 아닌 retinotopic coordinate가 지배적.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JHR** | **8** | 5 | 6 | 6 | 5 | **8** | 6.0 |
| SMJ | 5 | 3 | 5 | 3 | 5 | 5 | 4.2 |

**JHR D1=8:** JHR의 SpatialExtent = EVC pRF anisotropy(radiality dominant) vs perception(co-axiality dominant)의 mismatch 연구. Dumoulin의 "retinotopic reference frame이 visual hierarchy 전체에서 지배적" 결과는 JHR의 "V1-V4에서 radial→co-axial hierarchical shift" 연구에 **직접 활용 가능한 reference frame data**를 제공.
**JHR D4=6:** Dumoulin은 pRF의 foundational researcher. 이 결과가 JHR의 radial/co-axial framework와 어떻게 align되는지 검토 필수.
> "retinotopic reference frame for space throughout human visual cortex"

---

### Paper 6: The precision of attention controls attraction of population receptive fields

**Dumoulin lab — Journal of Vision (2025)**
DOI: 10.1167/jov.25.11.3

**Abstract:** Attention이 pRF를 attended position으로 attract. 이 연구는 attention의 **precision**이 이 attraction의 정도를 결정함을 보임. Spatial attention의 precision이 높을수록 pRF attraction이 강해지고, 이는 feature-based attention과 구분되는 spatial attention의 고유 메커니즘.

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JHR** | 6 | 4 | **8** | 6 | 5 | **8** | 5.8 |
| SMJ | 5 | 3 | 6 | 3 | 4 | 6 | 4.2 |

**JHR D3=8:** "Attention precision → pRF attraction" — JHR의 oriented grating pRF 실험에서 attention 조건에 따른 pRF 변화를 측정할 때 직접 방법론적 참고. Dumoulin의 "precision-controlled attraction" 패러다임을 JHR의 radial/co-axial anisotropy 측정에 적용 가능.

---

## === GROUP A: Bayesian, History Effects ===

### Paper 7: Large-scale mega-analysis indicates that serial dependence deteriorates perceptual decision-making

**Ozkirli, Chetverikov & Pascucci — Nature Human Behaviour (2025-12-22)**
DOI: 10.1038/s41562-025-02362-8

**(Full-text reviewed — see previous version for details)**

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JOP** | 5 | **9** | 6 | **8** | 6 | **9** | 6.8 |
| MSY | 4 | **8** | 5 | **7** | 5 | **8** | 5.8 |

---

### Paper 8: Serial Dependence operates on categorical rather than physical representations

**Costa & Collins — bioRxiv (2026-01-22)**
DOI: 10.64898/2026.01.22.700534

**(Full-text reviewed — see previous version for details)**

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **MSY** | **9** | 5 | 5 | **8** | 5 | **9** | 6.4 |
| JOP | 4 | **8** | 3 | 4 | 6 | **8** | 5.0 |
| BHL | **7** | 3 | 4 | 3 | 4 | **7** | 4.2 |

---

## Final Selection (8 papers, balanced across groups)

| # | Paper | Max | Primary | Group | Hook Pattern |
|---|-------|-----|---------|-------|-------------|
| 1 | **Serences — Sensory-mnemonic interaction** | **9** (SK) | SK | B | D1 Direct Advance |
| 2 | **Ozkirli — SD deteriorates** | **9** (JOP) | JOP, MSY | A | D2 Hypothesis Tension |
| 3 | **Costa — Categorical SD** | **9** (MSY) | MSY, BHL | A | D1+D4 Competitive |
| 4 | **Pascucci — Drift-diffusion preview** | **9** (JYK) | JYK | B | D1+D4 Competitive |
| 5 | **Rademaker — Top-down feedback EVC** | **8** (SK) | SK | B | D1 Direct + D2 Tension |
| 6 | **Dumoulin — Retinotopic reference** | **8** (JHR) | JHR | C | D1 Direct Advance |
| 7 | **Dumoulin — pRF attention precision** | **8** (JHR) | JHR | C | D3 Method Import |
| 8 | **Serences — WM load drift** | **7** (SK) | SK | B | D1 Direct Advance |

### Group Balance Check
- **Group A** (JOP, MSY, BYL): 2 papers (Ozkirli, Costa)
- **Group B** (JYK, MJC, SK): 4 papers (Serences×2, Rademaker, Pascucci)
- **Group C** (JHR, SMJ): 2 papers (Dumoulin×2)

### Member Coverage
| Member | Papers Tagged | Top Score |
|--------|-------------|-----------|
| SK | 4 | D1=9 (Serences sensory-mnemonic) |
| JOP | 2 | D2=9 (Ozkirli) |
| MSY | 2 | D1=9 (Costa categorical SD) |
| JYK | 1 | D1=9 (Pascucci drift-diffusion) |
| JHR | 2 | D1=8, D3=8 (Dumoulin×2) |
| BHL | 1 | D1=7 (Costa) |

### Revision Log (v2→v3)
- **SD 편향 해소:** v2에서 6편 중 5편이 SD 주제 → v3에서 8편 중 3편만 SD
- **PI network 기반 스캔:** Semantic Scholar API로 17명 PI의 66편 크롤링 → 관련도 평가
- **Group B 강화:** SK에 3편 (Serences sensory-mnemonic, Rademaker feedback, Serences WM load)
- **Group C 신규:** JHR에 2편 (Dumoulin retinotopic reference, pRF attention)
- **JYK 강화:** Pascucci의 Gu et al. Neuron preview (D1=9, D4=8)
- **Andriushchenko 유지 제외**, Kandemir 제외 (JHR에 더 직접적인 Dumoulin 논문으로 대체)
- **Pinchuk-Yacobi 제외** (JOP에 이미 Ozkirli가 있고, reframing 가치가 Dumoulin/Rademaker보다 낮음)
- **Fischer 제외** (SK에 더 직접적인 Serences/Rademaker가 있음)
