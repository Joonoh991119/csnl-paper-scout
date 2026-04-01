# NAS Supplement Pipeline — Session Handoff (2026-04-01 12:30 KST)

## 파이프라인 현황

| Metric | Value |
|--------|-------|
| Pass list | 1,463 papers |
| NAS PDFs | 851 (3.53 GB) |
| Embeddings | 5,729 vectors (0 unembedded) |
| Failures | 627 remaining |
| Success rate | 57.1% |

## Failure 분류 (627건)

| Category | Count | Status | Action |
|----------|-------|--------|--------|
| JOV abstracts | 267 | `jov_abstract_no_fulltext` | VSS conference abstracts — full-text PDF 없음, 영구 제외 대상 |
| Other publishers | 314 | `failed_automated` | 자동 retry (daily 6AM task) |
| ScienceDirect | 39 | `needs_browser_elsevier` | IP 차단 — VPN 또는 rate limit 해제 후 수동 |
| Cell Press | 7 | `needs_browser_cell` | Browser relay 필요 (S2) |

## 해결된 전략 (이번 세션)

### Browser Relay Pattern (S2) — 핵심 발견
Cell.com PDF를 Chrome에서 로드 후 localhost relay로 저장하는 패턴:
1. `python3 rescue_unified.py --serve-only` (port 18765)
2. Chrome Extension으로 Cell.com PDF URL 탐색
3. JS `fetch(window.location.href)` → `POST localhost:18765`
4. `/tmp/elsevier_rescue/` → NAS로 이동

### PMC HTTPS Mirror (S1) — FTP 대안
`ftp://ftp.ncbi.nlm.nih.gov/...` → `https://ftp.ncbi.nlm.nih.gov/...` 변환으로 깨진 FTP tar.gz 해결.

## 7 ScienceDirect 미수집 DOI

```
10.1016/j.neuroimage.2023.119988   — Isherwood 2023, 7T MRI response inhibition
10.1016/j.neubiorev.2026.106627    — 2026 neurobiology review
10.1016/j.neubiorev.2026.106639    — 2026 emotion/allostatic
10.1016/j.cognition.2026.106454    — 2026 awareness/confidence
10.1016/j.cognition.2025.106340    — 2025 (PMC12797880 있으나 FTP 없음)
10.1016/j.neuroimage.2021.117909   — 2021 neuroimage
10.1016/j.cognition.2021.104763    — 2021 cognition (PMC7614705 있으나 FTP 없음)
```

**차단 원인**: SNU IP 147.47.66.137에서 ScienceDirect /pdfft endpoint 전면 차단. Article page는 접근 가능하나 PDF download만 선택적 블록.
**실패한 방법**: JS fetch, JS navigation, simulated View PDF click, Elsevier API (key 필요), Chrome cookies+requests, Google Scholar.
**해결 방법**: VPN/다른 IP, 또는 multi-day cooldown 후 재시도.

## 7 Cell Press 미수집 DOI (browser relay 필요)

Registry에서 `needs_browser_cell` status인 DOI. Browser relay 패턴(S2)으로 해결 가능.

## 파일 구조

```
supplement/
├── rescue_unified.py          ★ 통합 rescue fetcher (신규)
├── fetch-rescue-SKILL.md      ★ Fetch rescue skill (신규)
├── SESSION-HANDOFF.md         ★ 이 파일
├── rescue_ftp.py              Elsevier PMC FTP rescue
├── rescue_oa_ftp.py           전체 OA FTP rescue
├── embedder.py                증분 임베더
├── fetcher_batch.py           Playwright batch fetcher
├── candidates/
│   ├── failure_registry.json  ★ DOI별 실패 이력 (신규)
│   ├── elsevier_still_blocked.json  7건 ScienceDirect 미수집
│   ├── 02_resolved_pass.json  1,463건 pass list
│   └── 03_fetch_log.json      fetch 기록
└── logs/                      실행 로그
```

## 자동화

| Task | Schedule | 역할 |
|------|----------|------|
| `paper-scout-embed-sync` | 매시간 | 새 PDF → embedding 자동 |
| `paper-scout-rescue-retry` | 매일 06:00 | 실패 DOI 자동 retry (S1,S3-S6, max 50/일) |

## 다음 세션 우선순위

1. **Cell Press browser relay** (7건) — `rescue_unified.py --serve-only` + Chrome Extension
2. **ScienceDirect 차단 해제 확인** — `rescue_unified.py --publisher elsevier --dry-run`
3. **JOV abstracts 결정** — 267건 VSS abstracts를 pass list에서 영구 제외할지 결정
4. **eLife retry** — 60건, PMC deposit 없는 것은 browser relay 필요
5. **Skill 패키징** — `rescue_unified.py`를 csnl-paper-scout repo에도 반영

## Credentials
- `credentials.json` (gitignored): `openrouter_api_key`
- NAS: `/Volumes/CSNL_new/Memory/Papers/`
- Relay server: `http://127.0.0.1:18765`

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 관련 절대 금지
- JOP 외 DM 전송 금지
