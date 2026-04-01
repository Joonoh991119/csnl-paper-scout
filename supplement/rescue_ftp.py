#!/usr/bin/env python3
"""Rescue Elsevier papers via NCBI FTP (bypasses Cloudflare).
For PMC papers: OA API → FTP tar.gz → extract PDF.
For non-PMC OA papers: tries ScienceDirect with browser cookies.
"""
import json, re, os, hashlib, time, subprocess, tarfile, tempfile
import urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

NAS_PDF_DIR = Path("/Volumes/CSNL_new/Memory/Papers/_new_supplement")
CANDIDATES = Path(__file__).resolve().parent / "candidates"

PMC_MAP = {
    "10.1016/j.neuroimage.2022.119536": "PMC9756767",
    "10.1016/j.neuroimage.2024.120772": "PMC12117960",
    "10.1016/j.isci.2025.114436": "PMC12803941",
    "10.1016/j.isci.2026.114998": "PMC12955650",
    "10.1016/j.isci.2025.113441": "PMC12481093",
    "10.1016/j.cognition.2025.106340": "PMC12797880",
    "10.1016/j.isci.2023.108047": "PMC10589857",
    "10.1016/j.isci.2023.107750": "PMC10505979",
    "10.1016/j.cognition.2021.104763": "PMC7614705",
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def make_filename(paper):
    authors = paper.get('authors', [])
    first = authors[0] if authors else 'Unknown'
    parts = first.strip().split()
    last = re.sub(r'[^\w]', '', parts[-1]) if parts else 'Unknown'
    year = paper.get('year', 'XXXX')
    title = re.sub(r'[^\w\s]', '', paper.get('title', '')[:80]).strip().replace(' ', '_')
    doi_hash = hashlib.md5(paper.get('doi', '').encode()).hexdigest()[:6]
    return f"{last}_{year}_{title}_{doi_hash}.pdf"

def get_ftp_url(pmcid):
    """Query NCBI OA API for FTP tar.gz URL."""
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_str = resp.read().decode()
        root = ET.fromstring(xml_str)
        for link in root.iter('link'):
            if link.get('format') == 'tgz':
                return link.get('href')
    except Exception as e:
        log(f"    OA API error: {e}")
    return None

def download_from_ftp(ftp_url, out_path):
    """Download tar.gz from FTP, extract PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tgz_path = os.path.join(tmpdir, "package.tar.gz")
        try:
            cmd = ['curl', '-s', '-o', tgz_path, '--max-time', '120', ftp_url]
            subprocess.run(cmd, capture_output=True, timeout=130)

            if not os.path.exists(tgz_path) or os.path.getsize(tgz_path) < 1000:
                return False, "download_failed"

            # Extract PDF from tar.gz
            with tarfile.open(tgz_path, 'r:gz') as tar:
                pdf_members = [m for m in tar.getmembers() if m.name.endswith('.pdf')]
                if not pdf_members:
                    return False, "no_pdf_in_tar"

                # Extract the main PDF (usually the largest one)
                pdf_members.sort(key=lambda m: m.size, reverse=True)
                member = pdf_members[0]
                tar.extract(member, tmpdir)
                extracted = os.path.join(tmpdir, member.name)

                # Verify it's a PDF
                with open(extracted, 'rb') as f:
                    header = f.read(5)
                if header != b'%PDF-':
                    return False, "not_pdf"

                # Copy to destination
                import shutil
                shutil.copy2(extracted, str(out_path))
                return True, out_path.stat().st_size

        except Exception as e:
            return False, str(e)

def main():
    NAS_PDF_DIR.mkdir(exist_ok=True)

    # Load metadata
    pass_list = json.load(open(CANDIDATES / "02_resolved_pass.json"))
    doi_info = {p['doi']: p for p in pass_list}
    piis = json.load(open(CANDIDATES / "elsevier_piis.json"))

    # Load fetch log
    fetch_log_path = CANDIDATES / "03_fetch_log.json"
    fetch_log = json.load(open(fetch_log_path))
    done_dois = set(e['doi'] for e in fetch_log if e.get('status') in ('success', 'exists'))

    log(f"=== FTP RESCUE: {len(piis)} Elsevier papers ===")

    success = 0
    failed = 0
    failed_dois = []

    for i, p in enumerate(piis):
        doi = p['doi']
        paper = doi_info.get(doi, {'doi': doi, 'title': 'unknown', 'authors': [], 'year': ''})
        fname = make_filename(paper)
        out_path = NAS_PDF_DIR / fname

        if out_path.exists() and out_path.stat().st_size > 10000:
            log(f"[{i+1}/{len(piis)}] EXISTS: {fname[:55]}")
            if doi not in done_dois:
                fetch_log.append({'doi': doi, 'status': 'exists', 'path': str(out_path)})
            success += 1
            continue

        if doi in done_dois:
            log(f"[{i+1}/{len(piis)}] DONE: {doi[:45]}")
            success += 1
            continue

        pmcid = PMC_MAP.get(doi)
        if not pmcid:
            log(f"[{i+1}/{len(piis)}] NO_PMC: {doi[:45]}")
            failed += 1
            failed_dois.append({'doi': doi, 'pii': p['pii']})
            continue

        log(f"[{i+1}/{len(piis)}] {doi} → {pmcid}")

        ftp_url = get_ftp_url(pmcid)
        if not ftp_url:
            log(f"  ✗ No FTP URL")
            failed += 1
            failed_dois.append({'doi': doi, 'pii': p['pii']})
            continue

        log(f"  FTP: {ftp_url[-50:]}")
        ok, info = download_from_ftp(ftp_url, out_path)

        if ok:
            log(f"  ✓ {info/1e6:.1f} MB → {fname[:55]}")
            fetch_log.append({'doi': doi, 'status': 'success', 'path': str(out_path), 'source': 'pmc_ftp'})
            success += 1
        else:
            log(f"  ✗ {info}")
            failed += 1
            failed_dois.append({'doi': doi, 'pii': p['pii']})

        time.sleep(1)

        if (i + 1) % 5 == 0:
            with open(fetch_log_path, 'w') as f:
                json.dump(fetch_log, f, indent=2, ensure_ascii=False)

    # Final save
    with open(fetch_log_path, 'w') as f:
        json.dump(fetch_log, f, indent=2, ensure_ascii=False)

    if failed_dois:
        with open(CANDIDATES / "elsevier_still_blocked.json", 'w') as f:
            json.dump(failed_dois, f, indent=2)

    log(f"\n{'='*50}")
    log(f"FTP RESCUE: {success} success, {failed} failed")
    if failed_dois:
        log(f"Still need Chrome: {len(failed_dois)} papers")
        for d in failed_dois:
            log(f"  {d['doi']}")

if __name__ == '__main__':
    main()
