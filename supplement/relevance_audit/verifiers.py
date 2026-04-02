#!/usr/bin/env python3
"""LLM Verifiers for Relevance Verification v2.
Three narrow-scope verifiers that can only PROMOTE papers (never demote).
"""
import json, re, os, time
import requests
from pathlib import Path

CREDS_FILE = Path("/Users/joonoh/paper-scout-hub/source/credentials.json")
LLM_MODEL = "qwen/qwen3-32b"
LLM_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
LLM_DELAY = 1.0


def get_api_key():
    if CREDS_FILE.exists():
        return json.load(open(CREDS_FILE)).get('openrouter_api_key', '')
    return os.environ.get('OPENROUTER_API_KEY', '')


def _call_llm(prompt, api_key, max_tokens=300):
    """Call LLM with /no_think prefix."""
    resp = requests.post(LLM_ENDPOINT, headers={
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }, json={
        'model': LLM_MODEL,
        'messages': [{'role': 'user', 'content': f'/no_think\n{prompt}'}],
        'temperature': 0.1,
        'max_tokens': max_tokens,
    }, timeout=120)
    resp.raise_for_status()
    content = resp.json()['choices'][0]['message']['content']
    return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()


# ═══════════════════════════════════════════════════
#  VERIFIER A: PI HOMONYM DISAMBIGUATION
# ═══════════════════════════════════════════════════

def verify_pi_homonym(author, abstract, pi_info, api_key):
    """Determine if author is the same person as the known PI.

    Returns: 'same' | 'different' | 'uncertain'
    Can only PROMOTE (same → higher S2 score). Never demotes.
    """
    prompt = f"""아래 논문의 저자가 신경과학자 {pi_info['full_name']} ({pi_info['affiliation']}, 분야: {', '.join(pi_info['categories'])})와 같은 사람인지 판단하세요.

논문 저자: {author}
논문 초록: {abstract[:400]}

같은 사람이면 "same", 다른 사람이면 "different", 불확실하면 "uncertain"을 JSON으로 응답:
{{"verdict": "same|different|uncertain", "reason": "1문장"}}"""

    try:
        content = _call_llm(prompt, api_key)
        m = re.search(r'\{[^{}]*"verdict"[^{}]*\}', content)
        if m:
            result = json.loads(m.group())
            return result.get('verdict', 'uncertain'), result.get('reason', '')
    except:
        pass
    return 'uncertain', 'API error'


# ═══════════════════════════════════════════════════
#  VERIFIER B: PROJECT CONNECTION MAPPER
# ═══════════════════════════════════════════════════

PROJECT_DESCRIPTIONS = {
    'JOP_RingRepSca': 'History effect dissociation in orientation estimation, relative vs absolute space, BMBU model',
    'JOP_GranRDT': 'Granularity effect in decision variable space, belief range narrowing with commitment',
    'MSY_CatVsMag': 'Categorical vs magnitude serial dependence on face gender spectrum, X-shape SD, gambler fallacy',
    'BYL_BayesianObserver': 'Bayesian observer models for VWM, contraction bias, efficient coding',
    'JYK_RNN': 'Stimulus-specific + decision-consistent bias from drift-diffusion in RNN WM models',
    'MJC_SeqVWM': 'Sequential VWM with contrast-dependent attraction/repulsion, SOB energy field model',
    'SK_WMRepresentation': 'Sensory vs mnemonic code in EVC, orthogonal subspaces, geometry-preserving rotation, 7T fMRI',
    'JHR_SpatialExtent': 'EVC pRF anisotropy, radiality vs co-axiality, oriented grating pRF, individual differences',
    'SMJ_Concentricity': 'Co-circularity in natural images, saccadic targeting, eye movement optimization',
    'JSL_SerialDep_Spatial': 'Serial dependence in object-centered space, attention gating',
    'BHL_WM_Binding': 'Feature binding in VWM, multi-object context, sensory decoding',
    'lab_methods': 'Model-based fMRI, dPCA, IEM, RSA, crossnobis, psychophysics, pupillometry, tDCS',
}

def verify_project_connection(abstract, api_key):
    """Find specific CSNL project connections for a paper.

    Returns: (project_name, connection_description) or (None, None)
    Can only PROMOTE papers to higher tier.
    """
    project_list = "\n".join(f"- {k}: {v}" for k, v in PROJECT_DESCRIPTIONS.items())

    prompt = f"""아래 논문이 CSNL 연구실의 프로젝트와 구체적으로 연결되는지 판단하세요.

CSNL 프로젝트:
{project_list}

논문 초록:
{abstract[:500]}

연결이 있으면 프로젝트 이름과 연결 설명을 JSON으로:
{{"connected": true, "project": "프로젝트명", "connection": "구체적 연결 1문장"}}

연결이 없으면:
{{"connected": false}}"""

    try:
        content = _call_llm(prompt, api_key, max_tokens=400)
        m = re.search(r'\{[^{}]*"connected"[^{}]*\}', content)
        if m:
            result = json.loads(m.group())
            if result.get('connected'):
                return result.get('project', ''), result.get('connection', '')
    except:
        pass
    return None, None


