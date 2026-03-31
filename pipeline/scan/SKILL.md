---
name: paper-scout-scan
description: >
  Phase 1 of CSNL Paper Scout: RAG-anchored journal scanning. Uses Zotero semantic search and PI Network
  to find papers in CSNL's intellectual neighborhood — not keyword matching. Triggers on: 'scan journals',
  'find new papers', 'paper scout scan', '논문 스캔', '저널 스캔', 'new papers', 'recent publications',
  '최근 논문', 'journal scan'. Also trigger when user wants to start the paper recommendation pipeline.
---

# Paper Scout — Phase 1: RAG-Anchored Journal Scanning (v3)

Find recent papers that live in CSNL's semantic neighborhood by anchoring searches to the lab's own
publications and tracked PI network — not keyword guessing.

## Why RAG, Not Keywords

CSNL's research sits at niche intersections (e.g., "estimation-only paradigm history effects in absolute vs
relative space"). No keyword query captures this. And when an LLM tries to bridge a vaguely related paper
to CSNL, it hallucinates connections. The solution: use CSNL's own papers as semantic anchors. If a new
paper isn't in our embedding neighborhood, it doesn't pass.

## Prerequisites — Load Before Starting

1. **Zotero `csnl` collection** (key: `CFDCVNMK`): 20+ lab publications as Tier 1 anchors
2. **PI Network data**: `csnl-pi-network/data/pi_network_data.json` — 11 relevance-5 PIs, 22 relevance-4 PIs
3. **Already-read DB**: `csnl-pi-network/data/study_paper_reading_db.json` — 637 papers for dedup
4. **Journal tiers**: `csnl-pi-network/journals.md` — 5-tier priority list
5. **Context bundle**: `../paper-scout/context-bundle.json` — member projects, Slack IDs, categories, `scan_window_days: 90`
6. **Anchor embedding DB**: `paper-scout-anchor-vectors.json` — pre-built embedding vectors from CSNL publications (see Setup section)

## Three-Tier Anchor System

### Tier 1 — CSNL's Own Papers (highest authority)

These are the papers Sang-Hun Lee's lab has published. They define our exact intellectual space.

Load from Zotero:
```
get_collection_items(collectionKey="CFDCVNMK", limit=50)
```

Key anchor papers (by project relevance):
- **Gu et al. (2025, Neuron)** — attractor dynamics, WM bias, drift-diffusion [IMUJVYGB]
- **Lee, Lee, Choe & Lee (2023, J Neurosci)** — boundary updating, repulsive bias [NUCFDV5A]
- **Lee, Lee, Lim, Rhim & Lee (2023, PLoS Bio)** — feedback-as-evidence [FX6HSI8F]
- **Lee, Lim & Lee (2025, iScience)** — granularity, belief updating in DV space [7TTFVY6S]
- **Lim & Lee (2023, Sci Rep)** — serial dependence, relative coordinates [6FSN7R4L]
- **Ryu & Lee (2024, Comms Bio)** — pRF anisotropy, radial/co-axial [KHMDWQBW]
- **Ryu & Lee (2018, Cereb Cortex)** — orientation-specific FC [UNQ8LNA6]
- **Park, Cha & Lee (2013, J Neurosci)** — coaxial CPS [49AEEKDU]

### Tier 2 — Core PI Network (relevance 4-5)

These 33 PIs are CSNL's closest intellectual neighbors. Their recent papers are high-probability hits.

**Relevance 5** (core overlap): Wei, Stocker, Bays, Jehee, Bledowski, Pascucci, Akrami, Schneegans,
Whitney, Luu, Sims

**Relevance 4** (directly applicable): Summerfield, Brody, Kiani, Mante, Shadlen, Pouget, Serences,
Dumoulin, van den Berg, Urai, de Lange, Fritsche, Drugowitsch, Wyart, Kriegeskorte, Sprague, Wang,
Sohn, Husain, Yang, Rademaker, Bae

### Tier 3 — Lab Reading History

637 papers that CSNL members have actually read and shared in `study-paper-reading` channel.
Use as **dedup filter** (don't recommend what's already been read) and **interest signal**
(recurring authors indicate sustained interest).

## Setup: Build Anchor Embedding DB

**One-time initialization** (run before first scan):

1. **Load CSNL papers from Zotero**:
   ```
   get_collection_items(collectionKey="CFDCVNMK", limit=50)
   ```

2. **Embed all CSNL papers**:
   ```
   # Using paper-scout-embed.py utility
   python paper-scout-embed.py build-anchor-db \
     --zotero-collection CFDCVNMK \
     --output paper-scout-anchor-vectors.json
   ```
   This generates a JSON file with structure:
   ```json
   {
     "anchors": [
       {
         "zotero_key": "IMUJVYGB",
         "title": "Gu et al. (2025)",
         "vector": [2048-dim float array],
         "abstract": "..."
       },
       ...
     ]
   }
   ```

3. **Optional: Also embed reading profiles**:
   ```
   python paper-scout-embed.py embed-profiles \
     --profiles researcher_reading_profiles.json \
     --anchor-db paper-scout-anchor-vectors.json
   ```

4. **Update frequency**: Rebuild anchor DB whenever a new CSNL paper is published (low frequency, typically quarterly or after major paper release).

## Scanning Workflow

### Step 0: Calculate Date Window

**3-month rolling window** (configurable):

1. Read `scan_window_days` from context-bundle.json (default: 90)
2. Calculate: `window_start = today - scan_window_days` (in ISO 8601 format: YYYY-MM-DD)
3. Use this window for all external searches:
   - WebSearch queries: append `after:{window_start}` date filter
   - bioRxiv MCP `search_preprints`: use `date_from={window_start}` parameter
   - Journal tracking: focus on articles published in last 90 days

