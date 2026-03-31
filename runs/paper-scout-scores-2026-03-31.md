# Paper Scout Scores — 2026-03-31 (Full-Text Reviewed)

## Scan Summary
- Window: 2025-12-31 ~ 2026-03-31 (90 days)
- Sources: bioRxiv, Nature Human Behaviour, eLife, AP&P, Research Square
- Method: Playwright full-text PDF (6/6 fetched)
- DB dedup: 1,069 entries checked
- Selected (threshold ≥7): **5 papers**

---

## Paper 1: Serial Dependence operates on categorical rather than physical representations: evidence from behavior and EEG

**Costa, P. & Collins, T. — bioRxiv (2026-01-22)**
DOI: 10.64898/2026.01.22.700534 | 24pp, 10 figs

**Full-text key findings:**
- Face morphs from 3 emotional prototypes (anger, fear, sadness)로 perceptual similarity matrix 구축
- Odd-one-out 실험으로 emotional expressions가 categorically perceived됨을 확인
- SD가 physical similarity가 아닌 **perceptual (categorical) distance**에 tuned
- EEG RSA: neural responses가 emotional ambiguity를 encode, category membership이 아님
- "Models combining feature tuning with categorical structure best accounted for behavioral biases"
- **Past stimuli의 memory-based representation이 sensory representation과 가장 diverge할 때 SD가 strongest**

### Scoring (revised from full-text)

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **MSY** | **9** | 5 | 5 | **8** | 5 | **9** | 6.4 |
| JOP | 4 | **8** | 3 | 4 | 6 | **8** | 5.0 |
| BHL | **7** | 3 | 4 | 3 | 4 | **7** | 4.2 |
| BYL | 4 | 4 | 3 | 2 | 3 | 4 | 3.2 |

**MSY D1=9:** MSY의 CatVsMag 프로젝트 = face gender spectrum에서 categorical vs magnitude task가 다른 SD를 보임. Costa & Collins의 결과는 정확히 같은 구조: categorical representation이 SD를 결정. MSY는 StyleGAN2 + hierarchical Bayesian model을 사용, Costa는 EEG RSA — **방법론적 상보성이 높아 즉시 활용 가능.**
> Quote: "attractive serial dependence tuned to perceptual distance rather than physical similarity"

**MSY D4=8:** Pascucci 그룹(Ozkirli 공저)이 아닌 Collins 그룹이 독립적으로 categorical SD를 발표. MSY의 CatVsMag가 아직 미발표이므로 **직접 경쟁은 아니나**, 같은 결론에 도달하는 그룹이 늘어나고 있음을 시사. D4를 9→8로 하향 (직접 경쟁 그룹이 아닌 독립 발견).

**JOP D2=8:** Full-text에서 "memory-based representations diverged most from sensory representations → strongest SD" 발견. JOP의 RingRepSca에서 relative vs absolute space 독립성 가설 — categorical boundary가 일종의 reference frame이 될 수 있다는 tension. 또한 중견 Grant의 "feedforward(sensory) vs feedback(memory)" 프레임과 직접 연결: memory-based representation이 sensory에서 diverge할수록 SD가 강해진다.
> Quote: "Stimuli for which memory-based representations diverged most from sensory representations showed the strongest attractive serial dependence"

**BHL D1=7:** BHL의 SerialDep_Feature — secondary features의 SD 역할 연구. Costa의 "categorical structure가 SD를 결정" 결과는 BHL이 feature-level SD 메커니즘을 이해하는 데 직접 참조 가능.

---

## Paper 2: Large-scale mega-analysis indicates that serial dependence deteriorates perceptual decision-making

**Ozkirli, A., Chetverikov, A. & Pascucci, D. — Nature Human Behaviour (2025-12-22)**
DOI: 10.1038/s41562-025-02362-8 | 14pp, 2 figs

**Full-text key findings:**
- 지난 10년간 SD 연구의 most extensive dataset 컴파일
- "Superiority effect" (SD가 perceptual decision을 improve한다는 주장)에 대한 대규모 검증
- **결론: SD가 perceptual decision-making을 deteriorate** — superiority effect 반박
- Stimulus-specific biases를 modelling 전에 제거 (confound 처리)
- "Need to rethink serial dependence and its role in human perception, cognition and behaviour"
- Discussion에서 "SD는 low-level perceptual bias가 아니라 fundamental aspect of brain function"으로 재정의

### Scoring (revised)

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JOP** | 5 | **9** | 6 | **8** | 6 | **9** | 6.8 |
| MSY | 4 | **8** | 5 | **7** | 5 | **8** | 5.8 |
| JSL | 4 | **7** | 4 | 5 | 4 | **7** | 4.8 |
| BYL | 3 | 5 | 4 | 2 | 4 | 5 | 3.6 |

