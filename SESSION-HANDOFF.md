# Paper Scout Session Handoff — 2026-03-31

## 프로젝트 개요
CSNL(인지 및 시스템 신경과학 연구실, 서울대 이상훈 교수) 논문 추천 파이프라인.
PI network 저자들의 최신 논문을 크롤링하여, 각 연구원의 프로젝트와의 관련성을 5차원(D1-D5)으로 평가하고, 6-agent 팀 드래프팅을 거쳐 Slack에 figure 포함 포스트를 배포하는 end-to-end 시스템.

## 현재 상태 (이 세션에서 완료한 것)

### 인프라 구축 완료
- **Repo**: `~/csnl-paper-scout/` (GitHub: Joonoh991119/csnl-paper-scout, private)
- **5-phase pipeline**: scan → score → team → review → post (각각 SKILL.md 정의)
- **6 agents**: drafter, hook_evaluator, visual_agent, accuracy_evaluator, member_advocate, final_editor
- **Harness**: 7차원 적합성 평가 (E1-E7), 자동화 러너 (`harness/run-harness.py`)
- **Sync module**: Slack #study-paper-reading 채널에서 읽은 논문 DB 자동 파싱 (`sync/sync_reading_db.py`)
- **Reading DB**: 1,069편 (637 Slack + 432 CSNL_new 라이브러리)
- **Post Engine**: figure upload + Block Kit + atomic pipeline (`pipeline/post/post_engine.py`)

### 90일 스캔 + 스코어링 완료 (8편 → 5편 선정)
- PI network 저자 크롤링 (Semantic Scholar, 17 PIs, 66 papers)
- Playwright PDF 다운로드 (6/6 성공)
- embed-vl figure ranking (nvidia/llama-nemotron-embed-vl-1b-v2:free)
- Full-text 기반 D1-D5 재검토

### 선정된 5편
| # | Paper | Primary | Score |
|---|-------|---------|-------|
| 1 | Serences — Sensory-mnemonic interaction | SK D1=9 | bioRxiv 2025 |
| 2 | Ozkirli — SD deteriorates decision | JOP D2=9 | NHB 2025 |
| 3 | Costa — Categorical SD (EEG) | MSY D1=9 | bioRxiv 2026 |
| 4 | Pascucci — Drift-diffusion preview | JYK D1=9 | Neuron 2025 |
| 5 | Rademaker — Top-down feedback EVC | SK D1=8 | bioRxiv 2025 |

(Dumoulin×2, Serences WM load는 v3에서 선정되었으나 최종 게시 대상에서 제외)

### Post Engine 테스트 (Ozkirli → JOP DM)
- Figure upload + Block Kit thread: **작동 확인**
- 패턴: figure+hook = 메인 메시지, Block Kit detail = 스레드 reply (broadcast)
- 현재 JOP DM 비워둔 상태

## 다음 세션에서 해야 할 것 (미완료)

### 1. Agent Team 검토 (최우선)
**포스트 품질이 낮다.** 다음 항목에 대해 agent team이 머리를 맞대고 검토해야 함:

- **가독성**: 현재 포스트가 Slack에서 실제로 읽기 편한가? 텍스트 밀도, 줄 간격, 정보 계층
- **내용 요약**: abstract 요약이 너무 길거나 짧은가? 핵심 finding이 1문장으로 전달되는가?
- **추천 근거**: :dart: 타겟팅 라인이 "이 멤버가 구체적으로 무엇을 해야 하는지" 전달하는가?
- **Graphical abstract 선택**: embed-vl cosine 0.26~0.38은 낮음. page render가 아닌 actual figure 추출이 필요. PyMuPDF가 vector figures를 못 잡는 문제 해결 필요.
- **Graphical abstract 생성**: figure가 없거나 매칭이 약할 때 AI로 conceptual diagram을 생성하는 능력

### 2. 포스트 테스트 대상
- **JOP(박준오)에게만 DM 전송** (다른 연구원에겐 ㄴㄴ)
- JOP DM channel: `D0AMRACTLBH`
- 피드백 수집 → 로직 업데이트

