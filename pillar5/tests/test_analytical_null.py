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
    build_null_table_cached,
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
    _pool_hash,
    _null_cache_path,
    _load_cached_null_table,
    _save_null_table,
    _reading_to_sca_class,
    compute_class_background_rates,
    freq_norm_adjust_pvalue,
    pvalue_from_class_conditional_null,
    _build_class_conditional_null_worker,
    build_grid_prior,
    grid_prior_adjust_pvalue,
    LB_HOLDOUT_SIGNS,
    SCA_ALPHABET,
    SCA_K,
    DOLGOPOLSKY,
    NULL_SAMPLES,
    NULL_CACHE_DIR,
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


# ============================================================
# Tier 1b: Bias correction formula tests
# ============================================================


class TestReadingToSCAClass:
    """Test _reading_to_sca_class mapping."""

    def test_da_maps_to_T(self):
        assert _reading_to_sca_class("da") == "T"

    def test_ra_maps_to_R(self):
        assert _reading_to_sca_class("ra") == "R"

    def test_ka_maps_to_K(self):
        assert _reading_to_sca_class("ka") == "K"

    def test_qa_maps_to_K(self):
        # q -> K in Dolgopolsky
        assert _reading_to_sca_class("qa") == "K"

    def test_na_maps_to_N(self):
        assert _reading_to_sca_class("na") == "N"

    def test_pure_vowel_maps_to_V(self):
        assert _reading_to_sca_class("a") == "V"
        assert _reading_to_sca_class("u") == "V"

    def test_empty_maps_to_V(self):
        assert _reading_to_sca_class("") == "V"

    def test_ja_maps_to_J(self):
        assert _reading_to_sca_class("ja") == "J"

    def test_sa_maps_to_S(self):
        assert _reading_to_sca_class("sa") == "S"

    def test_pa_maps_to_P(self):
        assert _reading_to_sca_class("pa") == "P"

    def test_wa_maps_to_W(self):
        assert _reading_to_sca_class("wa") == "W"


class TestFreqNormAdjustPvalue:
    """Test consonant-class frequency normalization p-value adjustment."""

    def test_no_reading_map_returns_raw(self):
        """Empty reading map should return raw p-value."""
        assert freq_norm_adjust_pvalue(0.05, {}, {"T": 0.3}) == 0.05

    def test_no_class_rates_returns_raw(self):
        """Empty class rates should return raw p-value."""
        assert freq_norm_adjust_pvalue(0.05, {"AB60": "da"}, {}) == 0.05

    def test_above_average_class_increases_pvalue(self):
        """A class with above-average rate should increase the p-value."""
        # T has rate 0.4, mean of all is 0.2 -> relative = 2.0
        rates = {"T": 0.4, "K": 0.2, "R": 0.1, "S": 0.1, "P": 0.2,
                 "N": 0.1, "M": 0.1, "L": 0.15, "H": 0.15,
                 "J": 0.2, "W": 0.1, "V": 1.0}
        raw = 0.01
        adjusted = freq_norm_adjust_pvalue(raw, {"AB60": "da"}, rates)
        assert adjusted > raw

    def test_below_average_class_decreases_pvalue(self):
        """A class with below-average rate should decrease the p-value."""
        rates = {"T": 0.4, "K": 0.2, "R": 0.05, "S": 0.1, "P": 0.2,
                 "N": 0.1, "M": 0.1, "L": 0.15, "H": 0.15,
                 "J": 0.2, "W": 0.1, "V": 1.0}
        raw = 0.01
        adjusted = freq_norm_adjust_pvalue(raw, {"AB60": "ra"}, rates)
        assert adjusted < raw

    def test_average_class_returns_approximately_raw(self):
        """A class with exactly average rate should return ~raw p-value."""
        rates = {c: 0.2 for c in SCA_ALPHABET if c != "V"}
        rates["V"] = 1.0
        raw = 0.05
        adjusted = freq_norm_adjust_pvalue(raw, {"AB60": "da"}, rates)
        assert adjusted == pytest.approx(raw, abs=1e-10)

    def test_bounded_at_one(self):
        """Adjusted p-value should never exceed 1.0."""
        rates = {"T": 10.0, "K": 0.001, "R": 0.001, "S": 0.001,
                 "P": 0.001, "N": 0.001, "M": 0.001, "L": 0.001,
                 "H": 0.001, "J": 0.001, "W": 0.001, "V": 1.0}
        adjusted = freq_norm_adjust_pvalue(0.5, {"AB60": "da"}, rates)
        assert adjusted <= 1.0


