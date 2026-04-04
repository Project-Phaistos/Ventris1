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


# ── Fix 1 regression: min_prefix=1 (legacy) still yields high pair count ──

def test_legacy_prefix1_yields_many_pairs(
    corpus_data: CorpusData,
) -> None:
    """With min_shared_prefix_length=1 (legacy), the real corpus should
    still yield hundreds of pairs (proving old behavior is preserved as
    an option, even though it is dominated by artifacts)."""
    result = detect_alternations(
        corpus_data,
        min_shared_prefix_length=1,
    )
    # The old detector produced ~449 pairs (610 before the diff_len=2 fix).
    # Require >= 200 to confirm old behavior is accessible.
    assert result.total_significant_pairs >= 200, (
        f"Legacy prefix=1 should yield >= 200 significant pairs, "
        f"got {result.total_significant_pairs}"
    )


# ── Fix 1: Prefix length test ────────────────────────────────────────

def test_prefix2_excludes_two_sign_words() -> None:
    """With min_shared_prefix_length=2, 2-sign words must contribute
    ZERO pairs. Only words with >= 3 signs can share a 2-sign prefix.

    This is the core fix: 2-sign words sharing only an initial syllable
    are NOT evidence of inflectional alternation."""
    # Corpus with ONLY 2-sign words (different final signs sharing initial)
    corpus_2sign = _make_synthetic_corpus([
        ["A", "X"],
        ["A", "Y"],
        ["A", "Z"],
        ["B", "X"],
        ["B", "Y"],
    ])
    result = detect_alternations(
        corpus_2sign,
        min_shared_prefix_length=2,
        min_independent_stems=1,
        alternation_alpha=1.0,
    )
    assert len(result.all_pairs) == 0, (
        f"With prefix=2, 2-sign words should contribute 0 pairs, "
        f"got {len(result.all_pairs)}"
    )

    # But prefix=1 should find them
    result_legacy = detect_alternations(
        corpus_2sign,
        min_shared_prefix_length=1,
        min_independent_stems=1,
        alternation_alpha=1.0,
    )
    assert len(result_legacy.all_pairs) > 0, (
        "With prefix=1, 2-sign words should produce alternation pairs"
    )


def test_prefix2_keeps_three_sign_words() -> None:
    """With min_shared_prefix_length=2, 3-sign words sharing a 2-sign
    prefix should still produce alternation pairs."""
    corpus_3sign = _make_synthetic_corpus([
        ["A", "B", "X"],
        ["A", "B", "Y"],
        ["A", "B", "Z"],
    ])
    result = detect_alternations(
        corpus_3sign,
        min_shared_prefix_length=2,
        min_independent_stems=1,
        alternation_alpha=1.0,
    )
    detected = {frozenset({p.sign_a, p.sign_b}) for p in result.all_pairs}
    expected = {
        frozenset({"X", "Y"}),
        frozenset({"X", "Z"}),
        frozenset({"Y", "Z"}),
    }
    assert expected.issubset(detected), (
        f"3-sign words with 2-sign prefix should produce pairs. "
        f"Expected {expected}, got {detected}"
    )


# ── Fix 2: diff_len=2 final-position only ────────────────────────────

def test_diff_len2_only_extracts_final_position() -> None:
    """When two words differ in their last 2 signs, only the final-position
    pair should be extracted. The penultimate pair is a stem difference,
    not a suffix alternation.

    For [A, B, X1, X2] vs [A, B, Y1, Y2]:
      - (X2, Y2) should be detected (final position = suffix alternation)
      - (X1, Y1) should NOT be detected (penultimate = stem difference)
    """
    corpus = _make_synthetic_corpus([
        ["A", "B", "X1", "X2"],
        ["A", "B", "Y1", "Y2"],
    ])
    result = detect_alternations(
        corpus,
        min_shared_prefix_length=1,
        max_suffix_diff_length=2,
        min_independent_stems=1,
        alternation_alpha=1.0,
    )
    detected = {frozenset({p.sign_a, p.sign_b}) for p in result.all_pairs}

    # Final-position pair should be present
    final_pair = frozenset({"X2", "Y2"})
    assert final_pair in detected, (
        f"Final-position pair {final_pair} should be detected, got {detected}"
    )

    # Penultimate pair should NOT be present
    penult_pair = frozenset({"X1", "Y1"})
    assert penult_pair not in detected, (
        f"Penultimate pair {penult_pair} should NOT be detected (stem position, "
        f"not suffix alternation)"
    )


# ── Fix 3: Permutation null test ─────────────────────────────────────

