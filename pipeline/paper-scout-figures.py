#!/usr/bin/env python3
"""
paper-scout-figures.py — Zero-token figure extraction and ranking from PDFs.

Extracts figures and equations from PDFs using pymupdf, then ranks them
using OpenRouter's embed-vl API. Replaces the LLM-based Visual Agent.

Usage:
    python paper-scout-figures.py extract --pdf paper.pdf --output-dir ./figures/
    python paper-scout-figures.py rank --pdf paper.pdf --members '{"SK": "EVC...", "JYK": "RNN..."}'
    python paper-scout-figures.py download --doi "10.1073/pnas.2518110123" --output paper.pdf
    python paper-scout-figures.py best --pdf paper.pdf --members '{"SK": "...", "JYK": "..."}'
"""

import os
import sys
import json
import base64
import tempfile
import argparse
import math
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from io import BytesIO
import re

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    import fitz  # pymupdf
except ImportError:
    print("Error: pymupdf not installed. Run: pip install pymupdf")
    sys.exit(1)

# ============================================================================
# Configuration
# ============================================================================

OPENROUTER_API_KEY = None
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
EMBED_MODEL = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
EMBED_DIM = 2048
API_TIMEOUT = 30
MAX_RETRIES = 3

MATH_SYMBOLS = {'∫', 'Σ', '∂', '∆', '∇', '≈', '≠', '∝', '∞', '±', '√', '∈', '∉', '⊂', '⊃', '∪', '∩', '∀', '∃'}
LATEX_PATTERNS = [
    r'\$.*?\$',  # $...$
    r'\$\$.*?\$\$',  # $$...$$
    r'\\[.*?\\]',  # \[...\]
    r'\\(.*?\\)',  # \(...\)
    r'\\alpha', r'\\beta', r'\\gamma', r'\\delta',
    r'\\frac{', r'\\int', r'\\sum', r'\\prod', r'\\sqrt',
]

# ============================================================================
# Environment & Configuration
# ============================================================================

def load_env(env_path: str = None) -> None:
    """Load .env file from same directory or given path."""
    global OPENROUTER_API_KEY
    
    if env_path is None:
        # Look in same directory as this script
        script_dir = Path(__file__).parent
        env_path = script_dir / ".env"
    else:
        env_path = Path(env_path)
    
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == 'OPENROUTER_API_KEY':
                            OPENROUTER_API_KEY = value.strip()
    
    # Fall back to environment variable
    if not OPENROUTER_API_KEY:
        OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
    
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not found in .env or environment")


# ============================================================================
# PDF Extraction
# ============================================================================

def extract_figures_from_pdf(
    pdf_path: str,
    min_width: int = 200,
    min_height: int = 200
) -> List[Dict]:
    """
    Extract all images from a PDF that are likely figures (not logos/icons).
    
    Args:
        pdf_path: Path to PDF file
        min_width: Minimum width in pixels
        min_height: Minimum height in pixels
    
    Returns:
        List of dicts with keys: page, index, width, height, image_bytes, bbox
    """
    figures = []
    
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return figures
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        images = page.get_images()
        
        for img_idx, img_ref in enumerate(images):
            try:
                xref = img_ref[0]
                pix = fitz.Pixmap(doc, xref)
                
                # Get image dimensions
                width = pix.width
                height = pix.height
                
                # Skip small icons/logos
                if width < min_width or height < min_height:
                    continue
                
                # Convert to PNG bytes
                if pix.n - pix.alpha < 4:  # GRAY or RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                
                img_bytes = pix.tobytes("png")
                
                # Get bounding box
                bbox = page.get_image_bbox(img_ref)
                
                figures.append({
                    'page': page_num,
                    'index': img_idx,
                    'width': width,
                    'height': height,
                    'image_bytes': img_bytes,
                    'bbox': bbox,
                })
            except Exception as e:
                # Skip problematic images
                continue
    
    doc.close()
    return figures


def extract_equations_from_pdf(pdf_path: str) -> List[Dict]:
    """
    Extract text blocks that look like equations from PDF.
    
    Heuristics: lines with math symbols or LaTeX-like patterns.
    
    Returns:
        List of dicts with keys: page, text, bbox
    """
    equations = []
    
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return equations
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        
        for block in blocks:
            if block["type"] == 0:  # Text block
                text = block["lines"][0]["spans"][0]["text"] if block.get("lines") else ""
                
                # Check for math symbols
                has_math_symbol = any(sym in text for sym in MATH_SYMBOLS)
                
                # Check for LaTeX patterns
                has_latex = any(re.search(pattern, text) for pattern in LATEX_PATTERNS)
                
                if (has_math_symbol or has_latex) and len(text.strip()) > 3:
                    equations.append({
                        'page': page_num,
                        'text': text.strip(),
                        'bbox': block.get("bbox"),
                    })
    
    doc.close()
    return equations


# ============================================================================
# File Operations
# ============================================================================

