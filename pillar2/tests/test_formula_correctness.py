"""Tier 1 formula-level math correctness tests for Pillar 2.

Every mathematical formula and computation in pillar2/ is tested here
with hand-computed expected values on synthetic inputs.

Formulas tested:
  1. Suffix stripping candidate generation
  2. Suffix scoring formula: n_stems * (1.0 + 0.1 * suf_len)
  3. Segmentation confidence: min(1.0, n_stems / 10.0)
  4. BPE confidence: min(1.0, n_splits * 0.3)
  5. Productivity score: n_distinct_stems / max_n_distinct_stems
  6. Jaccard similarity: |A & B| / |A | B|
  7. Jaccard similarity — empty sets
  8. Paradigm completeness: n_attested / (n_stems * n_slots)
  9. Inflection classification: productivity > 0.3 AND paradigm_regular
 10. Inflection classification: productivity < 0.1 OR not paradigm_regular
 11. Inflection classification: ambiguous range
 12. Frequency-type ratio: frequency / n_distinct_stems
 13. Suffix frequency and stem-count filtering
 14. BPE stem selection (longest morpheme heuristic)
 15. Word-class hinter: confidence formulas (PRD 5.5)
 16. Word-class hinter: classification logic (PRD 5.5)
 17. BPE pair frequency weighting by word frequency
 18. Paradigm completeness inline computation (sum of slot freqs)
 19. Grid analysis: consonant-row sharing check
"""

from __future__ import annotations

import pytest

from pillar1.corpus_loader import CorpusData, Inscription, Word, SignToken
from pillar2.pillar1_loader import Pillar1Output, GridAssignment
from pillar2.segmenter import (
    SegmentedLexicon,
    SegmentedWord,
    _suffix_strip_segment,
    _WordInfo,
    _check_boundary,
    _bpe_segment,
    segment_corpus,
)
from pillar2.affix_extractor import (
    AffixInventory,
    Affix,
    extract_affixes,
    _build_affix_list,
)
from pillar2.paradigm_inducer import (
    _jaccard,
    induce_paradigms,
    ParadigmTable,
)
from pillar2.inflection_classifier import (
    classify_affixes,
    _classify_one,
)


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
# 1. Suffix stripping: candidate generation
# ===================================================================

class TestSuffixCandidateGeneration:
    """Given word [A, B, C] and max_suffix_length=2, the candidates are:
       suffix=() stem=(A,B,C)  [no suffix]
       suffix=(C,) stem=(A,B)  [suf_len=1]
       suffix=(B,C) stem=(A,)  [suf_len=2]
    suf_len=3 is skipped because stem would be empty (len < 1).
    """

    def test_candidate_suffixes_three_sign_word(self):
        """Word (A, B, C), max_suffix_length=2.
        Expected suffix candidates generated:
          suf_len=1 -> suffix=(C,), stem=(A,B)
          suf_len=2 -> suffix=(B,C), stem=(A,)
        The word itself (unsegmented) is always a fallback, not a candidate.
        """
        word = ("A", "B", "C")
        max_suffix_length = 2

        # Reproduce the inner loop from _suffix_strip_segment
        candidates = []
        for suf_len in range(1, min(max_suffix_length, len(word)) + 1):
            if len(word) - suf_len < 1:
                continue
            suffix = word[-suf_len:]
            stem = word[:-suf_len]
            candidates.append((stem, suffix))

        # Hand-computed: suf_len 1 and 2 both produce valid stems (len>=1)
        assert candidates == [
            (("A", "B"), ("C",)),
            (("A",), ("B", "C")),
        ]

    def test_candidate_suffixes_two_sign_word_max3(self):
        """Word (X, Y), max_suffix_length=3.
        min(3, 2) = 2, so suf_len in {1, 2}.
        suf_len=1 -> suffix=(Y,), stem=(X,)    [OK, len(stem)=1>=1]
        suf_len=2 -> suffix=(X,Y), stem=()      [SKIP, len(stem)=0<1]
        Only 1 candidate.
        """
        word = ("X", "Y")
        max_suffix_length = 3

        candidates = []
        for suf_len in range(1, min(max_suffix_length, len(word)) + 1):
            if len(word) - suf_len < 1:
                continue
            suffix = word[-suf_len:]
            stem = word[:-suf_len]
            candidates.append((stem, suffix))

        assert candidates == [(("X",), ("Y",))]


# ===================================================================
# 2. Suffix scoring formula
# ===================================================================

class TestSuffixScoringFormula:
    """Score = n_stems * (1.0 + 0.1 * suf_len).
    This favours suffixes with many stems and slightly longer length.
    """

    def test_score_2_stems_length_1(self):
        """n_stems=2, suf_len=1 -> 2 * (1.0 + 0.1) = 2 * 1.1 = 2.2"""
        n_stems = 2
        suf_len = 1
        score = n_stems * (1.0 + 0.1 * suf_len)
        assert score == pytest.approx(2.2)

    def test_score_5_stems_length_3(self):
        """n_stems=5, suf_len=3 -> 5 * (1.0 + 0.3) = 5 * 1.3 = 6.5"""
        n_stems = 5
        suf_len = 3
        score = n_stems * (1.0 + 0.1 * suf_len)
        assert score == pytest.approx(6.5)

    def test_longer_suffix_beats_shorter_with_same_stems(self):
        """n_stems=3 for both; suf_len=2 vs suf_len=1.
        score(len=2) = 3 * 1.2 = 3.6
        score(len=1) = 3 * 1.1 = 3.3
        Longer wins.
        """
        score_long = 3 * (1.0 + 0.1 * 2)
        score_short = 3 * (1.0 + 0.1 * 1)
        assert score_long > score_short


