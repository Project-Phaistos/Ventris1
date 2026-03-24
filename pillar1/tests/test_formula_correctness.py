"""Tier 1 formula-level mathematical correctness tests for Pillar 1.

Every test verifies a SPECIFIC formula against a HAND-COMPUTED expected value.
These are the ground truth: if any test fails, the pipeline's statistical
reasoning is broken.

Reference: PRD Appendix A.1 and Sections 5.2-5.7.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats
from sklearn.metrics import adjusted_rand_score


# ====================================================================
# vowel_identifier.py formulas
# ====================================================================


class TestEnrichmentScore:
    """Formula: E = (k / n) / p_0"""

    def test_enrichment_score_formula_k83_n90_p0339(self) -> None:
        """Enrichment score: E = (k/n) / p_0.

        Hand computation:
            k = 83  (initial-position count for sign)
            n = 90  (total occurrences of sign)
            p_0 = 0.339  (corpus-wide initial rate)
            E = (83/90) / 0.339
              = 0.92222... / 0.339
              = 2.72041953...
        """
        k, n, p_0 = 83, 90, 0.339
        enrichment_score = (k / n) / p_0
        assert enrichment_score == pytest.approx(2.72041953, rel=1e-4)


class TestPValueInitial:
    """Formula: p_value_initial = binom.sf(k - 1, n, p_0)

    This is P(X >= k | X ~ Bin(n, p_0)), the one-sided binomial test
    for initial-position enrichment.
    """

    def test_p_value_initial_k83_n90_p0339(self) -> None:
        """P(X >= 83 | Bin(90, 0.339)) should be astronomically small.

        Hand reasoning:
            Expected count = 90 * 0.339 = 30.51
            Observed count = 83 (nearly all tokens are initial)
            This is ~8.4 standard deviations above the mean
            (sigma = sqrt(90 * 0.339 * 0.661) = 4.49)
            So the p-value must be < 1e-20.

        Scipy gives: 4.367417e-31
        """
        k, n, p_0 = 83, 90, 0.339
        p_value_initial = stats.binom.sf(k - 1, n, p_0)

        # Verify it is astronomically small
        assert p_value_initial < 1e-20
        # Verify the exact scipy value
        assert p_value_initial == pytest.approx(4.367417e-31, rel=1e-3)


class TestPValueMedial:
    """Formula: p_value_medial = binom.cdf(m, n, p_med)

    This is P(X <= m | X ~ Bin(n, p_med)), the one-sided binomial test
    for medial-position depletion.
    """

    def test_p_value_medial_m3_n90_pmed0322(self) -> None:
        """P(X <= 3 | Bin(90, 0.322)) should be very small.

        Hand reasoning:
            Expected count = 90 * 0.322 = 28.98
            Observed count = 3 (almost never appears medially)
            This is ~5.3 sigma below the mean
            (sigma = sqrt(90 * 0.322 * 0.678) = 4.43)
            So the p-value must be < 1e-10.

        Scipy gives: 8.750389e-12
        """
        m, n, p_med = 3, 90, 0.322
        p_value_medial = stats.binom.cdf(m, n, p_med)

        assert p_value_medial < 1e-10
        assert p_value_medial == pytest.approx(8.750389e-12, rel=1e-3)


class TestPValueCorrected:
    """Formula: p_corrected = min(max(p_init, p_med) * n_tests, 1.0)

    Bonferroni correction: take the LARGER of the two p-values
    (since both tests must pass), multiply by number of tests,
    and cap at 1.0.
    """

    def test_p_value_corrected_basic(self) -> None:
        """Corrected p-value with p_init=1e-25, p_med=1e-12, n_tests=45.

        Hand computation:
            max(1e-25, 1e-12) = 1e-12
            1e-12 * 45 = 4.5e-11
            min(4.5e-11, 1.0) = 4.5e-11
        """
        p_init = 1e-25
        p_med = 1e-12
        n_tests = 45

        p_corrected = max(p_init, p_med) * n_tests
        p_corrected = min(p_corrected, 1.0)

        assert p_corrected == pytest.approx(4.5e-11, rel=1e-6)

    def test_p_value_corrected_caps_at_1(self) -> None:
        """When the Bonferroni product exceeds 1.0, it must cap at 1.0.

        Hand computation:
            max(0.5, 0.8) = 0.8
            0.8 * 45 = 36.0
            min(36.0, 1.0) = 1.0
        """
        p_init = 0.5
        p_med = 0.8
        n_tests = 45

        p_corrected = max(p_init, p_med) * n_tests
        p_corrected = min(p_corrected, 1.0)

        assert p_corrected == 1.0


class TestConfidence:
    """Formula: confidence = min(1 - p_init/alpha_corr, 1 - p_med/alpha_corr)

    Clamped to [0.0, 1.0]. Measures how far below the significance
    threshold each p-value is, as a fraction of the threshold.
    """

    def test_confidence_extreme_p_values(self) -> None:
        """Confidence with very small p-values approaches 1.0.

        Hand computation:
            alpha = 0.05, n_tests = 45
            alpha_corr = 0.05 / 45 = 1/900 = 0.001111...
            p_init = 1e-25
            p_med = 1e-12

            1 - p_init / alpha_corr = 1 - (1e-25 / 1.111e-3)
                                    = 1 - 9.0e-23
                                    ~= 1.0

            1 - p_med / alpha_corr  = 1 - (1e-12 / 1.111e-3)
                                    = 1 - 9.0e-10
                                    = 0.9999999991

            confidence = min(1.0, 0.9999999991) = 0.9999999991
        """
        alpha = 0.05
        n_tests = 45
        alpha_corr = alpha / n_tests

        p_init = 1e-25
        p_med = 1e-12

        confidence = min(
            1.0 - p_init / alpha_corr,
            1.0 - p_med / alpha_corr,
        )
        confidence = max(0.0, min(1.0, confidence))

        assert confidence == pytest.approx(0.9999999991, rel=1e-6)
        # The binding constraint is p_med (the larger p-value)
        assert confidence < 1.0

    def test_confidence_zero_when_p_equals_threshold(self) -> None:
        """When p-value equals alpha_corrected, confidence should be 0.

        Hand computation:
            alpha_corr = 0.001
            p_init = 0.001  (equals threshold)
            p_med = 0.0001
            1 - p_init / alpha_corr = 1 - 1.0 = 0.0
            1 - p_med / alpha_corr  = 1 - 0.1 = 0.9
            confidence = min(0.0, 0.9) = 0.0
        """
        alpha_corr = 0.001
        p_init = 0.001
        p_med = 0.0001

        confidence = min(
            1.0 - p_init / alpha_corr,
            1.0 - p_med / alpha_corr,
        )
        confidence = max(0.0, min(1.0, confidence))

        assert confidence == 0.0


# ====================================================================
# alternation_detector.py formulas
# ====================================================================


class TestExpectedAlternation:
    """Formula: expected = p_a * p_b * n_branching_prefixes

    No symmetry factor: pairs are stored as frozensets (unordered).
    """

    def test_expected_alternation_pa01_pb005_ngroups100(self) -> None:
        """Expected co-occurrence under independence.

        Hand computation:
            p_a = 0.1   (frequency of sign a in final position)
            p_b = 0.05  (frequency of sign b in final position)
            n_branching_prefixes = 100  (number of distinct prefixes with >= 2 continuations)

            expected = 0.1 * 0.05 * 100 = 0.5
        """
        p_a, p_b, n_groups = 0.1, 0.05, 100
        expected = p_a * p_b * n_groups
        assert expected == pytest.approx(0.5, abs=1e-15)


class TestPoissonSignificance:
    """Formula: p_value = poisson.sf(n_stems - 1, expected)

    P(X >= n_stems | X ~ Pois(expected)).
    Tests whether the number of independent stems showing an alternation
    significantly exceeds what is expected under independence.
    """

    def test_poisson_sf_nstems5_expected1(self) -> None:
        """P(X >= 5 | Pois(1.0)).

        Hand computation via Poisson PMF:
            P(X >= 5) = 1 - P(X <= 4)
            P(X=k) = e^{-1} * 1^k / k!

            P(X=0) = e^{-1}           = 0.367879441
            P(X=1) = e^{-1}           = 0.367879441
            P(X=2) = e^{-1}/2         = 0.183939721
            P(X=3) = e^{-1}/6         = 0.061313240
            P(X=4) = e^{-1}/24        = 0.015328310

            P(X<=4) = 0.996340153
            P(X>=5) = 1 - 0.996340153 = 0.003659847

        Scipy gives: 0.003659847
        """
        n_stems, expected = 5, 1.0
        p_value = stats.poisson.sf(n_stems - 1, expected)

        # Verify against hand-computed value
        assert p_value == pytest.approx(0.003659847, rel=1e-4)

        # Cross-check: verify the Poisson CDF identity
        assert p_value == pytest.approx(1.0 - stats.poisson.cdf(4, 1.0), abs=1e-15)

        # Cross-check: verify the hand-computed PMF sum
        hand_cdf = sum(
            math.exp(-1.0) * (1.0 ** k) / math.factorial(k) for k in range(5)
        )
        assert p_value == pytest.approx(1.0 - hand_cdf, rel=1e-10)


# ====================================================================
# phonotactic_analyzer.py formulas
# ====================================================================


class TestExpectedBigramFrequency:
    """Formula: E[i,j] = (row_total * col_total) / grand_total

    Expected frequency under the independence model for a contingency table.
    """

    def test_expected_frequency_row50_col30_total500(self) -> None:
        """Expected bigram count under independence.

        Hand computation:
            row_total = 50  (sign i appears as first element 50 times)
            col_total = 30  (sign j appears as second element 30 times)
            grand_total = 500  (total bigrams in corpus)
            E[i,j] = 50 * 30 / 500 = 1500 / 500 = 3.0
        """
        row_total, col_total, grand_total = 50, 30, 500
        expected = (row_total * col_total) / grand_total
        assert expected == pytest.approx(3.0, abs=1e-15)


class TestStandardizedResidual:
    """Formula: R = (observed - expected) / sqrt(expected)

    Standardized Pearson residual for a contingency table cell.
    """

    def test_std_residual_obs0_exp3(self) -> None:
        """Standardized residual for a zero cell with expected 3.0.

        Hand computation:
            observed = 0
            expected = 3.0
            R = (0 - 3) / sqrt(3)
              = -3 / 1.7320508...
              = -1.7320508...
        """
        observed, expected = 0, 3.0
        std_residual = (observed - expected) / math.sqrt(expected)
        assert std_residual == pytest.approx(-1.7320508076, rel=1e-6)
        # Cross-check with numpy
        assert std_residual == pytest.approx(-math.sqrt(3.0), rel=1e-15)


class TestForbiddenBigramPValue:
    """Formula: p_value = poisson.pmf(0, expected)

    For a zero cell, the probability of observing zero events when
    the Poisson rate is `expected`. Equals e^{-expected}.
    """

    def test_forbidden_bigram_pvalue_exp3(self) -> None:
        """P(X=0 | Pois(3.0)) = e^{-3}.

        Hand computation:
            P(X=0) = e^{-3} * 3^0 / 0!
                   = e^{-3}
                   = 0.049787068...
        """
        expected = 3.0
        p_value = stats.poisson.pmf(0, expected)

        # Verify against hand-computed e^{-3}
        assert p_value == pytest.approx(math.exp(-3.0), rel=1e-10)
        # Verify the numeric value
        assert p_value == pytest.approx(0.049787068, rel=1e-4)


class TestFavoredBigramPValue:
    """Formula: p_value = poisson.sf(obs - 1, expected)

    P(X >= obs | Pois(expected)). Tests whether an observed bigram count
    significantly exceeds the independence expectation.
    """

    def test_favored_bigram_pvalue_obs10_exp3(self) -> None:
        """P(X >= 10 | Pois(3.0)).

        Hand computation (sum of Poisson PMFs for k=0..9):
            P(X=k) = e^{-3} * 3^k / k!

            P(X=0) = 0.04978707
            P(X=1) = 0.14936121
            P(X=2) = 0.22404181
            P(X=3) = 0.22404181
            P(X=4) = 0.16803136
            P(X=5) = 0.10081882
            P(X=6) = 0.05040941
            P(X=7) = 0.02160403
            P(X=8) = 0.00810151
            P(X=9) = 0.00270050

            P(X<=9) = 0.99889752
            P(X>=10) = 1 - 0.99889752 = 0.00110249

        Scipy gives: 0.0011024881
        """
        obs, expected = 10, 3.0
        p_value = stats.poisson.sf(obs - 1, expected)

        assert p_value == pytest.approx(0.0011024881, rel=1e-4)

        # Cross-check: manually sum PMFs for k=0..9
        hand_cdf = sum(
            math.exp(-3.0) * (3.0 ** k) / math.factorial(k) for k in range(10)
        )
        assert p_value == pytest.approx(1.0 - hand_cdf, rel=1e-10)


# ====================================================================
# lb_validator.py — Adjusted Rand Index
# ====================================================================


class TestAdjustedRandIndex:
    """Formula: ARI = (sum C(n_ij,2) - t3) / (0.5*(t1+t2) - t3)

    where t1 = sum C(a_i,2), t2 = sum C(b_j,2), t3 = t1*t2/C(n,2).
    """

    def test_ari_known_clustering(self) -> None:
        """ARI with a known partial mismatch.

        Inputs:
            labels_true = [0, 0, 1, 1, 2, 2]
            labels_pred = [0, 0, 1, 1, 1, 1]  (merges true classes 1 and 2)

        Hand computation of contingency table:
                    pred=0  pred=1
            true=0:   2       0     | a_0 = 2
            true=1:   0       2     | a_1 = 2
            true=2:   0       2     | a_2 = 2
                    -----  -----
            b_j:      2       4

        C(n_ij, 2) values:
            C(2,2)=1  C(0,2)=0
            C(0,2)=0  C(2,2)=1
            C(0,2)=0  C(2,2)=1
            Sum = 3

        Sum C(a_i, 2) = C(2,2) + C(2,2) + C(2,2) = 1 + 1 + 1 = 3
        Sum C(b_j, 2) = C(2,2) + C(4,2) = 1 + 6 = 7
        C(n, 2) = C(6, 2) = 15
        t3 = 3 * 7 / 15 = 21/15 = 1.4

        ARI = (3 - 1.4) / (0.5*(3+7) - 1.4)
            = 1.6 / 3.6
            = 4/9
            = 0.44444...
        """
        labels_true = [0, 0, 1, 1, 2, 2]
        labels_pred = [0, 0, 1, 1, 1, 1]

        ari = adjusted_rand_score(labels_true, labels_pred)

        # Verify against the hand-computed fraction 4/9
        assert ari == pytest.approx(4.0 / 9.0, rel=1e-10)
        assert ari == pytest.approx(0.4444444444, rel=1e-6)

    def test_ari_perfect_agreement(self) -> None:
        """ARI = 1.0 when labels_true == labels_pred.

        Hand reasoning:
            When clusterings are identical, all items in the same true
            cluster are in the same predicted cluster and vice versa.
            Numerator = denominator, so ARI = 1.0.
        """
        labels = [0, 0, 1, 1, 2, 2]
        ari = adjusted_rand_score(labels, labels)
        assert ari == pytest.approx(1.0, abs=1e-15)

    def test_ari_random_baseline(self) -> None:
        """ARI should be near 0 for large random clusterings.

        Hand reasoning:
            By construction, ARI is adjusted so that random label
            assignments give an expected ARI of 0. With large n,
            a random assignment should yield ARI close to 0.
        """
        rng = np.random.default_rng(42)
        labels_true = rng.integers(0, 5, size=500)
        labels_pred = rng.integers(0, 5, size=500)
        ari = adjusted_rand_score(labels_true, labels_pred)
        # Should be near zero (within +/- 0.1 for n=500)
        assert abs(ari) < 0.1


# ====================================================================
# dead_vowel_tester.py formula
# ====================================================================


class TestDeadVowelPValue:
    """Formula: p_value = binom.sf(n_same - 1, n_total, expected_rate)

    P(X >= n_same | X ~ Bin(n_total, 1/V)). Tests whether consecutive
    signs share the same vowel class more often than the 1/V null rate.
    """

    def test_dead_vowel_binom_nsame60_ntotal100_rate025(self) -> None:
        """P(X >= 60 | Bin(100, 0.25)) should be astronomically small.

        Hand reasoning:
            Expected same-vowel pairs = 100 * 0.25 = 25
            Observed = 60 (more than double the expectation)
            sigma = sqrt(100 * 0.25 * 0.75) = sqrt(18.75) = 4.33
            z = (60 - 25) / 4.33 = 8.08 standard deviations
            So the p-value must be < 1e-10.

        Scipy gives: 1.326835e-13
        """
        n_same = 60
        n_total = 100
        expected_rate = 0.25  # 1/V where V=4

        p_value = stats.binom.sf(n_same - 1, n_total, expected_rate)

        assert p_value < 1e-10
        assert p_value == pytest.approx(1.326835e-13, rel=1e-3)

    def test_dead_vowel_effect_size(self) -> None:
        """Effect size = (observed_rate - expected_rate) / expected_rate.

        Hand computation:
            observed_rate = 60 / 100 = 0.6
            expected_rate = 0.25
            effect_size = (0.6 - 0.25) / 0.25 = 0.35 / 0.25 = 1.4

        This means 140% excess same-vowel pairs above the null rate.
        """
        n_same, n_total = 60, 100
        expected_rate = 0.25

        observed_rate = n_same / n_total
        effect_size = (observed_rate - expected_rate) / expected_rate

        assert observed_rate == pytest.approx(0.6, abs=1e-15)
        assert effect_size == pytest.approx(1.4, abs=1e-15)
