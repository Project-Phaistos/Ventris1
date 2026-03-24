"""Formula mapping for Pillar 4 (Semantic Anchoring).

Maps libation formula variants with BIAS-FREE labels only.

PRD Section 5.3: Collect libation inscriptions, compute sign-group
frequency rates, and classify elements as fixed/semi_fixed/variable
based solely on frequency thresholds.

BIAS-FREE LABELLING:
- "fixed_element": sign-group appearing in >= fixed_element_threshold
  of libation inscriptions
- "variable_element": sign-group appearing in < variable_element_threshold
- "semi_fixed_element": between the two thresholds
- NO labels like "deity", "verb", "offering", "dedicant"
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from pillar4.corpus_context_loader import (
    ContextCorpus,
    InscriptionContext,
    SignGroup,
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FormulaElement:
    """A sign-group element of the libation formula.

    BIAS-FREE: classified purely by frequency, not by assumed linguistic
    function.

    Attributes:
        sign_group_ids: Tuple of sign readings identifying this element.
        transliterations: Set of observed transliteration strings.
        frequency_count: Number of libation inscriptions containing this
            element.
        frequency_rate: fraction of libation inscriptions containing it.
        classification: "fixed_element", "semi_fixed_element", or
            "variable_element" — based solely on frequency thresholds.
        typical_position: "early", "middle", "late", or "varied" — based
            on the modal position in the inscription.  Only computed for
            fixed/semi_fixed elements.
        position_distribution: Fraction of occurrences in each third of
            the inscription (early/middle/late).
        inscriptions_found_in: Set of inscription IDs where this element
            appears.
    """
    sign_group_ids: Tuple[str, ...]
    transliterations: Set[str]
    frequency_count: int
    frequency_rate: float
    classification: str   # "fixed_element" | "semi_fixed_element" | "variable_element"
    typical_position: str  # "early" | "middle" | "late" | "varied"
    position_distribution: Dict[str, float] = field(default_factory=dict)
    inscriptions_found_in: Set[str] = field(default_factory=set)


@dataclass
class FormulaTemplate:
    """A template showing slot positions in the libation formula.

    Slots are ordered by typical position and contain the fixed/semi_fixed
    elements that fill them.

    Attributes:
        slots: Ordered list of (position_label, list_of_elements).
            Position labels are "early", "middle", "late".
        n_libation_inscriptions: Total libation inscriptions analyzed.
        template_coverage: Fraction of libation inscriptions that have
            at least one fixed element.
    """
    slots: List[Tuple[str, List[FormulaElement]]]
    n_libation_inscriptions: int
    template_coverage: float


@dataclass
class FormulaMapResult:
    """Complete result of formula analysis.

    PRD Section 5.3 output.

    Attributes:
        elements: All sign-group elements with frequency data and
            classifications.
        template: Slot-based formula template from fixed/semi_fixed
            elements.
        frequency_table: Dict mapping sign_group_ids to frequency_rate.
        n_libation_inscriptions: Count of libation inscriptions analyzed.
        n_fixed_elements: Count of fixed elements found.
        n_semi_fixed_elements: Count of semi-fixed elements found.
        n_variable_elements: Count of variable elements found.
    """
    elements: List[FormulaElement]
    template: FormulaTemplate
    frequency_table: Dict[Tuple[str, ...], float]
    n_libation_inscriptions: int = 0
    n_fixed_elements: int = 0
    n_semi_fixed_elements: int = 0
    n_variable_elements: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_libation_inscription(
    inscription: InscriptionContext,
    libation_types: List[str],
) -> bool:
    """Check if an inscription is a libation inscription.

    Matches the inscription type against the configured list (case-
    insensitive comparison as a fallback, but tries exact match first).
    """
    insc_type = inscription.type
    if insc_type in libation_types:
        return True
    # Case-insensitive fallback
    insc_lower = insc_type.lower().replace(" ", "_")
    for lt in libation_types:
        if lt.lower().replace(" ", "_") == insc_lower:
            return True
    return False


def _compute_position_label(
    position: int,
    total: int,
) -> str:
    """Classify a sign-group position as early/middle/late.

    Divides the inscription into thirds:
    - early: first third
    - middle: middle third
    - late: last third
    """
    if total <= 1:
        return "early"
    relative = position / (total - 1)
    if relative < 1 / 3:
        return "early"
    elif relative < 2 / 3:
        return "middle"
    else:
        return "late"


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def map_formulas(
    corpus: ContextCorpus,
    libation_inscription_types: Optional[List[str]] = None,
    fixed_element_threshold: float = 0.20,
    variable_element_threshold: float = 0.05,
) -> FormulaMapResult:
    """Map libation formula variants with bias-free labels.

    PRD Section 5.3 algorithm:

    1. Collect all libation inscriptions (types matching config).
    2. For each sign-group, count how many libation inscriptions it
       appears in.
    3. Compute frequency_rate = count / n_libation_inscriptions.
    4. Classify: fixed (>= threshold), variable (< lower threshold),
       semi_fixed (between).
    5. For fixed elements, record typical position (early/middle/late).
    6. Build a template showing slot positions.

    Args:
        corpus: Loaded ContextCorpus.
        libation_inscription_types: Inscription type strings to match
            (default: common libation types).
        fixed_element_threshold: Frequency rate above which an element
            is "fixed_element".
        variable_element_threshold: Frequency rate below which an element
            is "variable_element".

    Returns:
        FormulaMapResult with elements, template, and frequency table.
    """
    if libation_inscription_types is None:
        libation_inscription_types = [
            "libation_table",
            "libation table",
            "Libation table",
            "libation_table_corpus",
            "libation table fragment",
            "libation ladle",
        ]

    # Step 1: Collect libation inscriptions
    libation_inscriptions: List[InscriptionContext] = [
        insc for insc in corpus.inscriptions
        if _is_libation_inscription(insc, libation_inscription_types)
    ]
    n_lib = len(libation_inscriptions)

    if n_lib == 0:
        return FormulaMapResult(
            elements=[],
            template=FormulaTemplate(
                slots=[], n_libation_inscriptions=0, template_coverage=0.0
            ),
            frequency_table={},
        )

    # Step 2: Count sign-group occurrences across libation inscriptions
    # Use sign_group_ids as key; track transliterations and positions
    sg_inscription_sets: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    sg_transliterations: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    sg_positions: Dict[Tuple[str, ...], List[Tuple[int, int]]] = defaultdict(list)

    for insc in libation_inscriptions:
        n_sgs = insc.n_sign_groups
        for sg in insc.sign_groups:
            if not sg.sign_ids:
                continue
            sg_inscription_sets[sg.sign_ids].add(insc.id)
            sg_transliterations[sg.sign_ids].add(sg.transliteration)
            sg_positions[sg.sign_ids].append(
                (sg.position_in_inscription, n_sgs)
            )

    # Step 3-4: Classify elements
    elements: List[FormulaElement] = []
    frequency_table: Dict[Tuple[str, ...], float] = {}

    for sg_ids, insc_set in sg_inscription_sets.items():
        count = len(insc_set)
        rate = count / n_lib
        frequency_table[sg_ids] = rate

        if rate >= fixed_element_threshold:
            classification = "fixed_element"
        elif rate < variable_element_threshold:
            classification = "variable_element"
        else:
            classification = "semi_fixed_element"

        # Step 5: Compute position distribution for fixed/semi_fixed
        pos_counts: Dict[str, int] = Counter()
        for pos, total in sg_positions[sg_ids]:
            label = _compute_position_label(pos, total)
            pos_counts[label] += 1
        n_pos = sum(pos_counts.values())
        pos_dist = {
            k: v / n_pos for k, v in pos_counts.items()
        } if n_pos > 0 else {}

        # Determine typical position
        if pos_dist:
            max_label = max(pos_dist, key=pos_dist.get)  # type: ignore[arg-type]
            max_frac = pos_dist[max_label]
            if max_frac >= 0.5:
                typical_position = max_label
            else:
                typical_position = "varied"
        else:
            typical_position = "varied"

        elements.append(FormulaElement(
            sign_group_ids=sg_ids,
            transliterations=sg_transliterations[sg_ids],
            frequency_count=count,
            frequency_rate=rate,
            classification=classification,
            typical_position=typical_position,
            position_distribution=pos_dist,
            inscriptions_found_in=insc_set,
        ))

    # Sort by frequency (descending)
    elements.sort(key=lambda e: e.frequency_rate, reverse=True)

    # Step 6: Build template
    fixed_or_semi = [
        e for e in elements
        if e.classification in ("fixed_element", "semi_fixed_element")
    ]

    # Group by typical position
    early_elements = [e for e in fixed_or_semi if e.typical_position == "early"]
    middle_elements = [e for e in fixed_or_semi if e.typical_position == "middle"]
    late_elements = [e for e in fixed_or_semi if e.typical_position == "late"]
    varied_elements = [e for e in fixed_or_semi if e.typical_position == "varied"]

    slots: List[Tuple[str, List[FormulaElement]]] = []
    if early_elements:
        slots.append(("early", early_elements))
    if middle_elements:
        slots.append(("middle", middle_elements))
    if late_elements:
        slots.append(("late", late_elements))
    if varied_elements:
        slots.append(("varied", varied_elements))

    # Template coverage: fraction of libation inscriptions with >= 1 fixed element
    inscriptions_with_fixed = set()
    for e in elements:
        if e.classification == "fixed_element":
            inscriptions_with_fixed.update(e.inscriptions_found_in)
    template_coverage = len(inscriptions_with_fixed) / n_lib if n_lib > 0 else 0.0

    template = FormulaTemplate(
        slots=slots,
        n_libation_inscriptions=n_lib,
        template_coverage=template_coverage,
    )

    return FormulaMapResult(
        elements=elements,
        template=template,
        frequency_table=frequency_table,
        n_libation_inscriptions=n_lib,
        n_fixed_elements=sum(
            1 for e in elements if e.classification == "fixed_element"
        ),
        n_semi_fixed_elements=sum(
            1 for e in elements if e.classification == "semi_fixed_element"
        ),
        n_variable_elements=sum(
            1 for e in elements if e.classification == "variable_element"
        ),
    )
