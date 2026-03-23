"""Dead vowel convention test.

Implements PRD Section 5.7: tests whether consecutive signs within a word
share the same vowel class more often than expected by chance.

In Linear B, the "dead vowel" convention means that when a consonant cluster
CC occurs, it is spelled as CV1-CV2 where V1 is a "dead" (unpronounced) copy
of V2. This creates an excess of same-vowel consecutive pairs.

Mathematical basis:
    Under the null hypothesis (no dead vowel convention), the probability that
    two consecutive signs share the same vowel class is approximately 1/V,
    where V is the number of vowel classes.

    Under the alternative (dead vowel convention exists), consecutive signs
    share the same vowel class at rate > 1/V.

    Test: one-sided binomial test for same_vowel_rate > 1/V.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple

import numpy as np
from scipy import stats as sp_stats

from .grid_constructor import GridResult
from .corpus_loader import CorpusData


@dataclass
class DeadVowelPair:
    """A consecutive sign pair and their vowel class comparison."""
    sign_i: str
    sign_j: str
    vowel_class_i: int
    vowel_class_j: int
    same_vowel: bool
    word_sign_ids: List[str]
    inscription_id: str


@dataclass
class DeadVowelResult:
    """Results of dead vowel convention test (PRD Section 5.7)."""
    same_vowel_rate: float        # Observed rate of same-vowel consecutive pairs
    expected_rate: float          # Expected rate under null (1/V)
    n_consecutive_pairs: int      # Total consecutive pairs tested
    n_same_vowel: int             # Number sharing same vowel class
    p_value: float                # One-sided binomial test p-value
    significant: bool             # Whether the test is significant at alpha=0.05
    effect_size: float            # (observed - expected) / expected
    vowel_count: int              # V from grid
    # Per-vowel-class breakdown
    per_vowel_rates: Dict[int, float]  # vowel_class -> same-vowel rate
    per_vowel_counts: Dict[int, Tuple[int, int]]  # vowel_class -> (same, total)
    # Sample pairs for inspection
    sample_same_vowel_pairs: List[DeadVowelPair]
    sample_diff_vowel_pairs: List[DeadVowelPair]


def test_dead_vowel(
    grid: GridResult,
    corpus: CorpusData,
    alpha: float = 0.05,
    max_sample_pairs: int = 20,
) -> DeadVowelResult:
    """Test for the dead vowel convention in Linear A.

    Algorithm (PRD Section 5.7):
    1. For each word in the corpus, iterate over consecutive sign pairs.
    2. Look up each sign's vowel class from grid assignments.
    3. Count how often consecutive signs share the same vowel class.
    4. Compare observed rate to expected rate (1/V) using a binomial test.

    Args:
        grid: Grid construction results with vowel class assignments.
        corpus: Corpus data with words.
        alpha: Significance level for the binomial test.
        max_sample_pairs: Maximum example pairs to include in output.

    Returns:
        DeadVowelResult with test statistics and examples.
    """
    V = grid.vowel_count
    if V <= 0:
        return _empty_dead_vowel_result(V)

    expected_rate = 1.0 / V

    # Build sign_id -> vowel_class lookup from grid assignments
    sign_to_vowel: Dict[str, int] = {}
    for assignment in grid.assignments:
        sign_to_vowel[assignment.sign_id] = assignment.vowel_class

    # Iterate over all words, collecting consecutive pairs
    all_pairs: List[DeadVowelPair] = []
    n_same = 0
    n_total = 0

    # Per-vowel tracking
    per_vowel_same: Dict[int, int] = {}
    per_vowel_total: Dict[int, int] = {}

    for inscription in corpus.inscriptions:
        for word in inscription.words:
            sids = word.sign_ids
            if len(sids) < 2:
                continue

            for k in range(len(sids) - 1):
                s_i = sids[k]
                s_j = sids[k + 1]

                v_i = sign_to_vowel.get(s_i)
                v_j = sign_to_vowel.get(s_j)

                # Skip pairs where either sign has no vowel assignment
                if v_i is None or v_j is None:
                    continue

                same = v_i == v_j
                n_total += 1
                if same:
                    n_same += 1

                # Track per-vowel rates (based on first sign's vowel)
                per_vowel_total[v_i] = per_vowel_total.get(v_i, 0) + 1
                if same:
                    per_vowel_same[v_i] = per_vowel_same.get(v_i, 0) + 1

                pair = DeadVowelPair(
                    sign_i=s_i,
                    sign_j=s_j,
                    vowel_class_i=v_i,
                    vowel_class_j=v_j,
                    same_vowel=same,
                    word_sign_ids=sids,
                    inscription_id=inscription.id,
                )
                all_pairs.append(pair)

    if n_total == 0:
        return _empty_dead_vowel_result(V)

    observed_rate = n_same / n_total

    # One-sided binomial test: H1: p > 1/V
    # P(X >= n_same | X ~ Bin(n_total, 1/V))
    p_value = sp_stats.binom.sf(n_same - 1, n_total, expected_rate)

    significant = p_value < alpha

    # Effect size: relative excess
    effect_size = (observed_rate - expected_rate) / expected_rate if expected_rate > 0 else 0.0

    # Per-vowel breakdown
    per_vowel_rates: Dict[int, float] = {}
    per_vowel_counts: Dict[int, Tuple[int, int]] = {}
    for v_class in sorted(set(list(per_vowel_total.keys()) + list(per_vowel_same.keys()))):
        total_v = per_vowel_total.get(v_class, 0)
        same_v = per_vowel_same.get(v_class, 0)
        per_vowel_rates[v_class] = same_v / total_v if total_v > 0 else 0.0
        per_vowel_counts[v_class] = (same_v, total_v)

    # Collect sample pairs
    same_pairs = [p for p in all_pairs if p.same_vowel]
    diff_pairs = [p for p in all_pairs if not p.same_vowel]

    sample_same = same_pairs[:max_sample_pairs]
    sample_diff = diff_pairs[:max_sample_pairs]

    return DeadVowelResult(
        same_vowel_rate=observed_rate,
        expected_rate=expected_rate,
        n_consecutive_pairs=n_total,
        n_same_vowel=n_same,
        p_value=p_value,
        significant=significant,
        effect_size=effect_size,
        vowel_count=V,
        per_vowel_rates=per_vowel_rates,
        per_vowel_counts=per_vowel_counts,
        sample_same_vowel_pairs=sample_same,
        sample_diff_vowel_pairs=sample_diff,
    )


def _empty_dead_vowel_result(V: int) -> DeadVowelResult:
    """Return an empty result when no pairs can be tested."""
    return DeadVowelResult(
        same_vowel_rate=0.0,
        expected_rate=1.0 / V if V > 0 else 0.0,
        n_consecutive_pairs=0,
        n_same_vowel=0,
        p_value=1.0,
        significant=False,
        effect_size=0.0,
        vowel_count=V,
        per_vowel_rates={},
        per_vowel_counts={},
        sample_same_vowel_pairs=[],
        sample_diff_vowel_pairs=[],
    )
