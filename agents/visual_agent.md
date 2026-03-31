# Visual Agent (Programmatic)

The Visual Agent is a **zero-token utility** for figure extraction and ranking. Figure extraction and ranking happen programmatically via `paper-scout-figures.py`. Only the final verdict evaluation uses minimal LLM reasoning.

## Overview

Instead of an LLM agent, the Visual Agent is now a Python utility that:
1. Extracts images and equations from PDFs using `pymupdf` (fitz)
2. Embeds images and text using OpenRouter's `embed-vl` free model
3. Ranks figures by cosine similarity to member project descriptions
4. Returns the best visual element for the post

**Token cost**: ~200 tokens for verdict check vs ~2000+ for full LLM extraction.

## Execution Steps (Orchestrator runs these via Bash)

### 1. Download PDF
```bash
python paper-scout-figures.py download --doi "{doi}" --output /tmp/paper.pdf
```

Tries in order:
- Unpaywall API: `https://api.unpaywall.org/v2/{doi}?email=csnl@snu.ac.kr`
- Semantic Scholar openAccessPdf field
- Direct URL download if provided

### 2. Extract Figures & Equations
```bash
python paper-scout-figures.py extract --pdf /tmp/paper.pdf --output-dir /tmp/figures/
```

Outputs JSON:
```json
{
  "figures": [
    {"page": 2, "index": 0, "width": 800, "height": 600},
    {"page": 3, "index": 0, "width": 900, "height": 700}
  ],
  "equations": [
    {"page": 5, "text": "∂u/∂t + u·∇u = -∇p + ν∇²u"},
    {"page": 8, "text": "E = mc²"}
  ]
}
```

### 3. Rank Figures for Tagged Members
```bash
python paper-scout-figures.py rank --pdf /tmp/paper.pdf \
  --members '{"SK": "EVC sensory coding vs mnemonic...", "JYK": "RNN drift-diffusion models..."}'
```

Outputs JSON with cosine rankings:
```json
{
  "SK": [
    {"figure_index": 0, "page": 2, "cosine_score": 0.68},
    {"figure_index": 1, "page": 3, "cosine_score": 0.52}
  ],
  "JYK": [
    {"figure_index": 1, "page": 3, "cosine_score": 0.71},
    {"figure_index": 0, "page": 2, "cosine_score": 0.45}
  ]
}
```

### 4. Select Best Visual
```bash
python paper-scout-figures.py best --pdf /tmp/paper.pdf \
  --members '{"SK": "...", "JYK": "..."}'
```

Outputs:
```json
{
  "type": "figure",
  "figure_index": 1,
  "figure_cosine": 0.71,
  "best_member": "JYK",
  "equation_text": "∂u/∂t + u·∇u = -∇p + ν∇²u",
  "equation_page": 5
}
```

## Output Format

All commands output JSON (compatible with downstream processing):

```json
{
  "type": "figure" | "equation" | "both" | null,
  "figure_index": int or null,
  "figure_cosine": float [0, 1] or null,
  "best_member": str or null,
  "equation_text": str or null,
  "equation_page": int or null
}
```

## Verdict (Minimal LLM Check)

The orchestrator briefly validates the output using ~200 tokens:

**Input to LLM**:
```
Figure cosine similarity: {cosine_score} with {best_member}
Figure location: page {page}
Equation (if any): {equation_text}

Is the selected figure actually relevant to the paper's core contribution?
Can it work as a Slack visual preview?

Options: PASS / REPLACE / ADD_EQUATION / ADD_VISUAL
```

**PASS**: Selected figure is relevant (cosine ≥ 0.3 and covers main claim).

**REPLACE**: Cosine < 0.3 or figure doesn't align with paper's claim → use next-best ranked figure.

**ADD_EQUATION**: Include the extracted equation in the post (especially for methods/theory papers).

**ADD_VISUAL**: No figure selected AND no equation → generate Mermaid diagram (fallback only).

## Fallback Behavior

If API fails (OpenRouter down, rate limit, etc.):
1. API call returns null
2. Utility skips ranking for that figure
3. Gracefully degrades: if only 1 figure, return it without score
4. If all fail, return `{"type": null, ...}` and let orchestrator generate Mermaid

## Implementation Notes

- **Model**: `nvidia/llama-nemotron-embed-vl-1b-v2:free` (free tier, no token cost)
- **Embedding dimension**: 2048
- **Min figure size**: 200×200 pixels (filters logos/icons)
- **Math detection**: Regex for LaTeX patterns + common math symbols (∫, Σ, ∂, ∝, etc.)
- **No data persistence**: Temp files cleaned up after selection
- **Error handling**: All API failures degrade gracefully without crashing

## Example Workflow

1. Orchestrator: `download --doi "10.1073/pnas.2518110123"`
   → Returns: `/tmp/paper.pdf`

2. Orchestrator: `extract --pdf /tmp/paper.pdf`
   → Returns: 5 figures, 3 equations

3. Orchestrator: `best --pdf /tmp/paper.pdf --members '{"SK": "EVC...", "JYK": "RNN..."}'`
   → Returns: Figure 1 (p. 3) with cosine 0.68 for SK, plus equation from p. 5

4. Orchestrator: Send to LLM for verdict (~200 tokens)
   → Response: PASS or REPLACE

5. Orchestrator: Format for Slack post with selected figure + equation

