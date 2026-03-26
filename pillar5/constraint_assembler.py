"""Pillar 5 Step 1: Assemble constraints from Pillars 1-4 per sign-group.

For each sign-group in the Linear A vocabulary, gathers:
- Phonological form (P1 grid assignments)
- Phonetic reading (LB values, CONSENSUS_ASSUMED)
- Morphological stem and class (P2)
- Word class and functional word status (P3)
- Semantic field anchors (P4)

Filters to matchable vocabulary: excludes functional words, requires at
least one constraint (semantic field, morphological class, or phonetic reading).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# Evidence provenance tags per Section 15 of standards
PROVENANCE_WEIGHTS = {
    "INDEPENDENT": 1.0,
    "INDEPENDENT_VALIDATED": 1.0,
    "CONSENSUS_CONFIRMED": 0.8,
    "CONSENSUS_ASSUMED": 0.5,
    "CONSENSUS_DEPENDENT": 0.3,
}


@dataclass
class SignGroupConstraints:
    """Constraints gathered for a single sign-group from Pillars 1-4."""

    sign_group_ids: List[str]
    frequency: int = 0

    # Pillar 1: phonological constraints
    grid_assignments: List[Dict[str, Any]] = field(default_factory=list)
    phonetic_reading_lb: Optional[str] = None
    vowel_count: int = 1
    phonotactic_violations: List[str] = field(default_factory=list)

    # Pillar 2: morphological constraints
    stem_sign_ids: Optional[List[str]] = None
    stem_ipa_lb: Optional[str] = None
    suffixes: List[List[str]] = field(default_factory=list)
    morphological_class: Optional[str] = None  # "declining" / "uninflected" / "unknown"

    # Pillar 3: grammatical constraints
    word_class: Optional[str] = None
    is_functional: bool = False
    functional_word_type: Optional[str] = None

    # Pillar 4: semantic constraints
    semantic_field: Optional[str] = None
    semantic_confidence: float = 0.0
    phonetic_anchors: Optional[Dict[str, str]] = None

    # Evidence provenance (highest-trust tag across all constraints)
    evidence_provenance: str = "CONSENSUS_DEPENDENT"

    @property
    def has_constraints(self) -> bool:
        """True if the sign-group has at least one matchable constraint."""
        return (
            self.semantic_field is not None
            or self.morphological_class is not None
            or self.phonetic_reading_lb is not None
        )

    @property
    def provenance_weight(self) -> float:
        """Numerical weight for this sign-group's evidence quality."""
        return PROVENANCE_WEIGHTS.get(self.evidence_provenance, 0.3)


@dataclass
class ConstrainedVocabulary:
    """The filtered set of sign-groups ready for vocabulary resolution."""

    sign_groups: List[SignGroupConstraints]
    n_total_in_corpus: int = 0
    n_functional_excluded: int = 0
    n_no_constraints: int = 0
    n_matchable: int = 0

    @property
    def acceptance_rate(self) -> float:
        """Fraction of corpus sign-groups that pass filtering."""
        if self.n_total_in_corpus == 0:
            return 0.0
        return self.n_matchable / self.n_total_in_corpus


def _load_json(path: str | Path) -> Dict[str, Any]:
    """Load a JSON file, returning empty dict if not found."""
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _sign_ids_to_key(sign_ids: List[str]) -> str:
    """Create a canonical lookup key from a list of sign IDs."""
    return "|".join(s.lower() for s in sign_ids)


