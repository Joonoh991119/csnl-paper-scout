# Paper Blitz Style Guide
## Nature/Neuron-Grade Academic Design for Slide Presentations

> **Data-driven**: Automated analysis of **216 figures from 139 papers** across
> Nature, Science, Cell, Neuron, Nat Neurosci, eLife, PNAS, JNeurosci, etc.
> via `style_learner.py` Find-Learn-Review-Record pipeline (28 loop iterations).
>
> Also includes manual analysis of 6 key papers and official journal guidelines.
>
> **Key statistical findings** (n=216 figures):
> - Layout: grid 51% | vertical 15% | horizontal 15% | hybrid 10%
> - Spines: two (top+right removed) 44% | none 33% | all four 24%
> - Panel labels: uppercase bold 58% | none 26% | lowercase bold 15%
> - Whitespace: mean 44% ± 12% (generous margins are the norm)
> - Aesthetic: minimal 54% | rich 45% | cluttered <1%

---

## 1. Design Philosophy

**Core principles:**
1. **Visual > Text** — always
2. **Paper crops > AI generation** — real data figures are always from the paper
3. **Action titles** — every slide title is a complete sentence stating the takeaway
4. **One exhibit per slide** — single chart/diagram per slide
5. **~40 word body limit** per slide

Academic slides that work follow the "billboard test" — if you can't understand
the slide's message in 3 seconds from 10 feet away, it has too much text.

### Figure Priority (STRICT):
1. **Paper figure crop** (from PDF) — for ALL data figures. Always.
2. **Native PPT paradigm diagram** — for experimental procedures (editable shapes)
3. **Native PPT model schematic** — for computational models (editable stages)
4. **AI-generated figure** — ONLY for graphical abstract, paradigm, scenario prediction
5. **NEVER AI-generate data plots** — crop from paper instead