# ═══════════════════════════════════════════════════
#  VERIFIER C: ALIEN FIELD CONFIRMER
# ═══════════════════════════════════════════════════

def verify_alien_field(title, abstract, api_key):
    """Confirm that a low-scoring paper is truly from a non-neuroscience field.

    Returns: (field_name, is_neuroscience)
    If uncertain, returns (field, True) → paper stays in review (conservative).
    """
    prompt = f"""이 논문의 연구 분야를 판단하세요.

제목: {title}
초록: {abstract[:400]}

다음 중 해당하는 분야:
A) 신경과학/인지과학/심리학/계산신경과학 (광의) → is_neuro = true
B) 신경과학과 무관 (재료공학, 농업, 지질학, 비신경의학, 사회과학, 경영학 등) → is_neuro = false

의심스러우면 is_neuro = true로 판단 (보수적).

JSON으로만 응답:
{{"field": "구체적 분야", "is_neuro": true/false}}"""

    try:
        content = _call_llm(prompt, api_key)
        m = re.search(r'\{[^{}]*"is_neuro"[^{}]*\}', content)
        if m:
            result = json.loads(m.group())
            return result.get('field', 'unknown'), result.get('is_neuro', True)
    except:
        pass
    return 'unknown', True  # Default: assume neuroscience (conservative)


# ═══════════════════════════════════════════════════
#  BATCH RUNNER
# ═══════════════════════════════════════════════════

def run_verifiers(scores_path, output_path=None):
    """Run all verifiers on scored papers and update tiers."""
    api_key = get_api_key()

    with open(scores_path) as f:
        papers = json.load(f)

    active = [p for p in papers if not p.get('is_trashbin', False)]
    updates = []

    # Verifier A: PI Homonym
    homonym_papers = [p for p in active if p['details'].get('needs_homonym_check')]
    if homonym_papers:
        print(f"Verifier A: {len(homonym_papers)} PI homonym checks")
        for p in homonym_papers:
            pi_info = {'full_name': p['author'], 'affiliation': '', 'categories': []}
            verdict, reason = verify_pi_homonym(
                p['author'], p.get('_abstract', ''), pi_info, api_key)
            updates.append({
                'filename': p['filename'],
                'verifier': 'A_homonym',
                'verdict': verdict,
                'reason': reason,
                'action': 'promote_s2' if verdict == 'same' else 'none',
            })
            print(f"  {verdict}: {p['author']} — {reason[:60]}")
            time.sleep(LLM_DELAY)

    # Verifier B: Project Connection (review tier only)
    review_papers = [p for p in active if p['tier'] == 'review']
    if review_papers:
        print(f"\nVerifier B: {len(review_papers)} project connection checks")
        for p in review_papers:
            project, connection = verify_project_connection(
                p.get('_abstract', ''), api_key)
            action = 'promote' if project else 'none'
            updates.append({
                'filename': p['filename'],
                'verifier': 'B_project',
                'project': project,
                'connection': connection,
                'action': action,
            })
            if project:
                print(f"  CONNECT: {p['author']} → {project}: {connection[:50]}")
            time.sleep(LLM_DELAY)

    # Verifier C: Alien Field (likely_trash tier only)
    trash_papers = [p for p in active if p['tier'] == 'likely_trash']
    if trash_papers:
        print(f"\nVerifier C: {len(trash_papers)} alien field checks")
        for p in trash_papers:
            field, is_neuro = verify_alien_field(
                p['title'], p.get('_abstract', ''), api_key)
            action = 'promote' if is_neuro else 'confirm_trash'
            updates.append({
                'filename': p['filename'],
                'verifier': 'C_alien',
                'field': field,
                'is_neuro': is_neuro,
                'action': action,
            })
            tag = "NEURO" if is_neuro else "ALIEN"
            print(f"  {tag}: {p['author']} ({field})")
            time.sleep(LLM_DELAY)

    # Save updates
    out = output_path or scores_path.replace('.json', '_verified.json')
    with open(out, 'w') as f:
        json.dump(updates, f, indent=2, ensure_ascii=False)
    print(f"\nVerification results saved to {out}")

    # Summary
    promoted = sum(1 for u in updates if u['action'] == 'promote')
    confirmed_trash = sum(1 for u in updates if u['action'] == 'confirm_trash')
    print(f"Promoted: {promoted}, Confirmed trash: {confirmed_trash}, No change: {len(updates) - promoted - confirmed_trash}")

    return updates
