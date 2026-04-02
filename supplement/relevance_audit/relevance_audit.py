#!/usr/bin/env python3
"""Relevance Audit Pipeline for NAS Paper DB
============================================
Task A: Embedding-based outlier detection → LLM verification
Task B: Abstract-based screening → LLM verification

Usage:
  python3 relevance_audit.py --task A --dry-run
  python3 relevance_audit.py --task A --apply
  python3 relevance_audit.py --task B --dry-run --batch-size 50
  python3 relevance_audit.py --task all --apply
"""
import json, os, sys, time, re, hashlib, argparse, shutil
import numpy as np
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Paths ──
SCRIPT_DIR = Path(__file__).resolve().parent
SUPPLEMENT_DIR = SCRIPT_DIR.parent
NAS_PDF_DIR = Path("/Volumes/CSNL_new/Memory/Papers/_new_supplement")
NPZ_PATH = Path("/Volumes/CSNL_new/Memory/Papers/embedding_nemotron/embeddings.npz")
INDEX_PATH = Path("/Volumes/CSNL_new/Memory/Papers/embedding_nemotron/index.json")
TRASH_DIR = NAS_PDF_DIR / "_trashbin"
PI_NETWORK = SUPPLEMENT_DIR.parent / "data" / "pi_network_data.json"
CREDS_FILE = SUPPLEMENT_DIR.parent / "source" / "credentials.json"

# ── Output paths ──
AUDIT_DIR = SCRIPT_DIR / "results"
AUDIT_DIR.mkdir(exist_ok=True)

# ── LLM Config ──
LLM_MODEL = "qwen/qwen3-32b"
LLM_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_ENDPOINT = "https://openrouter.ai/api/v1/embeddings"
NUM_JUDGES = 3
LLM_DELAY = 1.0  # seconds between LLM calls

# ── Thresholds ──
OUTLIER_PERCENTILE = 10  # Task A: bottom N% by max anchor similarity
OUTLIER_COSINE_MAX = 0.20  # Task A: absolute cosine threshold
ABSTRACT_BATCH_SIZE = 30  # Task B: papers per LLM screening batch


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)


def get_api_key():
    if CREDS_FILE.exists():
        with open(CREDS_FILE) as f:
            return json.load(f).get('openrouter_api_key', '')
    return os.environ.get('OPENROUTER_API_KEY', '')


# ═══════════════════════════════════════════════════
#  CSNL CONTEXT
# ═══════════════════════════════════════════════════

CSNL_RESEARCH_SUMMARY = """CSNL (Cognitive and Systems Neuroscience Lab, SNU) 연구 분야:
- Visual Working Memory (VWM): precision, capacity, drift, serial dependence, attractor dynamics
- Bayesian Decision Making (BDM): observer models, drift-diffusion, evidence accumulation, confidence
- Neural Dynamics (NN): population coding, RNN models, latent manifold, dimensionality reduction
- fMRI & Visual Cortex (fVC): retinotopy, pRF, layer-specific BOLD, 7T imaging, V1-V4
- Categorization & Generalization (CG): boundary effects, prototype models, transfer learning
- Methodology (METH): psychophysics, RSA, IEM, dPCA, meta-analysis, Bayesian statistics
- Metacognition: confidence, signal detection theory, type-2 sensitivity
- Perceptual Decision Making: 2AFC, speed-accuracy tradeoff, sequential effects
- Sensorimotor Control: motor planning, eye movements, saccades, adaptation
- Computational Models: efficient coding, normalization, gain control, divisive normalization"""

