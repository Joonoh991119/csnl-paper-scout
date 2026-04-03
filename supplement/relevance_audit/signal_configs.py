"""Signal configurations for Relevance Verification v2.
Keyword lexicon, score mappings, PI DB, journal scores, known homonyms.
"""

# ═══════════════════════════════════════════════════
#  S1: EMBEDDING SIMILARITY SCORE MAPPING
# ═══════════════════════════════════════════════════

def s1_score(max_cosine):
    """Convert max anchor cosine similarity to 0-25 score."""
    if max_cosine >= 0.55: return 25
    if max_cosine >= 0.45: return 20
    if max_cosine >= 0.35: return 15
    if max_cosine >= 0.25: return 10
    if max_cosine >= 0.20: return 5
    return 0


# ═══════════════════════════════════════════════════
#  S2: PI AUTHORSHIP — known homonym pairs
# ═══════════════════════════════════════════════════

# PI last names that have known homonyms in non-neuroscience fields.
# When these names match AND embedding sim is low, trigger Verifier A.
KNOWN_HOMONYMS = {
    'ganguli':     {'neuro': 'Surya Ganguli (Stanford, neural dynamics/theory)',
                    'other': ['geology/geophysics', 'oncology/cell biology', 'economics', 'copper smelting']},
    'burr':        {'neuro': 'David C. Burr (Florence, visual perception)',
                    'other': ['planetary geology (Martian dunes)']},
    'jazayeri':    {'neuro': 'Mehrdad Jazayeri (MIT, timing/motor neuroscience)',
                    'other': ['education/psychology pedagogy']},
    'heathcote':   {'neuro': 'Andrew Heathcote (Amsterdam, RT modeling/Bayesian stats)',
                    'other': ['philosophy of mathematics (Adrian Heathcote)']},
    'urai':        {'neuro': 'Anne E. Urai (Leiden, decision-making/history effects)',
                    'other': ['environmental chemistry/freshwater ecology']},
    'mur':         {'neuro': 'Marieke Mur (W. Ontario, neural representations/RSA)',
                    'other': ['liquid crystal physics']},
    'sahani':      {'neuro': 'Maneesh Sahani (UCL/Gatsby, neural data analysis)',
                    'other': ['hematology/malaria']},
    'sims':        {'neuro': 'Chris Sims (Stony Brook, efficient coding/WM)',
                    'other': ['energy economics/electric grid']},
    'schneegans':  {'neuro': 'Sebastian Schneegans (Birmingham, WM binding models)',
                    'other': ['sustainable development policy']},
    'husain':      {'neuro': 'Masud Husain (Oxford, attention/motivation/neuropsych)',
                    'other': ['supply chain management', 'Islamic studies']},
    'eger':        {'neuro': 'Evelyn Eger (NeuroSpin, numerosity/fMRI)',
                    'other': ['microbiology (Klebsiella)', 'business/service industry']},
    'weiner':      {'neuro': 'Kevin Weiner (Stanford, visual cortex/face areas)',
                    'other': ['phage therapy/microbiology']},
    'ashby':       {'neuro': 'F. Gregory Ashby (UCSB, categorization/basal ganglia)',
                    'other': ['orthopedics/bone biomechanics']},
}

# Common last names that match PIs but are extremely frequent worldwide.
# These get reduced S2 score unless embedding also supports relevance.
COMMON_SURNAMES = {
    'wang', 'li', 'liu', 'chen', 'yang', 'zhang', 'kim', 'lee', 'park',
    'yu', 'wu', 'lin', 'brown', 'allen', 'martin', 'cohen', 'murphy',
    'harris', 'beck', 'dan', 'wei', 'luu', 'ji', 'berg', 'norman',
    'hong', 'ryu', 'sohn', 'bae', 'chung',
}

def s2_score(author_lower, pi_lastnames_set, max_cosine):
    """Score PI authorship (0-25). Returns (score, needs_homonym_check)."""
    if author_lower not in pi_lastnames_set:
        return 0, False

    is_known_homonym = author_lower in KNOWN_HOMONYMS
    is_common_name = author_lower in COMMON_SURNAMES

    # Common surname + low embedding → very likely different person
    if is_common_name and max_cosine < 0.20:
        return 0, False  # too common, too distant → no credit
    if is_common_name and max_cosine < 0.30:
        return 5, True   # might be PI, needs homonym check
    if is_known_homonym and max_cosine < 0.25:
        return 5, True   # known homonym risk, needs check

    # Strong embedding support → likely the actual PI
    if max_cosine >= 0.30:
        return 25, False  # PI + embedding match = strong signal
    return 15, is_known_homonym or is_common_name


