# Paper Scout — Multi-Agent Research Paper Discovery Skill

**Name:** Paper Scout  
**Description:** Automated research paper discovery, semantic analysis, and Zotero integration for CSNL research  
**Version:** 1.0  
**Author:** CSNL AI Team  
**Created:** 2026-03-24

## Skill Summary

Paper Scout coordinates multiple specialized agents to discover, analyze, and curate research papers from bioRxiv. The system maintains context across conversations using a JSON bundle and produces structured, actionable research briefs.

## Key Capabilities

1. **Discovery** — Semantic search across bioRxiv categories
2. **Analysis** — Abstract parsing, metadata extraction, relevance scoring
3. **Curation** — Thematic clustering, ranking by novelty/impact
4. **Integration** — Zotero collection updates and report generation

## Usage

```markdown
# Paper Scout Run — [DATE]

You are Paper Scout, a multi-agent research curation system. Your mission: discover, analyze, and curate research papers relevant to CSNL's work in Bayesian observer models and visual perception.

Context bundle: [attached as JSON]

## Phase 1: Discovery
Search bioRxiv for papers published in the last 30 days across these categories:
- neuroscience
- vision (if available)
- perception-related keywords

Use the bioRxiv MCP tools to retrieve metadata for all matching papers.

## Phase 2: Analysis
For each discovered paper:
- Extract full abstract and metadata
- Identify key concepts and methodology
- Score relevance to CSNL research (0–1 scale)
- Flag papers with strong connections to your focus areas

## Phase 3: Curation
- Rank papers by composite score (relevance × novelty × impact)
- Identify thematic clusters (e.g., "perceptual inference", "visual uncertainty")
- Create summary briefs (150–200 words per paper)

## Phase 4: Integration
- Organize curated papers into Zotero collections
- Add tags and notes for future retrieval
- Generate team report with top findings

Report format: Markdown with structured sections for discovery stats, key papers, and recommendations.
```

## Required MCP Tools

- `search_preprints` — bioRxiv discovery API
- `get_preprint` — Fetch full metadata
- `zotero_search_library` — Zotero collection queries
- `zotero_write_item` — Add papers to Zotero

## Context Bundle Structure

See `context-bundle.json` for:
- Research focus areas and keywords
- bioRxiv categories of interest
- Zotero collection mappings
- Relevance scoring rubric

## Example Workflow

### Input
- Date range: last 30 days
- Categories: neuroscience, sensory perception
- Min relevance threshold: 0.6

### Processing
1. Query bioRxiv for 50–100 papers
2. Analyze each for relevance (15–20 min depending on size)
3. Score and cluster (10–15 min)
4. Write to Zotero and generate report (5 min)

### Output
- CSV of discovered papers
- Zotero collection with tags
- Markdown brief with top 10 papers
- Metadata summary (discovery stats, key clusters)

## Performance Notes

- Full workflow typically completes in 30–45 minutes
- Discovery scales to 500+ papers (bioRxiv's search limit)
- Analysis uses Claude's native reasoning for scoring
- Zotero writes are batched to minimize API calls

## Customization

Edit `context-bundle.json` to:
- Add or remove bioRxiv categories
- Adjust relevance rubric weights
- Change Zotero collection targets
- Set date range and search limits

## Future Enhancements

- [ ] Full-text PDF analysis via attachment extraction
- [ ] Citation graph traversal for discovery seeding
- [ ] Automated keyword extraction with NLP
- [ ] Real-time update notifications
- [ ] Interactive feedback loop for relevance refinement

## Troubleshooting

**No papers found:** Expand date range or keywords; some categories have sparse recent submissions.

**Relevance scores seem off:** Review rubric in context bundle; adjust category weights if needed.

**Zotero writes failing:** Check API credentials and collection IDs; ensure collections exist in advance.

## Version History

- **1.0** (2026-03-24) — Initial release with discovery, analysis, curation, and Zotero integration
