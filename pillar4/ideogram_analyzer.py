"""Ideogram co-occurrence analyzer for Pillar 4 (Semantic Anchoring).

Builds a sign-group x ideogram co-occurrence matrix and assigns semantic
fields based on exclusivity and Fisher's exact test.

PRD Section 5.1: For each sign-group, check whether a NAMED ideogram
(from GORILA -- must have "/" in reading) appears within
``adjacency_window`` sign positions.  Only named ideograms with
pictographic identification are considered communis opinio.

BIAS WARNING: Unknown logograms (A-series codes without "/" names) are
NOT treated as identified commodity ideograms.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from scipy.stats import fisher_exact  # type: ignore[import-untyped]

from pillar4.corpus_context_loader import (
    ContextCorpus,
    InscriptionContext,
    SignGroup,
    SignOccurrence,
)


# ---------------------------------------------------------------------------
# Ideogram -> semantic-field mapping (communis opinio only)
# ---------------------------------------------------------------------------

# Only named GORILA ideograms with pictographic identification.
# Sources: Evans, Bennett (via GORILA volumes).
IDEOGRAM_SEMANTIC_FIELDS: Dict[str, str] = {
    "AB30/FIC":    "COMMODITY:FIG",
    "AB120/GRA":   "COMMODITY:GRAIN",
    "AB120/GRAb":  "COMMODITY:GRAIN",
    "AB131/VIN":   "COMMODITY:WINE",
    "AB131/VINa":  "COMMODITY:WINE",
    "AB131/VINb":  "COMMODITY:WINE",
    "AB131/VINc":  "COMMODITY:WINE",
    "AB122/OLIV":  "COMMODITY:OLIVE",
    "AB100/VIR":   "PERSON",
    "AB21/OVIS":   "COMMODITY:SHEEP",
    "AB21/OVISf":  "COMMODITY:SHEEP",
    "AB21/OVISm":  "COMMODITY:SHEEP",
    "AB23/BOS":    "COMMODITY:CATTLE",
    "AB23/BOSm":   "COMMODITY:CATTLE",
    "AB22/CAP":    "COMMODITY:GOAT",
    "AB22/CAPf":   "COMMODITY:GOAT",
    "AB22/CAPm":   "COMMODITY:GOAT",
    "AB85/SUS":    "COMMODITY:PIG",
    "AB302/OLE":   "COMMODITY:OIL",
    "AB54/TELA":   "COMMODITY:TEXTILE",
    # A1001/SUS+SI is a composite -- map to PIG
    "A1001/SUS+SI": "COMMODITY:PIG",
}


def _get_semantic_field(ideogram_reading: str) -> Optional[str]:
    """Map an ideogram reading to its semantic field, or None if unknown."""
    return IDEOGRAM_SEMANTIC_FIELDS.get(ideogram_reading, None)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CoOccurrence:
    """A single sign-group x ideogram co-occurrence."""
    sign_group_ids: Tuple[str, ...]
    sign_group_transliteration: str
    ideogram_reading: str
    positional_relationship: str   # "immediately_adjacent" | "nearby" | "same_inscription"
    inscription_id: str


@dataclass
class SemanticFieldAssignment:
    """A sign-group assigned to a semantic field via ideogram co-occurrence.

    Attributes:
        sign_group_ids: Tuple of sign readings identifying the sign-group.
        transliterations: Set of transliteration strings seen for this group.
        semantic_field: Assigned semantic field (e.g. "COMMODITY:GRAIN").
        strongest_ideogram: The ideogram with highest exclusivity.
        co_occurrence_count: Number of co-occurrences with that ideogram.
        exclusivity: C[sg, ideo] / sum_over_all_ideo C[sg, .].
        fisher_p_value: Fisher's exact test p-value for enrichment.
        evidence_rating: "strong" if p < alpha and exclusivity > threshold,
            "suggestive" otherwise.
    """
    sign_group_ids: Tuple[str, ...]
    transliterations: Set[str]
    semantic_field: str
    strongest_ideogram: str
    co_occurrence_count: int
    exclusivity: float
    fisher_p_value: float
    evidence_rating: str


@dataclass
class IdeogramWordList:
    """Sign-groups co-occurring with a specific ideogram."""
    ideogram_reading: str
    semantic_field: Optional[str]
    sign_groups: List[Tuple[Tuple[str, ...], int]]  # (sign_group_ids, count)


@dataclass
class IdeogramAnalysisResult:
    """Complete result of ideogram co-occurrence analysis.

    PRD Section 5.1 output.

    Attributes:
        co_occurrence_matrix: Dict mapping (sign_group_ids, ideogram_reading)
            to count.
        semantic_field_assignments: Sign-groups with assigned semantic fields.
        per_ideogram_word_lists: For each ideogram, the list of co-occurring
            sign-groups.
        co_occurrences_raw: All individual co-occurrence records.
        n_named_ideograms_found: Count of distinct named ideograms in corpus.
        n_sign_groups_analyzed: Count of distinct sign-groups analyzed.
    """
    co_occurrence_matrix: Dict[Tuple[Tuple[str, ...], str], int]
    semantic_field_assignments: List[SemanticFieldAssignment]
    per_ideogram_word_lists: List[IdeogramWordList]
    co_occurrences_raw: List[CoOccurrence]
    n_named_ideograms_found: int = 0
    n_sign_groups_analyzed: int = 0


# ---------------------------------------------------------------------------
# Positional helpers
# ---------------------------------------------------------------------------

def _find_sign_group_positions(
    inscription: InscriptionContext,
    sign_group: SignGroup,
) -> List[int]:
    """Find plausible positions of a sign-group in the full sign sequence.

    Searches for a contiguous subsequence of readings matching the
    sign-group's sign_ids.  Returns starting positions (indices into
    full_sign_sequence).

    This is a best-effort alignment since the corpus words array and
    signs_sequence may not align perfectly due to damage markers.
    """
    target = sign_group.sign_ids
    if not target:
        return []

    seq = inscription.full_sign_sequence
    n = len(seq)
    tlen = len(target)
    positions: List[int] = []

    for start in range(n - tlen + 1):
        match = True
        for k in range(tlen):
            if seq[start + k].reading != target[k]:
                match = False
                break
        if match:
            positions.append(start)

    return positions


def _classify_relationship(
    sg_start: int,
    sg_end: int,
    ideo_pos: int,
    adjacency_window: int,
) -> str:
    """Classify the positional relationship between sign-group and ideogram.

    Returns:
        "immediately_adjacent" if ideogram is within 1 position of the group,
        "nearby" if within adjacency_window, or "same_inscription" otherwise.
    """
    # Distance from nearest edge of the sign-group
    if ideo_pos < sg_start:
        dist = sg_start - ideo_pos
    elif ideo_pos > sg_end:
        dist = ideo_pos - sg_end
    else:
        # Ideogram is inside the sign-group range (shouldn't happen
        # for named ideograms, but handle gracefully)
        dist = 0

    if dist <= 1:
        return "immediately_adjacent"
    elif dist <= adjacency_window:
        return "nearby"
    else:
        return "same_inscription"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_ideograms(
    corpus: ContextCorpus,
    adjacency_window: int = 3,
    min_co_occurrence: int = 2,
    min_exclusivity: float = 0.3,
    co_occurrence_alpha: float = 0.05,
) -> IdeogramAnalysisResult:
    """Build sign-group x ideogram co-occurrence matrix and assign fields.

    PRD Section 5.1 algorithm:

    For each sign-group in each inscription:
    1. Check if a NAMED ideogram (must have "/" in reading) appears within
       ``adjacency_window`` sign positions.
    2. Record co-occurrence with positional_relationship.
    3. Compute exclusivity and Fisher's exact test for enrichment.
    4. Assign semantic_field from highest-exclusivity ideogram (only if
       significant and above threshold).

    Args:
        corpus: Loaded ContextCorpus from corpus_context_loader.
        adjacency_window: Max sign positions between sign-group edge and
            ideogram for "nearby" classification.
        min_co_occurrence: Minimum co-occurrences for a pair to be
            considered.
        min_exclusivity: Minimum exclusivity score for semantic field
            assignment.
        co_occurrence_alpha: Significance threshold for Fisher's exact test.

    Returns:
        IdeogramAnalysisResult with co-occurrence matrix, semantic field
        assignments, and per-ideogram sign-group lists.
    """
    # Collect co-occurrences: (sign_group_ids, ideogram) -> list of records
    raw_co_occurrences: List[CoOccurrence] = []

    # Count matrix: (sign_group_ids, ideogram_reading) -> count
    co_count: Dict[Tuple[Tuple[str, ...], str], int] = defaultdict(int)

    # Track all sign-groups and ideograms seen
    all_sign_group_ids: Set[Tuple[str, ...]] = set()
    all_ideogram_readings: Set[str] = set()

    # Transliteration lookup
    sg_transliterations: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)

    # Total co-occurrence counts per sign-group (for exclusivity denominator)
    sg_total_co_occ: Dict[Tuple[str, ...], int] = defaultdict(int)

    # Total inscriptions containing each ideogram / sign-group
    # (for Fisher's test: need marginal counts)
    ideo_inscription_count: Dict[str, int] = defaultdict(int)
    sg_inscription_count: Dict[Tuple[str, ...], int] = defaultdict(int)
    n_inscriptions_total = corpus.n_inscriptions

    # Pre-count ideogram presence per inscription
    for insc in corpus.inscriptions:
        seen_ideos: Set[str] = set()
        for ideo_occ in insc.ideograms_in_sequence:
            seen_ideos.add(ideo_occ.reading)
        for r in seen_ideos:
            ideo_inscription_count[r] += 1

    for insc in corpus.inscriptions:
        if not insc.ideograms_in_sequence:
            # No named ideograms -> still count sign-groups for marginals
            for sg in insc.sign_groups:
                if sg.sign_ids:
                    all_sign_group_ids.add(sg.sign_ids)
                    sg_inscription_count[sg.sign_ids] += 1
                    sg_transliterations[sg.sign_ids].add(sg.transliteration)
            continue

        ideogram_positions = {
            occ.position_in_sequence: occ
            for occ in insc.ideograms_in_sequence
        }

        for sg in insc.sign_groups:
            if not sg.sign_ids:
                continue

            all_sign_group_ids.add(sg.sign_ids)
            sg_inscription_count[sg.sign_ids] += 1
            sg_transliterations[sg.sign_ids].add(sg.transliteration)

            # Find where this sign-group sits in the full sequence
            positions = _find_sign_group_positions(insc, sg)
            if not positions:
                # Can't locate in sequence; fall back to same_inscription
                for ideo_occ in insc.ideograms_in_sequence:
                    co_key = (sg.sign_ids, ideo_occ.reading)
                    co_count[co_key] += 1
                    sg_total_co_occ[sg.sign_ids] += 1
                    all_ideogram_readings.add(ideo_occ.reading)
                    raw_co_occurrences.append(CoOccurrence(
                        sign_group_ids=sg.sign_ids,
                        sign_group_transliteration=sg.transliteration,
                        ideogram_reading=ideo_occ.reading,
                        positional_relationship="same_inscription",
                        inscription_id=insc.id,
                    ))
                continue

            # Use the first match position
            sg_start = positions[0]
            sg_end = sg_start + len(sg.sign_ids) - 1

            for ideo_pos, ideo_occ in ideogram_positions.items():
                relationship = _classify_relationship(
                    sg_start, sg_end, ideo_pos, adjacency_window
                )

                # Only count if within window (not just same_inscription)
                # unless there is no other relationship available
                if relationship in ("immediately_adjacent", "nearby"):
                    co_key = (sg.sign_ids, ideo_occ.reading)
                    co_count[co_key] += 1
                    sg_total_co_occ[sg.sign_ids] += 1
                    all_ideogram_readings.add(ideo_occ.reading)
                    raw_co_occurrences.append(CoOccurrence(
                        sign_group_ids=sg.sign_ids,
                        sign_group_transliteration=sg.transliteration,
                        ideogram_reading=ideo_occ.reading,
                        positional_relationship=relationship,
                        inscription_id=insc.id,
                    ))

    # --- Compute exclusivity and Fisher's exact test ---
    semantic_assignments: List[SemanticFieldAssignment] = []
    per_ideogram_sgs: Dict[str, List[Tuple[Tuple[str, ...], int]]] = defaultdict(list)

    # For each sign-group, find its strongest ideogram
    for sg_ids in all_sign_group_ids:
        # Collect all ideograms this sign-group co-occurs with
        ideo_counts: Dict[str, int] = {}
        for ideo_r in all_ideogram_readings:
            c = co_count.get((sg_ids, ideo_r), 0)
            if c > 0:
                ideo_counts[ideo_r] = c

        if not ideo_counts:
            continue

        total_co = sg_total_co_occ.get(sg_ids, 0)
        if total_co == 0:
            continue

        # Find strongest ideogram by exclusivity
        best_ideo = None
        best_exclusivity = 0.0
        best_count = 0

        for ideo_r, c in ideo_counts.items():
            excl = c / total_co
            if excl > best_exclusivity or (
                excl == best_exclusivity and c > best_count
            ):
                best_exclusivity = excl
                best_ideo = ideo_r
                best_count = c

        if best_ideo is None or best_count < min_co_occurrence:
            continue

        # Fisher's exact test for enrichment
        # Contingency table:
        #   sg+ideo | sg+not_ideo
        #   not_sg+ideo | not_sg+not_ideo
        a = best_count  # inscriptions with both sg and ideo
        b = sg_inscription_count.get(sg_ids, 0) - a  # sg without ideo
        c_val = ideo_inscription_count.get(best_ideo, 0) - a  # ideo without sg
        d = n_inscriptions_total - a - b - c_val  # neither

        # Clamp negatives (can happen due to counting differences)
        b = max(b, 0)
        c_val = max(c_val, 0)
        d = max(d, 0)

        table = [[a, b], [c_val, d]]
        try:
            _, p_value = fisher_exact(table, alternative="greater")
        except ValueError:
            p_value = 1.0

        # Determine semantic field
        sem_field = _get_semantic_field(best_ideo)
        if sem_field is None:
            # Named ideogram without a mapped field -- skip assignment
            continue

        if best_exclusivity >= min_exclusivity and p_value < co_occurrence_alpha:
            evidence = "strong"
        elif best_exclusivity >= min_exclusivity or p_value < co_occurrence_alpha:
            evidence = "suggestive"
        else:
            continue  # Not enough evidence

        semantic_assignments.append(SemanticFieldAssignment(
            sign_group_ids=sg_ids,
            transliterations=sg_transliterations.get(sg_ids, set()),
            semantic_field=sem_field,
            strongest_ideogram=best_ideo,
            co_occurrence_count=best_count,
            exclusivity=best_exclusivity,
            fisher_p_value=p_value,
            evidence_rating=evidence,
        ))

    # Build per-ideogram word lists
    for ideo_r in sorted(all_ideogram_readings):
        sg_list: List[Tuple[Tuple[str, ...], int]] = []
        for sg_ids in all_sign_group_ids:
            c = co_count.get((sg_ids, ideo_r), 0)
            if c > 0:
                sg_list.append((sg_ids, c))
        sg_list.sort(key=lambda x: x[1], reverse=True)
        per_ideogram_sgs[ideo_r] = sg_list

    per_ideogram_word_lists = [
        IdeogramWordList(
            ideogram_reading=ideo_r,
            semantic_field=_get_semantic_field(ideo_r),
            sign_groups=sgs,
        )
        for ideo_r, sgs in sorted(per_ideogram_sgs.items())
    ]

    return IdeogramAnalysisResult(
        co_occurrence_matrix=dict(co_count),
        semantic_field_assignments=semantic_assignments,
        per_ideogram_word_lists=per_ideogram_word_lists,
        co_occurrences_raw=raw_co_occurrences,
        n_named_ideograms_found=len(all_ideogram_readings),
        n_sign_groups_analyzed=len(all_sign_group_ids),
    )
