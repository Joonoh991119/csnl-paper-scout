"""
Style-Learning State Management.

Handles:
  - Persistent state (JSON) across runs
  - Zotero SQLite queries for paper discovery
  - Queue management (tier-sorted)
  - Convergence detection
"""

import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent
BLITZ_DIR = REPO_DIR / "blitz"
STATE_DIR = BLITZ_DIR / "style_knowledge"
STATE_PATH = STATE_DIR / "state.json"
LOG_PATH = STATE_DIR / "analysis_log.jsonl"
STATS_PATH = STATE_DIR / "pattern_stats.json"

ZOTERO_DB = Path.home() / "Zotero" / "zotero.sqlite"
ZOTERO_STORAGE = Path.home() / "Zotero" / "storage"

# Journal tiers — higher tier = higher design standards
JOURNAL_TIERS = {
    1: [
        'Nature', 'Science', 'Cell',
        'Neuron', 'Nature Neuroscience',
    ],
    2: [
        'eLife',
        'Proceedings of the National Academy of Sciences',
        'Proceedings of the National Academy of Sciences of the United States of America',
        'PNAS Nexus',
        'Nature Communications', 'Nature Human Behaviour',
        'Nature Reviews Neuroscience',
        'Current Biology',
    ],
    3: [
        'Journal of Neuroscience', 'The Journal of Neuroscience',
        'Trends in Cognitive Sciences', 'Trends in Neurosciences',
        'PLOS Computational Biology', 'PLoS Comput. Biol.',
        'Journal of Cognitive Neuroscience',
        'Psychological Review', 'Cognition',
        'Journal of Vision', 'Vision Research',
        'PLOS Biology', 'Scientific Reports',
        'iScience',
        'Cell Reports', 'Nature Reviews Psychology',
        'Psychological Science', 'Cerebral Cortex',
        'NeuroImage', 'Brain', 'Cortex',
        'Frontiers in Neuroscience', 'Frontiers in Psychology',
        'Frontiers in Computational Neuroscience',
        'Journal of Experimental Psychology: General',
        'Journal of Mathematical Psychology',
        'Behavioral and Brain Sciences',
        'Brain and Cognition', 'Brain Stimulation',
        'Philosophical Transactions of the Royal Society B: Biological Sciences',
        'Proceedings of the Royal Society B: Biological Sciences',
        'PLOS ONE',
        'Annual Review of Neuroscience', 'Annual Review of Psychology',
    ],
}

# Flatten for SQL query
ALL_JOURNALS = []
JOURNAL_TO_TIER = {}
for tier, journals in JOURNAL_TIERS.items():
    for j in journals:
        ALL_JOURNALS.append(j)
        JOURNAL_TO_TIER[j] = tier


# ── State Management ─────────────────────────────────────────

def _empty_state() -> dict:
    return {
        "version": 1,
        "created": datetime.now(timezone.utc).isoformat(),
        "last_run": None,
        "loop_count": 0,
        "papers_analyzed": {},
        "queue": [],
        "convergence": {
            "patterns_per_batch": [],
            "gan_pass_rates": [],
            "consecutive_zero_batches": 0,
        },
        "pattern_stats": {
            "n_figures_analyzed": 0,
            "layout_counts": {},
            "spine_counts": {},
            "panel_label_counts": {},
            "aesthetic_counts": {},
            "color_clusters": [],
            "element_sums": {},
            "whitespace_values": [],
            "figure_type_counts": {},
        },
    }


def load_state(path: Path = STATE_PATH) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return _empty_state()


def save_state(state: dict, path: Path = STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    # Atomic write
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, 'w') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise


# ── Zotero Query ──────────────────────────────────────────────

