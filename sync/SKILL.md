---
name: paper-scout-sync
description: Slack #study-paper-reading 채널에서 멤버 독후감을 자동 파싱하여 reading-db와 member-profiles를 업데이트. context-bundle.json의 멤버 관심사도 자동 갱신.
---

# Paper Scout Sync — 읽은 논문 DB 자동 동기화

## Trigger
- `paper scout sync` — 마지막 동기화 이후 새 메시지만
- `paper scout sync full` — 전체 채널 히스토리 동기화
- `paper scout sync update-context` — 프로필에서 context-bundle 업데이트

## Protocol

### Step 1: Slack 채널 읽기

Slack MCP의 `slack_read_channel`로 `#study-paper-reading` (C06KJ95MGGZ) 메시지를 가져온다.

```
incremental: sync/.sync-state.json의 last_sync_ts 이후 메시지만
full: 전체 히스토리 (pagination 사용)
```

### Step 2: 메시지 파싱

각 메시지에서 추출:

1. **논문 인용 정보** — Author et al. (Year) "Title" Journal 패턴 감지
2. **DOI** — `10.xxxx/...` 패턴
3. **독서 노트** — 한국어 섹션 (범위, 내용, 정리, 생각, 궁금)
4. **주제 분류** — 14개 토픽 키워드 자동 매칭
5. **저자 추적** — 인용 저자 파싱

### Step 3: DB 업데이트

파싱된 결과를 `sync/sync_reading_db.py`의 `sync_messages()`에 전달:

```python
from sync.sync_reading_db import sync_messages

messages = [
    {
        "user": "U07728304R5",
        "user_name": "Boyun Lee",
        "text": "...(메시지 원문)...",
        "ts": "1711540623.862469",
        "date": "2026-03-27 22:23:43 KST"
    },
    ...
]

result = sync_messages(messages, dry_run=False)
```

### Step 4: 결과 확인

```json
{
    "total_messages": 50,
    "parsed": 42,
    "new_entries": 38,
    "skipped_duplicates": 4,
    "errors": 0
}
```

### Step 5 (선택): Context Bundle 업데이트

```python
from sync.sync_reading_db import update_context_bundle_from_profiles

result = update_context_bundle_from_profiles()
```

이 함수는 member-profiles/*.json에서 상위 토픽과 추적 저자를 추출하여
context-bundle.json의 각 멤버 프로젝트에 `_reading_profile` 필드를 추가한다.

기존 프로젝트 기술은 건드리지 않음. 읽기 프로필만 추가/갱신.

## 업데이트 대상 파일

| File | Updated By | Content |
|------|-----------|---------|
| `data/reading-db/study_paper_reading_db.json` | sync_messages() | 전체 독서 기록 |
| `data/member-profiles/{SLACK_ID}.json` | update_member_profile() | 멤버별 토픽/저자/히스토리 |
| `data/context-bundle.json` | update_context_bundle_from_profiles() | _reading_profile 필드 |
| `sync/.sync-state.json` | save_sync_state() | 마지막 동기화 타임스탬프 |

## Dedup Rules

- DOI 정확 매칭 → skip
- Title 소문자 정확 매칭 → skip
- 같은 멤버가 같은 논문을 여러 날에 걸쳐 읽은 경우 → 첫 엔트리만 DB에 추가 (profile 카운트는 1회)

## 자동화 시나리오 (미래)

DB가 충분히 축적되면:

1. **주간 자동 sync** — launchd/cron으로 `paper scout sync` 실행
2. **Scan 전 자동 sync** — scan-SKILL.md의 Tier 3 dedup을 위해 최신 DB 보장
3. **Score 시 프로필 참조** — 멤버별 _reading_profile로 더 정확한 D1-D5 평가
4. **Member Advocate 강화** — 실제 독서 패턴 기반 "이 멤버가 관심 가질까?" 판단