**Example** (if today is 2026-03-31 and scan_window_days=90):
```
window_start = 2025-12-01
WebSearch query: "[PI name]" recent paper "after:2025-12-01"
bioRxiv: search_preprints(date_from="2025-12-01", date_to="2026-03-31", ...)
```

### Step 1: Anchor Expansion via Zotero

For each Tier 1 anchor paper:
```
find_similar(itemKey="[anchor_key]", topK=10, minScore=0.5)
```
This maps CSNL's embedding neighborhood. Collect the results — these define what "relevant" looks like
in vector space.

### Step 2: Semantic Query Generation

From each anchor paper's abstract + matched project context (from enriched-contexts-v3.md), extract
the core intellectual claim — not keywords, but the gist of the contribution.

Example:
- Anchor: Gu et al. 2025 → "drift-diffusion dynamics in working memory cause both stimulus-specific and decision-consistent estimation biases via discrete attractor steering"
- Generated queries: use this gist for `semantic_search` and WebSearch

### Step 3: External Search (Tier 2 PI tracking)

For each relevance 4-5 PI, search for their recent publications:
```
WebSearch: "[PI name]" + recent paper/preprint + "after:{window_start}"
```
Focus on Tier 1-2 journals first (Nature, Neuron, eLife, J Neurosci, etc.), then expand per journals.md.

Also use bioRxiv MCP:
```
search_preprints(
  query="[gist-based query]",
  category="neuroscience",
  date_from="{window_start}",
  date_to="{today}"
)
```

### Step 4: Semantic Validation (the gate)

For every candidate paper found externally, validate its proximity to CSNL's space:
```
semantic_search(query="[candidate abstract text, first 200 words]", topK=3, minScore=0.4)
```

**Gate rule**: A candidate must achieve `minScore >= 0.4` against at least one Zotero item to proceed.
This prevents hallucinated connections — if our embedding space doesn't recognize the paper as nearby,
the LLM's claim of relevance is suspect.

Record the semantic similarity score and nearest anchor for each candidate that passes.

### Step 4b: Embedding-Based Dual Validation (NEW)

After a candidate passes the Zotero semantic gate (Step 4), run an additional embedding validation:

1. **Generate embedding for candidate**:
   ```
   # Using paper-scout-embed.py utility
   candidate_abstract = "[first 300 words of candidate abstract]"
   candidate_vec = embed_text(candidate_abstract)
   ```

2. **Search against anchor DB**:
   ```
   matches = search_vectors(
     candidate_vec,
     anchor_db="paper-scout-anchor-vectors.json",
     top_k=3,
     metric="cosine"
   )
   ```

3. **Require minimum anchor match**:
   ```
   best_cosine = max(match.cosine_sim for match in matches)
   if best_cosine >= 0.45:
       candidate_passes = True
       embedding_cosine = best_cosine
   else:
       candidate_rejected_reason = "Below embed-vl threshold (cosine={:.3f})".format(best_cosine)
   ```

4. **Store embedding for later use**:
   ```
   # Save candidate's embedding vector (2048-dim) for Draft phase figure matching
   candidate_record.embedding_vector = candidate_vec
   candidate_record.embedding_cosine = best_cosine
   ```

**Dual-gate rationale**: The combination of Zotero semantic_search (corpus-aware) + embedding validation (vector-space absolute position) reduces false positives. A paper might locally cluster with CSNL papers but still be outside the neighborhood's absolute embedding sphere.

### Step 5: Dedup Against Reading History

Check each passing candidate against `study_paper_reading_db.json`:
- Match by DOI (exact)
- Match by title (fuzzy, >90% similarity)
- If already read by any lab member → exclude

### Step 6: Metadata Enrichment

For each surviving candidate:
1. Semantic Scholar API via WebFetch: `https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,authors,year,venue,publicationDate,citationCount`
2. Record: title, authors, journal, year, DOI, abstract, citation count, publication date
3. Record: semantic_distance to nearest CSNL anchor, anchor_paper_title
4. **NEW**: Record embedding validation results:
   - `embedding_cosine`: best cosine similarity score from Step 4b
   - `embedding_vector`: candidate's 2048-dimensional vector (for Draft phase)

## Output Format

Save to workspace: `paper-scout-candidates-[YYYY-MM-DD].md`

```markdown
# Paper Scout Candidates — [DATE]

## Scan Summary
- Date window: [window_start] to [today] (scan_window_days: 90)
- Tier 1 anchors used: [N]
- Tier 2 PIs tracked: [N]
- External candidates found: [N]
- Passed semantic gate (≥0.4): [N]
- Passed embedding gate (cosine ≥0.45): [N]
- After dedup: [N] final candidates

## Candidates

### [1] [Paper Title]
- **Authors**: ...
- **Journal**: ... ([Year])
- **DOI**: ...
- **Published**: [Date]
- **Citations**: [N]
- **Abstract**: [Full abstract]
- **Semantic distance**: [score] → nearest anchor: [anchor paper title]
- **Embedding validation**: cosine=0.52 (passed dual gate)
- **Source**: [How found — PI tracking / anchor expansion / bioRxiv / etc.]
- **Potential groups**: [A/B/C based on anchor match]
```

## Handoff

> "스캔 완료: [N]편의 후보 논문 (semantic + embedding gate 통과). `paper-scout-score` 스킬로 value dimension scoring을 진행할까요?"
