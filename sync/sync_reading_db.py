#!/usr/bin/env python3
"""
Paper Scout — Slack Reading DB Sync

#study-paper-reading 채널에서 멤버들의 논문 독후감을 파싱하여
reading-db와 member-profiles를 자동 업데이트한다.

Usage:
    python sync_reading_db.py                    # 마지막 동기화 이후 새 메시지만
    python sync_reading_db.py --full             # 전체 채널 히스토리 동기화
    python sync_reading_db.py --since 2026-03-01 # 특정 날짜 이후
    python sync_reading_db.py --dry-run          # 파싱만 하고 저장하지 않음

이 스크립트는 직접 Slack API를 호출하지 않는다.
대신 Claude Code의 Slack MCP를 통해 채널을 읽고,
파싱된 결과를 JSON DB로 저장한다.

자동화 시나리오:
1. Claude Code에서 `paper scout sync` 명령으로 실행
2. Claude가 Slack MCP로 채널 메시지를 읽고 이 모듈의 파서에 전달
3. 파서가 논문 메타데이터 + 멤버 관심사를 추출
4. DB 파일 업데이트
"""

import json
import re
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# --- Paths ---
REPO_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_DIR / "data"
READING_DB_DIR = DATA_DIR / "reading-db"
PROFILE_DIR = DATA_DIR / "member-profiles"
CONTEXT_BUNDLE = DATA_DIR / "context-bundle.json"
SYNC_STATE_FILE = REPO_DIR / "sync" / ".sync-state.json"

READING_DB_DIR.mkdir(parents=True, exist_ok=True)
PROFILE_DIR.mkdir(parents=True, exist_ok=True)

# --- Load context ---
def load_context():
    with open(CONTEXT_BUNDLE) as f:
        return json.load(f)


def load_reading_db() -> list:
    """Load existing reading DB."""
    db_file = READING_DB_DIR / "study_paper_reading_db.json"
    if db_file.exists():
        with open(db_file) as f:
            return json.load(f)
    return []


def save_reading_db(entries: list):
    """Save reading DB."""
    db_file = READING_DB_DIR / "study_paper_reading_db.json"
    with open(db_file, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def load_member_profile(member_id: str) -> dict:
    """Load a member's profile."""
    profile_file = PROFILE_DIR / f"{member_id}.json"
    if profile_file.exists():
        with open(profile_file) as f:
            return json.load(f)
    return {
        "member_id": member_id,
        "papers_read": 0,
        "topics": defaultdict(int),
        "authors_tracked": defaultdict(int),
        "last_updated": None,
        "reading_history": [],
    }


def save_member_profile(member_id: str, profile: dict):
    """Save a member's profile."""
    profile_file = PROFILE_DIR / f"{member_id}.json"
    # Convert defaultdicts to regular dicts for JSON serialization
    profile_copy = dict(profile)
    if isinstance(profile_copy.get("topics"), defaultdict):
        profile_copy["topics"] = dict(profile_copy["topics"])
    if isinstance(profile_copy.get("authors_tracked"), defaultdict):
        profile_copy["authors_tracked"] = dict(profile_copy["authors_tracked"])
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(profile_copy, f, ensure_ascii=False, indent=2)


def load_sync_state() -> dict:
    """Load last sync timestamp."""
    if SYNC_STATE_FILE.exists():
        with open(SYNC_STATE_FILE) as f:
            return json.load(f)
    return {"last_sync_ts": None, "last_sync_date": None}


def save_sync_state(ts: str):
    """Save sync state."""
    SYNC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SYNC_STATE_FILE, "w") as f:
        json.dump({
            "last_sync_ts": ts,
            "last_sync_date": datetime.now().isoformat(),
        }, f, indent=2)


# ============================================================
# PARSER — Slack 메시지에서 논문 정보 추출
# ============================================================

