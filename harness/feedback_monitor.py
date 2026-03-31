"""
Feedback Monitor — poll Slack DM channels for reactions and replies.

Checks each member's DM for:
- Emoji reactions on posts (:thumbsup:, :thinking_face:, :thumbsdown:)
- Thread replies with text feedback

Outputs a feedback report for downstream processing.

Usage:
    python harness/feedback_monitor.py
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime

REPO_DIR = Path(__file__).resolve().parent.parent

def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)

MEMBERS = {
    "U06K5MX4GHE": {"name": "SK", "korean": "김성제", "dm": "D0AN6PLBXU2",
                     "papers": ["Serences", "Rademaker"]},
    "U06JGAX5HD5": {"name": "JOP", "korean": "박준오", "dm": "D0AMRACTLBH",
                     "papers": ["Ozkirli"]},
    "U06JA7D5XC7": {"name": "MSY", "korean": "여민수", "dm": "D0AP128V9DE",
                     "papers": ["Ozkirli", "Costa"]},
    "U09DQQFB4E4": {"name": "BHL", "korean": "이보현", "dm": "D0AN6PXAESE",
                     "papers": ["Costa"]},
    "U081CN9JVK3": {"name": "JYK", "korean": "김정예", "dm": "D0AN3B8K0CD",
                     "papers": ["Pascucci"]},
}

REACTION_MAP = {
    "+1": "useful",
    "thumbsup": "useful",
    "thinking_face": "partial",
    "-1": "not_relevant",
    "thumbsdown": "not_relevant",
}


def get_recent_messages(channel_id, bot_token, limit=20):
    """Get recent messages from a DM channel."""
    r = requests.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"channel": channel_id, "limit": limit},
        timeout=10,
    )
    d = r.json()
    if not d.get("ok"):
        return []
    return d.get("messages", [])


def get_reactions(channel_id, message_ts, bot_token):
    """Get reactions on a specific message."""
    r = requests.get(
        "https://slack.com/api/reactions.get",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"channel": channel_id, "timestamp": message_ts},
        timeout=10,
    )
    d = r.json()
    if not d.get("ok"):
        return []
    msg = d.get("message", {})
    return msg.get("reactions", [])


def get_thread_replies(channel_id, thread_ts, bot_token):
    """Get replies in a thread."""
    r = requests.get(
        "https://slack.com/api/conversations.replies",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"channel": channel_id, "ts": thread_ts, "limit": 50},
        timeout=10,
    )
    d = r.json()
    if not d.get("ok"):
        return []
    # Skip the parent message
    msgs = d.get("messages", [])
    return [m for m in msgs if m.get("ts") != thread_ts]


def identify_paper(message_text):
    """Identify which paper a message is about from its content."""
    paper_keywords = {
        "Serences": ["Serences", "sensory-mnemonic", "low-interference"],
        "Ozkirli": ["Ozkirli", "mega-analysis", "deteriorates"],
        "Costa": ["Costa", "categorical", "RSA"],
        "Pascucci": ["Pascucci", "drift-diffusion", "Neuron Preview"],
        "Rademaker": ["Rademaker", "top-down feedback", "STSP"],
    }
    for paper, keywords in paper_keywords.items():
        for kw in keywords:
            if kw.lower() in message_text.lower():
                return paper
    return None


def collect_feedback(bot_token):
    """Collect all feedback from all member DMs."""
    feedback = []

    for uid, member in MEMBERS.items():
        name = member["name"]
        dm = member["dm"]

        messages = get_recent_messages(dm, bot_token)
        if not messages:
            continue

        for msg in messages:
            # Skip bot's own messages that aren't file shares with reactions
            text = msg.get("text", "")
            ts = msg.get("ts", "")

            # Check for Paper Scout posts (file shares with our caption)
            is_post = ("Paper Scout" in text or ":fire:" in text or
                       msg.get("files") or msg.get("subtype") == "file_share")
            if not is_post:
                continue

            paper = identify_paper(text)
            if not paper:
                continue

            entry = {
                "member": name,
                "member_korean": member["korean"],
                "user_id": uid,
                "paper": paper,
                "ts": ts,
                "reactions": [],
                "replies": [],
            }

            # Get reactions
            reactions = get_reactions(dm, ts, bot_token)
            for rxn in reactions:
                rxn_name = rxn.get("name", "")
                rxn_users = rxn.get("users", [])
                # Only count reactions from the member (not the bot)
                if uid in rxn_users:
                    sentiment = REACTION_MAP.get(rxn_name, rxn_name)
                    entry["reactions"].append({
                        "emoji": rxn_name,
                        "sentiment": sentiment,
                    })

            # Get thread replies
            replies = get_thread_replies(dm, ts, bot_token)
            for reply in replies:
                reply_user = reply.get("user", "")
                if reply_user == uid:  # Only member's replies, not bot
                    entry["replies"].append({
                        "text": reply.get("text", ""),
                        "ts": reply.get("ts", ""),
                    })

            # Only include if there's actual feedback
            if entry["reactions"] or entry["replies"]:
                feedback.append(entry)

    return feedback


def save_feedback(feedback):
    """Save feedback report."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir = REPO_DIR / "harness" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"feedback-{timestamp}.json"
    with open(path, "w") as f:
        json.dump(feedback, f, indent=2, ensure_ascii=False)
    return path


def print_feedback(feedback):
    """Print feedback summary."""
    if not feedback:
        print("No feedback yet.")
        return

    print(f"\n{'='*50}")
    print(f"FEEDBACK COLLECTED: {len(feedback)} responses")
    print(f"{'='*50}")

    for fb in feedback:
        print(f"\n  {fb['member']}({fb['member_korean']}) → {fb['paper']}")
        for rxn in fb["reactions"]:
            print(f"    :{rxn['emoji']}: → {rxn['sentiment']}")
        for reply in fb["replies"]:
            print(f"    💬 \"{reply['text'][:100]}\"")


def main():
    creds = load_credentials()
    bot_token = creds["slack_bot_token"]

    print("Collecting feedback from member DMs...")
    feedback = collect_feedback(bot_token)
    print_feedback(feedback)

    if feedback:
        path = save_feedback(feedback)
        print(f"\n📝 Saved: {path}")

    return feedback


if __name__ == "__main__":
    main()
