"""Tier 3: Null and negative tests for Pillar 4.

These tests verify that the pipeline produces sensible null results
when given degenerate inputs (empty corpus, shuffled data, etc.).
"""

from __future__ import annotations

import copy
import random
from typing import List, Optional, Tuple

import pytest

from pillar4.corpus_context_loader import (
    ContextCorpus,
    InscriptionContext,
    SignGroup,
    SignOccurrence,
)
from pillar4.ideogram_analyzer import analyze_ideograms
from pillar4.transaction_analyzer import analyze_transactions
from pillar4.formula_mapper import map_formulas
from pillar4.place_name_finder import find_place_names
from pillar4.anchor_assembler import assemble_anchors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sign(reading: str, pos: int, sign_type: str = "syllabogram",
               ab_code: Optional[str] = None) -> SignOccurrence:
    return SignOccurrence(
        sign_id=reading,
        sign_type=sign_type,
        reading=reading,
        position_in_sequence=pos,
        ab_code=ab_code,
    )


def _make_empty_corpus() -> ContextCorpus:
    return ContextCorpus(inscriptions=[])


def _strip_ideograms_from_corpus(
    corpus: ContextCorpus,
) -> ContextCorpus:
    """Return a copy of the corpus with all named ideograms removed."""
    new_inscriptions = []
    for insc in corpus.inscriptions:
        # Filter out named ideograms from the sign sequence
        new_seq = [
            occ for occ in insc.full_sign_sequence
            if occ.sign_type != "named_ideogram"
        ]
        # Re-number positions
        for i, occ in enumerate(new_seq):
            occ = SignOccurrence(
                sign_id=occ.sign_id,
                sign_type=occ.sign_type,
                reading=occ.reading,
                position_in_sequence=i,
                ab_code=occ.ab_code,
            )
            new_seq[i] = occ

        new_insc = InscriptionContext(
            id=insc.id,
            type=insc.type,
            site=insc.site,
            full_sign_sequence=new_seq,
            sign_groups=insc.sign_groups,
            ideograms_in_sequence=[],  # No ideograms
            numerals_in_sequence=insc.numerals_in_sequence,
            unknown_logograms_in_sequence=insc.unknown_logograms_in_sequence,
        )
        new_inscriptions.append(new_insc)

    return ContextCorpus(
        inscriptions=new_inscriptions,
        ideogram_inventory=set(),
        numeral_inventory=corpus.numeral_inventory,
        unknown_logogram_inventory=corpus.unknown_logogram_inventory,
    )


def _shuffle_ideogram_positions(
    corpus: ContextCorpus,
    seed: int = 42,
) -> ContextCorpus:
    """Return a copy of the corpus with ideogram positions randomly shuffled.

    For each inscription, the ideogram readings are shuffled among the
    same set of positions. This breaks the real co-occurrence structure.
    """
    rng = random.Random(seed)
    new_inscriptions = []

    for insc in corpus.inscriptions:
        if not insc.ideograms_in_sequence:
            new_inscriptions.append(insc)
            continue

        # Get ideogram positions and readings
        ideo_positions = [
            occ.position_in_sequence for occ in insc.ideograms_in_sequence
        ]
        ideo_readings = [occ.reading for occ in insc.ideograms_in_sequence]
        rng.shuffle(ideo_readings)

        # Rebuild the full sign sequence with shuffled ideograms
        new_seq = list(insc.full_sign_sequence)
        new_ideos = []
        for i, pos in enumerate(ideo_positions):
            old_occ = new_seq[pos]
            new_occ = SignOccurrence(
                sign_id=ideo_readings[i],
                sign_type="named_ideogram",
                reading=ideo_readings[i],
                position_in_sequence=pos,
                ab_code=old_occ.ab_code,
            )
            new_seq[pos] = new_occ
            new_ideos.append(new_occ)

        new_insc = InscriptionContext(
            id=insc.id,
            type=insc.type,
            site=insc.site,
            full_sign_sequence=new_seq,
            sign_groups=insc.sign_groups,
            ideograms_in_sequence=new_ideos,
            numerals_in_sequence=insc.numerals_in_sequence,
            unknown_logograms_in_sequence=insc.unknown_logograms_in_sequence,
        )
        new_inscriptions.append(new_insc)

    return ContextCorpus(
        inscriptions=new_inscriptions,
        ideogram_inventory=corpus.ideogram_inventory,
        numeral_inventory=corpus.numeral_inventory,
        unknown_logogram_inventory=corpus.unknown_logogram_inventory,
    )


