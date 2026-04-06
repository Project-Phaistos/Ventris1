"""3-tier tests for the analytical null cognate search.

Tier 1 (formula): NED properties, BH-FDR math, null distribution properties
Tier 2 (known-answer): Validation Gates 1-3
Tier 3 (null/negative): random SCA strings should not survive FDR

Per Section 13.4 of STANDARDS_AND_PROCEDURES.md.
"""

from __future__ import annotations

import random
import pytest

from pillar5.scripts.analytical_null_search import (
    ipa_to_sca,
    normalized_edit_distance,
    bh_fdr_correction,
    build_null_table,
    pvalue_from_null_table,
    analytical_pvalue,
    search_lexicon_full,
    bucket_lexicon,
    cap_bucketed_lexicon,
    load_lexicon,
    self_consistency_analysis,
    aggregate_by_stem_language,
    run_validation_gates,
    _count_pool_size,
    SCA_ALPHABET,
    SCA_K,
    DOLGOPOLSKY,
    NULL_SAMPLES,
)


# ============================================================
# Tier 1: Formula-level mathematical correctness
# ============================================================


class TestNEDProperties:
    """Test normalized edit distance formula correctness."""

    def test_identical_strings_return_zero(self):
        assert normalized_edit_distance("PATER", "PATER") == 0.0

    def test_completely_different_strings(self):
        # "ABC" vs "XYZ" -- 3 substitutions, max_len=3
        ned = normalized_edit_distance("ABC", "XYZ")
        assert ned == 1.0

    def test_one_substitution(self):
        # "PATER" vs "MATER" -- 1 sub, max_len=5
        ned = normalized_edit_distance("PATER", "MATER")
        assert ned == pytest.approx(1 / 5, abs=1e-10)

    def test_one_deletion(self):
        # "PATER" vs "PTER" -- 1 delete, max_len=5
        ned = normalized_edit_distance("PATER", "PTER")
        assert ned == pytest.approx(1 / 5, abs=1e-10)

    def test_empty_string(self):
        assert normalized_edit_distance("", "ABC") == 1.0
        assert normalized_edit_distance("ABC", "") == 1.0
        assert normalized_edit_distance("", "") == 1.0

    def test_symmetry(self):
        ned1 = normalized_edit_distance("PATER", "MATER")
        ned2 = normalized_edit_distance("MATER", "PATER")
        assert ned1 == ned2

    def test_triangle_inequality(self):
        # NED satisfies triangle inequality on the unnormalized part
        a, b, c = "PATER", "MATER", "MAKER"
        ab = normalized_edit_distance(a, b) * max(len(a), len(b))
        bc = normalized_edit_distance(b, c) * max(len(b), len(c))
        ac = normalized_edit_distance(a, c) * max(len(a), len(c))
        assert ac <= ab + bc + 1e-10

    def test_single_char(self):
        assert normalized_edit_distance("A", "A") == 0.0
        assert normalized_edit_distance("A", "B") == 1.0


class TestIPAToSCA:
    """Test IPA to SCA conversion correctness."""

    def test_pater_to_sca(self):
        assert ipa_to_sca("pater") == "PVTVR"

    def test_vowels_collapse(self):
        # All vowels -> V
        assert ipa_to_sca("aeiou") == "VVVVV"

    def test_known_consonant_classes(self):
        assert ipa_to_sca("p") == "P"
        assert ipa_to_sca("t") == "T"
        assert ipa_to_sca("s") == "S"
        assert ipa_to_sca("k") == "K"
        assert ipa_to_sca("m") == "M"
        assert ipa_to_sca("n") == "N"
        assert ipa_to_sca("l") == "L"
        assert ipa_to_sca("r") == "R"
        assert ipa_to_sca("w") == "W"
        assert ipa_to_sca("j") == "J"
        assert ipa_to_sca("h") == "H"

    def test_unknown_chars_dropped(self):
        # Characters not in DOLGOPOLSKY are dropped
        result = ipa_to_sca("p.a.t")
        assert result == "PVT"

    def test_empty_input(self):
        assert ipa_to_sca("") == ""

    def test_sca_alphabet_coverage(self):
        # Ensure all 12 SCA classes are represented
        all_classes = set(DOLGOPOLSKY.values())
        assert all_classes == set(SCA_ALPHABET)
        assert len(SCA_ALPHABET) == 12