def save_figure_as_png(image_dict: Dict, output_dir: str, prefix: str = "fig") -> str:
    """
    Save extracted image bytes as PNG file.
    
    Args:
        image_dict: Dict from extract_figures_from_pdf
        output_dir: Directory to save PNG
        prefix: Filename prefix
    
    Returns:
        Path to saved PNG file
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    page = image_dict['page']
    index = image_dict['index']
    filename = f"{prefix}_p{page}_{index}.png"
    filepath = Path(output_dir) / filename
    
    with open(filepath, 'wb') as f:
        f.write(image_dict['image_bytes'])
    
    return str(filepath)


# ============================================================================
# OpenRouter API
# ============================================================================

def _call_embed_api(payload: Dict) -> Optional[List[float]]:
    """
    Call OpenRouter embeddings API with retry logic.
    
    Returns:
        2048-dim embedding vector or None if failed
    """
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not set")
        return None
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/embeddings",
                json=payload,
                headers=headers,
                timeout=API_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            if "data" in data and len(data["data"]) > 0:
                return data["data"][0]["embedding"]
            else:
                print(f"Unexpected API response: {data}")
                return None
                
        except requests.exceptions.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                print(f"API call failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                continue
            else:
                print(f"API call failed after {MAX_RETRIES} attempts: {e}")
                return None


def embed_image_bytes(image_bytes: bytes) -> Optional[List[float]]:
    """
    Embed image via OpenRouter embed-vl API.
    
    Args:
        image_bytes: PNG image bytes
    
    Returns:
        2048-dim embedding vector or None if failed
    """
    try:
        # Convert to base64 data URL
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        image_url = f"data:image/png;base64,{b64}"
        
        payload = {
            "model": EMBED_MODEL,
            "input": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_url
                    }
                }
            ]
        }
        
        return _call_embed_api(payload)
        
    except Exception as e:
        print(f"Error embedding image: {e}")
        return None


def embed_text_for_ranking(text: str) -> Optional[List[float]]:
    """
    Embed text via OpenRouter API for cosine ranking.
    
    Args:
        text: Text to embed
    
    Returns:
        2048-dim embedding vector or None if failed
    """
    try:
        payload = {
            "model": EMBED_MODEL,
            "input": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
        
        return _call_embed_api(payload)
        
    except Exception as e:
        print(f"Error embedding text: {e}")
        return None


# ============================================================================
# Vector Operations
# ============================================================================

def cosine_sim(a: List[float], b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        a: Vector A
        b: Vector B
    
    Returns:
        Cosine similarity in range [-1, 1]
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x ** 2 for x in a))
    norm_b = math.sqrt(sum(x ** 2 for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


# ============================================================================
# Ranking
# ============================================================================

def rank_figures_for_members(
    figures: List[Dict],
    member_descriptions: Dict[str, str],
) -> Dict[str, List[Dict]]:
    """
    Rank all figures by cosine similarity to each member's project description.
    
    Args:
        figures: List of dicts from extract_figures_from_pdf (with image_bytes)
        member_descriptions: Dict mapping member names to project descriptions
    
    Returns:
        Dict mapping member names to sorted list of figures with scores
    """
    results = {}
    
    # Pre-embed member descriptions
    member_embeddings = {}
    for member, desc in member_descriptions.items():
        embedding = embed_text_for_ranking(desc)
        if embedding:
            member_embeddings[member] = embedding
        else:
            print(f"Warning: Could not embed description for {member}")
    
    # Rank figures for each member
    for member, member_embedding in member_embeddings.items():
        ranked_figures = []
        
        for fig_idx, figure in enumerate(figures):
            # Embed figure
            fig_embedding = embed_image_bytes(figure['image_bytes'])
            if not fig_embedding:
                continue
            
            # Compute similarity
            score = cosine_sim(fig_embedding, member_embedding)
            
            ranked_figures.append({
                'figure_index': fig_idx,
                'page': figure['page'],
                'width': figure['width'],
                'height': figure['height'],
                'cosine_score': score,
            })
        
        # Sort by score descending
        ranked_figures.sort(key=lambda x: x['cosine_score'], reverse=True)
        results[member] = ranked_figures
    
    return results


def select_best_visual(
    figures: List[Dict],
    member_descriptions: Dict[str, str],
    equations: List[Dict] = None,
) -> Dict:
    """
    Select the best visual element for a Slack post.
    
    Args:
        figures: List of dicts from extract_figures_from_pdf (with image_bytes)
        member_descriptions: Dict mapping member names to project descriptions
        equations: Optional list from extract_equations_from_pdf
    
    Returns:
        Dict with keys: type, figure_path, figure_cosine, best_member, equation_text, equation_page
    """
    result = {
        'type': None,
        'figure_path': None,
        'figure_cosine': None,
        'best_member': None,
        'equation_text': None,
        'equation_page': None,
    }
    
    if not figures and not equations:
        return result
    
    # Rank figures
    ranked = rank_figures_for_members(figures, member_descriptions)
    
    # Find best figure across all members
    best_score = -1
    best_fig_idx = None
    best_member = None
    
    for member, member_figs in ranked.items():
        if member_figs and member_figs[0]['cosine_score'] > best_score:
            best_score = member_figs[0]['cosine_score']
            best_fig_idx = member_figs[0]['figure_index']
            best_member = member
    
    # Select best figure if score is reasonable
    if best_fig_idx is not None and best_score > 0.3:
        result['type'] = 'figure'
        result['figure_cosine'] = best_score
        result['best_member'] = best_member
        result['figure_index'] = best_fig_idx
    
    # Add equation if available
    if equations and len(equations) > 0:
        best_eq = equations[0]  # Could rank equations too
        if result['type'] == 'figure':
            result['type'] = 'both'
        else:
            result['type'] = 'equation'
        result['equation_text'] = best_eq['text']
        result['equation_page'] = best_eq['page']
    
    return result


# ============================================================================
# Download
# ============================================================================

def download_pdf(doi_or_url: str, output_path: str) -> str:
    """
    Try to download PDF from various sources.
    
    1. Unpaywall API: https://api.unpaywall.org/v2/{doi}?email=csnl@snu.ac.kr
    2. Semantic Scholar: check openAccessPdf field
    3. bioRxiv/PNAS direct PDF URLs
    
    Args:
        doi_or_url: DOI or direct PDF URL
        output_path: Path to save PDF
    
    Returns:
        Path to downloaded PDF
    
    Raises:
        Exception if PDF cannot be obtained
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # If it's already a URL, try direct download
    if doi_or_url.startswith('http'):
        try:
            response = requests.get(doi_or_url, timeout=30)
            response.raise_for_status()
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return str(output_path)
        except Exception as e:
            print(f"Direct download failed: {e}")
    
    # Try Unpaywall
    doi = doi_or_url.replace('https://doi.org/', '')
    try:
        response = requests.get(
            f"https://api.unpaywall.org/v2/{doi}?email=csnl@snu.ac.kr",
            timeout=30
        )
        data = response.json()
        
        if data.get("is_oa") and data.get("best_oa_location"):
            pdf_url = data["best_oa_location"].get("url_for_pdf")
            if pdf_url:
                response = requests.get(pdf_url, timeout=30)
                response.raise_for_status()
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return str(output_path)
    except Exception as e:
        print(f"Unpaywall lookup failed: {e}")
    
    raise Exception(f"Could not obtain PDF for {doi_or_url}")