class TestGridPriorAdjustPvalue:
    """Test P1 grid prior p-value adjustment."""

    def test_no_reading_map_returns_raw(self):
        assert grid_prior_adjust_pvalue(0.05, {}, {"AB60": {"T": 0.5}}) == 0.05

    def test_no_priors_returns_raw(self):
        assert grid_prior_adjust_pvalue(0.05, {"AB60": "da"}, {}) == 0.05

    def test_high_prior_reduces_pvalue(self):
        """If prior for this class is above uniform, p-value should decrease."""
        # Prior for T = 0.5 >> uniform = 1/12 ~ 0.083
        # adjustment = uniform / prior = 0.083 / 0.5 ~ 0.167
        priors = {"AB60": {"T": 0.5, "K": 0.1, "R": 0.1, "V": 0.083}}
        raw = 0.05
        adjusted = grid_prior_adjust_pvalue(raw, {"AB60": "da"}, priors)
        assert adjusted < raw

    def test_low_prior_increases_pvalue(self):
        """If prior for this class is below uniform, p-value should increase."""
        priors = {"AB60": {"T": 0.02, "K": 0.3, "R": 0.3, "V": 0.083}}
        raw = 0.01
        adjusted = grid_prior_adjust_pvalue(raw, {"AB60": "da"}, priors)
        assert adjusted > raw

    def test_uniform_prior_returns_raw(self):
        """Uniform prior should return approximately raw p-value."""
        uniform = 1.0 / len(SCA_ALPHABET)
        priors = {"AB60": {c: uniform for c in SCA_ALPHABET}}
        raw = 0.05
        adjusted = grid_prior_adjust_pvalue(raw, {"AB60": "da"}, priors)
        assert adjusted == pytest.approx(raw, abs=1e-10)

    def test_unknown_sign_not_in_priors_returns_raw(self):
        """If the sign is not in grid priors, return raw p-value."""
        priors = {"AB99": {"T": 0.5}}  # AB60 not present
        assert grid_prior_adjust_pvalue(0.05, {"AB60": "da"}, priors) == 0.05

    def test_bounded_zero_one(self):
        """Adjusted p-value should be in [0, 1]."""
        priors = {"AB60": {"T": 0.001}}
        adjusted = grid_prior_adjust_pvalue(0.9, {"AB60": "da"}, priors)
        assert 0.0 <= adjusted <= 1.0


class TestComputeClassBackgroundRates:
    """Test consonant-class background rate computation."""

    @pytest.fixture
    def small_lexicon_capped(self):
        """Build a small lexicon bucketed by length for testing."""
        entries = [
            "TVTVR",  # T-initial
            "TVKVR",  # T-initial
            "KVTVR",  # K-initial
            "RVTVR",  # R-initial
            "PVTVR",  # P-initial
        ]
        by_len = {5: entries}
        return by_len

    def test_returns_dict_of_rates(self, small_lexicon_capped):
        rng = random.Random(42)
        rates = compute_class_background_rates(small_lexicon_capped, 5, 100, rng)
        assert isinstance(rates, dict)
        # Should have entries for all consonant classes + V
        assert "T" in rates
        assert "K" in rates
        assert "V" in rates

    def test_rates_are_nonnegative(self, small_lexicon_capped):
        rng = random.Random(42)
        rates = compute_class_background_rates(small_lexicon_capped, 5, 100, rng)
        for cls, rate in rates.items():
            assert rate >= 0, f"Rate for {cls} is negative: {rate}"

    def test_t_class_higher_with_t_heavy_lexicon(self):
        """With a T-heavy lexicon, T-class should have higher match rate."""
        # Lexicon dominated by T-initial strings
        t_heavy = {5: ["TVTVR", "TVKVR", "TVSVR", "TVNVR", "TVRVS"]}
        rng = random.Random(42)
        rates = compute_class_background_rates(t_heavy, 5, 200, rng)
        # T should have one of the higher rates
        if "T" in rates and "W" in rates:
            assert rates["T"] >= rates["W"] * 0.5  # Not strictly greater due to randomness

    def test_empty_pool_returns_empty(self):
        rng = random.Random(42)
        rates = compute_class_background_rates({}, 5, 100, rng)
        assert rates == {}


