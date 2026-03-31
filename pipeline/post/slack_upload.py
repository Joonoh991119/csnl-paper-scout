"""Slack file upload via v2 external upload API."""

import os
import requests
from pathlib import Path


class SlackUploadError(Exception):
    pass


def get_bot_token():
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise SlackUploadError("SLACK_BOT_TOKEN not set")
    return token


def upload_figure(image_path: str, channel_id: str, title: str = "Figure") -> dict:
    """
    Upload image to Slack via external upload flow (v2 API).

    Returns: {file_id, permalink, ok}
    Raises SlackUploadError on failure.
    """
    token = get_bot_token()
    headers = {"Authorization": f"Bearer {token}"}
    headers_json = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    fpath = Path(image_path)
    if not fpath.exists():
        raise SlackUploadError(f"File not found: {image_path}")

    fsize = fpath.stat().st_size
    fname = fpath.name

    # Step 1: Get upload URL
    r = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers=headers,
        data={"filename": fname, "length": fsize},
        timeout=15,
    )
    d = r.json()
    if not d.get("ok"):
        raise SlackUploadError(f"getUploadURLExternal failed: {d.get('error')}")

    upload_url = d["upload_url"]
    file_id = d["file_id"]

    # Step 2: Upload file content
    with open(fpath, "rb") as f:
        r2 = requests.post(upload_url, files={"file": (fname, f)}, timeout=30)
    if r2.status_code not in (200, 201):
        raise SlackUploadError(f"File upload failed: HTTP {r2.status_code}")

    # Step 3: Complete upload and share to channel
    r3 = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers=headers_json,
        json={
            "files": [{"id": file_id, "title": title}],
            "channel_id": channel_id,
        },
        timeout=15,
    )
    d3 = r3.json()
    if not d3.get("ok"):
        raise SlackUploadError(f"completeUploadExternal failed: {d3.get('error')}")

    # Extract permalink
    permalink = ""
    for f_obj in d3.get("files", []):
        permalink = f_obj.get("permalink", "") or f_obj.get("url_private", "")
        break

    return {"file_id": file_id, "permalink": permalink, "ok": True}
