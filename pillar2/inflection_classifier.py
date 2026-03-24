"""Inflection vs. derivation classification for affixes.

Implements PRD Section 5.4: Scores each affix on productivity and
paradigm regularity to classify it as inflectional, derivational,
or ambiguous.

Classification rules:
- productivity > inflectional_threshold AND paradigm_regular -> "inflectional"
- productivity < derivational_threshold OR not paradigm_regular -> "derivational"
- Otherwise -> "ambiguous"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .affix_extractor import AffixInventory, Affix
from .paradigm_inducer import ParadigmTable


@dataclass
class ClassifiedAffix:
    """An affix with its inflection/derivation classification."""
    signs: List[str]
    frequency: int
    n_distinct_stems: int
    productivity: float
    classification: str  # "inflectional", "derivational", "ambiguous"
    paradigm_classes: List[int]
    paradigm_regular: bool
    freq_type_ratio: float


def classify_affixes(
    affix_inv: AffixInventory,
    paradigm_table: ParadigmTable,
    inflectional_threshold: float = 0.3,
    derivational_threshold: float = 0.1,
) -> AffixInventory:
    """Classify all affixes as inflectional, derivational, or ambiguous.

    Updates the classification field on each Affix in the inventory.

    Args:
        affix_inv: The affix inventory to classify.
        paradigm_table: The paradigm table for regularity checking.
        inflectional_threshold: Productivity above this = inflectional candidate.
        derivational_threshold: Productivity below this = derivational.

    Returns:
        The same AffixInventory with classification fields updated.
    """
    # Build set of paradigm-regular suffixes:
    # A suffix is paradigm-regular if it fills a consistent slot in at
    # least one paradigm class.
    paradigm_suffix_keys = set()
    for paradigm in paradigm_table.paradigms:
        for slot in paradigm.slots:
            paradigm_suffix_keys.add(tuple(slot.ending_signs))

    # Classify suffixes
    for affix in affix_inv.suffixes:
        _classify_one(
            affix,
            paradigm_suffix_keys,
            inflectional_threshold,
            derivational_threshold,
        )

    # Classify prefixes (same logic)
    paradigm_prefix_keys: set = set()  # No prefix paradigms currently
    for affix in affix_inv.prefixes:
        _classify_one(
            affix,
            paradigm_prefix_keys,
            inflectional_threshold,
            derivational_threshold,
        )

    return affix_inv


def _classify_one(
    affix: Affix,
    paradigm_keys: set,
    inflectional_threshold: float,
    derivational_threshold: float,
) -> None:
    """Classify a single affix in place."""
    affix_key = tuple(affix.signs)
    is_paradigm_regular = affix_key in paradigm_keys

    # Frequency-type ratio
    freq_type_ratio = (
        affix.frequency / affix.n_distinct_stems
        if affix.n_distinct_stems > 0 else 0.0
    )

    # Classification logic (PRD Section 5.4)
    if affix.productivity > inflectional_threshold and is_paradigm_regular:
        classification = "inflectional"
    elif affix.productivity < derivational_threshold or not is_paradigm_regular:
        classification = "derivational"
    else:
        classification = "ambiguous"

    affix.classification = classification
