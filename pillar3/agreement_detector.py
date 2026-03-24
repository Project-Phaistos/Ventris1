"""Agreement pattern detection for adjacent word pairs.

PRD Section 5.4: Discover if adjacent words share morphological features
(case/number/gender agreement) by checking whether their suffixes from
the Pillar 2 segmented lexicon match.

Algorithm:
1. For adjacent word pairs, check if their suffixes match exactly.
2. Group by word class pair.
3. For each class pair with enough data, test same_suffix_rate > expected_rate.
4. expected_rate = sum over all suffixes of P(suffix)^2 (chance match probability).
5. Binomial test with Bonferroni correction.
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
class AgreementPattern:
    """A detected agreement pattern between two word classes.

    PRD Section 5.4: If a class-pair (A, B) shows significantly elevated
    suffix agreement, this suggests they share a grammatical category.

    Attributes:
        word_pair_classes: Tuple of (class_a, class_b).
        shared_suffix_rate: Observed rate of suffix match when adjacent.
        expected_by_chance: Expected rate under random suffix assignment.
        p_value: Binomial test p-value (Bonferroni corrected).
        p_value_raw: Uncorrected p-value.
        n_adjacent_pairs: Number of adjacent pairs observed.
        n_same_suffix: Number with matching suffix.
        interpretation: Human-readable interpretation.
    """
    word_pair_classes: Tuple[int, int]
    shared_suffix_rate: float
    expected_by_chance: float
    p_value: float
    p_value_raw: float
    n_adjacent_pairs: int
    n_same_suffix: int
    interpretation: str


@dataclass
class AgreementResult:
    """Result of agreement pattern detection.

    Attributes:
        patterns: List of detected agreement patterns (significant ones).
        all_pair_stats: Statistics for all class pairs tested.
        expected_rate: Corpus-wide expected suffix match rate by chance.
        n_pairs_tested: Number of class pairs tested.
        n_pairs_significant: Number of significant agreement patterns.
    """
    patterns: List[AgreementPattern]
    all_pair_stats: List[AgreementPattern]
    expected_rate: float
    n_pairs_tested: int = 0
    n_pairs_significant: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "min_adjacent_pairs": 5,  # Minimum adjacent pairs to test a class pair
    "alpha": 0.05,            # Significance level (before Bonferroni)
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_suffixes_for_word(
    word_sign_ids: List[str],
    pillar2: Pillar2Data,
) -> Optional[Tuple[str, ...]]:
    """Get the first (primary) suffix for a word from Pillar 2.

    Returns None if the word has no suffix or is not in the lexicon.
    """
    word_key = tuple(word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is None:
        return None

    # Look up the word entry to get its specific suffixes
    for entry in pillar2.segmented_lexicon:
        if tuple(entry.word_sign_ids) == word_key:
            if entry.suffixes:
                # Return the first suffix as a tuple for comparison
                return tuple(entry.suffixes[0])
            return None

    return None


def _compute_expected_rate(
    suffix_counts: Counter,
) -> float:
    """Compute the expected suffix match rate by chance.

    PRD Section 5.4: expected_rate = sum over all suffixes of P(suffix)^2.

    This is the probability that two independently drawn suffixes match.
    """
    total = sum(suffix_counts.values())
    if total == 0:
        return 0.0

    expected = 0.0
    for count in suffix_counts.values():
        p = count / total
        expected += p * p

    return expected


def _assign_word_class(
    word_sign_ids: List[str],
    pillar2: Pillar2Data,
    word_classes: WordClassResult,
) -> Optional[int]:
    """Look up the word class for a word."""
    word_key = tuple(word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is None:
        stem = word_key
    return word_classes.assignments.get(stem)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_agreement(
    data: GrammarInputData,
    word_classes: WordClassResult,
    config: Optional[Dict[str, Any]] = None,
) -> AgreementResult:
    """Detect agreement patterns between adjacent word pairs.

    PRD Section 5.4: For each pair of adjacent words in the corpus,
    check whether their suffixes match. Group by word class pair and
    test whether the match rate exceeds chance expectation.

    Args:
        data: Combined grammar input data.
        word_classes: Induced word class assignments.
        config: Optional configuration overrides.

    Returns:
        AgreementResult with significant patterns and diagnostics.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    min_pairs = cfg["min_adjacent_pairs"]
    alpha = cfg["alpha"]

    pillar2 = data.pillar2
    inscriptions = data.inscriptions

    # --- Step 1: Compute corpus-wide suffix frequency distribution ---
    suffix_counts: Counter = Counter()
    for insc in inscriptions:
        for word in insc.words:
            suf = _get_suffixes_for_word(word.word_sign_ids, pillar2)
            if suf is not None:
                suffix_counts[suf] += 1

    expected_rate = _compute_expected_rate(suffix_counts)

    # --- Step 2: Collect adjacent pair statistics ---
    # For each (class_i, class_j) pair, count adjacencies and suffix matches
    pair_adjacent: Counter = Counter()
    pair_same_suffix: Counter = Counter()

    for insc in inscriptions:
        words = insc.words
        for i in range(len(words) - 1):
            w1 = words[i]
            w2 = words[i + 1]

            c1 = _assign_word_class(w1.word_sign_ids, pillar2, word_classes)
            c2 = _assign_word_class(w2.word_sign_ids, pillar2, word_classes)

            if c1 is None or c2 is None:
                continue

            suf1 = _get_suffixes_for_word(w1.word_sign_ids, pillar2)
            suf2 = _get_suffixes_for_word(w2.word_sign_ids, pillar2)

            if suf1 is None or suf2 is None:
                continue

            # Use ordered pair (smaller class first for symmetry)
            pair_key = (min(c1, c2), max(c1, c2))
            pair_adjacent[pair_key] += 1

            if suf1 == suf2:
                pair_same_suffix[pair_key] += 1

    # --- Step 3: Statistical testing ---
    n_tests = sum(1 for k, v in pair_adjacent.items() if v >= min_pairs)
    bonferroni = max(n_tests, 1)

    all_stats: List[AgreementPattern] = []
    significant: List[AgreementPattern] = []

    for pair_key, n_adj in pair_adjacent.items():
        if n_adj < min_pairs:
            continue

        n_same = pair_same_suffix.get(pair_key, 0)
        rate = n_same / n_adj if n_adj > 0 else 0.0

        # Binomial test: is rate > expected_rate?
        if expected_rate < 1.0 and n_adj > 0:
            result = binomtest(
                n_same, n_adj, expected_rate, alternative="greater"
            )
            p_raw = result.pvalue
        else:
            p_raw = 1.0

        p_corrected = min(p_raw * bonferroni, 1.0)

        # Interpretation
        c1, c2 = pair_key
        if c1 == c2:
            interp = (
                f"Words of class {c1} show suffix agreement when adjacent "
                f"(rate={rate:.2f} vs expected={expected_rate:.2f}) — "
                f"possible coordination or apposition"
            )
        else:
            interp = (
                f"Words of class {c1} and class {c2} tend to share suffixes "
                f"when adjacent (rate={rate:.2f} vs expected={expected_rate:.2f}) — "
                f"possible agreement (e.g., noun-adjective)"
            )

        pattern = AgreementPattern(
            word_pair_classes=pair_key,
            shared_suffix_rate=round(rate, 4),
            expected_by_chance=round(expected_rate, 4),
            p_value=p_corrected,
            p_value_raw=p_raw,
            n_adjacent_pairs=n_adj,
            n_same_suffix=n_same,
            interpretation=interp,
        )

        all_stats.append(pattern)
        if p_corrected < alpha:
            significant.append(pattern)

    # Sort significant patterns by p-value
    significant.sort(key=lambda p: p.p_value)
    all_stats.sort(key=lambda p: p.p_value)

    return AgreementResult(
        patterns=significant,
        all_pair_stats=all_stats,
        expected_rate=round(expected_rate, 4),
        n_pairs_tested=n_tests,
        n_pairs_significant=len(significant),
    )