def _query_zotero() -> list[dict]:
    """Query Zotero DB for papers with PDFs from target journals."""
    db_uri = f"file:{ZOTERO_DB}?mode=ro&immutable=1"
    conn = sqlite3.connect(db_uri, uri=True)
    conn.row_factory = sqlite3.Row

    placeholders = ",".join(["?"] * len(ALL_JOURNALS))
    query = f"""
    SELECT
        i.itemID,
        iv_title.value as title,
        iv_journal.value as journal,
        ia.path as attachment_path,
        i_att.key as storage_key
    FROM items i
    JOIN itemData id_title ON i.itemID = id_title.itemID
    JOIN fields f_title ON id_title.fieldID = f_title.fieldID
        AND f_title.fieldName = 'title'
    JOIN itemDataValues iv_title ON id_title.valueID = iv_title.valueID
    JOIN itemData id_journal ON i.itemID = id_journal.itemID
    JOIN fields f_journal ON id_journal.fieldID = f_journal.fieldID
        AND f_journal.fieldName = 'publicationTitle'
    JOIN itemDataValues iv_journal ON id_journal.valueID = iv_journal.valueID
    JOIN itemAttachments ia ON ia.parentItemID = i.itemID
        AND ia.contentType = 'application/pdf'
    JOIN items i_att ON ia.itemID = i_att.itemID
    WHERE iv_journal.value IN ({placeholders})
        AND ia.path IS NOT NULL
        AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
    ORDER BY iv_journal.value, iv_title.value
    """

    rows = conn.execute(query, ALL_JOURNALS).fetchall()
    conn.close()

    papers = []
    seen_titles = set()
    for row in rows:
        title = row["title"]
        if title in seen_titles:
            continue
        seen_titles.add(title)

        storage_key = row["storage_key"]
        if not storage_key:
            # Try extracting from path like "storage:filename.pdf"
            path = row["attachment_path"] or ""
            if path.startswith("storage:"):
                # Key is the parent folder name, need to find it
                continue
            continue

        journal = row["journal"]
        tier = JOURNAL_TO_TIER.get(journal, 4)

        papers.append({
            "storage_key": storage_key,
            "title": title,
            "journal": journal,
            "tier": tier,
        })

    return papers


def build_queue(state: dict) -> list[dict]:
    """Build paper queue from Zotero, excluding already-analyzed papers."""
    all_papers = _query_zotero()
    analyzed = set(state.get("papers_analyzed", {}).keys())
    queue = [p for p in all_papers if p["storage_key"] not in analyzed]
    # Sort by tier (1 first), then journal name
    queue.sort(key=lambda p: (p["tier"], p["journal"], p["title"]))
    return queue


def dequeue(state: dict, batch_size: int) -> list[dict]:
    """Pop next batch from queue."""
    batch = state["queue"][:batch_size]
    state["queue"] = state["queue"][batch_size:]
    return batch


def find_pdf(storage_key: str) -> Path | None:
    """Find PDF file in Zotero storage by key."""
    folder = ZOTERO_STORAGE / storage_key
    if not folder.exists():
        return None
    pdfs = list(folder.glob("*.pdf"))
    return pdfs[0] if pdfs else None


# ── Analysis Recording ────────────────────────────────────────

