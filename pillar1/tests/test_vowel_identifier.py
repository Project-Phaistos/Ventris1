"""Tests for pillar1.vowel_identifier — positional-frequency vowel detection."""

from __future__ import annotations

import random
from copy import deepcopy
from typing import List

import pytest

from pillar1.corpus_loader import CorpusData, PositionalRecord
from pillar1.vowel_identifier import identify_vowels, VowelInventory


# ── Helpers ────────────────────────────────────────────────────────────

def _shuffle_positional_records(
    corpus: CorpusData,
    seed: int = 42,
) -> CorpusData:
    """Return a copy of the corpus with sign_id assignments randomly
    permuted within each word, destroying positional structure.

    This is the null model for Gate 2: if the method is sound, it should
    find zero vowels when positional signal is destroyed.
    """
    rng = random.Random(seed)

    # Group positional records by word (inscription_id + word_sign_ids)
    from collections import defaultdict
    word_groups: dict[tuple, List[PositionalRecord]] = defaultdict(list)
    for rec in corpus.positional_records:
        key = (rec.inscription_id, tuple(rec.word_sign_ids))
        word_groups[key].append(rec)

    shuffled_records: List[PositionalRecord] = []
    for key, recs in word_groups.items():
        # Extract sign_ids and shuffle them
        sign_ids = [r.sign_id for r in recs]
        rng.shuffle(sign_ids)

        # Reassign shuffled sign_ids to records (keeping positions intact)
        for rec, new_sid in zip(recs, sign_ids):
            shuffled_records.append(PositionalRecord(
                sign_id=new_sid,
                position=rec.position,
                word_sign_ids=rec.word_sign_ids,
                inscription_id=rec.inscription_id,
            ))

    # Build a shallow copy of the corpus with shuffled positional records
    shuffled_corpus = CorpusData(
        inscriptions=corpus.inscriptions,
        positional_records=shuffled_records,
        bigram_records=corpus.bigram_records,
        sign_inventory=corpus.sign_inventory,
        corpus_hash=corpus.corpus_hash,
        total_inscriptions=corpus.total_inscriptions,
        total_words=corpus.total_words,
        total_syllabogram_tokens=corpus.total_syllabogram_tokens,
        unique_syllabograms=corpus.unique_syllabograms,
        words_used_positional=corpus.words_used_positional,
        words_used_bigram=corpus.words_used_bigram,
    )
    return shuffled_corpus


# ── Minimum vowel count ───────────────────────────────────────────────

def test_identifies_at_least_1_vowel_on_real_corpus(
    vowel_result: VowelInventory,
) -> None:
    """The real SigLA corpus should yield at least 1 pure vowel.

    With Bonferroni correction on ~45 testable signs, only the strongest
    signal (AB08, the 'a' vowel) survives both the initial-enrichment and
    medial-depletion tests. The bootstrap CI [1, 4] confirms more vowels
    are likely; the strict statistical filter is conservative by design."""
    assert vowel_result.count >= 1, (
        f"Expected >= 1 vowel, got {vowel_result.count}"
    )


# ── Confidence interval sanity ─────────────────────────────────────────

def test_vowel_count_ci_contains_point_estimate(
    vowel_result: VowelInventory,
) -> None:
    """The 95% bootstrap CI must contain the point estimate."""
    lo, hi = vowel_result.count_ci_95
    assert lo <= vowel_result.count <= hi, (
        f"Point estimate {vowel_result.count} outside CI [{lo}, {hi}]"
    )


# ── Enrichment scores ─────────────────────────────────────────────────

def test_enrichment_scores_positive_for_vowels(
    vowel_result: VowelInventory,
) -> None:
    """All identified vowels must have enrichment > 1.0 (i.e., they appear
    in initial position MORE than the corpus-wide base rate)."""
    for sign in vowel_result.signs:
        assert sign.enrichment_score > 1.0, (
            f"Vowel {sign.sign_id} has enrichment {sign.enrichment_score:.3f} <= 1.0"
        )


# ── P-value threshold ─────────────────────────────────────────────────

def test_p_values_below_corrected_threshold(
    vowel_result: VowelInventory,
) -> None:
    """All identified vowels must have Bonferroni-corrected p < alpha (0.05)."""
    alpha = 0.05
    for sign in vowel_result.signs:
        assert sign.p_value_corrected < alpha, (
            f"Vowel {sign.sign_id} has corrected p={sign.p_value_corrected:.4f} >= {alpha}"
        )


# ── Insufficient data classification ──────────────────────────────────

def test_insufficient_data_signs_not_classified(
    vowel_result: VowelInventory,
) -> None:
    """Signs with total_count < min_sign_frequency (default 15) must be
    classified as 'insufficient_data', never as 'pure_vowel'."""
    min_freq = 15  # default in identify_vowels
    for stat in vowel_result.all_sign_stats:
        if stat.total_count < min_freq:
            assert stat.classification == "insufficient_data", (
                f"Sign {stat.sign_id} with count {stat.total_count} < {min_freq} "
                f"was classified as '{stat.classification}' instead of 'insufficient_data'"
            )


# ── Null input: Gate 2 ────────────────────────────────────────────────

def test_null_input_random_permutation_finds_no_vowels(
    corpus_data: CorpusData,
) -> None:
    """Gate 2: When sign_id assignments are randomly shuffled within words
    (destroying positional structure), the method must find 0 vowels.

    If it finds vowels in random data, the statistical test is broken."""
    shuffled = _shuffle_positional_records(corpus_data, seed=42)
    result = identify_vowels(shuffled)
    assert result.count == 0, (
        f"Found {result.count} 'vowels' in permuted null data — "
        f"statistical test is too liberal. Signs: "
        f"{[s.sign_id for s in result.signs]}"
    )