class TestBHFDR:
    """Test Benjamini-Hochberg FDR correction math."""

    def test_empty_input(self):
        assert bh_fdr_correction([]) == []

    def test_single_significant_pvalue(self):
        qvals = bh_fdr_correction([0.01])
        assert qvals == [0.01]

    def test_single_nonsignificant_pvalue(self):
        qvals = bh_fdr_correction([0.5])
        assert qvals == [0.5]

    def test_monotonicity(self):
        """Q-values should be non-decreasing when sorted by p-value."""
        pvals = [0.001, 0.01, 0.03, 0.04, 0.05, 0.10, 0.50]
        qvals = bh_fdr_correction(pvals)
        # Sort both by p-value
        paired = sorted(zip(pvals, qvals), key=lambda x: x[0])
        sorted_q = [q for _, q in paired]
        for i in range(1, len(sorted_q)):
            assert sorted_q[i] >= sorted_q[i - 1] - 1e-10

    def test_qvalues_bounded_by_one(self):
        qvals = bh_fdr_correction([0.5, 0.6, 0.8, 0.9])
        for q in qvals:
            assert q <= 1.0

    def test_known_bh_computation(self):
        """Test with hand-computed BH values.

        m=5, alpha=0.05
        Sorted p-values: 0.001, 0.01, 0.03, 0.20, 0.50
        BH thresholds: 0.01, 0.02, 0.03, 0.04, 0.05
        k* = 3 (p_(3)=0.03 <= 3/5 * 0.05 = 0.03)

        Q-values:
          q_(5) = min(0.50*5/5, 1) = 0.50
          q_(4) = min(0.20*5/4, 0.50) = min(0.25, 0.50) = 0.25
          q_(3) = min(0.03*5/3, 0.25) = min(0.05, 0.25) = 0.05
          q_(2) = min(0.01*5/2, 0.05) = min(0.025, 0.05) = 0.025
          q_(1) = min(0.001*5/1, 0.025) = min(0.005, 0.025) = 0.005
        """
        pvals = [0.001, 0.01, 0.03, 0.20, 0.50]
        qvals = bh_fdr_correction(pvals, alpha=0.05)
        assert qvals[0] == pytest.approx(0.005, abs=1e-10)
        assert qvals[1] == pytest.approx(0.025, abs=1e-10)
        assert qvals[2] == pytest.approx(0.05, abs=1e-10)
        assert qvals[3] == pytest.approx(0.25, abs=1e-10)
        assert qvals[4] == pytest.approx(0.50, abs=1e-10)

    def test_all_significant(self):
        pvals = [0.0001, 0.0002, 0.0003]
        qvals = bh_fdr_correction(pvals, alpha=0.05)
        # All should have small q-values
        for q in qvals:
            assert q < 0.05

    def test_none_significant(self):
        pvals = [0.5, 0.6, 0.7, 0.8, 0.9]
        qvals = bh_fdr_correction(pvals, alpha=0.05)
        for q in qvals:
            assert q >= 0.05


class TestAnalyticalPvalue:
    """Test properties of the analytical p-value formula."""

    def test_exact_match_small_pool_is_small(self):
        """Exact match (NED=0) against small pool should have small p-value."""
        p = analytical_pvalue(0.0, 5, 100)
        assert p < 0.01

    def test_exact_match_large_pool_is_larger(self):
        """Larger pool increases chance of random match."""
        p_small = analytical_pvalue(0.0, 5, 100)
        p_large = analytical_pvalue(0.0, 5, 3000)
        assert p_large > p_small

    def test_longer_strings_more_discriminative(self):
        """Longer SCA strings should give smaller p-values for same NED."""
        p_short = analytical_pvalue(0.0, 4, 1000)
        p_long = analytical_pvalue(0.0, 8, 1000)
        assert p_long < p_short

    def test_high_ned_gives_high_pvalue(self):
        """Poor matches (high NED) should give high p-values."""
        p = analytical_pvalue(0.8, 5, 1000)
        assert p > 0.5

    def test_zero_pool_gives_one(self):
        """Empty pool should return p-value of 1.0."""
        assert analytical_pvalue(0.0, 5, 0) == 1.0

    def test_monotonicity_in_ned(self):
        """p-value should increase with NED (worse matches are less significant)."""
        for pool in [100, 1000]:
            prev_p = 0.0
            for ned in [0.0, 0.1, 0.2, 0.3, 0.5, 0.8]:
                p = analytical_pvalue(ned, 6, pool)
                assert p >= prev_p - 1e-10, f"Non-monotonic at NED={ned}, pool={pool}"
                prev_p = p

    def test_pvalue_bounded_zero_one(self):
        """p-value should always be in [0, 1]."""
        for ned in [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]:
            for L in [3, 5, 8, 10]:
                for N in [10, 100, 1000, 10000]:
                    p = analytical_pvalue(ned, L, N)
                    assert 0.0 <= p <= 1.0


