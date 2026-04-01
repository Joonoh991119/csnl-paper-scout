#!/usr/bin/env python3
"""Unified PDF Rescue Fetcher — all strategies in one script.
=============================================================
Consolidates: rescue_ftp.py, rescue_oa_ftp.py, browser relay, cookies.

Strategy cascade (per paper):
  S0: Skip if already on NAS
  S1: PMC HTTPS mirror (tar.gz) — bypasses ALL Cloudflare
  S2: Cell.com browser relay (requires local HTTP server + Chrome Extension)
  S3: PMC FTP (tar.gz) — fallback if HTTPS mirror fails
  S4: eLife CDN direct
  S5: Frontiers direct /pdf
  S6: Unpaywall OA direct link
  S7: Elsevier ScienceDirect via browser relay (requires cleared rate limit)

Usage:
  python3 rescue_unified.py                      # all failed DOIs
  python3 rescue_unified.py --doi 10.1016/...    # single DOI
  python3 rescue_unified.py --publisher elsevier  # filter by publisher
  python3 rescue_unified.py --strategy pmc_https  # force single strategy
  python3 rescue_unified.py --dry-run             # report what would be fetched
  python3 rescue_unified.py --serve-only          # just start relay server (for browser mode)
  python3 rescue_unified.py --status              # print current failure registry

Requires:
  pip3 install requests --break-system-packages
  NAS mounted at /Volumes/CSNL_new/Memory/Papers/
"""
import json, re, os, sys, hashlib, time, io, shutil, argparse
import tarfile, tempfile, subprocess, socketserver
import urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from collections import Counter
from urllib.parse import quote
from http.server import HTTPServer, BaseHTTPRequestHandler

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_DIR = Path(__file__).resolve().parent
NAS_PDF_DIR = Path("/Volumes/CSNL_new/Memory/Papers/_new_supplement")
CANDIDATES  = _DIR / "candidates"
REGISTRY    = CANDIDATES / "failure_registry.json"
FETCH_LOG   = CANDIDATES / "03_fetch_log.json"
PASS_LIST   = CANDIDATES / "02_resolved_pass.json"
EMAIL       = "joonop99@snu.ac.kr"
RELAY_PORT  = 18765
RELAY_DIR   = Path("/tmp/elsevier_rescue")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LOG_DIR = _DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
_log_file = None

def log(msg):
    global _log_file
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FILENAME
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_filename(paper):
    authors = paper.get('authors', [])
    first = authors[0] if authors else 'Unknown'
    parts = first.strip().split()
    last = re.sub(r'[^\w]', '', parts[-1]) if parts else 'Unknown'
    year = paper.get('year', 'XXXX')
    title = re.sub(r'[^\w\s]', '', paper.get('title', '')[:80]).strip().replace(' ', '_')
    doi_hash = hashlib.md5(paper.get('doi', '').encode()).hexdigest()[:6]
    return f"{last}_{year}_{title}_{doi_hash}.pdf"

def is_valid_pdf(path):
    if not path.exists() or path.stat().st_size < 5000:
        return False
    with open(path, 'rb') as f:
        return f.read(5) == b'%PDF-'

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S1: PMC HTTPS MIRROR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_pmcid(doi):
    """DOI → PMCID via NCBI ID converter."""
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={quote(doi, safe='')}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        records = data.get('records', [])
        if records and records[0].get('pmcid'):
            return records[0]['pmcid']
    except Exception:
        pass
    return None

def get_ftp_url(pmcid):
    """PMCID → FTP tar.gz URL via NCBI OA API."""
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            root = ET.fromstring(resp.read())
        for link in root.iter('link'):
            if link.get('format') == 'tgz':
                return link.get('href')
    except Exception:
        pass
    return None

def extract_main_pdf(tgz_data, out_path):
    """Extract main article PDF (not supplement) from tar.gz bytes."""
    tgz_io = io.BytesIO(tgz_data)
    with tarfile.open(fileobj=tgz_io, mode='r:gz') as tar:
        pdf_members = [m for m in tar.getmembers() if m.name.endswith('.pdf')]
        if not pdf_members:
            return False, "no_pdf_in_tar"
        # Prefer non-supplement PDFs
        main = [m for m in pdf_members if 'supplement' not in m.name.lower()]
        candidates = main if main else pdf_members
        candidates.sort(key=lambda m: m.size, reverse=True)
        best = candidates[0]
        f = tar.extractfile(best)
        data = f.read()
        if data[:5] != b'%PDF-':
            return False, "extracted_not_pdf"
        out_path.write_bytes(data)
        return True, out_path.stat().st_size

