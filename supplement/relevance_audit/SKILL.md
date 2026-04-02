---
name: relevance-audit
description: NAS 논문 DB에서 CSNL 연구와 무관한 논문을 임베딩 + LLM 추론으로 식별하고 제거하는 2단계 검증 파이프라인
license: Internal
metadata:
  skill-author: CSNL
  version: "1.0"
---

# Relevance Audit Pipeline

NAS embedding DB (5,810 papers)에서 CSNL 연구 분야와 무관한 논문을 체계적으로 식별·제거하는 파이프라인.

## Architecture

```
Task A: Embedding Outlier Detection
────────────────────────────────────
embeddings.npz ──► cosine distance to 24 CSNL anchors
                   ──► bottom N% outliers (flag candidates)
                       ──► 3× Relevance Judge (LLM reasoning)
                           ──► Consensus Arbiter ──► trash / keep

Task B: Abstract-Based Screening
─────────────────────────────────
All PDFs ──► extract abstract (first 2 pages)
             ──► LLM screening against CSNL themes + PI network
                 ──► flag candidates
                     ──► 3× Relevance Judge (LLM reasoning)
                         ──► Consensus Arbiter ──► trash / keep
```

## 실행

```bash
# Task A: 임베딩 기반 이상치 탐지
python3 relevance_audit.py --task A --dry-run
python3 relevance_audit.py --task A --apply

# Task B: 초록 기반 스크리닝 (느림 — LLM 호출 많음)
python3 relevance_audit.py --task B --dry-run
python3 relevance_audit.py --task B --apply

# 전체
python3 relevance_audit.py --task all --apply
```

## Agent Team

| Agent | 역할 | 모델 |
|-------|------|------|
| Outlier Detector | 임베딩 거리 계산, bottom-N% 추출 | NumPy (non-LLM) |
| Abstract Extractor | PDF에서 초록 텍스트 추출 | pypdf (non-LLM) |
| Relevance Judge ×3 | CSNL 관련성 판단 (독립 추론) | qwen/qwen3-32b (via OpenRouter) |
| Consensus Arbiter | 3명 판사 합의 도출 → 최종 결정 | Rule-based (2/3 majority) |

## Harness (검증)

| Dimension | 설명 | 방법 |
|-----------|------|------|
| H1: Precision | 제거 대상이 정말 무관한가 | 랜덤 샘플 20건 수동 검증 |
| H2: Recall | 무관한 논문이 남아있지 않은가 | Task B가 Task A 미포착분 보완 |
| H3: Judge Agreement | 판사 간 일치율 | Fleiss' kappa ≥ 0.6 |
| H4: False Positive Audit | Keep 판정 중 실제 무관한 것 | 랜덤 샘플 20건 역검증 |

## Judge Prompt 구조

```
당신은 CSNL (Cognitive and Systems Neuroscience Laboratory) 연구 관련성 판사입니다.

CSNL 연구 분야:
- Visual Working Memory (VWM): 정밀도, 용량, drift, serial dependence
- Bayesian Decision Making (BDM): observer models, drift-diffusion, evidence accumulation
- Neural Dynamics (NN): attractor networks, population coding, RNN models
- fMRI & Visual Cortex (fVC): retinotopy, pRF, layer-specific BOLD, 7T
- Categorization & Generalization (CG): boundary effects, prototype models
- Methodology (METH): psychophysics, RSA, IEM, dPCA, meta-analysis

PI Network: 182명의 인지/계산 신경과학 연구자 네트워크

판단 기준:
1. 이 논문의 연구 질문이 위 분야 중 하나에 직접 기여하는가?
2. CSNL 멤버가 자신의 프로젝트에 이 논문을 인용/활용할 수 있는가?
3. PI network의 연구자가 저자인가? (동명이인 주의)

출력 형식:
VERDICT: RELEVANT | IRRELEVANT | BORDERLINE
CONFIDENCE: HIGH | MEDIUM | LOW
REASON: (1-2문장 한국어)
FIELD: (논문의 실제 분야)
PI_MATCH: (PI 이름 매칭 여부, 동명이인 가능성)
```

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 관련 절대 금지
- 논문 삭제는 trashbin 이동만 (영구 삭제 아님)
- Embedding DB에서 제거 시 반드시 백업
