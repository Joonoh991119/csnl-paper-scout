# Relevance Audit Report — 2026-04-02

## Summary

| Metric | Value |
|--------|-------|
| NAS PDFs before audit | 1,060 (pre-session: 932 after manual cleanup) |
| NAS PDFs after audit | **913** |
| Total trashed | **147** (128 manual + 12 Task A + 6 Task A round 2 + 1 Task B) |
| Embeddings | **5,792** |
| False positives restored | **16** (Task A round 2) |

## Task A: Embedding Outlier Detection

### Method
- Computed cosine similarity of each paper to 24 CSNL topic anchor embeddings
- Threshold: cosine < 0.20 → 55 candidates (then 49 after first round)
- 3-judge panel (Qwen3-32B via OpenRouter) for verification

### Results

**Round 1** (with `<think>` tag issue):
- 55 candidates, 6 TRASH (85% ERROR rate due to Qwen3 thinking output)

**Round 2** (with `/no_think` fix):
- 49 candidates, 28 TRASH, 21 KEEP
- Manual review: **16 false positives identified and restored**
- Net true positives: **12 papers correctly trashed**

### False Positive Patterns
LLM judges incorrectly flagged:
- **Neuroscience tools**: Neuropixels, silicon probes, calcium indicators, head fixation
- **Visual science fundamentals**: Cone fundamentals (Wandell), retinotopy
- **PI papers with low-embedding titles**: Short/generic titles by known PIs
- **Methodology papers**: Statistics, experimental design for neuroscience

## Task B: Abstract-Based Screening

### Method
- Extracted abstracts from all 914 remaining PDFs (3 pages, ≤1500 chars)
- Batch LLM screening (40 papers/batch) with 7-category relevance criteria
- Tighter prompt requiring ONLY truly unrelated fields

### Results
- **63 candidates flagged** by LLM screening
- Manual review: **59 false positives**, only **4 true candidates**
- Of those 4: **3 were actually relevant** (Tsodyks PI paper, Ganguli/Yamins PI paper, Kobak methodology)
- Net true positives: **1 paper** (Zhao 2025 memristor hardware)

## Harness Metrics

| Metric | Task A | Task B | Notes |
|--------|--------|--------|-------|
| H1 Precision | 43% (12/28) | 1.6% (1/63) | Task A too aggressive, Task B extremely aggressive |
| H2 Recall | Good | Excellent | Tasks A+B found 13 true irrelevants |
| H3 Judge Agreement | ~85% | N/A (batch) | High agreement but often wrong together |
| H4 False Positive Rate | 57% (16/28) | 98% (62/63) | Manual review essential |

## Key Learnings

1. **LLM judges have very low precision for neuroscience relevance** — they conflate "not directly about VWM/decision-making" with "irrelevant to CSNL"
2. **Neuroscience tools/methods are systematic blind spots** — judges don't understand that Neuropixels papers are core to the field
3. **PI homonym detection works** but generates false positives when the homonym IS the PI (e.g., Surya Ganguli's SGD paper)
4. **`/no_think` is essential for Qwen3** — without it, 85% of responses are unparseable
5. **Embedding-based detection is better than LLM-only** — cosine distance correctly identifies truly distant papers, while LLM judges make more nuanced but less reliable decisions
6. **Manual cleanup (prior session) was more effective** — keyword + title analysis caught 128 papers vs 13 from automated pipeline

## Recommendation
- Use embedding outlier detection as **screening only** (generate candidate list)
- **Never auto-apply** LLM judge decisions
- Present candidates as **manual review checklist** for human operator
- For future runs: tune judge prompt with explicit PI whitelist and tool/method whitelist