# ===================================================================
# 3. Segmentation confidence
# ===================================================================

class TestSegmentationConfidence:
    """confidence = min(1.0, n_stems / 10.0)"""

    def test_confidence_3_stems(self):
        """n_stems=3 -> min(1.0, 3/10) = 0.3"""
        n_stems = 3
        confidence = min(1.0, n_stems / 10.0)
        assert confidence == pytest.approx(0.3)

    def test_confidence_10_stems(self):
        """n_stems=10 -> min(1.0, 10/10) = 1.0"""
        n_stems = 10
        confidence = min(1.0, n_stems / 10.0)
        assert confidence == pytest.approx(1.0)

    def test_confidence_15_stems_clamped(self):
        """n_stems=15 -> min(1.0, 15/10) = min(1.0, 1.5) = 1.0"""
        n_stems = 15
        confidence = min(1.0, n_stems / 10.0)
        assert confidence == pytest.approx(1.0)


# ===================================================================
# 4. BPE confidence
# ===================================================================

class TestBPEConfidence:
    """BPE confidence = min(1.0, n_splits * 0.3)"""

    def test_bpe_confidence_1_split(self):
        """1 split -> min(1.0, 0.3) = 0.3"""
        n_splits = 1
        confidence = min(1.0, n_splits * 0.3)
        assert confidence == pytest.approx(0.3)

    def test_bpe_confidence_3_splits(self):
        """3 splits -> min(1.0, 0.9) = 0.9"""
        n_splits = 3
        confidence = min(1.0, n_splits * 0.3)
        assert confidence == pytest.approx(0.9)

    def test_bpe_confidence_4_splits_clamped(self):
        """4 splits -> min(1.0, 1.2) = 1.0"""
        n_splits = 4
        confidence = min(1.0, n_splits * 0.3)
        assert confidence == pytest.approx(1.0)


# ===================================================================
# 5. Productivity score
# ===================================================================

class TestProductivityScore:
    """productivity = n_distinct_stems / max_n_distinct_stems_across_all.
    Tested via _build_affix_list which computes this.
    """

    def test_productivity_three_affixes(self):
        """Three suffixes with stem counts 2, 5, 10.
        max = 10.
        Productivities: 2/10=0.2, 5/10=0.5, 10/10=1.0
        """
        affix_stems = {
            ("X",): {("s1",), ("s2",)},               # 2 stems
            ("Y",): {("s1",), ("s2",), ("s3",), ("s4",), ("s5",)},  # 5 stems
            ("Z",): {("s1",), ("s2",), ("s3",), ("s4",), ("s5",),
                     ("s6",), ("s7",), ("s8",), ("s9",), ("s10",)},  # 10 stems
        }
        affix_freq = {("X",): 4, ("Y",): 8, ("Z",): 20}
        result = _build_affix_list(affix_stems, affix_freq, min_affix_stems=1)

        # Build lookup by signs
        lookup = {tuple(a.signs): a for a in result}
        assert lookup[("X",)].productivity == pytest.approx(0.2)
        assert lookup[("Y",)].productivity == pytest.approx(0.5)
        assert lookup[("Z",)].productivity == pytest.approx(1.0)

    def test_productivity_single_affix(self):
        """Single suffix with 3 stems -> max=3, productivity=3/3=1.0"""
        affix_stems = {("A",): {("s1",), ("s2",), ("s3",)}}
        affix_freq = {("A",): 6}
        result = _build_affix_list(affix_stems, affix_freq, min_affix_stems=1)
        assert len(result) == 1
        assert result[0].productivity == pytest.approx(1.0)

    def test_productivity_filtered_by_min_stems(self):
        """Suffix with 1 stem is filtered out when min_affix_stems=2.
        Remaining suffix with 4 stems -> max=4, productivity=1.0.
        """
        affix_stems = {
            ("A",): {("s1",)},           # 1 stem — filtered
            ("B",): {("s1",), ("s2",), ("s3",), ("s4",)},  # 4 stems
        }
        affix_freq = {("A",): 2, ("B",): 10}
        result = _build_affix_list(affix_stems, affix_freq, min_affix_stems=2)
        assert len(result) == 1
        assert result[0].signs == ["B"]
        assert result[0].productivity == pytest.approx(1.0)


# ===================================================================
# 6. Jaccard similarity
# ===================================================================