def strategy_pmc_https(doi, out_path):
    """S1: PMC HTTPS mirror — most reliable, bypasses Cloudflare."""
    pmcid = get_pmcid(doi)
    if not pmcid:
        return False, "no_pmcid"
    ftp_url = get_ftp_url(pmcid)
    if not ftp_url:
        return False, "no_ftp_url"
    # Convert ftp:// to https:// mirror
    https_url = ftp_url.replace('ftp://ftp.ncbi.nlm.nih.gov/', 'https://ftp.ncbi.nlm.nih.gov/')
    try:
        req = urllib.request.Request(https_url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        resp = urllib.request.urlopen(req, timeout=120)
        data = resp.read()
        if len(data) < 1000:
            return False, "download_too_small"
        return extract_main_pdf(data, out_path)
    except Exception as e:
        return False, f"https_error:{str(e)[:50]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S3: PMC FTP (original)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def strategy_pmc_ftp(doi, out_path):
    """S3: PMC FTP tar.gz — curl-based, fallback if HTTPS fails."""
    pmcid = get_pmcid(doi)
    if not pmcid:
        return False, "no_pmcid"
    ftp_url = get_ftp_url(pmcid)
    if not ftp_url:
        return False, "no_ftp_url"
    with tempfile.TemporaryDirectory() as tmpdir:
        tgz_path = os.path.join(tmpdir, "package.tar.gz")
        try:
            subprocess.run(
                ['curl', '-s', '-o', tgz_path, '--max-time', '120', ftp_url],
                capture_output=True, timeout=130
            )
            if not os.path.exists(tgz_path) or os.path.getsize(tgz_path) < 1000:
                return False, "curl_failed"
            data = Path(tgz_path).read_bytes()
            return extract_main_pdf(data, out_path)
        except Exception as e:
            return False, f"ftp_error:{str(e)[:50]}"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S4: eLife CDN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def strategy_elife_cdn(doi, out_path):
    """S4: eLife direct CDN — predictable URL pattern."""
    match = re.search(r'eLife\.(\d+)', doi)
    if not match:
        return False, "not_elife"
    article_id = match.group(1)
    # Try multiple version suffixes
    for version in ['v3', 'v2', 'v1']:
        pdf_url = f"https://cdn.elifesciences.org/articles/{article_id}/eLife-{article_id}-{version}.pdf"
        try:
            req = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=30)
            data = resp.read()
            if data[:5] == b'%PDF-' and len(data) > 10000:
                out_path.write_bytes(data)
                return True, out_path.stat().st_size
        except Exception:
            continue
    return False, "elife_all_versions_failed"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S5: Frontiers direct /pdf
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def strategy_frontiers(doi, out_path):
    """S5: Frontiers direct — append /pdf to resolved DOI URL."""
    if not doi.startswith('10.3389/'):
        return False, "not_frontiers"
    try:
        req = urllib.request.Request(f"https://doi.org/{doi}", headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        final_url = resp.geturl().rstrip('/') + '/pdf'
        req2 = urllib.request.Request(final_url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Accept': 'application/pdf,*/*'
        })
        resp2 = urllib.request.urlopen(req2, timeout=60)
        data = resp2.read()
        if data[:5] == b'%PDF-' and len(data) > 10000:
            out_path.write_bytes(data)
            return True, out_path.stat().st_size
    except Exception as e:
        return False, f"frontiers_error:{str(e)[:50]}"
    return False, "frontiers_not_pdf"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S6: Unpaywall OA link
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def strategy_unpaywall(doi, out_path):
    """S6: Unpaywall — get best OA PDF URL."""
    try:
        url = f"https://api.unpaywall.org/v2/{quote(doi, safe='')}?email={EMAIL}"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        oa = data.get('best_oa_location', {})
        if not oa:
            return False, "no_oa_location"
        pdf_url = oa.get('url_for_pdf')
        if not pdf_url:
            return False, "no_pdf_url_in_oa"
        # Skip publisher URLs (they'll be Cloudflare-blocked)
        if any(d in pdf_url for d in ['sciencedirect.com', 'cell.com', 'elsevier.com']):
            return False, "oa_url_is_publisher"
        req2 = urllib.request.Request(pdf_url, headers={'User-Agent': 'Mozilla/5.0'})
        resp2 = urllib.request.urlopen(req2, timeout=60)
        data = resp2.read()
        if data[:5] == b'%PDF-' and len(data) > 10000:
            out_path.write_bytes(data)
            return True, out_path.stat().st_size
    except Exception as e:
        return False, f"unpaywall_error:{str(e)[:50]}"
    return False, "unpaywall_not_pdf"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  S2/S7: BROWSER RELAY SERVER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
class RelayHandler(BaseHTTPRequestHandler):
    """Receives PDF data POSTed from Chrome Extension JS."""
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        fname = self.headers.get('X-Filename', 'unknown.pdf')
        RELAY_DIR.mkdir(exist_ok=True)
        path = RELAY_DIR / fname
        path.write_bytes(body)
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(f"saved {len(body)} bytes to {path}".encode())
        log(f"  [relay] Saved {fname}: {len(body)} bytes")

    def do_OPTIONS(self):
        self.send_response(200)
        for h, v in [('Access-Control-Allow-Origin', '*'),
                     ('Access-Control-Allow-Methods', 'POST, OPTIONS'),
                     ('Access-Control-Allow-Headers', 'Content-Type, X-Filename')]:
            self.send_header(h, v)
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging

class ReuseTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def start_relay_server():
    """Start local HTTP server for browser→disk PDF relay."""
    try:
        server = ReuseTCPServer(('127.0.0.1', RELAY_PORT), RelayHandler)
        log(f"Relay server on http://127.0.0.1:{RELAY_PORT}")
        return server
    except OSError as e:
        if 'Address already in use' in str(e):
            log(f"Relay server already running on port {RELAY_PORT}")
            return None
        raise

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BROWSER RELAY JS TEMPLATES (for Claude / Chrome Extension)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_browser_relay_js(filename):
    """JS snippet for Chrome Extension to POST current page PDF to relay."""
    return f"""(async () => {{
    try {{
        const resp = await fetch(window.location.href);
        const blob = await resp.blob();
        const arrayBuf = await blob.arrayBuffer();
        const postResp = await fetch('http://127.0.0.1:{RELAY_PORT}', {{
            method: 'POST',
            headers: {{ 'X-Filename': '{filename}', 'Content-Type': 'application/pdf' }},
            body: arrayBuf
        }});
        return 'OK: ' + await postResp.text();
    }} catch(e) {{ return 'ERROR: ' + e.message; }}
}})()"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  FAILURE REGISTRY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_registry():
    if REGISTRY.exists():
        return json.load(open(REGISTRY))
    return {}

def save_registry(reg):
    with open(REGISTRY, 'w') as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)

def update_registry_entry(reg, doi, status, strategy, detail=""):
    if doi not in reg:
        reg[doi] = {
            'doi': doi,
            'attempts': [],
            'status': status,
            'last_attempt': datetime.now().isoformat(),
        }
    reg[doi]['status'] = status
    reg[doi]['last_attempt'] = datetime.now().isoformat()
    reg[doi]['attempts'].append({
        'time': datetime.now().isoformat(),
        'strategy': strategy,
        'result': status,
        'detail': detail,
    })

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STRATEGY CASCADE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def classify_publisher(doi):
    """Classify DOI into publisher category."""
    prefix_map = {
        '10.1016/': 'elsevier',   # Elsevier (ScienceDirect, Cell Press)
        '10.7554/': 'elife',
        '10.3389/': 'frontiers',
        '10.1073/': 'pnas',
        '10.1167/': 'jov',
        '10.1038/': 'nature',
        '10.1037/': 'apa',
        '10.1177/': 'sage',
        '10.1080/': 'taylor_francis',
        '10.1371/': 'plos',
        '10.1523/': 'jneurosci',
    }
    for prefix, pub in prefix_map.items():
        if doi.startswith(prefix):
            return pub
    return 'other'

def is_cell_press(doi):
    """Check if Elsevier DOI is from Cell Press (cell.com)."""
    cell_journals = ['celrep', 'cub', 'neuron', 'cell.', 'cels', 'isci']
    return any(j in doi for j in cell_journals)

def get_cell_pdf_url(doi):
    """Convert Cell Press DOI to cell.com PDF URL."""
    # DOI: 10.1016/j.{journal}.{year}.{id} → PII
    # PII: S{issn_prefix}{id_suffix}
    pii_map = {
        'celrep': 'S2211-1247',
        'cub': 'S0960-9822',
        'neuron': 'S0896-6273',
        'isci': 'S2589-0042',
    }
    journal_url_map = {
        'celrep': 'cell-reports',
        'cub': 'current-biology',
        'neuron': 'neuron',
        'isci': 'iscience',
    }
    for journal_key in pii_map:
        if f'.{journal_key}.' in doi:
            # Need PII from external source — this function just provides the pattern
            return journal_key, journal_url_map.get(journal_key, journal_key)
    return None, None

def get_strategy_cascade(doi):
    """Return ordered list of strategies to try for a given DOI."""
    pub = classify_publisher(doi)
    strategies = []

    # Universal: try PMC first (works for any publisher)
    strategies.append(('pmc_https', strategy_pmc_https))

    if pub == 'elife':
        strategies.append(('elife_cdn', strategy_elife_cdn))
    elif pub == 'frontiers':
        strategies.append(('frontiers', strategy_frontiers))

    # Unpaywall for non-publisher OA sources
    strategies.append(('unpaywall', strategy_unpaywall))

    # PMC FTP as last automated resort
    strategies.append(('pmc_ftp', strategy_pmc_ftp))

    # Cell Press browser relay is manual (needs Chrome Extension)
    # Elsevier ScienceDirect browser relay is manual (needs cleared rate limit)
    # These are flagged in registry as 'needs_browser'

    return strategies

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN RUNNER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def collect_failures():
    """Gather all DOIs that still need PDFs."""
    pass_list = json.load(open(PASS_LIST))
    doi_info = {p['doi']: p for p in pass_list}
    fetch_log = json.load(open(FETCH_LOG))
    success_dois = set(e['doi'] for e in fetch_log if e.get('status') in ('success', 'exists'))

    # Also check NAS directly
    nas_pdfs = set(f.name for f in NAS_PDF_DIR.glob('*.pdf'))
    for doi, paper in doi_info.items():
        fname = make_filename(paper)
        if fname in nas_pdfs:
            success_dois.add(doi)

    failed = []
    for doi, paper in doi_info.items():
        if doi not in success_dois:
            failed.append(paper)

    return failed, doi_info

def run_automated(targets, doi_info, dry_run=False, strategy_filter=None):
    """Run automated strategies on target papers."""
    registry = load_registry()
    success, failed, skipped = 0, 0, 0
    fetch_log = json.load(open(FETCH_LOG))
    fetch_set = set(e['doi'] for e in fetch_log if e.get('status') in ('success', 'exists'))

    for i, paper in enumerate(targets):
        doi = paper['doi']
        fname = make_filename(paper)
        out_path = NAS_PDF_DIR / fname

        # S0: already exists
        if is_valid_pdf(out_path):
            skipped += 1
            continue

        pub = classify_publisher(doi)
        cascade = get_strategy_cascade(doi)
        if strategy_filter:
            cascade = [(n, f) for n, f in cascade if n == strategy_filter]

        log(f"[{i+1}/{len(targets)}] {doi[:55]} ({pub})")

        if dry_run:
            strats = ', '.join(n for n, _ in cascade)
            log(f"  would try: {strats}")
            continue

        ok = False
        for strat_name, strat_fn in cascade:
            try:
                ok, info = strat_fn(doi, out_path)
            except Exception as e:
                ok, info = False, f"exception:{str(e)[:50]}"

            if ok:
                log(f"  ✓ [{strat_name}] {info/1e6:.1f} MB → {fname[:50]}")
                update_registry_entry(registry, doi, 'success', strat_name)
                fetch_log.append({
                    'doi': doi, 'status': 'success',
                    'path': str(out_path), 'source': strat_name
                })
                success += 1
                break
            else:
                log(f"  ✗ [{strat_name}] {info}")
                update_registry_entry(registry, doi, 'failed', strat_name, str(info))

        if not ok:
            # Mark for browser rescue if Elsevier/Cell
            if pub == 'elsevier' and is_cell_press(doi):
                update_registry_entry(registry, doi, 'needs_browser_cell', 'auto', 'Cell Press — use browser relay')
            elif pub == 'elsevier':
                update_registry_entry(registry, doi, 'needs_browser_elsevier', 'auto', 'ScienceDirect — IP rate-limited')
            else:
                update_registry_entry(registry, doi, 'exhausted', 'auto', 'all automated strategies failed')
            failed += 1

        time.sleep(0.5)

        # Checkpoint every 20
        if (i + 1) % 20 == 0:
            save_registry(registry)
            with open(FETCH_LOG, 'w') as f:
                json.dump(fetch_log, f, indent=2, ensure_ascii=False)

    # Final save
    save_registry(registry)
    with open(FETCH_LOG, 'w') as f:
        json.dump(fetch_log, f, indent=2, ensure_ascii=False)

    log(f"\n{'='*50}")
    log(f"Result: {success} success, {failed} failed, {skipped} skipped")
    return success, failed

def print_status():
    """Print current failure registry summary."""
    failed, doi_info = collect_failures()
    registry = load_registry()

    pub_counts = Counter()
    status_counts = Counter()
    for paper in failed:
        doi = paper['doi']
        pub = classify_publisher(doi)
        pub_counts[pub] += 1
        if doi in registry:
            status_counts[registry[doi]['status']] += 1
        else:
            status_counts['not_attempted'] += 1

    print(f"\n{'='*60}")
    print(f"FAILURE REGISTRY — {len(failed)} papers remaining")
    print(f"{'='*60}")
    print(f"\nBy publisher:")
    for pub, cnt in pub_counts.most_common():
        print(f"  {pub:20s} {cnt:4d}")
    print(f"\nBy status:")
    for st, cnt in status_counts.most_common():
        print(f"  {st:30s} {cnt:4d}")

    # List browser-rescue candidates
    browser_cell = [d for d, r in registry.items() if r.get('status') == 'needs_browser_cell']
    browser_els = [d for d, r in registry.items() if r.get('status') == 'needs_browser_elsevier']
    if browser_cell:
        print(f"\nCell Press (browser relay): {len(browser_cell)}")
        for d in browser_cell[:5]:
            print(f"  {d}")
    if browser_els:
        print(f"\nScienceDirect (IP blocked): {len(browser_els)}")
        for d in browser_els[:5]:
            print(f"  {d}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CLI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main():
    global _log_file
    parser = argparse.ArgumentParser(description='Unified PDF Rescue Fetcher')
    parser.add_argument('--doi', help='Rescue single DOI')
    parser.add_argument('--publisher', help='Filter by publisher (elsevier, elife, etc.)')
    parser.add_argument('--strategy', help='Force single strategy (pmc_https, elife_cdn, etc.)')
    parser.add_argument('--dry-run', action='store_true', help='Report only, no downloads')
    parser.add_argument('--serve-only', action='store_true', help='Start relay server and wait')
    parser.add_argument('--status', action='store_true', help='Print failure registry')
    parser.add_argument('--max', type=int, default=0, help='Max papers to process (0=all)')
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if args.serve_only:
        server = start_relay_server()
        if server:
            log("Relay server running. Use Chrome Extension JS to POST PDFs.")
            log(f"POST http://127.0.0.1:{RELAY_PORT} with X-Filename header")
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                log("Server stopped.")
        return

    # Set up logging
    log_name = f"rescue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    _log_file = open(LOG_DIR / log_name, 'w')

    NAS_PDF_DIR.mkdir(exist_ok=True)
    failed, doi_info = collect_failures()

    log(f"Total failures: {len(failed)}")

    # Filter
    targets = failed
    if args.doi:
        targets = [p for p in failed if p['doi'] == args.doi]
    elif args.publisher:
        targets = [p for p in failed if classify_publisher(p['doi']) == args.publisher]

    if args.max > 0:
        targets = targets[:args.max]

    log(f"Targets: {len(targets)}")

    if targets:
        run_automated(targets, doi_info, args.dry_run, args.strategy)

    _log_file.close()

if __name__ == '__main__':
    main()
