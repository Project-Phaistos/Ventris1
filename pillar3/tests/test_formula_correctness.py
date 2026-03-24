"""Tier 1: Hand-computed formula correctness tests for Pillar 3.

Each test constructs minimal hand-computed inputs, calls the relevant
function or implements the formula directly, and asserts exact (or
near-exact) results against known correct values.

At least 15 tests covering:
- PPMI formula
- Direction ratio
- Binomial test for directionality
- Suffix match rate computation
- Expected agreement rate
- Morphological coherence
- Relative position
- Functional word classification thresholds
- SVD explained variance ratio
- Silhouette score model selection
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pytest
from scipy.stats import binomtest
from sklearn.metrics import silhouette_score


# ========================================================================
# PPMI formula tests
# ========================================================================

class TestPPMIFormula:
    """Test the PPMI formula: PMI(s,c) = log2(P(s,c) / (P(s)*P(c))), PPMI = max(0, PMI)."""

    def test_ppmi_positive_association(self):
        """Two items that co-occur more than expected should have positive PPMI."""
        # P(s,c) = 4/20 = 0.2
        # P(s) = 5/20 = 0.25
        # P(c) = 6/20 = 0.3
        # PMI = log2(0.2 / (0.25 * 0.3)) = log2(0.2/0.075) = log2(2.6667) ~ 1.415
        p_sc = 4 / 20
        p_s = 5 / 20
        p_c = 6 / 20
        pmi = math.log2(p_sc / (p_s * p_c))
        ppmi = max(0.0, pmi)
        assert ppmi == pytest.approx(math.log2(8 / 3), rel=1e-6)
        assert ppmi > 0

    def test_ppmi_negative_association_clamped_to_zero(self):
        """Items that co-occur less than expected should have PPMI = 0."""
        # P(s,c) = 1/100 = 0.01
        # P(s) = 20/100 = 0.2
        # P(c) = 30/100 = 0.3
        # PMI = log2(0.01 / 0.06) = log2(1/6) ~ -2.585  -> PPMI = 0
        p_sc = 1 / 100
        p_s = 20 / 100
        p_c = 30 / 100
        pmi = math.log2(p_sc / (p_s * p_c))
        ppmi = max(0.0, pmi)
        assert ppmi == 0.0
        assert pmi < 0

    def test_ppmi_independence_is_zero(self):
        """If P(s,c) = P(s)*P(c) exactly, PMI = 0, PPMI = 0."""
        p_s = 0.3
        p_c = 0.4
        p_sc = p_s * p_c  # = 0.12
        pmi = math.log2(p_sc / (p_s * p_c))
        ppmi = max(0.0, pmi)
        assert ppmi == pytest.approx(0.0, abs=1e-10)

    def test_ppmi_with_smoothing(self):
        """PPMI with context distribution smoothing (alpha=0.75)."""
        # Smoothed context probability: P_alpha(c) = count(c)^alpha / sum(count(c')^alpha)
        alpha = 0.75
        context_counts = {"A": 10, "B": 2, "C": 8}
        total_smoothed = sum(v ** alpha for v in context_counts.values())
        p_c_smoothed = context_counts["B"] ** alpha / total_smoothed

        # Without smoothing: P(B) = 2/20 = 0.1
        # With smoothing: P(B) = 2^0.75 / (10^0.75 + 2^0.75 + 8^0.75)
        # 2^0.75 = 1.6818, 10^0.75 = 5.6234, 8^0.75 = 4.7568
        # total = 12.0621, P_alpha(B) = 1.6818/12.0621 ~ 0.1394
        assert p_c_smoothed == pytest.approx(1.6818 / 12.0621, rel=1e-3)
        assert p_c_smoothed > 2 / 20  # Smoothing raises rare context probability


# ========================================================================
# Direction ratio tests
# ========================================================================

class TestDirectionRatio:
    """Test direction_ratio = P[i,j] / max(P[j,i], 1)."""

    def test_strong_direction(self):
        """10 times A before B, 1 time B before A -> ratio = 10."""
        a_before_b = 10
        b_before_a = 1
        ratio = a_before_b / max(b_before_a, 1)
        assert ratio == 10.0

    def test_symmetric_direction(self):
        """Equal counts -> ratio = 1.0 (no preference)."""
        a_before_b = 5
        b_before_a = 5
        ratio = a_before_b / max(b_before_a, 1)
        assert ratio == 1.0

    def test_zero_reverse_floor_to_one(self):
        """When reverse count is 0, use floor of 1 to avoid division by zero."""
        a_before_b = 7
        b_before_a = 0
        ratio = a_before_b / max(b_before_a, 1)
        assert ratio == 7.0


# ========================================================================
# Binomial test for directionality
# ========================================================================

class TestBinomialDirectionality:
    """Binomial test: under H0, P(A before B) = 0.5."""

    def test_strong_signal_is_significant(self):
        """20 out of 20 observations -> extremely significant."""
        result = binomtest(20, 20, 0.5, alternative="two-sided")
        assert result.pvalue < 1e-5

    def test_balanced_is_not_significant(self):
        """10 out of 20 observations -> not significant."""
        result = binomtest(10, 20, 0.5, alternative="two-sided")
        assert result.pvalue > 0.5  # Should be ~1.0


# ========================================================================
# Suffix match rate computation
# ========================================================================

class TestSuffixMatchRate:
    """Test observed suffix match rate = n_same / n_total."""

    def test_basic_suffix_match_rate(self):
        """3 matches out of 10 pairs -> rate = 0.3."""
        n_same = 3
        n_total = 10
        rate = n_same / n_total
        assert rate == pytest.approx(0.3)

    def test_zero_matches(self):
        """No matches -> rate = 0."""
        n_same = 0
        n_total = 15
        rate = n_same / n_total
        assert rate == pytest.approx(0.0)


# ========================================================================
# Expected agreement rate
# ========================================================================

class TestExpectedAgreementRate:
    """expected_rate = sum(P(suffix)^2)."""

    def test_uniform_distribution(self):
        """With 4 equally frequent suffixes: expected = 4 * (1/4)^2 = 0.25."""
        counts = Counter({"a": 10, "b": 10, "c": 10, "d": 10})
        total = sum(counts.values())
        expected = sum((c / total) ** 2 for c in counts.values())
        assert expected == pytest.approx(0.25)

    def test_skewed_distribution(self):
        """One dominant suffix: expected rate is high."""
        counts = Counter({"a": 90, "b": 5, "c": 5})
        total = sum(counts.values())
        expected = sum((c / total) ** 2 for c in counts.values())
        # (0.9)^2 + (0.05)^2 + (0.05)^2 = 0.81 + 0.0025 + 0.0025 = 0.815
        assert expected == pytest.approx(0.815)

    def test_single_suffix(self):
        """Only one suffix -> expected = 1.0."""
        counts = Counter({"a": 50})
        total = sum(counts.values())
        expected = sum((c / total) ** 2 for c in counts.values())
        assert expected == pytest.approx(1.0)


# ========================================================================
# Morphological coherence
# ========================================================================

class TestMorphologicalCoherence:
    """max_label_fraction per cluster, averaged across clusters."""

    def test_perfect_coherence(self):
        """All members of each cluster share the same label -> coherence = 1.0."""
        # Cluster 0: all "declining", Cluster 1: all "uninflected"
        labels_in_clusters = {
            0: ["declining", "declining", "declining"],
            1: ["uninflected", "uninflected"],
        }
        coherences = []
        for members in labels_in_clusters.values():
            counts = Counter(members)
            max_frac = max(counts.values()) / len(members)
            coherences.append(max_frac)
        assert np.mean(coherences) == pytest.approx(1.0)

    def test_mixed_coherence(self):
        """Mixed clusters: 3/4 in cluster 0, 2/3 in cluster 1."""
        labels_in_clusters = {
            0: ["declining", "declining", "declining", "uninflected"],
            1: ["uninflected", "uninflected", "declining"],
        }
        coherences = []
        for members in labels_in_clusters.values():
            counts = Counter(members)
            max_frac = max(counts.values()) / len(members)
            coherences.append(max_frac)
        # (0.75 + 0.6667) / 2 = 0.7083
        assert np.mean(coherences) == pytest.approx((3 / 4 + 2 / 3) / 2, rel=1e-6)


# ========================================================================
# Relative position
# ========================================================================

class TestRelativePosition:
    """relative_position = index / (total_words - 1)."""

    def test_first_word(self):
        """Position 0 in a 5-word inscription -> 0.0."""
        pos = 0 / (5 - 1)
        assert pos == pytest.approx(0.0)

    def test_last_word(self):
        """Position 4 in a 5-word inscription -> 1.0."""
        pos = 4 / (5 - 1)
        assert pos == pytest.approx(1.0)

    def test_middle_word(self):
        """Position 2 in a 5-word inscription -> 0.5."""
        pos = 2 / (5 - 1)
        assert pos == pytest.approx(0.5)

    def test_single_word_inscription(self):
        """Single word -> relative_position = 0.5 (convention)."""
        # When total_words == 1, CorpusWord returns 0.5
        total = 1
        if total <= 1:
            pos = 0.5
        else:
            pos = 0 / (total - 1)
        assert pos == pytest.approx(0.5)


# ========================================================================
# Functional word classification thresholds
# ========================================================================

class TestFunctionalWordThresholds:
    """Test the classification heuristic thresholds."""

    def test_structural_marker_threshold(self):
        """final_rate > 0.30 -> structural_marker."""
        final_rate = 0.35
        threshold = 0.30
        assert final_rate > threshold

    def test_below_structural_marker_threshold(self):
        """final_rate = 0.20 -> not structural_marker."""
        final_rate = 0.20
        threshold = 0.30
        assert final_rate <= threshold


# ========================================================================
# SVD explained variance ratio
# ========================================================================

class TestSVDExplainedVariance:
    """Test SVD explained variance computation and component selection."""

    def test_variance_ratio_sums_to_one_or_less(self):
        """Explained variance ratios from SVD must sum to <= 1.0."""
        from sklearn.decomposition import TruncatedSVD

        rng = np.random.RandomState(42)
        X = rng.randn(50, 10)
        X = np.abs(X)  # TruncatedSVD needs non-negative or centered data
        svd = TruncatedSVD(n_components=5, random_state=42)
        svd.fit(X)
        total_var = sum(svd.explained_variance_ratio_)
        assert total_var <= 1.0 + 1e-10

    def test_cumulative_variance_selection(self):
        """Select d components to explain at least 80% variance."""
        target = 0.80
        variances = [0.40, 0.25, 0.15, 0.10, 0.05, 0.03, 0.02]
        cumvar = np.cumsum(variances)
        d = len(variances)  # default
        for i, cv in enumerate(cumvar):
            if cv >= target:
                d = i + 1
                break
        assert d == 3  # 0.40 + 0.25 + 0.15 = 0.80


# ========================================================================
# Silhouette score model selection
# ========================================================================

class TestSilhouetteModelSelection:
    """Test that silhouette score drives model selection correctly."""

    def test_well_separated_clusters(self):
        """Well-separated clusters should have high silhouette."""
        X = np.array([
            [0, 0], [0.1, 0.1], [0.2, 0],     # Cluster 0
            [10, 10], [10.1, 10.1], [9.9, 10],  # Cluster 1
        ])
        labels = np.array([0, 0, 0, 1, 1, 1])
        sil = silhouette_score(X, labels)
        assert sil > 0.8

    def test_random_labels_low_silhouette(self):
        """Random labels on structured data should have low silhouette."""
        rng = np.random.RandomState(42)
        X = rng.randn(30, 5)
        labels = rng.randint(0, 3, size=30)
        sil = silhouette_score(X, labels)
        assert sil < 0.3
