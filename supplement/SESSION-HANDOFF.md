# NAS Supplement Pipeline — Session Handoff (2026-04-03 11:05 KST)

## 파이프라인 현황

| Metric | Value |
|--------|-------|
| NAS PDFs | **725** |
| Embeddings | **5,604** |
| Trashbin | **335** |
| Pass list | 1,201 (262 VSS abstracts excluded) |
| Fetch failures | 156 (paywall 117 + SD 35 + Cell 4) |

## Relevance Verification v2.1 — 최종 결과

### Calibration Harness — ALL PASS

| Metric | Value | Target |
|--------|-------|--------|
| H1 False Trash | **0.00%** | <1% |
| H2 True Trash | **89.9%** | >80% |
| H3 Tier Separation | **38pt** | >20pt |
| H5 Review Volume | **1.1%** | <20% |

### DB 신뢰도

| Tier | 건수 | 비율 |
|------|------|------|
| auto_keep (≥45) | 425 | 58.6% |
| likely_keep (25-44) | 292 | 40.3% |
| review (15-24) | 8 | 1.1% |

### Signal 기여도

| Signal | Separation | 설명 |
|--------|-----------|------|
| S1 Embedding | +11.9 | 24 CSNL anchor cosine |
| S2 PI Author | +9.2 | first + co-author matching |
| S3 Keywords | +6.1 | 3-tier lexicon (~200 terms) |
| S6 Journal | +5.7 | target journal matching |
| S5 Read DB | +3.6 | tracked author count |
| S4 Project | +2.1 | 16 per-member project gist |

### v2 → v2.1 개선 (2026-04-03)

1. **S4 Project Match**: 5 group gists → 16 per-member expanded descriptions
   - Separation: 0.9 → 2.1pt
2. **S2 Co-author PI matching**: abstract에서 co-author 추출 → PI network 매칭
   - Separation: 0.8 → 9.2pt
3. **Review 186건 trashbin 이동**: 신경과학이지만 CSNL 프로젝트 미연결

## 파일 구조

```
supplement/
├── relevance_audit/
│   ├── relevance_scorer.py     ★ 6-signal scoring engine
│   ├── signal_configs.py       keyword lexicon, PI DB, thresholds
│   ├── verifiers.py            3 LLM verifiers (promotion-only)
│   ├── calibration.py          ground truth harness (H1-H5)
│   ├── agents/                 verifier agent definitions
│   └── results/v2/             scores, verifier results, calibration
├── rescue_unified.py           통합 rescue fetcher
├── embedder.py                 증분 임베더
└── candidates/                 failure registry, pass list
```

## TODO (우선순위)

### HIGH
1. **eLife web strategy → rescue_unified.py 통합**
2. **Cell Press 4건 Chrome relay**
3. **VPN → ScienceDirect 35건**

### MEDIUM
4. **S4 seed paper centroid** — project별 대표 논문 embedding centroid 사용
5. **Embedding model 업그레이드** — SPECTER2/SciBERT 검토
6. **Duplicate detection** — DOI dedup + title similarity

### LOW
7. **자동 re-scoring** — 새 PDF fetch 시 자동 6-signal scoring
8. **v1 코드 정리** — deprecated 파일 삭제

## 자동화

| Task | Schedule |
|------|----------|
| `paper-scout-embed-sync` | 매시간 |
| `paper-scout-rescue-retry` | 매일 06:00 |

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 관련 절대 금지
- JOP 외 DM 전송 금지
