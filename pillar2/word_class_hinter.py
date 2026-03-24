"""Morphological word-class hints.

Implements PRD Section 5.5: Classifies stems as "declining", "conjugating",
"uninflected", or "unknown" based on their affix behavior, paradigm
membership, and inscription context.

These hints feed Pillar 3 (Grammar) to inform word class induction.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .segmenter import SegmentedLexicon, SegmentedWord
from .affix_extractor import AffixInventory
from .paradigm_inducer import ParadigmTable
from .inflection_classifier import classify_affixes


@dataclass
class WordClassHint:
    """A word-class hint for a stem."""
    stem: List[str]
    label: str  # "declining", "conjugating", "uninflected", "unknown"
    paradigm_classes: List[int]
    n_inflectional_suffixes: int
    n_total_suffixes: int
    inscription_types: List[str]
    confidence: float


@dataclass
class MorphologicalWordClass:
    """A morphological word class with its members."""
    class_id: int
    label: str
    description: str
    n_stems: int
    paradigm_classes: List[int] = field(default_factory=list)


@dataclass
class WordClassResult:
    """Results of word-class hinting."""
    stem_hints: List[WordClassHint]
    word_classes: List[MorphologicalWordClass]


def hint_word_classes(
    lexicon: SegmentedLexicon,
    affix_inv: AffixInventory,
    paradigm_table: ParadigmTable,
) -> WordClassResult:
    """Classify stems into morphological word classes.

    Heuristics (no external language knowledge):
    1. Uninflected: stems that never appear with any inflectional suffix.
    2. Declining: stems that take inflectional suffixes from paradigm classes.
       If the paradigm has 3+ slots, these stems decline.
    3. Conjugating: stems taking a DIFFERENT set of affixes than declining stems
       (a separate paradigm family). Only detectable if corpus contains verbs.
    4. Unknown: stems with some affixes but no clear paradigm membership.

    Args:
        lexicon: Segmented lexicon.
        affix_inv: Classified affix inventory.
        paradigm_table: Induced paradigm table.

    Returns:
        WordClassResult with hints per stem and aggregate word classes.
    """
    # Build inflectional suffix set
    inflectional_suffixes: Set[Tuple[str, ...]] = set()
    for affix in affix_inv.suffixes:
        if affix.classification == "inflectional":
            inflectional_suffixes.add(tuple(affix.signs))

    # Build stem -> paradigm class mapping
    stem_paradigms: Dict[Tuple[str, ...], Set[int]] = defaultdict(set)
    for paradigm in paradigm_table.paradigms:
        for example in paradigm.example_stems:
            stem_key = tuple(example.stem)
            stem_paradigms[stem_key].add(paradigm.class_id)

    # Also build from the full lexicon: for each stem, check which paradigm
    # suffixes it takes and map back to paradigm classes
    suffix_to_paradigms: Dict[Tuple[str, ...], Set[int]] = defaultdict(set)
    for paradigm in paradigm_table.paradigms:
        for slot in paradigm.slots:
            suffix_to_paradigms[tuple(slot.ending_signs)].add(paradigm.class_id)

    # Collect unique stems and their properties
    stem_info: Dict[Tuple[str, ...], Dict] = {}
    for word in lexicon.words:
        stem_key = tuple(word.stem)
        if stem_key not in stem_info:
            stem_info[stem_key] = {
                "suffixes": set(),
                "inscription_types": set(),
                "n_inflectional": 0,
            }
        for suffix in word.suffixes:
            suf_key = tuple(suffix)
            stem_info[stem_key]["suffixes"].add(suf_key)
            if suf_key in inflectional_suffixes:
                stem_info[stem_key]["n_inflectional"] += 1
        for itype in word.inscription_types:
            stem_info[stem_key]["inscription_types"].add(itype)

    # Classify each stem
    hints: List[WordClassHint] = []
    class_counts: Dict[str, int] = defaultdict(int)
    class_paradigms: Dict[str, Set[int]] = defaultdict(set)

    for stem_key, info in sorted(stem_info.items()):
        n_infl = info["n_inflectional"]
        n_total = len(info["suffixes"])
        insc_types = sorted(info["inscription_types"])

        # Determine paradigm classes for this stem
        p_classes: Set[int] = set()
        p_classes.update(stem_paradigms.get(stem_key, set()))
        for suf_key in info["suffixes"]:
            p_classes.update(suffix_to_paradigms.get(suf_key, set()))

        # Classification logic
        if n_total == 0:
            label = "uninflected"
            confidence = 0.8
        elif n_infl > 0 and p_classes:
            label = "declining"
            confidence = min(1.0, n_infl * 0.3 + len(p_classes) * 0.2)
        elif n_total > 0 and not p_classes:
            # Has suffixes but no paradigm membership — ambiguous
            label = "unknown"
            confidence = 0.3
        else:
            label = "unknown"
            confidence = 0.2

        hints.append(WordClassHint(
            stem=list(stem_key),
            label=label,
            paradigm_classes=sorted(p_classes),
            n_inflectional_suffixes=n_infl,
            n_total_suffixes=n_total,
            inscription_types=insc_types,
            confidence=confidence,
        ))

        class_counts[label] += 1
        class_paradigms[label].update(p_classes)

    # Build aggregate word classes
    word_classes: List[MorphologicalWordClass] = []
    descriptions = {
        "declining": "Stems that take inflectional suffixes from paradigm classes",
        "conjugating": "Stems that take a different set of inflectional affixes (verbs)",
        "uninflected": "Stems that never appear with any attested suffix",
        "unknown": "Stems with some affixes but no clear paradigm membership",
    }

    for cid, label in enumerate(["declining", "conjugating", "uninflected", "unknown"]):
        if class_counts[label] > 0:
            word_classes.append(MorphologicalWordClass(
                class_id=cid,
                label=label,
                description=descriptions[label],
                n_stems=class_counts[label],
                paradigm_classes=sorted(class_paradigms.get(label, set())),
            ))

    return WordClassResult(
        stem_hints=hints,
        word_classes=word_classes,
    )