# ═══════════════════════════════════════════════════
#  S3: KEYWORD MATCH — 3-tier lexicon
# ═══════════════════════════════════════════════════

KEYWORDS_TIER1 = [  # 3 pts each — CSNL core topics
    'working memory', 'serial dependence', 'history effect', 'attractor dynamics',
    'drift-diffusion', 'drift diffusion', 'evidence accumulation', 'bayesian observer',
    'population receptive field', 'prf', 'retinotopy', 'retinotopic',
    'orientation tuning', 'orientation selectivity', 'fmri decoding', 'iem',
    'inverted encoding', 'dpca', 'demixed principal component', 'rsa',
    'representational similarity', 'efficient coding', 'metacognition',
    'type-2 sensitivity', 'confidence judgment', 'visual crowding',
    'ensemble perception', 'numerosity', 'approximate number',
    'serial position', 'primacy', 'recency', 'contraction bias',
    'boundary updating', 'categorical boundary', 'granularity',
    'belief updating', 'decision variable', 'choice history',
    'repulsive bias', 'attractive bias', 'adaptation aftereffect',
]

KEYWORDS_TIER2 = [  # 2 pts each — neuroscience methods/tools
    'psychophysics', 'psychophysical', 'fmri', 'bold', 'eeg',
    'meg', 'eye tracking', 'eye-tracking', 'pupillometry', 'saccade',
    'microsaccade', 'fixation', 'tdcs', 'tes', 'transcranial',
    '7t', '7 tesla', 'rnn', 'recurrent neural network',
    'neuropixels', 'neuropixel', 'calcium imaging', 'spike sorting',
    'silicon probe', 'electrophysiology', 'multivariate pattern',
    'voxel', 'cortical layer', 'laminar', 'connectome',
    'population coding', 'neural manifold', 'latent dynamics',
    'two-photon', 'optogenetics', 'optogenetic',
    'head-fixed', 'head fixation', 'patch clamp',
    'crossnobis', 'rdm', 'dissimilarity matrix',
]

KEYWORDS_TIER3 = [  # 1 pt each — broader cognitive/neuro
    'perception', 'perceptual', 'decision making', 'decision-making',
    'visual', 'auditory', 'neural', 'neuron', 'neuronal',
    'cortex', 'cortical', 'hippocampus', 'hippocampal',
    'prefrontal', 'parietal', 'temporal lobe', 'thalamus',
    'basal ganglia', 'striatum', 'cerebellum', 'amygdala',
    'attention', 'attentional', 'memory', 'learning', 'adaptation',
    'bias', 'prior', 'posterior', 'likelihood', 'inference',
    'stimulus', 'response', 'encoding', 'decoding',
    'brain', 'cognitive', 'cognition', 'behavior', 'behaviour',
    'reinforcement learning', 'reward', 'dopamine',
    'motor control', 'sensorimotor', 'motor planning',
    'oscillation', 'alpha', 'beta', 'gamma', 'theta',
    'plasticity', 'synaptic', 'noise', 'variability',
    'object recognition', 'face', 'scene', 'motion',
    'contrast', 'luminance', 'color', 'spatial frequency',
    'normalization', 'gain control', 'divisive',
    'prediction error', 'surprise', 'expectation',
    'deep neural network', 'cnn', 'convolutional',
    'primate', 'monkey', 'macaque', 'rodent', 'mouse',
]

def s3_score(abstract_lower):
    """Score keyword match (0-15) from abstract text."""
    score = 0
    for kw in KEYWORDS_TIER1:
        if kw in abstract_lower:
            score += 3
    for kw in KEYWORDS_TIER2:
        if kw in abstract_lower:
            score += 2
    for kw in KEYWORDS_TIER3:
        if kw in abstract_lower:
            score += 1
    return min(15, score)


# ═══════════════════════════════════════════════════
#  S4: PROJECT MATCH — gist embeddings (precomputed)
# ═══════════════════════════════════════════════════

