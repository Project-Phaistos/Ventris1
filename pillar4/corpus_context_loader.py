"""Corpus context loader for Pillar 4 (Semantic Anchoring).

Loads the SigLA corpus with FULL sign sequences — syllabograms, logograms,
and numerals — preserving the interleaving of text and non-text elements.

PRD Section 5: Semantic anchoring requires the full inscription context,
including commodity ideograms (named GORILA logograms with "/" in their
reading), unknown logograms (A-series codes without names), and numeral
signs (A70x series).

IMPORTANT: Sign-groups in this corpus are separated by physical dividers
on tablets, NOT by linguistic analysis.  Many inscriptions have NO word
dividers.  We label segmentation_confidence accordingly.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Named-ideogram recognition
# ---------------------------------------------------------------------------

# A named GORILA ideogram has "/" in its reading, e.g. "AB120/GRA"
_NAMED_IDEOGRAM_RE = re.compile(r"^AB\d+[a-z]?/.+$", re.IGNORECASE)

# Numeral readings — A70x family (decimal-additive system, Bennett 1950)
_NUMERAL_RE = re.compile(r"^A70\d")


def _is_named_ideogram(reading: str) -> bool:
    """Return True if *reading* matches a named GORILA ideogram (has '/')."""
    return "/" in reading and bool(_NAMED_IDEOGRAM_RE.match(reading))


def _is_numeral_sign(reading: str) -> bool:
    """Return True if *reading* looks like a Linear A numeral (A70x series)."""
    return bool(_NUMERAL_RE.match(reading))


def _is_unknown_logogram(reading: str, sign_type: str) -> bool:
    """Return True for logograms that are NOT named ideograms and NOT numerals.

    These are A-series codes without "/" names — their semantic identity is
    unknown and they must NOT be treated as identified commodity ideograms.
    """
    if _is_named_ideogram(reading):
        return False
    if _is_numeral_sign(reading):
        return False
    # A-series logograms (A3xx through A6xx) or other codes appearing as logogram
    if sign_type == "logogram":
        return True
    # Some logograms are mis-typed as syllabogram in the corpus (data quirk).
    # Catch A-series codes that look like logograms even if typed syllabogram.
    if re.match(r"^A[3-6]\d{2}", reading):
        return True
    return False


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SignOccurrence:
    """A single sign in an inscription's sequence.

    Attributes:
        sign_id: The reading string from the corpus (e.g. "ku", "AB120/GRA",
            "A704").  For signs with an ``ab_code`` field, that code is used
            as an alternate identifier.
        sign_type: Categorised type: "syllabogram", "named_ideogram",
            "unknown_logogram", or "numeral".  This is re-classified from
            the raw corpus type which conflates several categories.
        reading: The raw reading string from the corpus.
        position_in_sequence: Zero-based index within the inscription's
            full signs_sequence.
        ab_code: AB-code if available in the corpus entry, else None.
    """
    sign_id: str
    sign_type: str          # syllabogram | named_ideogram | unknown_logogram | numeral
    reading: str
    position_in_sequence: int
    ab_code: Optional[str] = None


@dataclass
class SignGroup:
    """A group of syllabographic signs separated by physical dividers.

    TERMINOLOGY NOTE: These are called "sign_groups", not "words", because
    they are separated by physical dividers on tablets, NOT by confirmed
    linguistic word boundaries.

    Attributes:
        signs: List of syllabogram SignOccurrences in this group.
        sign_ids: Tuple of sign readings for hashing / lookup.
        ab_codes_str: Hyphen-joined AB-codes from the corpus word entry.
        transliteration: Transliteration string from the corpus.
        has_damage: Whether damage markers are present.
        segmentation_confidence: "divider_attested" if the corpus explicitly
            segments this group (it comes from the ``words`` array, which
            represents divider-separated segments), or "inferred" otherwise.
        inscription_id: Parent inscription identifier.
        position_in_inscription: Zero-based index among sign-groups in this
            inscription.
    """
    signs: List[SignOccurrence]
    sign_ids: Tuple[str, ...]
    ab_codes_str: str
    transliteration: str
    has_damage: bool
    segmentation_confidence: str   # "divider_attested" | "inferred"
    inscription_id: str = ""
    position_in_inscription: int = 0

    @property
    def n_signs(self) -> int:
        return len(self.signs)


@dataclass
class InscriptionContext:
    """Full context of a single inscription, preserving all sign types.

    Attributes:
        id: Inscription identifier (e.g. "HT 9a").
        type: Inscription type (e.g. "Tablet", "libation_table").
        site: Finding site (e.g. "Hagia Triada").
        full_sign_sequence: ALL signs in order, including syllabograms,
            named ideograms, unknown logograms, and numerals.
        sign_groups: Text segments (sign-groups) from the ``words`` array.
        ideograms_in_sequence: Named ideograms found in signs_sequence,
            with their positions.
        numerals_in_sequence: Numeral signs found in signs_sequence,
            with their positions.
        unknown_logograms_in_sequence: Unknown logograms (A-series without
            "/" names) found in signs_sequence.
    """
    id: str
    type: str
    site: str
    full_sign_sequence: List[SignOccurrence]
    sign_groups: List[SignGroup]
    ideograms_in_sequence: List[SignOccurrence] = field(default_factory=list)
    numerals_in_sequence: List[SignOccurrence] = field(default_factory=list)
    unknown_logograms_in_sequence: List[SignOccurrence] = field(
        default_factory=list
    )

    @property
    def n_signs(self) -> int:
        return len(self.full_sign_sequence)

    @property
    def n_sign_groups(self) -> int:
        return len(self.sign_groups)


@dataclass
class ContextCorpus:
    """The full loaded corpus with inventories.

    Attributes:
        inscriptions: List of InscriptionContext objects.
        ideogram_inventory: Set of named GORILA ideogram readings found
            in the corpus (only those with "/" in reading).
        numeral_inventory: Set of numeral readings found in the corpus
            (A70x series).
        unknown_logogram_inventory: Set of unknown logogram readings
            (A-series without "/" names).
    """
    inscriptions: List[InscriptionContext]
    ideogram_inventory: Set[str] = field(default_factory=set)
    numeral_inventory: Set[str] = field(default_factory=set)
    unknown_logogram_inventory: Set[str] = field(default_factory=set)

    @property
    def n_inscriptions(self) -> int:
        return len(self.inscriptions)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _classify_sign(reading: str, raw_type: str) -> str:
    """Re-classify a sign from the raw corpus type into our four categories.

    The raw corpus conflates some categories (e.g. numerals typed as
    "syllabogram").  We re-classify based on reading patterns:
    - Named ideogram: has "/" in reading and matches AB pattern
    - Numeral: A70x series
    - Unknown logogram: A-series without "/" or logogram type
    - Syllabogram: everything else
    """
    if _is_named_ideogram(reading):
        return "named_ideogram"
    if _is_numeral_sign(reading):
        return "numeral"
    if _is_unknown_logogram(reading, raw_type):
        return "unknown_logogram"
    return "syllabogram"


def _parse_ab_codes(ab_codes_str: str) -> List[str]:
    """Parse a hyphen-separated ab_codes string into individual sign IDs."""
    if not ab_codes_str:
        return []
    return [p.strip() for p in ab_codes_str.split("-") if p.strip()]


def _sign_id_from_ab_code(ab_code: str, sign_inventory: Dict[str, Any]) -> str:
    """Resolve an AB-code to a reading using the sign inventory.

    Falls back to the AB-code itself if no mapping is found.
    """
    # The sign_inventory maps reading -> {ab_codes: [...]}
    # We need the reverse: ab_code -> reading
    for reading, info in sign_inventory.items():
        for code in info.get("ab_codes", []):
            if code == ab_code:
                return reading
    return ab_code


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_context_corpus(
    corpus_path: str | Path,
) -> ContextCorpus:
    """Load the SigLA corpus with full sign-sequence context.

    Parses ``signs_sequence`` preserving the order of ALL sign types.
    Identifies named ideograms by "/" in reading, separately tracks unknown
    logograms (A-series codes without "/" names), and recognises numeral
    signs (A70x series).

    Sign-groups come from the existing word segmentation in the ``words``
    array, but segmentation_confidence is set to "divider_attested" since
    these entries represent segments separated by physical tablet dividers.

    Inscriptions with no ``signs_sequence`` data are skipped.

    Args:
        corpus_path: Path to ``data/sigla_full_corpus.json``.

    Returns:
        ContextCorpus with all inscriptions and inventories.

    Raises:
        FileNotFoundError: If the corpus file does not exist.
    """
    path = Path(corpus_path)
    if not path.exists():
        raise FileNotFoundError(f"Corpus file not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        raw_inscriptions = data.get("inscriptions", [])
        sign_inventory = data.get("sign_inventory", {})
    elif isinstance(data, list):
        raw_inscriptions = data
        sign_inventory = {}
    else:
        raise ValueError(f"Unexpected corpus format: {type(data)}")

    # Build reverse map: ab_code -> reading from sign_inventory
    ab_code_to_reading: Dict[str, str] = {}
    for reading, info in sign_inventory.items():
        for code in info.get("ab_codes", []):
            ab_code_to_reading[code] = reading

    ideogram_inventory: Set[str] = set()
    numeral_inventory: Set[str] = set()
    unknown_logogram_inventory: Set[str] = set()
    inscriptions: List[InscriptionContext] = []

    for raw_insc in raw_inscriptions:
        insc_id = raw_insc.get("id", "")
        insc_type = raw_insc.get("type", "")
        site = raw_insc.get("site", "")
        raw_seq = raw_insc.get("signs_sequence", [])

        # Skip inscriptions with no signs_sequence data
        if not raw_seq:
            continue

        # --- Parse full sign sequence ---
        full_sequence: List[SignOccurrence] = []
        ideograms: List[SignOccurrence] = []
        numerals: List[SignOccurrence] = []
        unknown_logos: List[SignOccurrence] = []

        for pos, raw_sign in enumerate(raw_seq):
            reading = raw_sign.get("reading", "")
            raw_type = raw_sign.get("type", "")
            ab_code = raw_sign.get("ab_code", None)

            classified_type = _classify_sign(reading, raw_type)

            occ = SignOccurrence(
                sign_id=reading,
                sign_type=classified_type,
                reading=reading,
                position_in_sequence=pos,
                ab_code=ab_code,
            )
            full_sequence.append(occ)

            if classified_type == "named_ideogram":
                ideograms.append(occ)
                ideogram_inventory.add(reading)
            elif classified_type == "numeral":
                numerals.append(occ)
                numeral_inventory.add(reading)
            elif classified_type == "unknown_logogram":
                unknown_logos.append(occ)
                unknown_logogram_inventory.add(reading)

        # --- Parse sign-groups from words array ---
        raw_words = raw_insc.get("words", [])
        sign_groups: List[SignGroup] = []

        for sg_pos, raw_word in enumerate(raw_words):
            ab_codes_str = raw_word.get("ab_codes", "")
            transliteration = raw_word.get("transliteration", "")
            has_damage = (
                raw_word.get("has_damage", False)
                or raw_word.get("has_damage_marker", False)
            )
            sign_readings_list = raw_word.get("sign_readings", [])

            # Parse individual ab-codes
            ab_codes = _parse_ab_codes(ab_codes_str)

            # Filter out damage markers
            real_codes = [
                c for c in ab_codes
                if c not in ("[?]", "?") and not c.startswith("[")
            ]
            if not real_codes:
                continue

            # Build SignOccurrences for the sign-group
            # Use sign_readings if available, otherwise resolve from ab_codes
            sg_signs: List[SignOccurrence] = []
            if sign_readings_list and len(sign_readings_list) == len(real_codes):
                for i, (code, rdg) in enumerate(
                    zip(real_codes, sign_readings_list)
                ):
                    sg_signs.append(SignOccurrence(
                        sign_id=rdg,
                        sign_type="syllabogram",
                        reading=rdg,
                        position_in_sequence=-1,  # not in full_sign_sequence indexing
                        ab_code=code,
                    ))
            else:
                for code in real_codes:
                    rdg = ab_code_to_reading.get(code, code)
                    sg_signs.append(SignOccurrence(
                        sign_id=rdg,
                        sign_type="syllabogram",
                        reading=rdg,
                        position_in_sequence=-1,
                        ab_code=code,
                    ))

            sign_ids_tuple = tuple(
                s.reading for s in sg_signs
            )

            sign_groups.append(SignGroup(
                signs=sg_signs,
                sign_ids=sign_ids_tuple,
                ab_codes_str=ab_codes_str,
                transliteration=transliteration,
                has_damage=has_damage,
                # All entries in the corpus "words" array represent segments
                # separated by physical dividers on the tablet.
                segmentation_confidence="divider_attested",
                inscription_id=insc_id,
                position_in_inscription=sg_pos,
            ))

        inscriptions.append(InscriptionContext(
            id=insc_id,
            type=insc_type,
            site=site,
            full_sign_sequence=full_sequence,
            sign_groups=sign_groups,
            ideograms_in_sequence=ideograms,
            numerals_in_sequence=numerals,
            unknown_logograms_in_sequence=unknown_logos,
        ))

    return ContextCorpus(
        inscriptions=inscriptions,
        ideogram_inventory=ideogram_inventory,
        numeral_inventory=numeral_inventory,
        unknown_logogram_inventory=unknown_logogram_inventory,
    )
