"""Phonotactic constraint discovery for Linear A.

Implements PRD Section 5.5: discovers forbidden and favored sign bigrams,
positional constraints (initial-only, never-initial, never-final signs),
and structural patterns that constrain the phonological interpretation.

Mathematical basis:
    Observed bigram matrix B[i,j] is compared to expected frequencies under
    independence: E[i,j] = (row_i * col_j) / total.
    Standardized residuals R[i,j] = (B[i,j] - E[i,j]) / sqrt(E[i,j])
    identify cells deviating from independence.

    For zero cells (B[i,j]=0) with sufficient expected count (E[i,j] >= min_expected),
    a Poisson test establishes forbidden bigrams.
    For highly overrepresented cells, a Poisson test establishes favored bigrams.
    Bonferroni correction controls family-wise error across all cells.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple
from collections import Counter, defaultdict

import numpy as np
from scipy import stats as sp_stats

from .corpus_loader import CorpusData, BigramRecord
from .alternation_detector import AlternationResult


@dataclass
class BigramConstraint:
    """A single forbidden or favored bigram."""
    sign_i: str
    sign_j: str
    observed: int
    expected: float
    std_residual: float
    p_value: float
    p_value_corrected: float
    constraint_type: str  # "forbidden" or "favored"


@dataclass
class PositionalConstraint:
    """A sign with a positional constraint."""
    sign_id: str
    constraint: str  # "initial_only", "never_initial", "never_final"
    initial_count: int
    medial_count: int
    final_count: int
    total_count: int


@dataclass
class PhonotacticResult:
    """Results of phonotactic constraint analysis (PRD Section 5.5)."""
    bigram_matrix: np.ndarray           # Raw observed bigram counts
    expected_matrix: np.ndarray         # Expected under independence
    residual_matrix: np.ndarray         # Standardized residuals
    sign_ids: List[str]                 # Ordered sign IDs for matrix axes
    sign_id_to_index: Dict[str, int]    # Maps sign_id to matrix index
    forbidden_bigrams: List[BigramConstraint]
    favored_bigrams: List[BigramConstraint]
    initial_only_signs: List[PositionalConstraint]
    never_initial_signs: List[PositionalConstraint]
    never_final_signs: List[PositionalConstraint]
    # Diagnostics
    total_bigrams: int = 0
    unique_bigrams: int = 0
    n_testable_cells: int = 0
    n_forbidden: int = 0
    n_favored: int = 0


def analyze_phonotactics(
    corpus: CorpusData,
    alternation: AlternationResult,
    min_expected: float = 2.0,
    phonotactic_alpha: float = 0.01,
    min_sign_frequency: int = 15,
) -> PhonotacticResult:
    """Discover phonotactic constraints from bigram distribution.

    Algorithm (PRD Section 5.5):
    1. Build bigram frequency matrix B[i,j] from corpus bigram records.
    2. Compute expected frequencies under independence.
    3. Compute standardized residuals.
    4. For cells where B[i,j]=0 and E[i,j] >= min_expected: Poisson test for
       forbidden bigrams (probability of seeing 0 given expected >= min_expected).
    5. For cells where B[i,j] >> E[i,j]: Poisson test for favored bigrams.
    6. Bonferroni correction across all testable cells.
    7. Identify positional constraints (initial_only, never_initial, never_final).

    Args:
        corpus: Processed corpus data with bigram records.
        alternation: Alternation results (for sign_id_to_index mapping).
        min_expected: Minimum expected count for a cell to be testable.
        phonotactic_alpha: Significance level before Bonferroni correction.
        min_sign_frequency: Minimum total occurrences for positional constraint analysis.

    Returns:
        PhonotacticResult with constraint lists and matrices.
    """
    # --- Step 1: Build the sign index from alternation results ---
    # Use the same sign ordering as the alternation module for consistency
    sign_ids = sorted(alternation.sign_id_to_index.keys())
    sign_id_to_idx = {sid: i for i, sid in enumerate(sign_ids)}
    n = len(sign_ids)

    # --- Step 2: Build bigram frequency matrix ---
    B = np.zeros((n, n), dtype=np.float64)
    total_bigrams = 0

    for rec in corpus.bigram_records:
        i = sign_id_to_idx.get(rec.sign_i)
        j = sign_id_to_idx.get(rec.sign_j)
        if i is not None and j is not None:
            B[i, j] += 1
            total_bigrams += 1

    unique_bigrams = int(np.count_nonzero(B))

    # --- Step 3: Compute expected frequencies under independence ---
    row_sums = B.sum(axis=1)  # How often sign_i appears as first in a bigram
    col_sums = B.sum(axis=0)  # How often sign_j appears as second in a bigram
    total = B.sum()

    if total == 0:
        return _empty_phonotactic_result(sign_ids, sign_id_to_idx, n)

    E = np.outer(row_sums, col_sums) / total

    # --- Step 4: Compute standardized residuals ---
    # R[i,j] = (B[i,j] - E[i,j]) / sqrt(E[i,j])
    # Handle E[i,j] = 0 by setting residual to 0
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(E > 0, (B - E) / np.sqrt(E), 0.0)

    # --- Step 5: Identify forbidden and favored bigrams ---
    # Count testable cells for Bonferroni correction
    testable_mask = E >= min_expected
    n_testable = int(testable_mask.sum())

    if n_testable == 0:
        return PhonotacticResult(
            bigram_matrix=B,
            expected_matrix=E,
            residual_matrix=R,
            sign_ids=sign_ids,
            sign_id_to_index=sign_id_to_idx,
            forbidden_bigrams=[],
            favored_bigrams=[],
            initial_only_signs=[],
            never_initial_signs=[],
            never_final_signs=[],
            total_bigrams=total_bigrams,
            unique_bigrams=unique_bigrams,
            n_testable_cells=0,
        )

    alpha_corrected = phonotactic_alpha / n_testable

    forbidden: List[BigramConstraint] = []
    favored: List[BigramConstraint] = []

    for i in range(n):
        for j in range(n):
            if not testable_mask[i, j]:
                continue

            obs = int(B[i, j])
            exp = float(E[i, j])
            residual = float(R[i, j])

            # Forbidden: B[i,j] = 0 with E[i,j] >= min_expected
            # Poisson test: P(X = 0 | lambda = E) = exp(-E)
            if obs == 0:
                p_val = sp_stats.poisson.pmf(0, exp)
                p_corrected = min(p_val * n_testable, 1.0)
                if p_val < alpha_corrected:
                    forbidden.append(BigramConstraint(
                        sign_i=sign_ids[i],
                        sign_j=sign_ids[j],
                        observed=obs,
                        expected=exp,
                        std_residual=residual,
                        p_value=p_val,
                        p_value_corrected=p_corrected,
                        constraint_type="forbidden",
                    ))

            # Favored: B[i,j] >> E[i,j]
            # Poisson test: P(X >= obs | lambda = E) = 1 - P(X < obs)
            elif obs > exp:
                p_val = sp_stats.poisson.sf(obs - 1, exp)
                p_corrected = min(p_val * n_testable, 1.0)
                if p_val < alpha_corrected:
                    favored.append(BigramConstraint(
                        sign_i=sign_ids[i],
                        sign_j=sign_ids[j],
                        observed=obs,
                        expected=exp,
                        std_residual=residual,
                        p_value=p_val,
                        p_value_corrected=p_corrected,
                        constraint_type="favored",
                    ))

    # Sort by significance
    forbidden.sort(key=lambda c: c.p_value)
    favored.sort(key=lambda c: c.p_value)

    # --- Step 6: Positional constraints ---
    initial_only, never_initial, never_final = _find_positional_constraints(
        corpus, min_sign_frequency,
    )

    return PhonotacticResult(
        bigram_matrix=B,
        expected_matrix=E,
        residual_matrix=R,
        sign_ids=sign_ids,
        sign_id_to_index=sign_id_to_idx,
        forbidden_bigrams=forbidden,
        favored_bigrams=favored,
        initial_only_signs=initial_only,
        never_initial_signs=never_initial,
        never_final_signs=never_final,
        total_bigrams=total_bigrams,
        unique_bigrams=unique_bigrams,
        n_testable_cells=n_testable,
        n_forbidden=len(forbidden),
        n_favored=len(favored),
    )


def _find_positional_constraints(
    corpus: CorpusData,
    min_sign_frequency: int,
) -> Tuple[
    List[PositionalConstraint],
    List[PositionalConstraint],
    List[PositionalConstraint],
]:
    """Identify signs with positional constraints.

    A sign is:
    - initial_only: appears ONLY in initial position (never medial or final)
    - never_initial: never appears in initial position
    - never_final: never appears in final position

    Only considers signs with total frequency >= min_sign_frequency to avoid
    spurious constraints from rare signs.
    """
    pos_counts: Dict[str, Counter] = defaultdict(Counter)
    for rec in corpus.positional_records:
        pos_counts[rec.sign_id][rec.position] += 1

    initial_only: List[PositionalConstraint] = []
    never_initial: List[PositionalConstraint] = []
    never_final: List[PositionalConstraint] = []

    for sign_id, counts in pos_counts.items():
        n_init = counts.get("initial", 0)
        n_med = counts.get("medial", 0)
        n_fin = counts.get("final", 0)
        n_total = n_init + n_med + n_fin

        if n_total < min_sign_frequency:
            continue

        constraint_base = PositionalConstraint(
            sign_id=sign_id,
            constraint="",
            initial_count=n_init,
            medial_count=n_med,
            final_count=n_fin,
            total_count=n_total,
        )

        if n_init > 0 and n_med == 0 and n_fin == 0:
            c = PositionalConstraint(
                sign_id=sign_id,
                constraint="initial_only",
                initial_count=n_init,
                medial_count=n_med,
                final_count=n_fin,
                total_count=n_total,
            )
            initial_only.append(c)

        if n_init == 0:
            c = PositionalConstraint(
                sign_id=sign_id,
                constraint="never_initial",
                initial_count=n_init,
                medial_count=n_med,
                final_count=n_fin,
                total_count=n_total,
            )
            never_initial.append(c)

        if n_fin == 0:
            c = PositionalConstraint(
                sign_id=sign_id,
                constraint="never_final",
                initial_count=n_init,
                medial_count=n_med,
                final_count=n_fin,
                total_count=n_total,
            )
            never_final.append(c)

    # Sort by total count descending
    initial_only.sort(key=lambda c: c.total_count, reverse=True)
    never_initial.sort(key=lambda c: c.total_count, reverse=True)
    never_final.sort(key=lambda c: c.total_count, reverse=True)

    return initial_only, never_initial, never_final


def _empty_phonotactic_result(
    sign_ids: List[str],
    sign_id_to_idx: Dict[str, int],
    n: int,
) -> PhonotacticResult:
    """Return an empty result when there are no bigrams."""
    return PhonotacticResult(
        bigram_matrix=np.zeros((n, n)),
        expected_matrix=np.zeros((n, n)),
        residual_matrix=np.zeros((n, n)),
        sign_ids=sign_ids,
        sign_id_to_index=sign_id_to_idx,
        forbidden_bigrams=[],
        favored_bigrams=[],
        initial_only_signs=[],
        never_initial_signs=[],
        never_final_signs=[],
    )