# Citation patterns
CITATION_PATTERNS = [
    # Pattern A: "Last, F., Last, F., & Last, F. (Year). Title. Journal, vol(issue), pages."
    # Handles: Neri, P., & Heeger, D. J. (2002). Spatiotemporal mechanisms...
    # Handles: Yang, J., Zhang, H., & Lim, S. (2024). Sensory-memory interactions...
    re.compile(
        r"(?P<authors>[A-Z][a-zA-Z\-]+,\s*[A-Z]\.?"
        r"(?:[,\s&]+[A-Z][a-zA-Z\-]+,?\s*[A-Z]\.?\s*[A-Z]?\.?)*)"
        r"\s*\((?P<year>\d{4})\)\.\s*"
        r'["\u201c]?(?P<title>[A-Z][^"\u201d\n.]{10,200}?)["\u201d.]+'
        r"\s*_?(?P<journal>[A-Z][a-zA-Z\s&:.]+?)_?"
        r"(?:[,\s]+_?\d+_?(?:\s*\(\d+\))?"
        r"(?:[,\s]+\d[\d\u2013\-]+)?)?"
        r"\s*\.?"
    ),
    # Pattern B: "Last Last, Last Last (Year). "Title" Journal"
    # Handles: Stein H, Barbosa J, Bhatt DV (2024). "Unifying network..."
    re.compile(
        r"(?P<authors>[A-Z][a-zA-Z\-]+\s+[A-Z][A-Za-z]*"
        r"(?:[,\s]+[A-Z][a-zA-Z\-]+\s+[A-Z][A-Za-z]*)*"
        r"(?:\s+et\s+al\.?)?)"
        r"\s*\((?P<year>\d{4})\)[.\s]*"
        r'["\u201c](?P<title>[^"\u201d\n]{10,200})["\u201d][.\s]*'
        r"(?:_(?P<journal>[^_\n]+)_|(?P<journal2>[A-Z][a-zA-Z\s&]+))?"
    ),
    # Pattern C: "Last et al. (Year) Title"
    re.compile(
        r"(?P<authors>[A-Z][a-zA-Z\-]+(?:\s+et\s+al\.?))"
        r"\s*\((?P<year>\d{4})\)"
        r"[.\s:]*(?P<title>[A-Z][^\n]{10,200})"
    ),
    # Pattern D: First line = citation, flexible (fallback)
    # Grab first line that has (YEAR) and preceding author-like text
    re.compile(
        r"(?P<authors>[A-Z][a-zA-Z\-., &]+?)\s*"
        r"\((?P<year>\d{4})\)[.\s]*"
        r"(?P<title>[A-Z][^\n]{10,200})"
    ),
]

# DOI pattern
DOI_PATTERN = re.compile(r"(?:doi[:\s]*|https?://doi\.org/)?(10\.\d{4,}/[^\s\]>]+)", re.I)

# Section markers (Korean reading notes format)
SECTION_MARKERS = {
    "범위": "scope",
    "내용": "content",
    "정리": "summary",
    "생각": "thoughts",
    "궁금": "questions",
    "의문": "questions",
}

# Topic keywords for auto-classification
TOPIC_KEYWORDS = {
    "Bayesian inference": ["bayesian", "prior", "posterior", "likelihood", "bayes"],
    "Serial dependence": ["serial dependence", "serial bias", "history effect", "previous trial"],
    "Working memory": ["working memory", "WM", "delay period", "retention", "maintenance"],
    "Decision making": ["decision", "choice", "evidence accumulation", "drift-diffusion"],
    "Visual perception": ["visual", "perception", "orientation", "contrast", "motion"],
    "fMRI": ["fmri", "bold", "voxel", "hemodynamic"],
    "Computational modeling": ["model", "simulation", "neural network", "RNN", "attractor"],
    "Efficient coding": ["efficient coding", "optimal coding", "fisher information"],
    "Bias": ["bias", "contraction", "repulsion", "attraction", "systematic error"],
    "Neural geometry": ["manifold", "subspace", "orthogonal", "geometry", "population code"],
    "Attention": ["attention", "attentional", "salien"],
    "Eye movements": ["saccade", "eye movement", "fixation", "gaze"],
    "Psychophysics": ["psychophysic", "threshold", "just noticeable", "weber"],
    "Neural coding": ["tuning curve", "receptive field", "pRF", "population response"],
}


