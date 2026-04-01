#!/usr/bin/env python3
"""Phase 4: Incremental Embedder
=================================
Scans _new_supplement/ for PDFs not yet in the NAS embeddings.npz,
extracts first-page text, embeds via OpenRouter nemotron, and merges
into the existing npz/index/doi-list.

Can be run repeatedly as new PDFs arrive from the fetcher.

Usage:
  python3 embedder.py              # embed all new PDFs
  python3 embedder.py --dry-run    # just report what would be embedded
  python3 embedder.py --batch 50   # custom batch size
"""
import os, sys, json, time, math, re, shutil, hashlib
import requests
import numpy as np
from pathlib import Path
from datetime import datetime

# ━━ Config ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_SCRIPT_DIR  = Path(__file__).resolve().parent
NAS_PAPERS   = Path("/Volumes/CSNL_new/Memory/Papers")
NAS_EMBED    = NAS_PAPERS / "embedding_nemotron"
NAS_DOI_FILE = NAS_PAPERS / "papers_doi_list.json"
NEW_PDF_DIR  = NAS_PAPERS / "_new_supplement"
CANDIDATES   = Path(os.environ.get('CANDIDATES_DIR', _SCRIPT_DIR / "candidates"))
CREDS_FILE   = Path(os.environ.get('CREDS_FILE', _SCRIPT_DIR.parent / "source" / "credentials.json"))

EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_DIM   = 2048
BATCH_SIZE  = 20
DELAY       = 1.5    # seconds between API batches
MAX_CHARS   = 1500   # max chars from first page

LOG_DIR = Path("/Users/joonoh/paper-scout-hub/supplement/logs")
LOG_DIR.mkdir(exist_ok=True)

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)

def get_api_key():
    if CREDS_FILE.exists():
        with open(CREDS_FILE) as f:
            creds = json.load(f)
        return creds.get('openrouter_api_key', '')
    return os.environ.get('OPENROUTER_API_KEY', '')

