"""Vowel identification via positional frequency analysis.

Implements Ventris's method computationally: pure vowel signs are enriched
in word-initial position and depleted in word-medial position in a CV syllabary.

Mathematical basis (PRD Appendix A.1):
    In a CV syllabary, words starting with a vowel require a bare V sign initially.
    This creates measurable enrichment: E = p_v * C / (1 - p_v) ≈ 6x for typical params.

    Test: one-sided binomial test for initial-position enrichment.
    Correction: Bonferroni for N simultaneous tests.
    Cross-validation: medial-position depletion must also hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from collections import Counter

import numpy as np
from scipy import stats

from .corpus_loader import CorpusData, PositionalRecord


@dataclass
class SignPositionalStats:
    """Positional frequency statistics for one sign."""
    sign_id: str
    initial_count: int
    medial_count: int
    final_count: int
    total_count: int

    # Enrichment analysis
    enrichment_score: float = 0.0     # (k/n) / p_0
    p_value_initial: float = 1.0      # one-sided binomial for initial enrichment
    p_value_medial: float = 1.0       # one-sided binomial for medial depletion
    p_value_corrected: float = 1.0    # Bonferroni-corrected (max of the two)
    classification: str = "cv_sign"   # "pure_vowel" or "cv_sign" or "insufficient_data"
    confidence: float = 0.0


@dataclass
class VowelInventory:
    """Results of vowel identification."""
    count: int
    count_ci_95: Tuple[int, int]
    method: str = "positional_frequency_binomial"
    signs: List[SignPositionalStats] = field(default_factory=list)
    all_sign_stats: List[SignPositionalStats] = field(default_factory=list)
    # Diagnostics
    global_initial_rate: float = 0.0
    global_medial_rate: float = 0.0
    global_final_rate: float = 0.0
    n_testable_signs: int = 0


def identify_vowels(
    corpus: CorpusData,
    alpha: float = 0.05,
    min_sign_frequency: int = 15,
    bootstrap_n: int = 1000,
    seed: int = 1234,
) -> VowelInventory:
    """Identify pure vowel signs from positional frequency analysis.

    Algorithm (PRD Section 5.2):
    1. Count each sign's frequency in initial, medial, and final positions.
    2. For each sign, test for initial-position enrichment (one-sided binomial).
    3. Cross-validate with medial-position depletion.
    4. Signs passing BOTH tests = pure vowels.
    5. Bootstrap CI on vowel count.

    Args:
        corpus: Processed corpus data from corpus_loader.
        alpha: Significance level before Bonferroni correction.
        min_sign_frequency: Minimum total occurrences for a sign to be testable.
        bootstrap_n: Number of bootstrap resamples for CI.
        seed: Random seed.

    Returns:
        VowelInventory with identified vowels and all sign statistics.
    """
    rng = np.random.default_rng(seed)

    # --- Step 1: Count positional frequencies ---
    pos_counts: Dict[str, Counter] = {}  # sign_id -> Counter(position -> count)
    for rec in corpus.positional_records:
        if rec.sign_id not in pos_counts:
            pos_counts[rec.sign_id] = Counter()
        pos_counts[rec.sign_id][rec.position] += 1

    # Global rates
    total_tokens = len(corpus.positional_records)
    if total_tokens == 0:
        raise ValueError("No positional records — corpus may be empty or all words excluded.")

    total_initial = sum(c["initial"] for c in pos_counts.values())
    total_medial = sum(c["medial"] for c in pos_counts.values())
    total_final = sum(c["final"] for c in pos_counts.values())

    p_initial = total_initial / total_tokens if total_tokens > 0 else 0
    p_medial = total_medial / total_tokens if total_tokens > 0 else 0
    p_final = total_final / total_tokens if total_tokens > 0 else 0

    # --- Step 2: Compute statistics for each sign ---
    all_stats: List[SignPositionalStats] = []
    testable_signs: List[SignPositionalStats] = []

    for sign_id, counts in pos_counts.items():
        n_init = counts.get("initial", 0)
        n_med = counts.get("medial", 0)
        n_fin = counts.get("final", 0)
        n_total = n_init + n_med + n_fin

        stat = SignPositionalStats(
            sign_id=sign_id,
            initial_count=n_init,
            medial_count=n_med,
            final_count=n_fin,
            total_count=n_total,
        )

        if n_total < min_sign_frequency:
            stat.classification = "insufficient_data"
            all_stats.append(stat)
            continue

        # Enrichment score: (k/n) / p_0
        # PRD Eq: E_i = (k_i / n_i) / p_0
        stat.enrichment_score = (n_init / n_total) / p_initial if p_initial > 0 else 0

        # One-sided binomial test for initial enrichment
        # H0: k ~ Bin(n, p_initial)
        # H1: sign appears initially MORE than expected
        # p-value = P(X >= k | X ~ Bin(n, p_initial))
        # scipy binom_test is two-sided; use survival function instead
        stat.p_value_initial = stats.binom.sf(n_init - 1, n_total, p_initial)

        # One-sided binomial test for medial depletion
        # H0: m ~ Bin(n, p_medial)
        # H1: sign appears medially LESS than expected
        # p-value = P(X <= m | X ~ Bin(n, p_medial))
        stat.p_value_medial = stats.binom.cdf(n_med, n_total, p_medial)

        all_stats.append(stat)
        testable_signs.append(stat)

    # --- Step 3: Bonferroni correction and classification ---
    n_tests = len(testable_signs)
    if n_tests == 0:
        return VowelInventory(
            count=0, count_ci_95=(0, 0),
            all_sign_stats=all_stats,
            global_initial_rate=p_initial,
            global_medial_rate=p_medial,
            global_final_rate=p_final,
            n_testable_signs=0,
        )

    alpha_corrected = alpha / n_tests

    vowel_signs: List[SignPositionalStats] = []
    for stat in testable_signs:
        # Must pass BOTH tests: enriched initially AND depleted medially
        initial_sig = stat.p_value_initial < alpha_corrected
        medial_sig = stat.p_value_medial < alpha_corrected

        # Corrected p-value = max of the two (both must be significant)
        stat.p_value_corrected = max(stat.p_value_initial, stat.p_value_medial) * n_tests
        stat.p_value_corrected = min(stat.p_value_corrected, 1.0)  # cap at 1

        if initial_sig and medial_sig:
            stat.classification = "pure_vowel"
            # Confidence based on how far below threshold
            stat.confidence = min(
                1.0 - stat.p_value_initial / alpha_corrected,
                1.0 - stat.p_value_medial / alpha_corrected,
            )
            stat.confidence = max(0.0, min(1.0, stat.confidence))
            vowel_signs.append(stat)
        elif initial_sig:
            # Enriched initially but not depleted medially — ambiguous
            stat.classification = "cv_sign"
            stat.confidence = 0.0
        else:
            stat.classification = "cv_sign"
            stat.confidence = 0.0

    # --- Step 4: Bootstrap CI for vowel count ---
    # Resample inscriptions with replacement, re-run the test, count vowels
    ci_low, ci_high = _bootstrap_vowel_count_ci(
        corpus, alpha, min_sign_frequency, bootstrap_n, rng,
    )

    # Sort vowel signs by enrichment score (highest first)
    vowel_signs.sort(key=lambda s: s.enrichment_score, reverse=True)
    # Sort all stats by enrichment score for readability
    all_stats.sort(key=lambda s: s.enrichment_score, reverse=True)

    return VowelInventory(
        count=len(vowel_signs),
        count_ci_95=(ci_low, ci_high),
        signs=vowel_signs,
        all_sign_stats=all_stats,
        global_initial_rate=p_initial,
        global_medial_rate=p_medial,
        global_final_rate=p_final,
        n_testable_signs=n_tests,
    )


def _bootstrap_vowel_count_ci(
    corpus: CorpusData,
    alpha: float,
    min_sign_frequency: int,
    bootstrap_n: int,
    rng: np.random.Generator,
) -> Tuple[int, int]:
    """Bootstrap 95% CI for vowel count by resampling inscriptions.

    Resamples inscriptions (not individual records) to preserve within-inscription
    structure, then re-runs the positional frequency test on each resample.
    """
    # Group positional records by inscription
    insc_groups: Dict[str, List[PositionalRecord]] = {}
    for rec in corpus.positional_records:
        insc_groups.setdefault(rec.inscription_id, []).append(rec)

    insc_ids = list(insc_groups.keys())
    n_inscriptions = len(insc_ids)

    if n_inscriptions == 0:
        return (0, 0)

    vowel_counts: List[int] = []

    for _ in range(bootstrap_n):
        # Resample inscriptions with replacement
        sampled_ids = rng.choice(insc_ids, size=n_inscriptions, replace=True)

        # Collect positional records from sampled inscriptions
        sampled_records: List[PositionalRecord] = []
        for sid in sampled_ids:
            sampled_records.extend(insc_groups[sid])

        # Quick vowel count on this resample
        v_count = _count_vowels_from_records(sampled_records, alpha, min_sign_frequency)
        vowel_counts.append(v_count)

    vowel_counts_arr = np.array(vowel_counts)
    ci_low = int(np.percentile(vowel_counts_arr, 2.5))
    ci_high = int(np.percentile(vowel_counts_arr, 97.5))

    return (ci_low, ci_high)


def _count_vowels_from_records(
    records: List[PositionalRecord],
    alpha: float,
    min_sign_frequency: int,
) -> int:
    """Count vowels from a set of positional records (used in bootstrap)."""
    pos_counts: Dict[str, Counter] = {}
    for rec in records:
        if rec.sign_id not in pos_counts:
            pos_counts[rec.sign_id] = Counter()
        pos_counts[rec.sign_id][rec.position] += 1

    total = len(records)
    if total == 0:
        return 0

    total_initial = sum(c.get("initial", 0) for c in pos_counts.values())
    total_medial = sum(c.get("medial", 0) for c in pos_counts.values())
    p_initial = total_initial / total
    p_medial = total_medial / total

    testable = [(sid, c) for sid, c in pos_counts.items()
                if sum(c.values()) >= min_sign_frequency]
    n_tests = len(testable)
    if n_tests == 0:
        return 0

    alpha_corrected = alpha / n_tests
    count = 0

    for sid, counts in testable:
        n_init = counts.get("initial", 0)
        n_med = counts.get("medial", 0)
        n_total = sum(counts.values())

        p_init = stats.binom.sf(n_init - 1, n_total, p_initial)
        p_med = stats.binom.cdf(n_med, n_total, p_medial)

        if p_init < alpha_corrected and p_med < alpha_corrected:
            count += 1

    return count
