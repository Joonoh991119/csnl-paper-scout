# NAS Supplement Pipeline — Session Handoff (2026-04-01 16:25 KST)

## 파이프라인 현황

| Metric | Value |
|--------|-------|
| Pass list | 1,201 papers (was 1,463 — 262 VSS abstracts excluded) |
| NAS PDFs | 1,060 (≈4.8 GB) |
| Embeddings | 5,937 vectors (0 unembedded) |
| Failures | 156 remaining |
| Coverage | 88.3% |

## Failure 분류 (156건)

| Category | Count | Status | Action |
|----------|-------|--------|--------|
| Paywall papers | 117 | `failed_automated` | No OA/PMC source; need institutional browser |
| ScienceDirect | 35 | `needs_browser_elsevier` | IP 147.47.66.137 blocked; VPN required |
| Cell Press (Curr Biol) | 4 | `needs_browser_cell` | Browser relay — `open /tmp/cell_relay_helper.html` |

## 이번 세션 성과 (2026-04-01)

### 209 PDFs rescued — strategies:
- **Unpaywall OA**: 80건 (direct PDF links from OA repositories)
- **Preprints**: 60건 (bioRxiv v1-v5, arXiv, PsyArXiv direct download)
- **eLife web parse**: 59건 (★ new strategy — base64 encoded download URLs)
- **PMC FTP tar.gz**: 10건 (Cell Press, ScienceDirect → PMC OA deposits)

### Key discoveries:
1. **eLife base64 URL pattern**: `elifesciences.org/download/aHR0cHM6...` — parse article page for `elife-{id}-v{N}.pdf` encoded URL. Works for all eLife articles.
2. **bioRxiv versioning**: Many preprints need v2-v5, not just v1.
3. **VSS abstracts**: 262 JOV papers confirmed as conference abstracts (issue 9, 10, 14) — permanently excluded. 5 papers reclassified as real articles.
4. **ScienceDirect**: Still blocked at SNU IP. No VPN available on this machine.

## 4 Cell Press 미수집 DOI

All Current Biology — need Chrome relay:
```
10.1016/j.cub.2022.10.053  — Saccade vigor (PMC9795813, but not OA)
10.1016/j.cub.2020.10.034  — V1 Projection Zone (cell.com 403)
10.1016/j.cub.2021.09.036  — Inter-electrode EEG (PMC8612967, not OA)
10.1016/j.cub.2023.09.062  — Complex spikes Purkinje (PMC10751015, not OA)
```

Helper page: `open /tmp/cell_relay_helper.html`

## 파일 구조

```
supplement/
├── rescue_unified.py          ★ 통합 rescue fetcher
├── rescue_browser.py          ★ Playwright browser fetcher (new)
├── fetch-rescue-SKILL.md      Fetch rescue skill
├── SESSION-HANDOFF.md         ★ 이 파일
├── rescue_ftp.py              Elsevier PMC FTP rescue
├── rescue_oa_ftp.py           전체 OA FTP rescue
├── embedder.py                증분 임베더
├── fetcher_batch.py           Playwright batch fetcher
├── candidates/
│   ├── failure_registry.json  ★ DOI별 실패 이력
│   ├── elsevier_still_blocked.json  ScienceDirect 미수집
│   ├── 02_resolved_pass.json  1,201건 pass list
│   └── 03_fetch_log.json      fetch 기록
└── logs/                      실행 로그
```

## 자동화

| Task | Schedule | 역할 |
|------|----------|------|
| `paper-scout-embed-sync` | 매시간 | 새 PDF → embedding 자동 |
| `paper-scout-rescue-retry` | 매일 06:00 | 실패 DOI 자동 retry (max 50/일) |

## 다음 세션 우선순위

1. **rescue_unified.py에 eLife web strategy 추가** — 이번 세션에서 발견한 base64 URL 패턴
2. **Cell Press 4건 Chrome relay** — helper page 사용
3. **VPN 확보 → ScienceDirect 35건** — IP 차단 해제 필요
4. **failed_automated 117건 분석** — publisher별 browser-based strategy 또는 영구 제외 판단
5. **Skill 패키징** — `rescue_unified.py`를 csnl-paper-scout repo에도 반영

## Credentials
- `credentials.json` (gitignored): `openrouter_api_key`
- NAS: `/Volumes/CSNL_new/Memory/Papers/`
- Relay server: `http://127.0.0.1:18765`

## 금지 사항
- HSL, P3 (김민아), P4 (임채영) 관련 절대 금지
- JOP 외 DM 전송 금지
