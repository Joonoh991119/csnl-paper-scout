# CSNL Paper Scout

CSNL 연구실 논문 추천 파이프라인.

## Quick Commands

- `paper scout scan` — Phase 1: RAG 기반 저널 스캔
- `paper scout score` — Phase 2: 5차원 가치 평가
- `paper scout team` — Phase 3: 6-agent 팀 드래프팅
- `paper scout review` — Phase 4: Group 피어 리뷰 (선택)
- `paper scout post` — Phase 5: Slack 게시
- `paper scout sync` — Slack 채널에서 읽은 논문 DB 동기화
- `paper scout harness eval-team {file}` — 하네스 평가

## Execution Rules

- 각 단계의 SKILL.md를 반드시 읽고 해당 지침을 따를 것
  - Scan: `pipeline/scan/SKILL.md`
  - Score: `pipeline/score/SKILL.md`
  - Team: `pipeline/team/SKILL.md`
  - Review: `pipeline/review/SKILL.md`
  - Post: `pipeline/post/SKILL.md`
  - Sync: `sync/SKILL.md`
  - Harness: `harness/SKILL.md`
- Agent 정의: `agents/*.md`
- Context bundle: `data/context-bundle.json`
- 출력은 `runs/paper-scout-{phase}-{YYYY-MM-DD}.md` 형식
- Slack 게시 전 반드시 사용자 확인 필요
- **HSL, P3 (김민아), P4 (임채영) 관련 내용 절대 금지**

## Slack

- Channel: `#study-paper-reading` (C06KJ95MGGZ)
- Emoji: :fire: :dart: :link: :label: only
- Member mentions: `<@SLACK_ID>` format
- Korean for recommendations, English for citations

## Sync (자동 DB 업데이트)

DB가 구축되면 자동화 흐름:
1. `paper scout sync` → Slack MCP로 채널 읽기 → `sync/sync_reading_db.py`로 파싱
2. `data/reading-db/` 업데이트 (논문 기록)
3. `data/member-profiles/` 업데이트 (멤버별 관심사)
4. `--update-context` → `data/context-bundle.json`의 `_reading_profile` 갱신

## Harness

7차원 적합성 평가 (E1-E7). E7 Safety는 hard fail gate.
- `python harness/run-harness.py eval-team {file}` — 자동 검증
- `python harness/run-harness.py dry-run` — 테스트 케이스 모의 실행