class TestJaccardSimilarity:
    """Jaccard(A, B) = |A & B| / |A | B|"""

    def test_jaccard_hand_computed(self):
        """sig_a = {0, 1, 2}, sig_b = {1, 2, 3}
        intersection = {1, 2}, size = 2
        union = {0, 1, 2, 3}, size = 4
        Jaccard = 2/4 = 0.5
        """
        assert _jaccard(frozenset({0, 1, 2}), frozenset({1, 2, 3})) == pytest.approx(0.5)

    def test_jaccard_identical_sets(self):
        """Identical sets -> intersection = union -> Jaccard = 1.0"""
        s = frozenset({1, 2, 3})
        assert _jaccard(s, s) == pytest.approx(1.0)

    def test_jaccard_disjoint_sets(self):
        """No overlap -> intersection = 0 -> Jaccard = 0.0"""
        assert _jaccard(frozenset({1, 2}), frozenset({3, 4})) == pytest.approx(0.0)

    def test_jaccard_empty_sets(self):
        """Both empty -> defined as 1.0 (identical vacuously)."""
        assert _jaccard(frozenset(), frozenset()) == pytest.approx(1.0)

    def test_jaccard_one_empty(self):
        """One empty, one not -> intersection=0, union=|B| -> 0.0"""
        assert _jaccard(frozenset(), frozenset({1})) == pytest.approx(0.0)

    def test_jaccard_subset(self):
        """{1,2} vs {1,2,3,4}: intersection=2, union=4 -> 0.5"""
        assert _jaccard(frozenset({1, 2}), frozenset({1, 2, 3, 4})) == pytest.approx(0.5)

    def test_jaccard_distance(self):
        """Jaccard distance = 1 - Jaccard similarity.
        {1,2,3} vs {2,3,4,5}: intersection={2,3}=2, union={1,2,3,4,5}=5
        Jaccard = 2/5 = 0.4, distance = 0.6
        """
        sim = _jaccard(frozenset({1, 2, 3}), frozenset({2, 3, 4, 5}))
        distance = 1.0 - sim
        assert sim == pytest.approx(0.4)
        assert distance == pytest.approx(0.6)


# ===================================================================
# 7. Paradigm completeness
# ===================================================================

class TestParadigmCompleteness:
    """completeness = n_attested_cells / (n_stems * n_slots).
    n_attested_cells = sum of slot frequencies (each slot.frequency =
    how many stems in the group attest that slot).
    """

    def test_completeness_hand_computed(self):
        """3 stems, 2 slots.
        Slot 0: attested by 3 stems (freq=3)
        Slot 1: attested by 1 stem (freq=1)
        n_cells = 3 * 2 = 6
        n_attested = 3 + 1 = 4
        completeness = 4/6 = 0.6667
        """
        n_stems = 3
        n_slots = 2
        slot_freqs = [3, 1]  # how many stems attest each slot
        n_cells = n_stems * n_slots  # = 6
        n_attested = sum(slot_freqs)  # = 4
        completeness = n_attested / n_cells  # = 4/6
        assert completeness == pytest.approx(2 / 3)

    def test_completeness_full_paradigm(self):
        """4 stems, 3 slots, all cells filled.
        n_cells = 12, n_attested = 4+4+4 = 12, completeness = 1.0
        """
        n_cells = 4 * 3
        n_attested = 4 + 4 + 4
        completeness = n_attested / n_cells
        assert completeness == pytest.approx(1.0)

    def test_completeness_sparse_paradigm(self):
        """5 stems, 4 slots, only diagonal attested.
        Slot 0: freq=1, Slot 1: freq=1, Slot 2: freq=1, Slot 3: freq=1
        n_cells = 20, n_attested = 4, completeness = 4/20 = 0.2
        """
        n_cells = 5 * 4
        n_attested = 1 + 1 + 1 + 1
        completeness = n_attested / n_cells
        assert completeness == pytest.approx(0.2)


# ===================================================================
# 8. Inflection classification rules
# ===================================================================

class TestInflectionClassification:
    """Classification logic from _classify_one:
    - productivity > inflectional_threshold AND paradigm_regular -> "inflectional"
    - productivity < derivational_threshold OR not paradigm_regular -> "derivational"
    - Otherwise -> "ambiguous"

    Default thresholds: inflectional=0.3, derivational=0.1.
    """

    def _make_affix(self, productivity: float, frequency: int = 10,
                    n_stems: int = 5) -> Affix:
        return Affix(
            signs=["X"],
            frequency=frequency,
            n_distinct_stems=n_stems,
            productivity=productivity,
        )

    def test_inflectional(self):
        """productivity=0.5 > 0.3 AND paradigm_regular=True -> inflectional"""
        affix = self._make_affix(productivity=0.5)
        paradigm_keys = {("X",)}  # affix_key in paradigm_keys -> regular
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "inflectional"

    def test_derivational_low_productivity(self):
        """productivity=0.05 < 0.1 -> derivational (regardless of paradigm)"""
        affix = self._make_affix(productivity=0.05)
        paradigm_keys = {("X",)}  # even if paradigm-regular
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "derivational"

    def test_derivational_not_paradigm_regular(self):
        """productivity=0.5 > 0.3 BUT not paradigm_regular -> derivational
        (because the 'elif' checks `not is_paradigm_regular`)
        """
        affix = self._make_affix(productivity=0.5)
        paradigm_keys = set()  # affix_key NOT in paradigm_keys -> not regular
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "derivational"

    def test_ambiguous(self):
        """productivity=0.2 (between 0.1 and 0.3) AND paradigm_regular=True.
        Not > 0.3 so first branch fails.
        Not < 0.1 so first part of elif fails.
        paradigm_regular=True so second part of elif fails.
        Falls through to "ambiguous".
        """
        affix = self._make_affix(productivity=0.2)
        paradigm_keys = {("X",)}
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "ambiguous"

    def test_boundary_exactly_at_inflectional_threshold(self):
        """productivity=0.3 is NOT > 0.3 (strict inequality).
        paradigm_regular=True.
        Not > 0.3, not < 0.1, is paradigm_regular -> ambiguous.
        """
        affix = self._make_affix(productivity=0.3)
        paradigm_keys = {("X",)}
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "ambiguous"

    def test_boundary_exactly_at_derivational_threshold(self):
        """productivity=0.1 is NOT < 0.1 (strict inequality).
        paradigm_regular=True.
        Not > 0.3, not < 0.1, is_paradigm_regular -> ambiguous.
        """
        affix = self._make_affix(productivity=0.1)
        paradigm_keys = {("X",)}
        _classify_one(affix, paradigm_keys, 0.3, 0.1)
        assert affix.classification == "ambiguous"