# ━━ Text extraction ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def extract_text(pdf_path, max_chars=MAX_CHARS):
    """Extract text from first page of PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        if not reader.pages:
            return ""
        text = ""
        for page in reader.pages[:2]:  # first 2 pages for better coverage
            t = page.extract_text() or ""
            text += t + " "
            if len(text) >= max_chars:
                break
        return text[:max_chars].strip()
    except Exception as e:
        return ""

# ━━ Embedding API ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def embed_batch_api(texts, api_key, max_retries=3):
    """Embed a batch of texts via OpenRouter."""
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={"model": EMBED_MODEL, "input": texts},
                timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                return [item['embedding'] for item in data['data']]
            elif resp.status_code == 429:
                wait = 5 * (2 ** attempt)
                log(f"    429 rate limit, waiting {wait}s")
                time.sleep(wait)
                continue
            else:
                log(f"    API error {resp.status_code}: {resp.text[:150]}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    continue
                return None
        except Exception as e:
            log(f"    Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
    return None

# ━━ DOI lookup from fetch log ━━━━━━━━━━━━━━━━━━━━━━━━━
def build_doi_map():
    """Map filenames to DOIs from fetch log + resolved data."""
    doi_map = {}
    # From fetch log
    log_path = CANDIDATES / "03_fetch_log.json"
    if log_path.exists():
        with open(log_path) as f:
            for entry in json.load(f):
                if entry.get('path'):
                    fname = Path(entry['path']).name
                    if entry.get('doi'):
                        doi_map[fname] = entry['doi']
    # From resolved (fallback via filename matching)
    res_path = CANDIDATES / "02_resolved.json"
    if res_path.exists():
        with open(res_path) as f:
            resolved = json.load(f)
        for p in resolved:
            # Build expected filename (both old and new format with hash)
            authors = p.get('authors', [])
            first = authors[0] if authors else 'Unknown'
            parts = first.strip().split()
            last = re.sub(r'[^\w]', '', parts[-1]) if parts else 'Unknown'
            year = p.get('year', 'XXXX')
            title = re.sub(r'[<>:"/\\|?*\n\r]', '', p.get('title', 'untitled'))
            title = title.replace(' ', '_')[:80]
            doi = p.get('doi', '')
            # Old format (no hash)
            fname_old = f"{last}_{year}_{title}.pdf"
            if fname_old not in doi_map and doi:
                doi_map[fname_old] = doi
            # New format (with DOI hash)
            doi_hash = hashlib.md5(doi.encode()).hexdigest()[:6]
            fname_new = f"{last}_{year}_{title}_{doi_hash}.pdf"
            if fname_new not in doi_map and doi:
                doi_map[fname_new] = doi
    return doi_map

# ━━ Main ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--batch', type=int, default=BATCH_SIZE)
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key and not args.dry_run:
        log("ERROR: No OpenRouter API key found")
        sys.exit(1)

    log("═══ Phase 4: INCREMENTAL EMBEDDER ═══")

    # Load existing embeddings
    npz_path = NAS_EMBED / "embeddings.npz"
    idx_path = NAS_EMBED / "index.json"

    if npz_path.exists():
        npz = np.load(str(npz_path), allow_pickle=False)
        existing_keys = set(npz.keys())
        log(f"Existing embeddings: {len(existing_keys)}")
    else:
        existing_keys = set()
        log("No existing embeddings found — starting fresh")

    if idx_path.exists():
        with open(idx_path) as f:
            index = json.load(f)
    else:
        index = {}

    # Scan new PDFs
    if not NEW_PDF_DIR.exists():
        log(f"ERROR: PDF dir not found: {NEW_PDF_DIR}")
        sys.exit(1)

    all_pdfs = sorted(NEW_PDF_DIR.glob("*.pdf"))
    new_pdfs = [p for p in all_pdfs if p.name not in existing_keys and p.stat().st_size > 10000]
    log(f"PDFs on disk: {len(all_pdfs)}, new to embed: {len(new_pdfs)}")

    if not new_pdfs:
        log("Nothing to embed — all PDFs already in database.")
        return

    if args.dry_run:
        log(f"DRY RUN — would embed {len(new_pdfs)} PDFs")
        for p in new_pdfs[:20]:
            log(f"  {p.name}")
        if len(new_pdfs) > 20:
            log(f"  ... and {len(new_pdfs) - 20} more")
        return

    # Build DOI lookup
    doi_map = build_doi_map()
    log(f"DOI map: {len(doi_map)} entries")

    # Extract text from new PDFs
    log("Extracting text from PDFs...")
    texts = []
    valid_pdfs = []
    skip_count = 0
    for i, pdf in enumerate(new_pdfs):
        text = extract_text(pdf)
        if len(text) > 50:
            texts.append(text)
            valid_pdfs.append(pdf)
        else:
            skip_count += 1
        if (i + 1) % 100 == 0:
            log(f"  Extracted {i+1}/{len(new_pdfs)} ({len(valid_pdfs)} valid, {skip_count} skipped)")

    log(f"Valid texts: {len(texts)}, skipped (no text): {skip_count}")

    if not texts:
        log("No valid texts to embed.")
        return

    # Backup before modifying
    backup_npz = NAS_EMBED / "embeddings_pre_supplement.npz"
    backup_idx = NAS_EMBED / "index_pre_supplement.json"
    if not backup_npz.exists():
        log("Creating backups...")
        shutil.copy(npz_path, backup_npz)
        shutil.copy(idx_path, backup_idx)
        log("Backups: embeddings_pre_supplement.npz, index_pre_supplement.json")

    # Load DOI list
    if NAS_DOI_FILE.exists():
        with open(NAS_DOI_FILE) as f:
            doi_list = json.load(f)
    else:
        doi_list = {}

    # Embed in batches
    total_batches = math.ceil(len(texts) / args.batch)
    embedded_count = 0
    failed_count = 0
    new_embeddings = {}  # fname -> np.array

    for batch_i in range(0, len(texts), args.batch):
        batch_texts = texts[batch_i:batch_i + args.batch]
        batch_pdfs = valid_pdfs[batch_i:batch_i + args.batch]
        batch_num = batch_i // args.batch + 1

        log(f"  Batch {batch_num}/{total_batches} ({len(batch_texts)} texts)")

        embs = embed_batch_api(batch_texts, api_key)

        if embs and len(embs) == len(batch_texts):
            for pdf, emb in zip(batch_pdfs, embs):
                vec = np.array(emb, dtype=np.float16)
                new_embeddings[pdf.name] = vec
                embedded_count += 1
        else:
            # Try one-by-one fallback
            log(f"    Batch failed, trying individual...")
            for pdf, text in zip(batch_pdfs, batch_texts):
                single = embed_batch_api([text], api_key)
                if single and len(single) == 1:
                    vec = np.array(single[0], dtype=np.float16)
                    new_embeddings[pdf.name] = vec
                    embedded_count += 1
                else:
                    failed_count += 1
                    log(f"    FAIL: {pdf.name}")
                time.sleep(0.5)

        time.sleep(DELAY)

        # Checkpoint every 10 batches (save incrementally)
        if batch_num % 10 == 0 and new_embeddings:
            log(f"  Checkpoint: saving {len(new_embeddings)} new embeddings...")
            _save_all(npz_path, idx_path, existing_keys, index, new_embeddings,
                      doi_map, doi_list, NAS_DOI_FILE)
            log(f"  Checkpoint saved.")

    # Final save
    if new_embeddings:
        _save_all(npz_path, idx_path, existing_keys, index, new_embeddings,
                  doi_map, doi_list, NAS_DOI_FILE)

    log(f"\n═══ Embedder Results ═══")
    log(f"New embedded: {embedded_count}")
    log(f"Failed: {failed_count}")
    log(f"Total in DB: {len(existing_keys) + embedded_count}")

    # Save embed log
    embed_log = {
        'timestamp': datetime.now().isoformat(),
        'new_embedded': embedded_count,
        'failed': failed_count,
        'total': len(existing_keys) + embedded_count,
        'skipped_no_text': skip_count,
    }
    with open(CANDIDATES / "04_embed_log.json", 'w') as f:
        json.dump(embed_log, f, indent=2)
    log("Done.")


def _save_all(npz_path, idx_path, existing_keys, index, new_embeddings,
              doi_map, doi_list, doi_file):
    """Save embeddings, index, and DOI list to NAS."""
    # Load current npz (might have been updated by a previous checkpoint)
    if npz_path.exists():
        _npz = np.load(str(npz_path), allow_pickle=False)
        current = {k: _npz[k] for k in _npz.files}
        _npz.close()
    else:
        current = {}

    # Add new embeddings
    for fname, vec in new_embeddings.items():
        current[fname] = vec

    # Save npz
    np.savez_compressed(str(npz_path), **current)

    # Update index
    next_idx = max((v.get('idx', 0) for v in index.values()), default=-1) + 1
    for fname in new_embeddings:
        if fname not in index:
            parts = fname.replace('.pdf', '').split('_', 2)
            index[fname] = {
                'idx': next_idx,
                'author': parts[0] if len(parts) > 0 else '',
                'year': parts[1] if len(parts) > 1 else '',
                'title': (parts[2].replace('_', ' ') if len(parts) > 2 else ''),
                'doi': doi_map.get(fname, ''),
                'source': 'supplement_pipeline'
            }
            next_idx += 1

    with open(idx_path, 'w') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)

    # Update DOI list
    for fname in new_embeddings:
        doi = doi_map.get(fname, '')
        if doi and fname not in doi_list:
            fparts = fname.replace('.pdf', '').split('_', 2)
            doi_list[fname] = {
                'doi': doi,
                'all_dois': [doi],
                'author': fparts[0].lower() if fparts else '',
                'year': fparts[1] if len(fparts) > 1 else '',
            }
    with open(doi_file, 'w') as f:
        json.dump(doi_list, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    main()
