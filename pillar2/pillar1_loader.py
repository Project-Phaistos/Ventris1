"""Loader for Pillar 1 output JSON.

Reads and validates the Pillar 1 interface contract, providing typed
dataclasses for downstream consumption by Pillar 2 modules.

The Pillar 1 output contains:
- Grid assignments (sign_id -> consonant_class, vowel_class)
- Vowel inventory (signs identified as pure vowels)
- Phonotactic constraints (forbidden/favored bigrams)
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GridAssignment:
    """A sign's position in the C-V grid."""
    sign_id: str
    consonant_class: int
    vowel_class: int
    confidence: float
    evidence_count: int = 0


@dataclass
class VowelSign:
    """A sign identified as a pure vowel by Pillar 1."""
    sign_id: str
    enrichment_score: float
    confidence: float


@dataclass
class PhonotacticConstraint:
    """A forbidden or favored bigram from phonotactic analysis."""
    sign_i: str
    sign_j: str
    type: str  # "forbidden" or "favored"
    observed: int = 0
    expected: float = 0.0
    std_residual: float = 0.0
    p_value_corrected: float = 1.0


@dataclass
class Pillar1Output:
    """Complete Pillar 1 output for Pillar 2 consumption."""
    # Grid
    grid_assignments: List[GridAssignment]
    consonant_count: int
    vowel_count: int
    grid_method: str

    # Vowel inventory
    vowel_signs: List[VowelSign]
    vowel_sign_ids: List[str]

    # Phonotactic constraints
    forbidden_bigrams: List[PhonotacticConstraint]
    favored_bigrams: List[PhonotacticConstraint]

    # Lookups (built on load)
    sign_to_grid: Dict[str, GridAssignment] = field(default_factory=dict)
    favored_bigram_set: set = field(default_factory=set)
    forbidden_bigram_set: set = field(default_factory=set)

    # Metadata
    corpus_hash: str = ""
    config_hash: str = ""
    pillar1_hash: str = ""


_REQUIRED_KEYS = {"metadata", "vowel_inventory", "grid", "phonotactics"}


def load_pillar1(path: str | Path) -> Pillar1Output:
    """Load and validate the Pillar 1 output JSON.

    Args:
        path: Path to results/pillar1_output.json

    Returns:
        Pillar1Output with typed dataclasses and prebuilt lookups.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If required keys are missing or data is malformed.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pillar 1 output not found: {path}")

    # Compute hash of the file for provenance
    raw_bytes = path.read_bytes()
    pillar1_hash = hashlib.sha256(raw_bytes).hexdigest()

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate required keys
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(
            f"Pillar 1 output missing required keys: {missing}. "
            f"Found: {set(data.keys())}"
        )

    # --- Parse grid ---
    grid_data = data["grid"]
    consonant_count = grid_data.get("consonant_count", 0)
    vowel_count = grid_data.get("vowel_count", 0)
    grid_method = grid_data.get("method", "unknown")

    grid_assignments: List[GridAssignment] = []
    for a in grid_data.get("assignments", []):
        grid_assignments.append(GridAssignment(
            sign_id=a["sign_id"],
            consonant_class=a["consonant_class"],
            vowel_class=a["vowel_class"],
            confidence=a.get("confidence", 0.0),
            evidence_count=a.get("evidence_count", 0),
        ))

    # --- Parse vowel inventory ---
    vowel_data = data["vowel_inventory"]
    vowel_signs: List[VowelSign] = []
    for s in vowel_data.get("signs", []):
        vowel_signs.append(VowelSign(
            sign_id=s["sign_id"],
            enrichment_score=s.get("enrichment_score", 0.0),
            confidence=s.get("confidence", 0.0),
        ))
    vowel_sign_ids = [vs.sign_id for vs in vowel_signs]

    # --- Parse phonotactic constraints ---
    phon_data = data["phonotactics"]

    forbidden_bigrams: List[PhonotacticConstraint] = []
    for b in phon_data.get("forbidden_bigrams", []):
        forbidden_bigrams.append(PhonotacticConstraint(
            sign_i=b["sign_i"],
            sign_j=b["sign_j"],
            type="forbidden",
            observed=b.get("observed", 0),
            expected=b.get("expected", 0.0),
            std_residual=b.get("std_residual", 0.0),
            p_value_corrected=b.get("p_value_corrected", 1.0),
        ))

    favored_bigrams: List[PhonotacticConstraint] = []
    for b in phon_data.get("favored_bigrams", []):
        favored_bigrams.append(PhonotacticConstraint(
            sign_i=b["sign_i"],
            sign_j=b["sign_j"],
            type="favored",
            observed=b.get("observed", 0),
            expected=b.get("expected", 0.0),
            std_residual=b.get("std_residual", 0.0),
            p_value_corrected=b.get("p_value_corrected", 1.0),
        ))

    # --- Build lookups ---
    sign_to_grid = {a.sign_id: a for a in grid_assignments}
    favored_set = {(b.sign_i, b.sign_j) for b in favored_bigrams}
    forbidden_set = {(b.sign_i, b.sign_j) for b in forbidden_bigrams}

    # --- Metadata ---
    meta = data.get("metadata", {})
    corpus_hash = meta.get("corpus_hash", "")
    config_hash = meta.get("config_hash", "")

    return Pillar1Output(
        grid_assignments=grid_assignments,
        consonant_count=consonant_count,
        vowel_count=vowel_count,
        grid_method=grid_method,
        vowel_signs=vowel_signs,
        vowel_sign_ids=vowel_sign_ids,
        forbidden_bigrams=forbidden_bigrams,
        favored_bigrams=favored_bigrams,
        sign_to_grid=sign_to_grid,
        favored_bigram_set=favored_set,
        forbidden_bigram_set=forbidden_set,
        corpus_hash=corpus_hash,
        config_hash=config_hash,
        pillar1_hash=pillar1_hash,
    )