class TestAggregateByStomLanguage:
    """Test per-hypothesis aggregation (best reading per stem-language pair)."""

    def _make_result(self, stem_ids, reading_map, language, p_value):
        """Helper to construct a search result dict."""
        return {
            "stem_ids": stem_ids,
            "readings": stem_ids,  # simplified
            "reading_for_unknown": reading_map,
            "complete_ipa": "test",
            "complete_sca": "TVST",
            "language": language,
            "matched_word": "word",
            "matched_ipa": "ipa",
            "matched_sca": "SCA",
            "gloss": "gloss",
            "ned_distance": 0.1,
            "raw_p_value": p_value,
        }

    def test_single_reading_no_correction(self):
        """With one reading, corrected p = raw p (Bonferroni * 1)."""
        results = [
            self._make_result(["AB07", "AB08"], {}, "hit", 0.01),
        ]
        agg = aggregate_by_stem_language(results)
        assert len(agg) == 1
        assert agg[0]["corrected_p_value"] == pytest.approx(0.01)
        assert agg[0]["n_readings_tested"] == 1

    def test_multiple_readings_bonferroni(self):
        """Best p-value is multiplied by number of readings."""
        results = [
            self._make_result(["AB07", "AB08"], {"AB08": "ra"}, "hit", 0.05),
            self._make_result(["AB07", "AB08"], {"AB08": "ka"}, "hit", 0.01),
            self._make_result(["AB07", "AB08"], {"AB08": "ta"}, "hit", 0.10),
        ]
        agg = aggregate_by_stem_language(results)
        assert len(agg) == 1
        # Best p=0.01, n_readings=3 -> corrected = 0.03
        assert agg[0]["corrected_p_value"] == pytest.approx(0.03)
        assert agg[0]["n_readings_tested"] == 3
        assert agg[0]["best_reading_for_unknown"] == {"AB08": "ka"}

    def test_bonferroni_capped_at_one(self):
        """Corrected p-value never exceeds 1.0."""
        results = [
            self._make_result(["AB07", "AB08"], {"AB08": "ra"}, "hit", 0.50),
            self._make_result(["AB07", "AB08"], {"AB08": "ka"}, "hit", 0.60),
            self._make_result(["AB07", "AB08"], {"AB08": "ta"}, "hit", 0.70),
        ]
        agg = aggregate_by_stem_language(results)
        assert agg[0]["corrected_p_value"] == 1.0

    def test_different_languages_separate_groups(self):
        """Same stem against different languages produces separate entries."""
        results = [
            self._make_result(["AB07", "AB08"], {}, "hit", 0.01),
            self._make_result(["AB07", "AB08"], {}, "grc", 0.02),
            self._make_result(["AB07", "AB08"], {}, "lat", 0.03),
        ]
        agg = aggregate_by_stem_language(results)
        assert len(agg) == 3

    def test_different_stems_separate_groups(self):
        """Different stems against same language produce separate entries."""
        results = [
            self._make_result(["AB07", "AB08"], {}, "hit", 0.01),
            self._make_result(["AB10", "AB13"], {}, "hit", 0.02),
        ]
        agg = aggregate_by_stem_language(results)
        assert len(agg) == 2

    def test_aggregation_reduces_count(self):
        """3 readings x 2 languages = 6 raw -> 2 aggregated."""
        results = []
        for lang in ["hit", "grc"]:
            for reading in ["ra", "ka", "ta"]:
                results.append(
                    self._make_result(["AB07", "AB08"], {"AB08": reading}, lang, 0.05)
                )
        agg = aggregate_by_stem_language(results)
        assert len(agg) == 2
        for a in agg:
            assert a["n_readings_tested"] == 3

    def test_empty_input(self):
        """Empty search results produce empty aggregation."""
        assert aggregate_by_stem_language([]) == []

    def test_best_reading_selected(self):
        """The reading with the lowest raw p-value is selected."""
        results = [
            self._make_result(["AB07", "AB60"], {"AB60": "ra"}, "hit", 0.10),
            self._make_result(["AB07", "AB60"], {"AB60": "ka"}, "hit", 0.001),
            self._make_result(["AB07", "AB60"], {"AB60": "ta"}, "hit", 0.05),
            self._make_result(["AB07", "AB60"], {"AB60": "pa"}, "hit", 0.20),
        ]
        agg = aggregate_by_stem_language(results)
        assert agg[0]["best_reading_for_unknown"] == {"AB60": "ka"}
        assert agg[0]["best_raw_p_value"] == 0.001
        # Bonferroni: 0.001 * 4 = 0.004
        assert agg[0]["corrected_p_value"] == pytest.approx(0.004)


