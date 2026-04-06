"""
Tests for Jaccard Paradigmatic Sign Classification
===================================================

3-tier test structure:
  Tier 1 (formula, ~15 tests): Jaccard properties, matrix symmetry,
         transform correctness, clustering determinism
  Tier 2 (known-answer, ~10 tests): LB consonant/vowel recovery,
         specific series tests, ARI thresholds
  Tier 3 (null/negative, ~5 tests): shuffled corpus, random data,
         degenerate inputs
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from pillar1.scripts.jaccard_sign_classification import (
    BOS,
    EOS,
    MIN_TOKEN_COUNT,
    compute_context_vectors,
    cosine_similarity_matrix,
    tfidf_transform,
    ppmi_transform,
    mutual_knn_sparsify,
    jaccard_similarity,
    weighted_jaccard,
    cluster_consonants,
    cluster_vowels,
    run_pipeline,
    validate_on_linear_b,
    run_null_test,
    count_recovered_series,
    compute_ari,
    extract_consonant,
    extract_vowel,
    build_lb_ground_truth,
    load_linear_b_corpus,
    load_linear_b_hf_words,
    deduplicate_sign_groups,
)

# ============================================================================
# PATHS
# ============================================================================

BASE = Path(__file__).resolve().parents[2]
HF_BASE = Path("C:/Users/alvin/hf-ancient-scripts/data/linear_b")
LB_CORPUS = BASE / "pillar1" / "tests" / "fixtures" / "linear_b_test_corpus.json"
LB_SIGN_IPA_FIXTURE = BASE / "pillar1" / "tests" / "fixtures" / "linear_b_sign_to_ipa.json"
LB_SIGN_IPA_HF = HF_BASE / "sign_to_ipa.json"
LB_WORDS_HF = HF_BASE / "linear_b_words.tsv"
LA_CORPUS = BASE / "data" / "sigla_full_corpus.json"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def sign_to_ipa():
    """Load sign-to-IPA mapping."""
    with open(LB_SIGN_IPA_HF, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def lb_sign_groups(sign_to_ipa):
    """Load and combine full LB corpus (test + HF)."""
    lb_test = load_linear_b_corpus(str(LB_CORPUS))
    lb_hf = load_linear_b_hf_words(str(LB_WORDS_HF), sign_to_ipa)
    return deduplicate_sign_groups([lb_test, lb_hf])


@pytest.fixture(scope="module")
def lb_validation(lb_sign_groups, sign_to_ipa):
    """Run full LB validation (cached for all tests)."""
    return validate_on_linear_b(lb_sign_groups, sign_to_ipa)


@pytest.fixture(scope="module")
def lb_pipeline(lb_validation):
    """Extract pipeline result from validation."""
    return lb_validation["pipeline"]


@pytest.fixture(scope="module")
def lb_context(lb_sign_groups):
    """Compute context vectors for LB corpus."""
    return compute_context_vectors(lb_sign_groups)


# ============================================================================
# TIER 1: FORMULA CORRECTNESS (~15 tests)
# ============================================================================

class TestTier1Formula:
    """Unit tests for mathematical properties and transforms."""

    # --- Jaccard properties ---

    def test_jaccard_empty_sets(self):
        """Jaccard of two empty sets should be 0."""
        assert jaccard_similarity(set(), set()) == 0.0

    def test_jaccard_identical_sets(self):
        """Jaccard of identical sets should be 1."""
        s = {"a", "b", "c"}
        assert jaccard_similarity(s, s) == 1.0

    def test_jaccard_disjoint_sets(self):
        """Jaccard of disjoint sets should be 0."""
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_jaccard_partial_overlap(self):
        """Jaccard of partially overlapping sets should be correct."""
        a = {"x", "y", "z"}
        b = {"y", "z", "w"}
        # intersection = {y, z} = 2, union = {x, y, z, w} = 4
        assert jaccard_similarity(a, b) == pytest.approx(0.5)

    def test_jaccard_symmetry(self):
        """Jaccard(A, B) == Jaccard(B, A)."""
        a = {"a", "b", "c"}
        b = {"b", "c", "d", "e"}
        assert jaccard_similarity(a, b) == jaccard_similarity(b, a)

    def test_jaccard_range(self):
        """Jaccard should be in [0, 1]."""
        for _ in range(50):
            a = set(random.sample("abcdefghij", random.randint(1, 8)))
            b = set(random.sample("abcdefghij", random.randint(1, 8)))
            j = jaccard_similarity(a, b)
            assert 0.0 <= j <= 1.0

    # --- Weighted Jaccard ---

    def test_weighted_jaccard_identical(self):
        """Weighted Jaccard of identical counters should be 1."""
        c = Counter({"a": 5, "b": 3})
        assert weighted_jaccard(c, c) == pytest.approx(1.0)

    def test_weighted_jaccard_disjoint(self):
        """Weighted Jaccard of disjoint counters should be 0."""
        a = Counter({"x": 3})
        b = Counter({"y": 5})
        assert weighted_jaccard(a, b) == pytest.approx(0.0)

    def test_weighted_jaccard_partial(self):
        """Weighted Jaccard with partial overlap."""
        a = Counter({"x": 4, "y": 2})
        b = Counter({"x": 2, "z": 3})
        # min: x=2, y=0, z=0 -> sum=2
        # max: x=4, y=2, z=3 -> sum=9
        assert weighted_jaccard(a, b) == pytest.approx(2 / 9)

    # --- Cosine similarity matrix ---

    def test_cosine_sim_diagonal_is_one(self):
        """Diagonal of cosine similarity matrix should be 1."""
        vecs = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]], dtype=float)
        sim = cosine_similarity_matrix(vecs)
        np.testing.assert_allclose(np.diag(sim), 1.0, atol=1e-10)

    def test_cosine_sim_symmetry(self):
        """Cosine similarity matrix should be symmetric."""
        rng = np.random.RandomState(42)
        vecs = rng.rand(10, 5)
        sim = cosine_similarity_matrix(vecs)
        np.testing.assert_allclose(sim, sim.T, atol=1e-10)

    def test_cosine_sim_range(self):
        """Cosine similarity values should be in [-1, 1]."""
        rng = np.random.RandomState(42)
        vecs = rng.rand(10, 5)
        sim = cosine_similarity_matrix(vecs)
        assert np.all(sim >= -1.0 - 1e-10)
        assert np.all(sim <= 1.0 + 1e-10)

    def test_cosine_sim_non_negative_for_non_negative_vecs(self):
        """Cosine similarity of non-negative vectors should be >= 0."""
        rng = np.random.RandomState(42)
        vecs = rng.rand(10, 5)  # all positive
        sim = cosine_similarity_matrix(vecs)
        assert np.all(sim >= -1e-10)

    # --- TF-IDF transform ---

    def test_tfidf_preserves_shape(self):
        """TF-IDF should preserve matrix shape."""
        vecs = np.array([[1, 0, 3], [0, 2, 1]], dtype=float)
        result = tfidf_transform(vecs)
        assert result.shape == vecs.shape

    def test_tfidf_zero_row_stays_zero(self):
        """A zero row should remain zero after TF-IDF."""
        vecs = np.array([[0, 0, 0], [1, 2, 3]], dtype=float)
        result = tfidf_transform(vecs)
        np.testing.assert_allclose(result[0], 0.0, atol=1e-10)

    # --- PPMI transform ---

    def test_ppmi_non_negative(self):
        """PPMI values should be non-negative."""
        rng = np.random.RandomState(42)
        vecs = rng.randint(0, 10, size=(5, 8)).astype(float)
        result = ppmi_transform(vecs)
        assert np.all(result >= -1e-10)

    def test_ppmi_zero_stays_zero(self):
        """Zero counts should remain zero after PPMI."""
        vecs = np.array([[0, 0, 5], [3, 0, 0]], dtype=float)
        result = ppmi_transform(vecs)
        assert result[0, 0] == 0.0
        assert result[0, 1] == 0.0
        assert result[1, 1] == 0.0

    # --- Mutual kNN ---

    def test_mknn_symmetry(self):
        """Mutual kNN result should be symmetric."""
        rng = np.random.RandomState(42)
        sim = cosine_similarity_matrix(rng.rand(10, 5))
        mknn = mutual_knn_sparsify(sim, k_nn=3)
        np.testing.assert_allclose(mknn, mknn.T, atol=1e-10)

    def test_mknn_diagonal_is_one(self):
        """Diagonal of mutual kNN should be 1."""
        rng = np.random.RandomState(42)
        sim = cosine_similarity_matrix(rng.rand(10, 5))
        mknn = mutual_knn_sparsify(sim, k_nn=3)
        np.testing.assert_allclose(np.diag(mknn), 1.0, atol=1e-10)

    def test_mknn_sparsifies(self):
        """Mutual kNN should produce a sparser matrix than the input."""
        rng = np.random.RandomState(42)
        sim = cosine_similarity_matrix(rng.rand(20, 5))
        mknn = mutual_knn_sparsify(sim, k_nn=3)
        n_nonzero_sim = np.count_nonzero(sim)
        n_nonzero_mknn = np.count_nonzero(mknn)
        assert n_nonzero_mknn < n_nonzero_sim

    # --- Clustering determinism ---

    def test_consonant_clustering_deterministic(self):
        """Same input should produce same clusters."""
        rng = np.random.RandomState(42)
        sim = cosine_similarity_matrix(rng.rand(15, 8))
        labels1, _ = cluster_consonants(sim, knn_k=3, n_clusters=5)
        labels2, _ = cluster_consonants(sim, knn_k=3, n_clusters=5)
        np.testing.assert_array_equal(labels1, labels2)

    def test_vowel_clustering_deterministic(self):
        """Same input should produce same clusters."""
        rng = np.random.RandomState(42)
        sim_r = cosine_similarity_matrix(rng.rand(15, 8))
        sim_l = cosine_similarity_matrix(rng.rand(15, 8))
        labels1, _ = cluster_vowels(sim_r, sim_l, beta=0.15, n_clusters=4)
        labels2, _ = cluster_vowels(sim_r, sim_l, beta=0.15, n_clusters=4)
        np.testing.assert_array_equal(labels1, labels2)


# ============================================================================
# TIER 2: KNOWN-ANSWER TESTS (~10 tests)
# ============================================================================

class TestTier2KnownAnswer:
    """Known-answer tests on Linear B full corpus."""

    # --- Data loading ---

    def test_lb_corpus_loads(self, lb_sign_groups):
        """LB corpus should load with sufficient data."""
        assert len(lb_sign_groups) >= 2000
        total_tokens = sum(len(g) for g in lb_sign_groups)
        assert total_tokens >= 8000

    def test_lb_context_vectors(self, lb_context):
        """Context vectors should have expected dimensions."""
        signs, left_vecs, right_vecs, counts = lb_context
        assert len(signs) >= 50
        assert left_vecs.shape[0] == len(signs)
        assert right_vecs.shape[0] == len(signs)
        # Frequency signs should have high counts
        assert counts.get("ta", 0) >= 100
        assert counts.get("ka", 0) >= 100

    # --- Gate 1: Consonant ARI ---

    def test_gate1_consonant_ari(self, lb_validation):
        """Consonant ARI should be >= 0.30 on full LB corpus."""
        assert lb_validation["consonant_ari"] >= 0.30, (
            f"Consonant ARI = {lb_validation['consonant_ari']:.4f} < 0.30"
        )

    def test_gate1_recovered_series(self, lb_validation):
        """At least 3 of 5 major consonant series should be recovered."""
        assert lb_validation["n_recovered_series"] >= 3, (
            f"Recovered {lb_validation['n_recovered_series']}/5 series: "
            f"{lb_validation['recovered_series']}"
        )

    def test_gate1_pass(self, lb_validation):
        """Gate 1 should pass (both ARI and recovery criteria)."""
        assert lb_validation["gate1_pass"], (
            f"Gate 1 FAILED: ARI={lb_validation['consonant_ari']:.4f}, "
            f"recovered={lb_validation['n_recovered_series']}"
        )

    # --- Gate 2: Vowel ARI ---

    def test_gate2_vowel_ari(self, lb_validation):
        """Vowel ARI should be >= 0.40 on full LB corpus."""
        assert lb_validation["vowel_ari"] >= 0.40, (
            f"Vowel ARI = {lb_validation['vowel_ari']:.4f} < 0.40"
        )

    def test_gate2_pass(self, lb_validation):
        """Gate 2 should pass."""
        assert lb_validation["gate2_pass"], (
            f"Gate 2 FAILED: vowel ARI={lb_validation['vowel_ari']:.4f}"
        )

    # --- Specific series tests ---

    def test_t_series_recovered(self, lb_validation, sign_to_ipa):
        """T-series (ta, te, ti, to, tu) should be recovered."""
        pipeline = lb_validation["pipeline"]
        signs = pipeline["signs"]
        labels = pipeline["consonant"]["labels"]
        n, recovered = count_recovered_series(
            signs, labels, sign_to_ipa, target_series=["t"]
        )
        assert n >= 1, "T-series not recovered"

    def test_k_series_recovered(self, lb_validation, sign_to_ipa):
        """K-series (ka, ke, ki, ko, ku) should be recovered."""
        pipeline = lb_validation["pipeline"]
        signs = pipeline["signs"]
        labels = pipeline["consonant"]["labels"]
        n, recovered = count_recovered_series(
            signs, labels, sign_to_ipa, target_series=["k"]
        )
        assert n >= 1, "K-series not recovered"

    def test_n_series_recovered(self, lb_validation, sign_to_ipa):
        """N-series (na, ne, ni, no, nu) should be recovered."""
        pipeline = lb_validation["pipeline"]
        signs = pipeline["signs"]
        labels = pipeline["consonant"]["labels"]
        n, recovered = count_recovered_series(
            signs, labels, sign_to_ipa, target_series=["n"]
        )
        assert n >= 1, "N-series not recovered"

    def test_j_series_pure_cluster(self, lb_pipeline, sign_to_ipa):
        """J-series (ja, je, jo) should form a pure or near-pure cluster."""
        signs = lb_pipeline["signs"]
        labels = lb_pipeline["consonant"]["labels"]
        j_signs = [s for s in signs if extract_consonant(s) == "j"]
        if len(j_signs) < 2:
            pytest.skip("Too few j-series signs")

        j_labels = [int(labels[signs.index(s)]) for s in j_signs]
        # All j-signs should be in the same cluster
        assert len(set(j_labels)) == 1, (
            f"J-series split across clusters: {list(zip(j_signs, j_labels))}"
        )

    def test_q_series_cluster(self, lb_pipeline, sign_to_ipa):
        """Q-series: majority (>= 50%) of frequent q-signs should co-cluster."""
        signs = lb_pipeline["signs"]
        labels = lb_pipeline["consonant"]["labels"]
        q_signs = [s for s in signs if extract_consonant(s) == "q"]
        if len(q_signs) < 2:
            pytest.skip("Too few q-series signs")

        q_labels = [int(labels[signs.index(s)]) for s in q_signs]
        most_common_label = Counter(q_labels).most_common(1)[0]
        majority_frac = most_common_label[1] / len(q_signs)
        assert majority_frac >= 0.5, (
            f"Q-series split: {list(zip(q_signs, q_labels))}, "
            f"majority only {majority_frac:.0%}"
        )

    def test_vowel_clusters_count(self, lb_pipeline):
        """Vowel clustering should produce 3-8 clusters."""
        k = lb_pipeline["vowel"]["k"]
        assert 3 <= k <= 8, f"Vowel k={k} outside expected range [3, 8]"

    def test_consonant_clusters_count(self, lb_pipeline):
        """Consonant clustering should produce >= 8 clusters."""
        k = lb_pipeline["consonant"]["k"]
        assert k >= 8, f"Consonant k={k} < 8"

    # --- Cross-validation ---

    def test_cross_validation_nmi_below_1(self, lb_pipeline):
        """Normalized MI between consonant and vowel should be < 1.0."""
        cv = lb_pipeline.get("cross_validation") if "cross_validation" in lb_pipeline else None
        if cv is None:
            # Recompute
            from pillar1.scripts.jaccard_sign_classification import _cross_validate
            cv = _cross_validate(
                lb_pipeline["signs"],
                lb_pipeline["consonant"]["labels"],
                lb_pipeline["vowel"]["labels"],
            )
        assert cv["normalized_mi"] < 1.0

    # --- Extract helpers ---

    def test_extract_consonant_cv(self):
        """Extract consonant from standard CV signs."""
        assert extract_consonant("ta") == "t"
        assert extract_consonant("ka") == "k"
        assert extract_consonant("ra") == "r"
        assert extract_consonant("na") == "n"
        assert extract_consonant("sa") == "s"

    def test_extract_consonant_vowel(self):
        """Extract consonant from pure vowels returns 'V'."""
        assert extract_consonant("a") == "V"
        assert extract_consonant("e") == "V"
        assert extract_consonant("i") == "V"
        assert extract_consonant("o") == "V"
        assert extract_consonant("u") == "V"

    def test_extract_consonant_special(self):
        """Extract consonant from special signs."""
        assert extract_consonant("dwe") == "dw"
        assert extract_consonant("nwa") == "nw"
        assert extract_consonant("ra2") == "r"
        assert extract_consonant("pu2") == "p"

    def test_extract_vowel_cv(self):
        """Extract vowel from CV signs."""
        assert extract_vowel("ta") == "a"
        assert extract_vowel("ke") == "e"
        assert extract_vowel("ri") == "i"
        assert extract_vowel("to") == "o"
        assert extract_vowel("su") == "u"

    def test_extract_vowel_pure(self):
        """Extract vowel from pure vowel signs."""
        assert extract_vowel("a") == "a"
        assert extract_vowel("e") == "e"

    def test_extract_vowel_special(self):
        """Extract vowel from special signs."""
        assert extract_vowel("dwe") == "e"
        assert extract_vowel("ra2") == "a"


# ============================================================================
# TIER 3: NULL AND NEGATIVE TESTS (~5 tests)
# ============================================================================

class TestTier3NullNegative:
    """Null tests and edge cases."""

    def test_null_shuffled_consonant_ari(self, lb_sign_groups, sign_to_ipa):
        """Shuffled corpus should produce consonant ARI < 0.05."""
        null = run_null_test(lb_sign_groups, sign_to_ipa, seed=42)
        assert abs(null["shuffled_consonant_ari"]) < 0.05, (
            f"Shuffled consonant ARI = {null['shuffled_consonant_ari']:.4f} >= 0.05"
        )

    def test_null_shuffled_vowel_ari(self, lb_sign_groups, sign_to_ipa):
        """Shuffled corpus should produce vowel ARI < 0.05."""
        null = run_null_test(lb_sign_groups, sign_to_ipa, seed=42)
        assert abs(null["shuffled_vowel_ari"]) < 0.05, (
            f"Shuffled vowel ARI = {null['shuffled_vowel_ari']:.4f} >= 0.05"
        )

    def test_null_gate_pass(self, lb_sign_groups, sign_to_ipa):
        """Null test gate should pass."""
        null = run_null_test(lb_sign_groups, sign_to_ipa, seed=42)
        assert null["gate_pass"]

    def test_random_data_low_ari(self, sign_to_ipa):
        """Completely random sign-groups should produce near-zero ARI."""
        rng = random.Random(42)
        vocab = list(sign_to_ipa.keys())
        random_groups = []
        for _ in range(500):
            length = rng.randint(2, 5)
            group = [rng.choice(vocab) for _ in range(length)]
            random_groups.append(group)

        val = validate_on_linear_b(random_groups, sign_to_ipa, min_count=3)
        assert abs(val["consonant_ari"]) < 0.10, (
            f"Random consonant ARI = {val['consonant_ari']:.4f}"
        )

    def test_degenerate_single_sign_groups(self):
        """Single-sign groups should not crash."""
        groups = [["a"], ["e"], ["i"], ["o"], ["u"]] * 20
        result = run_pipeline(groups, min_count=5)
        # Should either produce results or report insufficient data
        assert "signs" in result or "error" in result

    def test_degenerate_empty_corpus(self):
        """Empty corpus should not crash."""
        result = run_pipeline([], min_count=5)
        assert "error" in result or len(result.get("signs", [])) == 0

    def test_degenerate_two_signs(self):
        """Corpus with only 2 unique signs should handle gracefully."""
        groups = [["a", "b"]] * 100
        result = run_pipeline(groups, min_count=5)
        # Should not crash, may report insufficient signs
        assert result is not None

    def test_null_multiple_seeds(self, lb_sign_groups, sign_to_ipa):
        """Null test should pass with different random seeds."""
        for seed in [0, 7, 99, 12345]:
            null = run_null_test(lb_sign_groups, sign_to_ipa, seed=seed)
            assert abs(null["shuffled_consonant_ari"]) < 0.10, (
                f"Seed {seed}: shuffled cons ARI = "
                f"{null['shuffled_consonant_ari']:.4f}"
            )
            assert abs(null["shuffled_vowel_ari"]) < 0.10, (
                f"Seed {seed}: shuffled vowel ARI = "
                f"{null['shuffled_vowel_ari']:.4f}"
            )
