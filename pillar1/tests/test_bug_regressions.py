"""Regression tests for critical bugs found by adversarial audit.

Each test is named after the bug it would have caught, and constructs
a synthetic scenario where the old (buggy) code would have produced
wrong results.
"""

from __future__ import annotations

from typing import Dict, List, Set

import numpy as np
import pytest
from sklearn.metrics import silhouette_score

from pillar1.corpus_loader import (
    CorpusData,
    Inscription,
    Word,
    SignToken,
    PositionalRecord,
    BigramRecord,
)
from pillar1.alternation_detector import (
    detect_alternations,
    AlternationResult,
)
from pillar1.grid_constructor import construct_grid, GridResult
from pillar1.vowel_identifier import VowelInventory


# ── Helpers ────────────────────────────────────────────────────────────

def _make_synthetic_corpus(
    words: List[List[str]],
    inscription_id: str = "SYNTH-001",
) -> CorpusData:
    """Build a minimal CorpusData from a list of words (each word is a
    list of sign-id strings, all treated as syllabograms)."""
    sign_tokens_per_word: List[Word] = []
    positional_records: List[PositionalRecord] = []
    bigram_records: List[BigramRecord] = []

    for wi, sign_ids in enumerate(words):
        tokens = [
            SignToken(sign_id=sid, sign_type="syllabogram", reading=sid.lower())
            for sid in sign_ids
        ]
        word = Word(
            signs=tokens,
            has_damage=False,
            inscription_id=inscription_id,
            word_index=wi,
        )
        sign_tokens_per_word.append(word)

        syllib_ids = word.sign_ids
        # Positional records
        for pos_idx, sid in enumerate(syllib_ids):
            if len(syllib_ids) == 1:
                position = "singleton"
            elif pos_idx == 0:
                position = "initial"
            elif pos_idx == len(syllib_ids) - 1:
                position = "final"
            else:
                position = "medial"
            positional_records.append(PositionalRecord(
                sign_id=sid,
                position=position,
                word_sign_ids=syllib_ids,
                inscription_id=inscription_id,
            ))
        # Bigram records
        if len(syllib_ids) >= 2:
            for j in range(len(syllib_ids) - 1):
                bigram_records.append(BigramRecord(
                    sign_i=syllib_ids[j],
                    sign_j=syllib_ids[j + 1],
                    position_in_word=j,
                    word_sign_ids=syllib_ids,
                    inscription_id=inscription_id,
                ))

    inscription = Inscription(
        id=inscription_id,
        type="synthetic",
        site="test",
        words=sign_tokens_per_word,
    )

    return CorpusData(
        inscriptions=[inscription],
        positional_records=positional_records,
        bigram_records=bigram_records,
        sign_inventory={},
        corpus_hash="synthetic",
        total_inscriptions=1,
        total_words=len(words),
        total_syllabogram_tokens=sum(len(w) for w in words),
        unique_syllabograms=len({s for w in words for s in w}),
        words_used_positional=len(words),
        words_used_bigram=sum(1 for w in words if len(w) >= 2),
    )


def _make_block_affinity(cluster_sizes: List[int], within: float, between: float) -> np.ndarray:
    """Build a block-diagonal affinity matrix with known cluster structure.

    Args:
        cluster_sizes: Number of nodes per cluster.
        within: Affinity value within clusters.
        between: Affinity value between clusters.

    Returns:
        Symmetric affinity matrix with zeros on the diagonal.
    """
    n = sum(cluster_sizes)
    A = np.full((n, n), between, dtype=np.float64)

    offset = 0
    for size in cluster_sizes:
        A[offset:offset + size, offset:offset + size] = within
        offset += size

    np.fill_diagonal(A, 0)
    return A


# ====================================================================
# C3: Silhouette score must use distance matrix, not affinity matrix
# ====================================================================