class TestNullDistribution:
    """Test properties of the Monte Carlo null distribution."""

    @pytest.fixture
    def small_lexicon(self):
        """Build a small deterministic lexicon for testing."""
        return [
            {"word": "test1", "ipa": "pater", "sca": "PVTVR", "gloss": ""},
            {"word": "test2", "ipa": "mater", "sca": "MVTVR", "gloss": ""},
            {"word": "test3", "ipa": "aster", "sca": "VSTVR", "gloss": ""},
            {"word": "test4", "ipa": "nomen", "sca": "NVMVN", "gloss": ""},
            {"word": "test5", "ipa": "genus", "sca": "KVNVS", "gloss": ""},
        ]

    def test_null_table_is_sorted(self, small_lexicon):
        rng = random.Random(123)
        by_len = bucket_lexicon(small_lexicon)
        null = build_null_table(5, by_len, 100, rng)
        assert null == sorted(null)

    def test_null_table_length(self, small_lexicon):
        rng = random.Random(123)
        by_len = bucket_lexicon(small_lexicon)
        null = build_null_table(5, by_len, 200, rng)
        assert len(null) == 200

    def test_null_values_in_range(self, small_lexicon):
        rng = random.Random(123)
        by_len = bucket_lexicon(small_lexicon)
        null = build_null_table(5, by_len, 100, rng)
        for v in null:
            assert 0.0 <= v <= 1.0

    def test_pvalue_exact_match_is_small(self, small_lexicon):
        """An exact match should have a very small p-value."""
        rng = random.Random(42)
        by_len = bucket_lexicon(small_lexicon)
        null = build_null_table(5, by_len, 1000, rng)
        p = pvalue_from_null_table(0.0, null)
        assert p <= 0.05

    def test_pvalue_high_distance_is_large(self, small_lexicon):
        """A very poor match should have a high p-value."""
        rng = random.Random(42)
        by_len = bucket_lexicon(small_lexicon)
        null = build_null_table(5, by_len, 1000, rng)
        p = pvalue_from_null_table(0.9, null)
        assert p >= 0.5


# ============================================================
# Tier 2: Known-answer validation (Gates)
# ============================================================


class TestGate1UgariticHebrew:
    """Gate 1: Ugaritic-Hebrew known cognate recovery.

    Must recover at least 5/10 known cognate pairs at FDR q < 0.10.
    """

    @pytest.fixture(scope="class")
    def gate_results(self):
        rng = random.Random(42)
        results = run_validation_gates(rng, verbose=False)
        return results

    def test_gate1_passes(self, gate_results):
        g1 = gate_results["gate1_ugaritic_hebrew"]
        assert g1["status"] == "PASS", (
            f"Gate 1 FAILED: only {g1['recovered']}/{g1['out_of']} "
            f"cognates recovered at FDR q < 0.10"
        )

    def test_gate1_recovers_minimum(self, gate_results):
        g1 = gate_results["gate1_ugaritic_hebrew"]
        assert g1["recovered"] >= 5


