"""Slack Block Kit composer for Paper Scout posts.

v2: Thread reply no longer duplicates the hook (hook lives in the figure caption).
    Score tables and evidence quotes removed — targeting lines carry all context.
"""


def build_post_blocks(
    title: str,
    authors: str,
    journal: str,
    year: str,
    doi_url: str,
    summary: str,
    figure_guide: str = "",
    targeting_lines: list = None,
    dimension_tags: str = "",
    anchor_paper: str = "",
    equation_text: str = None,
    equation_explanation: str = None,
    # Legacy params kept for compatibility but ignored
    hook: str = "",
    figure_file_id: str = None,
    figure_alt_text: str = "",
) -> tuple:
    """
    Build Slack Block Kit blocks for the THREAD REPLY (detail message).
    The hook + figure go in the main message (file upload caption).

    Returns: (blocks: list[dict], fallback_text: str)
    """
    blocks = []
    fallback_parts = []

    # 1. Paper metadata
    meta = f"*{title}*\n_{authors} — {journal} ({year})_\n:link: <{doi_url}|DOI>"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": meta},
    })
    fallback_parts.append(meta)

    # 2. Figure guide (what to look at in the figure)
    if figure_guide:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":mag: {figure_guide}"},
        })
        fallback_parts.append(f":mag: {figure_guide}")

    # 3. Summary (1-2 sentences, Korean)
    if summary:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        })
        fallback_parts.append(summary)

    # 3. Equation (if present)
    if equation_text:
        eq_block = f"> `{equation_text}`"
        if equation_explanation:
            eq_block += f"\n> — {equation_explanation}"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": eq_block},
        })
        fallback_parts.append(eq_block)

    # 4. Targeting lines — each as its own section for readability
    if targeting_lines:
        target_texts = []
        for t in targeting_lines:
            line = f":dart: *<@{t['slack_id']}> {t['name']}의 {t['project']}*: {t['description']}"
            target_texts.append(line)

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(target_texts)},
        })
        fallback_parts.append("\n".join(target_texts))

    # 5. Dimension tags + anchor (context block)
    tag_text = f":label: {dimension_tags}"
    if anchor_paper:
        tag_text += f" — anchor: {anchor_paper}"
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": tag_text}],
    })
    fallback_parts.append(tag_text)

    fallback_text = "\n\n".join(fallback_parts)
    return blocks, fallback_text
