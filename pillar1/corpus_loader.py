"""Corpus loader for Pillar 1.

Reads the SigLA Full Linear A Corpus JSON, filters to syllabograms,
and produces clean sign-sequence data in positional and bigram formats.

IMPORTANT: This module operates on sign IDs (ab_codes), NOT on phonetic
labels (sign_readings). This enforces the independent discovery requirement.
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional


@dataclass
class SignToken:
    """A single sign occurrence with its reading and type."""
    sign_id: str       # AB code (e.g., "AB08", "AB59")
    sign_type: str     # "syllabogram", "logogram", "numeral", "unknown"
    reading: str       # Original reading (e.g., "a", "ta") — NOT used by analysis


@dataclass
class Word:
    """A word (sign-group) as a sequence of sign tokens."""
    signs: List[SignToken]
    has_damage: bool
    inscription_id: str
    word_index: int  # Position within inscription

    @property
    def syllabogram_signs(self) -> List[SignToken]:
        return [s for s in self.signs if s.sign_type == "syllabogram"]

    @property
    def sign_ids(self) -> List[str]:
        """Return only syllabogram sign IDs."""
        return [s.sign_id for s in self.syllabogram_signs]


@dataclass
class Inscription:
    """A single inscription with its words."""
    id: str
    type: str
    site: str
    words: List[Word]


@dataclass
class PositionalRecord:
    """A sign occurrence with its position label."""
    sign_id: str
    position: str  # "initial", "medial", "final", "singleton"
    word_sign_ids: List[str]  # The full word for context
    inscription_id: str


@dataclass
class BigramRecord:
    """A consecutive sign pair within a word."""
    sign_i: str
    sign_j: str
    position_in_word: int  # 0-indexed position of sign_i
    word_sign_ids: List[str]
    inscription_id: str


@dataclass
class CorpusData:
    """Processed corpus data ready for analysis."""
    inscriptions: List[Inscription]
    positional_records: List[PositionalRecord]
    bigram_records: List[BigramRecord]
    sign_inventory: Dict[str, dict]
    corpus_hash: str
    # Summary statistics
    total_inscriptions: int = 0
    total_words: int = 0
    total_syllabogram_tokens: int = 0
    unique_syllabograms: int = 0
    words_used_positional: int = 0
    words_used_bigram: int = 0


def load_corpus(
    corpus_path: str | Path,
    sign_types_included: List[str] | None = None,
    exclude_damaged: bool = True,
    min_word_length: int = 2,
) -> CorpusData:
    """Load and preprocess the SigLA corpus.

    Args:
        corpus_path: Path to sigla_full_corpus.json
        sign_types_included: Sign types to retain (default: ["syllabogram"])
        exclude_damaged: Whether to exclude damaged words from positional analysis
        min_word_length: Minimum syllabogram signs per word for positional analysis

    Returns:
        CorpusData with clean sign sequences, positional records, and bigram records.
    """
    if sign_types_included is None:
        sign_types_included = ["syllabogram"]

    corpus_path = Path(corpus_path)

    # Compute corpus hash for provenance
    with open(corpus_path, "rb") as f:
        corpus_hash = hashlib.sha256(f.read()).hexdigest()

    with open(corpus_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    sign_inventory = raw.get("sign_inventory", {})
    raw_inscriptions = raw.get("inscriptions", [])

    inscriptions: List[Inscription] = []
    positional_records: List[PositionalRecord] = []
    bigram_records: List[BigramRecord] = []

    total_words = 0
    total_syllabogram_tokens = 0
    all_syllabogram_ids = set()
    words_used_positional = 0
    words_used_bigram = 0

    for raw_insc in raw_inscriptions:
        insc_id = raw_insc.get("id", "unknown")
        insc_type = raw_insc.get("type", "unknown")
        insc_site = raw_insc.get("site", "unknown")

        words: List[Word] = []
        for wi, raw_word in enumerate(raw_insc.get("words", [])):
            sign_readings = raw_word.get("sign_readings", [])
            ab_codes_str = raw_word.get("ab_codes", "")
            has_damage = raw_word.get("has_damage", False)

            # Parse ab_codes — format is "AB59-AB39" or similar
            ab_codes = _parse_ab_codes(ab_codes_str, sign_readings, sign_inventory)

            # Build sign tokens
            signs: List[SignToken] = []
            for sign_id, reading in ab_codes:
                stype = _get_sign_type(sign_id, reading, sign_inventory)
                signs.append(SignToken(sign_id=sign_id, sign_type=stype, reading=reading))

            word = Word(signs=signs, has_damage=has_damage,
                        inscription_id=insc_id, word_index=wi)
            words.append(word)

            # Count syllabograms
            syllib_ids = word.sign_ids
            total_words += 1
            total_syllabogram_tokens += len(syllib_ids)
            all_syllabogram_ids.update(syllib_ids)

            # --- Positional records ---
            # Only for undamaged words with enough syllabograms, from multi-word inscriptions
            use_for_positional = (
                len(syllib_ids) >= min_word_length
                and (not exclude_damaged or not has_damage)
            )
            if use_for_positional:
                words_used_positional += 1
                for pos_idx, sid in enumerate(syllib_ids):
                    if len(syllib_ids) == 1:
                        position = "singleton"
                    elif pos_idx == 0:
                        position = "initial"
                    elif pos_idx == len(syllib_ids) - 1:
                        position = "final"
                    else:
                        position = "medial"
                    positional_records.append(PositionalRecord(
                        sign_id=sid, position=position,
                        word_sign_ids=syllib_ids, inscription_id=insc_id,
                    ))

            # --- Bigram records ---
            # For all words with ≥2 syllabograms (even damaged — bigrams within
            # the attested portion are still valid)
            if len(syllib_ids) >= 2:
                words_used_bigram += 1
                for j in range(len(syllib_ids) - 1):
                    bigram_records.append(BigramRecord(
                        sign_i=syllib_ids[j], sign_j=syllib_ids[j + 1],
                        position_in_word=j, word_sign_ids=syllib_ids,
                        inscription_id=insc_id,
                    ))

        inscriptions.append(Inscription(
            id=insc_id, type=insc_type, site=insc_site, words=words,
        ))

    return CorpusData(
        inscriptions=inscriptions,
        positional_records=positional_records,
        bigram_records=bigram_records,
        sign_inventory=sign_inventory,
        corpus_hash=corpus_hash,
        total_inscriptions=len(inscriptions),
        total_words=total_words,
        total_syllabogram_tokens=total_syllabogram_tokens,
        unique_syllabograms=len(all_syllabogram_ids),
        words_used_positional=words_used_positional,
        words_used_bigram=words_used_bigram,
    )


def _parse_ab_codes(
    ab_codes_str: str,
    sign_readings: List[str],
    sign_inventory: Dict[str, dict],
) -> List[Tuple[str, str]]:
    """Parse AB codes string and pair with readings.

    Returns list of (sign_id, reading) tuples.
    """
    if not ab_codes_str:
        # Fall back to using readings as IDs (with a prefix to distinguish)
        return [(f"R_{r}", r) for r in sign_readings]

    ab_parts = ab_codes_str.split("-")

    # Handle length mismatch: ab_codes and sign_readings may differ
    # (logograms, numerals may be absent from one or the other)
    result = []
    for i, ab in enumerate(ab_parts):
        reading = sign_readings[i] if i < len(sign_readings) else ab
        result.append((ab, reading))

    return result


def _get_sign_type(
    sign_id: str, reading: str, sign_inventory: Dict[str, dict]
) -> str:
    """Determine sign type from inventory."""
    # Check inventory by reading (the key used in sign_inventory)
    if reading in sign_inventory:
        return sign_inventory[reading].get("type", "unknown")

    # Check by sign_id
    if sign_id in sign_inventory:
        return sign_inventory[sign_id].get("type", "unknown")

    # Heuristics for signs not in inventory
    if sign_id.startswith("A7") or sign_id.startswith("NUM"):
        return "numeral"

    return "unknown"
