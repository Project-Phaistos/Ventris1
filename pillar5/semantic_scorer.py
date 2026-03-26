"""Pillar 5 Step 3: Semantic compatibility scoring.

For sign-groups with Pillar 4 semantic anchors, scores how well each
candidate cognate's gloss matches the constrained semantic field.

Method (from PRD Section 5.3):
- Exact semantic field match -> 1.0
- Same domain match (both COMMODITY) -> 0.5
- No match or no gloss -> null (not scored, not penalized)

Academic basis: Campbell & Poser 2008, "Language Classification: History and Method"
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


# Semantic domain taxonomy: keyword -> semantic domain
# Maps candidate word glosses to the same domain categories used by Pillar 4
_DOMAIN_KEYWORDS: Dict[str, str] = {
    # COMMODITY domains
    "fig": "COMMODITY:FIG",
    "grain": "COMMODITY:GRAIN",
    "wheat": "COMMODITY:GRAIN",
    "barley": "COMMODITY:GRAIN",
    "cereal": "COMMODITY:GRAIN",
    "olive": "COMMODITY:OLIVE",
    "oil": "COMMODITY:OLIVE",
    "wine": "COMMODITY:WINE",
    "grape": "COMMODITY:WINE",
    "vine": "COMMODITY:WINE",
    "sheep": "COMMODITY:SHEEP",
    "goat": "COMMODITY:GOAT",
    "cattle": "COMMODITY:CATTLE",
    "ox": "COMMODITY:CATTLE",
    "cow": "COMMODITY:CATTLE",
    "bull": "COMMODITY:CATTLE",
    "pig": "COMMODITY:PIG",
    "swine": "COMMODITY:PIG",
    "honey": "COMMODITY:HONEY",
    "cloth": "COMMODITY:CLOTH",
    "textile": "COMMODITY:CLOTH",
    "wool": "COMMODITY:CLOTH",
    "bronze": "COMMODITY:METAL",
    "copper": "COMMODITY:METAL",
    "gold": "COMMODITY:METAL",
    "silver": "COMMODITY:METAL",
    "metal": "COMMODITY:METAL",
    "iron": "COMMODITY:METAL",
    "tin": "COMMODITY:METAL",
    "food": "COMMODITY",
    "fruit": "COMMODITY",
    "plant": "COMMODITY",
    "seed": "COMMODITY",
    "crop": "COMMODITY",
    "herb": "COMMODITY",
    "tree": "COMMODITY",

    # PLACE domains
    "city": "PLACE",
    "town": "PLACE",
    "mountain": "PLACE",
    "island": "PLACE",
    "land": "PLACE",
    "country": "PLACE",
    "region": "PLACE",
    "sea": "PLACE",
    "river": "PLACE",
    "field": "PLACE",

    # PERSON domains
    "man": "PERSON",
    "woman": "PERSON",
    "person": "PERSON",
    "king": "PERSON",
    "queen": "PERSON",
    "lord": "PERSON",
    "servant": "PERSON",
    "slave": "PERSON",
    "child": "PERSON",
    "son": "PERSON",
    "daughter": "PERSON",
    "father": "PERSON",
    "mother": "PERSON",
    "brother": "PERSON",
    "sister": "PERSON",
    "priest": "PERSON",
    "scribe": "PERSON",
    "craftsman": "PERSON",
    "worker": "PERSON",

    # TRANSACTION domains
    "total": "TRANSACTION:TOTAL",
    "sum": "TRANSACTION:TOTAL",
    "count": "TRANSACTION:COUNT",
    "number": "TRANSACTION:COUNT",
    "give": "TRANSACTION",
    "receive": "TRANSACTION",
    "pay": "TRANSACTION",
    "owe": "TRANSACTION",
    "tribute": "TRANSACTION",
    "offering": "TRANSACTION",
    "measure": "TRANSACTION",
    "weight": "TRANSACTION",
    "quantity": "TRANSACTION",
}


def _get_domain(semantic_field: str) -> Optional[str]:
    """Extract the top-level domain from a semantic field.

    E.g., "COMMODITY:FIG" -> "COMMODITY", "PLACE:PHAISTOS" -> "PLACE"
    """
    if not semantic_field:
        return None
    return semantic_field.split(":")[0]


def _classify_gloss(gloss: str) -> Optional[str]:
    """Map a gloss string to a semantic field via keyword matching.

    Returns the most specific match found, or None.
    """
    if not gloss:
        return None

    gloss_lower = gloss.lower()

    # Check exact keyword matches
    best_match = None
    best_specificity = 0

    for keyword, field in _DOMAIN_KEYWORDS.items():
        if keyword in gloss_lower:
            # More specific fields (with ":" separator) are preferred
            specificity = field.count(":") + 1
            if specificity > best_specificity:
                best_match = field
                best_specificity = specificity

    return best_match


def score_semantic_compatibility(
    anchor_semantic_field: Optional[str],
    candidate_gloss: Optional[str],
) -> Optional[float]:
    """Score how well a candidate word's meaning matches an anchor's semantic field.

    Args:
        anchor_semantic_field: The Pillar 4 semantic field (e.g., "COMMODITY:FIG")
        candidate_gloss: The candidate word's English gloss (e.g., "fig tree")

    Returns:
        1.0 for exact field match, 0.5 for same-domain match,
        0.0 for domain mismatch, or None if scoring is impossible
        (no anchor field or no gloss).
    """
    if anchor_semantic_field is None or candidate_gloss is None:
        return None

    candidate_field = _classify_gloss(candidate_gloss)
    if candidate_field is None:
        return None  # Gloss doesn't map to any known domain

    # Exact field match
    if candidate_field == anchor_semantic_field:
        return 1.0

    # Same top-level domain match
    anchor_domain = _get_domain(anchor_semantic_field)
    candidate_domain = _get_domain(candidate_field)
    if anchor_domain and candidate_domain and anchor_domain == candidate_domain:
        return 0.5

    # Domain mismatch
    return 0.0


def score_all_candidates(
    anchor_semantic_field: Optional[str],
    candidates: List[Tuple[str, Optional[str]]],
) -> List[Optional[float]]:
    """Score semantic compatibility for a list of candidate words.

    Args:
        anchor_semantic_field: The sign-group's semantic field from P4
        candidates: List of (word, gloss) tuples

    Returns:
        List of scores (float or None) aligned with input candidates.
    """
    return [
        score_semantic_compatibility(anchor_semantic_field, gloss)
        for _, gloss in candidates
    ]
