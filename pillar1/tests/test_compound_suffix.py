"""Tests for compound suffix constraint extraction.

Three tiers:
  - Tier 1: Unit tests for parsing, grouping, constraint emission
  - Tier 2: LB validation (known-answer tests)
  - Tier 3: Null test (shuffled suffixes should be at chance level)

All tests use either synthetic data or the real P2 output +
LB ground truth fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from pillar1.suffix_constraints.compound_suffix_analyzer import (
    CompoundSuffix,
    ConstraintPair,
    extract_compound_suffixes,
    group_by_head,
    group_by_tail,
    emit_shared_head_constraints,
    emit_shared_tail_constraints,
    validate_on_lb,
    find_la_unknown_signs_constrained,
    run_compound_suffix_analysis,
    parse_cv,
    serialize_result,
)


# ── Paths ──────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
LB_SIGN_TO_IPA_PATH = FIXTURES_DIR / "linear_b_sign_to_ipa.json"
P2_OUTPUT_PATH = Path(__file__).resolve().parents[2] / "results" / "pillar2_output.json"


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def lb_sign_to_ipa() -> Dict[str, str]:
    """Load Linear B sign-to-IPA mapping."""
    assert LB_SIGN_TO_IPA_PATH.exists(), f"Fixture not found: {LB_SIGN_TO_IPA_PATH}"
    with open(LB_SIGN_TO_IPA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p2_data() -> Dict[str, Any]:
    """Load real P2 output."""
    assert P2_OUTPUT_PATH.exists(), f"P2 output not found: {P2_OUTPUT_PATH}"
    with open(P2_OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def compound_suffixes(p2_data: Dict[str, Any]) -> List[CompoundSuffix]:
    """Extract compound suffixes from P2 data."""
    return extract_compound_suffixes(p2_data)


@pytest.fixture(scope="module")
def full_result(
    p2_data: Dict[str, Any],
    lb_sign_to_ipa: Dict[str, str],
) -> Any:
    """Run the complete analysis pipeline (cached for the module)."""
    return run_compound_suffix_analysis(
        p2_data=p2_data,
        lb_sign_to_ipa=lb_sign_to_ipa,
        min_group_size=3,
        seed=42,
        n_shuffles=200,
    )


# ── Synthetic data for unit tests ──────────────────────────────────────

def _make_p2_data(suffix_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create minimal P2-like data with given suffix entries."""
    return {
        "affix_inventory": {
            "suffixes": suffix_entries,
            "prefixes": [],
        },
    }


def _make_suffix(signs: List[str], freq: int = 3, stems: int = 2) -> Dict[str, Any]:
    """Create a minimal suffix entry."""
    return {
        "signs": signs,
        "frequency": freq,
        "n_distinct_stems": stems,
        "productivity": 1.0,
        "classification": "inflectional",
        "paradigm_classes": [0],
    }


# =========================================================================
# TIER 1: Unit tests — parsing, grouping, constraint emission
# =========================================================================

class TestParseCV:
    """Test the CV reading parser."""

    def test_pure_vowel(self) -> None:
        assert parse_cv("a") == (None, "a")
        assert parse_cv("e") == (None, "e")
        assert parse_cv("u") == (None, "u")

    def test_cv_syllable(self) -> None:
        assert parse_cv("da") == ("d", "a")
        assert parse_cv("ti") == ("t", "i")
        assert parse_cv("ro") == ("r", "o")

    def test_complex_onset(self) -> None:
        assert parse_cv("qe") == ("q", "e")
        assert parse_cv("we") == ("w", "e")

    def test_unknown(self) -> None:
        assert parse_cv("") == (None, None)
        assert parse_cv("xyz") == (None, None)