def parse_citation(text: str) -> dict | None:
    """Extract paper citation from message text."""
    for pattern in CITATION_PATTERNS:
        match = pattern.search(text)
        if match:
            d = match.groupdict()
            journal = d.get("journal") or d.get("journal2") or ""
            return {
                "authors": d["authors"].strip(),
                "year": int(d["year"]),
                "title": d["title"].strip().rstrip("."),
                "journal": journal.strip().rstrip(",. "),
            }
    return None


def parse_doi(text: str) -> str | None:
    """Extract DOI from message text."""
    match = DOI_PATTERN.search(text)
    if match:
        return match.group(1).rstrip(".")
    return None


def parse_sections(text: str) -> dict:
    """Extract Korean reading note sections."""
    sections = {}
    lines = text.split("\n")
    current_section = None
    current_content = []

    for line in lines:
        found = False
        for marker, key in SECTION_MARKERS.items():
            if line.strip().startswith(marker):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = key
                # Content after the marker on same line
                after = line.split(":", 1)[-1].strip() if ":" in line else ""
                current_content = [after] if after else []
                found = True
                break
        if not found and current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def classify_topics(text: str) -> list[str]:
    """Auto-classify paper topics from text."""
    text_lower = text.lower()
    topics = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            topics.append(topic)
    return topics


def extract_authors_from_citation(authors_str: str) -> list[str]:
    """Extract individual author last names."""
    # Remove "et al."
    clean = re.sub(r"\s*et\s+al\.?\s*", "", authors_str)

    # Format A: "Last, F., Last, F." — split by " & " or ", " between author groups
    if re.search(r"[A-Z][a-z]+,\s*[A-Z]\.", clean):
        # Split author groups: "Neri, P., & Heeger, D. J." → ["Neri", "Heeger"]
        groups = re.split(r"\s*&\s*", clean)
        last_names = []
        for g in groups:
            # First word before comma is last name
            match = re.match(r"([A-Z][a-zA-Z\-]+)", g.strip())
            if match:
                last_names.append(match.group(1))
        return last_names

    # Format B: "Last F, Last F" — "Stein H, Barbosa J"
    if re.search(r"[A-Z][a-z]+\s+[A-Z][A-Z]?(?:,|$)", clean):
        parts = re.split(r"\s*,\s*", clean)
        last_names = []
        for p in parts:
            match = re.match(r"([A-Z][a-zA-Z\-]+)", p.strip())
            if match:
                last_names.append(match.group(1))
        return last_names

    # Fallback: split by comma/& and take first word of each
    parts = re.split(r"\s*[,&]\s*|\s+and\s+", clean)
    return [p.split()[0] for p in parts if p.strip() and len(p.strip()) > 1]


def extract_journal_from_text(text: str) -> str:
    """Extract journal name from the first few lines of message text."""
    # Common journal patterns in citations
    journal_patterns = [
        re.compile(r"_([A-Z][a-zA-Z\s&:.]+?)_"),  # _Journal Name_
        re.compile(r"(?:Nature\s+\w+|Science\s+\w+|eLife|Neuron|PNAS|"
                   r"Journal\s+of\s+\w+|PLoS\s+\w+|Nature|Science|"
                   r"NeuroImage|Cerebral\s+Cortex|Current\s+Biology|"
                   r"Proceedings\s+of\s+the\s+Royal|Nat(?:ure)?\s+(?:Rev|Neurosci|Commun))",
                   re.I),
    ]
    first_lines = text.split("\n")[0:3]
    combined = " ".join(first_lines)
    for pattern in journal_patterns:
        match = pattern.search(combined)
        if match:
            journal = match.group(1) if match.lastindex else match.group(0)
            return journal.strip().rstrip(",. ")
    return ""


# ============================================================
# SYNC ENGINE
# ============================================================

