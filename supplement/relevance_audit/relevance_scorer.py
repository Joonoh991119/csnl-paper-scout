#!/usr/bin/env python3
"""Relevance Scorer v2 — 6-signal composite scoring engine.
All rule-based, no LLM calls. Fast batch processing.

Usage:
  python3 relevance_scorer.py                    # score all papers
  python3 relevance_scorer.py --include-trash    # also score trashbin (for calibration)
"""
import json, os, re, hashlib, argparse, time
import numpy as np
from pathlib import Path
from datetime import datetime
from collections import Counter

from signal_configs import (
    s1_score, s2_score, s3_score, s4_score, s5_score, s6_score,
    assign_tier, KNOWN_HOMONYMS, PROJECT_GISTS, KEYWORDS_TIER1,
)

# ── Paths ──
SCRIPT_DIR = Path(__file__).resolve().parent
SUPPLEMENT_DIR = SCRIPT_DIR.parent
NAS_PDF_DIR = Path("/Volumes/CSNL_new/Memory/Papers/_new_supplement")
TRASH_DIR = NAS_PDF_DIR / "_trashbin"
NPZ_PATH = Path("/Volumes/CSNL_new/Memory/Papers/embedding_nemotron/embeddings.npz")
PI_NETWORK = SUPPLEMENT_DIR.parent / "data" / "pi_network_data.json"
CONTEXT_BUNDLE = Path("/Users/joonoh/csnl-paper-scout/data/context-bundle.json")
CREDS_FILE = SUPPLEMENT_DIR.parent / "source" / "credentials.json"

RESULTS_DIR = SCRIPT_DIR / "results" / "v2"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Embedding config
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"

# Reuse existing CSNL anchors
from relevance_audit import CSNL_ANCHORS


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_api_key():
    if CREDS_FILE.exists():
        return json.load(open(CREDS_FILE)).get('openrouter_api_key', '')
    return os.environ.get('OPENROUTER_API_KEY', '')


# ═══════════════════════════════════════════════════
#  DATA LOADING
# ═══════════════════════════════════════════════════

def load_embeddings():
    data = np.load(NPZ_PATH, allow_pickle=True)
    return {k: data[k].astype(np.float32) for k in data.files}


def load_pi_data():
    with open(PI_NETWORK) as f:
        data = json.load(f)
    pi_lastnames = set()
    pi_full = {}
    for n in data.get('nodes', []):
        name = n.get('full_name') or n.get('id', '')
        parts = name.strip().split()
        if parts:
            ln = parts[-1].lower()
            pi_lastnames.add(ln)
            pi_full[ln] = {
                'full_name': name,
                'categories': n.get('categories', []),
                'affiliation': n.get('affiliation', ''),
            }
    return pi_lastnames, pi_full


def load_relevance_db():
    """Load tracked author counts from relevance DB."""
    author_counts = Counter()
    for fname in ['csnl_new_relevance.json', 'csnl_new_high_value.json']:
        path = Path(f"/Users/joonoh/csnl-paper-scout/sync/{fname}")
        if path.exists():
            with open(path) as f:
                entries = json.load(f)
            for e in entries:
                auth = (e.get('author') or '').split()
                if auth:
                    author_counts[auth[-1].lower()] += 1
    return author_counts


def extract_abstract(pdf_path, max_chars=2000):
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for page in reader.pages[:3]:
            t = page.extract_text() or ""
            text += t + " "
            if len(text) > max_chars:
                break
        return text[:max_chars].strip()
    except:
        return ""


def parse_title_from_filename(filename):
    stem = filename.replace('.pdf', '')
    parts = stem.split('_', 2)
    if len(parts) >= 3:
        author = parts[0]
        year = parts[1]
        title = parts[2].replace('_', ' ')
        title = re.sub(r'\s+[a-f0-9]{6}$', '', title)
        return author, year, title
    return stem, '', ''


def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0: return 0.0
    return float(np.dot(a, b) / (na * nb))


# ═══════════════════════════════════════════════════
#  EMBEDDING UTILITIES
# ═══════════════════════════════════════════════════

def embed_texts(texts, api_key):
    import requests
    resp = requests.post(EMBED_ENDPOINT, headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }, json={'model': EMBED_MODEL, 'input': texts}, timeout=60)
    resp.raise_for_status()
    return [np.array(d['embedding'], dtype=np.float32) for d in resp.json()['data']]


