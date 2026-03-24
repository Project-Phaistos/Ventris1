"""Integration tests on the REAL Linear A corpus.

These tests run the Pillar 2 pipeline on the actual SigLA Full Linear A
corpus and verify that the results are consistent with known properties
of Linear A.

All pipeline stages are run once (via session-scoped conftest fixtures)
and shared across tests.

Known properties of Linear A (from the literature):
  - The most frequent word-final signs are: AB27 (re), AB60 (ra),
    AB37 (ti), AB57 (ja), AB06 (na), AB59 (ta), AB04 (te)
  - Linear A has some inflectional morphology (not purely isolating)
  - Pillar 1 identifies favored bigrams that should not be split
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict

import pytest

from pillar1.corpus_loader import CorpusData
from pillar2.pillar1_loader import Pillar1Output
from pillar2.segmenter import SegmentedLexicon
from pillar2.affix_extractor import AffixInventory
from pillar2.paradigm_inducer import ParadigmTable
from pillar2.word_class_hinter import WordClassResult


# Known frequent final signs in Linear A (AB codes)
KNOWN_FREQUENT_FINALS = {"AB27", "AB60", "AB37", "AB57", "AB06", "AB59", "AB04"}


def test_real_corpus_pipeline_runs(
    real_lexicon: SegmentedLexicon,
    real_affix_inv: AffixInventory,
    real_paradigm_table: ParadigmTable,
    real_classified_inv: AffixInventory,
    real_word_classes: WordClassResult,
) -> None:
    """The full pipeline completes without error on the real corpus.

    This test simply forces all session-scoped fixtures to execute.
    If any stage raises an exception, the test fails.
    """
    assert real_lexicon.total_words > 0, "Lexicon is empty"
    assert len(real_affix_inv.suffixes) > 0, "No suffixes found"
    assert real_paradigm_table.n_classes > 0, "No paradigm classes"
    assert len(real_classified_inv.suffixes) > 0, "No classified suffixes"
    assert len(real_word_classes.stem_hints) > 0, "No word-class hints"


def test_real_corpus_top_suffixes_match_known_finals(
    real_affix_inv: AffixInventory,
) -> None:
    """Top 5 suffixes overlap with known frequent final signs.

    The known frequent final signs of Linear A (AB27/re, AB60/ra,
    AB37/ti, AB57/ja, AB06/na, AB59/ta, AB04/te) should appear among
    the top 5 suffixes discovered by the pipeline.

    We require at least 3 of the top 5 suffix sign IDs to be in the
    known set.
    """
    top5 = real_affix_inv.suffixes[:5]
    top5_sign_ids = set()
    for affix in top5:
        top5_sign_ids.update(affix.signs)

    overlap = top5_sign_ids & KNOWN_FREQUENT_FINALS
    assert len(overlap) >= 3, (
        f"Expected >= 3 of the top-5 suffix signs to be known finals, "
        f"got {len(overlap)}: {overlap}. "
        f"Top 5 suffixes: {[a.signs for a in top5]}. "
        f"Known finals: {KNOWN_FREQUENT_FINALS}"
    )


def test_real_corpus_paradigm_count_in_range(
    real_paradigm_table: ParadigmTable,
) -> None:
    """Between 2 and 50 paradigm classes.

    Linear A is not well understood, so we use a wide range. The lower
    bound (2) ensures the pipeline finds some structure. The upper bound
    (50) guards against the paradigm inducer creating one class per stem.
    """
    n = real_paradigm_table.n_classes
    assert 2 <= n <= 50, (
        f"Expected 2-50 paradigm classes, got {n}. "
        f"Sizes: {[p.n_members for p in real_paradigm_table.paradigms]}"
    )


def test_real_corpus_has_declining_stems(
    real_word_classes: WordClassResult,
) -> None:
    """At least some stems classified as declining.

    Linear A shows evidence of inflectional morphology (recurring
    endings like -re, -ja, -ti that alternate on the same stems).
    The word-class hinter should classify at least some stems as
    'declining'.
    """
    declining = sum(
        1 for h in real_word_classes.stem_hints if h.label == "declining"
    )
    total = len(real_word_classes.stem_hints)
    assert declining > 0, (
        f"No stems classified as declining (total={total}). "
        f"Labels: {_count_labels(real_word_classes)}"
    )
    # At least 10% should be declining (generous lower bound)
    pct = declining / total
    assert pct >= 0.10, (
        f"Only {pct:.1%} of stems declining ({declining}/{total}), "
        f"expected >= 10%. Labels: {_count_labels(real_word_classes)}"
    )


def test_real_corpus_no_segmentation_violates_favored_bigrams(
    real_lexicon: SegmentedLexicon,
    real_pillar1: Pillar1Output,
) -> None:
    """No segmentation splits a favored bigram from Pillar 1.

    Favored bigrams are sign pairs that co-occur significantly more
    often than expected. The segmenter should respect these as
    within-morpheme pairs and never place a morpheme boundary between
    them.
    """
    if not real_pillar1.favored_bigram_set:
        pytest.skip("No favored bigrams in Pillar 1 output")

    violations = []
    for word in real_lexicon.words:
        if not word.suffixes:
            continue
        stem = tuple(word.stem)
        for suffix in word.suffixes:
            suf_tuple = tuple(suffix)
            if stem and suf_tuple:
                boundary_pair = (stem[-1], suf_tuple[0])
                if boundary_pair in real_pillar1.favored_bigram_set:
                    violations.append({
                        "word": word.word_sign_ids,
                        "stem": list(stem),
                        "suffix": list(suf_tuple),
                        "boundary": boundary_pair,
                    })

    assert len(violations) == 0, (
        f"Found {len(violations)} segmentations that split a favored "
        f"bigram. First 5: {violations[:5]}"
    )


# -- Helper ----------------------------------------------------------------

def _count_labels(wc_result: WordClassResult) -> Dict[str, int]:
    """Count stems by label."""
    counts: Dict[str, int] = defaultdict(int)
    for h in wc_result.stem_hints:
        counts[h.label] += 1
    return dict(counts)
