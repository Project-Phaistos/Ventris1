"""Tier 1: Formula-level mathematical correctness tests for Pillar 5.

Every function implementing a mathematical formula gets a test with
hand-computed expected values. Not "does it return a float" but
"does it return THIS specific float for THIS input?"

Per Section 13.4 of STANDARDS_AND_PROCEDURES.md.
"""

from __future__ import annotations

import pytest

from pillar5.semantic_scorer import (
    score_semantic_compatibility,
    _classify_gloss,
    _get_domain,
)
from pillar5.evidence_combiner import (
    compute_combined_score,
    normalize_scores,
    W_PHON,
)
from pillar5.constraint_assembler import (
    PROVENANCE_WEIGHTS,
    SignGroupConstraints,
)
from pillar5.cognate_list_assembler import _normalized_edit_distance
from pillar5.stratum_detector import detect_strata, MATCH_THRESHOLD


# ============================================================
# Semantic Scoring Formula Tests
# ============================================================


class TestSemanticScoring:
    """Test semantic compatibility scoring formulas."""

    def test_exact_field_match_returns_1(self):
        """COMMODITY:FIG anchor vs "fig" gloss -> 1.0."""
        score = score_semantic_compatibility("COMMODITY:FIG", "fig tree")
        assert score == 1.0

    def test_same_domain_match_returns_05(self):
        """COMMODITY:FIG anchor vs "grain" gloss -> 0.5 (both COMMODITY)."""
        score = score_semantic_compatibility("COMMODITY:FIG", "barley grain")
        assert score == 0.5

    def test_domain_mismatch_returns_0(self):
        """COMMODITY:FIG anchor vs "king" gloss -> 0.0."""
        score = score_semantic_compatibility("COMMODITY:FIG", "great king")
        assert score == 0.0

    def test_no_anchor_returns_none(self):
        """No semantic anchor -> None (not scored)."""
        score = score_semantic_compatibility(None, "water")
        assert score is None

    def test_no_gloss_returns_none(self):
        """No candidate gloss -> None (not scored)."""
        score = score_semantic_compatibility("COMMODITY:FIG", None)
        assert score is None

    def test_both_none_returns_none(self):
        """Both None -> None."""
        score = score_semantic_compatibility(None, None)
        assert score is None

    def test_unclassifiable_gloss_returns_none(self):
        """Gloss that doesn't map to any domain -> None."""
        score = score_semantic_compatibility("COMMODITY:FIG", "abstract concept")
        assert score is None

    def test_place_domain_match(self):
        """PLACE:PHAISTOS anchor vs "city" gloss -> 0.5 (both PLACE)."""
        score = score_semantic_compatibility("PLACE:PHAISTOS", "ancient city")
        assert score == 0.5

    def test_transaction_exact_match(self):
        """TRANSACTION:TOTAL anchor vs "total/sum" gloss -> 1.0."""
        score = score_semantic_compatibility("TRANSACTION:TOTAL", "the total sum")
        assert score == 1.0

    def test_person_vs_commodity_mismatch(self):
        """PERSON anchor vs "wheat" gloss -> 0.0."""
        score = score_semantic_compatibility("PERSON", "wheat grain")
        assert score == 0.0


class TestDomainExtraction:
    """Test domain extraction helper."""

    def test_commodity_fig(self):
        assert _get_domain("COMMODITY:FIG") == "COMMODITY"

    def test_place_phaistos(self):
        assert _get_domain("PLACE:PHAISTOS") == "PLACE"

    def test_function_total(self):
        assert _get_domain("FUNCTION:TOTAL_MARKER") == "FUNCTION"

    def test_person_no_subtype(self):
        assert _get_domain("PERSON") == "PERSON"

    def test_empty_returns_none(self):
        assert _get_domain("") is None


class TestGlossClassification:
    """Test keyword-based gloss classification."""

    def test_fig_classifies_correctly(self):
        assert _classify_gloss("fig tree") == "COMMODITY:FIG"

    def test_grain_classifies_correctly(self):
        assert _classify_gloss("barley") == "COMMODITY:GRAIN"

    def test_king_classifies_as_person(self):
        assert _classify_gloss("the king") == "PERSON"

    def test_mountain_classifies_as_place(self):
        assert _classify_gloss("tall mountain") == "PLACE"

    def test_unknown_returns_none(self):
        assert _classify_gloss("xyzzy") is None


# ============================================================
# Combined Scoring Formula Tests
# ============================================================


