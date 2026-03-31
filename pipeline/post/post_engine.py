"""
Paper Scout Post Engine — Atomic paper-to-Slack pipeline.

Handles: figure resolution → Slack upload → Block Kit composition → send.
One method call per paper: post_paper(paper_dict).
"""

import json
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

import requests

from .slack_upload import upload_figure, SlackUploadError
from .block_builder import build_post_blocks

logger = logging.getLogger("post_engine")

REPO_DIR = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = REPO_DIR / "runs"
FIGURES_DIR = RUNS_DIR / "figures"
PDFS_DIR = RUNS_DIR / "pdfs"


class PostEngine:
    """Atomic paper → Slack message engine."""

    def __init__(self, channel_id: str = "C06KJ95MGGZ", bot_token: str = None):
        self.channel_id = channel_id
        self.bot_token = bot_token or os.environ.get("SLACK_BOT_TOKEN", "")
        self.ranking = self._load_ranking()
        self.context = self._load_context()

    def _load_ranking(self) -> dict:
        path = FIGURES_DIR / "ranking_results.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    def _load_context(self) -> dict:
        path = REPO_DIR / "data" / "context-bundle.json"
        with open(path) as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # Figure resolution
    # ------------------------------------------------------------------

    def resolve_figure(self, paper_name: str) -> str | None:
        """
        Find the best figure PNG for a paper.
        Priority: ranking_results.json → scan figures dir → None
        """
        # From pre-computed ranking
        rank = self.ranking.get(paper_name, {})
        if rank.get("path"):
            fpath = Path(rank["path"])
            if not fpath.is_absolute():
                fpath = REPO_DIR / fpath
            if fpath.exists():
                cosine = rank.get("cosine", 0)
                logger.info(f"Figure from ranking: {fpath} (cosine={cosine:.3f})")
                return str(fpath)

        # Scan figures directory
        fig_dir = FIGURES_DIR / paper_name
        if fig_dir.exists():
            pngs = sorted(fig_dir.glob("page_*.png"), key=lambda p: p.stat().st_size, reverse=True)
            if pngs:
                logger.info(f"Figure from dir scan: {pngs[0]}")
                return str(pngs[0])

        logger.warning(f"No figure found for {paper_name}")
        return None

    # ------------------------------------------------------------------
    # Equation extraction
    # ------------------------------------------------------------------

    def extract_equation(self, paper_name: str) -> tuple | None:
        """Extract key equation from PDF. Returns (equation, explanation) or None."""
        # Check extraction summary
        summary_path = FIGURES_DIR / "extraction_summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                summary = json.load(f)
            eqs = summary.get(paper_name, {}).get("equations", [])
            if eqs:
                return eqs[0].get("text", ""), ""

        # Try from PDF directly
        try:
            sys.path.insert(0, str(REPO_DIR / "pipeline"))
            from importlib import import_module
            # Dynamic import to avoid circular deps
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "psfig", str(REPO_DIR / "pipeline" / "paper-scout-figures.py"))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            for pdf in PDFS_DIR.glob(f"*{paper_name}*"):
                eqs = mod.extract_equations_from_pdf(str(pdf))
                if eqs:
                    return eqs[0]["text"], ""
        except Exception as e:
            logger.warning(f"Equation extraction failed: {e}")

        return None

    # ------------------------------------------------------------------
    # Slack operations
    # ------------------------------------------------------------------

    def upload_figure_with_caption(
        self, figure_path: str, paper_name: str, caption: str
    ) -> str | None:
        """
        Upload figure with hook caption as initial_comment.
        Returns the message ts (for threading) or None on failure.

        This is the main message — figure + hook appear together in the channel.
        """
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        headers_json = {**headers, "Content-Type": "application/json"}

        try:
            fsize = Path(figure_path).stat().st_size
            fname = Path(figure_path).name

            # Step 1: Get upload URL
            r = requests.post(
                "https://slack.com/api/files.getUploadURLExternal",
                headers=headers,
                data={"filename": fname, "length": fsize},
                timeout=15,
            )
            d = r.json()
            if not d.get("ok"):
                raise SlackUploadError(d.get("error"))

            # Step 2: Upload file
            with open(figure_path, "rb") as f:
                requests.post(d["upload_url"], files={"file": f}, timeout=30)

            # Step 3: Complete with caption
            cosine = self.ranking.get(paper_name, {}).get("cosine", 0)
            fig_title = f"{paper_name} - Key Figure (embed-vl cosine={cosine:.3f})"

            r3 = requests.post(
                "https://slack.com/api/files.completeUploadExternal",
                headers=headers_json,
                json={
                    "files": [{"id": d["file_id"], "title": fig_title}],
                    "channel_id": self.channel_id,
                    "initial_comment": caption,
                },
                timeout=15,
            )
            d3 = r3.json()
            if not d3.get("ok"):
                raise SlackUploadError(d3.get("error"))

            logger.info(f"Figure+caption uploaded for {paper_name}")

            # Find the message ts for threading (retry with backoff)
            for attempt in range(4):
                time.sleep(1.5 + attempt)
                hist = requests.get(
                    "https://slack.com/api/conversations.history",
                    headers=headers_json,
                    params={"channel": self.channel_id, "limit": 5},
                    timeout=10,
                ).json()
                for msg in hist.get("messages", []):
                    if msg.get("files") or msg.get("subtype") == "file_share":
                        logger.info(f"Found file message ts: {msg['ts']}")
                        return msg["ts"]

            logger.warning("Could not find file message ts after upload")
            return None

        except (SlackUploadError, Exception) as e:
            logger.warning(f"Figure upload failed for {paper_name}: {e}")
            return None

    def send_blocks(self, blocks: list, fallback_text: str, thread_ts: str = None) -> dict:
        """Send Block Kit message. If thread_ts given, replies in thread with broadcast."""
        payload = {
            "channel": self.channel_id,
            "text": fallback_text,
            "blocks": blocks,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
            payload["reply_broadcast"] = True

        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        d = r.json()
        if not d.get("ok"):
            logger.error(f"chat.postMessage failed: {d.get('error')}")
        return d

    # ------------------------------------------------------------------
    # Main atomic pipeline
    # ------------------------------------------------------------------

    def post_paper(self, paper: dict, dry_run: bool = False) -> dict:
        """
        Full atomic pipeline:
        1. Upload figure + hook caption → main message (figure visible in channel)
        2. Send Block Kit details → thread reply (broadcast to channel)

        paper dict keys:
            name, doi, title, authors, journal, year, doi_url,
            hook, targeting_lines, dimension_tags, anchor_paper,
            equation_text (opt), equation_explanation (opt)

        targeting_lines: [{slack_id, name, project, description, quote (opt)}]

        Returns: {ok, ts, figure_uploaded, equation_included, blocks_count}
        """
        name = paper.get("name", "unknown")
        result = {
            "paper": name,
            "ok": False,
            "figure_uploaded": False,
            "equation_included": False,
            "fallback_used": None,
        }

        # Equation
        eq = self.extract_equation(name)
        eq_text = paper.get("equation_text") or (eq[0] if eq else None)
        eq_expl = paper.get("equation_explanation") or (eq[1] if eq else None)
        if eq_text:
            result["equation_included"] = True

        # Build detail blocks (thread reply — hook is in the figure caption)
        blocks, fallback = build_post_blocks(
            title=paper["title"],
            authors=paper["authors"],
            journal=paper["journal"],
            year=str(paper["year"]),
            doi_url=paper["doi_url"],
            summary=paper.get("summary", ""),
            figure_guide=paper.get("figure_guide", ""),
            equation_text=eq_text,
            equation_explanation=eq_expl,
            targeting_lines=paper["targeting_lines"],
            dimension_tags=paper["dimension_tags"],
            anchor_paper=paper["anchor_paper"],
        )
        result["blocks_count"] = len(blocks)

        if dry_run:
            result["ok"] = True
            result["blocks"] = blocks
            result["fallback_text"] = fallback
            return result

        # Step 1: Upload figure + hook caption as main message
        fig_path = self.resolve_figure(name)
        thread_ts = None

        if fig_path:
            caption = f":fire: *{paper['hook']}*"
            thread_ts = self.upload_figure_with_caption(fig_path, name, caption)
            if thread_ts:
                result["figure_uploaded"] = True

        # Step 2: Send detail blocks
        if thread_ts:
            # Thread reply (broadcast) — details appear under the figure
            resp = self.send_blocks(blocks, fallback, thread_ts=thread_ts)
        else:
            # No figure uploaded — send as standalone message (fallback)
            result["fallback_used"] = "no_figure"
            resp = self.send_blocks(blocks, fallback)

        result["ok"] = resp.get("ok", False)
        result["ts"] = resp.get("ts")
        result["error"] = resp.get("error")

        return result

    # ------------------------------------------------------------------
    # Batch posting
    # ------------------------------------------------------------------

    def post_batch(self, papers: list, dry_run: bool = False) -> list:
        """Post multiple papers sequentially (highest score first)."""
        results = []
        for paper in papers:
            r = self.post_paper(paper, dry_run=dry_run)
            results.append(r)
            logger.info(f"  {paper['name']}: {'OK' if r['ok'] else r.get('error', 'FAIL')}"
                        f" fig={'Y' if r['figure_uploaded'] else 'N'}"
                        f" eq={'Y' if r['equation_included'] else 'N'}")
            if not dry_run:
                time.sleep(1)  # Rate limit between posts

        # Save log
        log_path = RUNS_DIR / f"paper-scout-post-log-{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(log_path, "w") as f:
            json.dump(results, f, indent=2, default=str)

        return results
