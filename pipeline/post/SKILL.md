---
name: paper-scout-post
description: >
  Phase 5: Atomic paper-to-Slack posting with figure upload, Block Kit composition,
  embed-vl visual ranking, and equation extraction. Handles the complete pipeline from
  scored/drafted paper to a rich Slack message with images.
---

# Paper Scout — Phase 5: Post Engine

모든 포스트에 시각적 요소(figure/equation)를 포함한다. 텍스트만 있는 포스트는 최종 게시 대상이 아니다.

## Architecture

```
PostEngine.post_paper(paper_dict)
    │
    ├─[1] resolve_figure(name) ──→ runs/figures/{name}/page_N.png
    │     Priority: ranking_results.json → dir scan → None
    │
    ├─[2] upload_figure_to_slack(path) ──→ file_id
    │     Slack v2: getUploadURLExternal → PUT → completeUploadExternal
    │
    ├─[3] extract_equation(name) ──→ (text, korean_explanation)
    │     From extraction_summary.json or paper-scout-figures.py
    │
    ├─[4] build_post_blocks(...) ──→ Block Kit JSON + fallback mrkdwn
    │     hook → metadata → image(file_id) → equation → targeting → tags
    │
    └─[5] send_blocks(blocks, fallback) ──→ chat.postMessage
          blocks= for rich rendering, text= for notification fallback
```

## Modules

| File | Role |
|------|------|
| `post_engine.py` | Atomic orchestrator: figure→upload→compose→send |
| `slack_upload.py` | Slack v2 file upload (files:write scope) |
| `block_builder.py` | Block Kit JSON composer |
| `slack_bot.py` | Low-level Slack API wrapper |

## Paper Dict Schema

```python
paper = {
    "name": "Ozkirli",                      # Internal identifier
    "doi": "10.1038/s41562-025-02362-8",
    "title": "Large-scale mega-analysis...",
    "authors": "Ozkirli A, Chetverikov A, Pascucci D",
    "journal": "Nature Human Behaviour",
    "year": 2025,
    "doi_url": "https://doi.org/10.1038/s41562-025-02362-8",
    "hook": "CSNL SD 프레임워크에 정면 도전 — serial dependence는 adaptive가 아니라 decision을 악화시킨다",
    "targeting_lines": [
        {
            "slack_id": "U06JGAX5HD5",
            "name": "JOP",
            "project": "RingRepSca/Time/GranRDT",
            "description": "SD를 adaptive Bayesian process로 보는 CSNL 프레임워크에 대한 직접 도전",
            "quote": "SD deteriorates rather than improves perceptual decision-making",
        },
    ],
    "dimension_tags": "D2 Tension 9 (JOP) · D4 Competitive 8",
    "anchor_paper": "Lee, Lee, Choe, Lee 2023 (J Neurosci)",
    "equation_text": None,           # Optional
    "equation_explanation": None,     # Optional, Korean
}
```

## Block Kit Structure

```json
[
  {"type": "section", "text": {"type": "mrkdwn", "text": ":fire: {hook}"}},
  {"type": "section", "text": {"type": "mrkdwn", "text": "*{title}*\n_{authors}_\n:link: <{doi}|DOI>"}},
  {"type": "image", "slack_file": {"id": "{file_id}"}, "alt_text": "..."},
  {"type": "section", "text": {"type": "mrkdwn", "text": "> `{equation}` — {explanation}"}},
  {"type": "section", "text": {"type": "mrkdwn", "text": ":dart: targeting lines..."}},
  {"type": "context", "elements": [{"type": "mrkdwn", "text": ":label: {tags} — anchor: {anchor}"}]}
]
```

## Figure Resolution Priority

1. `runs/figures/ranking_results.json` — embed-vl cosine pre-computed
2. `runs/figures/{name}/` directory scan — largest PNG
3. Re-extract from PDF via `paper-scout-figures.py`
4. Mermaid/SVG fallback (text-only last resort)

Cosine thresholds (embed-vl):
- ≥0.3: Use as primary visual
- 0.1–0.3: Use with "moderate match" note
- <0.1: Skip, use fallback

## Execution

### Programmatic (from Python)
```python
from pipeline.post.post_engine import PostEngine

engine = PostEngine(channel_id="C06KJ95MGGZ")
result = engine.post_paper(paper_dict)
# or
results = engine.post_batch([paper1, paper2, ...])
```

### From Claude Code
```
paper scout post {DATE}
```
Loads `runs/paper-scout-draft-{DATE}.md`, parses into paper dicts,
presents dry_run preview, then posts on approval.

### DM to specific member
```python
engine = PostEngine(channel_id=dm_channel_id)
engine.post_paper(paper_dict)
```

## Safety Rules

1. Never post without explicit user approval
2. Verify channel = study-paper-reading (C06KJ95MGGZ) or approved test channel
3. Cross-check all Slack IDs against context-bundle.json
4. NO forbidden mentions (검증은 harness E7에서 자동 수행)
5. If upload/send fails, report error (no silent retry)
6. Figure upload BEFORE message send (file_id must be ready)

## Error Cascade

```
Figure upload fail → post without image block (text-only sections)
Equation extraction fail → post without equation section
Block Kit fail → fallback to plain mrkdwn text
chat.postMessage fail → log error, do not retry silently
```