class TestCombinedScoring:
    """Test the combined scoring formula from PRD Section 5.4.

    combined_score = phon_score * w_phon + semantic * w_sem

    w_phon = 0.5 (CONSENSUS_ASSUMED)
    w_sem  = provenance_weight(semantic evidence)
    """

    def test_phonology_only_no_semantic(self):
        """phon=0.8, semantic=None -> 0.8 * 0.5 = 0.4."""
        score = compute_combined_score(0.8, None)
        assert abs(score - 0.4) < 1e-10

    def test_full_match_independent_semantic(self):
        """phon=1.0, sem=1.0, provenance=INDEPENDENT -> 1.0*0.5 + 1.0*1.0 = 1.5."""
        score = compute_combined_score(1.0, 1.0, "INDEPENDENT")
        assert abs(score - 1.5) < 1e-10

    def test_full_match_consensus_dependent_semantic(self):
        """phon=1.0, sem=1.0, provenance=CONSENSUS_DEPENDENT -> 1.0*0.5 + 1.0*0.3 = 0.8."""
        score = compute_combined_score(1.0, 1.0, "CONSENSUS_DEPENDENT")
        assert abs(score - 0.8) < 1e-10

    def test_half_match_consensus_assumed(self):
        """phon=0.6, sem=0.5, provenance=CONSENSUS_ASSUMED -> 0.6*0.5 + 0.5*0.5 = 0.55."""
        score = compute_combined_score(0.6, 0.5, "CONSENSUS_ASSUMED")
        assert abs(score - 0.55) < 1e-10

    def test_zero_phonology_with_semantic(self):
        """phon=0.0, sem=1.0, provenance=INDEPENDENT -> 0.0*0.5 + 1.0*1.0 = 1.0."""
        score = compute_combined_score(0.0, 1.0, "INDEPENDENT")
        assert abs(score - 1.0) < 1e-10

    def test_w_phon_is_half(self):
        """Verify w_phon = 0.5 as specified in PRD."""
        assert W_PHON == 0.5

    def test_provenance_weights_match_standards(self):
        """Verify provenance weights match Section 15 of standards."""
        assert PROVENANCE_WEIGHTS["INDEPENDENT"] == 1.0
        assert PROVENANCE_WEIGHTS["INDEPENDENT_VALIDATED"] == 1.0
        assert PROVENANCE_WEIGHTS["CONSENSUS_CONFIRMED"] == 0.8
        assert PROVENANCE_WEIGHTS["CONSENSUS_ASSUMED"] == 0.5
        assert PROVENANCE_WEIGHTS["CONSENSUS_DEPENDENT"] == 0.3


# ============================================================
# Normalization Tests
# ============================================================


class TestNormalization:
    """Test score normalization to [0, 1]."""

    def test_basic_normalization(self):
        """[10, 20, 30] -> [0.0, 0.5, 1.0]."""
        result = normalize_scores([10.0, 20.0, 30.0])
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[1] - 0.5) < 1e-10
        assert abs(result[2] - 1.0) < 1e-10

    def test_single_score(self):
        """Single score -> [1.0]."""
        result = normalize_scores([42.0])
        assert result == [1.0]

    def test_empty_scores(self):
        """Empty list -> empty list."""
        result = normalize_scores([])
        assert result == []

    def test_all_equal(self):
        """All equal -> [0.5, 0.5, 0.5]."""
        result = normalize_scores([5.0, 5.0, 5.0])
        assert all(abs(r - 0.5) < 1e-10 for r in result)

    def test_negative_scores(self):
        """[-10, 0, 10] -> [0.0, 0.5, 1.0]."""
        result = normalize_scores([-10.0, 0.0, 10.0])
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[1] - 0.5) < 1e-10
        assert abs(result[2] - 1.0) < 1e-10


# ============================================================
# Edit Distance Tests
# ============================================================


class TestEditDistance:
    """Test normalized edit distance computation."""

    def test_identical_strings(self):
        """Identical strings -> 0.0."""
        assert _normalized_edit_distance("abc", "abc") == 0.0

    def test_completely_different(self):
        """Completely different equal-length strings -> 1.0."""
        assert _normalized_edit_distance("aaa", "bbb") == 1.0

    def test_one_substitution(self):
        """'abc' vs 'axc' -> 1/3 = 0.333..."""
        dist = _normalized_edit_distance("abc", "axc")
        assert abs(dist - 1.0 / 3.0) < 1e-10

    def test_insertion(self):
        """'ab' vs 'abc' -> 1/3 = 0.333..."""
        dist = _normalized_edit_distance("ab", "abc")
        assert abs(dist - 1.0 / 3.0) < 1e-10

    def test_empty_vs_nonempty(self):
        """Empty vs non-empty -> 1.0."""
        assert _normalized_edit_distance("", "abc") == 1.0
        assert _normalized_edit_distance("abc", "") == 1.0

    def test_both_empty(self):
        """Both empty -> 1.0 (no information)."""
        assert _normalized_edit_distance("", "") == 1.0

    def test_hand_computed_example(self):
        """'ka' vs 'kappu' -> edit distance 3, max len 5, normalized 3/5 = 0.6."""
        dist = _normalized_edit_distance("ka", "kappu")
        assert abs(dist - 3.0 / 5.0) < 1e-10

    def test_symmetry(self):
        """Distance is symmetric: d(a,b) == d(b,a)."""
        d1 = _normalized_edit_distance("kata", "katu")
        d2 = _normalized_edit_distance("katu", "kata")
        assert abs(d1 - d2) < 1e-10


# ============================================================
# Constraint Assembly Tests
# ============================================================


class TestConstraintProperties:
    """Test SignGroupConstraints property methods."""

    def test_has_constraints_with_semantic_field(self):
        sg = SignGroupConstraints(
            sign_group_ids=["AB01"],
            semantic_field="COMMODITY:FIG",
        )
        assert sg.has_constraints is True

    def test_has_constraints_with_morph_class(self):
        sg = SignGroupConstraints(
            sign_group_ids=["AB01"],
            morphological_class="declining",
        )
        assert sg.has_constraints is True

    def test_has_constraints_with_phonetic_reading(self):
        sg = SignGroupConstraints(
            sign_group_ids=["AB01"],
            phonetic_reading_lb="ka",
        )
        assert sg.has_constraints is True

    def test_no_constraints(self):
        sg = SignGroupConstraints(sign_group_ids=["AB01"])
        assert sg.has_constraints is False

    def test_provenance_weight_independent(self):
        sg = SignGroupConstraints(
            sign_group_ids=["AB01"],
            evidence_provenance="INDEPENDENT",
        )
        assert sg.provenance_weight == 1.0

    def test_provenance_weight_consensus_dependent(self):
        sg = SignGroupConstraints(
            sign_group_ids=["AB01"],
            evidence_provenance="CONSENSUS_DEPENDENT",
        )
        assert sg.provenance_weight == 0.3