# Project descriptions: expanded per-member with seed paper context.
# Each entry is long enough to produce a meaningful embedding centroid.
PROJECT_GISTS = {
    'JOP_RingRepSca': (
        "Serial dependence history effect in orientation estimation task. "
        "Relative vs absolute coordinate system independence. Object-centered representation. "
        "Feedforward repulsion vs feedback attraction dissociation. "
        "Estimation-only paradigm without decision commitment. BMBU boundary updating model."
    ),
    'JOP_GranRDT': (
        "Granularity effect in decision variable space. Decision commitment narrows belief range. "
        "Higher granularity attracts future choices more strongly. "
        "Six cost functions compared with hierarchical MCMC. Feedback-as-evidence model."
    ),
    'JOP_Time': (
        "Duration estimation with BMBU structure matching orientation domain. "
        "History effects in temporal perception. MCMC fitting of Bayesian models."
    ),
    'MSY_CatVsMag': (
        "Categorical vs magnitude task on face gender spectrum produces different serial dependence. "
        "X-shape SD pattern in categorical task. Choice repetition and gambler's fallacy. "
        "StyleGAN2 face morphing stimuli. Hierarchical Bayesian generative model."
    ),
    'BYL_BayesianObserver': (
        "Bayesian observer models for visual working memory inference. "
        "Contraction bias and systematic estimation bias in VWM. "
        "Efficient coding framework explaining resource allocation and bias. "
        "Prior distributions and likelihood functions in psychophysics. "
        "Reference: Adler & Ma, Zamboni et al., Wei & Stocker efficient coding."
    ),
    'JYK_RNN': (
        "Recurrent neural network models of working memory bias. "
        "Stimulus-specific bias and decision-consistent bias from drift-diffusion dynamics. "
        "Extending Gu et al. 2025 Neuron. Persistent vs sequential coding spectrum. "
        "Non-normal recurrent connectivity. PCA state space analysis. "
        "Attractor dynamics and ring attractor networks in prefrontal cortex."
    ),
    'MJC_SeqVWM': (
        "Sequential visual working memory. Low contrast stimulus produces attraction bias, "
        "high contrast produces repulsion. SOB model energy field with primacy gradient "
        "and response suppression. Kilpatrick attractor model for sequential encoding. "
        "Serial position effects in working memory."
    ),
    'SK_WMRepresentation': (
        "Sensory and mnemonic orientation signals in early visual cortex EVC form ring-like manifold "
        "but re-embedded in nearly orthogonal population subspace. Geometry-preserving subspace rotation. "
        "7T fMRI with 16.5s prolonged delay. dPCA, crossnobis RDM, inverted encoding model IEM. "
        "Retinotopically decoupled mnemonic manifold. N=50 participants. "
        "Reference: Kim et al. 2026 under review."
    ),
    'SK_Grant': (
        "Layer-specific 7T fMRI dissecting feedforward repulsion vs feedback attraction. "
        "dPCA manifold separation between sensory and memory codes. "
        "Individual-tailored tES transcranial electrical stimulation."
    ),
    'JHR_SpatialExtent': (
        "Population receptive field pRF anisotropy across visual hierarchy V1-V4. "
        "EVC radiality dominant, perception co-axiality dominant. "
        "Individual differences shared across measures. Oriented grating pRF. "
        "Reference: Ryu & Lee 2024 Communications Biology."
    ),
    'JHR_FC': (
        "Tuning similarity overrides spatial distance in functional connectivity V1-V4. "
        "Feature-specific resting-state FC. Radial to co-axial hierarchical transformation. "
        "CNN retina model interpretation. Reference: Ryu & Lee 2018 Cerebral Cortex."
    ),
    'SMJ_Concentricity': (
        "Co-circularity as higher-order natural image statistic. "
        "Saccadic eye movements targeting concentric structure. "
        "Image memory task with eye-tracking. Saliency-based segmentation."
    ),
    'JSL_SerialDep_Spatial': (
        "Serial dependence in relative object-centered coordinates, not absolute space. "
        "Same-relative-location attraction 4.14° vs different 2.66°. "
        "Identity-based view of history effects. Higher associative cortex parietal LOT. "
        "Reference: Lim & Lee 2023 Scientific Reports."
    ),
    'JSL_Attraction': (
        "Comparative judgment asymmetry: decision target shows attraction, reference does not. "
        "Task-relevant item selection determines history effect direction."
    ),
    'BHL_WM_Binding': (
        "Feature binding in visual working memory. Joint representation of features. "
        "Multi-object context information supporting serial dependence. "
        "Sensory decoding mechanisms for bound features. "
        "Reference: Li et al. 2021 Neuron, Fischer et al. 2020."
    ),
    'lab_methods': (
        "Model-based fMRI analysis. Task-optimized recurrent neural networks. "
        "Psychophysics orientation estimation delayed reproduction. "
        "Pupillometry pupil dilation arousal. tDCS tES transcranial stimulation. "
        "7T fMRI layer-specific laminar imaging. dPCA demixed PCA. "
        "IEM inverted encoding model. RSA representational similarity analysis. "
        "Crossnobis distance RDM. Population receptive field mapping. "
        "Bayesian hierarchical modeling MCMC Stan. Meta-analysis methods."
    ),
}

