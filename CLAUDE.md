# CSNL Paper Scout

CSNL 연구실 논문 추천 파이프라인. 새 세션 시작 시 `SESSION-HANDOFF.md`를 반드시 먼저 읽을 것.

## Credentials

`credentials.json` (gitignored, 로컬 전용):
- `slack_bot_token`: Claude bot으로 Slack 전송 (files:write 포함)
- `openrouter_api_key`: embed-vl(figure ranking) + gen model
- `jop_dm_channel`: D0AMRACTLBH (테스트 전송 대상)

사용법:
```python
import json
with open("credentials.json") as f:
    creds = json.load(f)
os.environ["SLACK_BOT_TOKEN"] = creds["slack_bot_token"]
os.environ["OPENROUTER_API_KEY"] = creds["openrouter_api_key"]
```

## Quick Commands

- `paper scout scan` — PI network 크롤링 + semantic gate
- `paper scout score` — 5차원(D1-D5) 가치 평가
- `paper scout team` — 6-agent 팀 드래프팅
- `paper scout post` — PostEngine으로 Slack 게시 (figure + Block Kit)
- `paper scout sync` — Slack #study-paper-reading → reading DB 동기화
- `paper scout harness eval-team {file}` — 7차원 적합성 평가

## Post Engine 사용법

```python
from pipeline.post.post_engine import PostEngine
engine = PostEngine(channel_id="D0AMRACTLBH")  # JOP DM
result = engine.post_paper(paper_dict, dry_run=False)
```

포스트 패턴:
1. **Figure + hook caption** → `files.completeUploadExternal` (메인 메시지)
2. **Block Kit detail** → `chat.postMessage` thread reply (broadcast)

## Execution Rules

- 각 SKILL.md를 반드시 읽고 따를 것
- Agents: `agents/*.md` (6개)
- Context: `data/context-bundle.json`
- 출력: `runs/paper-scout-{phase}-{YYYY-MM-DD}.md`
- **JOP에게만 DM 전송** (다른 연구원 ㄴㄴ, 테스트 단계)
- **HSL, P3 (김민아), P4 (임채영) 절대 금지**

## 현재 미완료 과제

1. **포스트 품질 agent team 검토**: 가독성, 요약, 추천 근거, graphical abstract
2. **Figure 추출 개선**: PyMuPDF vector figure 미지원 → HTML figure URL 추출 또는 AI 생성
3. **embed-vl cosine 낮음** (0.26~0.38): page render 대신 actual figure 필요
4. **Slack Block Kit `image` block**: `slack_file` type `invalid_blocks` → figure를 별도 메시지로 분리 해결됨

## 이름 주의
- 이보연 = Boyun = BYL
- 이보현 = Bohyun = BHL
