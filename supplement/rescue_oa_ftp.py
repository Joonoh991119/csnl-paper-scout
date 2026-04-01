#!/usr/bin/env python3
"""Rescue ALL failed OA papers via NCBI FTP + Unpaywall + direct DOI.
Handles eLife, Frontiers, PNAS, and any other OA publishers.
Uses FTP tar.gz (bypasses Cloudflare) as primary strategy.
"""
import json, re, os, hashlib, time, subprocess, tarfile, tempfile
import urllib.request, xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from collections import Counter

NAS_PDF_DIR = Path("/Volumes/CSNL_new/Memory/Papers/_new_supplement")
CANDIDATES = Path(__file__).resolve().parent / "candidates"
EMAIL = "joonop99@snu.ac.kr"

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

def get_pmcid(doi):
    """Get PMCID from DOI via NCBI ID converter."""
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={quote(doi, safe='')}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        records = data.get('records', [])
        if records and records[0].get('pmcid'):
            return records[0]['pmcid']
    except:
        pass
    return None

def get_ftp_url(pmcid):
    """Get FTP tar.gz URL from NCBI OA API."""
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
        req = urllib.request.Request(url, headers={'User-Agent': 'CSNL-PaperScout/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_str = resp.read().decode()
        root = ET.fromstring(xml_str)
        for link in root.iter('link'):
            if link.get('format') == 'tgz':
                return link.get('href')
    except:
        pass
    return None

def download_from_ftp(ftp_url, out_path, timeout=120):
    """Download tar.gz, extract PDF."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tgz_path = os.path.join(tmpdir, "package.tar.gz")
        try:
            subprocess.run(['curl', '-s', '-o', tgz_path, '--max-time', str(timeout), ftp_url],
                         capture_output=True, timeout=timeout+10)
            if not os.path.exists(tgz_path) or os.path.getsize(tgz_path) < 1000:
                return False, "download_failed"
            with tarfile.open(tgz_path, 'r:gz') as tar:
                pdf_members = [m for m in tar.getmembers() if m.name.endswith('.pdf')]
                if not pdf_members:
                    return False, "no_pdf_in_tar"
                pdf_members.sort(key=lambda m: m.size, reverse=True)
                tar.extract(pdf_members[0], tmpdir)
                extracted = os.path.join(tmpdir, pdf_members[0].name)
                with open(extracted, 'rb') as f:
                    if f.read(5) != b'%PDF-':
                        return False, "not_pdf"
                import shutil
                shutil.copy2(extracted, str(out_path))
                return True, out_path.stat().st_size
        except Exception as e:
            return False, str(e)

def try_elife_direct(doi, out_path):
    """eLife has direct PDF at predictable URL."""
    # eLife DOI: 10.7554/eLife.XXXXX → https://elifesciences.org/articles/XXXXX
    match = re.search(r'eLife\.(\d+)', doi)
    if not match:
        return False, "no_elife_id"
    article_id = match.group(1)
    pdf_url = f"https://elifesciences.org/download/aHR0cHM6Ly9jZG4uZWxpZmVzY2llbmNlcy5vcmcvYXJ0aWNsZXMve30vZUxpZmUtezB9LXYxLnBkZg==/eLife-{article_id}-v1.pdf"
    # Simpler: just use the standard URL
    pdf_url = f"https://cdn.elifesciences.org/articles/{article_id}/eLife-{article_id}-v1.pdf"
    try:
        cmd = ['curl', '-sL', '-o', str(out_path), '--max-time', '60',
               '-H', 'User-Agent: Mozilla/5.0', pdf_url]
        subprocess.run(cmd, capture_output=True, timeout=70)
        if out_path.exists() and out_path.stat().st_size > 10000:
            with open(out_path, 'rb') as f:
                if f.read(5) == b'%PDF-':
                    return True, out_path.stat().st_size
            out_path.unlink()
    except:
        pass
    return False, "elife_direct_failed"

def try_frontiers_direct(doi, out_path):
    """Frontiers PDFs follow predictable patterns."""
    try:
        # Resolve DOI to get the article URL
        req = urllib.request.Request(f"https://doi.org/{doi}",
            headers={'User-Agent': 'Mozilla/5.0'})
        req.get_method = lambda: 'HEAD'
        resp = urllib.request.urlopen(req, timeout=15)
        final_url = resp.geturl()
        # Frontiers PDF: append /pdf to article URL
        pdf_url = final_url.rstrip('/') + '/pdf'
        cmd = ['curl', '-sL', '-o', str(out_path), '--max-time', '60',
               '-H', 'User-Agent: Mozilla/5.0', '-H', 'Accept: application/pdf,*/*', pdf_url]
        subprocess.run(cmd, capture_output=True, timeout=70)
        if out_path.exists() and out_path.stat().st_size > 10000:
            with open(out_path, 'rb') as f:
                if f.read(5) == b'%PDF-':
                    return True, out_path.stat().st_size
            out_path.unlink()
    except:
        pass
    return False, "frontiers_failed"

def main():
    NAS_PDF_DIR.mkdir(exist_ok=True)

    # Load data
    pass_list = json.load(open(CANDIDATES / "02_resolved_pass.json"))
    doi_info = {p['doi']: p for p in pass_list}
    fetch_log = json.load(open(CANDIDATES / "03_fetch_log.json"))
    
    success_dois = set(e['doi'] for e in fetch_log if e['status'] in ('success', 'exists'))
    fail_dois = set(e['doi'] for e in fetch_log if e['status'] == 'not_available') - success_dois

    # Filter to non-Elsevier failures (Elsevier handled separately)
    blocked = []
    for doi in fail_dois:
        if doi in doi_info and not doi.startswith('10.1016/'):
            blocked.append(doi_info[doi])

    pub_counts = Counter()
    for p in blocked:
        d = p['doi']
        if d.startswith('10.7554/'): pub_counts['eLife'] += 1
        elif d.startswith('10.3389/'): pub_counts['Frontiers'] += 1
        elif d.startswith('10.1073/'): pub_counts['PNAS'] += 1
        elif d.startswith('10.1167/'): pub_counts['JOV'] += 1
        else: pub_counts['Other'] += 1

    log(f"=== OA/FTP RESCUE: {len(blocked)} non-Elsevier failures ===")
    for pub, c in pub_counts.most_common():
        log(f"  {pub}: {c}")

    success = 0
    failed = 0

    for i, paper in enumerate(blocked):
        doi = paper['doi']
        fname = make_filename(paper)
        out_path = NAS_PDF_DIR / fname

        if out_path.exists() and out_path.stat().st_size > 10000:
            success += 1
            continue

        log(f"[{i+1}/{len(blocked)}] {doi[:50]}")

        ok = False

        # Strategy 1: eLife direct CDN
        if doi.startswith('10.7554/'):
            ok, info = try_elife_direct(doi, out_path)
            if ok:
                log(f"  ✓ eLife CDN: {info/1e6:.1f} MB")
                fetch_log.append({'doi': doi, 'status': 'success', 'path': str(out_path), 'source': 'elife_cdn'})

        # Strategy 2: Frontiers direct
        if not ok and doi.startswith('10.3389/'):
            ok, info = try_frontiers_direct(doi, out_path)
            if ok:
                log(f"  ✓ Frontiers: {info/1e6:.1f} MB")
                fetch_log.append({'doi': doi, 'status': 'success', 'path': str(out_path), 'source': 'frontiers'})

        # Strategy 3: PMC FTP (works for any publisher with PMC deposit)
        if not ok:
            pmcid = get_pmcid(doi)
            if pmcid:
                ftp_url = get_ftp_url(pmcid)
                if ftp_url:
                    log(f"  PMC FTP: {pmcid}")
                    ok, info = download_from_ftp(ftp_url, out_path)
                    if ok:
                        log(f"  ✓ FTP: {info/1e6:.1f} MB")
                        fetch_log.append({'doi': doi, 'status': 'success', 'path': str(out_path), 'source': 'pmc_ftp'})

        if ok:
            success += 1
        else:
            log(f"  ✗ Failed")
            failed += 1

        time.sleep(0.5)

        if (i + 1) % 20 == 0:
            with open(CANDIDATES / "03_fetch_log.json", 'w') as f:
                json.dump(fetch_log, f, indent=2, ensure_ascii=False)
            log(f"  --- Progress: {success} ok, {failed} fail ---")

    with open(CANDIDATES / "03_fetch_log.json", 'w') as f:
        json.dump(fetch_log, f, indent=2, ensure_ascii=False)

    log(f"\n{'='*50}")
    log(f"OA RESCUE: {success} success, {failed} failed")

if __name__ == '__main__':
    main()