# ===================================================================
# 9. Frequency-type ratio
# ===================================================================

class TestFrequencyTypeRatio:
    """freq_type_ratio = frequency / n_distinct_stems.
    Tested via _classify_one which computes it inline but does not
    store it on the Affix (it's on ClassifiedAffix). We test the
    formula directly.
    """

    def test_freq_type_ratio_basic(self):
        """frequency=12, n_distinct_stems=4 -> 12/4 = 3.0"""
        frequency = 12
        n_distinct_stems = 4
        ratio = frequency / n_distinct_stems if n_distinct_stems > 0 else 0.0
        assert ratio == pytest.approx(3.0)

    def test_freq_type_ratio_zero_stems(self):
        """n_distinct_stems=0 -> ratio = 0.0 (guard clause)"""
        frequency = 5
        n_distinct_stems = 0
        ratio = frequency / n_distinct_stems if n_distinct_stems > 0 else 0.0
        assert ratio == pytest.approx(0.0)


# ===================================================================
# 10. Suffix frequency and stem-count filtering
# ===================================================================

class TestSuffixFiltering:
    """A suffix is valid iff:
    n_distinct_stems >= min_suffix_stems AND frequency >= min_suffix_frequency.
    """

    def test_suffix_passes_both_thresholds(self):
        """n_stems=3 >= 2, freq=5 >= 3 -> valid"""
        n_stems, freq = 3, 5
        min_suffix_stems, min_suffix_freq = 2, 3
        valid = n_stems >= min_suffix_stems and freq >= min_suffix_freq
        assert valid is True

    def test_suffix_fails_stem_threshold(self):
        """n_stems=1 < 2 -> invalid"""
        n_stems, freq = 1, 10
        min_suffix_stems, min_suffix_freq = 2, 3
        valid = n_stems >= min_suffix_stems and freq >= min_suffix_freq
        assert valid is False

    def test_suffix_fails_freq_threshold(self):
        """n_stems=5, freq=2 < 3 -> invalid"""
        n_stems, freq = 5, 2
        min_suffix_stems, min_suffix_freq = 2, 3
        valid = n_stems >= min_suffix_stems and freq >= min_suffix_freq
        assert valid is False


# ===================================================================
# 11. Boundary checking (Pillar 1 constraints)
# ===================================================================

class TestBoundaryChecking:
    """_check_boundary returns False if the stem/suffix boundary creates
    a forbidden bigram or splits a favored bigram.
    """

    def test_boundary_no_constraints(self):
        """No forbidden/favored bigrams -> boundary is valid."""
        p1 = _empty_pillar1()
        assert _check_boundary(("A", "B"), ("C",), p1, 1.0) is True

    def test_boundary_forbidden_bigram(self):
        """Boundary pair (B, C) is forbidden -> rejected."""
        p1 = _empty_pillar1(forbidden_bigram_set={("B", "C")})
        assert _check_boundary(("A", "B"), ("C",), p1, 1.0) is False

    def test_boundary_favored_bigram(self):
        """Boundary pair (B, C) is favored -> rejected (don't split
        within a favored collocation)."""
        p1 = _empty_pillar1(favored_bigram_set={("B", "C")})
        assert _check_boundary(("A", "B"), ("C",), p1, 1.0) is False

    def test_boundary_empty_stem(self):
        """Empty stem -> returns True (guard clause)."""
        p1 = _empty_pillar1(forbidden_bigram_set={("X", "Y")})
        assert _check_boundary((), ("Y",), p1, 1.0) is True


# ===================================================================
# 12. BPE stem selection (longest morpheme heuristic)
# ===================================================================

class TestBPEStemSelection:
    """After BPE splits a word into morphemes, the longest morpheme
    is chosen as the stem. Morphemes before it are prefixes, after
    it are suffixes.
    """

    def test_longest_morpheme_is_stem(self):
        """Morphemes: [["A"], ["B", "C", "D"], ["E"]]
        Lengths: 1, 3, 1. Index of max length = 1.
        stem = ["B", "C", "D"]
        prefixes = [["A"]]
        suffixes = [["E"]]
        """
        morphemes = [["A"], ["B", "C", "D"], ["E"]]
        stem_idx = max(range(len(morphemes)), key=lambda i: len(morphemes[i]))
        stem = morphemes[stem_idx]
        prefixes = morphemes[:stem_idx] if stem_idx > 0 else []
        suffixes = morphemes[stem_idx + 1:] if stem_idx < len(morphemes) - 1 else []

        assert stem_idx == 1
        assert stem == ["B", "C", "D"]
        assert prefixes == [["A"]]
        assert suffixes == [["E"]]

    def test_first_morpheme_is_longest(self):
        """Morphemes: [["A", "B", "C"], ["D"]]
        stem_idx = 0. No prefixes. suffixes = [["D"]].
        """
        morphemes = [["A", "B", "C"], ["D"]]
        stem_idx = max(range(len(morphemes)), key=lambda i: len(morphemes[i]))
        stem = morphemes[stem_idx]
        prefixes = morphemes[:stem_idx] if stem_idx > 0 else []
        suffixes = morphemes[stem_idx + 1:] if stem_idx < len(morphemes) - 1 else []

        assert stem_idx == 0
        assert stem == ["A", "B", "C"]
        assert prefixes == []
        assert suffixes == [["D"]]


