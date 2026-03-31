# CSNL Paper Scout

CSNL 연구실 논문 추천 파이프라인. 새 세션 시작 시 `SESSION-HANDOFF.md`를 반드시 먼저 읽을 것.

## Credentials

`credentials.json` (gitignored, 로컬 전용):
- `slack_bot_token`: Claude bot으로 Slack 전송 (files:write 포함)
- `openrouter_api_key`: embed-vl(figure ranking) + gen model
- `jop_dm_channel`: D0AMRACTLBH (테스트 전송 대상)

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
- `paper scout post` — 통합 Slack 게시 (figure + hook + guide + summary + targeting + 피드백요청)
- `paper scout blind-eval` — Blind Evaluator 자기평가 루프
- `paper scout pooled-eval` — Pooled QA 평가 (다중 멤버 관점)
- `paper scout sync` — Slack #study-paper-reading → reading DB 동기화
- `paper scout harness eval-team {file}` — 7차원 적합성 평가

## Post Engine v2

**통합 포스트 패턴** (figure + 전체 텍스트가 하나의 메시지):
```python
# files.completeUploadExternal의 initial_comment에 모든 내용 포함:
# :fire: hook
# metadata + DOI
# :mag: figure guide (어디를 보면 뭘 알 수 있는지)
# summary (1-2문장)
# :dart: targeting lines (구체적 action)
# :label: tags
# :speech_balloon: 피드백 요청
```

**paper_dict 필수 필드**:
```python
paper = {
    "name", "doi", "title", "authors", "journal", "year", "doi_url",
    "hook",           # high-level, 수치/통계 불필요
    "figure_guide",   # "Figure X의 Y에 주목하면 Z를 확인할 수 있다"
    "summary",        # 1-2문장 핵심 발견
    "targeting_lines", "dimension_tags", "anchor_paper"
}
```

## Figure 우선순위

1. **논문 내 actual figure crop** (PDF에서 tight crop, 텍스트 제거)
2. **논문 graphical abstract** (있으면 최우선)
3. **AI 생성** (논문에 figure가 없거나, blind reviewer가 이해 못할 때만)

Figure crop 방법:
```python
import fitz
doc = fitz.open("paper.pdf")
page = doc[page_num]
clip = fitz.Rect(x0, y0, x1, y1)  # figure 영역만
pix = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=clip)
pix.save("figure_tight.png")
```

## QA Harness

### Blind Eval (`harness/blind_eval.py`)
- 멤버 관점 시뮬레이션 (B1-B5 scoring)
- Anti-leniency: 기본 1점, 2점은 genuinely excellent만
- Auto-escalation: leniency > 0.85 → 3단계 자동 강화
- Auto-revision loop: 실패 시 자동 수정 → 재평가

```bash
python harness/blind_eval.py --paper Ozkirli --max-rounds 3
python harness/blind_eval.py  # 전체 5편
```

### Pooled Eval (`harness/pooled_eval.py`)
- 5편을 한 번에 보고 배치 평가 (V1-V4 + P1-P3)
- 다중 멤버 관점 (JOP, SK, MSY)
- 포스트 간 상대 비교

```bash
python harness/pooled_eval.py --max-rounds 3
```

## Agents (7개)

| Agent | Role |
|-------|------|
| `drafter.md` | 초안 생성 |
| `hook_evaluator.md` | 3초 테스트 |
| `accuracy_evaluator.md` | 사실 검증 |
| `member_advocate.md` | 멤버 관점 시뮬레이션 |
| `visual_agent.md` | Figure 추출/랭킹 |
| `final_editor.md` | 최종 편집 |
| `blind_evaluator.md` | Adversarial QA (B1-B5) |

## SK 연구 정확한 프레이밍 (hallucination 방지)

- **올바름**: geometry-preserving subspace rotation, re-embedded code, nearly orthogonal (71°), ring-like manifold, retinotopically decoupled mnemonic
- **금지**: "abstract representation 가설" (존재하지 않음)
- **3가지 시나리오**: Common code / Distinct code / Re-embedded code (SK 발견)
- KimEtal 2026: N=50 fMRI, 16.5s prolonged delay, dPCA + crossnobis RDM + IEM

## Execution Rules

- 각 SKILL.md를 반드시 읽고 따를 것
- Context: `data/context-bundle.json`
- **JOP에게만 DM 전송** (다른 연구원 ㄴㄴ, 테스트 단계)
- **HSL, P3 (김민아), P4 (임채영) 절대 금지**

## 이름 주의
- 이보연 = Boyun = BYL
- 이보현 = Bohyun = BHL
