#!/usr/bin/env python3
"""
Paper Scout — Slack Bot Sender

Claude bot으로 Slack 메시지를 전송한다.
claude.ai Slack MCP는 사용자 계정으로 전송되므로,
bot token을 직접 사용하여 Claude bot identity로 전송.

Usage:
    python slack_bot.py --channel C0ANVB92GMP --message "test"
    python slack_bot.py --user U06JGAX5HD5 --message "DM test"
    python slack_bot.py --user U06JGAX5HD5 --file runs/paper-scout-post-2026-03-31.md
"""

import argparse
import json
import os
import requests

BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise EnvironmentError("SLACK_BOT_TOKEN environment variable is required")
API_BASE = "https://slack.com/api"


def open_dm(user_id: str) -> str:
    """Open a DM channel with a user. Returns channel ID."""
    r = requests.post(
        f"{API_BASE}/conversations.open",
        headers={"Authorization": f"Bearer {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"users": user_id},
        timeout=10,
    )
    data = r.json()
    if not data["ok"]:
        raise Exception(f"conversations.open failed: {data.get('error')}")
    return data["channel"]["id"]


def send_message(channel_id: str, text: str, thread_ts: str = None, blocks: list = None) -> dict:
    """Send a message to a channel or DM. Supports Block Kit via blocks param."""
    payload = {"channel": channel_id, "text": text}
    if thread_ts:
        payload["thread_ts"] = thread_ts
    if blocks:
        payload["blocks"] = blocks

    r = requests.post(
        f"{API_BASE}/chat.postMessage",
        headers={"Authorization": f"Bearer {BOT_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )
    data = r.json()
    if not data["ok"]:
        raise Exception(f"chat.postMessage failed: {data.get('error')}")
    return {"channel": channel_id, "ts": data["ts"], "ok": True}


def send_dm(user_id: str, text: str) -> dict:
    """Send a DM to a user via bot."""
    channel = open_dm(user_id)
    return send_message(channel, text)


def read_replies(channel_id: str, message_ts: str) -> list:
    """Read thread replies to a message."""
    r = requests.get(
        f"{API_BASE}/conversations.replies",
        headers={"Authorization": f"Bearer {BOT_TOKEN}"},
        params={"channel": channel_id, "ts": message_ts},
        timeout=10,
    )
    data = r.json()
    if not data["ok"]:
        return []
    # Skip the parent message, return only replies
    return [m for m in data.get("messages", []) if m.get("ts") != message_ts]


def main():
    parser = argparse.ArgumentParser(description="Paper Scout Slack Bot Sender")
    parser.add_argument("--channel", help="Channel ID to post to")
    parser.add_argument("--user", help="User ID to DM")
    parser.add_argument("--message", help="Message text")
    parser.add_argument("--file", help="Read message from file")
    args = parser.parse_args()

    text = args.message
    if args.file:
        with open(args.file) as f:
            text = f.read()

    if not text:
        print("No message provided")
        return

    if args.user:
        result = send_dm(args.user, text)
    elif args.channel:
        result = send_message(args.channel, text)
    else:
        print("Provide --channel or --user")
        return

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