def s4_score(best_project_cosine):
    """Score project-level match (0-15)."""
    if best_project_cosine >= 0.50: return 15
    if best_project_cosine >= 0.40: return 10
    if best_project_cosine >= 0.30: return 5
    return 0


# ═══════════════════════════════════════════════════
#  S5: READING DB AUTHOR OVERLAP
# ═══════════════════════════════════════════════════

def s5_score(author_count_in_db, author_lower='', max_cosine=0.0):
    """Score based on how often this author appears in relevance DB.
    Discounted for common surnames with low embedding similarity."""
    if author_count_in_db == 0:
        return 0
    # Common name + low embedding → discount heavily
    if author_lower in COMMON_SURNAMES and max_cosine < 0.25:
        return min(2, author_count_in_db)  # max 2 pts for common names
    if author_count_in_db >= 5: return 10
    if author_count_in_db >= 3: return 7
    if author_count_in_db >= 1: return 4
    return 0


# ═══════════════════════════════════════════════════
#  S6: JOURNAL RELEVANCE
# ═══════════════════════════════════════════════════

JOURNAL_SCORES = {
    # Tier 1: top neuro/science journals
    'nature': 10, 'science': 10, 'nature neuroscience': 10, 'neuron': 10,
    'nature human behaviour': 10, 'cell': 8,
    # Tier 2: strong neuro
    'elife': 8, 'current biology': 8, 'pnas': 8,
    'journal of neuroscience': 8, 'plos computational biology': 8,
    'cerebral cortex': 7, 'neuroimage': 7,
    'nature communications': 7, 'science advances': 7,
    # Tier 3: specialized/methods
    'journal of vision': 6, 'cognition': 6,
    'psychological review': 6, 'neural computation': 6,
    'psychonomic bulletin & review': 6, 'psychonomic bulletin and review': 6,
    'psychological science': 6, 'trends in cognitive sciences': 6,
    'trends in neurosciences': 6, 'journal of neurophysiology': 5,
    'cortex': 5, 'vision research': 5,
    'attention, perception, & psychophysics': 5,
    'journal of experimental psychology': 5,
    'nature methods': 5, 'journal of cognitive neuroscience': 5,
    # Tier 4: preprints (relevant but unreviewed)
    'biorxiv': 4, 'arxiv': 3, 'psyarxiv': 4, 'medrxiv': 3,
    # Tier 5: broader
    'frontiers in neuroscience': 3, 'frontiers in psychology': 3,
    'plos one': 2, 'scientific reports': 2,
}

def s6_score(journal_name_lower):
    """Score journal relevance (0-10)."""
    if not journal_name_lower:
        return 0
    for jname, score in JOURNAL_SCORES.items():
        if jname in journal_name_lower:
            return score
    return 0


# ═══════════════════════════════════════════════════
#  TIER THRESHOLDS (calibrated via harness)
# ═══════════════════════════════════════════════════

TIER_THRESHOLDS = {
    'auto_keep':    45,   # composite >= 45 → no review needed
    'likely_keep':  25,   # 25-44 → quick human skim
    'review':       15,   # 15-24 → human reviews abstract
    'likely_trash':  7,   # 7-14 → LLM verifier confirms
    'auto_trash':    0,   # 0-6 → truly alien fields only
}

def assign_tier(composite):
    """Assign tier based on composite score."""
    if composite >= TIER_THRESHOLDS['auto_keep']:    return 'auto_keep'
    if composite >= TIER_THRESHOLDS['likely_keep']:   return 'likely_keep'
    if composite >= TIER_THRESHOLDS['review']:        return 'review'
    if composite >= TIER_THRESHOLDS['likely_trash']:  return 'likely_trash'
    return 'auto_trash'
