"""Tier 2: Known-answer tests on the REAL Linear A corpus.

These tests verify that specific scholarly expectations are met when
running the Pillar 4 pipeline on the actual SigLA corpus data.
They use session-scoped fixtures from conftest.py.
"""

from __future__ import annotations

import pytest

from pillar4.corpus_context_loader import ContextCorpus
from pillar4.ideogram_analyzer import IdeogramAnalysisResult
from pillar4.transaction_analyzer import TransactionAnalysisResult
from pillar4.formula_mapper import FormulaMapResult
from pillar4.place_name_finder import PlaceNameResult
from pillar4.anchor_assembler import AnchorVocabulary


# ===========================================================================
# Tests
# ===========================================================================


class TestKuroIdentification:
    """Tests that ku-ro is correctly identified in the corpus."""

    def test_kuro_identified_as_total_marker(
        self, anchor_vocab: AnchorVocabulary
    ):
        """ku-ro (AB81-AB02) should be in anchor vocabulary with
        semantic field FUNCTION:TOTAL_MARKER.
        """
        kuro_anchors = [
            a for a in anchor_vocab.anchored_sign_groups
            if a.sign_group_ids == ("ku", "ro")
        ]
        assert len(kuro_anchors) >= 1, (
            "ku-ro not found in anchor vocabulary"
        )
        anchor = kuro_anchors[0]
        assert anchor.semantic_field == "FUNCTION:TOTAL_MARKER", (
            f"ku-ro has semantic field '{anchor.semantic_field}', "
            f"expected 'FUNCTION:TOTAL_MARKER'"
        )


class TestIdeogramSemanticFields:
    """Tests that ideogram semantic fields are populated from corpus."""

    def test_at_least_three_commodity_fields(
        self, ideogram_result: IdeogramAnalysisResult
    ):
        """At least 3 of the commodity fields (FIG, GRAIN, WINE, OLIVE)
        should have associated sign-groups in the corpus.
        """
        target_fields = {
            "COMMODITY:FIG", "COMMODITY:GRAIN",
            "COMMODITY:WINE", "COMMODITY:OLIVE",
        }
        found_fields = set()
        for assignment in ideogram_result.semantic_field_assignments:
            if assignment.semantic_field in target_fields:
                found_fields.add(assignment.semantic_field)

        assert len(found_fields) >= 3, (
            f"Only {len(found_fields)} commodity fields found: "
            f"{found_fields}. Expected >= 3 of {target_fields}."
        )


class TestPlaceNames:
    """Tests for place name identification in the real corpus."""

    def test_place_name_paito_found(
        self, place_name_result: PlaceNameResult
    ):
        """PA-I-TO should appear in the anchor vocabulary.

        PA-I-TO (pa-i-to) is the universally accepted spelling for
        Phaistos in Linear A.
        """
        paito_matches = [
            m for m in place_name_result.found
            if m.name == "Phaistos"
        ]
        assert len(paito_matches) >= 1, (
            "PA-I-TO (Phaistos) not found in corpus. "
            f"Not-found list: {[nf.name for nf in place_name_result.not_found]}"
        )

    def test_place_name_ida_found(
        self, place_name_result: PlaceNameResult
    ):
        """I-DA should appear in the anchor vocabulary.

        I-DA (i-da) is the widely accepted spelling for Mount Ida.
        """
        ida_matches = [
            m for m in place_name_result.found
            if m.name == "Mount Ida"
        ]
        assert len(ida_matches) >= 1, (
            "I-DA (Mount Ida) not found in corpus. "
            f"Not-found list: {[nf.name for nf in place_name_result.not_found]}"
        )


class TestBiasRemoval:
    """Tests that bias-free labelling is enforced."""

    def test_no_deity_labels(
        self, anchor_vocab: AnchorVocabulary
    ):
        """No anchor should have semantic field containing 'deity' or 'god'.

        This is a bias removal check: we do not assign deity labels because
        they are speculative.
        """
        for anchor in anchor_vocab.anchored_sign_groups:
            field_lower = anchor.semantic_field.lower()
            assert "deity" not in field_lower, (
                f"Sign-group {anchor.sign_group_ids} has deity label: "
                f"'{anchor.semantic_field}'"
            )
            assert "god" not in field_lower, (
                f"Sign-group {anchor.sign_group_ids} has god label: "
                f"'{anchor.semantic_field}'"
            )

    def test_no_ritual_verb_labels(
        self, anchor_vocab: AnchorVocabulary
    ):
        """No anchor should have semantic field containing 'ritual' or 'verb'.

        This is a bias removal check: we do not assign ritual/verb labels
        because they are speculative.
        """
        for anchor in anchor_vocab.anchored_sign_groups:
            field_lower = anchor.semantic_field.lower()
            assert "ritual" not in field_lower, (
                f"Sign-group {anchor.sign_group_ids} has ritual label: "
                f"'{anchor.semantic_field}'"
            )
            assert "verb" not in field_lower, (
                f"Sign-group {anchor.sign_group_ids} has verb label: "
                f"'{anchor.semantic_field}'"
            )


class TestEvidenceIntegrity:
    """Tests for evidence chain integrity."""

    def test_anchors_have_evidence(
        self, anchor_vocab: AnchorVocabulary
    ):
        """Every anchor in the vocabulary should have at least one
        evidence source.
        """
        for anchor in anchor_vocab.anchored_sign_groups:
            assert len(anchor.evidence_chain) >= 1, (
                f"Sign-group {anchor.sign_group_ids} has no evidence chain"
            )
            assert anchor.n_evidence_sources >= 1, (
                f"Sign-group {anchor.sign_group_ids} has "
                f"n_evidence_sources={anchor.n_evidence_sources}"
            )

    def test_damaged_sign_groups_have_lower_confidence(
        self, context_corpus: ContextCorpus,
        anchor_vocab: AnchorVocabulary,
    ):
        """Sign-groups with damage markers should not have confidence > 0.8.

        Damaged sign-groups have uncertain readings, so their semantic
        anchoring should be more conservative.
        """
        # Find sign-groups with damage in the corpus
        damaged_sg_ids = set()
        for insc in context_corpus.inscriptions:
            for sg in insc.sign_groups:
                if sg.has_damage:
                    damaged_sg_ids.add(sg.sign_ids)

        for anchor in anchor_vocab.anchored_sign_groups:
            if anchor.sign_group_ids in damaged_sg_ids:
                # Damaged sign-groups should not have very high confidence
                # unless they are:
                # - place names (confirmed by external evidence)
                # - function markers like ku-ro (structurally confirmed
                #   by totaling behaviour, not dependent on reading)
                is_place = anchor.semantic_field.startswith("PLACE:")
                is_function = anchor.semantic_field.startswith("FUNCTION:")
                if not is_place and not is_function:
                    assert anchor.confidence <= 0.80, (
                        f"Damaged sign-group {anchor.sign_group_ids} has "
                        f"confidence={anchor.confidence:.2f} > 0.80 "
                        f"(semantic field: {anchor.semantic_field})"
                    )