def parse_slack_message(message: dict) -> dict | None:
    """
    Parse a single Slack message into a reading DB entry.

    Expected message format (from Slack MCP):
    {
        "user": "U07728304R5",
        "user_name": "Boyun Lee",
        "text": "Yang, J., Zhang, H., & Lim, S. (2024)...\n범위: methods\n내용: ...\n생각: ...",
        "ts": "1711540623.862469",
        "date": "2026-03-27 22:23:43 KST"
    }
    """
    text = message.get("text", "")
    if not text or len(text) < 50:
        return None

    citation = parse_citation(text)
    if not citation:
        return None

    doi = parse_doi(text)
    sections = parse_sections(text)
    topics = classify_topics(text)
    authors = extract_authors_from_citation(citation["authors"])

    # Try to get journal from citation, fallback to text extraction
    journal = citation["journal"]
    if not journal or len(journal) < 3:
        journal = extract_journal_from_text(text)

    return {
        "paper": {
            "title": citation["title"],
            "authors": citation["authors"],
            "year": citation["year"],
            "journal": journal,
            "doi": doi,
        },
        "reader": {
            "user_id": message.get("user", ""),
            "user_name": message.get("user_name", ""),
        },
        "reading": {
            "scope": sections.get("scope", ""),
            "summary": sections.get("summary") or sections.get("content", ""),
            "thoughts": sections.get("thoughts", ""),
            "questions": sections.get("questions", ""),
        },
        "metadata": {
            "topics": topics,
            "authors_parsed": authors,
            "message_ts": message.get("ts", ""),
            "date": message.get("date", ""),
            "char_count": len(text),
        },
    }


def update_member_profile(member_id: str, entry: dict):
    """Update member profile with new reading entry."""
    profile = load_member_profile(member_id)

    # Ensure defaultdicts
    if not isinstance(profile.get("topics"), defaultdict):
        profile["topics"] = defaultdict(int, profile.get("topics", {}))
    if not isinstance(profile.get("authors_tracked"), defaultdict):
        profile["authors_tracked"] = defaultdict(int, profile.get("authors_tracked", {}))

    # Update counts
    profile["papers_read"] = profile.get("papers_read", 0) + 1

    # Update topics
    for topic in entry["metadata"]["topics"]:
        profile["topics"][topic] += 1

    # Update tracked authors
    for author in entry["metadata"]["authors_parsed"]:
        profile["authors_tracked"][author] += 1

    # Append to reading history (keep last 500)
    history_entry = {
        "title": entry["paper"]["title"],
        "date": entry["metadata"]["date"],
        "topics": entry["metadata"]["topics"],
    }
    if "reading_history" not in profile:
        profile["reading_history"] = []
    profile["reading_history"].append(history_entry)
    profile["reading_history"] = profile["reading_history"][-500:]

    profile["last_updated"] = datetime.now().isoformat()

    save_member_profile(member_id, profile)


def sync_messages(messages: list[dict], dry_run: bool = False) -> dict:
    """
    Process a batch of Slack messages and update DBs.

    Args:
        messages: List of Slack message dicts (from MCP or manual input)
        dry_run: If True, parse only without saving

    Returns:
        Summary dict with counts and parsed entries
    """
    db = load_reading_db()
    existing_dois = {e["paper"].get("doi") for e in db if e.get("paper", {}).get("doi")}
    existing_titles = {e["paper"].get("title", "").lower() for e in db}

    new_entries = []
    skipped = 0
    errors = []

    for msg in messages:
        try:
            entry = parse_slack_message(msg)
            if not entry:
                continue

            # Dedup by DOI
            if entry["paper"]["doi"] and entry["paper"]["doi"] in existing_dois:
                skipped += 1
                continue

            # Dedup by title (fuzzy)
            title_lower = entry["paper"]["title"].lower()
            if title_lower in existing_titles:
                skipped += 1
                continue

            new_entries.append(entry)
            existing_dois.add(entry["paper"]["doi"])
            existing_titles.add(title_lower)

        except Exception as e:
            errors.append({"message_ts": msg.get("ts"), "error": str(e)})

    if not dry_run and new_entries:
        # Update reading DB
        db.extend(new_entries)
        save_reading_db(db)

        # Update member profiles
        for entry in new_entries:
            member_id = entry["reader"]["user_id"]
            if member_id:
                update_member_profile(member_id, entry)

        # Update sync state
        if messages:
            latest_ts = max(m.get("ts", "0") for m in messages)
            save_sync_state(latest_ts)

    return {
        "total_messages": len(messages),
        "parsed": len(new_entries) + skipped,
        "new_entries": len(new_entries),
        "skipped_duplicates": skipped,
        "errors": len(errors),
        "error_details": errors,
        "entries": new_entries if dry_run else [],
    }


