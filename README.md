# CSNL Paper Scout

AI-powered paper recommendation pipeline for **Cognitive & Systems Neuroscience Lab (CSNL)**, Seoul National University.

Semantic-embedding-grounded RAG로 CSNL의 연구 인접 논문을 자동 발견, 5차원 가치 평가, 6-agent 팀 드래프팅, Slack 배포까지 수행하는 end-to-end 시스템.

## Architecture

```
Scan ──→ Score ──→ Team ──→ Review ──→ Post
(RAG)    (D1-D5)   (6-agent)  (Group)   (Slack)
                      │
              ┌───────┼───────┐
          Drafter  Evaluators  Editor
              │       │         │
              └── Feedback Loop ┘
                  (max 3 rounds)
```

## Directory Structure

```
csnl-paper-scout/
├── pipeline/               # 5-phase pipeline
│   ├── scan/SKILL.md       #   Phase 1: RAG-anchored journal scanning
│   ├── score/SKILL.md      #   Phase 2: 5-dimension value scoring
│   ├── team/SKILL.md       #   Phase 3: 6-agent team drafting
│   ├── review/SKILL.md     #   Phase 4: Group peer review (optional)
│   ├── post/SKILL.md       #   Phase 5: Slack deployment
│   ├── paper-scout-embed.py    # Embedding utility (OpenRouter)
│   └── paper-scout-figures.py  # PDF figure extraction/ranking
├── agents/                 # 6 specialized agent definitions
│   ├── drafter.md
│   ├── hook_evaluator.md
│   ├── visual_agent.md
│   ├── accuracy_evaluator.md
│   ├── member_advocate.md
│   └── final_editor.md
├── data/                   # Configuration & databases
│   ├── context-bundle.json     # Central config (members, projects, scoring)
│   ├── reading-db/             # Paper reading history
│   ├── member-profiles/        # Auto-generated member interest profiles
│   ├── pi_network_data.json    # PI collaboration network
│   ├── journals.md             # Target journal tiers
│   └── tracked_authors.md      # Tracked author list
├── sync/                   # Auto-sync module
│   ├── SKILL.md                # Sync protocol
│   └── sync_reading_db.py      # Slack → DB parser & updater
├── harness/                # Quality evaluation
│   ├── SKILL.md                # 7-dimension fitness evaluation
│   ├── run-harness.py          # Automated evaluator
│   ├── rubrics/                # E1-E7 detailed rubrics
│   └── evals/                  # Test cases
├── ui/app.py               # Streamlit dashboard
├── runs/                   # Pipeline execution outputs (gitignored)
└── docs/                   # Documentation
```

## Pipeline Phases

| Phase | Trigger | What it does |
|-------|---------|-------------|
| **Scan** | `paper scout scan` | 90-day rolling window, dual semantic gate (Zotero ≥0.4 + embedding ≥0.45) |
| **Score** | `paper scout score` | 5 value dimensions (D1 Direct, D2 Tension, D3 Method, D4 Competitive, D5 Reframing) |
| **Team** | `paper scout team` | Drafter → Hook/Visual/Accuracy/Advocate evaluators → Final Editor, max 3 iterations |
| **Review** | `paper scout review` | Group A/B/C peer review (optional, for borderline 7-8 scores) |
| **Post** | `paper scout post` | Slack `#study-paper-reading` deployment with user confirmation |

## Scoring System

Composite = `max(D1, D2, D3, D4, D5)` (not average). Tiebreak by mean.

| Score | Meaning |
|-------|---------|
| 9-10 | Immediate action — read and change something |
| 7-8 | Strong connection — direct value |
| 5-6 | Meaningful — one method/phenomenon overlaps |
| 0-4 | Weak or no connection |

## Auto-Sync (Reading DB)

`sync/sync_reading_db.py` automatically parses `#study-paper-reading` Slack messages to maintain:
- **Reading DB** — paper citations, notes, topics (deduped by DOI/title)
- **Member Profiles** — per-member topic frequencies, tracked authors, reading history
- **Context Bundle** — auto-updates `_reading_profile` fields from profiles

```bash
# Sync new messages
paper scout sync

# Full history sync
paper scout sync full

# Update context-bundle from profiles
python sync/sync_reading_db.py --update-context
```

## Harness (Quality Evaluation)

7-dimension fitness scoring with automated + LLM-based checks:

| Dim | Name | Type |
|-----|------|------|
| E1 | Structural Compliance | Automated |
| E2 | Semantic Fidelity | LLM |
| E3 | Member Targeting | LLM |
| E4 | Hook Effectiveness | Automated |
| E5 | Agent Convergence | Automated |
| E6 | Pipeline Coherence | LLM |
| E7 | Safety (hard fail gate) | Automated |

Grade: A(≥0.85) B(0.70) C(0.55) D(0.40) F(<0.40 or E7 fail)

## Members

| ID | Name | Group | Focus |
|----|------|-------|-------|
| JOP | 박준오 | A | Bayesian estimation, serial dependence, granularity |
| MSY | 여민수 | A | Categorical vs magnitude SD, gambler's fallacy |
| BYL | 이보연 | A | Bayesian observer, VWM bias, efficient coding |
| JYK | 김정예 | B | RNN modeling, drift-diffusion dynamics |
| MJC | 최민진 | B | Sequential VWM, contrast-dependent bias |
| SK | 김성제 | B | EVC sensory vs mnemonic code, dPCA |
| JHR | 류주형 | C | pRF anisotropy, orientation-specific FC |
| SMJ | 정새미 | C | Co-circularity, V1-to-percept |
| JSL | 임재섭 | Ind | Serial dependence spatial reference frames |
| BHL | 이보현 | Ind | Serial dependence features, WM binding |

## Setup

```bash
# Clone
git clone https://github.com/Joonoh991119/csnl-paper-scout.git
cd csnl-paper-scout

# Set API key
export OPENROUTER_API_KEY="your_key"

# Run with Claude Code
claude
```

## Slack

- Channel: `#study-paper-reading` (C06KJ95MGGZ)
- Format: Korean + English citations, Slack mrkdwn
- Posting requires user confirmation (never silent)
