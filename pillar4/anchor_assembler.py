"""Anchor assembler for Pillar 4 (Semantic Anchoring).

Combines evidence from all Pillar 4 analysis modules into a unified
anchor vocabulary.

PRD Section 5.5: For each sign-group in the corpus, gather evidence
from ideogram co-occurrence, transaction role, formula position, and
place name identification.  Compute confidence from the strongest
evidence source and assign a semantic field.  Only sign-groups exceeding
``min_anchor_confidence`` are included.

EVIDENCE HIERARCHY:
1. Place name identification (highest confidence -- communis opinio)
2. Ideogram co-occurrence (strong/suggestive based on Fisher's test)
3. ku-ro / transaction role (structural, lower confidence)
4. Formula position (frequency-based, lowest individual confidence)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from pillar4.ideogram_analyzer import (
    IdeogramAnalysisResult,
    SemanticFieldAssignment,
)
from pillar4.transaction_analyzer import (
    TransactionAnalysisResult,
    PositionalRole,
)
from pillar4.formula_mapper import (
    FormulaMapResult,
    FormulaElement,
)
from pillar4.place_name_finder import (
    PlaceNameResult,
    PlaceNameMatch,
    PhoneticAnchor,
)


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

# Base confidence by evidence source
_PLACE_NAME_BASE_CONFIDENCE = 0.85
_IDEOGRAM_STRONG_CONFIDENCE = 0.70
_IDEOGRAM_SUGGESTIVE_CONFIDENCE = 0.45
_TRANSACTION_ROLE_CONFIDENCE: Dict[str, float] = {
    "kuro_marker": 0.90,   # ku-ro = "total" is communis opinio
    "pre_numeral": 0.40,
    "pre_ideogram": 0.35,
    "post_numeral": 0.30,
    "pre_kuro": 0.35,
    "post_kuro": 0.30,
    "standalone": 0.05,
}
_FORMULA_FIXED_CONFIDENCE = 0.35
_FORMULA_SEMI_FIXED_CONFIDENCE = 0.20
_FORMULA_VARIABLE_CONFIDENCE = 0.05


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """A single piece of evidence for a sign-group's semantic anchoring.

    Attributes:
        source: Evidence source: "place_name", "ideogram_co_occurrence",
            "transaction_role", or "formula_position".
        confidence: Confidence score for this evidence (0-1).
        semantic_field: Semantic field suggested by this evidence, or None.
        detail: Human-readable description of the evidence.
    """
    source: str
    confidence: float
    semantic_field: Optional[str]
    detail: str


@dataclass
class AnchoredSignGroup:
    """A sign-group with assembled semantic evidence.

    Attributes:
        sign_group_ids: Tuple of sign readings identifying this group.
        transliterations: Set of transliteration strings.
        semantic_field: Best semantic field from strongest evidence.
        confidence: Overall confidence (max of individual evidence scores).
        evidence_chain: All evidence items, sorted by confidence descending.
        n_evidence_sources: Number of distinct evidence sources.
        phonetic_anchors: Phonetic anchors if this is a place name.
    """
    sign_group_ids: Tuple[str, ...]
    transliterations: Set[str]
    semantic_field: str
    confidence: float
    evidence_chain: List[EvidenceItem]
    n_evidence_sources: int = 0
    phonetic_anchors: List[PhoneticAnchor] = field(default_factory=list)


@dataclass
class AnchorVocabulary:
    """The complete anchor vocabulary for downstream analysis.

    PRD Section 5.5 output.

    Attributes:
        anchored_sign_groups: List of sign-groups with semantic fields
            and confidence above the minimum threshold.
        all_evidence: Dict mapping sign_group_ids to all evidence items
            (including those below threshold, for transparency).
        n_total_sign_groups: Total sign-groups in the corpus.
        n_anchored: Count of sign-groups meeting the confidence threshold.
        n_by_source: Count of sign-groups with evidence from each source.
        min_confidence_used: The threshold applied.
    """
    anchored_sign_groups: List[AnchoredSignGroup]
    all_evidence: Dict[Tuple[str, ...], List[EvidenceItem]]
    n_total_sign_groups: int = 0
    n_anchored: int = 0
    n_by_source: Dict[str, int] = field(default_factory=dict)
    min_confidence_used: float = 0.3


# ---------------------------------------------------------------------------
# Evidence collection
# ---------------------------------------------------------------------------

def _collect_place_name_evidence(
    place_name_result: PlaceNameResult,
) -> Dict[Tuple[str, ...], List[EvidenceItem]]:
    """Collect evidence from place name identification."""
    evidence: Dict[Tuple[str, ...], List[EvidenceItem]] = defaultdict(list)

    for match in place_name_result.found:
        sg_ids = tuple(match.target_readings)

        # Adjust confidence based on site match
        conf = match.confidence
        if match.site_matches_expected:
            # Site provenance corroborates identification
            conf = min(conf * 1.05, 1.0)

        detail = (
            f"Place name '{match.name}' identified in {match.inscription_id} "
            f"at site {match.site}."
        )
        if match.site_matches_expected:
            detail += " Site matches expected location."

        evidence[sg_ids].append(EvidenceItem(
            source="place_name",
            confidence=max(conf, _PLACE_NAME_BASE_CONFIDENCE),
            semantic_field=f"PLACE:{match.name.upper().replace(' ', '_')}",
            detail=f"{detail} Source: {match.source}",
        ))

    return evidence


def _collect_ideogram_evidence(
    ideogram_result: IdeogramAnalysisResult,
) -> Dict[Tuple[str, ...], List[EvidenceItem]]:
    """Collect evidence from ideogram co-occurrence analysis."""
    evidence: Dict[Tuple[str, ...], List[EvidenceItem]] = defaultdict(list)

    for assignment in ideogram_result.semantic_field_assignments:
        if assignment.evidence_rating == "strong":
            conf = _IDEOGRAM_STRONG_CONFIDENCE
        else:
            conf = _IDEOGRAM_SUGGESTIVE_CONFIDENCE

        # Scale by exclusivity
        conf = conf * min(assignment.exclusivity / 0.5, 1.0)
        conf = max(conf, 0.1)

        translits = ", ".join(sorted(assignment.transliterations))
        detail = (
            f"Co-occurs with {assignment.strongest_ideogram} "
            f"({assignment.co_occurrence_count}x, "
            f"exclusivity={assignment.exclusivity:.2f}, "
            f"Fisher p={assignment.fisher_p_value:.4f}). "
            f"Evidence: {assignment.evidence_rating}. "
            f"Transliterations: {translits}"
        )

        evidence[assignment.sign_group_ids].append(EvidenceItem(
            source="ideogram_co_occurrence",
            confidence=conf,
            semantic_field=assignment.semantic_field,
            detail=detail,
        ))

    return evidence


def _collect_transaction_evidence(
    transaction_result: TransactionAnalysisResult,
) -> Dict[Tuple[str, ...], List[EvidenceItem]]:
    """Collect evidence from transaction / numeral analysis."""
    evidence: Dict[Tuple[str, ...], List[EvidenceItem]] = defaultdict(list)

    # Aggregate roles per sign-group (keep highest confidence role)
    sg_roles: Dict[Tuple[str, ...], Dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    sg_translits: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)

    for role in transaction_result.positional_role_assignments:
        sg_roles[role.sign_group_ids][role.role] += 1
        sg_translits[role.sign_group_ids].add(role.transliteration)

    for sg_ids, role_counts in sg_roles.items():
        # Pick the most frequent non-standalone role
        best_role = "standalone"
        best_count = 0
        for role, count in role_counts.items():
            if role == "standalone":
                continue
            if count > best_count:
                best_role = role
                best_count = count

        conf = _TRANSACTION_ROLE_CONFIDENCE.get(best_role, 0.05)

        # Scale by evidence count
        if best_count >= 3:
            conf = min(conf * 1.2, 0.95)
        elif best_count >= 2:
            conf = min(conf * 1.1, 0.90)

        if best_role == "standalone" and best_count == 0:
            continue

        # Determine semantic field from role
        if best_role == "kuro_marker":
            sem_field = "FUNCTION:TOTAL_MARKER"
        elif best_role in ("pre_numeral", "pre_ideogram"):
            sem_field = "TRANSACTION:ENTITY"
        elif best_role in ("pre_kuro", "post_kuro"):
            sem_field = "TRANSACTION:PARTICIPANT"
        elif best_role == "post_numeral":
            sem_field = "TRANSACTION:MODIFIER"
        else:
            sem_field = None

        translits = ", ".join(sorted(sg_translits.get(sg_ids, set())))
        detail = (
            f"Transaction role: {best_role} "
            f"({best_count}x across inscriptions). "
            f"Transliterations: {translits}"
        )

        evidence[sg_ids].append(EvidenceItem(
            source="transaction_role",
            confidence=conf,
            semantic_field=sem_field,
            detail=detail,
        ))

    return evidence


def _collect_formula_evidence(
    formula_result: FormulaMapResult,
) -> Dict[Tuple[str, ...], List[EvidenceItem]]:
    """Collect evidence from libation formula mapping."""
    evidence: Dict[Tuple[str, ...], List[EvidenceItem]] = defaultdict(list)

    for element in formula_result.elements:
        if element.classification == "fixed_element":
            conf = _FORMULA_FIXED_CONFIDENCE
            sem_field = f"FORMULA:FIXED_{element.typical_position.upper()}"
        elif element.classification == "semi_fixed_element":
            conf = _FORMULA_SEMI_FIXED_CONFIDENCE
            sem_field = f"FORMULA:SEMI_FIXED_{element.typical_position.upper()}"
        else:
            # Variable elements are too common to be useful anchors
            conf = _FORMULA_VARIABLE_CONFIDENCE
            sem_field = None

        # Scale by frequency rate
        conf = conf * min(element.frequency_rate / 0.10, 2.0)
        conf = min(conf, 0.60)

        translits = ", ".join(sorted(element.transliterations))
        detail = (
            f"Libation formula {element.classification}: "
            f"appears in {element.frequency_count}/{formula_result.n_libation_inscriptions} "
            f"({element.frequency_rate:.1%}). "
            f"Position: {element.typical_position}. "
            f"Transliterations: {translits}"
        )

        evidence[element.sign_group_ids].append(EvidenceItem(
            source="formula_position",
            confidence=conf,
            semantic_field=sem_field,
            detail=detail,
        ))

    return evidence


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def assemble_anchors(
    ideogram_result: Optional[IdeogramAnalysisResult] = None,
    transaction_result: Optional[TransactionAnalysisResult] = None,
    formula_result: Optional[FormulaMapResult] = None,
    place_name_result: Optional[PlaceNameResult] = None,
    min_anchor_confidence: float = 0.3,
) -> AnchorVocabulary:
    """Combine all evidence into an anchor vocabulary.

    PRD Section 5.5: For each sign-group, gather evidence from all
    sources, compute confidence = max of individual scores, assign
    semantic field from strongest evidence, and include only those
    above min_anchor_confidence.

    Args:
        ideogram_result: Output from ideogram_analyzer.
        transaction_result: Output from transaction_analyzer.
        formula_result: Output from formula_mapper.
        place_name_result: Output from place_name_finder.
        min_anchor_confidence: Minimum confidence for inclusion.

    Returns:
        AnchorVocabulary with anchored sign-groups, evidence chains,
        and summary statistics.
    """
    # Collect all evidence into one dict
    all_evidence: Dict[Tuple[str, ...], List[EvidenceItem]] = defaultdict(list)

    if place_name_result is not None:
        for sg_ids, items in _collect_place_name_evidence(
            place_name_result
        ).items():
            all_evidence[sg_ids].extend(items)

    if ideogram_result is not None:
        for sg_ids, items in _collect_ideogram_evidence(
            ideogram_result
        ).items():
            all_evidence[sg_ids].extend(items)

    if transaction_result is not None:
        for sg_ids, items in _collect_transaction_evidence(
            transaction_result
        ).items():
            all_evidence[sg_ids].extend(items)

    if formula_result is not None:
        for sg_ids, items in _collect_formula_evidence(
            formula_result
        ).items():
            all_evidence[sg_ids].extend(items)

    # Collect transliterations from all sources
    sg_transliterations: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)

    if ideogram_result is not None:
        for assignment in ideogram_result.semantic_field_assignments:
            sg_transliterations[assignment.sign_group_ids].update(
                assignment.transliterations
            )

    if formula_result is not None:
        for element in formula_result.elements:
            sg_transliterations[element.sign_group_ids].update(
                element.transliterations
            )

    if transaction_result is not None:
        for role in transaction_result.positional_role_assignments:
            sg_transliterations[role.sign_group_ids].add(role.transliteration)

    if place_name_result is not None:
        for match in place_name_result.found:
            sg_ids = tuple(match.target_readings)
            # Use the place name sign sequence as transliteration
            translit = "-".join(match.target_readings)
            sg_transliterations[sg_ids].add(translit)

    # Phonetic anchors from place names
    place_name_phonetic: Dict[Tuple[str, ...], List[PhoneticAnchor]] = (
        defaultdict(list)
    )
    if place_name_result is not None:
        for match in place_name_result.found:
            sg_ids = tuple(match.target_readings)
            for anchor in place_name_result.phonetic_anchors:
                if anchor.from_place_name == match.name:
                    if anchor not in place_name_phonetic[sg_ids]:
                        place_name_phonetic[sg_ids].append(anchor)

    # Build anchored sign-groups
    anchored: List[AnchoredSignGroup] = []
    n_by_source: Dict[str, int] = defaultdict(int)
    n_total = len(all_evidence)

    for sg_ids, items in all_evidence.items():
        # Sort by confidence descending
        items.sort(key=lambda e: e.confidence, reverse=True)

        # Overall confidence = max of individual scores
        max_conf = max(item.confidence for item in items)

        # Semantic field from strongest evidence
        best_field: Optional[str] = None
        for item in items:
            if item.semantic_field is not None:
                best_field = item.semantic_field
                break

        if max_conf < min_anchor_confidence:
            continue

        if best_field is None:
            # No semantic field assignable even from best evidence
            continue

        # Count distinct sources
        sources = set(item.source for item in items)

        for source in sources:
            n_by_source[source] += 1

        anchored.append(AnchoredSignGroup(
            sign_group_ids=sg_ids,
            transliterations=sg_transliterations.get(sg_ids, set()),
            semantic_field=best_field,
            confidence=max_conf,
            evidence_chain=items,
            n_evidence_sources=len(sources),
            phonetic_anchors=place_name_phonetic.get(sg_ids, []),
        ))

    # Sort by confidence descending
    anchored.sort(key=lambda a: a.confidence, reverse=True)

    return AnchorVocabulary(
        anchored_sign_groups=anchored,
        all_evidence=dict(all_evidence),
        n_total_sign_groups=n_total,
        n_anchored=len(anchored),
        n_by_source=dict(n_by_source),
        min_confidence_used=min_anchor_confidence,
    )