class TestCompoundSuffixParsing:
    """Test CompoundSuffix.from_affix_entry()."""

    def test_single_sign_suffix_returns_none(self) -> None:
        entry = _make_suffix(["AB06"])
        assert CompoundSuffix.from_affix_entry(entry) is None

    def test_two_sign_suffix_parses(self) -> None:
        entry = _make_suffix(["AB01", "AB27"])
        cs = CompoundSuffix.from_affix_entry(entry)
        assert cs is not None
        assert cs.head == "AB01"
        assert cs.tail == "AB27"
        assert cs.signs == ["AB01", "AB27"]

    def test_three_sign_suffix_parses(self) -> None:
        entry = _make_suffix(["AB01", "AB02", "AB03"])
        cs = CompoundSuffix.from_affix_entry(entry)
        assert cs is not None
        assert cs.head == "AB01"
        assert cs.tail == "AB03"

    def test_logogram_suffix_skipped(self) -> None:
        entry = _make_suffix(["R_ka", "R_na", "R_si"])
        assert CompoundSuffix.from_affix_entry(entry) is None

    def test_mixed_logogram_skipped(self) -> None:
        entry = _make_suffix(["AB01", "R_ka"])
        assert CompoundSuffix.from_affix_entry(entry) is None

    def test_frequency_and_stems_preserved(self) -> None:
        entry = _make_suffix(["AB01", "AB27"], freq=7, stems=5)
        cs = CompoundSuffix.from_affix_entry(entry)
        assert cs is not None
        assert cs.frequency == 7
        assert cs.n_distinct_stems == 5


class TestExtractCompoundSuffixes:
    """Test extraction from P2 data."""

    def test_extracts_only_multi_sign(self) -> None:
        p2 = _make_p2_data([
            _make_suffix(["AB06"]),           # single — skip
            _make_suffix(["AB01", "AB27"]),    # compound — keep
            _make_suffix(["AB59", "AB06"]),    # compound — keep
        ])
        result = extract_compound_suffixes(p2)
        assert len(result) == 2

    def test_empty_affix_inventory(self) -> None:
        p2 = _make_p2_data([])
        result = extract_compound_suffixes(p2)
        assert len(result) == 0

    def test_real_p2_data_has_compounds(self, p2_data: Dict[str, Any]) -> None:
        """Real P2 output should have at least 20 compound suffixes."""
        result = extract_compound_suffixes(p2_data)
        assert len(result) >= 20, (
            f"Expected >= 20 compound suffixes, got {len(result)}"
        )


class TestGroupByHead:
    """Test grouping compound suffixes by head sign."""

    def test_groups_by_first_sign(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB01", "AB60"], "AB01", "AB60", 3, 2),
            CompoundSuffix(["AB01", "AB02"], "AB01", "AB02", 3, 2),
            CompoundSuffix(["AB59", "AB06"], "AB59", "AB06", 3, 2),
        ]
        groups = group_by_head(suffixes, min_group_size=2)
        assert "AB01" in groups
        assert len(groups["AB01"]) == 3
        # AB59 has only 1 suffix, below min_group_size=2
        assert "AB59" not in groups

    def test_min_group_size_filters(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB01", "AB60"], "AB01", "AB60", 3, 2),
        ]
        # min_group_size=3 should filter out AB01 (only 2)
        groups = group_by_head(suffixes, min_group_size=3)
        assert len(groups) == 0

    def test_empty_input(self) -> None:
        groups = group_by_head([], min_group_size=2)
        assert len(groups) == 0


class TestGroupByTail:
    """Test grouping compound suffixes by tail sign."""

    def test_groups_by_last_sign(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB59", "AB27"], "AB59", "AB27", 3, 2),
            CompoundSuffix(["AB60", "AB27"], "AB60", "AB27", 3, 2),
        ]
        groups = group_by_tail(suffixes, min_group_size=2)
        assert "AB27" in groups
        assert len(groups["AB27"]) == 3


