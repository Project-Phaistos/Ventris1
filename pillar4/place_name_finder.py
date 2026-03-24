"""Place name finder for Pillar 4 (Semantic Anchoring).

Searches for confirmed place names and extracts phonetic anchors.

PRD Section 5.4: Only place names listed in the config
(confirmed_place_names) are searched.  NO candidate place names are
generated -- that would be speculative.

Confirmed place names (communis opinio):
- PA-I-TO (AB03-AB28-AB05) = Phaistos (Evans 1909)
- I-DA (AB28-AB01) = Mount Ida (widely accepted)
- A-DI-KI-TE (AB08-AB07-AB67-AB04) = Dikte (widely accepted)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from pillar4.corpus_context_loader import (
    ContextCorpus,
    InscriptionContext,
    SignOccurrence,
)


# ---------------------------------------------------------------------------
# AB-code to reading map (for place name matching)
# ---------------------------------------------------------------------------

# Standard Linear B syllabogram correspondences (tier 1, communis opinio).
# Used to resolve AB-codes to readings for sequence matching.
_AB_TO_READING: Dict[str, str] = {
    "AB01": "da",
    "AB02": "ro",
    "AB03": "pa",
    "AB04": "te",
    "AB05": "to",
    "AB06": "na",
    "AB07": "di",
    "AB08": "a",
    "AB09": "se",
    "AB10": "u",
    "AB11": "po",
    "AB12": "so",
    "AB13": "me",
    "AB16": "qa",
    "AB17": "za",
    "AB22": "mi",  # Note: also CAPx logogram
    "AB24": "ne",
    "AB25": "a2",
    "AB26": "ru",
    "AB27": "re",
    "AB28": "i",
    "AB29": "pu2",
    "AB30": "ni",  # Note: also FIC logogram
    "AB31": "sa",
    "AB37": "ti",
    "AB38": "e",
    "AB39": "pi",
    "AB40": "wi",
    "AB41": "si",
    "AB44": "ke",
    "AB45": "de",
    "AB47": "mu",
    "AB48": "nwa",
    "AB49": "no",  # uncertain
    "AB50": "pu",
    "AB51": "du",
    "AB54": "wa",  # Note: also TELA logogram
    "AB56": "*56",
    "AB57": "ja",
    "AB58": "su",
    "AB59": "ta",
    "AB60": "ra",
    "AB61": "o",
    "AB65": "ju",
    "AB67": "ki",
    "AB69": "tu",
    "AB73": "mi",
    "AB74": "ze",
    "AB77": "ka",
    "AB78": "qe",
    "AB79": "*79",
    "AB80": "ma",
    "AB81": "ku",
    "AB82": "qif",  # uncertain
    "AB85": "au",  # Note: also SUS logogram
    "AB86": "ra2",
    "AB87": "two",  # uncertain
    "AB100": "VIR",
    "AB118": "*118",
    "AB120": "GRA",
    "AB122": "OLIV",
    "AB123": "*123",
    "AB131": "VIN",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class PhoneticAnchor:
    """A phonetic value anchored by a place name.

    Each sign in a confirmed place name has a confirmed phonetic value
    (from the Linear B correspondence).

    Attributes:
        ab_code: The AB-code of the sign.
        reading: The syllabogram reading.
        phonetic_value: The phonetic value derived from Linear B.
        source: Citation for the identification.
        from_place_name: Which place name this anchor derives from.
    """
    ab_code: str
    reading: str
    phonetic_value: str
    source: str
    from_place_name: str


@dataclass
class PlaceNameMatch:
    """A confirmed place name found in the corpus.

    Attributes:
        name: Modern name (e.g. "Phaistos").
        sign_ids_config: AB-codes from config (e.g. ["AB03", "AB28", "AB05"]).
        target_readings: Resolved readings for matching.
        inscription_id: Where found.
        inscription_type: Type of inscription.
        site: Finding site.
        position_in_sequence: Starting position in signs_sequence.
        site_matches_expected: Whether the finding site matches the expected
            location (e.g. PA-I-TO found at Phaistos).
        confidence: Confidence from config.
        source: Citation from config.
    """
    name: str
    sign_ids_config: List[str]
    target_readings: List[str]
    inscription_id: str
    inscription_type: str
    site: str
    position_in_sequence: int
    site_matches_expected: bool
    confidence: float
    source: str


@dataclass
class PlaceNameNotFound:
    """A confirmed place name not found in the corpus.

    Attributes:
        name: Modern name.
        sign_ids_config: AB-codes from config.
        target_readings: Resolved readings that were searched for.
        confidence: Confidence from config.
        source: Citation from config.
    """
    name: str
    sign_ids_config: List[str]
    target_readings: List[str]
    confidence: float
    source: str


@dataclass
class PlaceNameResult:
    """Complete result of place name search.

    PRD Section 5.4 output.

    Attributes:
        found: Place names found in the corpus with match details.
        not_found: Place names not found.
        phonetic_anchors: Confirmed phonetic values from place names.
        site_matches: Summary of site-match checks.
    """
    found: List[PlaceNameMatch]
    not_found: List[PlaceNameNotFound]
    phonetic_anchors: List[PhoneticAnchor]
    site_matches: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Site matching heuristics
# ---------------------------------------------------------------------------

# Mapping from place name to expected site substrings (case-insensitive).
_EXPECTED_SITES: Dict[str, List[str]] = {
    "Phaistos": ["phaistos", "phaist"],
    "Mount Ida": ["ida"],
    "Dikte": ["dikte", "psychro", "lassithi", "lasithi"],
}


def _site_matches_expected(name: str, site: str) -> bool:
    """Check whether the finding site matches the expected location."""
    expected = _EXPECTED_SITES.get(name, [])
    if not expected:
        return False
    site_lower = site.lower()
    return any(exp in site_lower for exp in expected)


# ---------------------------------------------------------------------------
# AB-code resolution
# ---------------------------------------------------------------------------

def _resolve_ab_codes(
    ab_codes: List[str],
    corpus_inventory: Dict[str, str],
) -> List[str]:
    """Resolve a list of AB-codes to their readings.

    Uses the built-in _AB_TO_READING map first, falls back to the
    corpus sign inventory reverse map.
    """
    readings: List[str] = []
    for code in ab_codes:
        reading = _AB_TO_READING.get(code)
        if reading is None:
            reading = corpus_inventory.get(code, code)
        readings.append(reading)
    return readings


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def find_place_names(
    corpus: ContextCorpus,
    confirmed_place_names: Optional[List[Dict[str, Any]]] = None,
) -> PlaceNameResult:
    """Search for confirmed place names in the corpus.

    PRD Section 5.4: Only searches for place names listed in config.
    Does NOT generate candidate place names.

    For each confirmed place name:
    1. Resolve AB-code sequence to readings.
    2. Search the full signs_sequence of every inscription for an exact
       contiguous match.
    3. Record where found (site, type, position).
    4. Extract phonetic anchors: each sign gets a confirmed phonetic
       value.
    5. Check if finding site matches expected location.

    Args:
        corpus: Loaded ContextCorpus.
        confirmed_place_names: List of dicts from config, each with
            "sign_ids", "name", "source", "confidence".

    Returns:
        PlaceNameResult with found/not_found, phonetic anchors, site
        match summary.
    """
    if confirmed_place_names is None:
        confirmed_place_names = [
            {
                "sign_ids": ["AB03", "AB28", "AB05"],
                "name": "Phaistos",
                "source": "Evans 1909; confirmed by site provenance and Linear B PA-I-TO",
                "confidence": 0.90,
            },
            {
                "sign_ids": ["AB28", "AB01"],
                "name": "Mount Ida",
                "source": "Widely accepted; geographic context + Linear B I-DA",
                "confidence": 0.80,
            },
            {
                "sign_ids": ["AB08", "AB07", "AB67", "AB04"],
                "name": "Dikte",
                "source": "Widely accepted; attested at Psychro cave near Dikte + Linear B DI-KI-TE",
                "confidence": 0.80,
            },
        ]

    # Build a reverse map from the corpus sign inventory
    corpus_ab_map: Dict[str, str] = {}
    # We don't have direct access to the sign_inventory from ContextCorpus,
    # so we build from the _AB_TO_READING constant above.
    # The corpus_context_loader already resolved ab_codes for us.

    found: List[PlaceNameMatch] = []
    not_found: List[PlaceNameNotFound] = []
    all_anchors: List[PhoneticAnchor] = []
    site_match_summary: Dict[str, int] = {
        "total_matches": 0,
        "site_matches_expected": 0,
        "site_mismatches": 0,
    }

    # Track which phonetic anchors we've already added (avoid duplicates)
    anchor_keys: set = set()

    for pn in confirmed_place_names:
        sign_ids = pn["sign_ids"]
        name = pn["name"]
        source = pn["source"]
        confidence = pn.get("confidence", 0.5)

        # Resolve AB-codes to readings
        target_readings = _resolve_ab_codes(sign_ids, corpus_ab_map)
        tlen = len(target_readings)

        found_any = False

        for insc in corpus.inscriptions:
            seq = insc.full_sign_sequence
            n = len(seq)

            if n < tlen:
                continue

            # Search for exact contiguous reading match
            for start in range(n - tlen + 1):
                match = True
                for k in range(tlen):
                    if seq[start + k].reading != target_readings[k]:
                        match = False
                        break

                if match:
                    found_any = True
                    matches_site = _site_matches_expected(name, insc.site)

                    found.append(PlaceNameMatch(
                        name=name,
                        sign_ids_config=sign_ids,
                        target_readings=target_readings,
                        inscription_id=insc.id,
                        inscription_type=insc.type,
                        site=insc.site,
                        position_in_sequence=start,
                        site_matches_expected=matches_site,
                        confidence=confidence,
                        source=source,
                    ))

                    site_match_summary["total_matches"] += 1
                    if matches_site:
                        site_match_summary["site_matches_expected"] += 1
                    else:
                        site_match_summary["site_mismatches"] += 1

                    # Extract phonetic anchors
                    for k in range(tlen):
                        ab_code = sign_ids[k]
                        reading = target_readings[k]
                        anchor_key = (ab_code, reading, name)
                        if anchor_key not in anchor_keys:
                            anchor_keys.add(anchor_key)
                            all_anchors.append(PhoneticAnchor(
                                ab_code=ab_code,
                                reading=reading,
                                phonetic_value=reading,
                                source=source,
                                from_place_name=name,
                            ))

        if not found_any:
            not_found.append(PlaceNameNotFound(
                name=name,
                sign_ids_config=sign_ids,
                target_readings=target_readings,
                confidence=confidence,
                source=source,
            ))

    return PlaceNameResult(
        found=found,
        not_found=not_found,
        phonetic_anchors=all_anchors,
        site_matches=site_match_summary,
    )
