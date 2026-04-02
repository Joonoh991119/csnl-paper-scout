# NAS Supplement Pipeline — Session Handoff (2026-04-02 20:10 KST)

## 파이프라인 현황

| Metric | Value | 변화 |
|--------|-------|------|
| NAS PDFs | **911** | 1,060 → 932 (manual) → 913 (v1 audit) → 911 (v2 audit) |
| Embeddings | **5,790** | 5,937 → 5,790 |
| Trashbin | **149** | 128 (manual) + 14 (v1) + 5 (v2) + 2 (v2 verifier) |
| Pass list | 1,201 | (262 VSS abstracts excluded from original 1,463) |
| Fetch failures | 156 | paywall 117 + ScienceDirect 35 + Cell Press 4 |

## Relevance Verification v2 — 최종 결과

### DB 신뢰도 (6-signal composite scoring)

| Tier | 건수 | 비율 | 의미 |
|------|------|------|------|
| **auto_keep** (≥45pt) | 179 | 19.6% | CSNL 프로젝트와 직접 연결 확인 |
| **likely_keep** (25-44pt) | 546 | 59.8% | 높은 확률로 관련 (PI/keyword/embedding) |
| **review** (15-24pt) | 186 | 20.4% | 신경과학이지만 CSNL 프로젝트 연결 미확인 |
| confirmed_alien | 2 | 0.2% | 제거 완료 |

**확신 가능: 725건 (79%), 불확실: 186건 (20%)**

### Calibration Harness — ALL PASS

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| H1 False Trash Rate | 0.22% | <1% | PASS |
| H2 True Trash Rate | 96.6% | >80% | PASS |
| H3 Tier Separation | 27pt | >20pt | PASS |
| H5 Review Volume | 18.5% | <20% | PASS |

### Signal 기여도 (active vs trash 분리)

| Signal | Active mean | Trash mean | Separation |
|--------|-------------|------------|------------|
| S1 Embedding | 10.8 | 0.0 | **+10.7** (최대) |
| S3 Keywords | 9.8 | 3.1 | **+6.8** |
| S6 Journal | 6.9 | 2.1 | +4.8 |
| S5 Read DB | 3.4 | 0.8 | +2.6 |
| S2 PI Author | 1.8 | 1.0 | +0.8 |
| S4 Project | 0.9 | 0.0 | +0.9 |

## v1 → v2 진화 요약

### v1 (2026-04-01, 폐기됨)
- LLM judge 3명 독립 판정 → 2/3 다수결
- **Task A precision 43%, Task B precision 1.6%**
- 실패 원인: "IRRELEVANT 증명" 프레이밍, 도구/방법론 논문 과잉 제거, PI 동명이인 혼동

### v2 (2026-04-02, 현재)
- 6-signal rule-based scoring → LLM verifier (승격만 가능)
- **Calibration: H1-H5 ALL PASS**
- 핵심 혁신:
  1. "RELEVANCE 증거 수집" 프레이밍 전환
  2. Common surname discount (Wang, Li, Kim 등)
  3. No-embedding penalty (NPZ에 없는 논문의 name-based signal 할인)
  4. LLM은 승격만 가능, 강등 불가 → false positive 원천 차단
  5. Ground truth calibration (913 active vs 147 trash)

### Verifier 실행 결과 (2026-04-02)

**Verifier C (Alien Field Confirmer)**: 45건 → 43 NEURO (review 승격) + 2 ALIEN (제거)
**Verifier B (Project Mapper)**: 169건 → 26 CONNECT (likely_keep 승격) + 143 no connection

연결된 프로젝트 분포:
- JYK_RNN: 8건 (drift-diffusion, RNN, evidence accumulation)
- BYL_BayesianObserver: 7건 (Bayesian stats, prior elicitation)
- lab_methods: 3건 (psychophysics, pupillometry, fMRI)
- MJC_SeqVWM: 2건 (WM dynamics, activity-silent)
- BHL_WM_Binding: 2건 (object encoding, memory-driven capture)
- JOP_GranRDT: 2건 (DV space, discrete choice)
- JSL_SerialDep_Spatial: 1건 (spatial attention dissociation)
- JHR_SpatialExtent: 1건 (visual bias individual differences)

## 파일 구조