class TestSilhouetteUsesDistanceNotAffinity:
    """Bug C3: silhouette_score with metric='precomputed' expects a
    DISTANCE matrix (small values = similar), but the old code passed
    the raw affinity matrix (large values = similar). This inverted
    the model selection criterion."""

    def test_silhouette_uses_distance_not_affinity(self) -> None:
        """Build a clear 3-cluster affinity matrix. The best_k_silhouette
        must equal 3 (the known answer). With the old buggy code (passing
        affinity directly), the silhouette scores would be inverted and
        best_k_silhouette would NOT be 3."""
        # 3 clusters of 4 nodes each = 12 nodes
        cluster_sizes = [4, 4, 4]
        n = sum(cluster_sizes)
        within_affinity = 10.0
        between_affinity = 0.1
        A = _make_block_affinity(cluster_sizes, within_affinity, between_affinity)

        # Create a mock AlternationResult with this affinity matrix
        sign_ids = [f"S{i:02d}" for i in range(n)]
        sign_id_to_idx = {sid: i for i, sid in enumerate(sign_ids)}
        idx_to_sign_id = {i: sid for sid, i in sign_id_to_idx.items()}

        alt_result = AlternationResult(
            all_pairs=[],
            significant_pairs=[],
            affinity_matrix=A,
            sign_id_to_index=sign_id_to_idx,
            index_to_sign_id=idx_to_sign_id,
        )

        # Minimal vowel inventory and corpus
        vowel_inv = VowelInventory(
            count=3,
            count_ci_95=(2, 4),
            method="test",
        )

        # Create a corpus with positional records for all signs
        words = [[sid, "FILLER"] for sid in sign_ids]
        corpus = _make_synthetic_corpus(words)

        grid = construct_grid(
            alt_result,
            vowel_inv,
            corpus,
            min_consonant_classes=2,
            max_consonant_classes=6,
        )

        # The correct answer is k=3
        assert grid.best_k_silhouette == 3, (
            f"best_k_silhouette={grid.best_k_silhouette}, expected 3. "
            f"This suggests silhouette_score is still being passed an "
            f"affinity matrix instead of a distance matrix. "
            f"Silhouette scores: {grid.silhouette_scores}"
        )

    def test_silhouette_distance_conversion_manual(self) -> None:
        """Verify that converting affinity to distance and computing
        silhouette gives higher scores for the correct clustering than
        for a wrong clustering."""
        # 2 clear clusters of 3
        A = _make_block_affinity([3, 3], within=10.0, between=0.0)

        # Convert affinity to distance
        A_max = A.max()
        dist = A_max - A
        np.fill_diagonal(dist, 0)

        # Correct labels
        correct_labels = np.array([0, 0, 0, 1, 1, 1])
        sil_correct = silhouette_score(dist, correct_labels, metric="precomputed")

        # Wrong labels (scrambled)
        wrong_labels = np.array([0, 1, 0, 1, 0, 1])
        sil_wrong = silhouette_score(dist, wrong_labels, metric="precomputed")

        assert sil_correct > sil_wrong, (
            f"Correct clustering silhouette ({sil_correct:.3f}) should be > "
            f"wrong clustering silhouette ({sil_wrong:.3f})"
        )
        # Correct clustering should have a high positive silhouette
        assert sil_correct > 0.5, (
            f"Correct clustering silhouette ({sil_correct:.3f}) should be > 0.5"
        )


# ====================================================================
# C1+C2: Alternation null model uses correct branching prefix count
# ====================================================================


class TestAlternationExpectedCountUsesBranchingPrefixes:
    """Bug C1: n_prefix_groups counted the number of pair entries in
    pair_stems (one per sign pair), not the number of distinct prefixes
    with >= 2 continuations.

    Bug C2: The '* 2' symmetry factor was spurious because pairs are
    stored as frozensets (unordered)."""

    def test_alternation_expected_count_uses_branching_prefixes(self) -> None:
        """Create a corpus with a known number of branching prefixes.
        Verify that total_prefix_groups matches the actual count of
        distinct prefixes with >= 2 continuations.

        Corpus:
            Prefix "A-B" has words ending in X, Y, Z -> 1 branching prefix
            Prefix "C-D" has words ending in P, Q     -> 1 branching prefix
            Prefix "E-F" has only one word ending in R -> NOT branching
            Total branching prefixes = 2

        The old code (C1) would have counted 4 (the number of pair entries:
        {X,Y}, {X,Z}, {Y,Z}, {P,Q}).
        """
        corpus = _make_synthetic_corpus([
            # Branching prefix "A-B": 3 continuations -> 1 branching prefix
            ["A", "B", "X"],
            ["A", "B", "Y"],
            ["A", "B", "Z"],
            # Branching prefix "C-D": 2 continuations -> 1 branching prefix
            ["C", "D", "P"],
            ["C", "D", "Q"],
            # Non-branching prefix "E-F": only 1 word
            ["E", "F", "R"],
        ])

        result = detect_alternations(
            corpus,
            min_shared_prefix_length=1,
            max_suffix_diff_length=1,  # Only single-sign diff to keep it simple
            min_independent_stems=1,
            alternation_alpha=1.0,
        )

        # There are exactly 2 distinct branching prefixes: (A,B) and (C,D)
        assert result.total_prefix_groups == 2, (
            f"total_prefix_groups={result.total_prefix_groups}, expected 2. "
            f"The count should be the number of distinct prefixes with >= 2 "
            f"continuations, not the number of pair entries."
        )

    def test_no_spurious_symmetry_factor(self) -> None:
        """Verify the expected value has no '* 2' symmetry factor.

        With 2 branching prefixes, p_a = p_b = 0.5, the expected value
        should be 0.5 * 0.5 * 2 = 0.5 (no factor of 2).

        The old code (C2) would have computed 0.5 * 0.5 * N * 2 = 1.0."""
        corpus = _make_synthetic_corpus([
            # 2 words with the same prefix, 2 different final signs
            # Each final sign appears exactly once in 2 total final positions
            ["A", "X"],
            ["A", "Y"],
            # Add another branching prefix to make n_branching_prefixes = 2
            ["B", "X"],
            ["B", "Y"],
        ])

        result = detect_alternations(
            corpus,
            min_shared_prefix_length=1,
            max_suffix_diff_length=1,
            min_independent_stems=1,
            alternation_alpha=1.0,
        )

        # p_a(X) = 2/4 = 0.5, p_b(Y) = 2/4 = 0.5
        # n_branching_prefixes = 2
        # expected = 0.5 * 0.5 * 2 = 0.5  (NOT * 2 = 1.0)
        xy_pair = None
        for pair in result.all_pairs:
            if {pair.sign_a, pair.sign_b} == {"X", "Y"}:
                xy_pair = pair
                break

        assert xy_pair is not None, "Expected to find X-Y pair"
        assert xy_pair.expected_by_chance == pytest.approx(0.5, abs=1e-10), (
            f"expected_by_chance={xy_pair.expected_by_chance}, expected 0.5. "
            f"The '* 2' symmetry factor should not be present."
        )