class TestGate2GreekLatin:
    """Gate 2: Greek-Latin known cognate recovery.

    Must recover at least 3/10 known cognate pairs at FDR q < 0.10.
    """

    @pytest.fixture(scope="class")
    def gate_results(self):
        rng = random.Random(42)
        results = run_validation_gates(rng, verbose=False)
        return results

    def test_gate2_passes(self, gate_results):
        g2 = gate_results["gate2_greek_latin"]
        assert g2["status"] == "PASS", (
            f"Gate 2 FAILED: only {g2['recovered']}/{g2['out_of']} "
            f"cognates recovered at FDR q < 0.10"
        )

    def test_gate2_recovers_minimum(self, gate_results):
        g2 = gate_results["gate2_greek_latin"]
        assert g2["recovered"] >= 3


class TestGate3FalsePositive:
    """Gate 3: Synthetic SCA null calibration control.

    Searches 10 synthetic random SCA strings against Akkadian.  Since
    the queries are drawn from the same distribution as the MC null,
    a properly calibrated null should produce exactly 0 false positives.
    """

    @pytest.fixture(scope="class")
    def gate_results(self):
        rng = random.Random(42)
        results = run_validation_gates(rng, verbose=False)
        return results

    def test_gate3_passes(self, gate_results):
        g3 = gate_results["gate3_false_positive"]
        assert g3["status"] == "PASS", (
            f"Gate 3 FAILED: {g3['false_positives']}/{g3['out_of']} "
            f"false positives at FDR q < 0.05"
        )

    def test_gate3_zero_false_positives(self, gate_results):
        g3 = gate_results["gate3_false_positive"]
        assert g3["false_positives"] == 0, (
            f"Gate 3: {g3['false_positives']} false positives "
            f"(expected 0 for synthetic random SCA queries)"
        )


# ============================================================
# Tier 3: Null and negative controls
# ============================================================


class TestRandomSCANegativeControl:
    """Random SCA strings should not produce FDR-surviving matches."""

    def test_random_sca_strings_no_fdr_hits(self):
        """Generate 20 random SCA strings, search against a real lexicon,
        and verify none survive FDR correction at alpha=0.05."""
        rng = random.Random(99)

        # Use a medium-sized real lexicon
        lex = load_lexicon("heb")
        if not lex:
            pytest.skip("Hebrew lexicon not available")

        by_len = bucket_lexicon(lex)

        # Generate random queries of various lengths
        pvalues = []
        for _ in range(20):
            L = rng.randint(4, 8)
            query = "".join(rng.choice(SCA_ALPHABET) for _ in range(L))

            # Build null for this length
            null_table = build_null_table(L, by_len, 500, rng)
            ned, _ = search_lexicon_full(query, lex)
            p = pvalue_from_null_table(ned, null_table)
            pvalues.append(p)

        qvalues = bh_fdr_correction(pvalues, alpha=0.05)
        n_sig = sum(1 for q in qvalues if q < 0.05)
        assert n_sig == 0, f"{n_sig} random strings survived FDR (expected 0)"

    def test_null_table_deterministic_with_seed(self):
        """Null tables should be deterministic given the same seed."""
        lex = [
            {"word": "x", "ipa": "pa", "sca": "PV", "gloss": ""},
            {"word": "y", "ipa": "ta", "sca": "TV", "gloss": ""},
            {"word": "z", "ipa": "ka", "sca": "KV", "gloss": ""},
        ]
        by_len = bucket_lexicon(lex)

        rng1 = random.Random(777)
        null1 = build_null_table(3, by_len, 100, rng1)

        rng2 = random.Random(777)
        null2 = build_null_table(3, by_len, 100, rng2)

        assert null1 == null2

    def test_self_consistency_empty_input(self):
        """Self-consistency should return empty list for no significant results."""
        result = self_consistency_analysis([])
        assert result == []

    def test_self_consistency_single_sign(self):
        """Self-consistency with a single contributing sign."""
        sig = [{
            "stem_ids": ["AB07", "AB60", "AB13"],
            "reading_for_unknown": {"AB60": "ra"},
            "language": "hit",
            "q_value": 0.001,
            "matched_word": "test",
        }]
        result = self_consistency_analysis(sig)
        assert len(result) == 1
        assert result[0]["sign_id"] == "AB60"
        assert result[0]["best_reading"] == "ra"
        # Single stem, q < 0.01 -> TENTATIVE
        assert result[0]["confidence"] == "TENTATIVE"