**JOP D2=9:** CSNL의 history effect 연구 전체가 SD를 adaptive Bayesian process로 전제 (BMBU, granularity → belief updating). Ozkirli의 "SD deteriorates decision-making"은 이 전제에 정면 도전. Lab-wide framework 재검토가 필요할 수 있음.
> Quote: "Contrary to the proposed superiority effect, our findings indicate that serial dependence deteriorates rather than improves perceptual decision-making"

**JOP D4=8:** Pascucci는 CSNL PI network relevance-5. Nature Human Behaviour 논문은 SD 커뮤니티 전체에 파급력. JOP의 RingRepSca 및 Time 프로젝트가 SD의 functional role에 의존하므로 방어적 논증 준비 필요.

**JOP D3=6 (신규):** Full-text에서 "stimulus-specific biases를 prior에 제거" 방법론이 상세 기술됨. JOP의 MCMC fitting에서 SD와 stimulus-specific bias를 분리하는 방법론적 참고.

**MSY D2=8:** CatVsMag에서 SD가 generative model의 adaptive reflection이라는 해석. Ozkirli가 이를 부정하면 MSY의 theoretical framework에도 영향.

---

## Paper 3: A direct neural signature of serial dependence in working memory

**Fischer, C., Kaiser, J. & Bledowski, C. — eLife (2025-2026)**
DOI: 10.7554/eLife.99478 | 34pp, 13 figs

**Full-text key findings:**
- MEG + retro-cue WM task (sequential motion directions)
- Multivariate analysis로 두 motion directions 모두 reconstruct
- **Current trial의 reconstructed direction이 previous trial target에 attractively shifted** — behavioral bias mirror
- 시간적 해상도: **post-encoding time points에서 neural bias 출현** (encoding 중이 아님)
- "Serial dependence affects memorized information during **read-out and reactivation** processes"
- Visual cortex의 fMRI 연구(기존)는 repulsive neural bias 보였으나, MEG는 attractive bias — temporal resolution 차이
- Frontal + parietal regions이 memory trace storage와 transfer에 관여

### Scoring (revised)

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **SK** | **8** | 5 | **8** | 5 | 5 | **8** | 6.2 |
| JYK | 6 | 4 | **7** | 4 | 5 | **7** | 5.2 |
| MJC | 5 | 4 | 6 | 3 | 4 | 6 | 4.4 |

**SK D1=8 (↑):** Full-text에서 "fMRI에서는 repulsive neural bias, MEG에서는 attractive" — 이 modality 차이가 SK의 WMRepresentation 연구에 직접적. SK는 fMRI dPCA로 sensory vs mnemonic code 분리를 연구하는데, Fischer의 결과는 **fMRI가 잡는 것은 sensory repulsion이고, 실제 memory code의 attractive bias는 post-encoding에서 발생**함을 시사. SK의 "cross-generalization 실패 = different code" 해석에 temporal dimension을 추가.
> Quote: "neural bias emerged at later, post-encoding time points...serial dependence affects memorized information during read-out and reactivation"

**SK D3=8:** MEG multivariate reconstruction methodology가 SK의 fMRI decoding + dPCA 접근의 temporal 보완. 방법론적으로 cross-modal validation framework을 구축할 수 있음.

**JYK D3=7:** "Post-encoding에서 bias 발생" — JYK의 RNN에서 persistent vs sequential coding spectrum과 연결. RNN의 time-resolved dynamics에서 어느 시점에 drift가 시작되는지를 Fischer의 MEG temporal profile로 constraintㅇ할 수 있음.

---

## Paper 4: Serial Dependence Predicts Generalization in Perceptual Learning

**Pinchuk-Yacobi, N., Sagi, D. & Bonneh, Y. — bioRxiv (2026-02-27)**
DOI: 10.1101/2025.02.06.636846 | 21pp, 5 figs

**Full-text key findings:**
- 200,000+ trials, texture discrimination task (TDT), 50 observers
- 3 conditions으로 generalization을 differential modulation
- **SDE가 이전 보고보다 시간적으로 더 멀리 도달 (8일 훈련 후에도 지속)**
- **Individual SDE magnitude → learning transfer across locations 예측**
- "Extended temporal integration reduces over-fitting to specific context"
- Generalization 촉진 조건에서 larger long-range SDEs

### Scoring (revised)

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JOP** | 4 | 6 | 5 | 3 | **8** | **8** | 5.2 |
| JSL | 4 | 3 | 3 | 3 | 5 | 5 | 3.6 |
| BYL | 3 | 4 | 3 | 2 | 5 | 5 | 3.4 |

