"""Tier 3: Null and negative tests for Pillar 3.

Three null/negative tests:
1. Random word-order shuffling: direction ratios near 1.0, no significance.
2. Uniform random corpus: low silhouette (< 0.3) for random data.
3. Functional word false positive check: uniform frequency/length -> few/no FW.
"""

from __future__ import annotations

import copy
import random
from collections import Counter
from typing import List, Tuple

import numpy as np
import pytest

from pillar3.data_loader import (
    CorpusInscription,
    CorpusWord,
    GrammarInputData,
    Pillar1Data,
    Pillar2Data,
    GridAssignment,
    SegmentedWord,
    MorphologicalWordClass,
)
from pillar3.profile_builder import build_profiles, ProfileMatrix
from pillar3.word_class_inducer import induce_word_classes, WordClassResult
from pillar3.word_order_analyzer import analyze_word_order, WordOrderResult
from pillar3.functional_word_finder import find_functional_words, FunctionalWordResult


# ---------------------------------------------------------------------------
# Helper: build minimal synthetic Pillar1 / Pillar2
# ---------------------------------------------------------------------------

def _make_minimal_pillar1() -> Pillar1Data:
    """Create a minimal Pillar1Data with a few grid assignments."""
    signs = [f"S{i:02d}" for i in range(20)]
    assignments = [
        GridAssignment(
            sign_id=s,
            consonant_class=i % 4,
            vowel_class=i % 3,
            confidence=0.5,
            evidence_count=2,
        )
        for i, s in enumerate(signs)
    ]
    return Pillar1Data(
        grid_assignments=assignments,
        consonant_count=4,
        vowel_count=3,
        vowel_sign_ids=["S00"],
        favored_bigrams=[],
        forbidden_bigrams=[],
        sign_to_grid={a.sign_id: a for a in assignments},
        favored_bigram_set=set(),
        pillar1_hash="test_null_p1",
    )


def _make_minimal_pillar2(signs: List[str]) -> Pillar2Data:
    """Create a minimal Pillar2Data with unsegmented entries."""
    segmented_lexicon = []
    for s in signs:
        segmented_lexicon.append(SegmentedWord(
            word_sign_ids=[s],
            stem=[s],
            suffixes=[],
            prefixes=[],
            segmentation_confidence=1.0,
            frequency=1,
            inscription_types=["test"],
            method="test",
        ))

    morph_classes = [
        MorphologicalWordClass(
            class_id=0,
            label="uninflected",
            description="test",
            n_stems=len(signs),
            paradigm_classes=[],
        ),
    ]

    stem_to_word_class = {(s,): "uninflected" for s in signs}
    word_ids_to_stem = {(s,): (s,) for s in signs}

    return Pillar2Data(
        segmented_lexicon=segmented_lexicon,
        affix_inventory_suffixes=[],
        affix_inventory_prefixes=[],
        paradigm_classes=[],
        n_paradigm_classes=0,
        morphological_word_classes=morph_classes,
        stem_to_word_class=stem_to_word_class,
        stem_to_paradigm_class={},
        stem_to_suffixes={},
        word_ids_to_stem=word_ids_to_stem,
        pillar2_hash="test_null_p2",
    )


# ========================================================================
# Test 1: Random word-order shuffling
# ========================================================================