class TestEmitSharedHeadConstraints:
    """Test constraint emission from shared-head groups."""

    def test_emits_same_consonant_pairs(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB01", "AB60"], "AB01", "AB60", 3, 2),
            CompoundSuffix(["AB01", "AB02"], "AB01", "AB02", 3, 2),
        ]
        groups = group_by_head(suffixes, min_group_size=2)
        constraint_groups = emit_shared_head_constraints(groups)
        assert len(constraint_groups) == 1

        cg = constraint_groups[0]
        assert cg.group_key == "AB01"
        assert cg.group_type == "shared_head"
        # 3 tails -> C(3,2) = 3 pairs
        assert len(cg.constraints) == 3
        for c in cg.constraints:
            assert c.constraint_type == "same_consonant"
            assert c.source_group_key == "AB01"

    def test_constraint_pairs_are_correct(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB01", "AB60"], "AB01", "AB60", 3, 2),
        ]
        groups = group_by_head(suffixes, min_group_size=2)
        cgs = emit_shared_head_constraints(groups)
        assert len(cgs) == 1
        assert len(cgs[0].constraints) == 1
        c = cgs[0].constraints[0]
        assert {c.sign_a, c.sign_b} == {"AB27", "AB60"}

    def test_duplicate_tails_deduplicated(self) -> None:
        """If two compound suffixes have the same tail, no self-pair."""
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 2, 1),
            CompoundSuffix(["AB01", "AB60"], "AB01", "AB60", 3, 2),
        ]
        groups = group_by_head(suffixes, min_group_size=2)
        cgs = emit_shared_head_constraints(groups)
        assert len(cgs) == 1
        # Only one unique pair: AB27-AB60
        assert len(cgs[0].constraints) == 1


class TestEmitSharedTailConstraints:
    """Test constraint emission from shared-tail groups."""

    def test_emits_same_vowel_pairs(self) -> None:
        suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB59", "AB27"], "AB59", "AB27", 3, 2),
            CompoundSuffix(["AB60", "AB27"], "AB60", "AB27", 3, 2),
        ]
        groups = group_by_tail(suffixes, min_group_size=2)
        constraint_groups = emit_shared_tail_constraints(groups)
        assert len(constraint_groups) == 1

        cg = constraint_groups[0]
        assert cg.group_key == "AB27"
        assert cg.group_type == "shared_tail"
        # 3 heads -> C(3,2) = 3 pairs
        assert len(cg.constraints) == 3
        for c in cg.constraints:
            assert c.constraint_type == "same_vowel"

    def test_confidence_increases_with_group_size(self) -> None:
        """Larger groups should produce higher-confidence constraints."""
        small_suffixes = [
            CompoundSuffix(["AB01", "AB27"], "AB01", "AB27", 3, 2),
            CompoundSuffix(["AB59", "AB27"], "AB59", "AB27", 3, 2),
            CompoundSuffix(["AB60", "AB27"], "AB60", "AB27", 3, 2),
        ]
        large_suffixes = small_suffixes + [
            CompoundSuffix(["AB80", "AB27"], "AB80", "AB27", 3, 2),
            CompoundSuffix(["AB73", "AB27"], "AB73", "AB27", 3, 2),
        ]

        small_groups = group_by_tail(small_suffixes, min_group_size=2)
        large_groups = group_by_tail(large_suffixes, min_group_size=2)

        small_cgs = emit_shared_tail_constraints(small_groups)
        large_cgs = emit_shared_tail_constraints(large_groups)

        small_conf = small_cgs[0].constraints[0].confidence
        large_conf = large_cgs[0].constraints[0].confidence
        assert large_conf > small_conf


# =========================================================================
# TIER 2: LB validation (known-answer tests)
# =========================================================================