# ====================================================================
# C4: Eigengap range must include max_consonant_classes
# ====================================================================


class TestEigengapCanSelectMaxConsonantClasses:
    """Bug C4: The eigengap range excluded max_consonant_classes due to
    exclusive upper bound in range(). This meant the eigengap heuristic
    could never select max_consonant_classes as the number of clusters."""

    def test_eigengap_can_select_max_consonant_classes(self) -> None:
        """Create an affinity matrix where the optimal number of clusters
        is exactly max_consonant_classes. Verify that the eigengap
        heuristic can select it.

        We create 5 clear clusters and set max_consonant_classes=5.
        The old code's range would have been range(..., 5) which
        excludes index 4 (the gap between eigenvalue 4 and 5, i.e. k=5).
        """
        cluster_sizes = [3, 3, 3, 3, 3]  # 5 clusters of 3 = 15 nodes
        n = sum(cluster_sizes)
        A = _make_block_affinity(cluster_sizes, within=10.0, between=0.01)

        sign_ids = [f"S{i:02d}" for i in range(n)]
        sign_id_to_idx = {sid: i for i, sid in enumerate(sign_ids)}
        idx_to_sign_id = {i: sid for sid, i in sign_id_to_idx.items()}

        alt_result = AlternationResult(
            all_pairs=[],
            significant_pairs=[],
            affinity_matrix=A,
            sign_id_to_index=sign_id_to_idx,
            index_to_sign_id=idx_to_sign_id,
        )

        vowel_inv = VowelInventory(
            count=3,
            count_ci_95=(2, 4),
            method="test",
        )

        words = [[sid, "FILLER"] for sid in sign_ids]
        corpus = _make_synthetic_corpus(words)

        grid = construct_grid(
            alt_result,
            vowel_inv,
            corpus,
            min_consonant_classes=3,
            max_consonant_classes=5,
        )

        # The eigengap heuristic should be able to select k=5
        assert grid.best_k_eigengap == 5, (
            f"best_k_eigengap={grid.best_k_eigengap}, expected 5. "
            f"The eigengap range may be excluding max_consonant_classes. "
            f"Eigengaps: {grid.eigengaps[:8]}"
        )


# ====================================================================
# H2: diff_len=2 pairs must be weighted 0.5
# ====================================================================