### 3. Graphical Abstract 개선
- `paper-scout-figures.py`의 `extract_figures_from_pdf()`가 vector figures 못 잡음 (raster only)
- 대안: Playwright로 HTML 풀텍스트 렌더링 → figure URL 추출 → 다운로드
- 또는: Qwen(qwen/qwen3.6-plus-preview:free)으로 abstract 기반 conceptual diagram 생성
- 또는: PDF를 고해상도 page render → crop to figure region

### 4. Slack 포맷 제약
- `chat.postMessage`에서 Block Kit의 `image` block은 `slack_file` type이 `invalid_blocks` 에러 발생
- 해결: figure를 `files.completeUploadExternal`의 `initial_comment`로 hook과 함께 전송, detail을 thread reply로 전송
- `send_message`에서 Slack mrkdwn 특수문자(`*`, `_`, `<@ID>`, `:emoji:`)가 가끔 `invalid_blocks` 에러 → plain text는 항상 성공

### 5. Scan 개선
- 키워드 검색 → SD에 편향됨 (v2에서 발견)
- **PI network 저자 크롤링이 올바른 방법** (v3에서 적용)
- Semantic Scholar API rate limit (429) → 배치당 ~20명까지, sleep 필요
- bioRxiv 직접 PDF 다운로드 차단 → Playwright download handler 사용

## 파일 구조

```
csnl-paper-scout/
├── CLAUDE.md                  ← Claude Code 연동 가이드
├── credentials.json           ← Slack bot token + OpenRouter API key (gitignored)
├── pipeline/
│   ├── scan/SKILL.md
│   ├── score/SKILL.md
│   ├── team/SKILL.md + draft-SKILL.md
│   ├── review/SKILL.md
│   ├── post/
│   │   ├── SKILL.md           ← Post Engine 전체 스펙
│   │   ├── post_engine.py     ← Atomic pipeline (figure→upload→compose→send)
│   │   ├── slack_upload.py    ← Slack v2 file upload
│   │   ├── block_builder.py   ← Block Kit JSON composer
│   │   └── slack_bot.py       ← Low-level Slack API
│   ├── fetch/
│   │   └── fetch_fulltext.py  ← Playwright PDF downloader
│   ├── paper-scout-embed.py   ← OpenRouter embed-vl utility
│   └── paper-scout-figures.py ← PyMuPDF figure extraction + ranking
├── agents/                    ← 6 agent definitions
├── data/
│   ├── context-bundle.json    ← 멤버, 프로젝트, Slack ID, scoring 설정
│   ├── reading-db/            ← 1,069편 읽은 논문 DB
│   ├── pi_network_data.json
│   ├── journals.md
│   └── tracked_authors.md
├── sync/
│   ├── sync_reading_db.py     ← Slack → DB 파서
│   └── SKILL.md
├── harness/
│   ├── SKILL.md               ← 7차원 적합성 평가
│   ├── run-harness.py
│   ├── rubrics/e1-e7.md
│   └── evals/test-cases.json
└── runs/
    ├── paper-scout-scores-2026-03-31.md  ← 최종 스코어 (v3)
    ├── paper-scout-draft-2026-03-31.md   ← 8편 드래프트
    ├── abstracts-*.json                  ← Playwright 수집 abstract
    ├── pi_network_recent_papers.json     ← PI 크롤링 결과
    ├── pdfs/                             ← 다운로드된 PDF
    └── figures/                          ← embed-vl ranked figures
        └── ranking_results.json
```

## Credentials (credentials.json, gitignored)
- `slack_bot_token`: Claude bot (U0ANKLV7W5P), files:write scope 포함
- `openrouter_api_key`: embed-vl + gen model access
- `jop_dm_channel`: D0AMRACTLBH (테스트용)
- `study_channel`: C06KJ95MGGZ (#study-paper-reading)

## 금지 사항
- **HSL, P3 (김민아), P4 (임채영) 멘션 절대 금지**
- JOP 외 다른 연구원에게 DM 전송 금지 (현재 테스트 단계)
- 사용자 확인 없이 #study-paper-reading 채널 게시 금지

## 이름 주의
- 이보연 = Boyun Lee = BYL
- 이보현 = Bohyun Lee = BHL