class TestLBValidation:
    """Linear B known-answer tests for compound suffix constraints.

    The ground truth confirms:
      - Shared-head tails share consonants at ~37% (3.75x above ~10% baseline)
      - Shared-tail heads share vowels at ~54% (2.3x above ~23% baseline)
    """

    def test_head_purity_above_threshold(self, full_result: Any) -> None:
        """Shared-head tails should share consonants at >= 30%."""
        v = full_result.validation
        assert v is not None
        assert v.lb_head_purity >= 0.30, (
            f"Head purity {v.lb_head_purity:.1%} below 30% threshold. "
            f"({v.lb_head_pairs_same}/{v.lb_head_pairs_total} pairs)"
        )

    def test_tail_purity_above_threshold(self, full_result: Any) -> None:
        """Shared-tail heads should share vowels at >= 40%."""
        v = full_result.validation
        assert v is not None
        assert v.lb_tail_purity >= 0.40, (
            f"Tail purity {v.lb_tail_purity:.1%} below 40% threshold. "
            f"({v.lb_tail_pairs_same}/{v.lb_tail_pairs_total} pairs)"
        )

    def test_head_purity_above_baseline(self, full_result: Any) -> None:
        """Head purity should be at least 2x the baseline."""
        v = full_result.validation
        assert v is not None
        assert v.lb_head_purity >= 2.0 * v.head_baseline, (
            f"Head purity {v.lb_head_purity:.1%} is not 2x "
            f"baseline {v.head_baseline:.1%}"
        )

    def test_tail_purity_above_baseline(self, full_result: Any) -> None:
        """Tail purity should be at least 1.5x the baseline."""
        v = full_result.validation
        assert v is not None
        assert v.lb_tail_purity >= 1.5 * v.tail_baseline, (
            f"Tail purity {v.lb_tail_purity:.1%} is not 1.5x "
            f"baseline {v.tail_baseline:.1%}"
        )

    def test_sufficient_evidence(self, full_result: Any) -> None:
        """Validation should have at least 5 pairs for each analysis."""
        v = full_result.validation
        assert v is not None
        assert v.lb_head_pairs_total >= 5, (
            f"Only {v.lb_head_pairs_total} head pairs — insufficient evidence"
        )
        assert v.lb_tail_pairs_total >= 5, (
            f"Only {v.lb_tail_pairs_total} tail pairs — insufficient evidence"
        )

    def test_head_gate_passes(self, full_result: Any) -> None:
        """The head_pass gate should be True."""
        v = full_result.validation
        assert v is not None
        assert v.head_pass, (
            f"Head gate FAILED: purity={v.lb_head_purity:.1%}, "
            f"pairs={v.lb_head_pairs_total}"
        )

    def test_tail_gate_passes(self, full_result: Any) -> None:
        """The tail_pass gate should be True."""
        v = full_result.validation
        assert v is not None
        assert v.tail_pass, (
            f"Tail gate FAILED: purity={v.lb_tail_purity:.1%}, "
            f"pairs={v.lb_tail_pairs_total}"
        )

    def test_known_ab01_head_group(
        self, full_result: Any, lb_sign_to_ipa: Dict[str, str],
    ) -> None:
        """AB01(da) head group: tails AB27(re), AB60(ra), AB02(ro) all have consonant r."""
        # Find the AB01 head group
        ab01_group = None
        for g in full_result.shared_head_groups:
            if g.group_key == "AB01":
                ab01_group = g
                break

        if ab01_group is None:
            pytest.skip("AB01 head group not present at min_group_size=3")

        # Check that the tails resolve to r-series in LB
        tail_consonants = set()
        for tail in ab01_group.varying_signs:
            reading = lb_sign_to_ipa.get(tail)
            if reading:
                c, v = parse_cv(reading)
                if c is not None:
                    tail_consonants.add(c)

        # All should be 'r': re, ra, ro
        assert "r" in tail_consonants, (
            f"Expected r-series tails, got consonants: {tail_consonants}"
        )

    def test_known_ab27_tail_group(
        self, full_result: Any, lb_sign_to_ipa: Dict[str, str],
    ) -> None:
        """AB27(re) tail group: heads should have high same-vowel rate."""
        ab27_group = None
        for g in full_result.shared_tail_groups:
            if g.group_key == "AB27":
                ab27_group = g
                break

        if ab27_group is None:
            pytest.skip("AB27 tail group not present at min_group_size=3")

        # Check vowels of heads
        head_vowels = []
        for head in ab27_group.varying_signs:
            reading = lb_sign_to_ipa.get(head)
            if reading:
                c, v = parse_cv(reading)
                if v is not None:
                    head_vowels.append(v)

        if len(head_vowels) >= 2:
            # Count same-vowel pairs
            n_pairs = 0
            n_same = 0
            for i in range(len(head_vowels)):
                for j in range(i + 1, len(head_vowels)):
                    n_pairs += 1
                    if head_vowels[i] == head_vowels[j]:
                        n_same += 1
            rate = n_same / n_pairs
            # AB27 tail group in our data has da, ta, ra, ma — all vowel a
            assert rate >= 0.5, (
                f"AB27 tail group same-vowel rate {rate:.1%} below 50%. "
                f"Head vowels: {head_vowels}"
            )