def load_or_compute_anchor_embeddings(api_key):
    cache = RESULTS_DIR / "anchor_embeddings_v2.json"
    if cache.exists():
        with open(cache) as f:
            return [np.array(v, dtype=np.float32) for v in json.load(f)]
    vecs = []
    for i in range(0, len(CSNL_ANCHORS), 20):
        vecs.extend(embed_texts(CSNL_ANCHORS[i:i+20], api_key))
        time.sleep(1.5)
    with open(cache, 'w') as f:
        json.dump([v.tolist() for v in vecs], f)
    return vecs


def load_or_compute_project_embeddings(api_key):
    cache = RESULTS_DIR / "project_embeddings_v2.json"
    if cache.exists():
        with open(cache) as f:
            data = json.load(f)
        return {k: np.array(v, dtype=np.float32) for k, v in data.items()}
    texts = list(PROJECT_GISTS.values())
    keys = list(PROJECT_GISTS.keys())
    vecs = embed_texts(texts, api_key)
    result = dict(zip(keys, vecs))
    with open(cache, 'w') as f:
        json.dump({k: v.tolist() for k, v in result.items()}, f)
    return result


def extract_journal_from_abstract(abstract):
    """Try to extract journal name from abstract text (usually in first line)."""
    text = abstract[:500].lower()
    # Common patterns
    for journal in ['nature neuroscience', 'nature human behaviour', 'nature communications',
                    'nature methods', 'nature', 'science advances', 'science',
                    'neuron', 'current biology', 'cell', 'elife', 'pnas',
                    'journal of neuroscience', 'cerebral cortex', 'neuroimage',
                    'journal of vision', 'cognition', 'plos computational biology',
                    'neural computation', 'psychological review', 'psychological science',
                    'biorxiv', 'arxiv', 'psyarxiv']:
        if journal in text:
            return journal
    return ''


# ═══════════════════════════════════════════════════
#  MAIN SCORER
# ═══════════════════════════════════════════════════

def score_paper(filename, embedding, abstract, anchor_vecs, project_vecs,
                pi_lastnames, pi_full, author_db, journal_override=''):
    """Compute 6 signals and composite for one paper."""
    author, year, title = parse_title_from_filename(filename)
    author_lower = author.lower()
    abstract_lower = abstract.lower()

    # S1: Embedding similarity
    if embedding is not None:
        max_anchor_sim = max(cosine_sim(embedding, a) for a in anchor_vecs)
    else:
        max_anchor_sim = 0.0
    sig1 = s1_score(max_anchor_sim)

    # S2: PI authorship
    sig2, needs_homonym = s2_score(author_lower, pi_lastnames, max_anchor_sim)

    # S3: Keyword match
    sig3 = s3_score(abstract_lower)

    # S4: Project match
    if embedding is not None:
        best_proj_sim = max(cosine_sim(embedding, pv) for pv in project_vecs.values())
        best_proj_name = max(project_vecs.keys(), key=lambda k: cosine_sim(embedding, project_vecs[k]))
    else:
        best_proj_sim = 0.0
        best_proj_name = ''
    sig4 = s4_score(best_proj_sim)

    # S5: Reading DB author (discounted for common names)
    sig5 = s5_score(author_db.get(author_lower, 0), author_lower, max_anchor_sim)

    # S6: Journal
    journal = journal_override or extract_journal_from_abstract(abstract)
    sig6 = s6_score(journal)

    # If no embedding exists (paper removed from NPZ), discount name-based signals
    # because we can't verify the author/journal is the right person/paper
    has_embedding = embedding is not None and max_anchor_sim > 0
    if not has_embedding:
        sig2 = min(sig2, 5)   # PI credit capped without embedding confirmation
        sig5 = min(sig5, 2)   # Read DB credit capped
        sig6 = min(sig6, 3)   # Journal credit capped (generic journal names match too easily)

    composite = sig1 + sig2 + sig3 + sig4 + sig5 + sig6
    tier = assign_tier(composite)

    return {
        'filename': filename,
        'author': author,
        'year': year,
        'title': title,
        'signals': {
            's1_embedding': sig1,
            's2_pi_author': sig2,
            's3_keywords': sig3,
            's4_project': sig4,
            's5_read_db': sig5,
            's6_journal': sig6,
        },
        'details': {
            'max_anchor_sim': round(max_anchor_sim, 4),
            'best_project': best_proj_name,
            'best_project_sim': round(best_proj_sim, 4),
            'pi_match': author_lower in pi_lastnames,
            'needs_homonym_check': needs_homonym,
            'journal_detected': journal,
        },
        'composite': composite,
        'tier': tier,
    }


