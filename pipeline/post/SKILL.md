---
name: paper-scout-post
description: "Phase 5 of CSNL Paper Scout pipeline: finalize and post approved paper recommendations to Slack paper-reading-study channel. Use this skill after paper-scout-review (or paper-scout-draft if skipping review), or when the user wants to publish paper recommendations to Slack. Triggers on: 'post papers', 'publish to slack', 'paper scout post', '논문 게시', 'Slack에 올려', 'send recommendations', 'paper-reading-study에 게시'."
---

# Paper Scout — Phase 5: Finalize & Post

Post approved paper recommendations to the `paper-reading-study` Slack channel after human confirmation.

## Prerequisites

1. Load reviewed/approved posts from either:
   - `paper-scout-review-[DATE].md` (if Phase 4 was run)
   - `paper-scout-draft-[DATE].md` (if skipping review)
2. Ensure csnl-slack-bot MCP is available (`csnl_send_channel_message` tool)

## Target Channel

**`paper-reading-study`**

## Workflow

### Step 1: Present final posts for human confirmation

Display all approved posts to the user (JOP, 박준오) in the conversation. Ask explicitly:

> "아래 [N]편의 포스트를 paper-reading-study 채널에 게시합니다. 수정할 부분이 있으면 알려주세요."

Show each post exactly as it will appear in Slack (with formatting, @mentions, emojis).

### Step 2: Apply user edits (if any)

If the user requests modifications:
- Apply edits immediately
- Show the revised version for re-confirmation
- Do NOT post without explicit approval

### Step 3: Post to Slack

On user approval, post each paper using `csnl_send_channel_message`:

```
Tool: csnl_send_channel_message
channel: paper-reading-study
text: [formatted post content]
```

**Posting order**: Highest score first (Post 1 → Post 2 → Post 3).

**Between posts**: No delay needed, but post sequentially (not in parallel) to maintain order in the channel.

### Step 4: Confirmation

After all posts are sent, confirm:

> "게시 완료: [N]편의 논문 추천이 paper-reading-study 채널에 게시되었습니다."

## Slack Formatting Notes

- Use `*bold*` for paper titles and section headers
- Use `_italic_` for author/journal info
- Use `<@SLACK_ID>` format for member mentions (NOT @Name)
- Use emoji shortcodes: `:newspaper:`, `:mag:`, `:link:`, `:busts_in_silhouette:`
- Line breaks: use actual newlines, not `\n`

## Safety Rules

1. **Never post without explicit user approval.** This is non-negotiable.
2. **Never post to wrong channel.** Always verify channel name is `paper-reading-study`.
3. **Verify Slack IDs before posting.** Cross-check against context-bundle.json.
4. **No HSL, P3 (김민아), P4 (임채영) mentions.** These are not CSNL pipeline members.
5. **If csnl_send_channel_message fails**, report the error to the user. Do not retry silently.

## Pipeline Complete Message

After successful posting, optionally save a log:

```markdown
# Paper Scout Log — [DATE]

- Scanned: [N] journals
- Candidates: [M] papers
- Scored: Top 3 selected
- Reviewed: [verdicts summary]
- Posted: [N] papers to paper-reading-study
- Timestamp: [ISO datetime]
```

Save to `paper-scout-log-[YYYY-MM-DD].md` in workspace.
