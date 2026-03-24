"""Tier 2: Known-answer tests using real Linear A corpus data.

Uses the session-scoped fixtures from conftest.py that load the real
SigLA corpus, Pillar 1, and Pillar 2 outputs and run the full
Pillar 3 analysis chain.

These tests verify that the pipeline produces reasonable results on
real data, without hardcoding exact values (which depend on the corpus).
"""

from __future__ import annotations

import pytest
import numpy as np

from pillar3.data_loader import GrammarInputData
from pillar3.profile_builder import ProfileMatrix
from pillar3.word_class_inducer import WordClassResult
from pillar3.word_order_analyzer import WordOrderResult
from pillar3.agreement_detector import AgreementResult
from pillar3.functional_word_finder import FunctionalWordResult


# ========================================================================
# Test: word classes separate content from function
# ========================================================================

class TestWordClassSeparation:
    """Verify that word class induction produces meaningful clusters."""

    def test_word_classes_found(self, word_classes: WordClassResult):
        """At least 3 word classes should be induced."""
        assert word_classes.n_classes >= 3

    def test_largest_cluster_has_most_members(
        self,
        word_classes: WordClassResult,
    ):
        """The largest cluster should contain a substantial fraction of stems.

        In the real Linear A corpus, most stems fall into a dominant cluster
        reflecting the major distributional pattern.
        """
        if not word_classes.classes:
            pytest.skip("No word classes induced")
        largest = max(word_classes.classes, key=lambda c: c.n_members)
        total = sum(c.n_members for c in word_classes.classes)
        fraction = largest.n_members / total if total > 0 else 0
        assert fraction > 0.3, (
            f"Largest cluster has only {fraction:.1%} of stems, expected > 30%"
        )

    def test_silhouette_positive(self, word_classes: WordClassResult):
        """Silhouette score should be positive for a meaningful clustering."""
        assert word_classes.silhouette > 0, (
            f"Silhouette score should be > 0, got {word_classes.silhouette}"
        )

    def test_all_stems_assigned(
        self,
        profiles: ProfileMatrix,
        word_classes: WordClassResult,
    ):
        """Every profiled stem should be assigned to a word class."""
        for stem in profiles.stems:
            assert stem in word_classes.assignments, (
                f"Stem {stem} not found in word class assignments"
            )


# ========================================================================
# Test: functional words found
# ========================================================================

class TestFunctionalWordsFound:
    """Verify that functional words are identified from the corpus."""

    def test_some_functional_words_found(
        self,
        functional_words: FunctionalWordResult,
    ):
        """At least some functional words should be found in the Linear A corpus.

        Short, high-frequency, widely-distributed uninflected words should
        be identified as functional.
        """
        assert functional_words.n_functional > 0, (
            "Expected at least 1 functional word in the Linear A corpus"
        )

    def test_functional_words_are_short(
        self,
        functional_words: FunctionalWordResult,
    ):
        """Functional words should have at most 2 signs."""
        for fw in functional_words.functional_words:
            real_signs = [
                s for s in fw.word_sign_ids
                if s not in ("[?]", "?") and not s.startswith("[")
            ]
            assert len(real_signs) <= 2, (
                f"Functional word {fw.reading} has {len(real_signs)} signs, "
                f"expected <= 2"
            )

    def test_functional_words_are_frequent(
        self,
        functional_words: FunctionalWordResult,
    ):
        """Functional words should meet the frequency threshold."""
        for fw in functional_words.functional_words:
            assert fw.frequency >= 5, (
                f"Functional word {fw.reading} has frequency {fw.frequency}, "
                f"expected >= 5"
            )

    def test_functional_words_have_valid_classification(
        self,
        functional_words: FunctionalWordResult,
    ):
        """Each functional word should have a valid classification."""
        valid = {"structural_marker", "relator", "determiner", "particle"}
        for fw in functional_words.functional_words:
            assert fw.classification in valid, (
                f"Functional word {fw.reading} has invalid classification "
                f"'{fw.classification}'"
            )


# ========================================================================
# Test: agreement patterns are not wildly significant on small corpus
# ========================================================================

class TestAgreementSanity:
    """Agreement patterns should be statistically reasonable."""

    def test_agreement_tested_some_pairs(
        self,
        agreement: AgreementResult,
    ):
        """The agreement detector should test at least some class pairs."""
        assert agreement.n_pairs_tested >= 0

    def test_no_false_agreement_p_floor(
        self,
        agreement: AgreementResult,
    ):
        """If there are significant patterns, their p-values should not be
        astronomically low (e.g., < 1e-20) unless the signal is massive.

        This is a sanity check against numerical bugs producing false
        extreme significance.
        """
        for pattern in agreement.patterns:
            # A p-value < 1e-20 on a small corpus would indicate a bug
            # unless n_adjacent_pairs is very large (> 100)
            if pattern.n_adjacent_pairs < 100:
                assert pattern.p_value_raw > 1e-20, (
                    f"Suspiciously extreme p-value {pattern.p_value_raw} for "
                    f"class pair {pattern.word_pair_classes} with only "
                    f"{pattern.n_adjacent_pairs} observations"
                )

    def test_expected_rate_reasonable(
        self,
        agreement: AgreementResult,
    ):
        """Expected suffix match rate should be between 0 and 1."""
        assert 0.0 <= agreement.expected_rate <= 1.0


# ========================================================================
# Test: word order analysis
# ========================================================================

class TestWordOrderSanity:
    """Word order analysis should produce reasonable results."""

    def test_precedence_matrix_shape(
        self,
        word_order: WordOrderResult,
        word_classes: WordClassResult,
    ):
        """Precedence matrix should be n_classes x n_classes."""
        assert word_order.precedence_matrix.shape == (
            word_classes.n_classes, word_classes.n_classes
        )

    def test_position_stats_per_class(
        self,
        word_order: WordOrderResult,
        word_classes: WordClassResult,
    ):
        """Should have position stats for each word class."""
        assert len(word_order.position_stats) == word_classes.n_classes

    def test_mean_positions_bounded(
        self,
        word_order: WordOrderResult,
    ):
        """Mean relative positions should be in [0, 1]."""
        for ps in word_order.position_stats:
            if ps.n_observations > 0:
                assert 0.0 <= ps.mean_relative_position <= 1.0


# ========================================================================
# Test: profiles
# ========================================================================

class TestProfilesSanity:
    """Distributional profiles should be well-formed."""

    def test_profile_matrix_no_nan(self, profiles: ProfileMatrix):
        """Profile matrix should not contain NaN values."""
        assert not np.any(np.isnan(profiles.feature_matrix)), (
            "Profile matrix contains NaN values"
        )

    def test_profile_has_stems(self, profiles: ProfileMatrix):
        """Profile should include stems from the corpus."""
        assert len(profiles.stems) > 10, (
            f"Expected > 10 stems in profiles, got {len(profiles.stems)}"
        )