**JOP D5=8:** SD를 "momentary bias" → "long-term learning facilitator"로 완전히 재프레이밍. JOP의 history effect 프로젝트에서 SD의 기능적 의미를 새로운 시간 축(short-term deterioration vs long-term facilitation)으로 확장. Ozkirli 2025의 "SD deteriorates"와 대비하면 **SD의 이중적 역할 (short-term cost, long-term benefit)**이라는 통합 프레임이 가능.
> Quote: "extended temporal integration, captured by SDEs, reduces over-fitting to a specific context, providing a principled framework for when and why perceptual learning generalizes"

**JOP D3=5 (신규):** 200K+ trials의 대규모 재분석 방법론. MCMC fitting에서의 long-range dependency 분석 방법 참고.

---

## Paper 5: Serial dependence is stronger for peripheral than for central vision

**Kandemir, G. & Olivers, C.N.L. — Attention, Perception & Psychophysics (2026-01-08)**
DOI: 10.3758/s13414-025-03208-1 | 18pp, 9 figs

**Full-text key findings:**
- 3 experiments (Exp1: WM task, Exp2: spatial cueing, Exp3: low contrast + equal probability)
- **모든 실험에서 peripheral > central SD** (15° eccentricity)
- **Current item의 location이 핵심 driver** (previous item location이 아님)
- Spatial cueing (pre-knowledge of location)이 eccentricity effect에 영향 없음
- Reduced contrast/differential probability도 결론 불변
- "Responses more precise for central stimuli (larger k values)" — peripheral에서 precision 낮음 + SD 강함

### Scoring (revised)

| Member | D1 | D2 | D3 | D4 | D5 | Max | Mean |
|--------|----|----|----|----|----|----|------|
| **JHR** | 5 | 4 | 5 | 3 | **7** | **7** | 4.8 |
| SMJ | 4 | 3 | 4 | 3 | 5 | 5 | 3.8 |
| JSL | 4 | 3 | 3 | 3 | 4 | 4 | 3.4 |

**JHR D5=7:** Full-text에서 "peripheral에서 precision 낮음 + SD 강함"이 핵심. JHR의 pRF anisotropy 연구에서 **eccentricity에 따른 radial/co-axial bias 변화와 SD의 eccentricity dependence를 연결하는 새로운 프레임**. pRF size가 eccentricity에 따라 커지는 것과 SD 강도의 상관 — precision-SD tradeoff로 해석 가능.
> Quote: "this bias was always larger in the periphery relative to the central position, and it was mainly the current item's location that drove this effect"

**JHR D3=5 (신규):** 3 experiments design (WM task, cueing, contrast control)이 체계적. JHR의 oriented grating pRF 실험에서 eccentricity 조건 설계 참고.

---

## Selection Summary (Final — Full-Text Revised)

| Rank | Paper | Max | Tiebreak (Mean) | Primary | Hook Pattern |
|------|-------|-----|-----------------|---------|-------------|
| 1 | Ozkirli 2025 — SD deteriorates decision | **9** | **6.8** | JOP | Pattern 2 (Hypothesis Tension) |
| 2 | Costa & Collins 2026 — Categorical SD | **9** | **6.4** | MSY | Pattern 1 (Competitive Alert) |
| 3 | Fischer 2025 — Neural SD in WM | **8** | **6.2** | SK | Pattern 3 (Method Import) |
| 4 | Pinchuk-Yacobi 2026 — SD → Learning | **8** | **5.2** | JOP | Pattern 5 (Reframing) |
| 5 | Kandemir 2026 — Peripheral SD | **7** | **4.8** | JHR | Pattern 5 (Reframing) |

**제외:** Andriushchenko 2025 (VWM × SD) — full-text 검토 결과 MJC D1=7이지만 **3개 실험 중 2개에서 유의미한 차이 없음 (null result dominant)**. Mean=4.0으로 낮아 threshold 경계. Slack 게시 대비 가성비 낮음으로 제외.

### Revision Log
| Paper | Change | Reason |
|-------|--------|--------|
| Ozkirli | JOP D3 0→6 | Full-text: stimulus-specific bias 제거 방법론 상세 |
| Ozkirli | JOP D4 7→8 | Pascucci relevance-5 + NHB impact |
| Costa | MSY D4 9→8 | 직접 경쟁 아닌 독립 발견으로 하향 |
| Fischer | SK D1 7→8 | fMRI vs MEG modality contrast가 SK 연구에 직접적 |
| Fischer | JYK D3 유지 7 | Temporal profile → RNN constraint 확인 |
| Pinchuk-Yacobi | JOP D3 신규 5 | 200K trial 재분석 방법론 |
| Kandemir | JHR D3 신규 5 | 3-experiment systematic design |
| Andriushchenko | **제외** | Null result dominant, mean=4.0 |