def test_shuffled_corpus_produces_fewer_pairs(
    corpus_data: CorpusData,
) -> None:
    """The fixed detector must produce significantly more pairs on the
    real corpus than on shuffled copies (where sign order within
    sign-groups is randomized, destroying all alternation structure).

    Gate: N_original > 2 * mean(N_shuffled)

    This is the KEY validation: the old detector (prefix=1) failed this
    test entirely (610 original vs 609 mean shuffled = 1.0x ratio).
    """
    import random
    from pillar1.corpus_loader import (
        PositionalRecord, BigramRecord, Inscription, Word, SignToken,
    )

    # Original
    original = detect_alternations(corpus_data)
    n_original = original.total_significant_pairs

    # Build shuffled corpora
    def _shuffle_corpus(corpus: CorpusData, seed: int) -> CorpusData:
        rng = random.Random(seed)
        new_inscriptions = []
        all_pos: List[PositionalRecord] = []
        all_bi: List[BigramRecord] = []

        for insc in corpus.inscriptions:
            new_words = []
            for word in insc.words:
                sids = list(word.sign_ids)
                if len(sids) >= 2:
                    rng.shuffle(sids)
                tokens = [
                    SignToken(sign_id=s, sign_type="syllabogram", reading=s.lower())
                    for s in sids
                ]
                new_word = Word(
                    signs=tokens, has_damage=word.has_damage,
                    inscription_id=word.inscription_id, word_index=word.word_index,
                )
                new_words.append(new_word)

                syllib = new_word.sign_ids
                for pi, sid in enumerate(syllib):
                    if len(syllib) == 1:
                        pos = "singleton"
                    elif pi == 0:
                        pos = "initial"
                    elif pi == len(syllib) - 1:
                        pos = "final"
                    else:
                        pos = "medial"
                    all_pos.append(PositionalRecord(
                        sign_id=sid, position=pos,
                        word_sign_ids=syllib, inscription_id=insc.id,
                    ))
                if len(syllib) >= 2:
                    for j in range(len(syllib) - 1):
                        all_bi.append(BigramRecord(
                            sign_i=syllib[j], sign_j=syllib[j + 1],
                            position_in_word=j, word_sign_ids=syllib,
                            inscription_id=insc.id,
                        ))
            new_inscriptions.append(Inscription(
                id=insc.id, type=insc.type, site=insc.site, words=new_words,
            ))

        return CorpusData(
            inscriptions=new_inscriptions,
            positional_records=all_pos,
            bigram_records=all_bi,
            sign_inventory=corpus.sign_inventory,
            corpus_hash="shuffled",
            total_inscriptions=corpus.total_inscriptions,
            total_words=corpus.total_words,
            total_syllabogram_tokens=corpus.total_syllabogram_tokens,
            unique_syllabograms=corpus.unique_syllabograms,
            words_used_positional=corpus.words_used_positional,
            words_used_bigram=corpus.words_used_bigram,
        )

    shuffled_counts = []
    for seed in range(5):
        sc = _shuffle_corpus(corpus_data, seed)
        sr = detect_alternations(sc)
        shuffled_counts.append(sr.total_significant_pairs)

    mean_shuffled = sum(shuffled_counts) / len(shuffled_counts)

    # Gate: original must be at least 2x mean shuffled
    assert n_original > 2 * mean_shuffled, (
        f"Permutation null test FAILED: original={n_original} pairs, "
        f"mean_shuffled={mean_shuffled:.1f} pairs, "
        f"ratio={n_original / mean_shuffled:.2f}x (need > 2.0x). "
        f"Shuffled counts: {shuffled_counts}. "
        f"The detector is still measuring frequency artifacts, not alternation."
    )


# ── Fix 4: Consonant row purity ──────────────────────────────────────

def test_consonant_row_purity_improved(
    corpus_data: CorpusData,
) -> None:
    """Consonant row purity of the fixed detector's significant pairs
    must exceed 30% when checked against LB ground truth.

    The old detector achieved only 7.9% purity (worse than random).
    With the fixes, the remaining pairs are more likely to be genuine
    Kober alternations (same consonant, different vowel).

    Note: If there are fewer than 2 testable pairs (both signs have
    known LB values), the test is skipped — too few pairs to measure
    purity reliably.
    """
    import json
    from pathlib import Path

    result = detect_alternations(corpus_data)

    # Load LB ground truth
    fixture_path = Path(__file__).parent / "fixtures" / "linear_b_sign_to_ipa.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        lb_ipa = json.load(f)

    def _get_consonant(reading: str) -> str | None:
        vowels = {"a", "e", "i", "o", "u"}
        if reading in vowels:
            return ""
        clean = reading.rstrip("0123456789")
        if len(clean) >= 2 and clean[-1] in vowels:
            return clean[:-1]
        return None

    lb_consonant = {}
    for ab, reading in lb_ipa.items():
        c = _get_consonant(reading)
        if c is not None:
            lb_consonant[ab] = c

    n_pure = 0
    n_testable = 0
    for p in result.significant_pairs:
        c_a = lb_consonant.get(p.sign_a)
        c_b = lb_consonant.get(p.sign_b)
        if c_a is not None and c_b is not None:
            n_testable += 1
            if c_a == c_b:
                n_pure += 1

    if n_testable < 2:
        pytest.skip(
            f"Only {n_testable} testable pair(s) — too few for purity measurement"
        )

    purity = n_pure / n_testable
    assert purity > 0.30, (
        f"Consonant row purity {purity:.1%} ({n_pure}/{n_testable}) is below "
        f"30% threshold. The old detector was at 7.9%. Purity should improve "
        f"dramatically with the prefix-length and diff_len fixes."
    )