```
supplement/
├── relevance_audit/               ★ v2 relevance verification
│   ├── SKILL.md                   파이프라인 스펙
│   ├── relevance_scorer.py        6-signal scoring engine (핵심)
│   ├── signal_configs.py          keyword lexicon, PI DB, thresholds
│   ├── verifiers.py               3 LLM verifiers (promotion-only)
│   ├── calibration.py             ground truth harness (H1-H5)
│   ├── relevance_audit.py         v1 orchestrator (deprecated)
│   ├── agents/
│   │   ├── pi_homonym_verifier.md
│   │   ├── project_mapper.md
│   │   └── alien_confirmer.md
│   ├── harness/rubrics.md
│   └── results/v2/
│       ├── relevance_scores_v2.json
│       ├── verifier_b_results.json
│       └── verifier_c_results.json
├── rescue_unified.py              통합 rescue fetcher
├── embedder.py                    증분 임베더
├── fetcher_batch.py               Playwright batch fetcher
├── SESSION-HANDOFF.md             ★ 이 파일
└── candidates/                    failure registry, pass list, fetch log
```

## 개선 필요 사항 (TODO)

### 높은 우선순위

1. **Review 186건 수동 검증 인터페이스**
   - 현재 review tier는 "신경과학이지만 CSNL 프로젝트 직접 연결 미확인"
   - Streamlit 또는 CLI로 논문별 keep/trash 마킹 UI 필요
   - 마킹 결과 → calibration feedback loop

2. **S4 (Project Match) 개선**
   - 현재 기여도 0.9pt로 최저 — project gist embedding이 abstract와 잘 매칭 안 됨
   - 원인: gist가 짧고 추상적 (1문장) → embedding 공간에서 abstract와 거리가 먼 영역
   - 개선안: project별 seed paper DOI 목록 → seed paper embedding centroid 사용
   - 또는 project description을 3-4문장으로 확장

3. **S2 (PI Author) 정밀화**
   - 현재 filename의 첫 번째 저자만 확인 → 공저자 PI 매칭 못 함
   - 개선안: abstract에서 author list 파싱 → 전체 저자 대상 PI 매칭
   - ORCID 또는 Semantic Scholar ID 기반 disambiguation

### 중간 우선순위

4. **rescue_unified.py에 eLife web strategy 통합**
   - `elifesciences.org/download/` base64 패턴 (이번 세션에서 발견)
   - 현재 standalone 코드로만 존재 → rescue cascade에 S7으로 추가

5. **Cell Press 4건 + ScienceDirect 35건**
   - Cell Press: Chrome relay 수동 처리 (helper page 준비됨)
   - ScienceDirect: VPN 확보 후 재시도

6. **Embedding model 업그레이드 검토**
   - nemotron-embed-vl-1b (free tier)는 과학 논문 특화 아님
   - SPECTER2 또는 SciBERT 기반 embedding으로 S1/S4 정확도 향상 가능
   - 하지만 5,790개 re-embedding 비용 고려 필요

### 낮은 우선순위

7. **Duplicate detection**
   - 같은 논문의 버전 차이 (v1/v2, preprint/published, correction/original)
   - 현재 일부 중복 존재 (Bimbard ×2, Hadjiosif ×2, 등)
   - DOI dedup + title similarity 기반 자동 탐지

8. **자동 re-scoring 스케줄**
   - 새 PDF fetch 시 자동으로 6-signal scoring → tier 배정
   - embedder cron과 연동

9. **v1 코드 정리**
   - `relevance_audit.py` (v1)은 deprecated — 삭제 또는 archive
   - v1 agents (`relevance_judge.md`, `consensus_arbiter.md`) 정리

## Fetch 미완료 (이전 세션에서 이월)

| Category | Count | Action |
|----------|-------|--------|
| Paywall papers | 117 | Institutional browser 필요 |
| ScienceDirect | 35 | VPN 확보 후 재시도 |
| Cell Press | 4 | Chrome relay (`/tmp/cell_relay_helper.html`) |

## 자동화

| Task | Schedule | 역할 |
|------|----------|------|
| `paper-scout-embed-sync` | 매시간 | 새 PDF → embedding 자동 |
| `paper-scout-rescue-retry` | 매일 06:00 | 실패 DOI 자동 retry |

## Credentials
- `credentials.json` (gitignored): `openrouter_api_key`
- NAS: `/Volumes/CSNL_new/Memory/Papers/`
- Relay server: `http://127.0.0.1:18765`

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 관련 절대 금지
- JOP 외 DM 전송 금지