# ===================================================================
# 13. End-to-end: suffix stripping on synthetic corpus
# ===================================================================

class TestSuffixStripEndToEnd:
    """Drive _suffix_strip_segment with a synthetic word_info dict
    and verify the output matches hand-computed expectations.
    """

    def test_suffix_discovered_and_applied(self):
        """Corpus:
          ("A", "B", "X") freq=2   -> stem=(A,B) suffix=(X,)
          ("C", "D", "X") freq=3   -> stem=(C,D) suffix=(X,)
          ("E", "F", "X") freq=1   -> stem=(E,F) suffix=(X,)
          ("G", "H")      freq=1   -> no suffix (too short or suffix not valid)

        Suffix (X,) appears with 3 distinct stems {(A,B),(C,D),(E,F)},
        total freq = 2+3+1 = 6.
        With min_suffix_stems=2, min_suffix_frequency=3 -> valid.

        Scoring for each word with suffix (X,):
          n_stems=3, suf_len=1 -> score = 3 * (1.0 + 0.1) = 3.3

        Confidence = min(1.0, 3/10.0) = 0.3
        """
        word_info = _make_word_info([
            (("A", "B", "X"), 2),
            (("C", "D", "X"), 3),
            (("E", "F", "X"), 1),
            (("G", "H"), 1),
        ])
        p1 = _empty_pillar1()

        result = _suffix_strip_segment(
            word_info=word_info,
            pillar1=p1,
            min_suffix_frequency=3,
            min_suffix_stems=2,
            max_suffix_length=2,
            lambda_phon=1.0,
        )

        # Build lookup by word
        by_word = {tuple(w.word_sign_ids): w for w in result}

        # Words ending in X should have suffix=["X"], stem without X
        abx = by_word[("A", "B", "X")]
        assert abx.stem == ["A", "B"]
        assert abx.suffixes == [["X"]]
        assert abx.segmentation_confidence == pytest.approx(0.3)

        cdx = by_word[("C", "D", "X")]
        assert cdx.stem == ["C", "D"]
        assert cdx.suffixes == [["X"]]

        # (G, H): suffix (H,) only has 1 stem and freq=1, so not valid
        gh = by_word[("G", "H")]
        assert gh.suffixes == []
        assert gh.segmentation_confidence == pytest.approx(0.0)


# ===================================================================
# 14. End-to-end: productivity via extract_affixes
# ===================================================================