# ============================================================================
# CLI
# ============================================================================

def cmd_extract(args):
    """Extract figures and equations from PDF."""
    figures = extract_figures_from_pdf(args.pdf)
    equations = extract_equations_from_pdf(args.pdf)
    
    print(f"Found {len(figures)} figures and {len(equations)} equations")
    
    # Save figures
    saved_paths = []
    for fig in figures:
        path = save_figure_as_png(fig, args.output_dir)
        saved_paths.append(path)
        print(f"Saved: {path} ({fig['width']}x{fig['height']})")
    
    # Output JSON
    output = {
        'figures': [
            {
                'page': f['page'],
                'index': f['index'],
                'width': f['width'],
                'height': f['height'],
            }
            for f in figures
        ],
        'equations': [
            {
                'page': e['page'],
                'text': e['text'][:100],
            }
            for e in equations
        ],
    }
    
    print(json.dumps(output, indent=2))


def cmd_rank(args):
    """Rank figures for members."""
    load_env()
    
    figures = extract_figures_from_pdf(args.pdf)
    members = json.loads(args.members)
    
    ranked = rank_figures_for_members(figures, members)
    
    output = {}
    for member, figs in ranked.items():
        output[member] = figs[:5]  # Top 5
    
    print(json.dumps(output, indent=2))


def cmd_download(args):
    """Download PDF."""
    path = download_pdf(args.doi, args.output)
    print(f"Downloaded: {path}")


def cmd_best(args):
    """Select best visual."""
    load_env()
    
    figures = extract_figures_from_pdf(args.pdf)
    equations = extract_equations_from_pdf(args.pdf)
    members = json.loads(args.members)
    
    result = select_best_visual(figures, members, equations)
    
    print(json.dumps(result, indent=2))


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract and rank figures from PDFs')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # extract
    p_extract = subparsers.add_parser('extract', help='Extract figures and equations')
    p_extract.add_argument('--pdf', required=True, help='PDF file path')
    p_extract.add_argument('--output-dir', required=True, help='Output directory')
    p_extract.set_defaults(func=cmd_extract)
    
    # rank
    p_rank = subparsers.add_parser('rank', help='Rank figures for members')
    p_rank.add_argument('--pdf', required=True, help='PDF file path')
    p_rank.add_argument('--members', required=True, help='JSON string of member descriptions')
    p_rank.set_defaults(func=cmd_rank)
    
    # download
    p_download = subparsers.add_parser('download', help='Download PDF')
    p_download.add_argument('--doi', required=True, help='DOI or URL')
    p_download.add_argument('--output', required=True, help='Output file path')
    p_download.set_defaults(func=cmd_download)
    
    # best
    p_best = subparsers.add_parser('best', help='Select best visual')
    p_best.add_argument('--pdf', required=True, help='PDF file path')
    p_best.add_argument('--members', required=True, help='JSON string of member descriptions')
    p_best.set_defaults(func=cmd_best)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()