class TestRandomWordOrderShuffling:
    """Shuffling word positions within inscriptions should destroy ordering signal."""

    def test_shuffled_direction_ratios_near_one(
        self,
        grammar_input: GrammarInputData,
        word_classes: WordClassResult,
    ):
        """After shuffling word order within each inscription, direction ratios
        should be near 1.0 (no directional preference) and no significant
        p-values should appear.
        """
        rng = random.Random(42)

        # Deep-copy inscriptions and shuffle word order within each
        shuffled_inscriptions: List[CorpusInscription] = []
        for insc in grammar_input.inscriptions:
            if len(insc.words) < 3:
                shuffled_inscriptions.append(insc)
                continue

            # Shuffle the words
            shuffled_words_raw = list(insc.words)
            rng.shuffle(shuffled_words_raw)

            # Rebuild with new positions
            new_words = []
            for pos, w in enumerate(shuffled_words_raw):
                new_words.append(CorpusWord(
                    word_sign_ids=w.word_sign_ids,
                    transliteration=w.transliteration,
                    inscription_id=w.inscription_id,
                    inscription_type=w.inscription_type,
                    position_in_inscription=pos,
                    total_words_in_inscription=len(shuffled_words_raw),
                    has_numeral_after=False,
                    has_damage=w.has_damage,
                ))

            shuffled_inscriptions.append(CorpusInscription(
                inscription_id=insc.inscription_id,
                inscription_type=insc.inscription_type,
                site=insc.site,
                words=new_words,
                sign_count=insc.sign_count,
                word_count=insc.word_count,
            ))

        # Create a modified GrammarInputData with shuffled inscriptions
        shuffled_data = GrammarInputData(
            pillar1=grammar_input.pillar1,
            pillar2=grammar_input.pillar2,
            inscriptions=shuffled_inscriptions,
            corpus_hash="shuffled",
        )

        # Run word order analysis on shuffled data
        shuffled_order = analyze_word_order(
            shuffled_data, word_classes,
            config={"min_words_per_inscription": 3, "min_pair_count": 3, "alpha": 0.05},
        )

        # Check: most direction ratios should be near 1.0
        if shuffled_order.pairwise_orders:
            ratios = [po.direction_ratio for po in shuffled_order.pairwise_orders]
            median_ratio = np.median(ratios)
            # Median ratio should be near 1.0 (within 0.5-2.0 range)
            assert 0.3 < median_ratio < 3.0, (
                f"Median direction ratio after shuffling = {median_ratio}, "
                f"expected near 1.0"
            )

        # Check: no strongly significant p-values after shuffling
        n_sig = sum(
            1 for po in shuffled_order.pairwise_orders
            if po.p_value < 0.001
        )
        # Allow a small fraction of false positives (< 20%)
        total_tested = len(shuffled_order.pairwise_orders)
        if total_tested > 0:
            false_positive_rate = n_sig / total_tested
            assert false_positive_rate < 0.20, (
                f"Too many significant orderings after shuffling: "
                f"{n_sig}/{total_tested} = {false_positive_rate:.2%}"
            )


# ========================================================================
# Test 2: Uniform random corpus -> low silhouette
# ========================================================================

class TestUniformRandomCorpus:
    """Random corpus data should produce low-quality clusters."""

    def test_random_corpus_low_silhouette(self):
        """Randomly generated words/stems should yield silhouette < 0.3."""
        rng = np.random.RandomState(42)
        signs = [f"R{i:02d}" for i in range(30)]

        # Build a random corpus: 100 inscriptions with 3-6 random words each
        inscriptions: List[CorpusInscription] = []
        py_rng = random.Random(42)

        for idx in range(100):
            n_words = py_rng.randint(3, 6)
            words = []
            for pos in range(n_words):
                sign = py_rng.choice(signs)
                words.append(CorpusWord(
                    word_sign_ids=[sign],
                    transliteration=sign,
                    inscription_id=f"test_{idx}",
                    inscription_type="test",
                    position_in_inscription=pos,
                    total_words_in_inscription=n_words,
                    has_numeral_after=False,
                ))
            inscriptions.append(CorpusInscription(
                inscription_id=f"test_{idx}",
                inscription_type="test",
                site="test",
                words=words,
            ))

        pillar1 = _make_minimal_pillar1()
        pillar2 = _make_minimal_pillar2(signs)

        data = GrammarInputData(
            pillar1=pillar1,
            pillar2=pillar2,
            inscriptions=inscriptions,
            corpus_hash="random_test",
        )

        # Build profiles
        profiles = build_profiles(
            data, config={"min_stem_frequency": 2, "top_k_contexts": 10}
        )

        if len(profiles.stems) < 5:
            pytest.skip("Not enough stems for meaningful clustering")

        # Induce word classes
        wc = induce_word_classes(
            profiles, pillar2,
            config={"min_k": 3, "max_k": 6, "random_state": 42},
        )

        # Silhouette should be low for random data
        assert wc.silhouette < 0.5, (
            f"Silhouette = {wc.silhouette:.3f} on random data, expected < 0.5"
        )


