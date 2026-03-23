"""Tests for pillar1.corpus_loader — SigLA corpus loading and preprocessing."""

from __future__ import annotations

from pathlib import Path

import pytest

from pillar1.corpus_loader import load_corpus, CorpusData

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "sigla_full_corpus.json"


# ── Basic loading ──────────────────────────────────────────────────────

def test_load_corpus_returns_nonempty_data(corpus_data: CorpusData) -> None:
    """Loading the real SigLA corpus must produce non-empty inscriptions,
    positional records, and bigram records."""
    assert len(corpus_data.inscriptions) > 0, "Expected >0 inscriptions"
    assert len(corpus_data.positional_records) > 0, "Expected >0 positional records"
    assert len(corpus_data.bigram_records) > 0, "Expected >0 bigram records"


# ── Determinism ────────────────────────────────────────────────────────

def test_corpus_hash_is_deterministic() -> None:
    """Loading the same corpus twice must produce the identical SHA-256 hash."""
    c1 = load_corpus(CORPUS_PATH)
    c2 = load_corpus(CORPUS_PATH)
    assert c1.corpus_hash == c2.corpus_hash


# ── Damaged-word filtering ─────────────────────────────────────────────

def test_damaged_words_excluded_from_positional(corpus_data: CorpusData) -> None:
    """Words with has_damage=True must not contribute positional records
    (when exclude_damaged=True, the default).

    We verify this by counting: the number of positional-eligible words
    (undamaged, length >= 2) must match words_used_positional exactly,
    and no damaged-only sign sequence may appear in positional records.
    """
    # Count how many words are positional-eligible
    eligible_count = 0
    for insc in corpus_data.inscriptions:
        for word in insc.words:
            if not word.has_damage and len(word.sign_ids) >= 2:
                eligible_count += 1

    assert corpus_data.words_used_positional == eligible_count, (
        f"words_used_positional={corpus_data.words_used_positional} but "
        f"counted {eligible_count} eligible (undamaged, len>=2) words"
    )

    # Find sign sequences that ONLY appear in damaged words
    # (never in undamaged words within the same inscription).
    # These must be absent from positional records.
    from collections import defaultdict
    damaged_only_keys: set = set()
    undamaged_keys: set = set()
    for insc in corpus_data.inscriptions:
        for word in insc.words:
            key = (word.inscription_id, tuple(word.sign_ids))
            if word.has_damage:
                damaged_only_keys.add(key)
            else:
                undamaged_keys.add(key)

    # Remove keys that also appear undamaged — those legitimately have records
    damaged_only_keys -= undamaged_keys

    for rec in corpus_data.positional_records:
        key = (rec.inscription_id, tuple(rec.word_sign_ids))
        assert key not in damaged_only_keys, (
            f"Positional record from damaged-only word: {rec}"
        )


# ── Logogram exclusion ─────────────────────────────────────────────────

def test_logograms_excluded_from_sign_ids(corpus_data: CorpusData) -> None:
    """Only syllabograms should appear in Word.sign_ids; logograms,
    numerals, and unknowns must be filtered out."""
    for insc in corpus_data.inscriptions:
        for word in insc.words:
            for token in word.syllabogram_signs:
                assert token.sign_type == "syllabogram", (
                    f"Non-syllabogram {token.sign_id} ({token.sign_type}) "
                    f"found in sign_ids for word in {insc.id}"
                )


# ── Position labels ────────────────────────────────────────────────────

def test_position_labels_correct(corpus_data: CorpusData) -> None:
    """For a word of length 3, the first sign should be 'initial',
    the middle sign 'medial', and the last sign 'final'.

    Because the same sign sequence can appear multiple times in the same
    inscription, we verify per-record: each record's position label must
    be correct given its sign_id's index within word_sign_ids.
    """
    found_any = False
    for rec in corpus_data.positional_records:
        if len(rec.word_sign_ids) != 3:
            continue
        found_any = True

        # The record's sign_id should appear in its word_sign_ids.
        # Determine its position index.  The loader emits one record per
        # position, so sign_id corresponds to exactly one slot.  When a
        # sign appears more than once in the same word, we verify that
        # the position label is consistent with ANY valid index.
        valid_positions = set()
        for idx, sid in enumerate(rec.word_sign_ids):
            if sid == rec.sign_id:
                if idx == 0:
                    valid_positions.add("initial")
                elif idx == len(rec.word_sign_ids) - 1:
                    valid_positions.add("final")
                else:
                    valid_positions.add("medial")

        assert rec.position in valid_positions, (
            f"Record {rec} has position '{rec.position}' but valid positions "
            f"are {valid_positions} for sign {rec.sign_id} in word {rec.word_sign_ids}"
        )

    if not found_any:
        pytest.skip("No 3-sign words found in corpus")


# ── Bigram count consistency ──────────────────────────────────────────

def test_bigram_count_equals_word_length_minus_one(corpus_data: CorpusData) -> None:
    """For each word of length L (in syllabograms), exactly L-1 bigram
    records should be emitted.

    Because the same sign sequence can appear multiple times in the same
    inscription (different word_index), we verify at the aggregate level:
    total bigrams must equal sum of (word_len - 1) over all bigram-eligible
    words.
    """
    # Expected total: for every word with >=2 syllabograms, emit len-1 bigrams
    expected_total = 0
    for insc in corpus_data.inscriptions:
        for word in insc.words:
            sids = word.sign_ids
            if len(sids) >= 2:
                expected_total += len(sids) - 1

    actual_total = len(corpus_data.bigram_records)
    assert actual_total == expected_total, (
        f"Total bigrams emitted ({actual_total}) != sum of (word_len - 1) "
        f"over all eligible words ({expected_total})"
    )

    # Also verify each individual bigram record has a valid position_in_word
    for rec in corpus_data.bigram_records:
        assert 0 <= rec.position_in_word < len(rec.word_sign_ids) - 1, (
            f"Bigram record has position_in_word={rec.position_in_word} "
            f"but word has {len(rec.word_sign_ids)} signs"
        )