# ============================================================
# CONTEXT BUNDLE AUTO-UPDATE
# ============================================================

def update_context_bundle_from_profiles():
    """
    member-profiles에서 관심사를 추출하여 context-bundle.json의
    gist_relevance를 자동 업데이트한다.

    이 함수는 기존 프로젝트 기술은 건드리지 않고,
    reading profile 기반의 관심사만 추가한다.
    """
    ctx = load_context()
    profiles_dir = PROFILE_DIR

    if not profiles_dir.exists():
        return {"status": "no_profiles", "updated": 0}

    # Map Slack ID → member abbreviation
    id_to_member = {v: k for k, v in ctx["slack"]["member_ids"].items()}

    updated = 0
    for profile_file in profiles_dir.glob("*.json"):
        with open(profile_file) as f:
            profile = json.load(f)

        member_id = profile.get("member_id", "")
        member_abbr = id_to_member.get(member_id)
        if not member_abbr:
            continue

        # Extract top topics (sorted by frequency)
        topics = profile.get("topics", {})
        if not topics:
            continue

        top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:8]
        topic_str = ", ".join(f"{t[0]} ({t[1]})" for t in top_topics)

        # Extract top tracked authors
        authors = profile.get("authors_tracked", {})
        top_authors = sorted(authors.items(), key=lambda x: x[1], reverse=True)[:10]
        author_str = ", ".join(f"{a[0]} ({a[1]})" for a in top_authors)

        # Find which group the member belongs to
        for group_key, group_data in ctx["member_groups"].items():
            if member_abbr in group_data.get("members", []):
                # Add reading_profile field to member's projects
                if member_abbr not in group_data.get("projects", {}):
                    group_data["projects"][member_abbr] = {}

                group_data["projects"][member_abbr]["_reading_profile"] = {
                    "papers_read": profile.get("papers_read", 0),
                    "top_topics": topic_str,
                    "top_authors": author_str,
                    "last_updated": profile.get("last_updated"),
                }
                updated += 1
                break

    # Save updated context bundle
    with open(CONTEXT_BUNDLE, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)

    return {"status": "ok", "updated": updated}


# ============================================================
# CLI
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Paper Scout Slack Reading DB Sync")
    parser.add_argument("--full", action="store_true", help="Full channel history sync")
    parser.add_argument("--since", type=str, help="Sync since date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, don't save")
    parser.add_argument("--update-context", action="store_true",
                        help="Update context-bundle from member profiles")
    parser.add_argument("--input", type=str,
                        help="Path to JSON file with pre-fetched messages")
    args = parser.parse_args()

    if args.update_context:
        result = update_context_bundle_from_profiles()
        print(json.dumps(result, indent=2))
        return

    if args.input:
        # Process pre-fetched messages from file
        with open(args.input) as f:
            messages = json.load(f)
        result = sync_messages(messages, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Interactive mode — print instructions for Claude Code
    sync_state = load_sync_state()
    print("=" * 60)
    print("Paper Scout — Slack Reading DB Sync")
    print("=" * 60)
    print()

    if args.full:
        print("Mode: FULL SYNC (entire channel history)")
        print()
        print("Claude Code에서 다음 명령을 실행하세요:")
        print()
        print('  paper scout sync full')
        print()
        print("Claude가 Slack MCP로 전체 채널을 읽고")
        print("이 스크립트의 sync_messages()에 전달합니다.")
    elif args.since:
        print(f"Mode: SYNC SINCE {args.since}")
    else:
        last = sync_state.get("last_sync_date", "never")
        print(f"Mode: INCREMENTAL (last sync: {last})")
        print()
        print("Claude Code에서 다음 명령을 실행하세요:")
        print()
        print('  paper scout sync')

    print()
    print("또는 메시지 JSON 파일을 직접 전달:")
    print("  python sync_reading_db.py --input messages.json")
    print()
    print(f"Current DB: {len(load_reading_db())} entries")
    print(f"Profiles: {len(list(PROFILE_DIR.glob('*.json')))} members")


if __name__ == "__main__":
    main()