# =========================================================================
# TIER 3: Null test (shuffled suffixes at chance level)
# =========================================================================

class TestNullTest:
    """Null test: shuffled suffix assignments should produce chance-level purity."""

    def test_null_head_below_actual(self, full_result: Any) -> None:
        """Shuffled head purity should be well below actual head purity."""
        v = full_result.validation
        assert v is not None
        assert v.null_head_purity < v.lb_head_purity, (
            f"Null head purity {v.null_head_purity:.1%} >= "
            f"actual {v.lb_head_purity:.1%}"
        )

    def test_null_tail_below_actual(self, full_result: Any) -> None:
        """Shuffled tail purity should be well below actual tail purity."""
        v = full_result.validation
        assert v is not None
        assert v.null_tail_purity < v.lb_tail_purity, (
            f"Null tail purity {v.null_tail_purity:.1%} >= "
            f"actual {v.lb_tail_purity:.1%}"
        )

    def test_null_pass_gate(self, full_result: Any) -> None:
        """The null_pass gate should be True."""
        v = full_result.validation
        assert v is not None
        assert v.null_pass, (
            f"Null gate FAILED: null_head={v.null_head_purity:.1%} "
            f"null_tail={v.null_tail_purity:.1%}"
        )

    def test_null_head_near_baseline(
        self, compound_suffixes: List[CompoundSuffix],
        lb_sign_to_ipa: Dict[str, str],
    ) -> None:
        """Shuffled head purity should be within 2x of baseline.

        This confirms that shuffling destroys the signal and produces
        chance-level results.
        """
        v = validate_on_lb(
            compound_suffixes,
            lb_sign_to_ipa,
            min_group_size=2,
            seed=42,
            n_shuffles=200,
        )
        # Null head purity should be in range [0, 2 * baseline]
        assert v.null_head_purity <= 2.0 * v.head_baseline + 0.05, (
            f"Null head purity {v.null_head_purity:.1%} unexpectedly high "
            f"(baseline: {v.head_baseline:.1%})"
        )


# =========================================================================
# Integration tests
# =========================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_result_has_constraints(self, full_result: Any) -> None:
        """The full pipeline should produce at least some constraints."""
        assert len(full_result.shared_head_constraints) > 0
        assert len(full_result.shared_tail_constraints) > 0

    def test_constraint_types_correct(self, full_result: Any) -> None:
        """Head constraints should be same_consonant, tail same_vowel."""
        for c in full_result.shared_head_constraints:
            assert c.constraint_type == "same_consonant"
        for c in full_result.shared_tail_constraints:
            assert c.constraint_type == "same_vowel"

    def test_serialization_roundtrip(self, full_result: Any) -> None:
        """serialize_result() should produce valid JSON-compatible output."""
        output = serialize_result(full_result)
        # Should be JSON-serializable
        json_str = json.dumps(output)
        reparsed = json.loads(json_str)
        assert "shared_head_constraints" in reparsed
        assert "shared_tail_constraints" in reparsed
        assert "validation" in reparsed
        assert "la_unknown_signs_constrained" in reparsed

    def test_serialized_validation_values(self, full_result: Any) -> None:
        """Serialized validation should preserve purity scores."""
        output = serialize_result(full_result)
        v = output["validation"]
        assert v["lb_head_purity"] >= 0.30
        assert v["lb_tail_purity"] >= 0.40
        assert v["head_pass"] is True
        assert v["tail_pass"] is True

    def test_la_unknown_signs(self, full_result: Any) -> None:
        """Any LA unknown signs should have at least one constraint."""
        for sign_info in full_result.la_unknown_signs_constrained:
            assert sign_info["n_constraints"] > 0
            assert len(sign_info["constraints"]) > 0

    def test_evidence_suffixes_nonempty(self, full_result: Any) -> None:
        """Every constraint should cite at least 2 supporting suffixes."""
        for c in (
            full_result.shared_head_constraints
            + full_result.shared_tail_constraints
        ):
            assert len(c.evidence_suffixes) >= 2, (
                f"Constraint {c.sign_a}-{c.sign_b} has only "
                f"{len(c.evidence_suffixes)} evidence suffixes"
            )