CSNL_ANCHORS = [
    "Visual working memory precision and capacity limits in human fMRI, orientation estimation tasks",
    "Serial dependence and attractive bias in visual perception, previous stimuli influence current judgments",
    "Attractor dynamics in working memory, drift-diffusion models of estimation bias",
    "Bayesian observer models for perception, prior distributions and likelihood functions in psychophysics",
    "Population receptive field mapping using fMRI retinotopy, pRF anisotropy and cortical magnification",
    "Recurrent neural network models of working memory, ring attractor networks and persistent activity",
    "Representational similarity analysis RSA in human neuroimaging, multivariate pattern analysis",
    "Perceptual decision making in forced choice tasks, drift-diffusion modeling of reaction times",
    "Confidence judgments and metacognition in perceptual decisions, neural correlates of certainty",
    "Efficient coding theory of neural population responses in visual cortex, optimal resource allocation",
    "Psychophysical methods for measuring visual perception, bias and sensitivity in discrimination",
    "Adaptation aftereffects and sensory history on visual perception, sequential dependencies",
    "Numerosity perception and approximate number system, neural basis of numerical cognition",
    "Visual crowding and ensemble perception, texture statistics and summary representations",
    "Eye tracking saccade analysis in visual cognition, fixation stability during memory maintenance",
    "fMRI BOLD signal analysis for visual cortex mapping, connective field models",
    "Transcranial stimulation tDCS effects on visual perception and working memory",
    "Demixed principal component analysis dPCA of neural population activity during cognitive tasks",
    "Inverted encoding model IEM for reconstructing stimulus features from fMRI voxel patterns",
    "Neural coding of orientation selectivity in human visual cortex V1 V2 V3 V4",
    "Reinforcement learning and reward prediction error in decision making",
    "Deep neural networks as models of biological visual processing, CNN comparison to brain",
    "Motor control and planning, cerebellum, basal ganglia in sensorimotor processing",
    "Hippocampal representations, spatial coding, place cells, grid cells, navigation",
]


def load_pi_network():
    """Load PI last names from network data."""
    if not PI_NETWORK.exists():
        return set()
    with open(PI_NETWORK) as f:
        data = json.load(f)
    pi_names = set()
    for n in data.get('nodes', []):
        name = n.get('full_name') or n.get('id', '')
        parts = name.strip().split()
        if parts:
            pi_names.add(parts[-1].lower())
    return pi_names


# ═══════════════════════════════════════════════════
#  EMBEDDING UTILITIES
# ═══════════════════════════════════════════════════