def _build_sign_to_ipa(sign_to_ipa_path: str | Path) -> Dict[str, str]:
    """Load sign-to-IPA (LB values) mapping."""
    p = Path(sign_to_ipa_path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_ab_to_reading(corpus_path: str | Path) -> Dict[str, str]:
    """Build AB-code to reading mapping from the sigla corpus.

    The corpus sign_inventory maps reading -> {ab_codes: [...]}.
    P2/P3 use AB codes, P4 uses reading names. This bridge is needed
    to unify sign-groups across pillars.

    Returns:
        Dict mapping AB code (uppercase) to reading name (lowercase).
    """
    p = Path(corpus_path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        corpus = json.load(f)

    ab_to_reading: Dict[str, str] = {}
    sign_inv = corpus.get("sign_inventory", {})
    for reading, info in sign_inv.items():
        if isinstance(info, dict):
            for ab_code in info.get("ab_codes", []):
                ab_to_reading[ab_code] = reading
    return ab_to_reading


def _convert_ab_to_readings(
    sign_ids: List[str], ab_to_reading: Dict[str, str]
) -> List[str]:
    """Convert a list of AB-code sign IDs to reading-based IDs."""
    return [ab_to_reading.get(sid, sid) for sid in sign_ids]


def _sign_ids_to_ipa(sign_ids: List[str], sign_to_ipa: Dict[str, str]) -> Optional[str]:
    """Convert a list of sign IDs to an IPA string using LB values.

    Accepts both reading names ("ku") and AB codes ("AB81").
    Returns None if any sign has no LB reading.
    """
    parts = []
    for sid in sign_ids:
        # Try direct lookup (works for reading names like "ku")
        reading = sign_to_ipa.get(sid)
        if reading is None:
            # Try lowercase
            reading = sign_to_ipa.get(sid.lower())
        if reading is None:
            return None
        parts.append(reading)
    return "".join(parts)


def _extract_p2_index(
    p2_data: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Index Pillar 2 lexicon entries by sign-group key.

    Morphological class is inferred from segmentation: if the entry has
    suffixes, it's "declining"; otherwise "uninflected".

    Returns:
        lexicon_index mapping sign-group key -> entry dict (with added
        'inferred_morph_class' field).
    """
    lexicon_index: Dict[str, Dict[str, Any]] = {}

    for entry in p2_data.get("segmented_lexicon", []):
        word_ids = entry.get("word_sign_ids", [])
        key = _sign_ids_to_key(word_ids)

        # Infer morphological class from segmentation
        seg = entry.get("segmentation", {})
        suffixes = seg.get("suffixes", [])
        if suffixes:
            entry["inferred_morph_class"] = "declining"
        else:
            entry["inferred_morph_class"] = "uninflected"

        lexicon_index[key] = entry

    return lexicon_index


def _extract_p3_functional_words(
    p3_data: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Index Pillar 3 functional words by sign-group key."""
    result: Dict[str, Dict[str, Any]] = {}
    fw_data = p3_data.get("functional_words", {})
    words = fw_data.get("words", [])
    if isinstance(words, list):
        for w in words:
            key = _sign_ids_to_key(w.get("word_sign_ids", []))
            result[key] = w
    return result


def _extract_p4_anchors(
    p4_data: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Index Pillar 4 anchor vocabulary by sign-group key."""
    result: Dict[str, Dict[str, Any]] = {}
    for anchor in p4_data.get("anchor_vocabulary", []):
        key = _sign_ids_to_key(anchor.get("sign_group_ids", []))
        result[key] = anchor
    return result


def _collect_all_sign_groups(
    p2_data: Dict[str, Any],
    p4_data: Dict[str, Any],
) -> Dict[str, List[str]]:
    """Collect all unique sign-groups from P2 and P4 outputs."""
    groups: Dict[str, List[str]] = {}

    for entry in p2_data.get("segmented_lexicon", []):
        ids = entry.get("word_sign_ids", [])
        key = _sign_ids_to_key(ids)
        if key and key not in groups:
            groups[key] = ids

    for anchor in p4_data.get("anchor_vocabulary", []):
        ids = anchor.get("sign_group_ids", [])
        key = _sign_ids_to_key(ids)
        if key and key not in groups:
            groups[key] = ids

    return groups


def _resolve_provenance(
    has_independent: bool,
    has_consensus_confirmed: bool,
    has_consensus_assumed: bool,
) -> str:
    """Determine the best evidence provenance tag for a sign-group."""
    if has_independent:
        return "INDEPENDENT"
    if has_consensus_confirmed:
        return "CONSENSUS_CONFIRMED"
    if has_consensus_assumed:
        return "CONSENSUS_ASSUMED"
    return "CONSENSUS_DEPENDENT"


def assemble_constraints(
    p1_path: str | Path,
    p2_path: str | Path,
    p3_path: str | Path,
    p4_path: str | Path,
    sign_to_ipa_path: str | Path = "data/sign_to_ipa.json",
    corpus_path: str | Path = "data/sigla_full_corpus.json",
) -> ConstrainedVocabulary:
    """Assemble constraints from all four upstream pillars.

    Args:
        p1_path: Path to pillar1_output.json
        p2_path: Path to pillar2_output.json
        p3_path: Path to pillar3_output.json
        p4_path: Path to pillar4_output.json
        sign_to_ipa_path: Path to LB sign-to-IPA mapping
        corpus_path: Path to sigla_full_corpus.json (for AB-to-reading mapping)

    Returns:
        ConstrainedVocabulary with filtered, constrained sign-groups.
    """
    p1_data = _load_json(p1_path)
    p2_data = _load_json(p2_path)
    p3_data = _load_json(p3_path)
    p4_data = _load_json(p4_path)
    sign_to_ipa = _build_sign_to_ipa(sign_to_ipa_path)
    ab_to_reading = _build_ab_to_reading(corpus_path)

    # Build indices
    p2_lexicon = _extract_p2_index(p2_data)
    p3_functional = _extract_p3_functional_words(p3_data)
    p4_anchors = _extract_p4_anchors(p4_data)

    # P1 grid assignments indexed by sign_id (AB codes)
    p1_grid = {}
    for assignment in p1_data.get("grid", {}).get("assignments", []):
        sid = assignment.get("sign_id", "")
        p1_grid[sid.lower()] = assignment
        # Also index by reading name
        reading = ab_to_reading.get(sid)
        if reading:
            p1_grid[reading.lower()] = assignment

    vowel_count = p1_data.get("vowel_inventory", {}).get("count", 1)

    # Build P3 functional word index in BOTH namespaces
    # P3 uses AB codes, P4 uses readings — need to check both
    p3_func_by_reading: Dict[str, Dict[str, Any]] = {}
    for key, fw in p3_functional.items():
        p3_func_by_reading[key] = fw
        # Also convert AB codes to readings for cross-referencing
        ab_ids = fw.get("word_sign_ids", [])
        reading_ids = _convert_ab_to_readings(ab_ids, ab_to_reading)
        reading_key = _sign_ids_to_key(reading_ids)
        if reading_key != key:
            p3_func_by_reading[reading_key] = fw

    # Collect all sign-groups from P2 (AB codes) and P4 (reading names)
    # Unify them using the AB-to-reading mapping
    all_groups: Dict[str, List[str]] = {}  # canonical key -> sign_ids
    ab_key_to_canonical: Dict[str, str] = {}  # AB-code key -> canonical key

    # P2 entries (AB codes) — convert to reading-based canonical keys
    for entry in p2_data.get("segmented_lexicon", []):
        ab_ids = entry.get("word_sign_ids", [])
        ab_key = _sign_ids_to_key(ab_ids)
        reading_ids = _convert_ab_to_readings(ab_ids, ab_to_reading)
        canonical_key = _sign_ids_to_key(reading_ids)
        if canonical_key and canonical_key not in all_groups:
            all_groups[canonical_key] = reading_ids
        ab_key_to_canonical[ab_key] = canonical_key

    # P4 entries (reading names) — already in canonical form
    for anchor in p4_data.get("anchor_vocabulary", []):
        ids = anchor.get("sign_group_ids", [])
        key = _sign_ids_to_key(ids)
        if key and key not in all_groups:
            all_groups[key] = ids

    # Re-index P2 lexicon by canonical (reading-based) keys
    p2_canonical: Dict[str, Dict[str, Any]] = {}
    for ab_key, entry_data in p2_lexicon.items():
        canonical = ab_key_to_canonical.get(ab_key, ab_key)
        p2_canonical[canonical] = entry_data

    constrained = []
    n_functional_excluded = 0
    n_no_constraints = 0

    for key, sign_ids in all_groups.items():
        # Check functional word exclusion (P3) in both namespaces
        is_functional = key in p3_func_by_reading
        if is_functional:
            n_functional_excluded += 1
            continue

        # Gather P1 grid assignments for each sign in this group
        grid_assignments = []
        for sid in sign_ids:
            ga = p1_grid.get(sid.lower())
            if ga is not None:
                grid_assignments.append(ga)

        # Phonetic reading from LB values (works with reading names)
        phonetic_reading = _sign_ids_to_ipa(sign_ids, sign_to_ipa)

        # P2 segmentation (look up by canonical key)
        p2_entry = p2_canonical.get(key, {})
        seg = p2_entry.get("segmentation", {})
        stem_ids_raw = seg.get("stem")
        # Convert stem AB codes to readings too
        stem_ids = (_convert_ab_to_readings(stem_ids_raw, ab_to_reading)
                    if stem_ids_raw else None)
        stem_ipa = _sign_ids_to_ipa(stem_ids, sign_to_ipa) if stem_ids else None
        suffixes = seg.get("suffixes", [])
        frequency = p2_entry.get("frequency", 0)

        # Morphological class (inferred from P2 segmentation)
        morph_class = p2_entry.get("inferred_morph_class")

        # P4 semantic anchor (already indexed by reading-based key)
        p4_anchor = p4_anchors.get(key)
        semantic_field = p4_anchor.get("semantic_field") if p4_anchor else None
        semantic_conf = p4_anchor.get("confidence", 0.0) if p4_anchor else 0.0
        phonetic_anch = p4_anchor.get("phonetic_anchors") if p4_anchor else None

        # Determine provenance
        has_independent = len(grid_assignments) > 0 or morph_class is not None
        has_consensus_confirmed = False
        has_consensus_assumed = phonetic_reading is not None
        provenance = _resolve_provenance(
            has_independent, has_consensus_confirmed, has_consensus_assumed
        )

        sg = SignGroupConstraints(
            sign_group_ids=sign_ids,
            frequency=frequency,
            grid_assignments=grid_assignments,
            phonetic_reading_lb=phonetic_reading,
            vowel_count=vowel_count,
            stem_sign_ids=stem_ids,
            stem_ipa_lb=stem_ipa,
            suffixes=suffixes,
            morphological_class=morph_class,
            semantic_field=semantic_field,
            semantic_confidence=semantic_conf,
            phonetic_anchors=phonetic_anch,
            evidence_provenance=provenance,
        )

        if not sg.has_constraints:
            n_no_constraints += 1
            continue

        constrained.append(sg)

    # Sort by frequency descending for deterministic ordering
    constrained.sort(key=lambda sg: (-sg.frequency, _sign_ids_to_key(sg.sign_group_ids)))

    return ConstrainedVocabulary(
        sign_groups=constrained,
        n_total_in_corpus=len(all_groups),
        n_functional_excluded=n_functional_excluded,
        n_no_constraints=n_no_constraints,
        n_matchable=len(constrained),
    )
