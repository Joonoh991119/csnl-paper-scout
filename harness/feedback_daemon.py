#!/usr/bin/env python3
"""
Feedback Daemon — lightweight Slack listener (no LLM, no tokens wasted).

Runs in the background, polls Slack every 5 minutes for new reactions/replies
on Paper Scout posts. Writes new feedback to feedback-inbox.json.

Claude reads this inbox at session start and processes accumulated feedback.

Usage:
    python harness/feedback_daemon.py &          # background
    python harness/feedback_daemon.py --once      # single check
    launchctl load ~/Library/LaunchAgents/com.csnl.paper-scout-feedback.plist  # auto-start
"""

import json
import os
import sys
import time
import signal
import logging
import requests
from pathlib import Path
from datetime import datetime
from filelock import FileLock

REPO_DIR = Path(__file__).resolve().parent.parent
INBOX_PATH = REPO_DIR / "harness" / "feedback-inbox.json"
LOCK_PATH = INBOX_PATH.with_suffix(".lock")
STATE_PATH = REPO_DIR / "harness" / ".feedback-state.json"
POLL_INTERVAL = 300  # 5 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [feedback] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("feedback")

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
    "+1": "useful", "thumbsup": "useful",
    "thinking_face": "partial",
    "-1": "not_relevant", "thumbsdown": "not_relevant",
}

BOT_USER_ID = "U0ANKLV7W5P"  # Claude bot


def load_credentials():
    with open(REPO_DIR / "credentials.json") as f:
        return json.load(f)


def load_state():
    if STATE_PATH.exists():
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"last_check": {}, "seen_reactions": [], "seen_replies": []}


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def load_inbox():
    if INBOX_PATH.exists():
        with open(INBOX_PATH) as f:
            return json.load(f)
    return []


def save_inbox(inbox):
    lock = FileLock(str(LOCK_PATH), timeout=5)
    with lock:
        with open(INBOX_PATH, "w") as f:
            json.dump(inbox, f, indent=2, ensure_ascii=False)


def slack_get(endpoint, token, params=None):
    r = requests.get(
        f"https://slack.com/api/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=10,
    )
    return r.json()


def identify_paper(text):
    keywords = {
        "Serences": ["Serences", "sensory-mnemonic", "low-interference", "multiplexing"],
        "Ozkirli": ["Ozkirli", "mega-analysis", "deteriorates", "superiority"],
        "Costa": ["Costa", "categorical", "RSA", "CatVsMag"],
        "Pascucci": ["Pascucci", "drift-diffusion", "Preview"],
        "Rademaker": ["Rademaker", "top-down feedback", "STSP", "Feedback Model"],
    }
    for paper, kws in keywords.items():
        for kw in kws:
            if kw.lower() in text.lower():
                return paper
    return None


def check_feedback(token, state):
    """Check all DMs for new reactions and replies. Returns list of new feedback."""
    new_feedback = []

    for uid, member in MEMBERS.items():
        dm = member["dm"]
        oldest = state["last_check"].get(dm, "0")

        # Get recent messages
        resp = slack_get("conversations.history", token,
                         {"channel": dm, "limit": 15, "oldest": oldest})
        messages = resp.get("messages", [])

        for msg in messages:
            ts = msg.get("ts", "")
            text = msg.get("text", "")
            user = msg.get("user", "")

            # Check if this is a Paper Scout post (from bot)
            is_post = (user == BOT_USER_ID or msg.get("bot_id")) and (
                ":fire:" in text or "Paper Scout" in text or msg.get("files"))

            if is_post:
                paper = identify_paper(text)
                if not paper:
                    continue

                # Check reactions
                for rxn in msg.get("reactions", []):
                    rxn_name = rxn.get("name", "")
                    for rxn_user in rxn.get("users", []):
                        if rxn_user != BOT_USER_ID:
                            key = f"{dm}:{ts}:{rxn_name}:{rxn_user}"
                            if key not in state["seen_reactions"]:
                                state["seen_reactions"].append(key)
                                member_info = MEMBERS.get(rxn_user, {"name": rxn_user, "korean": ""})
                                new_feedback.append({
                                    "type": "reaction",
                                    "member": member_info["name"],
                                    "member_korean": member_info.get("korean", ""),
                                    "paper": paper,
                                    "emoji": rxn_name,
                                    "sentiment": REACTION_MAP.get(rxn_name, rxn_name),
                                    "timestamp": datetime.now().isoformat(),
                                })
                                log.info(f"New reaction: {member_info['name']} :{rxn_name}: on {paper}")

                # Check thread replies
                if msg.get("reply_count", 0) > 0:
                    replies_resp = slack_get("conversations.replies", token,
                                            {"channel": dm, "ts": ts, "limit": 20})
                    for reply in replies_resp.get("messages", []):
                        if reply.get("ts") == ts:
                            continue  # skip parent
                        reply_user = reply.get("user", "")
                        if reply_user == BOT_USER_ID:
                            continue
                        reply_key = f"{dm}:{reply['ts']}"
                        if reply_key not in state["seen_replies"]:
                            state["seen_replies"].append(reply_key)
                            member_info = MEMBERS.get(reply_user, {"name": reply_user, "korean": ""})
                            new_feedback.append({
                                "type": "reply",
                                "member": member_info["name"],
                                "member_korean": member_info.get("korean", ""),
                                "paper": paper,
                                "text": reply.get("text", ""),
                                "timestamp": datetime.now().isoformat(),
                            })
                            log.info(f"New reply: {member_info['name']} on {paper}: {reply.get('text','')[:60]}")

            # Check if this is a reply from a member (not in a thread — direct DM message)
            elif user == uid and not msg.get("thread_ts"):
                # Member sent a direct message — could be general feedback
                key = f"{dm}:{ts}:direct"
                if key not in state["seen_replies"]:
                    state["seen_replies"].append(key)
                    new_feedback.append({
                        "type": "direct_message",
                        "member": member["name"],
                        "member_korean": member["korean"],
                        "paper": None,
                        "text": text,
                        "timestamp": datetime.now().isoformat(),
                    })
                    log.info(f"Direct message from {member['name']}: {text[:60]}")

        # Update last check time
        if messages:
            state["last_check"][dm] = max(m["ts"] for m in messages)

    return new_feedback


def run_once(token):
    state = load_state()
    new_fb = check_feedback(token, state)
    if new_fb:
        inbox = load_inbox()
        inbox.extend(new_fb)
        save_inbox(inbox)
        log.info(f"Added {len(new_fb)} new feedback items to inbox")
    else:
        log.info("No new feedback")
    save_state(state)
    return new_fb


def run_daemon(token):
    log.info(f"Feedback daemon started (poll every {POLL_INTERVAL}s)")
    log.info(f"Inbox: {INBOX_PATH}")

    def handle_signal(sig, frame):
        log.info("Shutting down")
        sys.exit(0)
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while True:
        try:
            run_once(token)
        except Exception as e:
            log.error(f"Error: {e}")
        time.sleep(POLL_INTERVAL)


def main():
    creds = load_credentials()
    token = creds["slack_bot_token"]

    if "--once" in sys.argv:
        run_once(token)
    else:
        run_daemon(token)


if __name__ == "__main__":
    main()