def cosine_sim(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def embed_texts(texts, api_key):
    """Embed a batch of texts via OpenRouter."""
    import requests
    resp = requests.post(EMBED_ENDPOINT, headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }, json={'model': EMBED_MODEL, 'input': texts}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return [np.array(d['embedding'], dtype=np.float32) for d in data['data']]


def load_embeddings():
    """Load NPZ embeddings and return dict of {filename: vector}."""
    data = np.load(NPZ_PATH, allow_pickle=True)
    result = {}
    for key in data.files:
        vec = data[key].astype(np.float32)
        result[key] = vec
    return result


# ═══════════════════════════════════════════════════
#  TEXT EXTRACTION
# ═══════════════════════════════════════════════════

def extract_abstract(pdf_path, max_chars=2000):
    """Extract text from first 2 pages of PDF."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = ""
        for i, page in enumerate(reader.pages[:3]):
            t = page.extract_text() or ""
            text += t + " "
            if len(text) > max_chars:
                break
        return text[:max_chars].strip()
    except Exception:
        return ""


def parse_title_from_filename(filename):
    """Extract author, year, title from filename."""
    stem = filename.replace('.pdf', '')
    parts = stem.split('_', 2)
    if len(parts) >= 3:
        author = parts[0]
        year = parts[1]
        title = parts[2].replace('_', ' ')
        # Remove trailing hash
        title = re.sub(r'\s+[a-f0-9]{6}$', '', title)
        return author, year, title
    return stem, '', ''


# ═══════════════════════════════════════════════════
#  TASK A: EMBEDDING OUTLIER DETECTION
# ═══════════════════════════════════════════════════

def task_a_detect_outliers(embeddings, api_key):
    """Find papers with lowest similarity to CSNL anchors."""
    log("Task A: Computing anchor embeddings...")

    anchor_cache = AUDIT_DIR / "anchor_embeddings.json"
    if anchor_cache.exists():
        with open(anchor_cache) as f:
            anchor_vecs = [np.array(v, dtype=np.float32) for v in json.load(f)]
        log(f"  Loaded {len(anchor_vecs)} cached anchor embeddings")
    else:
        anchor_vecs = []
        for i in range(0, len(CSNL_ANCHORS), 20):
            batch = CSNL_ANCHORS[i:i+20]
            vecs = embed_texts(batch, api_key)
            anchor_vecs.extend(vecs)
            time.sleep(1.5)
        with open(anchor_cache, 'w') as f:
            json.dump([v.tolist() for v in anchor_vecs], f)
        log(f"  Computed and cached {len(anchor_vecs)} anchor embeddings")

    log(f"Task A: Computing distances for {len(embeddings)} papers...")
    scores = {}
    for fname, vec in embeddings.items():
        max_sim = max(cosine_sim(vec, a) for a in anchor_vecs)
        scores[fname] = max_sim

    # Sort by similarity (ascending = least relevant first)
    sorted_papers = sorted(scores.items(), key=lambda x: x[1])
    threshold_idx = int(len(sorted_papers) * OUTLIER_PERCENTILE / 100)
    threshold_val = sorted_papers[threshold_idx][1] if threshold_idx < len(sorted_papers) else 0.3

    # Filter to _new_supplement only
    nas_files = set(f.name for f in NAS_PDF_DIR.iterdir()
                    if f.is_file() and f.name.endswith('.pdf')) if NAS_PDF_DIR.exists() else set()
    sorted_papers = [(f, s) for f, s in sorted_papers if f in nas_files or not nas_files]

    # Use absolute threshold or percentile, whichever catches more
    outliers = [(fname, sim) for fname, sim in sorted_papers
                if sim < max(threshold_val, OUTLIER_COSINE_MAX)]

    log(f"Task A: {len(outliers)} outlier candidates "
        f"(cosine < {max(threshold_val, OUTLIER_COSINE_MAX):.4f})")

    return outliers, scores


# ═══════════════════════════════════════════════════
#  TASK B: ABSTRACT-BASED SCREENING
# ═══════════════════════════════════════════════════

def task_b_screen_abstracts(pdf_dir, already_flagged, api_key, batch_size=30):
    """Screen all papers by abstract using LLM batch screening."""
    log("Task B: Extracting abstracts from all PDFs...")

    pdf_files = sorted([f for f in pdf_dir.iterdir()
                       if f.is_file() and f.name.endswith('.pdf')])
    already_set = set(f for f, _ in already_flagged)

    # Extract abstracts for papers NOT already flagged by Task A
    candidates = []
    for pdf in pdf_files:
        if pdf.name in already_set:
            continue
        author, year, title = parse_title_from_filename(pdf.name)
        abstract = extract_abstract(pdf)
        if abstract:
            candidates.append({
                'filename': pdf.name,
                'author': author,
                'year': year,
                'title': title,
                'abstract': abstract[:800],
            })

    log(f"Task B: {len(candidates)} papers to screen (excluding {len(already_set)} Task A flags)")

    # LLM batch screening
    flagged = []
    import requests

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i+batch_size]
        paper_list = "\n".join(
            f"[{j+1}] {p['author']} ({p['year']}): {p['title']}\n    Abstract: {p['abstract'][:300]}..."
            for j, p in enumerate(batch)
        )

        prompt = f"""/no_think
{CSNL_RESEARCH_SUMMARY}

아래 논문 목록에서 CSNL 연구와 **완전히 무관한** 논문만 골라내세요.
의심스러우면 포함하지 마세요 (보수적으로).

IRRELEVANT 기준 (이것만 해당):
- 완전히 다른 분야: 재료공학, 화학합성, 농업, 지질학, 환경공학, 토목
- 비신경 의학: 암, 신장, 심장, 정형외과, 피부과, 산부인과
- 사회과학/경영: 경제학, 법학, 교육행정, 경영학, HR, 마케팅
- PI 동명이인: 같은 성이지만 다른 분야 (Ganguli 지질학, Burr 화성지질학)

RELEVANT (출력하지 말 것):
- 신경과학/인지과학/심리학/계산신경과학의 모든 하위분야
- 신경과학 도구: Neuropixels, silicon probes, calcium imaging, head fixation
- 시각과학 기초: cone fundamentals, retinotopy, optics
- 임상 신경과학: ADHD, 자폐, 파킨슨, 조현병의 인지적 측면
- 인지 관련 AI/ML: DNN 비교, 인지 모델링, 강화학습
- correction/erratum (원본이 신경과학이면)

논문 목록:
{paper_list}

출력 형식 (JSON array만, 설명 없이):
[{{"idx": 1, "reason": "재료공학 - 합금 연구", "field": "materials science"}}]

무관한 논문이 없으면 []을 출력하세요."""

        try:
            resp = requests.post(LLM_ENDPOINT, headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            }, json={
                'model': LLM_MODEL,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': 0.1,
                'max_tokens': 2000,
            }, timeout=120)
            resp.raise_for_status()
            content = resp.json()['choices'][0]['message']['content']

            # Parse JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                results = json.loads(json_match.group())
                for r in results:
                    idx = r.get('idx', 0) - 1
                    if 0 <= idx < len(batch):
                        flagged.append((
                            batch[idx]['filename'],
                            r.get('reason', ''),
                            r.get('field', ''),
                        ))
            log(f"  Batch {i//batch_size + 1}: {len(results) if json_match else 0} flagged")
        except Exception as e:
            log(f"  Batch {i//batch_size + 1} ERROR: {e}")

        time.sleep(LLM_DELAY)

    log(f"Task B: {len(flagged)} papers flagged by abstract screening")
    return flagged


# ═══════════════════════════════════════════════════
#  RELEVANCE JUDGE (LLM-based)
# ═══════════════════════════════════════════════════

def judge_paper(paper_info, judge_id, api_key, pi_names):
    """Single judge evaluates a paper's relevance to CSNL."""
    import requests

    author = paper_info.get('author', '')
    title = paper_info.get('title', '')
    abstract = paper_info.get('abstract', '')
    year = paper_info.get('year', '')
    filename = paper_info.get('filename', '')
    flag_reason = paper_info.get('flag_reason', '')

    is_pi_name = author.lower() in pi_names

    prompt = f"""/no_think
당신은 CSNL 연구 관련성 판사 #{judge_id}입니다. 의심스러우면 RELEVANT로 판단하세요 (보수적).

{CSNL_RESEARCH_SUMMARY}

PI Network 핵심 연구자: Shadlen, Churchland, Ratcliff, Ganguli(Surya, 신경과학), Brody, Jazayeri(Mehrdad, MIT 신경과학), Urai(Anne, 신경과학), Burr(David, 시각인지), Heathcote(Andrew, 심리통계), Sims(Chris, 효율코딩), Mur(Marieke, 신경과학), Wandell(Brian, 시각과학), Bimbard(Célian, IBL 신경과학), Sussillo(David, 계산신경과학), Steinmetz(Nick, Neuropixels), Summerfield(Chris, 인지신경과학)

=== 반드시 RELEVANT로 판단해야 하는 것들 ===
- 신경과학 실험 도구/방법: Neuropixels, silicon probes, calcium indicators, head fixation, 실험 장비 개선
- 신경과학 데이터 분석: fMRI preprocessing, spike sorting, neural data infrastructure
- 인지과학 방법론: psychophysics, Bayesian statistics, meta-analysis, experimental design
- 시각과학 기초: cone fundamentals, retinotopy, color science, visual optics
- 인지/의사결정/학습/기억 관련: 주제가 약간 다르더라도 인지과학 범주면 RELEVANT
- 위 PI들의 실제 신경과학/인지과학 논문 (동명이인 아닌 경우)
- correction/erratum: 원본이 신경과학이면 RELEVANT
- 임상 신경과학 (ADHD, 자폐, 파킨슨의 인지적 측면): RELEVANT

=== IRRELEVANT 판단 기준 (이것만 IRRELEVANT) ===
- 완전히 다른 분야: 재료공학, 화학합성, 농업, 지질학, 토목공학, 환경공학
- 비신경 의학: 암, 신장, 심장, 정형외과, 치과, 산부인과
- 사회과학/경영: 경제학, 법학, 교육행정, 마케팅, HR
- PI 동명이인 (다른 분야): Ganguli(지질/경제), Burr(화성), Jazayeri(교육), Heathcote(철학)

평가 대상:
- 저자: {author} ({year})
- 제목: {title}
- 초록/내용: {abstract[:600]}
- 플래그 사유: {flag_reason}
- PI 이름 매칭: {'YES' if is_pi_name else 'NO'}

JSON으로만 응답:
{{"verdict": "RELEVANT|IRRELEVANT|BORDERLINE", "confidence": "HIGH|MEDIUM|LOW", "reason": "1-2문장", "actual_field": "분야"}}"""

    try:
        resp = requests.post(LLM_ENDPOINT, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }, json={
            'model': LLM_MODEL,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.2,
            'max_tokens': 500,
        }, timeout=120)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']

        # Strip Qwen3 <think> tags if present
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        json_match = re.search(r'\{[^{}]*"verdict"[^{}]*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        # Fallback: try to extract verdict from free text
        if 'IRRELEVANT' in content.upper():
            return {'verdict': 'IRRELEVANT', 'confidence': 'MEDIUM', 'reason': content[:200], 'actual_field': 'unknown'}
        elif 'RELEVANT' in content.upper():
            return {'verdict': 'RELEVANT', 'confidence': 'MEDIUM', 'reason': content[:200], 'actual_field': 'unknown'}
    except Exception as e:
        return {'verdict': 'ERROR', 'confidence': 'LOW', 'reason': str(e)[:200], 'actual_field': 'unknown'}

    return {'verdict': 'ERROR', 'confidence': 'LOW', 'reason': 'parse failure', 'actual_field': 'unknown'}


def consensus_arbitrate(judgments):
    """Apply 2/3 majority rule to judge verdicts."""
    verdicts = [j.get('verdict', 'ERROR') for j in judgments]
    irrelevant_count = sum(1 for v in verdicts if v == 'IRRELEVANT')
    relevant_count = sum(1 for v in verdicts if v == 'RELEVANT')
    borderline_count = sum(1 for v in verdicts if v == 'BORDERLINE')

    # 2/3 majority for IRRELEVANT → trash
    if irrelevant_count >= 2:
        return 'TRASH', irrelevant_count
    # 2/3 majority for RELEVANT → keep
    if relevant_count >= 2:
        return 'KEEP', relevant_count
    # Mixed: default to KEEP (conservative)
    return 'KEEP', 0


# ═══════════════════════════════════════════════════
#  VERIFICATION (3-Judge Panel)
# ═══════════════════════════════════════════════════

def verify_candidates(candidates, api_key, pi_names, pdf_dir):
    """Run 3-judge panel on each candidate paper."""
    log(f"Verification: {len(candidates)} candidates × {NUM_JUDGES} judges")

    results = []
    for i, (filename, *extra) in enumerate(candidates):
        author, year, title = parse_title_from_filename(filename)
        abstract = extract_abstract(pdf_dir / filename) if (pdf_dir / filename).exists() else ''
        flag_reason = extra[0] if extra else f'embedding outlier'

        paper_info = {
            'filename': filename,
            'author': author,
            'year': year,
            'title': title,
            'abstract': abstract,
            'flag_reason': flag_reason,
        }

        # Run judges sequentially (to respect rate limits)
        judgments = []
        for j in range(1, NUM_JUDGES + 1):
            judgment = judge_paper(paper_info, j, api_key, pi_names)
            judgments.append(judgment)
            time.sleep(LLM_DELAY)

        decision, agreement = consensus_arbitrate(judgments)

        results.append({
            'filename': filename,
            'author': author,
            'year': year,
            'title': title,
            'flag_reason': flag_reason,
            'judgments': judgments,
            'decision': decision,
            'agreement': agreement,
        })

        verdict_str = ' / '.join(j.get('verdict', '?') for j in judgments)
        log(f"  [{i+1}/{len(candidates)}] {decision} ({verdict_str}) — {author} ({year}): {title[:50]}")

    return results


# ═══════════════════════════════════════════════════
#  HARNESS
# ═══════════════════════════════════════════════════

def compute_harness_metrics(results):
    """Compute quality metrics for the audit."""
    total = len(results)
    if total == 0:
        return {}

    trash_count = sum(1 for r in results if r['decision'] == 'TRASH')
    keep_count = sum(1 for r in results if r['decision'] == 'KEEP')

    # Judge agreement
    agreements = []
    for r in results:
        verdicts = [j.get('verdict', 'ERROR') for j in r['judgments']]
        # Simple agreement: all 3 same?
        if len(set(verdicts)) == 1:
            agreements.append(1.0)
        elif len(set(verdicts)) == 2:
            agreements.append(0.67)
        else:
            agreements.append(0.33)

    avg_agreement = np.mean(agreements) if agreements else 0

    # High-confidence trash (all 3 judges agree IRRELEVANT with HIGH confidence)
    high_conf_trash = sum(1 for r in results
                         if r['decision'] == 'TRASH'
                         and all(j.get('confidence') == 'HIGH' for j in r['judgments']))

    return {
        'total_candidates': total,
        'trash': trash_count,
        'keep': keep_count,
        'avg_judge_agreement': round(avg_agreement, 3),
        'high_confidence_trash': high_conf_trash,
    }


# ═══════════════════════════════════════════════════
#  APPLY (Move to trashbin)
# ═══════════════════════════════════════════════════

def apply_results(results, pdf_dir, npz_path):
    """Move trash papers to trashbin and update NPZ."""
    TRASH_DIR.mkdir(exist_ok=True)
    trash_papers = [r for r in results if r['decision'] == 'TRASH']

    moved = 0
    for r in trash_papers:
        src = pdf_dir / r['filename']
        if src.exists():
            shutil.move(str(src), str(TRASH_DIR / r['filename']))
            moved += 1

    log(f"Moved {moved} papers to {TRASH_DIR}")

    # Update NPZ
    if moved > 0 and npz_path.exists():
        trash_names = set(r['filename'] for r in trash_papers)
        data = np.load(npz_path, allow_pickle=True)
        keep = {k: data[k] for k in data.files if k not in trash_names}
        removed = len(data.files) - len(keep)
        np.savez(npz_path, **keep)
        log(f"NPZ: removed {removed} embeddings, {len(keep)} remaining")

    return moved


# ═══════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='Relevance Audit Pipeline')
    parser.add_argument('--task', choices=['A', 'B', 'all'], default='all')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--batch-size', type=int, default=ABSTRACT_BATCH_SIZE)
    parser.add_argument('--outlier-pct', type=int, default=OUTLIER_PERCENTILE)
    parser.add_argument('--skip-verify', action='store_true', help='Skip 3-judge verification')
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        log("ERROR: No API key found")
        sys.exit(1)

    pi_names = load_pi_network()
    log(f"Loaded {len(pi_names)} PI names")

    all_candidates = []
    all_results = []
    task_a_scores = {}

    # ── Task A ──
    if args.task in ('A', 'all'):
        log("=" * 60)
        log("TASK A: Embedding Outlier Detection")
        log("=" * 60)

        embeddings = load_embeddings()
        log(f"Loaded {len(embeddings)} embeddings")

        outliers, task_a_scores = task_a_detect_outliers(embeddings, api_key)

        # Save scores
        scores_path = AUDIT_DIR / "task_a_scores.json"
        with open(scores_path, 'w') as f:
            json.dump({k: round(v, 6) for k, v in sorted(task_a_scores.items(), key=lambda x: x[1])},
                      f, indent=2)
        log(f"Saved scores to {scores_path}")

        if args.dry_run:
            log(f"\nDRY RUN — Top {len(outliers)} outliers:")
            for fname, sim in outliers[:30]:
                author, year, title = parse_title_from_filename(fname)
                log(f"  {sim:.4f} | {author} ({year}): {title[:60]}")
            return

        all_candidates.extend(outliers)

    # ── Task B ──
    if args.task in ('B', 'all'):
        log("=" * 60)
        log("TASK B: Abstract-Based Screening")
        log("=" * 60)

        flagged = task_b_screen_abstracts(
            NAS_PDF_DIR, all_candidates, api_key, batch_size=args.batch_size)

        if args.dry_run:
            log(f"\nDRY RUN — {len(flagged)} papers flagged:")
            for fname, reason, field in flagged[:30]:
                log(f"  [{field}] {fname[:60]} — {reason}")
            return

        # Convert to same format as Task A candidates
        all_candidates.extend([(f, reason) for f, reason, _ in flagged])

    # ── Dedup candidates ──
    seen = set()
    deduped = []
    for item in all_candidates:
        fname = item[0]
        if fname not in seen:
            seen.add(fname)
            deduped.append(item)
    all_candidates = deduped
    log(f"\nTotal unique candidates: {len(all_candidates)}")

    # ── 3-Judge Verification ──
    if not args.skip_verify:
        all_results = verify_candidates(all_candidates, api_key, pi_names, NAS_PDF_DIR)
    else:
        # Skip verification, treat all candidates as TRASH
        all_results = [{'filename': c[0], 'decision': 'TRASH', 'judgments': [],
                        'agreement': 0, **dict(zip(['flag_reason'], c[1:] or ['']))}
                       for c in all_candidates]

    # ── Save results ──
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_path = AUDIT_DIR / f"audit_results_{timestamp}.json"
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    log(f"Results saved to {results_path}")

    # ── Harness metrics ──
    metrics = compute_harness_metrics(all_results)
    log(f"\n{'=' * 60}")
    log(f"HARNESS METRICS")
    log(f"{'=' * 60}")
    for k, v in metrics.items():
        log(f"  {k}: {v}")

    # ── Summary ──
    trash = [r for r in all_results if r['decision'] == 'TRASH']
    keep = [r for r in all_results if r['decision'] == 'KEEP']

    log(f"\n{'=' * 60}")
    log(f"SUMMARY: {len(trash)} TRASH, {len(keep)} KEEP out of {len(all_results)} candidates")
    log(f"{'=' * 60}")

    if trash:
        log("\nPapers to remove:")
        for r in trash:
            reasons = [j.get('reason', '') for j in r.get('judgments', [])]
            reason = reasons[0] if reasons else r.get('flag_reason', '')
            log(f"  {r.get('author', '?')} ({r.get('year', '?')}): {r.get('title', '?')[:60]}")
            log(f"    Reason: {reason[:80]}")

    # ── Apply ──
    if args.apply and trash:
        log(f"\nApplying: moving {len(trash)} papers to trashbin...")
        moved = apply_results(all_results, NAS_PDF_DIR, NPZ_PATH)
        log(f"Done. {moved} files moved.")
    elif not args.apply:
        log("\nUse --apply to move papers to trashbin.")


if __name__ == '__main__':
    main()
