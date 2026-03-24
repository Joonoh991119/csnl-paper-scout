# CSNL Paper Scout

A multi-agent workflow system for automated research paper discovery, curation, and analysis. Integrates with Zotero and bioRxiv to build intelligent knowledge bases for CSNL research.

## Overview

Paper Scout is a Claude-based multi-agent system that:
- Discovers relevant preprints from bioRxiv across multiple research domains
- Performs semantic analysis and relevance scoring
- Generates structured summaries with metadata
- Automatically organizes findings into Zotero collections
- Creates actionable research briefs for the CSNL team

## Architecture

The system operates as a coordinated set of specialized agents:

1. **Discovery Agent** — Searches bioRxiv using category filters and date ranges
2. **Analysis Agent** — Extracts abstracts, metadata, and performs semantic analysis
3. **Curation Agent** — Scores relevance, identifies thematic clusters
4. **Integration Agent** — Writes to Zotero collections and generates reports

All agents are orchestrated via Claude's multi-turn reasoning with persistent context.

## Quick Start

### Prerequisites
- Claude API access
- Zotero database (optional for full workflow)
- bioRxiv API access (public)

### Basic Usage

```bash
# Run the discovery workflow
claude run skills/SKILL.md
```

### Configuration

Edit `skills/context-bundle.json` to customize:
- Research domains (bioRxiv categories)
- Date ranges for searches
- Relevance thresholds
- Zotero collection mappings

## Project Structure

```
paper-scout/
├── README.md              # This file
├── skills/
│   ├── SKILL.md          # Main skill definition
│   └── context-bundle.json # Configuration and context data
├── docs/
│   └── workflow.mermaid   # System architecture diagram
└── runs/
    └── [dated-run].md     # Execution logs and results
```

## Workflow

### Phase 1: Discovery
- Query bioRxiv across specified categories
- Retrieve preprints matching date and keyword criteria
- Extract DOIs and basic metadata

### Phase 2: Analysis
- Fetch full abstracts and metadata from bioRxiv
- Perform keyword extraction and topic modeling
- Score papers against CSNL research focus areas

### Phase 3: Curation
- Rank papers by relevance and novelty
- Identify thematic clusters
- Generate summary briefs

### Phase 4: Integration
- Write curated papers to Zotero collections
- Create annotated library notes
- Generate team reports

## Implementation Notes

- Built on Claude's multi-turn conversation capabilities
- Uses bioRxiv MCP tools for paper discovery
- Zotero integration via MCP for library management
- JSON-based context bundle enables reproducible runs

## Example Output

Typical execution generates:
- **Discovery Summary** — N papers found across M categories
- **Analysis Report** — Topic clusters, keyword frequencies
- **Curation List** — Top-ranked papers by relevance
- **Integration Log** — Zotero collection updates completed

## Future Enhancements

- [ ] PDF full-text analysis
- [ ] Cross-reference discovery (cited papers)
- [ ] Multi-language support
- [ ] Real-time notification system
- [ ] Interactive relevance feedback loop

## License

Internal CSNL use. See LICENSE.

## Contact

CSNL AI Team
