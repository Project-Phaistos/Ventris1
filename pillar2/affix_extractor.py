"""Affix extraction with productivity scoring.

Implements PRD Section 5.2: From the segmented lexicon, extract the
inventory of attested suffixes and prefixes and compute their productivity.

Productivity = n_distinct_stems / max_n_distinct_stems across all affixes
of the same type (suffix/prefix).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .segmenter import SegmentedLexicon, SegmentedWord


@dataclass
class Affix:
    """An attested affix with its statistics."""
    signs: List[str]
    frequency: int
    n_distinct_stems: int
    productivity: float
    classification: str = "unclassified"  # Set by inflection_classifier
    paradigm_classes: List[int] = field(default_factory=list)


@dataclass
class AffixInventory:
    """The complete affix inventory extracted from the segmented lexicon."""
    suffixes: List[Affix]
    prefixes: List[Affix]
    # Lookup: tuple of sign IDs -> Affix (for fast access)
    suffix_lookup: Dict[Tuple[str, ...], Affix] = field(default_factory=dict)
    prefix_lookup: Dict[Tuple[str, ...], Affix] = field(default_factory=dict)


def extract_affixes(
    lexicon: SegmentedLexicon,
    min_affix_stems: int = 2,
) -> AffixInventory:
    """Extract suffix and prefix inventories from the segmented lexicon.

    Args:
        lexicon: The segmented lexicon from the segmenter.
        min_affix_stems: Minimum distinct stems for an affix to be retained.

    Returns:
        AffixInventory with suffixes and prefixes, each with productivity scores.
    """
    # Collect suffix statistics
    suffix_stems: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = defaultdict(set)
    suffix_freq: Dict[Tuple[str, ...], int] = defaultdict(int)

    # Collect prefix statistics
    prefix_stems: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = defaultdict(set)
    prefix_freq: Dict[Tuple[str, ...], int] = defaultdict(int)

    for word in lexicon.words:
        stem_key = tuple(word.stem)

        for suffix in word.suffixes:
            suf_key = tuple(suffix)
            suffix_stems[suf_key].add(stem_key)
            suffix_freq[suf_key] += word.frequency

        for prefix in word.prefixes:
            pre_key = tuple(prefix)
            prefix_stems[pre_key].add(stem_key)
            prefix_freq[pre_key] += word.frequency

    # Build suffix inventory
    suffixes = _build_affix_list(suffix_stems, suffix_freq, min_affix_stems)

    # Build prefix inventory
    prefixes = _build_affix_list(prefix_stems, prefix_freq, min_affix_stems)

    # Build lookups
    suffix_lookup = {tuple(a.signs): a for a in suffixes}
    prefix_lookup = {tuple(a.signs): a for a in prefixes}

    return AffixInventory(
        suffixes=suffixes,
        prefixes=prefixes,
        suffix_lookup=suffix_lookup,
        prefix_lookup=prefix_lookup,
    )


def _build_affix_list(
    affix_stems: Dict[Tuple[str, ...], Set[Tuple[str, ...]]],
    affix_freq: Dict[Tuple[str, ...], int],
    min_affix_stems: int,
) -> List[Affix]:
    """Build a filtered, productivity-scored affix list."""
    if not affix_stems:
        return []

    # First pass: filter by min_affix_stems
    candidates: List[Tuple[Tuple[str, ...], int, int]] = []
    for affix_key, stems in affix_stems.items():
        n_stems = len(stems)
        if n_stems >= min_affix_stems:
            candidates.append((affix_key, affix_freq[affix_key], n_stems))

    if not candidates:
        return []

    # Compute productivity: n_distinct_stems / max(n_distinct_stems)
    max_stems = max(c[2] for c in candidates)

    affixes: List[Affix] = []
    for affix_key, freq, n_stems in candidates:
        productivity = n_stems / max_stems if max_stems > 0 else 0.0
        affixes.append(Affix(
            signs=list(affix_key),
            frequency=freq,
            n_distinct_stems=n_stems,
            productivity=productivity,
        ))

    # Sort by productivity descending, then frequency descending
    affixes.sort(key=lambda a: (-a.productivity, -a.frequency))

    return affixes