### Anti-patterns (must fix):
- Text-dominant slides with tiny figures
- AI-generated data plots (use paper crops!)
- Gray text (#777777) — kills readability
- Topic titles ("Results") instead of action titles ("Higher uncertainty drives bias")
- Paradigm diagrams that are just labeled boxes with no visual interest

### Target aesthetic:
- **Neuron Figure 1** style: rich but clean, with actual stimulus screenshots
- **Nature Neuroscience** style: minimal, precise, maximal data-ink ratio
- Text exists to label, not to explain — the figure explains itself

---

## 2. Color System

### 2.1 Text Colors (Slide)

| Role | Hex | Usage |
|------|-----|-------|
| Primary text | `#1A1A1A` | Titles, body, all important text |
| Secondary text | `#333333` | Subtitles, captions |
| **FORBIDDEN** | `#777777` and lighter | Never for body text. Period. |
| Figure-only annotation | `#555555` | Axis labels <=10pt inside figures only |
| White | `#FFFFFF` | Background, always |

**Rule**: Body text must have `min(R,G,B) <= 0x55`. Validator enforces this.

### 2.2 Data Palettes

**Primary: NPG (Nature Publishing Group) palette** — used across all Nature journals:

```
Vermillion Red:  #E64B35   ← condition A / attention-grabbing
Cyan:            #4DBBD5   ← condition B / cool/neutral
Teal:            #00A087   ← condition C / positive/correct
Dark Blue:       #3C5488   ← primary accent / emphasis
Salmon:          #F39B7F   ← secondary / error bars / light fill
Slate Blue:      #8491B4   ← tertiary / disabled / reference
```

**Secondary: Okabe-Ito (colorblind-safe)** — for when strict accessibility is needed:

```
Blue:            #0072B2
Orange:          #E69F00
Green:           #009E73
Vermillion:      #D55E00
Sky Blue:        #56B4E9
Purple:          #CC79A7
Yellow:          #F0E442
```

### 2.3 Paradigm Diagram Colors

From observed patterns across all 6 papers:

| Element | Color | Opacity | Notes |
|---------|-------|---------|-------|
| Stimulus screen background | `#F5F5F5` | 100% | Light gray, simulates monitor |
| Active/current epoch | Palette color | 10-15% | Very light tint fill |
| Fixation cross | `#CC0000` | 100% | Red, standard psychophysics |
| Timeline arrow | `#333333` | 100% | Thin, subtle |
| Duration label | `#555555` | 100% | Below/above boxes |
| Box border | `#333333` | 100% | Thin stroke, 0.75-1.0pt |
| Feedback positive | `#009E73` | 100% | Green |
| Feedback negative | `#D55E00` | 100% | Red-orange |

### 2.4 Color Usage Rules (from Nature guidelines)

1. **Never use color for text** — use weight (bold) or size instead
2. **No red-green combinations** — use blue-orange or vermillion-teal
3. **Maximum 3 colors per figure panel** — more = visual noise
4. **Saturated = important, desaturated = background** — visual hierarchy by saturation
5. **Consistent across all slides** — same condition = same color everywhere

---

## 3. Typography

### 3.1 Slide Text

| Element | Font | Size | Weight | Color |
|---------|------|------|--------|-------|
| Slide title | Helvetica Neue / Arial | 28-36pt | Bold | `#1A1A1A` |
| Body text | Helvetica Neue / Arial | 16-18pt | Regular | `#1A1A1A` |
| Body minimum | — | 14pt | — | Hard floor, validator enforced |
| Bullet sub-text | — | 14-16pt | Regular | `#333333` |
| Figure caption | — | 12-14pt | Regular | `#333333` |
| Slide number | — | 10pt | Regular | `#999999` (exception: tiny UI) |

**Line spacing**: 1.35x for body text.

### 3.2 Figure-Internal Text (matplotlib, placed on slides)

Key insight: figures generated at large sizes (14-18" wide) get scaled down to
~9-10" on slides. Font sizes must compensate.

| Element | matplotlib pt | Effective on slide | Notes |
|---------|-------------|-------------------|-------|
| Panel title | 24-28pt | ~14-17pt | Bold |
| Axis label | 20-22pt | ~12-13pt | Regular |
| Tick label | 18-20pt | ~11-12pt | Regular |
| Annotation | 18pt | ~11pt | Regular |
| Legend | 18pt | ~11pt | Regular |
| Panel label (A,B,C) | 24pt | ~14pt | **Bold** |

**Scale factor**: For `figsize=(14, h)` placed at 10" on slide: `effective = mpl_pt * (10/14) ≈ 0.71x`

### 3.3 Panel Label Convention

| Journal | Style | Example |
|---------|-------|---------|
| Nature / Nat Neurosci | Bold lowercase, 8pt at print | **a**, **b**, **c** |
| Neuron / Cell Press | Bold uppercase, 7pt at print | **A**, **B**, **C** |

For Paper Blitz slides: use **bold uppercase** (A, B, C) — more readable at projection size.

---

## 4. Paradigm Diagram Design

### 4.1 Layout Patterns (from paper analysis)

**Pattern 1: Screen Sequence (most common)**
Used by: Jazayeri & Shadlen 2010, Sheahan et al. 2021, Gu et al. 2025

```
┌─────┐   ┌─────┐   ┌─────┐   ┌─────┐
│  +  │──▶│ ○ ○ │──▶│     │──▶│  ↻  │
│ Fix │   │Stim │   │Delay│   │Resp │
└─────┘   └─────┘   └─────┘   └─────┘
          500ms      1-2s      until
────────────────────────────────────────▶ Time
```

Key features:
- Show actual stimulus as simple icon/screenshot inside box
- Duration labels BELOW boxes (not inside)
- Thin arrows between boxes
- Timeline arrow at very bottom
- **NOT forced horizontal** — can wrap or use 2 rows for complex designs

**Pattern 2: Nested/Hierarchical (for multi-phase experiments)**
Used by: Flesch et al. 2022, Sheahan et al. 2021 (block structure)

```
┌─ Block 1 (Low range) ──────────────────────┐
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐  ...  (120 trials)│
│  │ T │ │ F │ │ T │ │ F │                    │
│  └───┘ └───┘ └───┘ └───┘                    │
└──────────────────────────────────────────────┘
┌─ Block 2 (High range) ─────────────────────┐
│  ...                                        │
└─────────────────────────────────────────────┘
```

**Pattern 3: Conceptual → Data hybrid**
Used by: Gu et al. 2025 (graphical abstract), Steel et al. 2024

Left side: conceptual schematic (brain, model)
Right side: concrete task display + timeline
Bottom: behavioral data panels

### 4.2 Visual Elements (what makes figures look "Nature-grade")

1. **Stimulus screenshots** — Show what the subject actually sees. Even simplified versions
   (circle + fixation) are better than text labels like "Stimulus presented".

2. **Icons over text** — Brain icon > "fMRI". Eye icon > "Visual stimulus".
   Screen icon > "Display". Clock icon > "Delay period".

3. **Minimal text inside diagram** — Only labels (1-2 words) and durations.
   Explanation goes in figure caption, NOT in the figure.

4. **Consistent box sizes** — All epoch boxes same height. Width can vary to suggest
   relative duration (but don't be too literal).

5. **Thin lines** — All borders/arrows: 0.75-1.0pt. Never thick outlines.
   Data lines in plots: 1.5-2.0pt. Axes: 0.6-1.0pt.

6. **White space** — Generous spacing between elements. Cramped = amateur.

7. **No drop shadows, no gradients, no 3D effects** — Flat design only.

8. **Corner radius** — Subtle rounded corners (2-4pt at print, ~6-8pt for slides)
   for stimulus boxes. Sharp corners for data panels/axes.

### 4.3 Arrow Styles

| Type | Style | Usage |
|------|-------|-------|
| Temporal flow | `->`, thin (0.8pt), `#333333` | Between epoch boxes |
| Timeline | `->`, medium (1.5pt), `#AAAAAA` | Bottom of diagram, "Time" label |
| Causal/model | `->`, thin (0.8pt), `#333333` | Model diagrams |
| Dashed | `--▶`, thin, `#999999` | Optional/variable paths |
| Bidirectional | `<->`, thin, `#333333` | Feedback loops |

---

## 5. Slide Layout

### 5.1 Dimensions

16:9 widescreen: 13.333" x 7.5"

### 5.2 Content Zones

```
┌──────────────────────────────────────────────────┐
│ ▐ Title (28-36pt bold)                           │ 0.2" - 0.9"
│──────────────────────────────────────────────────│
│                                                  │
│   ┌──────────────────────┐  ┌────────────────┐   │
│   │                      │  │                │   │
│   │   PRIMARY FIGURE     │  │  SECONDARY     │   │
│   │   (60-70% width)     │  │  (data/model)  │   │
│   │                      │  │                │   │
│   └──────────────────────┘  └────────────────┘   │
│                                                  │
│   ● Key point 1 (16pt)                           │
│   ● Key point 2 (16pt)                           │ bottom 15%
└──────────────────────────────────────────────────┘
  0.5"                                        0.5"
  margin                                      margin
```

### 5.3 Figure-to-Text Ratio

**Target**: 60-70% figure, 20-30% text, 10-15% whitespace

| Slide type | Figure area | Text area |
|-----------|------------|-----------|
| Paradigm/Methods | 70% | 30% (title + 1-2 bullets) |
| Results | 65% | 35% (title + key finding) |
| Model/Theory | 55% | 45% (title + equation + explanation) |
| Title slide | 40% | 60% |

### 5.4 Text Density Rules

- **Maximum 3 bullet points** per slide
- **Maximum 15 words** per bullet
- **No full sentences** in bullets — fragments preferred
- **One key message** per slide

---

## 6. Figure Generation (matplotlib)

### 6.1 rcParams

```python
MATPLOTLIB_STYLE = {
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica Neue', 'Helvetica'],
    'font.size': 20,
    'axes.labelsize': 20,
    'axes.titlesize': 24,
    'xtick.labelsize': 18,
    'ytick.labelsize': 18,
    'legend.fontsize': 18,
    'axes.linewidth': 1.0,
    'grid.linewidth': 0.5,
    'lines.linewidth': 2.0,
    'lines.markersize': 6,
    'xtick.direction': 'out',
    'ytick.direction': 'out',
    'xtick.major.size': 5,
    'xtick.major.width': 1.0,
    'ytick.major.size': 5,
    'ytick.major.width': 1.0,
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.15,
    'pdf.fonttype': 42,       # TrueType — required by Nature
    'axes.spines.top': False,
    'axes.spines.right': False,
}
```

### 6.2 Nature-Style Data Plot Conventions

From the analyzed papers:

- **Remove top and right spines** (always)
- **Tick marks outward** (always)
- **No gridlines** (unless explicitly needed for readability)
- **Error bars**: SEM, thin lines (0.8pt), same color as data with alpha
- **Individual data points**: small dots (alpha=0.3-0.5), jittered
- **Group means**: large markers or thick lines
- **Significance stars**: `*`, `**`, `***` above bracket lines, NOT p-values in the plot

---

## 7. Graphical Abstract Conventions

From Gu et al. 2025 and Cell Press guidelines:

- **Square format**: 1200x1200px at 300dpi
- **Grid layout**: 2x2 or 2x3 panels
- **Visual flow**: Left→right (process) or top→bottom (hierarchy)
- **Font**: Arial, 12-16pt minimum
- **Content**: New findings ONLY, no speculative content
- **Biological context**: Must include (brain region, species, task)
- **Max ~7 elements** (cognitive load limit)
- **Simplified plots**: No tick marks, minimal axis labels
- **Icons**: Flat style, consistent line weight, monochrome or 2-color

---

## 8. Validation Checklist (automated by validate_slide.py)

### Hard constraints (violation = must fix):
- [ ] No body text lighter than `#555555`
- [ ] No body text smaller than 14pt
- [ ] No title text smaller than 24pt
- [ ] No text overlap
- [ ] No text hidden behind figures
- [ ] Figure aspect ratio preserved (±8%)
- [ ] All elements within slide bounds
- [ ] Generated figure text ≥ 7pt effective on slide

### Soft guidelines (warning):
- [ ] ≤ 3 bullet points per slide
- [ ] Figure occupies ≥ 50% of content area
- [ ] ≤ 3 accent colors per slide
- [ ] Paradigm diagram has visual elements (not text-only boxes)
- [ ] Duration labels present for temporal paradigms

---

## 9. Reference Papers (Zotero library)

| Paper | Journal | Key Design Feature |
|-------|---------|-------------------|
| Jazayeri & Shadlen 2010 | Nat Neurosci | 3D perspective trial sequence, model diagram with Gaussian distributions |
| Steel et al. 2024 | Nat Neurosci | Clean fMRI paradigm schematic, brain surface colormaps |
| Fischer & Whitney 2014 | Nat Neurosci | Minimal psychophysics paradigm, Gabor stimuli |
| Sheahan et al. 2021 | Neuron | Perspective card sequence, color-coded contexts, range bars |
| Flesch et al. 2022 | Neuron | 2D stimulus space with naturalistic images, context frames |
| Gu et al. 2025 | Neuron | Graphical abstract 2x3 grid, paradigm with actual screen mockups |

---

## 10. Quick Reference: What Changed from Old Style

| Parameter | Old | New | Reason |
|-----------|-----|-----|--------|
| Secondary text color | `#777777` | `#333333` | #777 fails WCAG contrast |
| Paradigm layout | Horizontal only | Flexible (H/V/nested) | Papers use varied layouts |
| Box fill | Solid light blue tints | White + thin border | Matches Nature style |
| Data palette | Okabe-Ito only | NPG primary + OI fallback | NPG is what Nature actually uses |
| Paradigm content | Text labels in boxes | Stimulus icons/screenshots | All top papers show stimuli |
| Figure-text min | Not tracked | 7pt effective (validated) | Nature print minimum |
| Spines | All 4 visible | Top+right removed | Universal in analyzed papers |
| Panel labels | Not standardized | Bold uppercase A,B,C | Readable at projection size |
| Text density | Unlimited | Max 3 bullets, 15 words each | Cognitive load research |
