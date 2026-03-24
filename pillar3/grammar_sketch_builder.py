"""Grammar sketch synthesis from all Pillar 3 analysis outputs.

PRD Section 5 (final synthesis): Combines word class induction, word order
analysis, agreement detection, and functional word identification into a
coherent grammar sketch describing the typological profile of the script.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .word_class_inducer import WordClassResult
from .word_order_analyzer import WordOrderResult
from .agreement_detector import AgreementResult
from .functional_word_finder import FunctionalWordResult
from .data_loader import Pillar2Data


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class GrammarSketch:
    """Synthesised grammar sketch for the script.

    Attributes:
        is_inflected: Whether > 50% of stems are declining (from P2 word classes).
        estimated_word_classes: Number of distributional word classes induced.
        word_order_type: Dominant word-order type or "inconclusive".
        has_agreement: Whether any significant agreement patterns were found.
        n_functional_words: Number of identified functional words.
        summary: 1-2 sentence natural-language summary.
        details: Additional diagnostic details for downstream inspection.
    """
    is_inflected: bool
    estimated_word_classes: int
    word_order_type: str
    has_agreement: bool
    n_functional_words: int
    summary: str
    details: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_grammar_sketch(
    word_classes: WordClassResult,
    word_order: WordOrderResult,
    agreement: AgreementResult,
    functional_words: FunctionalWordResult,
    pillar2: Pillar2Data,
) -> GrammarSketch:
    """Synthesise all Pillar 3 outputs into a grammar sketch.

    Args:
        word_classes: Induced word classes from word_class_inducer.
        word_order: Word order analysis from word_order_analyzer.
        agreement: Agreement detection from agreement_detector.
        functional_words: Functional word identification from functional_word_finder.
        pillar2: Pillar 2 data for morphological word class proportions.

    Returns:
        GrammarSketch summarising the typological profile.
    """
    # --- is_inflected: > 50% of stems are declining ---
    total_stems = 0
    declining_stems = 0
    for mc in pillar2.morphological_word_classes:
        total_stems += mc.n_stems
        if mc.label == "declining":
            declining_stems += mc.n_stems
    is_inflected = (declining_stems / total_stems > 0.5) if total_stems > 0 else False

    # --- estimated_word_classes ---
    estimated_word_classes = word_classes.n_classes

    # --- word_order_type ---
    word_order_type = _determine_word_order_type(word_order)

    # --- has_agreement ---
    has_agreement = agreement.n_pairs_significant > 0

    # --- n_functional_words ---
    n_functional_words = functional_words.n_functional

    # --- summary ---
    summary = _build_summary(
        is_inflected, estimated_word_classes, word_order_type,
        has_agreement, n_functional_words, word_classes,
    )

    # --- details ---
    details: Dict[str, Any] = {
        "declining_stem_fraction": round(
            declining_stems / total_stems, 3
        ) if total_stems > 0 else 0.0,
        "total_stems": total_stems,
        "declining_stems": declining_stems,
        "silhouette_score": round(word_classes.silhouette, 3),
        "n_significant_word_orders": sum(
            1 for po in word_order.pairwise_orders if po.p_value < 0.05
        ),
        "n_agreement_patterns": agreement.n_pairs_significant,
        "expected_agreement_rate": agreement.expected_rate,
        "functional_word_classifications": _count_classifications(
            functional_words
        ),
    }

    return GrammarSketch(
        is_inflected=is_inflected,
        estimated_word_classes=estimated_word_classes,
        word_order_type=word_order_type,
        has_agreement=has_agreement,
        n_functional_words=n_functional_words,
        summary=summary,
        details=details,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _determine_word_order_type(word_order: WordOrderResult) -> str:
    """Determine dominant word-order type from pairwise direction ratios.

    If any pair has a significant direction ratio (p < 0.05) with ratio > 2.0,
    report a tentative ordering.  Otherwise "inconclusive".
    """
    significant_pairs = [
        po for po in word_order.pairwise_orders
        if po.p_value < 0.05 and po.direction_ratio > 2.0
    ]
    if not significant_pairs:
        return "inconclusive"

    # Find the pair with the strongest direction ratio
    best = max(significant_pairs, key=lambda p: p.direction_ratio)

    # Check positional stats: which class tends to be earlier?
    pos_map = {ps.class_id: ps.mean_relative_position
               for ps in word_order.position_stats}

    pos_a = pos_map.get(best.class_a, 0.5)
    pos_b = pos_map.get(best.class_b, 0.5)

    if pos_a < pos_b:
        return f"class_{best.class_a}_before_class_{best.class_b}"
    elif pos_b < pos_a:
        return f"class_{best.class_b}_before_class_{best.class_a}"
    else:
        return "weakly_ordered"


def _build_summary(
    is_inflected: bool,
    n_classes: int,
    word_order_type: str,
    has_agreement: bool,
    n_functional: int,
    word_classes: WordClassResult,
) -> str:
    """Build a 1-2 sentence natural-language summary."""
    parts: List[str] = []

    if is_inflected:
        parts.append(
            f"The script appears inflectional with {n_classes} distributional "
            f"word classes (silhouette={word_classes.silhouette:.2f})."
        )
    else:
        parts.append(
            f"The script shows limited inflection with {n_classes} distributional "
            f"word classes (silhouette={word_classes.silhouette:.2f})."
        )

    order_part = ""
    if word_order_type == "inconclusive":
        order_part = "No strong word-order preferences were detected"
    else:
        order_part = f"A tentative ordering pattern was found ({word_order_type})"

    agreement_part = ""
    if has_agreement:
        agreement_part = "with significant suffix agreement between adjacent words"
    else:
        agreement_part = "with no significant suffix agreement detected"

    func_part = f"{n_functional} functional words identified" if n_functional > 0 else "no functional words identified"

    parts.append(f"{order_part}, {agreement_part}; {func_part}.")

    return " ".join(parts)


def _count_classifications(
    functional_words: FunctionalWordResult,
) -> Dict[str, int]:
    """Count functional words by classification type."""
    counts: Dict[str, int] = {}
    for fw in functional_words.functional_words:
        counts[fw.classification] = counts.get(fw.classification, 0) + 1
    return counts
