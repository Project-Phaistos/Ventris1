"""Distributional profile builder for Pillar 3 (Grammar).

PRD Section 5.1: For each stem in the Pillar 2 segmented lexicon, compute
a distributional profile combining:
- Left/right context stems (PPMI-weighted)
- Positional features (relative_position, is_initial, is_final, is_pre_numeral)
- Morphological features (n_attested_suffixes, paradigm_class_id, word_class_hint)
- Inscription type features (tablet_rate, libation_rate, other_rate)

The output is a stem x feature matrix suitable for SVD and clustering
in word_class_inducer.py.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .data_loader import (
    CorpusInscription,
    CorpusWord,
    GrammarInputData,
    Pillar2Data,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProfileMatrix:
    """Distributional profile matrix for stems.

    PRD Section 5.1: The feature matrix rows correspond to stems,
    columns to distributional features (context PPMI scores, positional
    features, morphological features, inscription-type features).

    Attributes:
        stems: Ordered list of stem tuples (row identifiers).
        feature_matrix: 2D numpy array, shape (n_stems, n_features).
        feature_names: Ordered list of feature name strings (column identifiers).
        stem_frequencies: Total corpus frequency per stem.
        stem_index: Mapping from stem tuple to row index.
    """
    stems: List[Tuple[str, ...]]
    feature_matrix: np.ndarray
    feature_names: List[str]
    stem_frequencies: Dict[Tuple[str, ...], int] = field(default_factory=dict)
    stem_index: Dict[Tuple[str, ...], int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "min_stem_frequency": 2,       # Minimum corpus frequency to include a stem
    "top_k_contexts": 20,          # Top-k context stems by PMI per side
    "ppmi_smoothing": 0.75,        # Context distribution smoothing exponent
    "word_class_encoding": {       # Encode Pillar 2 word_class_hint as int
        "declining": 1,
        "uninflected": 0,
        "unknown": 2,
    },
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _stem_key_for_word(
    word: CorpusWord,
    pillar2: Pillar2Data,
) -> Optional[Tuple[str, ...]]:
    """Look up the Pillar 2 stem for a corpus word.

    Falls back to the full word_sign_ids as the stem if no Pillar 2
    segmentation exists (treating the whole word as an unsegmented stem).
    """
    word_key = tuple(word.word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is not None:
        return stem
    # Fallback: use the full word as the stem
    return word_key


def _build_context_pairs(
    inscriptions: List[CorpusInscription],
    pillar2: Pillar2Data,
    min_words: int = 2,
) -> Tuple[
    List[Tuple[Tuple[str, ...], str, Tuple[str, ...]]],
    Counter,
    Counter,
]:
    """Extract (stem, side, context_stem) triples from the corpus.

    For each word in each multi-word inscription, record:
    - Left context: stem of the preceding word (or ("<BOS>",))
    - Right context: stem of the following word (or ("<EOS>",))

    Args:
        inscriptions: Corpus inscriptions.
        pillar2: Pillar 2 data for stem lookup.
        min_words: Minimum words per inscription to include.

    Returns:
        (context_triples, stem_counts, context_counts)
        where context_triples is a list of (stem, side, context_stem),
        stem_counts maps stem -> total occurrences,
        context_counts maps (side, context_stem) -> total occurrences.
    """
    BOS: Tuple[str, ...] = ("<BOS>",)
    EOS: Tuple[str, ...] = ("<EOS>",)

    triples: List[Tuple[Tuple[str, ...], str, Tuple[str, ...]]] = []
    stem_counts: Counter = Counter()
    context_counts: Counter = Counter()

    for insc in inscriptions:
        if len(insc.words) < min_words:
            continue

        word_stems = [
            _stem_key_for_word(w, pillar2) for w in insc.words
        ]

        for i, stem in enumerate(word_stems):
            if stem is None:
                continue

            stem_counts[stem] += 1

            # Left context
            if i == 0:
                left = BOS
            else:
                left = word_stems[i - 1]
                if left is None:
                    left = BOS
            triples.append((stem, "L", left))
            context_counts[("L", left)] += 1

            # Right context
            if i == len(word_stems) - 1:
                right = EOS
            else:
                right = word_stems[i + 1]
                if right is None:
                    right = EOS
            triples.append((stem, "R", right))
            context_counts[("R", right)] += 1

    return triples, stem_counts, context_counts


def _compute_ppmi_matrix(
    triples: List[Tuple[Tuple[str, ...], str, Tuple[str, ...]]],
    stem_counts: Counter,
    context_counts: Counter,
    stems_ordered: List[Tuple[str, ...]],
    top_k: int = 20,
    alpha: float = 0.75,
) -> Tuple[np.ndarray, List[str]]:
    """Compute Positive PMI feature vectors for stems.

    PRD Section 5.1 (Mathematical basis):
    PMI(stem_s, context_c) = log2(P(s,c) / (P(s) * P(c)))
    PPMI = max(0, PMI)

    We select the top-k contexts per side (L, R) by their PMI with at
    least one stem, then build a dense matrix.

    Args:
        triples: (stem, side, context_stem) triples.
        stem_counts: Stem frequency counter.
        context_counts: (side, context_stem) frequency counter.
        stems_ordered: Ordered list of stems to include.
        top_k: Number of top context features per side.
        alpha: Smoothing exponent for context distribution.

    Returns:
        (ppmi_matrix, feature_names) where ppmi_matrix has shape
        (len(stems_ordered), n_context_features).
    """
    if not triples:
        return np.zeros((len(stems_ordered), 0)), []

    stem_set = set(stems_ordered)
    stem_idx = {s: i for i, s in enumerate(stems_ordered)}

    # Co-occurrence counts: (stem, side, context) -> count
    cooc: Counter = Counter()
    for stem, side, ctx in triples:
        if stem in stem_set:
            cooc[(stem, side, ctx)] += 1

    total_pairs = len(triples)
    total_stems_sum = sum(stem_counts[s] for s in stem_set)

    # Smoothed context distribution: P_alpha(c) = count(c)^alpha / sum(count(c')^alpha)
    context_keys = list(context_counts.keys())
    smoothed_context = {}
    denom = sum(context_counts[c] ** alpha for c in context_keys)
    if denom > 0:
        for c in context_keys:
            smoothed_context[c] = (context_counts[c] ** alpha) / denom
    else:
        for c in context_keys:
            smoothed_context[c] = 1.0 / max(len(context_keys), 1)

    # Compute PMI for all (stem, context) pairs
    pmi_values: Dict[Tuple[Tuple[str, ...], str, Tuple[str, ...]], float] = {}
    for (stem, side, ctx), count in cooc.items():
        # P(s, c) = cooc / total_pairs
        p_sc = count / total_pairs
        # P(s) = stem_count / total_stems_sum  (marginal over included stems)
        p_s = stem_counts[stem] / total_stems_sum if total_stems_sum > 0 else 1e-10
        # P(c) = smoothed context probability
        p_c = smoothed_context.get((side, ctx), 1e-10)

        if p_s > 0 and p_c > 0:
            pmi = math.log2(p_sc / (p_s * p_c)) if p_sc > 0 else 0.0
            pmi_values[(stem, side, ctx)] = max(0.0, pmi)  # PPMI

    # Select top-k contexts per side by max PMI across stems
    context_max_pmi: Dict[Tuple[str, Tuple[str, ...]], float] = defaultdict(float)
    for (stem, side, ctx), pmi in pmi_values.items():
        key = (side, ctx)
        if pmi > context_max_pmi[key]:
            context_max_pmi[key] = pmi

    # Top k for each side
    left_contexts = sorted(
        [(ctx, pmi) for (side, ctx), pmi in context_max_pmi.items() if side == "L"],
        key=lambda x: -x[1],
    )[:top_k]
    right_contexts = sorted(
        [(ctx, pmi) for (side, ctx), pmi in context_max_pmi.items() if side == "R"],
        key=lambda x: -x[1],
    )[:top_k]

    # Build feature names and matrix
    feature_names: List[str] = []
    selected_contexts: List[Tuple[str, Tuple[str, ...]]] = []

    for ctx, _ in left_contexts:
        name = f"L:{'-'.join(ctx)}"
        feature_names.append(name)
        selected_contexts.append(("L", ctx))

    for ctx, _ in right_contexts:
        name = f"R:{'-'.join(ctx)}"
        feature_names.append(name)
        selected_contexts.append(("R", ctx))

    n_features = len(selected_contexts)
    ppmi_matrix = np.zeros((len(stems_ordered), n_features), dtype=np.float64)

    for j, (side, ctx) in enumerate(selected_contexts):
        for i, stem in enumerate(stems_ordered):
            ppmi_matrix[i, j] = pmi_values.get((stem, side, ctx), 0.0)

    return ppmi_matrix, feature_names


def _build_positional_features(
    inscriptions: List[CorpusInscription],
    pillar2: Pillar2Data,
    stems_ordered: List[Tuple[str, ...]],
) -> Tuple[np.ndarray, List[str]]:
    """Compute positional feature vectors for stems.

    PRD Section 5.1c: relative_position, is_initial, is_final, is_pre_numeral
    are aggregated as means across all occurrences of each stem.

    Returns:
        (feature_matrix, feature_names) with shape (n_stems, 4).
    """
    stem_idx = {s: i for i, s in enumerate(stems_ordered)}
    n = len(stems_ordered)

    # Accumulators: [rel_position_sum, initial_count, final_count, pre_numeral_count]
    accum = np.zeros((n, 4), dtype=np.float64)
    counts = np.zeros(n, dtype=np.float64)

    for insc in inscriptions:
        for word in insc.words:
            stem = _stem_key_for_word(word, pillar2)
            if stem is None or stem not in stem_idx:
                continue
            idx = stem_idx[stem]
            counts[idx] += 1
            accum[idx, 0] += word.relative_position
            accum[idx, 1] += 1.0 if word.is_initial else 0.0
            accum[idx, 2] += 1.0 if word.is_final else 0.0
            accum[idx, 3] += 1.0 if word.has_numeral_after else 0.0

    # Normalize to means
    safe_counts = np.maximum(counts, 1.0)
    features = accum / safe_counts[:, np.newaxis]

    feature_names = [
        "pos:relative_position",
        "pos:is_initial",
        "pos:is_final",
        "pos:is_pre_numeral",
    ]
    return features, feature_names


def _build_morphological_features(
    pillar2: Pillar2Data,
    stems_ordered: List[Tuple[str, ...]],
    word_class_encoding: Dict[str, int],
) -> Tuple[np.ndarray, List[str]]:
    """Compute morphological feature vectors for stems.

    PRD Section 5.1d:
    - n_attested_suffixes: how many different suffixes this stem takes
    - paradigm_class_id: paradigm class index (or -1 if none)
    - word_class_hint: declining=1, uninflected=0, unknown=2

    Returns:
        (feature_matrix, feature_names) with shape (n_stems, 3).
    """
    n = len(stems_ordered)
    features = np.zeros((n, 3), dtype=np.float64)

    for i, stem in enumerate(stems_ordered):
        # n_attested_suffixes
        suf_list = pillar2.stem_to_suffixes.get(stem, [])
        features[i, 0] = len(suf_list)

        # paradigm_class_id (use -1 if no paradigm)
        pc_id = pillar2.stem_to_paradigm_class.get(stem, -1)
        features[i, 1] = pc_id

        # word_class_hint encoded as int
        wc_label = pillar2.stem_to_word_class.get(stem, "unknown")
        features[i, 2] = word_class_encoding.get(wc_label, 2)

    feature_names = [
        "morph:n_attested_suffixes",
        "morph:paradigm_class_id",
        "morph:word_class_hint",
    ]
    return features, feature_names


def _build_inscription_type_features(
    inscriptions: List[CorpusInscription],
    pillar2: Pillar2Data,
    stems_ordered: List[Tuple[str, ...]],
) -> Tuple[np.ndarray, List[str]]:
    """Compute inscription-type feature vectors for stems.

    PRD Section 5.1e: fraction of occurrences on Tablets, libation
    tables/vessels, and other types.

    Returns:
        (feature_matrix, feature_names) with shape (n_stems, 3).
    """
    stem_idx = {s: i for i, s in enumerate(stems_ordered)}
    n = len(stems_ordered)

    tablet_count = np.zeros(n, dtype=np.float64)
    libation_count = np.zeros(n, dtype=np.float64)
    other_count = np.zeros(n, dtype=np.float64)
    total_count = np.zeros(n, dtype=np.float64)

    for insc in inscriptions:
        itype = insc.inscription_type.lower()
        for word in insc.words:
            stem = _stem_key_for_word(word, pillar2)
            if stem is None or stem not in stem_idx:
                continue
            idx = stem_idx[stem]
            total_count[idx] += 1
            if "tablet" in itype:
                tablet_count[idx] += 1
            elif "libation" in itype:
                libation_count[idx] += 1
            else:
                other_count[idx] += 1

    safe_total = np.maximum(total_count, 1.0)
    features = np.column_stack([
        tablet_count / safe_total,
        libation_count / safe_total,
        other_count / safe_total,
    ])

    feature_names = [
        "type:tablet_rate",
        "type:libation_rate",
        "type:other_rate",
    ]
    return features, feature_names


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_profiles(
    data: GrammarInputData,
    config: Optional[Dict[str, Any]] = None,
) -> ProfileMatrix:
    """Build distributional profiles for all eligible stems.

    PRD Section 5.1: Aggregates context PPMI, positional, morphological,
    and inscription-type features into a single stem x feature matrix.

    Args:
        data: Combined grammar input data (Pillar 1, 2, corpus).
        config: Optional overrides for default configuration.

    Returns:
        ProfileMatrix with the feature matrix, stem list, and feature names.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    min_freq = cfg["min_stem_frequency"]
    top_k = cfg["top_k_contexts"]
    alpha = cfg["ppmi_smoothing"]
    wc_encoding = cfg["word_class_encoding"]

    pillar2 = data.pillar2
    inscriptions = data.inscriptions

    # --- Step 1: Count stem frequencies across corpus ---
    stem_freq: Counter = Counter()
    for insc in inscriptions:
        for word in insc.words:
            stem = _stem_key_for_word(word, pillar2)
            if stem is not None:
                stem_freq[stem] += 1

    # Filter to stems with sufficient frequency
    eligible_stems = [
        stem for stem, count in stem_freq.items() if count >= min_freq
    ]
    # Sort for determinism
    eligible_stems.sort(key=lambda s: (-stem_freq[s], s))

    if not eligible_stems:
        return ProfileMatrix(
            stems=[],
            feature_matrix=np.zeros((0, 0)),
            feature_names=[],
            stem_frequencies={},
            stem_index={},
        )

    # --- Step 2: Build context pairs and PPMI ---
    triples, stem_counts, context_counts = _build_context_pairs(
        inscriptions, pillar2, min_words=2
    )
    ppmi_mat, ppmi_names = _compute_ppmi_matrix(
        triples, stem_counts, context_counts,
        eligible_stems, top_k=top_k, alpha=alpha,
    )

    # --- Step 3: Positional features ---
    pos_mat, pos_names = _build_positional_features(
        inscriptions, pillar2, eligible_stems
    )

    # --- Step 4: Morphological features ---
    morph_mat, morph_names = _build_morphological_features(
        pillar2, eligible_stems, wc_encoding
    )

    # --- Step 5: Inscription-type features ---
    type_mat, type_names = _build_inscription_type_features(
        inscriptions, pillar2, eligible_stems
    )

    # --- Step 6: Concatenate all features ---
    feature_matrix = np.hstack([ppmi_mat, pos_mat, morph_mat, type_mat])
    feature_names = ppmi_names + pos_names + morph_names + type_names

    stem_index = {s: i for i, s in enumerate(eligible_stems)}

    return ProfileMatrix(
        stems=eligible_stems,
        feature_matrix=feature_matrix,
        feature_names=feature_names,
        stem_frequencies=dict(stem_freq),
        stem_index=stem_index,
    )
