"""Paradigm induction via stem-suffix clustering.

Implements PRD Section 5.3: Groups stems that share the same set of
possible endings into paradigm classes (analogous to Latin declension
classes).

Algorithm:
1. Build stem x suffix incidence matrix I
2. Compute paradigm signature for each stem: sig(s) = {suffixes s appears with}
3. Cluster stems by Jaccard similarity of signatures (agglomerative)
4. For each cluster: list slots, compute completeness, find examples
5. Optional: grid-informed analysis using Pillar 1 consonant/vowel classes
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from .segmenter import SegmentedLexicon, SegmentedWord
from .affix_extractor import AffixInventory, Affix
from .pillar1_loader import Pillar1Output


@dataclass
class ParadigmSlot:
    """A single slot in a paradigm (one suffix position)."""
    slot_id: int
    ending_signs: List[str]
    frequency: int
    label: str


@dataclass
class StemExample:
    """An example stem within a paradigm class."""
    stem: List[str]
    attested_slots: List[int]
    attested_forms: List[Dict]  # {"slot": int, "full_word": List[str]}


@dataclass
class GridAnalysis:
    """Grid-informed analysis of paradigm endings."""
    endings_share_consonant_row: bool
    consonant_class: Optional[int]
    vowel_classes_attested: List[int]


@dataclass
class Paradigm:
    """A paradigm class: a set of stems sharing a suffix pattern."""
    class_id: int
    n_members: int
    slots: List[ParadigmSlot]
    example_stems: List[StemExample]
    completeness: float  # fraction of stem x slot cells that are attested
    all_stems: List[List[str]] = field(default_factory=list)
    grid_analysis: Optional[GridAnalysis] = None


@dataclass
class ParadigmTable:
    """The full paradigm table."""
    n_classes: int
    paradigms: List[Paradigm]


def induce_paradigms(
    lexicon: SegmentedLexicon,
    affix_inv: AffixInventory,
    pillar1: Pillar1Output,
    jaccard_threshold: float = 0.3,
    min_paradigm_members: int = 2,
    min_paradigm_slots: int = 2,
    max_paradigm_classes: int = 15,
) -> ParadigmTable:
    """Induce paradigm classes from the segmented lexicon.

    Args:
        lexicon: Segmented lexicon from the segmenter.
        affix_inv: Affix inventory from the extractor.
        pillar1: Pillar 1 output for grid-informed analysis.
        jaccard_threshold: Minimum Jaccard similarity for merging.
        min_paradigm_members: Minimum stems per paradigm class.
        min_paradigm_slots: Minimum suffix slots per paradigm class.
        max_paradigm_classes: Upper bound for paradigm count.

    Returns:
        ParadigmTable with induced paradigm classes.
    """
    # --- Step 1: Build stem x suffix incidence matrix ---
    # Only consider words that have suffixes and whose suffix is in the inventory
    valid_suffix_keys = set(tuple(a.signs) for a in affix_inv.suffixes)

    stem_suffixes: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = defaultdict(set)
    stem_forms: Dict[Tuple[str, ...], Dict[Tuple[str, ...], List[str]]] = defaultdict(dict)

    for word in lexicon.words:
        if not word.suffixes:
            continue
        stem_key = tuple(word.stem)
        for suffix in word.suffixes:
            suf_key = tuple(suffix)
            if suf_key in valid_suffix_keys:
                stem_suffixes[stem_key].add(suf_key)
                stem_forms[stem_key][suf_key] = word.word_sign_ids

    # Filter: only stems that take at least 1 valid suffix
    stems_with_suffixes = {s: sigs for s, sigs in stem_suffixes.items() if sigs}

    if not stems_with_suffixes:
        return ParadigmTable(n_classes=0, paradigms=[])

    # Get all suffix keys that appear
    all_suffix_keys = sorted(set().union(*stems_with_suffixes.values()))
    suffix_index = {sk: i for i, sk in enumerate(all_suffix_keys)}
    stem_list = sorted(stems_with_suffixes.keys())

    if len(stem_list) < min_paradigm_members:
        return ParadigmTable(n_classes=0, paradigms=[])

    # --- Step 2: Cluster by Jaccard similarity ---
    # For small corpora, direct Jaccard-based clustering is more robust
    # than building a full distance matrix + scipy hierarchical clustering.
    # We use a simple greedy approach:
    #   1. Group stems with identical signatures
    #   2. Merge groups with Jaccard > threshold

    # Group by exact signature
    sig_to_stems: Dict[frozenset, List[Tuple[str, ...]]] = defaultdict(list)
    for stem in stem_list:
        sig = frozenset(stems_with_suffixes[stem])
        sig_to_stems[sig].add(stem) if hasattr(sig_to_stems[sig], 'add') else sig_to_stems[sig].append(stem)

    # Actually, defaultdict(list).append is correct. Fix above:
    sig_groups: List[Tuple[frozenset, List[Tuple[str, ...]]]] = [
        (sig, stems) for sig, stems in sig_to_stems.items()
    ]

    # Merge groups with high Jaccard similarity
    merged = _merge_groups(sig_groups, jaccard_threshold, max_paradigm_classes)

    # --- Step 3: Build paradigm classes ---
    paradigms: List[Paradigm] = []
    class_id = 0

    for group_sigs, group_stems in merged:
        if len(group_stems) < min_paradigm_members:
            continue

        # Collect all suffixes attested across the group
        all_suf: Set[Tuple[str, ...]] = set()
        for stem in group_stems:
            all_suf.update(stems_with_suffixes.get(stem, set()))

        if len(all_suf) < min_paradigm_slots:
            continue

        # Build slots
        slots: List[ParadigmSlot] = []
        for slot_id, suf_key in enumerate(sorted(all_suf)):
            # Count how many stems in this group attest this suffix
            freq = sum(1 for s in group_stems if suf_key in stems_with_suffixes.get(s, set()))
            slots.append(ParadigmSlot(
                slot_id=slot_id,
                ending_signs=list(suf_key),
                frequency=freq,
                label=f"slot_{slot_id}",
            ))

        # Completeness: fraction of stem x slot cells attested
        n_cells = len(group_stems) * len(slots)
        n_attested = sum(s.frequency for s in slots)
        completeness = n_attested / n_cells if n_cells > 0 else 0.0

        # Example stems (up to 5)
        examples: List[StemExample] = []
        for stem in group_stems[:5]:
            attested_slots = []
            attested_forms = []
            for slot in slots:
                suf_key = tuple(slot.ending_signs)
                if suf_key in stems_with_suffixes.get(stem, set()):
                    attested_slots.append(slot.slot_id)
                    full_word = stem_forms.get(stem, {}).get(suf_key, list(stem) + list(suf_key))
                    attested_forms.append({
                        "slot": slot.slot_id,
                        "full_word": full_word,
                    })
            examples.append(StemExample(
                stem=list(stem),
                attested_slots=attested_slots,
                attested_forms=attested_forms,
            ))

        # Grid analysis
        grid_analysis = _grid_analysis(slots, pillar1)

        paradigms.append(Paradigm(
            class_id=class_id,
            n_members=len(group_stems),
            slots=slots,
            example_stems=examples,
            completeness=completeness,
            all_stems=[list(s) for s in group_stems],
            grid_analysis=grid_analysis,
        ))
        class_id += 1

    # Update affix paradigm_classes
    for paradigm in paradigms:
        for slot in paradigm.slots:
            suf_key = tuple(slot.ending_signs)
            if suf_key in affix_inv.suffix_lookup:
                affix_inv.suffix_lookup[suf_key].paradigm_classes.append(paradigm.class_id)

    return ParadigmTable(
        n_classes=len(paradigms),
        paradigms=paradigms,
    )


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Compute Jaccard similarity between two sets."""
    if not a and not b:
        return 1.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def _merge_groups(
    sig_groups: List[Tuple[frozenset, List[Tuple[str, ...]]]],
    threshold: float,
    max_classes: int,
) -> List[Tuple[List[frozenset], List[Tuple[str, ...]]]]:
    """Merge signature groups with Jaccard similarity above threshold.

    Uses greedy agglomerative merging: repeatedly merge the most similar
    pair until no pair exceeds the threshold.
    """
    # Each entry: (set of signatures, list of stems)
    groups: List[Tuple[List[frozenset], List[Tuple[str, ...]]]] = [
        ([sig], list(stems)) for sig, stems in sig_groups
    ]

    changed = True
    while changed and len(groups) > 1:
        changed = False
        best_sim = -1.0
        best_i = -1
        best_j = -1

        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                # Compare the union of signatures
                sigs_i = frozenset().union(*groups[i][0])
                sigs_j = frozenset().union(*groups[j][0])
                sim = _jaccard(sigs_i, sigs_j)
                if sim > best_sim:
                    best_sim = sim
                    best_i = i
                    best_j = j

        # If similarity is below threshold AND we are already within
        # max_classes, stop merging.  But if we still have too many
        # groups, force-merge the best pair regardless of threshold.
        if best_sim < threshold and len(groups) <= max_classes:
            break

        # Merge best_j into best_i (either above threshold, or
        # forced because len(groups) > max_classes)
        groups[best_i] = (
            groups[best_i][0] + groups[best_j][0],
            groups[best_i][1] + groups[best_j][1],
        )
        groups.pop(best_j)
        changed = True

    return groups


def _grid_analysis(
    slots: List[ParadigmSlot],
    pillar1: Pillar1Output,
) -> Optional[GridAnalysis]:
    """Analyze paradigm endings against the Pillar 1 grid.

    Check if endings share a consonant row (suggesting they differ only
    in vowel = different case forms of the same declension).
    """
    if not pillar1.grid_assignments or not slots:
        return None

    # Get grid info for each ending's first sign
    consonant_classes: List[int] = []
    vowel_classes: List[int] = []

    for slot in slots:
        if not slot.ending_signs:
            continue
        sign_id = slot.ending_signs[0]
        if sign_id in pillar1.sign_to_grid:
            ga = pillar1.sign_to_grid[sign_id]
            consonant_classes.append(ga.consonant_class)
            vowel_classes.append(ga.vowel_class)

    if not consonant_classes:
        return None

    # Check if all endings share the same consonant class
    share_consonant = len(set(consonant_classes)) == 1
    consonant_class = consonant_classes[0] if share_consonant else None
    vowel_classes_attested = sorted(set(vowel_classes))

    return GridAnalysis(
        endings_share_consonant_row=share_consonant,
        consonant_class=consonant_class,
        vowel_classes_attested=vowel_classes_attested,
    )