def mark_analyzed(state: dict, storage_key: str, paper_info: dict,
                  n_figures: int, n_analyzed: int, new_patterns: int):
    state["papers_analyzed"][storage_key] = {
        "title": paper_info.get("title", ""),
        "journal": paper_info.get("journal", ""),
        "tier": paper_info.get("tier", 4),
        "figures_extracted": n_figures,
        "figures_analyzed": n_analyzed,
        "new_patterns_found": new_patterns,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def append_to_log(results: list[dict], path: Path = LOG_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ── Pattern Statistics ────────────────────────────────────────

def _hex_distance(c1: str, c2: str) -> float:
    """RGB Euclidean distance between two hex colors."""
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    return ((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2) ** 0.5


def _is_new_color(hex_color: str, existing_clusters: list[dict],
                  threshold: float = 40.0) -> bool:
    """Check if a color is far enough from all known clusters."""
    for cluster in existing_clusters:
        for centroid in cluster.get("colors", []):
            if _hex_distance(hex_color, centroid) < threshold:
                return False
    return True


def count_new_patterns(results: list[dict], stats: dict) -> int:
    """Count genuinely new patterns in this batch."""
    new = 0

    for r in results:
        # New layout pattern
        layout = r.get("layout", {}).get("pattern", "")
        if layout and stats.get("layout_counts", {}).get(layout, 0) == 0:
            new += 1

        # New color cluster
        for hex_c in r.get("colors", {}).get("dominant_palette", []):
            if hex_c and len(hex_c) == 7 and hex_c.startswith("#"):
                if _is_new_color(hex_c, stats.get("color_clusters", [])):
                    new += 1

        # New element combination
        elements = r.get("elements", {})
        combo = tuple(sorted(k for k, v in elements.items() if v and v > 0))
        # Track unique combos (simple heuristic)
        if combo and str(combo) not in stats.get("_seen_combos", set()):
            new += 1

    return new


def update_pattern_stats(state: dict, results: list[dict]):
    """Update aggregated statistics with new batch results."""
    stats = state["pattern_stats"]
    stats["n_figures_analyzed"] += len(results)

    for r in results:
        # Figure type
        ft = r.get("figure_type", "unknown")
        stats["figure_type_counts"][ft] = stats["figure_type_counts"].get(ft, 0) + 1

        # Layout
        layout = r.get("layout", {}).get("pattern", "")
        if layout:
            stats["layout_counts"][layout] = stats["layout_counts"].get(layout, 0) + 1

        # Spines
        spine = r.get("spine_style", "")
        if spine:
            stats["spine_counts"][spine] = stats["spine_counts"].get(spine, 0) + 1

        # Panel labels
        pl = r.get("typography", {}).get("panel_label_style", "")
        if pl:
            stats["panel_label_counts"][pl] = stats["panel_label_counts"].get(pl, 0) + 1

        # Aesthetic
        ae = r.get("overall_aesthetic", "")
        if ae:
            stats["aesthetic_counts"][ae] = stats["aesthetic_counts"].get(ae, 0) + 1

        # Whitespace
        ws = r.get("whitespace_ratio", None)
        if ws is not None:
            stats["whitespace_values"].append(ws)

        # Colors → clusters
        palette = r.get("colors", {}).get("dominant_palette", [])
        for hex_c in palette:
            if hex_c and len(hex_c) == 7 and hex_c.startswith("#"):
                found = False
                for cluster in stats["color_clusters"]:
                    for centroid in cluster.get("colors", []):
                        if _hex_distance(hex_c, centroid) < 40:
                            cluster["count"] = cluster.get("count", 0) + 1
                            found = True
                            break
                    if found:
                        break
                if not found:
                    stats["color_clusters"].append({
                        "colors": [hex_c],
                        "count": 1,
                    })

        # Elements
        for k, v in r.get("elements", {}).items():
            if v and isinstance(v, (int, float)):
                stats["element_sums"][k] = stats["element_sums"].get(k, 0) + v

    # Save stats separately too
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_PATH, "w") as f:
        json.dump(stats, f, indent=2)


# ── Convergence ───────────────────────────────────────────────

def check_convergence(state: dict) -> bool:
    """Check if learning has converged."""
    conv = state["convergence"]
    pats = conv["patterns_per_batch"]
    gan_rates = conv["gan_pass_rates"]

    # Criterion 1: two consecutive zero-pattern batches
    if len(pats) >= 2 and pats[-1] == 0 and pats[-2] == 0:
        return True

    # Criterion 2: GAN pass rate >= 80%
    if gan_rates and gan_rates[-1] >= 0.80:
        return True

    # Criterion 3: queue empty
    if not state["queue"]:
        return True

    return False


# ── CLI test ──────────────────────────────────────────────────

if __name__ == "__main__":
    print("Testing Zotero query...")
    state = _empty_state()
    queue = build_queue(state)
    print(f"  Papers queued: {len(queue)}")
    for tier in [1, 2, 3]:
        tier_count = sum(1 for p in queue if p["tier"] == tier)
        print(f"  Tier {tier}: {tier_count}")
    if queue:
        print(f"\n  First 5:")
        for p in queue[:5]:
            pdf = find_pdf(p["storage_key"])
            exists = "OK" if pdf and pdf.exists() else "MISSING"
            print(f"    [{exists}] T{p['tier']} {p['journal']}: {p['title'][:60]}")
