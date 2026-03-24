"""Tier 2: Known-language end-to-end tests -- Latin CV syllabary corpus.

These tests verify that Pillar 2's morphological analysis pipeline
recovers known Latin declension patterns from a corpus of Latin nouns
transliterated into an artificial CV syllabary.

Latin encoding:
  a=LA01, b=LA02, c=LA03, d=LA04, e=LA05, f=LA06, g=LA07, h=LA08,
  i=LA09, k=LA10, l=LA11, m=LA12, n=LA13, o=LA14, p=LA15, q=LA16,
  r=LA17, s=LA18, t=LA19, u=LA20, v=LA21, x=LA22

Expected AB-code suffixes for Latin case endings:
    -a   = [LA01]
    -ae  = [LA01, LA05]
    -am  = [LA01, LA12]
    -us  = [LA20, LA18]
    -um  = [LA20, LA12]
    -i   = [LA09]
    -o   = [LA14]
    -is  = [LA09, LA18]
    -em  = [LA05, LA12]
    -s   = [LA18]
    -m   = [LA12]
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Set, Tuple

import pytest

from pillar1.corpus_loader import CorpusData
from pillar2.segmenter import SegmentedLexicon
from pillar2.affix_extractor import AffixInventory
from pillar2.paradigm_inducer import ParadigmTable
from pillar2.word_class_hinter import WordClassResult


# -- Known Latin suffixes in AB-code form ----------------------------------

KNOWN_SUFFIX_SIGN_IDS = {
    # Single-sign case endings (the most productive)
    "LA18",  # -s  (nom sg 2nd/3rd/4th)
    "LA12",  # -m  (acc sg, all decls)
    "LA09",  # -i  (gen sg 2nd, dat sg 3rd, nom pl 2nd)
    "LA14",  # -o  (dat/abl sg 2nd)
    "LA05",  # -e  (voc 2nd, abl 3rd)
    "LA01",  # -a  (nom/voc sg 1st)
}

KNOWN_SUFFIX_TUPLES = {
    ("LA18",),         # -s
    ("LA12",),         # -m
    ("LA09",),         # -i
    ("LA14",),         # -o
    ("LA05",),         # -e
    ("LA01",),         # -a
    ("LA01", "LA05"),  # -ae
    ("LA01", "LA12"),  # -am
    ("LA20", "LA18"),  # -us
    ("LA20", "LA12"),  # -um
    ("LA09", "LA18"),  # -is
    ("LA05", "LA12"),  # -em
    ("LA22",),         # -x
}


# ==========================================================================
# Test 1: Corpus sanity
# ==========================================================================

def test_latin_corpus_has_enough_data(latin_corpus: CorpusData) -> None:
    """Sanity check: the Latin corpus has >= 150 words and >= 60 inscriptions."""
    assert latin_corpus.total_words >= 150, (
        f"Expected >= 150 words, got {latin_corpus.total_words}"
    )
    assert latin_corpus.total_inscriptions >= 60, (
        f"Expected >= 60 inscriptions, got {latin_corpus.total_inscriptions}"
    )


# ==========================================================================
# Test 2: Known suffix detection
# ==========================================================================

def test_latin_identifies_known_suffixes(
    latin_affix_inv: AffixInventory,
) -> None:
    """At least 3 of the expected Latin suffixes appear in the suffix inventory."""
    discovered = {tuple(a.signs) for a in latin_affix_inv.suffixes}
    overlap = discovered & KNOWN_SUFFIX_TUPLES

    matched_names = []
    for suf in sorted(overlap):
        matched_names.append("-".join(suf))

    assert len(overlap) >= 3, (
        f"Only {len(overlap)} known Latin suffixes found in inventory: "
        f"{matched_names}. Expected >= 3 from {len(KNOWN_SUFFIX_TUPLES)} known. "
        f"Discovered suffixes: {[a.signs for a in latin_affix_inv.suffixes]}"
    )


# ==========================================================================
# Test 3: Paradigm count in range
# ==========================================================================

def test_latin_paradigm_count_in_range(
    latin_paradigm_table: ParadigmTable,
) -> None:
    """Number of paradigm classes is between 2 and 15.

    Latin has 5 declension classes, but the segmenter may merge or split
    them. The range [2, 15] allows for imperfect recovery.  The upper
    bound matches max_paradigm_classes (default=15).  Greedy longest-match
    suffix selection may produce finer-grained paradigm splits.
    """
    n = latin_paradigm_table.n_classes
    assert 2 <= n <= 15, (
        f"Expected 2-15 paradigm classes, got {n}. "
        f"Sizes: {[p.n_members for p in latin_paradigm_table.paradigms]}"
    )


# ==========================================================================
# Test 4: At least one paradigm has multiple slots
# ==========================================================================

def test_latin_paradigm_has_multiple_slots(
    latin_paradigm_table: ParadigmTable,
) -> None:
    """At least one paradigm has >= 3 slots.

    Latin declensions have 5-6 case forms. Finding >= 3 slots in at least
    one paradigm confirms the system detects multiple case endings for a
    single declension class.
    """
    max_slots = max(
        len(p.slots) for p in latin_paradigm_table.paradigms
    )
    assert max_slots >= 3, (
        f"Expected at least one paradigm with >= 3 slots, "
        f"max found was {max_slots}. "
        f"Paradigms: {[(p.class_id, len(p.slots)) for p in latin_paradigm_table.paradigms]}"
    )


# ==========================================================================
# Test 5: Top productive suffixes are inflectional
# ==========================================================================

def test_latin_high_productivity_suffixes_are_inflectional(
    latin_classified_inv: AffixInventory,
) -> None:
    """Top-3 most productive suffixes classified as inflectional.

    The most productive suffixes in the Latin corpus (by n_distinct_stems)
    are the case endings -m, -s, -i. These should be classified as
    inflectional, not derivational.
    """
    top3 = latin_classified_inv.suffixes[:3]
    assert len(top3) == 3, f"Expected >= 3 suffixes, got {len(top3)}"
    for affix in top3:
        assert affix.classification == "inflectional", (
            f"Suffix {affix.signs} (prod={affix.productivity:.3f}, "
            f"stems={affix.n_distinct_stems}) classified as "
            f"{affix.classification!r}, expected 'inflectional'"
        )


# ==========================================================================
# Test 6: Most stems are declining
# ==========================================================================

def test_latin_most_stems_are_declining(
    latin_word_classes: WordClassResult,
) -> None:
    """> 50% of stems classified as 'declining'.

    The Latin corpus is entirely inflected nouns, so the majority should
    be classified as declining (taking paradigmatic suffixes).
    """
    total = len(latin_word_classes.stem_hints)
    assert total > 0, "No stem hints produced at all"

    declining = sum(
        1 for h in latin_word_classes.stem_hints if h.label == "declining"
    )
    pct = declining / total
    assert pct > 0.50, (
        f"Expected > 50% declining stems, got {declining}/{total} = {pct:.1%}. "
        f"Label distribution: {_count_labels(latin_word_classes)}"
    )


# -- Helper ----------------------------------------------------------------

def _count_labels(wc_result: WordClassResult) -> Dict[str, int]:
    """Count stems by label."""
    counts: Dict[str, int] = defaultdict(int)
    for h in wc_result.stem_hints:
        counts[h.label] += 1
    return dict(counts)
