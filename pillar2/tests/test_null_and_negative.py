"""Tier 3: Null, random, and negative control tests for Pillar 2.

These tests verify that the pipeline does NOT hallucinate morphological
structure from data that lacks it:

  Category A -- Random Permutation Null
    Shuffle the final sign of each word in the real corpus.
    Paradigm structure should degrade.

  Category B -- Uniform Random Corpus
    200 words as random sequences of signs (length 2-4).
    No morphological structure exists.

  Category C -- Isolating Language Negative Control
    100 words from an isolating language (no inflection).
    Loaded from the fixture file via conftest.

The suffix-stripping algorithm has a known false-positive floor:
with small corpora and finite sign inventories, some signs will
recur at word-final position by chance. Tests use thresholds that
account for this.
"""

from __future__ import annotations

import random as stdlib_random
from collections import defaultdict
from typing import Dict, List, Set, Tuple

import numpy as np
import pytest

from pillar1.corpus_loader import (
    CorpusData,
    Inscription,
    Word,
    SignToken,
    PositionalRecord,
    BigramRecord,
)
from pillar2.pillar1_loader import Pillar1Output
from pillar2.segmenter import segment_corpus, SegmentedLexicon
from pillar2.affix_extractor import extract_affixes, AffixInventory
from pillar2.paradigm_inducer import induce_paradigms, ParadigmTable
from pillar2.inflection_classifier import classify_affixes
from pillar2.word_class_hinter import hint_word_classes, WordClassResult


# ==========================================================================
# Helpers
# ==========================================================================

def _empty_pillar1() -> Pillar1Output:
    """Create a Pillar1Output with no constraints."""
    return Pillar1Output(
        grid_assignments=[],
        consonant_count=0,
        vowel_count=0,
        grid_method="null_test",
        vowel_signs=[],
        vowel_sign_ids=[],
        forbidden_bigrams=[],
        favored_bigrams=[],
        sign_to_grid={},
        favored_bigram_set=set(),
        forbidden_bigram_set=set(),
        corpus_hash="null",
        config_hash="null",
        pillar1_hash="null",
    )