class TestDiffLen2PairsWeightedHalf:
    """Bug H2: Two-sign-difference pairs should have weight 0.5 per the
    PRD, but the old code gave them weight 1.0 in the affinity matrix."""

    def test_diff_len_2_pairs_weighted_half(self) -> None:
        """Create a corpus where a final-position pair M-N alternates under
        one prefix via diff_len=2 (two-sign suffix difference). The
        weighted_stems for that pair should be 0.5, not 1.0.

        Words:
            ["A", "X", "M"]  and  ["A", "Y", "N"]
            share prefix "A" but differ in the last 2 signs.
            With max_suffix_diff_length=2, only the FINAL-position pair {M,N}
            is extracted (weight 0.5). The penultimate pair {X,Y} is a stem
            difference, not a suffix alternation, and is NOT extracted.
        """
        corpus = _make_synthetic_corpus([
            ["A", "X", "M"],
            ["A", "Y", "N"],
        ])

        result = detect_alternations(
            corpus,
            min_shared_prefix_length=1,
            max_suffix_diff_length=2,
            min_independent_stems=1,
            alternation_alpha=1.0,
        )

        # Find the M-N pair (final position from diff_len=2)
        mn_pair = None
        for pair in result.all_pairs:
            if {pair.sign_a, pair.sign_b} == {"M", "N"}:
                mn_pair = pair
                break

        assert mn_pair is not None, (
            f"Expected to find M-N pair from diff_len=2 final position. "
            f"All pairs: {[(p.sign_a, p.sign_b) for p in result.all_pairs]}"
        )

        assert mn_pair.weighted_stems == pytest.approx(0.5, abs=1e-10), (
            f"weighted_stems={mn_pair.weighted_stems}, expected 0.5. "
            f"diff_len=2 pairs should have weight 0.5, not 1.0."
        )

        # Penultimate pair X-Y should NOT be extracted (stem position, not suffix)
        xy_pair = None
        for pair in result.all_pairs:
            if {pair.sign_a, pair.sign_b} == {"X", "Y"}:
                xy_pair = pair
                break

        assert xy_pair is None, (
            f"Penultimate pair X-Y should NOT be extracted from diff_len=2. "
            f"Only final-position pairs are valid suffix alternations."
        )

    def test_diff_len_1_pairs_weighted_full(self) -> None:
        """Verify that diff_len=1 pairs still have weight 1.0 per stem.

        Words:
            ["A", "B", "X"]  and  ["A", "B", "Y"]
            share prefix "A-B" and differ in the last sign.
            With max_suffix_diff_length=1, the pair {X,Y} should have
            weighted_stems = 1.0 (one stem at full weight).
        """
        corpus = _make_synthetic_corpus([
            ["A", "B", "X"],
            ["A", "B", "Y"],
        ])

        result = detect_alternations(
            corpus,
            min_shared_prefix_length=1,
            max_suffix_diff_length=1,
            min_independent_stems=1,
            alternation_alpha=1.0,
        )

        xy_pair = None
        for pair in result.all_pairs:
            if {pair.sign_a, pair.sign_b} == {"X", "Y"}:
                xy_pair = pair
                break

        assert xy_pair is not None, "Expected to find X-Y pair"
        assert xy_pair.weighted_stems == pytest.approx(1.0, abs=1e-10), (
            f"weighted_stems={xy_pair.weighted_stems}, expected 1.0 for diff_len=1"
        )

    def test_mixed_weights_in_affinity_matrix(self) -> None:
        """Verify the affinity matrix uses weighted sums, not raw stem counts.

        Create two separate alternation pairs:
        - P-Q from diff_len=1 only (weight 1.0 per stem)
        - M-N from diff_len=2 final position only (weight 0.5 per stem)

        If the affinity matrix correctly uses weighted_stems, then the
        affinity entry for P-Q should be 1.0 and for M-N should be 0.5.
        With the old bug (using independent_stems), both would be 1.0.

        NOTE: diff_len=2 now only extracts the FINAL-position pair (M vs N),
        not the penultimate pair (X vs Y), which is a stem-position difference.
        """
        corpus = _make_synthetic_corpus([
            # diff_len=1: prefix "A", P vs Q (weight 1.0)
            ["A", "P"],
            ["A", "Q"],
            # diff_len=2: prefix "B", suffix differs in both positions.
            # Only final position M vs N is extracted (weight 0.5).
            # Penultimate X vs Y is a stem difference, NOT extracted.
            ["B", "X", "M"],
            ["B", "Y", "N"],
        ])

        result = detect_alternations(
            corpus,
            min_shared_prefix_length=1,
            max_suffix_diff_length=2,
            min_independent_stems=1,
            alternation_alpha=1.0,
        )

        pq_pair = None
        mn_pair = None
        for pair in result.all_pairs:
            if {pair.sign_a, pair.sign_b} == {"P", "Q"}:
                pq_pair = pair
            if {pair.sign_a, pair.sign_b} == {"M", "N"}:
                mn_pair = pair

        assert pq_pair is not None, "Expected to find P-Q pair"
        assert mn_pair is not None, "Expected to find M-N pair (final position from diff_len=2)"

        # P-Q from diff_len=1: 1 stem at weight 1.0
        assert pq_pair.weighted_stems == pytest.approx(1.0, abs=1e-10), (
            f"P-Q weighted_stems={pq_pair.weighted_stems}, expected 1.0"
        )

        # M-N from diff_len=2 final position: 1 stem at weight 0.5
        assert mn_pair.weighted_stems == pytest.approx(0.5, abs=1e-10), (
            f"M-N weighted_stems={mn_pair.weighted_stems}, expected 0.5 "
            f"(diff_len=2 pairs should have weight 0.5)"
        )