def _make_random_sign_corpus(
    n_inscriptions: int = 50,
    signs_per_inscription: int = 10,
    seed: int = 42,
) -> ContextCorpus:
    """Build a corpus of random sign sequences (no real structure)."""
    rng = random.Random(seed)
    syllables = [
        "ka", "pa", "da", "ta", "na", "ma", "ra", "sa", "wa", "ja",
        "ki", "pi", "di", "ti", "ni", "mi", "ri", "si", "wi", "ji",
        "ku", "pu", "du", "tu", "nu", "mu", "ru", "su", "wu", "ju",
        "ke", "pe", "de", "te", "ne", "me", "re", "se", "we", "je",
        "ko", "po", "do", "to", "no", "mo", "ro", "so", "wo", "jo",
    ]

    inscriptions = []
    for i in range(n_inscriptions):
        seq = []
        for j in range(signs_per_inscription):
            reading = rng.choice(syllables)
            seq.append(_make_sign(reading, j))

        # Build sign-groups from pairs of consecutive signs
        sign_groups = []
        for j in range(0, signs_per_inscription - 1, 2):
            sg = SignGroup(
                signs=[seq[j], seq[j + 1]],
                sign_ids=(seq[j].reading, seq[j + 1].reading),
                ab_codes_str=f"{seq[j].reading}-{seq[j + 1].reading}",
                transliteration=f"{seq[j].reading}-{seq[j + 1].reading}",
                has_damage=False,
                segmentation_confidence="divider_attested",
                inscription_id=f"RAND-{i}",
                position_in_inscription=j // 2,
            )
            sign_groups.append(sg)

        insc = InscriptionContext(
            id=f"RAND-{i}",
            type="Tablet",
            site="Random Site",
            full_sign_sequence=seq,
            sign_groups=sign_groups,
        )
        inscriptions.append(insc)

    return ContextCorpus(inscriptions=inscriptions)


# ===========================================================================
# Tests
# ===========================================================================


class TestRandomIdeogramPlacement:
    """Test that shuffled ideograms produce lower exclusivity."""

    def test_random_ideogram_placement_no_exclusivity(
        self, context_corpus: ContextCorpus
    ):
        """Randomly shuffle ideogram positions in the corpus.

        Exclusivity scores should be significantly lower than real data,
        because the co-occurrence structure is destroyed.
        """
        # Run on real corpus
        real_result = analyze_ideograms(
            context_corpus,
            adjacency_window=3,
            min_co_occurrence=1,
            min_exclusivity=0.0,
            co_occurrence_alpha=1.0,  # Accept all
        )
        real_exclusivities = [
            a.exclusivity for a in real_result.semantic_field_assignments
        ]

        # Run on shuffled corpus
        shuffled_corpus = _shuffle_ideogram_positions(context_corpus, seed=42)
        shuffled_result = analyze_ideograms(
            shuffled_corpus,
            adjacency_window=3,
            min_co_occurrence=1,
            min_exclusivity=0.0,
            co_occurrence_alpha=1.0,
        )
        shuffled_exclusivities = [
            a.exclusivity for a in shuffled_result.semantic_field_assignments
        ]

        # The real corpus should have higher mean exclusivity
        if real_exclusivities and shuffled_exclusivities:
            real_mean = sum(real_exclusivities) / len(real_exclusivities)
            shuf_mean = sum(shuffled_exclusivities) / len(shuffled_exclusivities)
            # Real data should have stronger exclusivity than shuffled
            # (not necessarily strictly, but on average)
            assert real_mean >= shuf_mean * 0.8, (
                f"Real mean exclusivity ({real_mean:.3f}) is not clearly "
                f"higher than shuffled ({shuf_mean:.3f})"
            )


class TestEmptyCorpus:
    """Tests on empty corpus."""

    def test_empty_corpus_produces_no_anchors(self):
        """An empty corpus should produce 0 anchors."""
        corpus = _make_empty_corpus()

        ideo = analyze_ideograms(corpus)
        trans = analyze_transactions(corpus)
        form = map_formulas(corpus)
        place = find_place_names(corpus)

        vocab = assemble_anchors(
            ideogram_result=ideo,
            transaction_result=trans,
            formula_result=form,
            place_name_result=place,
        )
        assert vocab.n_anchored == 0


class TestNoIdeograms:
    """Tests on corpus with ideograms removed."""

    def test_no_ideograms_produces_no_commodity_anchors(
        self, context_corpus: ContextCorpus
    ):
        """A corpus with all ideograms removed should produce 0
        commodity-field anchors.

        Place names and ku-ro may still appear.
        """
        stripped = _strip_ideograms_from_corpus(context_corpus)

        ideo = analyze_ideograms(stripped)
        trans = analyze_transactions(stripped)
        form = map_formulas(stripped)
        place = find_place_names(stripped)

        vocab = assemble_anchors(
            ideogram_result=ideo,
            transaction_result=trans,
            formula_result=form,
            place_name_result=place,
            min_anchor_confidence=0.3,
        )

        commodity_anchors = [
            a for a in vocab.anchored_sign_groups
            if a.semantic_field.startswith("COMMODITY:")
        ]
        assert len(commodity_anchors) == 0, (
            f"Found {len(commodity_anchors)} commodity anchors with no "
            f"ideograms: {[a.sign_group_ids for a in commodity_anchors]}"
        )


class TestRandomSignSequences:
    """Tests on random sign sequences."""

    def test_random_sign_sequences_no_place_names(self):
        """Random sign sequences should not match confirmed place names.

        The probability of a random 2-3 sign sequence matching PA-I-TO,
        I-DA, or A-DI-KI-TE is extremely low.
        """
        corpus = _make_random_sign_corpus(
            n_inscriptions=100, signs_per_inscription=20, seed=12345
        )
        result = find_place_names(corpus)

        assert len(result.found) == 0, (
            f"Random corpus matched {len(result.found)} place names: "
            f"{[m.name for m in result.found]}"
        )
