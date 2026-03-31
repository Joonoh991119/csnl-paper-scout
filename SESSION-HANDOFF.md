# Paper Scout Session Handoff — 2026-03-31 (updated)

## 현재 상태

### 완료
- **v2 포스트 포맷**: figure+hook(caption) → thread(metadata+summary+targeting+tags)
  - Hook 중복 제거 (caption에만), Score table/evidence quotes 제거, Summary 1-2문장 추가
- **Blind Evaluator v2**: adversarial B1-B5 평가 + auto-escalation + revision loop
  - `harness/blind_eval.py`, `agents/blind_evaluator.md`
  - Leniency threshold 0.85 → 초과 시 자동 escalation (3단계)
- **Figure 확보**: 5편 모두 (Pascucci는 AI 생성)
- **5편 JOP DM 전송 완료**
- **SK context-bundle 수정**: KimEtal 2026 실제 연구 반영, hallucination 수정

### 선정된 5편
| # | Paper | Primary | Score | Figure |
|---|-------|---------|-------|--------|
| 1 | Serences — Sensory-mnemonic interaction | SK D1=9 | bioRxiv 2025 | RMSE boxplots |
| 2 | Ozkirli — SD deteriorates decision | JOP D2=9 | NHB 2025 | 49-dataset scatter |
| 3 | Costa — Categorical SD (EEG) | MSY D1=9 | bioRxiv 2026 | RSA matrices |
| 4 | Pascucci — Drift-diffusion preview | JYK D1=9 | Neuron 2025 | AI graphical abstract |
| 5 | Rademaker — Top-down feedback EVC | SK D1=8 | bioRxiv 2025 | Model architecture |

### Blind Eval 결과 (adversarial v2)
| Paper | R1 Score | Final | Rounds | Key Issue |
|-------|----------|-------|--------|-----------|
| Serences | 6/8 | PASS | 1 | B3=2 targeting 구체적 |
| Ozkirli | 6/8 | PASS | 1 | B1=1 effect size 부족 |
| Costa | BHL 5→3→6 | PASS | 3 | BHL targeting 자동 수정 |
| Pascucci | 2→6 | PASS | 2 | summary 재작성 |
| Rademaker | 6/8 | PASS | 1 | B2=1 figure가 모델 |

## 다음 세션에서 해야 할 것

### 1. JOP 피드백 수집
### 2. Summary에 Quantitative Detail 추가 (B5 공통 피드백)
### 3. 결과 Figure 확보 (Serences boxplots, Rademaker 모델→결과)
### 4. 채널 게시 준비 (PI 승인 후)

## SK 연구 정확한 프레이밍 (hallucination 방지)
- **올바름**: geometry-preserving subspace rotation, re-embedded code, nearly orthogonal (71°), ring-like manifold
- **금지**: "abstract representation 가설" (존재하지 않음)
- **Serences 관계**: SK의 low-interference multiplexing에 대한 behavioral tension

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 멘션 절대 금지
- JOP 외 DM 전송 금지, 채널 게시는 명시적 승인 후
- 이보연=Boyun=BYL, 이보현=Bohyun=BHL

## Credentials
- `credentials.json` (gitignored): bot token + OpenRouter key
- `.env` (gitignored): OPENROUTER_API_KEY
- JOP DM: D0AMRACTLBH