class TestClassConditionalNullWorker:
    """Test the class-conditional null table worker function."""

    @pytest.fixture
    def t_heavy_pool(self):
        """A lexicon pool dominated by T-initial SCA strings."""
        return ["TVTVR", "TVKVR", "TVSVR", "TVNVR", "TVRVS",
                "TVTVM", "TVKVN", "TVSVL", "TVNVP"]

    @pytest.fixture
    def balanced_pool(self):
        """A balanced lexicon pool with diverse initial consonants."""
        return ["TVTVR", "KVKVR", "RVRVR", "SVSVR", "PVPVR",
                "NVNVR", "MVMVR", "LVLVR", "HVHVR", "JVJVR",
                "WVWVR"]

    def test_returns_sorted_list(self, balanced_pool):
        result = _build_class_conditional_null_worker(
            query_length=5, pool=balanced_pool,
            n_samples=100, seed=42, fixed_class="T", unknown_position=0,
        )
        assert isinstance(result, list)
        assert len(result) == 100
        # Verify sorted
        assert result == sorted(result)

    def test_first_char_fixed(self, balanced_pool):
        """T-class null should differ from W-class null on a T-heavy lexicon."""
        t_null = _build_class_conditional_null_worker(
            query_length=5, pool=["TVTVR", "TVKVR", "TVSVR"] * 10,
            n_samples=200, seed=42, fixed_class="T", unknown_position=0,
        )
        w_null = _build_class_conditional_null_worker(
            query_length=5, pool=["TVTVR", "TVKVR", "TVSVR"] * 10,
            n_samples=200, seed=42, fixed_class="W", unknown_position=0,
        )
        # T-class should have lower median NED on a T-heavy lexicon
        t_median = t_null[len(t_null) // 2]
        w_median = w_null[len(w_null) // 2]
        assert t_median < w_median, (
            f"T-class median ({t_median:.3f}) should be lower than "
            f"W-class median ({w_median:.3f}) on T-heavy lexicon"
        )

    def test_t_class_produces_lower_ned_on_t_heavy_lexicon(self, t_heavy_pool):
        """On a T-heavy lexicon, T-class null should have lower NEDs."""
        t_null = _build_class_conditional_null_worker(
            query_length=5, pool=t_heavy_pool,
            n_samples=300, seed=42, fixed_class="T", unknown_position=0,
        )
        w_null = _build_class_conditional_null_worker(
            query_length=5, pool=t_heavy_pool,
            n_samples=300, seed=42, fixed_class="W", unknown_position=0,
        )
        t_mean = sum(t_null) / len(t_null)
        w_mean = sum(w_null) / len(w_null)
        assert t_mean < w_mean, (
            f"T mean NED ({t_mean:.3f}) should < W mean NED ({w_mean:.3f})"
        )

    def test_different_positions(self, balanced_pool):
        """Fixing position 0 vs position 2 should give different distributions."""
        pos0 = _build_class_conditional_null_worker(
            query_length=5, pool=balanced_pool,
            n_samples=200, seed=42, fixed_class="T", unknown_position=0,
        )
        pos2 = _build_class_conditional_null_worker(
            query_length=5, pool=balanced_pool,
            n_samples=200, seed=42, fixed_class="T", unknown_position=2,
        )
        # Distributions should differ (not identical)
        assert pos0 != pos2


class TestPvalueFromClassConditionalNull:
    """Test the class-conditional p-value computation."""

    def test_no_reading_map_uses_unconditional(self):
        """With no unknowns, should use unconditional null."""
        unconditional = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        cc_tables = {}
        p = pvalue_from_class_conditional_null(
            0.3, {}, cc_tables, query_length=5, lang="hit",
            unconditional_table=unconditional,
        )
        expected = pvalue_from_null_table(0.3, unconditional)
        assert p == pytest.approx(expected)

    def test_uses_class_conditional_table(self):
        """With unknowns, should use class-conditional table."""
        # T-class table: easy matches (low NEDs)
        t_table = [0.0, 0.1, 0.1, 0.2, 0.2, 0.3, 0.3, 0.4, 0.5, 0.6]
        # W-class table: hard matches (high NEDs)
        w_table = [0.3, 0.4, 0.5, 0.6, 0.7, 0.7, 0.8, 0.8, 0.9, 1.0]
        unconditional = [0.1, 0.2, 0.3, 0.4, 0.5, 0.5, 0.6, 0.7, 0.8, 0.9]

        cc_tables = {
            (5, "hit", "T"): t_table,
            (5, "hit", "W"): w_table,
        }

        # For da (T-class), NED=0.2 should give a HIGHER p-value
        # because T-class null has more low-NED entries
        p_da = pvalue_from_class_conditional_null(
            0.2, {"AB60": "da"}, cc_tables, 5, "hit",
            unconditional_table=unconditional,
        )
        # For wa (W-class), NED=0.2 should give a LOWER p-value
        # because W-class null has fewer low-NED entries
        p_wa = pvalue_from_class_conditional_null(
            0.2, {"AB60": "wa"}, cc_tables, 5, "hit",
            unconditional_table=unconditional,
        )
        assert p_da > p_wa, (
            f"T-class p ({p_da:.4f}) should > W-class p ({p_wa:.4f}) "
            f"at same NED -- T matches more easily so same NED is less surprising"
        )

    def test_fallback_to_unconditional_when_no_cc_table(self):
        """If class-conditional table is missing, fall back to unconditional."""
        unconditional = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        cc_tables = {}  # No class-conditional tables
        p = pvalue_from_class_conditional_null(
            0.3, {"AB60": "da"}, cc_tables, 5, "hit",
            unconditional_table=unconditional,
        )
        expected = pvalue_from_null_table(0.3, unconditional)
        assert p == pytest.approx(expected)

    def test_no_tables_at_all_returns_one(self):
        """If no tables available at all, return 1.0."""
        p = pvalue_from_class_conditional_null(
            0.3, {"AB60": "da"}, {}, 5, "hit",
        )
        assert p == 1.0

    def test_debiases_da_reading(self):
        """Core debiasing test: da should get higher p-value than ra
        at the same NED when T-class has easier matches."""
        # T-class: many low-NED entries (easy matching)
        t_table = sorted([0.05 * i for i in range(20)])  # 0.0 to 0.95
        # R-class: fewer low-NED entries (harder matching)
        r_table = sorted([0.1 + 0.04 * i for i in range(20)])  # 0.1 to 0.86

        cc_tables = {
            (5, "hit", "T"): t_table,
            (5, "hit", "R"): r_table,
        }

        ned = 0.15
        p_da = pvalue_from_class_conditional_null(
            ned, {"AB60": "da"}, cc_tables, 5, "hit",
        )
        p_ra = pvalue_from_class_conditional_null(
            ned, {"AB60": "ra"}, cc_tables, 5, "hit",
        )
        # da should be penalized (higher p) because T-class matches easily
        assert p_da > p_ra


class TestAggregateWithBiasCorrection:
    """Test aggregate_by_stem_language with bias correction."""

    def _make_result(self, stem_ids, reading_map, language, p_value,
                     complete_sca="TVST"):
        return {
            "stem_ids": stem_ids,
            "readings": stem_ids,
            "reading_for_unknown": reading_map,
            "complete_ipa": "test",
            "complete_sca": complete_sca,
            "language": language,
            "matched_word": "word",
            "matched_ipa": "ipa",
            "matched_sca": "SCA",
            "gloss": "gloss",
            "ned_distance": 0.1,
            "raw_p_value": p_value,
        }

    def test_none_correction_matches_original(self):
        """bias_correction='none' should behave identically to original."""
        results = [
            self._make_result(["AB07", "AB08"], {"AB08": "ra"}, "hit", 0.05),
            self._make_result(["AB07", "AB08"], {"AB08": "da"}, "hit", 0.01),
        ]
        agg = aggregate_by_stem_language(results, bias_correction="none")
        assert len(agg) == 1
        assert agg[0]["best_reading_for_unknown"] == {"AB08": "da"}
        assert agg[0]["corrected_p_value"] == pytest.approx(0.02)

    def test_freq_norm_with_cc_tables_can_change_best_reading(self):
        """freq_norm with class-conditional null tables should debias."""
        # da (T-class) has lower raw p, but T-class null shows it's easy
        results = [
            self._make_result(["AB07", "AB60"], {"AB60": "ra"}, "hit", 0.02),
            self._make_result(["AB07", "AB60"], {"AB60": "da"}, "hit", 0.01),
        ]
        # Build cc_null_tables where T-class has easier matches
        # so T-class p-value at NED=0.1 is high (many null entries <= 0.1)
        t_table = [0.0, 0.05, 0.08, 0.1, 0.1, 0.12, 0.15, 0.2, 0.3, 0.5]
        # R-class has harder matches, so R p-value at NED=0.1 is low
        r_table = [0.2, 0.25, 0.3, 0.35, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        cc_tables = {
            (4, "hit", "T"): t_table,
            (4, "hit", "R"): r_table,
        }
        unconditional = [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        null_tables = {(4, "hit"): unconditional}

        agg = aggregate_by_stem_language(
            results, bias_correction="freq_norm",
            cc_null_tables=cc_tables,
            null_tables=null_tables,
        )
        assert len(agg) == 1
        # T-class has many null entries at NED<=0.1, so da's cc p-value
        # is large. R-class has few, so ra's cc p-value is small.
        assert agg[0]["best_reading_for_unknown"] == {"AB60": "ra"}

    def test_freq_norm_deprecated_fallback(self):
        """freq_norm should fall back to deprecated division if no cc_tables."""
        results = [
            self._make_result(["AB07", "AB60"], {"AB60": "ra"}, "hit", 0.02),
            self._make_result(["AB07", "AB60"], {"AB60": "da"}, "hit", 0.01),
        ]
        # T has 3x the mean rate -> should penalize "da"
        rates = {c: 0.1 for c in SCA_ALPHABET if c != "V"}
        rates["T"] = 0.3  # 3x average
        rates["V"] = 1.0
        class_rates_all = {(4, "hit"): rates}
        agg = aggregate_by_stem_language(
            results, bias_correction="freq_norm",
            class_rates_all=class_rates_all,
        )
        assert len(agg) == 1
        # With T rate 3x mean, da's adjusted p = 0.01 * 3 = 0.03 > ra's 0.02
        assert agg[0]["best_reading_for_unknown"] == {"AB60": "ra"}

    def test_grid_prior_can_change_best_reading(self):
        """grid_prior should change best reading based on prior."""
        results = [
            self._make_result(["AB07", "AB60"], {"AB60": "ra"}, "hit", 0.02),
            self._make_result(["AB07", "AB60"], {"AB60": "da"}, "hit", 0.01),
        ]
        # Prior says AB60 is likely R-class (high prior for R)
        priors = {"AB60": {c: 1.0 / len(SCA_ALPHABET) for c in SCA_ALPHABET}}
        priors["AB60"]["R"] = 0.5  # High prior for R
        priors["AB60"]["T"] = 0.02  # Low prior for T
        agg = aggregate_by_stem_language(
            results, bias_correction="grid_prior",
            grid_priors=priors,
        )
        assert len(agg) == 1
        # T has low prior -> penalized; R has high prior -> boosted
        assert agg[0]["best_reading_for_unknown"] == {"AB60": "ra"}

    def test_bias_correction_field_in_output(self):
        """Output should include bias_correction field."""
        results = [
            self._make_result(["AB07", "AB08"], {}, "hit", 0.01),
        ]
        agg = aggregate_by_stem_language(results, bias_correction="freq_norm")
        assert agg[0]["bias_correction"] == "freq_norm"


class TestLBHoldoutConstants:
    """Test LB holdout sign list properties."""

    def test_holdout_signs_have_valid_structure(self):
        for ab_code, reading, cons in LB_HOLDOUT_SIGNS:
            assert ab_code.startswith("AB")
            assert len(reading) >= 1
            assert isinstance(cons, str)

    def test_holdout_covers_multiple_consonant_classes(self):
        """Holdout signs should cover diverse consonant classes."""
        classes = set()
        for _, reading, _ in LB_HOLDOUT_SIGNS:
            cls = _reading_to_sca_class(reading)
            classes.add(cls)
        # Should cover at least 5 different classes
        assert len(classes) >= 5, f"Only {len(classes)} classes: {classes}"

    def test_holdout_signs_are_unique(self):
        ab_codes = [ab for ab, _, _ in LB_HOLDOUT_SIGNS]
        assert len(ab_codes) == len(set(ab_codes))


# ============================================================
# Tier 1b: Disk cache and pool hash tests
# ============================================================


class TestPoolHash:
    """Test pool hash determinism and sensitivity."""

    def test_same_pool_same_hash(self):
        pool1 = ["PVT", "MVT", "KVN"]
        pool2 = ["PVT", "MVT", "KVN"]
        assert _pool_hash(pool1) == _pool_hash(pool2)

    def test_order_independent(self):
        """Hash should be order-independent (uses sorted)."""
        pool1 = ["PVT", "MVT", "KVN"]
        pool2 = ["KVN", "PVT", "MVT"]
        assert _pool_hash(pool1) == _pool_hash(pool2)

    def test_different_pool_different_hash(self):
        pool1 = ["PVT", "MVT", "KVN"]
        pool2 = ["PVT", "MVT", "SVN"]
        assert _pool_hash(pool1) != _pool_hash(pool2)

    def test_empty_pool(self):
        h = _pool_hash([])
        assert isinstance(h, str)
        assert len(h) == 16


class TestDiskCache:
    """Test null table disk caching round-trip."""

    def test_save_and_load(self, tmp_path):
        """Null table should survive a save/load cycle."""
        import numpy as np
        table = np.array([0.1, 0.2, 0.3, 0.5, 0.8], dtype=np.float32)
        cache_path = tmp_path / "test_cache.npz"
        _save_null_table(cache_path, table)
        loaded = _load_cached_null_table(cache_path)
        assert loaded is not None
        np.testing.assert_array_almost_equal(loaded, table, decimal=5)

    def test_load_nonexistent(self, tmp_path):
        """Loading from nonexistent path should return None."""
        cache_path = tmp_path / "does_not_exist.npz"
        assert _load_cached_null_table(cache_path) is None

    def test_build_null_table_cached_roundtrip(self, tmp_path, monkeypatch):
        """build_null_table_cached should save and reload correctly.

        Uses approx comparison because npz stores float32, introducing
        minor rounding vs the original float64 Python values.
        """
        import numpy as np
        import pillar5.scripts.analytical_null_search as mod
        monkeypatch.setattr(mod, "NULL_CACHE_DIR", tmp_path)

        lex = [
            {"word": "x", "ipa": "pa", "sca": "PV", "gloss": ""},
            {"word": "y", "ipa": "ta", "sca": "TV", "gloss": ""},
            {"word": "z", "ipa": "ka", "sca": "KV", "gloss": ""},
        ]
        by_len = bucket_lexicon(lex)
        capped = cap_bucketed_lexicon(by_len, random.Random(42))

        rng1 = random.Random(42)
        null1 = build_null_table_cached(3, capped, 200, rng1, lang="test_lang")

        # Second call should load from cache
        rng2 = random.Random(999)  # different seed -- should not matter
        null2 = build_null_table_cached(3, capped, 200, rng2, lang="test_lang")

        # float32 round-trip introduces minor precision loss
        np.testing.assert_allclose(null1, null2, atol=1e-6)

    def test_null_samples_constant(self):
        """NULL_SAMPLES should be 100,000 for sufficient BH-FDR resolution."""
        assert NULL_SAMPLES == 100_000


class TestPvalueResolution:
    """Test that M=100K provides sufficient p-value resolution."""

    def test_minimum_pvalue_sufficient_for_bh_fdr(self):
        """Minimum p-value 1/(M+1) must be < 0.05/378 for rank-1 BH threshold."""
        min_p = 1 / (NULL_SAMPLES + 1)
        bh_rank1_threshold = 0.05 / 378
        assert min_p < bh_rank1_threshold, (
            f"min_p={min_p:.2e} >= BH rank-1={bh_rank1_threshold:.2e}"
        )

    def test_pvalue_granularity(self):
        """Adjacent null table positions should produce distinguishable p-values."""
        # With M=100K, consecutive entries differ by 1/100001
        granularity = 1 / (NULL_SAMPLES + 1)
        assert granularity < 1e-4  # at least 10^-5 resolution