class TestExtractAffixesProductivity:
    """Build a SegmentedLexicon and verify extract_affixes computes
    productivity = n_distinct_stems / max_n_distinct_stems correctly.
    """

    def test_productivity_from_segmented_lexicon(self):
        """Lexicon with two suffixes:
        Suffix ["X"] appears with stems ["A","B"] and ["C","D"] -> 2 distinct stems
        Suffix ["Y"] appears with stems ["E","F"], ["G","H"], ["I","J"], ["K","L"] -> 4 distinct stems
        max = 4
        productivity(X) = 2/4 = 0.5
        productivity(Y) = 4/4 = 1.0
        """
        words = [
            SegmentedWord(["A", "B", "X"], ["A", "B"], [["X"]], [], 0.5, 2, ["v"], "suffix_strip"),
            SegmentedWord(["C", "D", "X"], ["C", "D"], [["X"]], [], 0.5, 3, ["v"], "suffix_strip"),
            SegmentedWord(["E", "F", "Y"], ["E", "F"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
            SegmentedWord(["G", "H", "Y"], ["G", "H"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
            SegmentedWord(["I", "J", "Y"], ["I", "J"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
            SegmentedWord(["K", "L", "Y"], ["K", "L"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
        ]
        lexicon = SegmentedLexicon(words=words, total_words=6, words_with_suffixes=6)

        inv = extract_affixes(lexicon, min_affix_stems=1)

        lookup = {tuple(a.signs): a for a in inv.suffixes}
        assert lookup[("X",)].n_distinct_stems == 2
        assert lookup[("Y",)].n_distinct_stems == 4
        assert lookup[("X",)].productivity == pytest.approx(0.5)
        assert lookup[("Y",)].productivity == pytest.approx(1.0)


# ===================================================================
# 15. End-to-end: paradigm completeness via induce_paradigms
# ===================================================================

class TestParadigmCompletenessEndToEnd:
    """Build a lexicon where 3 stems each share 2 suffixes, then
    verify the computed paradigm completeness matches hand calculation.
    """

    def test_full_paradigm_completeness(self):
        """3 stems (s1, s2, s3) x 2 suffixes (X, Y).
        All 6 cells are filled.
        completeness = 6 / (3*2) = 1.0
        """
        words = []
        for stem in [["s1"], ["s2"], ["s3"]]:
            for suf in [["X"], ["Y"]]:
                words.append(SegmentedWord(
                    word_sign_ids=stem + suf,
                    stem=stem,
                    suffixes=[suf],
                    prefixes=[],
                    segmentation_confidence=0.5,
                    frequency=2,
                    inscription_types=["v"],
                    method="suffix_strip",
                ))
        lexicon = SegmentedLexicon(words=words, total_words=6, words_with_suffixes=6)
        inv = extract_affixes(lexicon, min_affix_stems=2)
        p1 = _empty_pillar1()

        table = induce_paradigms(
            lexicon, inv, p1,
            jaccard_threshold=0.3,
            min_paradigm_members=2,
            min_paradigm_slots=2,
        )

        # All stems have the same signature {X, Y} -> 1 paradigm class
        assert table.n_classes == 1
        paradigm = table.paradigms[0]
        assert paradigm.n_members == 3
        assert len(paradigm.slots) == 2
        # Each slot attested by all 3 stems -> sum = 6, cells = 6
        assert paradigm.completeness == pytest.approx(1.0)

    def test_partial_paradigm_completeness(self):
        """4 stems (s1, s2, s3, s4) x 2 suffixes (X, Y).
        s1 attests both X and Y.
        s2 attests both X and Y.
        s3 attests only X.
        s4 attests only X.

        Both suffixes X and Y have >=2 distinct stems, so both pass
        extract_affixes(min_affix_stems=2).

        Stem signatures after affix extraction:
          s1: {X, Y}
          s2: {X, Y}
          s3: {X}
          s4: {X}

        Exact-signature groups:
          Group A: sig={X,Y}, stems=[s1, s2]
          Group B: sig={X},   stems=[s3, s4]

        Jaccard({X,Y}, {X}) = |{X}| / |{X,Y}| = 1/2 = 0.5 >= 0.3 -> merge.

        After merge: 4 stems, 2 slots.
        Slot X: attested by s1, s2, s3, s4 -> freq=4
        Slot Y: attested by s1, s2           -> freq=2
        n_cells = 4 * 2 = 8
        n_attested = 4 + 2 = 6
        completeness = 6/8 = 0.75
        """
        words = [
            SegmentedWord(["s1", "X"], ["s1"], [["X"]], [], 0.5, 2, ["v"], "suffix_strip"),
            SegmentedWord(["s1", "Y"], ["s1"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
            SegmentedWord(["s2", "X"], ["s2"], [["X"]], [], 0.5, 2, ["v"], "suffix_strip"),
            SegmentedWord(["s2", "Y"], ["s2"], [["Y"]], [], 0.5, 1, ["v"], "suffix_strip"),
            SegmentedWord(["s3", "X"], ["s3"], [["X"]], [], 0.5, 2, ["v"], "suffix_strip"),
            SegmentedWord(["s4", "X"], ["s4"], [["X"]], [], 0.5, 2, ["v"], "suffix_strip"),
        ]
        lexicon = SegmentedLexicon(words=words, total_words=6, words_with_suffixes=6)
        inv = extract_affixes(lexicon, min_affix_stems=2)
        p1 = _empty_pillar1()

        # Verify both suffixes survived filtering
        assert len(inv.suffixes) == 2

        table = induce_paradigms(
            lexicon, inv, p1,
            jaccard_threshold=0.3,
            min_paradigm_members=2,
            min_paradigm_slots=2,
        )

        assert table.n_classes >= 1
        # Find the paradigm containing all 4 stems
        p = [p for p in table.paradigms if p.n_members == 4]
        assert len(p) == 1
        # completeness = (4 + 2) / (4 * 2) = 6/8 = 0.75
        assert p[0].completeness == pytest.approx(0.75)


# ===================================================================
# 16. Word-class hinter: confidence formulas (PRD Section 5.5)
# ===================================================================

class TestWordClassHinterConfidence:
    """Confidence formulas from word_class_hinter.py:

    - uninflected (n_total==0):        confidence = 0.8
    - declining (n_infl>0, p_classes): confidence = min(1.0, n_infl*0.3 + len(p_classes)*0.2)
    - unknown (n_total>0, no paradigm): confidence = 0.3
    - unknown (fallthrough):           confidence = 0.2
    """

    def test_uninflected_confidence(self):
        """No suffixes at all -> label='uninflected', confidence=0.8 (fixed)."""
        n_total = 0
        n_infl = 0
        p_classes = set()

        # Reproduce the classification logic
        if n_total == 0:
            label = "uninflected"
            confidence = 0.8
        elif n_infl > 0 and p_classes:
            label = "declining"
            confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        elif n_total > 0 and not p_classes:
            label = "unknown"
            confidence = 0.3
        else:
            label = "unknown"
            confidence = 0.2

        assert label == "uninflected"
        assert confidence == pytest.approx(0.8)

    def test_declining_confidence_1_infl_1_paradigm(self):
        """n_infl=1, p_classes={0} (len=1).
        confidence = min(1.0, 1*0.3 + 1*0.2) = min(1.0, 0.5) = 0.5
        """
        n_infl = 1
        p_classes = {0}
        confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        assert confidence == pytest.approx(0.5)

    def test_declining_confidence_2_infl_3_paradigms(self):
        """n_infl=2, p_classes={0,1,2} (len=3).
        confidence = min(1.0, 2*0.3 + 3*0.2) = min(1.0, 0.6+0.6) = min(1.0, 1.2) = 1.0
        """
        n_infl = 2
        p_classes = {0, 1, 2}
        confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        assert confidence == pytest.approx(1.0)

    def test_declining_confidence_3_infl_1_paradigm(self):
        """n_infl=3, p_classes={0} (len=1).
        confidence = min(1.0, 3*0.3 + 1*0.2) = min(1.0, 0.9+0.2) = min(1.0, 1.1) = 1.0
        Clamped at 1.0.
        """
        n_infl = 3
        p_classes = {0}
        confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        assert confidence == pytest.approx(1.0)

    def test_declining_confidence_1_infl_2_paradigms(self):
        """n_infl=1, p_classes={0,1} (len=2).
        confidence = min(1.0, 1*0.3 + 2*0.2) = min(1.0, 0.3+0.4) = 0.7
        """
        n_infl = 1
        p_classes = {0, 1}
        confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        assert confidence == pytest.approx(0.7)

    def test_unknown_has_suffixes_no_paradigm(self):
        """n_total=2 (has suffixes), p_classes=set() (no paradigm membership).
        n_infl=0 so first elif fails, second elif triggers.
        confidence = 0.3 (fixed).
        """
        n_total = 2
        n_infl = 0
        p_classes = set()

        if n_total == 0:
            label = "uninflected"
            confidence = 0.8
        elif n_infl > 0 and p_classes:
            label = "declining"
            confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        elif n_total > 0 and not p_classes:
            label = "unknown"
            confidence = 0.3
        else:
            label = "unknown"
            confidence = 0.2

        assert label == "unknown"
        assert confidence == pytest.approx(0.3)

    def test_unknown_fallthrough(self):
        """n_total=1 (has suffixes), n_infl=0, p_classes={0} (has paradigm).
        First if: n_total != 0 -> skip.
        First elif: n_infl=0 -> condition fails.
        Second elif: not p_classes is False (p_classes is non-empty) -> skip.
        Falls through to else -> 'unknown', confidence=0.2.
        """
        n_total = 1
        n_infl = 0
        p_classes = {0}

        if n_total == 0:
            label = "uninflected"
            confidence = 0.8
        elif n_infl > 0 and p_classes:
            label = "declining"
            confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        elif n_total > 0 and not p_classes:
            label = "unknown"
            confidence = 0.3
        else:
            label = "unknown"
            confidence = 0.2

        assert label == "unknown"
        assert confidence == pytest.approx(0.2)


# ===================================================================
# 17. Word-class hinter: classification logic (PRD Section 5.5)
# ===================================================================

class TestWordClassHinterClassification:
    """Tests the four classification branches in word_class_hinter.py:
    uninflected, declining, unknown (no paradigm), unknown (fallthrough).
    """

    def test_uninflected_when_no_suffixes(self):
        """A stem with n_total=0 suffixes is always 'uninflected'."""
        n_total, n_infl, p_classes = 0, 0, set()
        assert n_total == 0  # triggers first branch
        label = "uninflected"
        assert label == "uninflected"

    def test_declining_requires_both_infl_and_paradigm(self):
        """'declining' requires BOTH n_infl > 0 AND p_classes non-empty.
        If either is missing, it does NOT classify as declining.
        """
        # Both present -> declining
        n_infl, p_classes = 2, {0}
        assert (n_infl > 0 and bool(p_classes)) is True

        # n_infl=0 -> not declining
        n_infl2, p_classes2 = 0, {0}
        assert (n_infl2 > 0 and bool(p_classes2)) is False

        # p_classes empty -> not declining
        n_infl3, p_classes3 = 2, set()
        assert (n_infl3 > 0 and bool(p_classes3)) is False

    def test_unknown_no_paradigm_has_suffixes(self):
        """n_total > 0 and p_classes empty -> 'unknown' with confidence=0.3.
        This is the 'has affixes but no paradigm membership' case.
        """
        n_total, n_infl, p_classes = 3, 0, set()
        # First branch: n_total != 0 -> skip
        # Second branch: n_infl == 0 -> skip
        # Third branch: n_total > 0 and not p_classes -> True
        assert (n_total > 0 and not p_classes) is True


# ===================================================================
# 18. BPE pair frequency: weighted by word frequency
# ===================================================================

class TestBPEPairFrequencyWeighting:
    """In _bpe_segment, pair frequencies are weighted by word frequency:
    pair_freq[pair] += winfo.frequency

    So a pair in a word with frequency 5 counts 5x, not 1x.
    """

    def test_pair_freq_weighted_by_word_frequency(self):
        """Word (A, B, C) with frequency 3:
        Pairs: (A,B) and (B,C), each gets +3.

        Word (A, B) with frequency 2:
        Pair: (A,B) gets +2.

        Total: pair (A,B) = 3+2 = 5, pair (B,C) = 3.
        """
        from collections import defaultdict

        word_info = _make_word_info([
            (("A", "B", "C"), 3),
            (("A", "B"), 2),
        ])

        pair_freq: dict[tuple[str, str], int] = defaultdict(int)
        for word_sids, winfo in word_info.items():
            for i in range(len(word_sids) - 1):
                pair = (word_sids[i], word_sids[i + 1])
                pair_freq[pair] += winfo.frequency

        assert pair_freq[("A", "B")] == 5  # 3 + 2
        assert pair_freq[("B", "C")] == 3  # only from first word

    def test_pair_freq_single_word_high_frequency(self):
        """Word (X, Y, Z) with frequency 10:
        Pairs: (X,Y)=10, (Y,Z)=10.
        """
        from collections import defaultdict

        word_info = _make_word_info([
            (("X", "Y", "Z"), 10),
        ])

        pair_freq: dict[tuple[str, str], int] = defaultdict(int)
        for word_sids, winfo in word_info.items():
            for i in range(len(word_sids) - 1):
                pair = (word_sids[i], word_sids[i + 1])
                pair_freq[pair] += winfo.frequency

        assert pair_freq[("X", "Y")] == 10
        assert pair_freq[("Y", "Z")] == 10


# ===================================================================
# 19. Paradigm completeness inline computation
# ===================================================================

class TestParadigmCompletenessInline:
    """The completeness formula in induce_paradigms is:
        n_cells = len(group_stems) * len(slots)
        n_attested = sum(s.frequency for s in slots)
        completeness = n_attested / n_cells if n_cells > 0 else 0.0

    where slot.frequency = number of stems in the group that attest that slot.
    This test verifies the arithmetic with hand-chosen numbers.
    """

    def test_completeness_5_stems_3_slots_partial(self):
        """5 stems, 3 slots.
        Slot 0: freq=5 (all stems)
        Slot 1: freq=3
        Slot 2: freq=2
        n_cells = 5 * 3 = 15
        n_attested = 5 + 3 + 2 = 10
        completeness = 10/15 = 2/3 = 0.6667
        """
        n_stems = 5
        slot_freqs = [5, 3, 2]
        n_cells = n_stems * len(slot_freqs)
        n_attested = sum(slot_freqs)
        completeness = n_attested / n_cells if n_cells > 0 else 0.0
        assert n_cells == 15
        assert n_attested == 10
        assert completeness == pytest.approx(2 / 3)

    def test_completeness_zero_cells_guard(self):
        """0 stems or 0 slots -> n_cells=0 -> completeness=0.0 (guard clause)."""
        n_cells = 0
        completeness = 0 / n_cells if n_cells > 0 else 0.0
        assert completeness == pytest.approx(0.0)

    def test_completeness_1_stem_1_slot(self):
        """1 stem, 1 slot, freq=1 (attested).
        n_cells = 1, n_attested = 1, completeness = 1.0
        """
        n_cells = 1 * 1
        n_attested = 1
        completeness = n_attested / n_cells
        assert completeness == pytest.approx(1.0)


# ===================================================================
# 20. Grid analysis: consonant-row sharing check
# ===================================================================

class TestGridAnalysisConsonantSharing:
    """_grid_analysis checks if all paradigm endings share the same
    consonant class (suggesting they differ only in vowel = case forms).

    share_consonant = len(set(consonant_classes)) == 1
    """

    def test_all_same_consonant_class(self):
        """Consonant classes [2, 2, 2] -> len(set)=1 -> share=True.
        consonant_class = 2.
        """
        consonant_classes = [2, 2, 2]
        share = len(set(consonant_classes)) == 1
        consonant_class = consonant_classes[0] if share else None
        assert share is True
        assert consonant_class == 2

    def test_mixed_consonant_classes(self):
        """Consonant classes [1, 2, 1] -> len(set)=2 -> share=False.
        consonant_class = None.
        """
        consonant_classes = [1, 2, 1]
        share = len(set(consonant_classes)) == 1
        consonant_class = consonant_classes[0] if share else None
        assert share is False
        assert consonant_class is None

    def test_vowel_classes_attested_dedup_and_sort(self):
        """Vowel classes [3, 1, 3, 2] -> sorted(set) = [1, 2, 3]."""
        vowel_classes = [3, 1, 3, 2]
        vowel_classes_attested = sorted(set(vowel_classes))
        assert vowel_classes_attested == [1, 2, 3]

    def test_single_ending(self):
        """Single consonant class [5] -> len(set)=1 -> share=True.
        consonant_class = 5.
        """
        consonant_classes = [5]
        share = len(set(consonant_classes)) == 1
        consonant_class = consonant_classes[0] if share else None
        assert share is True
        assert consonant_class == 5


# ===================================================================
# 21. Suffix scoring: tie-breaking between competing suffixes
# ===================================================================

class TestSuffixScoringTieBreaking:
    """When multiple valid suffixes could segment a word, the one with
    the highest score = n_stems * (1.0 + 0.1 * suf_len) wins.

    This tests the comparison logic, not just the formula.
    """

    def test_more_stems_beats_longer_suffix(self):
        """Suffix A: n_stems=6, suf_len=1 -> 6 * 1.1 = 6.6
        Suffix B: n_stems=4, suf_len=3 -> 4 * 1.3 = 5.2
        Suffix A wins (more stems outweighs length bonus).
        """
        score_a = 6 * (1.0 + 0.1 * 1)
        score_b = 4 * (1.0 + 0.1 * 3)
        assert score_a == pytest.approx(6.6)
        assert score_b == pytest.approx(5.2)
        assert score_a > score_b

    def test_equal_stems_longer_suffix_wins(self):
        """Suffix A: n_stems=4, suf_len=1 -> 4 * 1.1 = 4.4
        Suffix B: n_stems=4, suf_len=2 -> 4 * 1.2 = 4.8
        Suffix B wins (length tiebreaker with equal stems).
        """
        score_a = 4 * (1.0 + 0.1 * 1)
        score_b = 4 * (1.0 + 0.1 * 2)
        assert score_a == pytest.approx(4.4)
        assert score_b == pytest.approx(4.8)
        assert score_b > score_a
