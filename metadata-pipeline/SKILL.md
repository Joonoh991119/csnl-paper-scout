# MetaData Scan Pipeline SKILL

## Overview
NAS Memory 폴더 메타데이터를 생성·업데이트하는 3단계 agent pipeline.

## Pipeline Architecture
```
Phase 1: SCAN (병렬)     Phase 2: POOL          Phase 3: REVIEW
┌──────────┐
│ Agent-JOP │──┐
├──────────┤  │         ┌──────────┐         ┌──────────────┐
│ Agent-SK  │──┼────────▶│ Pooling  │────────▶│ Review Agent │
├──────────┤  │         │  Agent   │         │ (cross-check │
│ Agent-MSY │──┤         └──────────┘         │  + gap fill) │
├──────────┤  │              │                └──────┬───────┘
│  ...etc   │──┘              ▼                       ▼
└──────────┘          members/*.json          reviews/review_DATE.json
                      (merged updates)        (comment → re-scan)
```

## Execution

### Quick Command
```
metadata scan          # Phase 1-3 전체 실행
metadata scan --member JOP   # 단일 멤버 업데이트
metadata review        # Phase 3만 실행 (기존 메타데이터 리뷰)
```

### Phase 1: SCAN (병렬 agent)
각 연구원 폴더를 독립 agent가 스캔. Agent 프롬프트: `_pipeline/scan_agent.md`

**실행 방식**: Cowork Agent tool로 병렬 spawn
```
Agent(prompt=scan_agent.md + member=JOP, model=sonnet)
Agent(prompt=scan_agent.md + member=SK, model=sonnet)
...
```

**각 agent의 작업:**
1. `registry.json`에서 해당 멤버의 프로젝트 목록 확인
2. NAS 폴더 접근 (Desktop Commander `list_directory`, `start_process`)
3. 기존 template.json / project.json / kb_*.json 읽기
4. Code/Data/Results/Context 하위 파일 통계 수집
5. `members/{INITIALS}.json` 업데이트 (write_file)

### Phase 2: POOL
모든 scan agent 완료 후 실행. Agent 프롬프트: `_pipeline/pooling_agent.md`

**작업:**
1. `members/*.json` 전체 로드
2. Cross-reference 일관성 검증 (A가 B를 참조하면 B도 A를 참조하는지)
3. 누락 필드 식별 → gaps 배열에 추가
4. registry.json 업데이트 (last_updated, 새 프로젝트 발견 시 추가)
5. `reviews/pool_YYYY-MM-DD.json` 출력

### Phase 3: REVIEW
Pooling 결과 기반 심층 검증. Agent 프롬프트: `_pipeline/review_agent.md`

**작업:**
1. Pool 결과의 gaps 항목별로 NAS 파일 직접 접근하여 확인
2. csnl_meta_knowledge.md와 대조 — 불일치 식별
3. 각 멤버 JSON의 hypothesis가 실제 template.json과 일치하는지 검증
4. review comment 생성 → `reviews/review_YYYY-MM-DD.json`
5. Comment 기반으로 members/*.json 자동 수정

## Update Triggers
- 새 세션 시작 시 `registry.json` last_updated 확인 → 7일 이상이면 자동 스캔 제안
- NAS에 새 폴더 생성 감지 → registry에 없는 폴더 발견 시 알림
- 수동: `metadata scan` 커맨드

## Safety Rules
- NAS 파일은 READ ONLY — 메타데이터만 MetaData/ 폴더에 쓴다
- 기존 template.json/project.json/kb_*.json 절대 수정 금지
- HSL, P3, P4 관련 내용 제한 규칙 적용