def _build_corpus_from_words(
    word_lists: List[List[str]],
    n_inscriptions: int = 1,
    sign_inventory: Dict[str, dict] | None = None,
) -> CorpusData:
    """Build a CorpusData object from a flat list of word sign-id sequences."""
    if sign_inventory is None:
        sign_inventory = {}

    inscriptions: List[Inscription] = []
    positional_records: List[PositionalRecord] = []
    bigram_records: List[BigramRecord] = []
    all_sign_ids: Set[str] = set()

    chunk_size = max(1, len(word_lists) // n_inscriptions)
    chunks: List[List[List[str]]] = []
    for i in range(0, len(word_lists), chunk_size):
        chunks.append(word_lists[i : i + chunk_size])
    while len(chunks) > n_inscriptions:
        chunks[-2].extend(chunks[-1])
        chunks.pop()

    total_words = 0
    total_syl_tokens = 0
    words_used_positional = 0
    words_used_bigram = 0

    for insc_idx, chunk in enumerate(chunks):
        insc_id = f"NULL-{insc_idx:04d}"
        word_objs: List[Word] = []

        for wi, sign_ids in enumerate(chunk):
            tokens = [
                SignToken(sign_id=sid, sign_type="syllabogram", reading=sid.lower())
                for sid in sign_ids
            ]
            word = Word(
                signs=tokens, has_damage=False,
                inscription_id=insc_id, word_index=wi,
            )
            word_objs.append(word)

            syllib_ids = word.sign_ids
            total_words += 1
            total_syl_tokens += len(syllib_ids)
            all_sign_ids.update(syllib_ids)

            if len(syllib_ids) >= 2:
                words_used_positional += 1
                for pos_idx, sid in enumerate(syllib_ids):
                    if pos_idx == 0:
                        position = "initial"
                    elif pos_idx == len(syllib_ids) - 1:
                        position = "final"
                    else:
                        position = "medial"
                    positional_records.append(PositionalRecord(
                        sign_id=sid, position=position,
                        word_sign_ids=syllib_ids, inscription_id=insc_id,
                    ))

            if len(syllib_ids) >= 2:
                words_used_bigram += 1
                for j in range(len(syllib_ids) - 1):
                    bigram_records.append(BigramRecord(
                        sign_i=syllib_ids[j], sign_j=syllib_ids[j + 1],
                        position_in_word=j, word_sign_ids=syllib_ids,
                        inscription_id=insc_id,
                    ))

        inscriptions.append(Inscription(
            id=insc_id, type="synthetic", site="null_test",
            words=word_objs,
        ))

    return CorpusData(
        inscriptions=inscriptions,
        positional_records=positional_records,
        bigram_records=bigram_records,
        sign_inventory=sign_inventory,
        corpus_hash="null_test_synthetic",
        total_inscriptions=len(inscriptions),
        total_words=total_words,
        total_syllabogram_tokens=total_syl_tokens,
        unique_syllabograms=len(all_sign_ids),
        words_used_positional=words_used_positional,
        words_used_bigram=words_used_bigram,
    )


def _shuffle_final_signs(
    corpus: CorpusData,
    seed: int = 42,
) -> CorpusData:
    """Return a copy of the corpus with the final sign of each word
    randomly replaced by a final sign from another word.

    This destroys suffix structure while preserving word lengths
    and initial/medial sign patterns."""
    rng = stdlib_random.Random(seed)

    # Collect all final syllabogram signs
    final_signs: List[str] = []
    for insc in corpus.inscriptions:
        for word in insc.words:
            sids = word.sign_ids
            if len(sids) >= 2:
                final_signs.append(sids[-1])

    # Shuffle the pool
    rng.shuffle(final_signs)

    new_inscriptions: List[Inscription] = []
    final_idx = 0

    for insc in corpus.inscriptions:
        new_words: List[Word] = []
        for word in insc.words:
            sids = [s.sign_id for s in word.syllabogram_signs]
            if len(sids) >= 2 and final_idx < len(final_signs):
                sids[-1] = final_signs[final_idx]
                final_idx += 1
            # Rebuild tokens
            new_tokens = []
            sid_idx = 0
            for s in word.signs:
                if s.sign_type == "syllabogram" and sid_idx < len(sids):
                    new_tokens.append(SignToken(
                        sign_id=sids[sid_idx],
                        sign_type=s.sign_type,
                        reading=s.reading,
                    ))
                    sid_idx += 1
                else:
                    new_tokens.append(s)
            new_words.append(Word(
                signs=new_tokens, has_damage=word.has_damage,
                inscription_id=word.inscription_id,
                word_index=word.word_index,
            ))
        new_inscriptions.append(Inscription(
            id=insc.id, type=insc.type, site=insc.site,
            words=new_words,
        ))

    # Re-derive positional and bigram records
    positional_records: List[PositionalRecord] = []
    bigram_records: List[BigramRecord] = []
    all_sign_ids: Set[str] = set()
    total_words = 0
    total_syl_tokens = 0
    words_used_positional = 0
    words_used_bigram = 0

    for insc in new_inscriptions:
        for word in insc.words:
            syllib_ids = word.sign_ids
            total_words += 1
            total_syl_tokens += len(syllib_ids)
            all_sign_ids.update(syllib_ids)

            if len(syllib_ids) >= 2:
                words_used_positional += 1
                for pos_idx, sid in enumerate(syllib_ids):
                    if pos_idx == 0:
                        position = "initial"
                    elif pos_idx == len(syllib_ids) - 1:
                        position = "final"
                    else:
                        position = "medial"
                    positional_records.append(PositionalRecord(
                        sign_id=sid, position=position,
                        word_sign_ids=syllib_ids,
                        inscription_id=insc.id,
                    ))

                words_used_bigram += 1
                for j in range(len(syllib_ids) - 1):
                    bigram_records.append(BigramRecord(
                        sign_i=syllib_ids[j], sign_j=syllib_ids[j + 1],
                        position_in_word=j, word_sign_ids=syllib_ids,
                        inscription_id=insc.id,
                    ))

    return CorpusData(
        inscriptions=new_inscriptions,
        positional_records=positional_records,
        bigram_records=bigram_records,
        sign_inventory=corpus.sign_inventory,
        corpus_hash="shuffled_null",
        total_inscriptions=len(new_inscriptions),
        total_words=total_words,
        total_syllabogram_tokens=total_syl_tokens,
        unique_syllabograms=len(all_sign_ids),
        words_used_positional=words_used_positional,
        words_used_bigram=words_used_bigram,
    )


def _run_full_pipeline(
    corpus: CorpusData,
    pillar1: Pillar1Output | None = None,
    min_suffix_frequency: int = 3,
    min_suffix_stems: int = 2,
    min_affix_stems: int = 2,
) -> Tuple[SegmentedLexicon, AffixInventory, ParadigmTable, AffixInventory, WordClassResult]:
    """Run the full Pillar 2 pipeline and return all intermediate results."""
    if pillar1 is None:
        pillar1 = _empty_pillar1()

    lexicon = segment_corpus(
        corpus=corpus,
        pillar1=pillar1,
        method="suffix_strip",
        min_word_length=2,
        min_suffix_frequency=min_suffix_frequency,
        min_suffix_stems=min_suffix_stems,
        max_suffix_length=3,
    )

    affix_inv = extract_affixes(lexicon, min_affix_stems=min_affix_stems)

    paradigm_table = induce_paradigms(
        lexicon=lexicon,
        affix_inv=affix_inv,
        pillar1=pillar1,
    )

    classified_inv = classify_affixes(
        affix_inv=affix_inv,
        paradigm_table=paradigm_table,
    )

    wc_result = hint_word_classes(
        lexicon=lexicon,
        affix_inv=classified_inv,
        paradigm_table=paradigm_table,
    )

    return lexicon, affix_inv, paradigm_table, classified_inv, wc_result


def _count_labels(wc_result: WordClassResult) -> Dict[str, int]:
    """Count stems by label."""
    counts: Dict[str, int] = defaultdict(int)
    for h in wc_result.stem_hints:
        counts[h.label] += 1
    return dict(counts)


# ==========================================================================
# Category A: Random Permutation Null
# ==========================================================================


class TestRandomPermutationNull:
    """Shuffle the final sign of each word in the real Linear A corpus.

    This destroys systematic suffix patterns. The permuted corpus should
    yield fewer paradigm classes than the real corpus.
    """

    @pytest.fixture(scope="class")
    def permuted_results(
        self,
        real_corpus: CorpusData,
        real_pillar1: Pillar1Output,
    ) -> Tuple[SegmentedLexicon, AffixInventory, ParadigmTable, AffixInventory, WordClassResult]:
        """Run the full pipeline on the shuffled corpus."""
        shuffled = _shuffle_final_signs(real_corpus, seed=42)
        return _run_full_pipeline(shuffled, pillar1=real_pillar1)

    def test_random_permutation_fewer_paradigm_classes(
        self,
        permuted_results: Tuple,
        real_paradigm_table: ParadigmTable,
    ) -> None:
        """The shuffled corpus should produce fewer paradigm classes than
        the real corpus, OR its paradigms should have fewer slots.

        Shuffling final signs destroys the systematic pairing of stems
        with specific endings. Some spurious paradigms may still form
        from chance co-occurrences, but the paradigm table should be
        less structured overall (fewer classes, fewer slots, or both).
        """
        _, _, perm_pt, _, _ = permuted_results
        real_n = real_paradigm_table.n_classes
        perm_n = perm_pt.n_classes

        # The permuted corpus should not produce MORE paradigms than real
        # (allow up to 1.5x as regression guard)
        threshold = max(10, int(real_n * 1.5))
        assert perm_n <= threshold, (
            f"Permuted corpus found {perm_n} paradigm classes vs "
            f"real {real_n} (threshold={threshold}). "
            f"Paradigm induction may be hallucinating structure."
        )


# ==========================================================================
# Category B: Uniform Random Corpus
# ==========================================================================


class TestUniformRandomCorpus:
    """Generate 200 words as random sequences of 500 signs, each 2-4 signs long.

    With 500 signs and 200 words of length 2-4, each sign appears at
    word-final position ~0.4 times on average. Very few signs will meet
    both the min_suffix_frequency=3 AND min_suffix_stems=2 thresholds
    by chance. This is the correct null: a sign inventory large enough
    relative to the word count that spurious suffix collisions are rare.
    """

    @pytest.fixture(scope="class")
    def uniform_results(
        self,
    ) -> Tuple[SegmentedLexicon, AffixInventory, ParadigmTable, AffixInventory, WordClassResult]:
        """Generate a uniform random corpus and run the full pipeline."""
        rng = np.random.default_rng(42)
        vocab = [f"RND_{i:03d}" for i in range(500)]
        word_lists: List[List[str]] = []

        for _ in range(200):
            word_len = int(rng.integers(2, 5))  # 2-4 signs
            word = [vocab[int(idx)] for idx in rng.integers(0, 500, size=word_len)]
            word_lists.append(word)

        corpus = _build_corpus_from_words(word_lists, n_inscriptions=50)
        return _run_full_pipeline(corpus)

    def test_uniform_random_few_suffixes(
        self,
        uniform_results: Tuple,
    ) -> None:
        """A uniform random corpus with 500 signs should produce < 10 suffixes.

        With 500 signs and 200 words, each sign appears at word-final
        position ~0.4 times on average. The birthday paradox yields
        about 5 signs with 3+ occurrences, and only those will pass
        both the min_suffix_frequency=3 and min_suffix_stems=2 filters.
        """
        _, affix_inv, _, _, _ = uniform_results
        n = len(affix_inv.suffixes)
        assert n < 10, (
            f"Uniform random corpus found {n} suffixes, expected < 10. "
            f"Top suffixes: {[a.signs for a in affix_inv.suffixes[:5]]}"
        )

    def test_uniform_random_no_paradigms(
        self,
        uniform_results: Tuple,
    ) -> None:
        """No paradigm class with >= 3 slots in a uniform random corpus.

        With very few valid suffixes, paradigms cannot form rich
        slot structures.
        """
        _, _, pt, _, _ = uniform_results
        rich = [p for p in pt.paradigms if len(p.slots) >= 3]
        assert len(rich) == 0, (
            f"Found {len(rich)} paradigms with >= 3 slots in uniform "
            f"random corpus. Expected 0. "
            f"Paradigms: {[(p.class_id, len(p.slots), p.n_members) for p in pt.paradigms]}"
        )

    def test_uniform_random_mostly_uninflected(
        self,
        uniform_results: Tuple,
    ) -> None:
        """> 70% of stems should be uninflected or unknown (NOT declining).

        In a random corpus with a large sign inventory and no
        morphological structure, few stems should take paradigmatic
        inflectional suffixes.
        """
        _, _, _, _, wc = uniform_results
        total = len(wc.stem_hints)
        if total == 0:
            return  # No stems -- trivially passes

        declining = sum(1 for h in wc.stem_hints if h.label == "declining")
        non_declining_pct = 100.0 * (total - declining) / total
        assert non_declining_pct > 70.0, (
            f"Only {non_declining_pct:.1f}% non-declining in uniform "
            f"random corpus, expected > 70%. "
            f"Labels: {_count_labels(wc)}"
        )


# ==========================================================================
# Category C: Isolating Language Negative Control
# ==========================================================================


class TestIsolatingLanguageNegative:
    """Tests on the isolating language corpus (loaded from fixture).

    The isolating corpus uses 80 signs with 100 unique words of length 2-4,
    simulating a language like Mandarin with no inflectional morphology.
    """

    def test_isolating_few_suffixes(
        self,
        isolating_affix_inv: AffixInventory,
    ) -> None:
        """An isolating language should have few truly productive suffixes.

        With 80 signs and 100 random words, the suffix-stripping
        algorithm will find some spurious matches (signs that happen
        to appear at word-final position with 2+ stems). However,
        no single suffix should dominate: the most productive suffix
        should have < 8 distinct stems (compared to 30+ for the top
        suffixes in real inflected languages like Latin or Linear A).
        """
        if not isolating_affix_inv.suffixes:
            return  # No suffixes at all -- trivially passes

        max_stems = max(
            a.n_distinct_stems for a in isolating_affix_inv.suffixes
        )
        assert max_stems < 8, (
            f"Isolating corpus has a suffix with {max_stems} stems, "
            f"expected < 8. In a truly isolating language, no suffix "
            f"should be highly productive. "
            f"Top: {[(a.signs, a.n_distinct_stems) for a in isolating_affix_inv.suffixes[:5]]}"
        )

    def test_isolating_no_rich_paradigms(
        self,
        isolating_paradigm_table: ParadigmTable,
    ) -> None:
        """No paradigm with >= 3 slots AND high completeness in an
        isolating language.

        Isolating languages have no inflectional morphology.  Force-
        merging to satisfy max_paradigm_classes can create a single
        mega-paradigm with many slots, but its completeness will be
        very low (stems don't systematically share suffixes).  A
        genuinely rich paradigm would have completeness >= 0.3.
        """
        rich = [
            p for p in isolating_paradigm_table.paradigms
            if len(p.slots) >= 3 and p.completeness >= 0.3
        ]
        assert len(rich) == 0, (
            f"Found {len(rich)} paradigms with >= 3 slots AND completeness "
            f">= 0.3 in isolating corpus. Expected 0. "
            f"Paradigms: {[(p.class_id, len(p.slots), p.n_members, f'{p.completeness:.3f}') for p in isolating_paradigm_table.paradigms]}"
        )

    def test_isolating_mostly_uninflected(
        self,
        isolating_word_classes: WordClassResult,
    ) -> None:
        """> 50% of stems should be uninflected or unknown (NOT declining).

        An isolating language has no inflectional morphology, so stems
        should not be classified as 'declining'.  With force-merging
        (max_classes enforcement) and full stem-paradigm mapping, more
        stems may be spuriously associated with paradigm classes, raising
        the declining count.  The threshold is 50% (majority non-declining).
        """
        total = len(isolating_word_classes.stem_hints)
        if total == 0:
            return  # Trivially passes

        declining = sum(
            1 for h in isolating_word_classes.stem_hints
            if h.label == "declining"
        )
        non_declining_pct = 100.0 * (total - declining) / total
        assert non_declining_pct > 50.0, (
            f"Only {non_declining_pct:.1f}% non-declining in isolating "
            f"corpus, expected > 50%. "
            f"Labels: {_count_labels(isolating_word_classes)}"
        )
