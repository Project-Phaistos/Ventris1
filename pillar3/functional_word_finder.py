"""Functional word identification.

PRD Section 5.5: Identify high-frequency, low-semantic-content words that
serve grammatical functions (articles, prepositions, conjunctions, discourse
markers, structural markers like ku-ro "total").

Algorithm:
1. Candidate selection: length <= max_length, frequency >= min_freq,
   inscriptions >= min_inscriptions, uninflected or unknown word class.
2. Positional profiling: initial_rate, final_rate, pre_numeral_rate.
3. Classification heuristics based on positional patterns.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .data_loader import (
    CorpusInscription,
    CorpusWord,
    GrammarInputData,
    Pillar2Data,
)
from .profile_builder import _stem_key_for_word
from .word_class_inducer import WordClassResult


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class FunctionalWord:
    """A candidate functional word with positional profile and classification.

    PRD Section 5.5: Functional words are short, frequent, widespread,
    and typically uninflected. Classification is based on positional
    patterns within inscriptions.
    """
    word_sign_ids: List[str]
    reading: str
    frequency: int
    n_inscriptions: int
    positional_profile: Dict[str, float]
    classification: str  # "structural_marker", "relator", "determiner", "particle"
    evidence: str
    word_class_id: Optional[int] = None
    word_class_label: Optional[str] = None


@dataclass
class FunctionalWordResult:
    """Result of functional word identification.

    Attributes:
        functional_words: List of identified functional words.
        n_candidates_screened: Total candidates meeting initial criteria.
        n_functional: Number classified as functional.
    """
    functional_words: List[FunctionalWord]
    n_candidates_screened: int = 0
    n_functional: int = 0


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "max_length": 2,              # Maximum sign count for functional words
    "min_freq": 5,                # Minimum corpus frequency
    "min_inscriptions": 5,        # Minimum distinct inscriptions
    "final_rate_threshold": 0.30, # Threshold for structural_marker
    "relator_consistency": 0.50,  # Fraction between two content words
    "determiner_consistency": 0.50,  # Fraction before same class
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_word_sign_count(word_sign_ids: List[str]) -> int:
    """Count the number of actual signs (excluding damage markers)."""
    return sum(
        1 for s in word_sign_ids
        if s not in ("[?]", "?") and not s.startswith("[")
    )


def _get_word_reading(word: CorpusWord) -> str:
    """Get the transliteration reading for display."""
    reading = word.transliteration.strip()
    # Remove damage markers from display
    for prefix in ("]", "["):
        reading = reading.replace(prefix, "")
    return reading.strip()


def _assign_word_class_id(
    word_sign_ids: List[str],
    pillar2: Pillar2Data,
    word_classes: Optional[WordClassResult],
) -> Optional[int]:
    """Look up the word class for a word."""
    if word_classes is None:
        return None
    word_key = tuple(word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is None:
        stem = word_key
    return word_classes.assignments.get(stem)


def _get_word_class_label(
    word_sign_ids: List[str],
    pillar2: Pillar2Data,
) -> str:
    """Get the Pillar 2 morphological word class label for a word."""
    word_key = tuple(word_sign_ids)
    stem = pillar2.word_ids_to_stem.get(word_key)
    if stem is None:
        stem = word_key
    return pillar2.stem_to_word_class.get(stem, "unknown")


def _is_content_word_class(
    class_id: Optional[int],
    word_classes: Optional[WordClassResult],
) -> bool:
    """Check if a word class is a content word class."""
    if word_classes is None or class_id is None:
        return False
    for cls in word_classes.classes:
        if cls.class_id == class_id:
            return cls.morphological_profile == "declining"
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_functional_words(
    data: GrammarInputData,
    word_classes: Optional[WordClassResult] = None,
    config: Optional[Dict[str, Any]] = None,
) -> FunctionalWordResult:
    """Identify functional words from the corpus.

    PRD Section 5.5: Selects candidates based on length, frequency, and
    distribution, then classifies them by positional pattern.

    Args:
        data: Combined grammar input data.
        word_classes: Optional word class assignments (for richer
            classification with relator/determiner detection).
        config: Optional configuration overrides.

    Returns:
        FunctionalWordResult with classified functional words.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    max_length = cfg["max_length"]
    min_freq = cfg["min_freq"]
    min_inscriptions = cfg["min_inscriptions"]
    final_thresh = cfg["final_rate_threshold"]
    relator_thresh = cfg["relator_consistency"]
    determiner_thresh = cfg["determiner_consistency"]

    pillar2 = data.pillar2
    inscriptions = data.inscriptions

    # --- Step 1: Aggregate word statistics across corpus ---
    # Key: word_sign_ids tuple -> statistics
    word_freq: Counter = Counter()
    word_inscriptions: Dict[Tuple[str, ...], Set[str]] = defaultdict(set)
    word_readings: Dict[Tuple[str, ...], str] = {}

    # Positional accumulators
    word_initial_count: Counter = Counter()
    word_final_count: Counter = Counter()
    word_pre_numeral_count: Counter = Counter()

    # Context tracking for relator/determiner detection
    # (word, predecessor_class, successor_class) counts
    word_between_content: Counter = Counter()  # times between two content words
    word_before_class: Dict[Tuple[str, ...], Counter] = defaultdict(Counter)

    for insc in inscriptions:
        for i, word in enumerate(insc.words):
            wkey = tuple(word.word_sign_ids)
            word_freq[wkey] += 1
            word_inscriptions[wkey].add(insc.inscription_id)

            if wkey not in word_readings:
                word_readings[wkey] = _get_word_reading(word)

            if word.is_initial:
                word_initial_count[wkey] += 1
            if word.is_final:
                word_final_count[wkey] += 1
            if word.has_numeral_after:
                word_pre_numeral_count[wkey] += 1

            # Context for relator/determiner detection (if word classes available)
            if word_classes is not None:
                # Check if between two content words
                if 0 < i < len(insc.words) - 1:
                    prev_cid = _assign_word_class_id(
                        insc.words[i - 1].word_sign_ids, pillar2, word_classes
                    )
                    next_cid = _assign_word_class_id(
                        insc.words[i + 1].word_sign_ids, pillar2, word_classes
                    )
                    if (_is_content_word_class(prev_cid, word_classes) and
                            _is_content_word_class(next_cid, word_classes)):
                        word_between_content[wkey] += 1

                # Track what class follows this word
                if i < len(insc.words) - 1:
                    next_cid = _assign_word_class_id(
                        insc.words[i + 1].word_sign_ids, pillar2, word_classes
                    )
                    if next_cid is not None:
                        word_before_class[wkey][next_cid] += 1

    # --- Step 2: Filter candidates ---
    candidates: List[Tuple[str, ...]] = []
    for wkey, freq in word_freq.items():
        # Length check
        sign_count = _get_word_sign_count(list(wkey))
        if sign_count > max_length:
            continue

        # Frequency check
        if freq < min_freq:
            continue

        # Inscription diversity check
        if len(word_inscriptions[wkey]) < min_inscriptions:
            continue

        # Morphological check: uninflected or unknown
        wc_label = _get_word_class_label(list(wkey), pillar2)
        if wc_label == "declining":
            continue  # Declining words are content words, not functional

        candidates.append(wkey)

    n_screened = len(candidates)

    # --- Step 3: Classify candidates ---
    functional_words: List[FunctionalWord] = []

    for wkey in candidates:
        freq = word_freq[wkey]
        n_insc = len(word_inscriptions[wkey])

        initial_rate = word_initial_count[wkey] / freq if freq > 0 else 0.0
        final_rate = word_final_count[wkey] / freq if freq > 0 else 0.0
        pre_numeral_rate = word_pre_numeral_count[wkey] / freq if freq > 0 else 0.0

        pos_profile = {
            "initial_rate": round(initial_rate, 3),
            "final_rate": round(final_rate, 3),
            "pre_numeral_rate": round(pre_numeral_rate, 3),
        }

        # Classification heuristics (PRD Section 5.5, step 3)
        classification = "particle"  # Default
        evidence_parts: List[str] = []

        if final_rate > final_thresh:
            classification = "structural_marker"
            evidence_parts.append(
                f"High final-position rate ({final_rate:.1%})"
            )

        elif word_classes is not None:
            between_rate = (
                word_between_content[wkey] / freq if freq > 0 else 0.0
            )
            if between_rate > relator_thresh:
                classification = "relator"
                evidence_parts.append(
                    f"Consistently between content words ({between_rate:.1%})"
                )
            else:
                # Check if consistently before the same word class
                class_counts = word_before_class.get(wkey, Counter())
                if class_counts:
                    most_common_class, mc_count = class_counts.most_common(1)[0]
                    total_follows = sum(class_counts.values())
                    consistency = mc_count / total_follows if total_follows > 0 else 0.0
                    if consistency > determiner_thresh and total_follows >= 3:
                        classification = "determiner"
                        evidence_parts.append(
                            f"Consistently before class {most_common_class} "
                            f"({consistency:.1%} of {total_follows} cases)"
                        )

        if not evidence_parts:
            evidence_parts.append(
                f"Short ({_get_word_sign_count(list(wkey))} signs), "
                f"frequent ({freq}x in {n_insc} inscriptions), "
                f"uninflected"
            )

        wc_id = _assign_word_class_id(list(wkey), pillar2, word_classes)
        wc_label = _get_word_class_label(list(wkey), pillar2)

        fw = FunctionalWord(
            word_sign_ids=list(wkey),
            reading=word_readings.get(wkey, "-".join(wkey)),
            frequency=freq,
            n_inscriptions=n_insc,
            positional_profile=pos_profile,
            classification=classification,
            evidence="; ".join(evidence_parts),
            word_class_id=wc_id,
            word_class_label=wc_label,
        )
        functional_words.append(fw)

    # Sort by frequency descending
    functional_words.sort(key=lambda fw: -fw.frequency)

    return FunctionalWordResult(
        functional_words=functional_words,
        n_candidates_screened=n_screened,
        n_functional=len(functional_words),
    )
