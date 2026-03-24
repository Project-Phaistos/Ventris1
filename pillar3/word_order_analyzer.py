"""Word order discovery from multi-word inscriptions.

PRD Section 5.3: Assign word classes to every word in every multi-word
inscription, build a class precedence matrix, compute direction ratios,
and test for significant ordering patterns via binomial tests.

Also computes mean relative position per word class to identify which
classes tend to appear in initial vs. final position.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import binomtest

from .data_loader import (
    CorpusInscription,
    GrammarInputData,
    Pillar2Data,
)
from .profile_builder import _stem_key_for_word
from .word_class_inducer import WordClassResult


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PairwiseOrder:
    """Directional ordering evidence for a pair of word classes.

    PRD Section 5.3 (step 3): direction_ratio = P[i,j] / max(P[j,i], 1)
    with binomial test for significance.
    """
    class_a: int
    class_b: int
    a_before_b_count: int
    b_before_a_count: int
    direction_ratio: float
    p_value: float


@dataclass
class ClassPositionStats:
    """Positional statistics for a word class within inscriptions.

    PRD Section 5.3 (step 5): mean relative position per class.
    """
    class_id: int
    mean_relative_position: float
    std_relative_position: float
    n_observations: int


@dataclass
class WordOrderResult:
    """Result of word order analysis.

    PRD Section 5.3: Pairwise class precedence, direction ratios,
    significance tests, and per-class positional profiles.

    Attributes:
        precedence_matrix: Raw counts P[i,j] = class i before class j.
        pairwise_orders: Pairwise direction ratios and significance.
        position_stats: Per-class mean relative position.
        n_classes: Number of word classes.
        n_inscriptions_used: Inscriptions contributing to analysis.
        n_bigrams_analyzed: Total class bigrams analyzed.
    """
    precedence_matrix: np.ndarray
    pairwise_orders: List[PairwiseOrder]
    position_stats: List[ClassPositionStats]
    n_classes: int
    n_inscriptions_used: int = 0
    n_bigrams_analyzed: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "min_words_per_inscription": 3,  # Minimum words for word-order evidence
    "min_pair_count": 3,             # Minimum observations for a class pair
    "alpha": 0.05,                   # Significance level for binomial test
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _assign_word_class(
    word_sign_ids: List[str],
    pillar2: Pillar2Data,
    word_classes: WordClassResult,
) -> Optional[int]:
    """Look up the word class for a word via its Pillar 2 stem.

    Returns None if the stem is not in the word class assignments.
    """
    word_key = tuple(word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is None:
        # Fallback: treat whole word as stem
        stem = word_key
    return word_classes.assignments.get(stem)


def _build_precedence_matrix(
    inscriptions: List[CorpusInscription],
    pillar2: Pillar2Data,
    word_classes: WordClassResult,
    n_classes: int,
    min_words: int,
) -> Tuple[np.ndarray, int, int]:
    """Build the class x class precedence matrix P.

    PRD Section 5.3 (step 2): P[i,j] = count of word-class-i immediately
    preceding word-class-j across all inscriptions.

    Args:
        inscriptions: Corpus inscriptions.
        pillar2: Pillar 2 data for stem lookup.
        word_classes: Induced word class assignments.
        n_classes: Number of word classes.
        min_words: Minimum words per inscription to include.

    Returns:
        (precedence_matrix, n_inscriptions_used, n_bigrams)
    """
    P = np.zeros((n_classes, n_classes), dtype=np.int64)
    n_inscriptions = 0
    n_bigrams = 0

    for insc in inscriptions:
        if len(insc.words) < min_words:
            continue

        # Assign word classes to all words in this inscription
        assigned: List[Optional[int]] = []
        for word in insc.words:
            cid = _assign_word_class(word.word_sign_ids, pillar2, word_classes)
            assigned.append(cid)

        used = False
        for i in range(len(assigned) - 1):
            ci = assigned[i]
            cj = assigned[i + 1]
            if ci is not None and cj is not None:
                P[ci, cj] += 1
                n_bigrams += 1
                used = True

        if used:
            n_inscriptions += 1

    return P, n_inscriptions, n_bigrams


def _compute_pairwise_orders(
    P: np.ndarray,
    n_classes: int,
    min_pair_count: int,
    alpha: float,
) -> List[PairwiseOrder]:
    """Compute direction ratios and binomial tests for all class pairs.

    PRD Section 5.3 (step 3):
    direction_ratio(i,j) = P[i,j] / max(P[j,i], 1)

    Binomial test: under H0 P(i before j) = 0.5,
    test k = P[i,j] out of n = P[i,j] + P[j,i].
    """
    orders: List[PairwiseOrder] = []

    for i in range(n_classes):
        for j in range(i + 1, n_classes):
            a_before_b = int(P[i, j])
            b_before_a = int(P[j, i])
            total = a_before_b + b_before_a

            if total < min_pair_count:
                continue

            direction_ratio = a_before_b / max(b_before_a, 1)

            # Two-sided binomial test
            result = binomtest(a_before_b, total, 0.5, alternative="two-sided")
            p_value = result.pvalue

            orders.append(PairwiseOrder(
                class_a=i,
                class_b=j,
                a_before_b_count=a_before_b,
                b_before_a_count=b_before_a,
                direction_ratio=round(direction_ratio, 3),
                p_value=p_value,
            ))

    return orders


def _compute_position_stats(
    inscriptions: List[CorpusInscription],
    pillar2: Pillar2Data,
    word_classes: WordClassResult,
    n_classes: int,
) -> List[ClassPositionStats]:
    """Compute mean relative position per word class.

    PRD Section 5.3 (step 5): For each word class, compute the mean
    relative position (0 = first, 1 = last).
    """
    positions: Dict[int, List[float]] = defaultdict(list)

    for insc in inscriptions:
        for word in insc.words:
            cid = _assign_word_class(word.word_sign_ids, pillar2, word_classes)
            if cid is not None:
                positions[cid].append(word.relative_position)

    stats: List[ClassPositionStats] = []
    for cid in range(n_classes):
        pos_list = positions.get(cid, [])
        if pos_list:
            arr = np.array(pos_list)
            stats.append(ClassPositionStats(
                class_id=cid,
                mean_relative_position=float(np.mean(arr)),
                std_relative_position=float(np.std(arr)),
                n_observations=len(pos_list),
            ))
        else:
            stats.append(ClassPositionStats(
                class_id=cid,
                mean_relative_position=0.5,
                std_relative_position=0.0,
                n_observations=0,
            ))

    return stats


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_word_order(
    data: GrammarInputData,
    word_classes: WordClassResult,
    config: Optional[Dict[str, Any]] = None,
) -> WordOrderResult:
    """Discover word order patterns from multi-word inscriptions.

    PRD Section 5.3: Builds the class precedence matrix, computes
    direction ratios with binomial significance tests, and analyzes
    per-class positional profiles.

    Args:
        data: Combined grammar input data.
        word_classes: Induced word class assignments from word_class_inducer.
        config: Optional configuration overrides.

    Returns:
        WordOrderResult with precedence matrix, pairwise orders,
        and positional statistics.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    min_words = cfg["min_words_per_inscription"]
    min_pair = cfg["min_pair_count"]
    alpha = cfg["alpha"]

    n_classes = word_classes.n_classes
    pillar2 = data.pillar2
    inscriptions = data.inscriptions

    # Build precedence matrix
    P, n_insc, n_bigrams = _build_precedence_matrix(
        inscriptions, pillar2, word_classes, n_classes, min_words
    )

    # Pairwise direction ratios + significance
    pairwise = _compute_pairwise_orders(P, n_classes, min_pair, alpha)

    # Per-class positional statistics
    pos_stats = _compute_position_stats(
        inscriptions, pillar2, word_classes, n_classes
    )

    return WordOrderResult(
        precedence_matrix=P,
        pairwise_orders=pairwise,
        position_stats=pos_stats,
        n_classes=n_classes,
        n_inscriptions_used=n_insc,
        n_bigrams_analyzed=n_bigrams,
    )
