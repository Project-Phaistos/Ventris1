"""Regression tests for bugs found by adversarial audit.

Each test reproduces a specific bug that was found and fixed, ensuring
the bug does not regress.

Tests:
  C3: test_suffix_scoring_prefers_longest_match
  C2: test_n_inflectional_counts_types_not_tokens
  C1: test_merge_groups_enforces_max_classes
  HIGH: test_all_stems_mapped_to_paradigms_not_just_examples
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Set, Tuple

import pytest

from pillar1.corpus_loader import CorpusData, Inscription, Word, SignToken
from pillar2.pillar1_loader import Pillar1Output
from pillar2.segmenter import (
    SegmentedLexicon,
    SegmentedWord,
    _suffix_strip_segment,
    _WordInfo,
    segment_corpus,
)
from pillar2.affix_extractor import AffixInventory, Affix, extract_affixes
from pillar2.paradigm_inducer import (
    induce_paradigms,
    _merge_groups,
    ParadigmTable,
)
from pillar2.inflection_classifier import classify_affixes
from pillar2.word_class_hinter import hint_word_classes, WordClassResult


# ---------------------------------------------------------------------------
# Helper: build a minimal Pillar1Output with no constraints
# ---------------------------------------------------------------------------

def _empty_pillar1(**overrides) -> Pillar1Output:
    """Create a Pillar1Output with no forbidden/favored bigrams."""
    defaults = dict(
        grid_assignments=[],
        consonant_count=0,
        vowel_count=0,
        grid_method="test",
        vowel_signs=[],
        vowel_sign_ids=[],
        forbidden_bigrams=[],
        favored_bigrams=[],
        sign_to_grid={},
        favored_bigram_set=set(),
        forbidden_bigram_set=set(),
        corpus_hash="",
        config_hash="",
        pillar1_hash="",
    )
    defaults.update(overrides)
    return Pillar1Output(**defaults)


def _make_word_info(
    words: list[tuple[tuple[str, ...], int]],
) -> dict[tuple[str, ...], _WordInfo]:
    """Build a word_info dict from (sign_tuple, frequency) pairs."""
    info = {}
    for sids, freq in words:
        info[sids] = _WordInfo(
            sign_ids=sids,
            frequency=freq,
            inscription_types=["votive"],
        )
    return info


# ===================================================================
# C3: Suffix scoring systematically prefers short suffixes
# ===================================================================

class TestSuffixScoringPrefersLongestMatch:
    """Bug C3: The old scoring formula n_stems * (1.0 + 0.1 * suf_len)
    meant that a high-frequency single-sign suffix always beat a
    multi-sign suffix with fewer stems.

    Fix: Greedy longest-match -- always prefer the longest valid
    suffix that passes boundary checks.
    """

    def test_suffix_scoring_prefers_longest_match(self):
        """Synthetic corpus where a 2-sign suffix ("B", "C") and a
        1-sign suffix ("C") both exist, but the 2-sign suffix is the
        correct segmentation.

        Words:
          ("S1", "B", "C") freq=2  -- stem=("S1",) suffix=("B","C")
          ("S2", "B", "C") freq=2  -- stem=("S2",) suffix=("B","C")
          ("S3", "B", "C") freq=2  -- stem=("S3",) suffix=("B","C")

        Plus many words ending in just "C" to make ("C",) highly frequent:
          ("X1", "C") freq=1
          ("X2", "C") freq=1
          ...20 of these => suffix ("C",) has 20 stems

        The 2-sign suffix ("B","C") has 3 stems, freq=6.
        The 1-sign suffix ("C",) has 23 stems (20 + 3), freq=26.

        Before the fix: ("C",) scored 23 * 1.1 = 25.3 while ("B","C")
        scored 3 * 1.2 = 3.6.  So ("C",) won and the segmentation
        was wrong.

        After the fix: greedy longest-match picks ("B","C") for words
        that end in B,C.
        """
        words = []
        # 3 words ending in "B","C" (the correct 2-sign suffix)
        for i in range(1, 4):
            words.append((("S" + str(i), "B", "C"), 2))

        # 20 words ending in "C" only (makes ("C",) high-frequency)
        for i in range(1, 21):
            words.append((("X" + str(i), "C"), 1))

        word_info = _make_word_info(words)
        p1 = _empty_pillar1()

        result = _suffix_strip_segment(
            word_info=word_info,
            pillar1=p1,
            min_suffix_frequency=3,
            min_suffix_stems=2,
            max_suffix_length=3,
            lambda_phon=1.0,
        )

        by_word = {tuple(w.word_sign_ids): w for w in result}

        # The key assertion: words ending in "B","C" should be
        # segmented with the LONGER suffix ("B","C"), not the
        # shorter ("C",).
        for i in range(1, 4):
            word_key = ("S" + str(i), "B", "C")
            seg = by_word[word_key]
            assert seg.suffixes == [["B", "C"]], (
                f"Word {word_key}: expected suffix ['B','C'] (longest match), "
                f"got {seg.suffixes}. The segmenter is still preferring "
                f"shorter high-frequency suffixes."
            )
            assert seg.stem == ["S" + str(i)], (
                f"Word {word_key}: expected stem ['S{i}'], got {seg.stem}"
            )

    def test_falls_back_to_shorter_when_longer_invalid(self):
        """When the longest suffix is blocked by a boundary check,
        the segmenter should fall back to a shorter valid suffix.
        """
        words = []
        # Words ending in "B","C" -- but boundary (stem[-1], B) will be forbidden
        for i in range(1, 4):
            words.append((("Z" + str(i), "B", "C"), 2))

        # Also make ("C",) valid with other stems
        for i in range(1, 6):
            words.append((("W" + str(i), "C"), 1))

        word_info = _make_word_info(words)

        # Forbid the bigram (Z*, B) -- since all Z-stems end in Zi,
        # we forbid all (Zi, B) pairs to block the 2-sign suffix
        forbidden = set()
        for i in range(1, 4):
            forbidden.add(("Z" + str(i), "B"))

        p1 = _empty_pillar1(forbidden_bigram_set=forbidden)

        result = _suffix_strip_segment(
            word_info=word_info,
            pillar1=p1,
            min_suffix_frequency=3,
            min_suffix_stems=2,
            max_suffix_length=3,
            lambda_phon=1.0,
        )

        by_word = {tuple(w.word_sign_ids): w for w in result}

        # The 2-sign suffix ("B","C") is blocked by boundary check,
        # so we should fall back to the 1-sign suffix ("C",).
        for i in range(1, 4):
            word_key = ("Z" + str(i), "B", "C")
            seg = by_word[word_key]
            assert seg.suffixes == [["C"]], (
                f"Word {word_key}: expected fallback suffix ['C'], "
                f"got {seg.suffixes}"
            )


# ===================================================================
# C2: n_inflectional counts tokens instead of types
# ===================================================================

class TestNInflectionalCountsTypesNotTokens:
    """Bug C2: The loop iterated over every word in the lexicon.
    If stem "A" appeared 5 times with suffix "-ta", n_inflectional
    got incremented 5 times. But n_total (from the suffixes set)
    correctly counted unique types.

    Fix: Track inflectional suffixes as a SET per stem.
    """

    def test_n_inflectional_counts_types_not_tokens(self):
        """Stem "A" appears 5 times with the same inflectional suffix "X".
        After the fix, n_inflectional should be 1 (one unique suffix
        type), not 5 (five tokens).
        """
        # Build a lexicon where stem ["A"] appears 5 times with suffix ["X"]
        words = []
        for _ in range(5):
            words.append(SegmentedWord(
                word_sign_ids=["A", "X"],
                stem=["A"],
                suffixes=[["X"]],
                prefixes=[],
                segmentation_confidence=0.5,
                frequency=1,
                inscription_types=["votive"],
                method="suffix_strip",
            ))
        lexicon = SegmentedLexicon(
            words=words, total_words=5, words_with_suffixes=5,
        )

        # Build an affix inventory where ("X",) is inflectional
        affix_x = Affix(
            signs=["X"],
            frequency=5,
            n_distinct_stems=1,
            productivity=1.0,
            classification="inflectional",
            paradigm_classes=[0],
        )
        affix_inv = AffixInventory(
            suffixes=[affix_x],
            prefixes=[],
            suffix_lookup={("X",): affix_x},
            prefix_lookup={},
        )

        # Build a minimal paradigm table
        from pillar2.paradigm_inducer import (
            Paradigm, ParadigmSlot, StemExample, ParadigmTable,
        )
        paradigm = Paradigm(
            class_id=0,
            n_members=1,
            slots=[ParadigmSlot(0, ["X"], 1, "slot_0")],
            example_stems=[StemExample(["A"], [0], [{"slot": 0, "full_word": ["A", "X"]}])],
            completeness=1.0,
            all_stems=[["A"]],
        )
        ptable = ParadigmTable(n_classes=1, paradigms=[paradigm])

        result = hint_word_classes(lexicon, affix_inv, ptable)

        # Find the hint for stem "A"
        a_hints = [h for h in result.stem_hints if h.stem == ["A"]]
        assert len(a_hints) == 1
        hint = a_hints[0]

        # The key assertion: n_inflectional_suffixes should count
        # unique types (1), not tokens (5)
        assert hint.n_inflectional_suffixes == 1, (
            f"Expected n_inflectional_suffixes=1 (one unique inflectional "
            f"suffix type), got {hint.n_inflectional_suffixes}. "
            f"The bug counted tokens instead of types."
        )

    def test_multiple_distinct_inflectional_suffixes(self):
        """Stem "A" with 2 distinct inflectional suffixes, each appearing
        3 times.  n_inflectional should be 2, not 6.
        """
        words = []
        for _ in range(3):
            words.append(SegmentedWord(
                word_sign_ids=["A", "X"],
                stem=["A"],
                suffixes=[["X"]],
                prefixes=[],
                segmentation_confidence=0.5,
                frequency=1,
                inscription_types=["votive"],
                method="suffix_strip",
            ))
            words.append(SegmentedWord(
                word_sign_ids=["A", "Y"],
                stem=["A"],
                suffixes=[["Y"]],
                prefixes=[],
                segmentation_confidence=0.5,
                frequency=1,
                inscription_types=["votive"],
                method="suffix_strip",
            ))
        lexicon = SegmentedLexicon(
            words=words, total_words=6, words_with_suffixes=6,
        )

        affix_x = Affix(
            signs=["X"], frequency=3, n_distinct_stems=1,
            productivity=1.0, classification="inflectional", paradigm_classes=[0],
        )
        affix_y = Affix(
            signs=["Y"], frequency=3, n_distinct_stems=1,
            productivity=1.0, classification="inflectional", paradigm_classes=[0],
        )
        affix_inv = AffixInventory(
            suffixes=[affix_x, affix_y],
            prefixes=[],
            suffix_lookup={("X",): affix_x, ("Y",): affix_y},
            prefix_lookup={},
        )

        from pillar2.paradigm_inducer import (
            Paradigm, ParadigmSlot, StemExample, ParadigmTable,
        )
        paradigm = Paradigm(
            class_id=0, n_members=1,
            slots=[
                ParadigmSlot(0, ["X"], 1, "slot_0"),
                ParadigmSlot(1, ["Y"], 1, "slot_1"),
            ],
            example_stems=[StemExample(["A"], [0, 1], [])],
            completeness=1.0,
            all_stems=[["A"]],
        )
        ptable = ParadigmTable(n_classes=1, paradigms=[paradigm])

        result = hint_word_classes(lexicon, affix_inv, ptable)
        a_hints = [h for h in result.stem_hints if h.stem == ["A"]]
        assert len(a_hints) == 1
        assert a_hints[0].n_inflectional_suffixes == 2, (
            f"Expected 2 distinct inflectional suffixes, "
            f"got {a_hints[0].n_inflectional_suffixes}"
        )


# ===================================================================
# C1: _merge_groups breaks before enforcing max_classes
# ===================================================================

class TestMergeGroupsEnforcesMaxClasses:
    """Bug C1: When best_sim < threshold AND len(groups) > max_classes,
    the elif fires before the merge logic, so max_classes is never
    enforced.

    Fix: Only break when BOTH best_sim < threshold AND
    len(groups) <= max_classes.
    """

    def test_merge_groups_enforces_max_classes(self):
        """Create 20 stems with fully disjoint suffix signatures (Jaccard=0
        between all pairs).  With threshold=0.3, no natural merges would
        happen.  But with max_classes=5, the algorithm must force-merge
        down to at most 5 groups.
        """
        # 20 groups with disjoint signatures
        sig_groups = []
        for i in range(20):
            sig = frozenset({f"suf_{i}"})  # unique suffix per group
            stems = [(f"stem_{i}",)]
            sig_groups.append((sig, stems))

        result = _merge_groups(sig_groups, threshold=0.3, max_classes=5)

        assert len(result) <= 5, (
            f"Expected <= 5 groups after enforcing max_classes=5, "
            f"got {len(result)}. The merge loop broke before "
            f"reaching max_classes."
        )

    def test_merge_groups_respects_threshold_when_within_max(self):
        """When groups are already within max_classes and best_sim < threshold,
        merging should stop.  3 groups with disjoint signatures,
        max_classes=5, threshold=0.3 -> no merging needed.
        """
        sig_groups = []
        for i in range(3):
            sig = frozenset({f"suf_{i}"})
            stems = [(f"stem_{i}",)]
            sig_groups.append((sig, stems))

        result = _merge_groups(sig_groups, threshold=0.3, max_classes=5)

        assert len(result) == 3, (
            f"Expected 3 groups (no merging needed), got {len(result)}"
        )

    def test_merge_groups_exact_max_classes(self):
        """10 groups, max_classes=3.  Should merge down to exactly 3."""
        sig_groups = []
        for i in range(10):
            sig = frozenset({f"suf_{i}"})
            stems = [(f"stem_{i}",)]
            sig_groups.append((sig, stems))

        result = _merge_groups(sig_groups, threshold=0.3, max_classes=3)

        assert len(result) <= 3, (
            f"Expected <= 3 groups with max_classes=3, got {len(result)}"
        )


# ===================================================================
# HIGH: Only 5 example stems per paradigm mapped to word classes
# ===================================================================

class TestAllStemsMappedToParadigmsNotJustExamples:
    """Bug HIGH: stem_paradigms only mapped the example_stems (up to 5)
    from each paradigm, not ALL stems.  Stems #6+ got wrong or missing
    paradigm mappings.

    Fix: Added all_stems field to Paradigm and use it in word_class_hinter.
    """

    def test_all_stems_mapped_to_paradigms_not_just_examples(self):
        """Create a paradigm with 10 stems, verify all 10 (not just 5)
        are correctly mapped to the paradigm class.
        """
        # Build a lexicon with 10 stems, each taking 2 suffixes
        stems = [f"stem_{i}" for i in range(10)]
        suffixes = ["X", "Y"]

        words = []
        for stem in stems:
            for suf in suffixes:
                words.append(SegmentedWord(
                    word_sign_ids=[stem, suf],
                    stem=[stem],
                    suffixes=[[suf]],
                    prefixes=[],
                    segmentation_confidence=0.5,
                    frequency=2,
                    inscription_types=["votive"],
                    method="suffix_strip",
                ))
        lexicon = SegmentedLexicon(
            words=words, total_words=len(words), words_with_suffixes=len(words),
        )

        # Extract affixes
        affix_inv = extract_affixes(lexicon, min_affix_stems=2)

        # Make sure both suffixes are marked as inflectional
        for affix in affix_inv.suffixes:
            affix.classification = "inflectional"

        # Induce paradigms
        p1 = _empty_pillar1()
        ptable = induce_paradigms(
            lexicon, affix_inv, p1,
            jaccard_threshold=0.3,
            min_paradigm_members=2,
            min_paradigm_slots=2,
        )

        assert ptable.n_classes >= 1, "Expected at least 1 paradigm class"

        # The paradigm should have all 10 stems
        paradigm = ptable.paradigms[0]
        assert paradigm.n_members == 10, (
            f"Expected 10 members, got {paradigm.n_members}"
        )

        # Key check: all_stems should contain all 10, not just 5
        assert len(paradigm.all_stems) == 10, (
            f"Expected all_stems to have 10 entries, "
            f"got {len(paradigm.all_stems)}"
        )

        # Now run classify_affixes first (needed by hint_word_classes)
        classify_affixes(affix_inv, ptable)

        # Run word class hinting
        result = hint_word_classes(lexicon, affix_inv, ptable)

        # Find all hints for our 10 stems
        mapped_stems = set()
        for hint in result.stem_hints:
            stem_key = tuple(hint.stem)
            if stem_key[0].startswith("stem_"):
                mapped_stems.add(stem_key)
                # Each stem should have paradigm_classes populated
                assert len(hint.paradigm_classes) > 0, (
                    f"Stem {hint.stem} has no paradigm_classes -- "
                    f"it was not mapped to any paradigm. "
                    f"This suggests only example_stems (first 5) were mapped."
                )

        # All 10 stems should be present and mapped
        assert len(mapped_stems) == 10, (
            f"Expected 10 stems with paradigm mappings, "
            f"got {len(mapped_stems)}. Missing: "
            f"{set((f'stem_{i}',) for i in range(10)) - mapped_stems}"
        )

    def test_example_stems_limited_to_5(self):
        """Verify that example_stems is still limited to 5 (display purpose)
        while all_stems contains all members.
        """
        stems = [f"s{i}" for i in range(12)]
        words = []
        for stem in stems:
            for suf in ["X", "Y"]:
                words.append(SegmentedWord(
                    word_sign_ids=[stem, suf],
                    stem=[stem],
                    suffixes=[[suf]],
                    prefixes=[],
                    segmentation_confidence=0.5,
                    frequency=2,
                    inscription_types=["votive"],
                    method="suffix_strip",
                ))
        lexicon = SegmentedLexicon(
            words=words, total_words=len(words), words_with_suffixes=len(words),
        )
        affix_inv = extract_affixes(lexicon, min_affix_stems=2)
        p1 = _empty_pillar1()
        ptable = induce_paradigms(
            lexicon, affix_inv, p1,
            jaccard_threshold=0.3,
            min_paradigm_members=2,
            min_paradigm_slots=2,
        )

        assert ptable.n_classes >= 1
        paradigm = ptable.paradigms[0]

        # example_stems should be capped at 5
        assert len(paradigm.example_stems) <= 5, (
            f"example_stems should be <= 5, got {len(paradigm.example_stems)}"
        )
        # all_stems should have all 12
        assert len(paradigm.all_stems) == 12, (
            f"all_stems should have 12, got {len(paradigm.all_stems)}"
        )
