"""Slack Block Kit composer for Paper Scout posts."""


def build_post_blocks(
    hook: str,
    title: str,
    authors: str,
    journal: str,
    year: str,
    doi_url: str,
    figure_file_id: str = None,
    figure_alt_text: str = "",
    equation_text: str = None,
    equation_explanation: str = None,
    targeting_lines: list = None,
    dimension_tags: str = "",
    anchor_paper: str = "",
) -> tuple:
    """
    Build Slack Block Kit blocks + fallback mrkdwn text.

    Returns: (blocks: list[dict], fallback_text: str)
    """
    blocks = []
    fallback_parts = []

    # 1. Hook
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f":fire: {hook}"},
    })
    fallback_parts.append(f":fire: {hook}")

    # 2. Paper metadata
    meta = f"*{title}*\n_{authors} — {journal} ({year})_\n:link: <{doi_url}|DOI>"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": meta},
    })
    fallback_parts.append(meta)

    # 3. Figure (if uploaded)
    if figure_file_id:
        blocks.append({
            "type": "image",
            "slack_file": {"id": figure_file_id},
            "alt_text": figure_alt_text or f"{title} - Key Figure",
        })
        fallback_parts.append(f"[Figure attached: {figure_alt_text}]")

    # 4. Equation (if present)
    if equation_text:
        eq_block = f"> `{equation_text}`"
        if equation_explanation:
            eq_block += f"\n> — {equation_explanation}"
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": eq_block},
        })
        fallback_parts.append(eq_block)

    # 5. Targeting lines
    if targeting_lines:
        target_texts = []
        for t in targeting_lines:
            line = f":dart: *<@{t['slack_id']}> {t['name']}의 {t['project']}*: {t['description']}"
            target_texts.append(line)

        # Add quote if present
        for t in targeting_lines:
            if t.get("quote"):
                target_texts.append(f"> \"{t['quote']}\"")
                break  # One quote is enough

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(target_texts)},
        })
        fallback_parts.append("\n".join(target_texts))

    # 6. Dimension tags + anchor (context block)
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