# ═══════════════════════════════════════════════════
#  BATCH RUNNER
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-trash', action='store_true', help='Also score trashbin papers')
    args = parser.parse_args()

    api_key = get_api_key()

    # Load data
    log("Loading data...")
    embeddings = load_embeddings()
    pi_lastnames, pi_full = load_pi_data()
    author_db = load_relevance_db()
    anchor_vecs = load_or_compute_anchor_embeddings(api_key)
    project_vecs = load_or_compute_project_embeddings(api_key)

    log(f"Loaded: {len(embeddings)} embeddings, {len(pi_lastnames)} PIs, "
        f"{len(anchor_vecs)} anchors, {len(project_vecs)} project gists")

    # Collect papers to score
    pdf_dirs = [NAS_PDF_DIR]
    if args.include_trash and TRASH_DIR.exists():
        pdf_dirs.append(TRASH_DIR)

    papers = []
    for d in pdf_dirs:
        for f in d.iterdir():
            if f.is_file() and f.name.endswith('.pdf'):
                papers.append((f.name, d == TRASH_DIR))
    log(f"Papers to score: {len(papers)} ({sum(1 for _,t in papers if t)} from trashbin)")

    # Extract abstracts (batch)
    log("Extracting abstracts...")
    abstracts = {}
    for fname, is_trash in papers:
        d = TRASH_DIR if is_trash else NAS_PDF_DIR
        abstracts[fname] = extract_abstract(d / fname)

    # Score all papers
    log("Scoring...")
    results = []
    for i, (fname, is_trash) in enumerate(papers):
        emb = embeddings.get(fname)
        abstract = abstracts.get(fname, '')
        result = score_paper(
            fname, emb, abstract, anchor_vecs, project_vecs,
            pi_lastnames, pi_full, author_db)
        result['is_trashbin'] = is_trash
        results.append(result)

    # Save results
    out_path = RESULTS_DIR / "relevance_scores_v2.json"
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Summary stats
    active = [r for r in results if not r['is_trashbin']]
    trash = [r for r in results if r['is_trashbin']]

    tier_counts = Counter(r['tier'] for r in active)
    trash_tier_counts = Counter(r['tier'] for r in trash)

    log(f"\n{'='*60}")
    log(f"SCORING COMPLETE — {len(results)} papers")
    log(f"{'='*60}")

    log(f"\nActive papers ({len(active)}):")
    for tier in ['auto_keep', 'likely_keep', 'review', 'likely_trash', 'auto_trash']:
        cnt = tier_counts.get(tier, 0)
        pct = cnt / len(active) * 100 if active else 0
        log(f"  {tier:15s}: {cnt:4d} ({pct:5.1f}%)")

    active_scores = [r['composite'] for r in active]
    log(f"  Mean score: {np.mean(active_scores):.1f}")
    log(f"  Median: {np.median(active_scores):.1f}")

    if trash:
        log(f"\nTrashbin papers ({len(trash)}):")
        for tier in ['auto_keep', 'likely_keep', 'review', 'likely_trash', 'auto_trash']:
            cnt = trash_tier_counts.get(tier, 0)
            pct = cnt / len(trash) * 100 if trash else 0
            log(f"  {tier:15s}: {cnt:4d} ({pct:5.1f}%)")
        trash_scores = [r['composite'] for r in trash]
        log(f"  Mean score: {np.mean(trash_scores):.1f}")
        log(f"  Median: {np.median(trash_scores):.1f}")

    # Papers needing homonym check
    homonyms = [r for r in active if r['details']['needs_homonym_check']]
    if homonyms:
        log(f"\nPI homonym checks needed: {len(homonyms)}")
        for r in homonyms:
            log(f"  {r['author']} ({r['year']}): {r['title'][:50]} [score={r['composite']}]")

    log(f"\nResults saved to {out_path}")


if __name__ == '__main__':
    main()