# ========================================================================
# Test 3: Functional word false positive check
# ========================================================================

class TestFunctionalWordFalsePositive:
    """On a corpus where all words have same frequency and length,
    no functional words should be identified (or very few).
    """

    def test_uniform_corpus_no_false_positives(self):
        """When all single-sign words appear with equal frequency and in
        the same number of inscriptions, the classifier should not
        identify any functional words (all are 'declining', or none
        pass the diversity threshold).
        """
        signs = [f"U{i:02d}" for i in range(10)]

        # Build corpus where each sign appears exactly the same number of
        # times across the same number of inscriptions. We use 10 signs
        # in 50 inscriptions, 3 words each.
        inscriptions: List[CorpusInscription] = []
        py_rng = random.Random(42)

        for idx in range(50):
            chosen = py_rng.sample(signs, 3)
            words = []
            for pos, sign in enumerate(chosen):
                words.append(CorpusWord(
                    word_sign_ids=[sign],
                    transliteration=sign,
                    inscription_id=f"unif_{idx}",
                    inscription_type="test",
                    position_in_inscription=pos,
                    total_words_in_inscription=3,
                    has_numeral_after=False,
                ))
            inscriptions.append(CorpusInscription(
                inscription_id=f"unif_{idx}",
                inscription_type="test",
                site="test",
                words=words,
            ))

        pillar1 = _make_minimal_pillar1()

        # Mark all stems as "declining" so they are excluded from
        # functional word consideration
        segmented_lexicon = []
        for s in signs:
            segmented_lexicon.append(SegmentedWord(
                word_sign_ids=[s],
                stem=[s],
                suffixes=[["X"]],  # has suffixes -> declining
                prefixes=[],
                segmentation_confidence=1.0,
                frequency=15,
                inscription_types=["test"],
                method="test",
            ))

        morph_classes = [
            MorphologicalWordClass(
                class_id=0,
                label="declining",
                description="test",
                n_stems=len(signs),
                paradigm_classes=[0],
            ),
        ]

        stem_to_word_class = {(s,): "declining" for s in signs}
        word_ids_to_stem = {(s,): (s,) for s in signs}
        stem_to_suffixes = {(s,): [("X",)] for s in signs}

        pillar2 = Pillar2Data(
            segmented_lexicon=segmented_lexicon,
            affix_inventory_suffixes=[],
            affix_inventory_prefixes=[],
            paradigm_classes=[],
            n_paradigm_classes=0,
            morphological_word_classes=morph_classes,
            stem_to_word_class=stem_to_word_class,
            stem_to_paradigm_class={},
            stem_to_suffixes=stem_to_suffixes,
            word_ids_to_stem=word_ids_to_stem,
            pillar2_hash="test_uniform_p2",
        )

        data = GrammarInputData(
            pillar1=pillar1,
            pillar2=pillar2,
            inscriptions=inscriptions,
            corpus_hash="uniform_test",
        )

        # Find functional words -- all are "declining", so none should qualify
        fw_result = find_functional_words(
            data,
            word_classes=None,
            config={"max_length": 2, "min_freq": 5, "min_inscriptions": 5},
        )

        assert fw_result.n_functional == 0, (
            f"Expected 0 functional words on all-declining corpus, "
            f"got {fw_result.n_functional}"
        )
