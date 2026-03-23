"""Tests for pillar1.alternation_detector — Kober's triplets detection."""

from __future__ import annotations

from typing import List, Set

import numpy as np
import pytest

from pillar1.corpus_loader import (
    CorpusData,
    Inscription,
    Word,
    SignToken,
    PositionalRecord,
    BigramRecord,
)
from pillar1.alternation_detector import (
    detect_alternations,
    AlternationResult,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _make_synthetic_corpus(
    words: List[List[str]],
    inscription_id: str = "SYNTH-001",
) -> CorpusData:
    """Build a minimal CorpusData from a list of words (each word is a
    list of sign-id strings, all treated as syllabograms)."""
    sign_tokens_per_word: List[Word] = []
    positional_records: List[PositionalRecord] = []
    bigram_records: List[BigramRecord] = []

    for wi, sign_ids in enumerate(words):
        tokens = [
            SignToken(sign_id=sid, sign_type="syllabogram", reading=sid.lower())
            for sid in sign_ids
        ]
        word = Word(
            signs=tokens,
            has_damage=False,
            inscription_id=inscription_id,
            word_index=wi,
        )
        sign_tokens_per_word.append(word)

        syllib_ids = word.sign_ids
        # Positional records
        for pos_idx, sid in enumerate(syllib_ids):
            if len(syllib_ids) == 1:
                position = "singleton"
            elif pos_idx == 0:
                position = "initial"
            elif pos_idx == len(syllib_ids) - 1:
                position = "final"
            else:
                position = "medial"
            positional_records.append(PositionalRecord(
                sign_id=sid,
                position=position,
                word_sign_ids=syllib_ids,
                inscription_id=inscription_id,
            ))
        # Bigram records
        if len(syllib_ids) >= 2:
            for j in range(len(syllib_ids) - 1):
                bigram_records.append(BigramRecord(
                    sign_i=syllib_ids[j],
                    sign_j=syllib_ids[j + 1],
                    position_in_word=j,
                    word_sign_ids=syllib_ids,
                    inscription_id=inscription_id,
                ))

    inscription = Inscription(
        id=inscription_id,
        type="synthetic",
        site="test",
        words=sign_tokens_per_word,
    )

    return CorpusData(
        inscriptions=[inscription],
        positional_records=positional_records,
        bigram_records=bigram_records,
        sign_inventory={},
        corpus_hash="synthetic",
        total_inscriptions=1,
        total_words=len(words),
        total_syllabogram_tokens=sum(len(w) for w in words),
        unique_syllabograms=len({s for w in words for s in w}),
        words_used_positional=len(words),
        words_used_bigram=sum(1 for w in words if len(w) >= 2),
    )


# ── Real corpus: basic detection ──────────────────────────────────────

def test_finds_alternation_pairs_on_real_corpus(
    alternation_result: AlternationResult,
) -> None:
    """The real SigLA corpus must yield at least one significant
    alternation pair (Kober's triplets)."""
    assert len(alternation_result.significant_pairs) > 0, (
        "Expected >0 significant alternation pairs on the real corpus"
    )


# ── Synthetic: known alternation ──────────────────────────────────────

def test_synthetic_known_alternation() -> None:
    """Words ["A","B","X"], ["A","B","Y"], ["A","B","Z"] share prefix AB
    with three different final signs. The detector should find (X,Y),
    (X,Z), and (Y,Z) as alternation pairs."""
    corpus = _make_synthetic_corpus([
        ["A", "B", "X"],
        ["A", "B", "Y"],
        ["A", "B", "Z"],
    ])
    result = detect_alternations(
        corpus,
        min_shared_prefix_length=1,
        min_independent_stems=1,
        alternation_alpha=1.0,  # Accept everything so we test detection, not filtering
    )

    detected_pairs: Set[frozenset] = {
        frozenset({p.sign_a, p.sign_b}) for p in result.all_pairs
    }

    expected = {
        frozenset({"X", "Y"}),
        frozenset({"X", "Z"}),
        frozenset({"Y", "Z"}),
    }
    assert expected.issubset(detected_pairs), (
        f"Expected pairs {expected} not all found. Detected: {detected_pairs}"
    )


# ── No alternation in unique words ─────────────────────────────────────

def test_no_alternation_in_unique_words() -> None:
    """If every word is unique (no shared prefixes), expect 0 alternation
    pairs."""
    corpus = _make_synthetic_corpus([
        ["A", "B"],
        ["C", "D"],
        ["E", "F"],
        ["G", "H"],
    ])
    result = detect_alternations(
        corpus,
        min_shared_prefix_length=1,
        min_independent_stems=1,
    )
    assert len(result.all_pairs) == 0, (
        f"Expected 0 pairs from unique words, got {len(result.all_pairs)}"
    )


# ── Affinity matrix symmetry ──────────────────────────────────────────

def test_affinity_matrix_is_symmetric(
    alternation_result: AlternationResult,
) -> None:
    """The affinity matrix A must equal its transpose A.T."""
    A = alternation_result.affinity_matrix
    np.testing.assert_array_equal(
        A, A.T,
        err_msg="Affinity matrix is not symmetric",
    )


# ── Minimum stems filter ──────────────────────────────────────────────

def test_minimum_stems_filter_works() -> None:
    """With min_independent_stems=3, pairs backed by only 2 distinct stems
    should be filtered out (not marked as significant)."""
    # Create corpus where X/Y alternate under 2 stems, and P/Q alternate
    # under 3 stems — only P/Q should pass the filter.
    #
    # Use max_suffix_diff_length=1 to avoid 2-sign suffix matching which
    # can add extra stem evidence from longer prefixes.
    corpus = _make_synthetic_corpus([
        # 2 stems for X/Y alternation
        ["A", "B", "X"],
        ["A", "B", "Y"],
        ["C", "D", "X"],
        ["C", "D", "Y"],
        # 3 stems for P/Q alternation
        ["E", "F", "P"],
        ["E", "F", "Q"],
        ["G", "H", "P"],
        ["G", "H", "Q"],
        ["I", "J", "P"],
        ["I", "J", "Q"],
    ])

    result = detect_alternations(
        corpus,
        min_shared_prefix_length=1,
        max_suffix_diff_length=1,
        min_independent_stems=3,
        alternation_alpha=1.0,  # Accept all p-values so we test only the stem filter
    )

    sig_pairs: Set[frozenset] = {
        frozenset({p.sign_a, p.sign_b}) for p in result.significant_pairs
    }

    pq = frozenset({"P", "Q"})
    xy = frozenset({"X", "Y"})

    assert pq in sig_pairs, (
        f"P/Q pair (3 stems) should be significant, but is missing. "
        f"Significant: {sig_pairs}"
    )
    assert xy not in sig_pairs, (
        f"X/Y pair (2 stems) should NOT be significant with min_independent_stems=3"
    )
