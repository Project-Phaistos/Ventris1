"""Linear B soft validation of independently derived grid.

Implements PRD Section 5.6: compares the independently constructed C-V grid
against the known Linear B phonetic values as a validation step. This is
NOT used as input to the grid construction — it is purely diagnostic.

The key metric is the Adjusted Rand Index (ARI) between:
- Independent consonant classes (from spectral clustering) vs. LB consonant classes
- Independent vowel classes (from grid assignment) vs. LB vowel classes

ARI = 1 means perfect agreement; ARI = 0 means no better than random;
ARI < 0 means worse than random (anti-correlated).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import numpy as np
from sklearn.metrics import adjusted_rand_score

from .grid_constructor import GridResult


@dataclass
class SignValidation:
    """Validation result for a single sign."""
    sign_id: str
    lb_reading: Optional[str]
    lb_consonant: Optional[str]
    lb_vowel: Optional[str]
    independent_consonant_class: int
    independent_vowel_class: int
    consonant_agrees: Optional[bool]  # None if no LB value
    vowel_agrees: Optional[bool]      # None if no LB value


@dataclass
class Disagreement:
    """A specific disagreement between independent and LB classification."""
    sign_id: str
    dimension: str  # "consonant" or "vowel"
    independent_class: int
    lb_class: str
    other_signs_in_independent_class: List[str]
    other_signs_in_lb_class: List[str]


@dataclass
class LBValidationResult:
    """Results of LB validation analysis (PRD Section 5.6)."""
    consonant_ari: float
    vowel_ari: float
    n_signs_with_lb_values: int
    n_signs_validated: int
    sign_validations: List[SignValidation]
    disagreements: List[Disagreement]
    # LB class summaries
    lb_consonant_classes: Dict[str, List[str]]  # consonant_letter -> [sign_ids]
    lb_vowel_classes: Dict[str, List[str]]      # vowel_letter -> [sign_ids]
    # Systematic patterns
    systematic_disagreements: List[str]  # Human-readable descriptions
    is_systematic: bool  # True if disagreements follow a pattern


def validate_against_lb(
    grid: GridResult,
    lb_validation_path: str | Path,
) -> LBValidationResult:
    """Validate the independent grid against Linear B phonetic values.

    Algorithm (PRD Section 5.6):
    1. Load sign_to_ipa.json mapping sign readings to IPA/CV values.
    2. Extract consonant letter and vowel letter from each CV reading.
    3. Group signs by LB consonant -> LB consonant classes.
    4. Group signs by LB vowel -> LB vowel classes.
    5. For signs that have both independent grid assignment AND LB values,
       compute ARI between the two classification systems.
    6. List and analyze disagreements.

    Args:
        grid: Grid construction results with consonant/vowel assignments.
        lb_validation_path: Path to sign_to_ipa.json.

    Returns:
        LBValidationResult with ARI scores and disagreement analysis.
    """
    lb_validation_path = Path(lb_validation_path)

    # --- Step 1: Load LB mappings ---
    with open(lb_validation_path, "r", encoding="utf-8") as f:
        sign_to_ipa = json.load(f)

    # --- Step 2: Parse CV structure from readings ---
    # Pure vowels: single letter (a, e, i, o, u) -> consonant=None, vowel=letter
    # CV signs: two+ letters (ta, ki, etc.) -> consonant=first part, vowel=last letter
    lb_consonant_map: Dict[str, Optional[str]] = {}  # reading -> consonant
    lb_vowel_map: Dict[str, Optional[str]] = {}      # reading -> vowel

    for reading, ipa_val in sign_to_ipa.items():
        consonant, vowel = _parse_cv(reading)
        lb_consonant_map[reading] = consonant
        lb_vowel_map[reading] = vowel

    # --- Step 3: Build grid assignment lookup ---
    # Map sign_id -> GridAssignment
    grid_lookup: Dict[str, object] = {}
    for assignment in grid.assignments:
        grid_lookup[assignment.sign_id] = assignment

    # --- Step 4: Match signs between grid and LB ---
    # The grid uses sign_ids (AB codes); sign_to_ipa uses readings.
    # We need to bridge these using the corpus sign inventory.
    # For now, try matching by reading (the SignToken.reading field).
    # Build reading -> sign_id mapping from grid assignments
    # Grid assignments use sign_ids; LB uses readings.
    # We try both: sign_id might be in sign_to_ipa, or the reading might be.

    sign_validations: List[SignValidation] = []
    matched_independent_consonants: List[int] = []
    matched_lb_consonants: List[str] = []
    matched_independent_vowels: List[int] = []
    matched_lb_vowels: List[str] = []

    # Build LB consonant and vowel class dictionaries
    lb_consonant_classes: Dict[str, List[str]] = {}
    lb_vowel_classes: Dict[str, List[str]] = {}

    for reading in sign_to_ipa:
        consonant = lb_consonant_map.get(reading)
        vowel = lb_vowel_map.get(reading)
        if consonant is not None:
            lb_consonant_classes.setdefault(consonant, []).append(reading)
        if vowel is not None:
            lb_vowel_classes.setdefault(vowel, []).append(reading)

    # For each grid assignment, try to find an LB match
    for assignment in grid.assignments:
        sign_id = assignment.sign_id
        lb_reading = None
        lb_consonant = None
        lb_vowel = None

        # Try to match: sign_id in sign_to_ipa (unlikely but possible)
        # or check all readings to find one whose sign maps to this sign_id
        # The most robust approach: iterate sign_to_ipa and check if reading
        # matches the sign_id pattern, or if we can reconstruct.
        # For LB, the reading IS the key in sign_to_ipa.
        # Grid signs use AB codes. We need a bridge.
        # Best effort: check if sign_id's reading appears in sign_to_ipa
        # by looking at the sign_inventory or the reading stored in the grid.

        # Direct match: sign_id is actually a reading (e.g., "a", "ta")
        if sign_id in sign_to_ipa:
            lb_reading = sign_id
        else:
            # Try matching by stripping "R_" prefix (from corpus_loader fallback)
            if sign_id.startswith("R_") and sign_id[2:] in sign_to_ipa:
                lb_reading = sign_id[2:]

        if lb_reading is not None:
            lb_consonant = lb_consonant_map.get(lb_reading)
            lb_vowel = lb_vowel_map.get(lb_reading)

        sv = SignValidation(
            sign_id=sign_id,
            lb_reading=lb_reading,
            lb_consonant=lb_consonant,
            lb_vowel=lb_vowel,
            independent_consonant_class=assignment.consonant_class,
            independent_vowel_class=assignment.vowel_class,
            consonant_agrees=None,
            vowel_agrees=None,
        )
        sign_validations.append(sv)

        # Collect matched pairs for ARI computation
        if lb_consonant is not None:
            matched_independent_consonants.append(assignment.consonant_class)
            matched_lb_consonants.append(lb_consonant)
        if lb_vowel is not None:
            matched_independent_vowels.append(assignment.vowel_class)
            matched_lb_vowels.append(lb_vowel)

    # --- Step 5: Compute ARI ---
    if len(matched_independent_consonants) >= 2:
        consonant_ari = adjusted_rand_score(
            matched_lb_consonants, matched_independent_consonants,
        )
    else:
        consonant_ari = 0.0

    if len(matched_independent_vowels) >= 2:
        vowel_ari = adjusted_rand_score(
            matched_lb_vowels, matched_independent_vowels,
        )
    else:
        vowel_ari = 0.0

    # --- Step 6: Identify disagreements ---
    # For consonant: signs with same LB consonant should have same independent class
    disagreements: List[Disagreement] = []
    _find_disagreements(
        sign_validations, "consonant", lb_consonant_classes, disagreements,
    )
    _find_disagreements(
        sign_validations, "vowel", lb_vowel_classes, disagreements,
    )

    # Mark consonant/vowel agreement on each sign validation
    _mark_agreement(sign_validations, lb_consonant_classes, lb_vowel_classes)

    # --- Step 7: Check if disagreements are systematic ---
    systematic_descriptions, is_systematic = _analyze_systematicity(
        disagreements, sign_validations,
    )

    n_with_lb = sum(1 for sv in sign_validations if sv.lb_reading is not None)

    return LBValidationResult(
        consonant_ari=consonant_ari,
        vowel_ari=vowel_ari,
        n_signs_with_lb_values=n_with_lb,
        n_signs_validated=len(sign_validations),
        sign_validations=sign_validations,
        disagreements=disagreements,
        lb_consonant_classes=lb_consonant_classes,
        lb_vowel_classes=lb_vowel_classes,
        systematic_disagreements=systematic_descriptions,
        is_systematic=is_systematic,
    )


def _parse_cv(reading: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a Linear B reading into consonant and vowel components.

    Examples:
        "a"   -> (None, "a")      # pure vowel
        "ta"  -> ("t", "a")
        "ki"  -> ("k", "i")
        "nwa" -> ("nw", "a")
        "*301" -> (None, None)    # unreadable sign
        "*56"  -> (None, None)

    Returns:
        (consonant, vowel) tuple. Either or both may be None.
    """
    if reading.startswith("*"):
        return (None, None)

    vowels = {"a", "e", "i", "o", "u"}

    # Pure vowel: single vowel letter
    if reading in vowels:
        return (None, reading)

    # CV sign: consonant(s) + vowel at end
    if len(reading) >= 2 and reading[-1] in vowels:
        consonant = reading[:-1]
        vowel = reading[-1]
        return (consonant, vowel)

    # Cannot parse
    return (None, None)


def _find_disagreements(
    validations: List[SignValidation],
    dimension: str,  # "consonant" or "vowel"
    lb_classes: Dict[str, List[str]],
    disagreements: List[Disagreement],
) -> None:
    """Find signs that are in the same LB class but different independent classes.

    For each LB class (e.g., all signs with consonant "t"), check if they were
    all assigned to the same independent class. If not, record disagreements.
    """
    # Build lookup from reading to validation
    reading_to_val: Dict[str, SignValidation] = {}
    for sv in validations:
        if sv.lb_reading is not None:
            reading_to_val[sv.lb_reading] = sv

    for lb_class_name, readings in lb_classes.items():
        # Get independent class assignments for signs in this LB class
        class_assignments: Dict[int, List[str]] = {}
        for reading in readings:
            sv = reading_to_val.get(reading)
            if sv is None:
                continue
            if dimension == "consonant":
                ind_class = sv.independent_consonant_class
            else:
                ind_class = sv.independent_vowel_class
            class_assignments.setdefault(ind_class, []).append(reading)

        # If signs in the same LB class are split across independent classes,
        # that's a disagreement
        if len(class_assignments) > 1:
            # Find the majority independent class
            majority_class = max(class_assignments, key=lambda k: len(class_assignments[k]))
            for ind_class, signs_in_class in class_assignments.items():
                if ind_class == majority_class:
                    continue
                for sign_reading in signs_in_class:
                    sv = reading_to_val[sign_reading]
                    disagreements.append(Disagreement(
                        sign_id=sv.sign_id,
                        dimension=dimension,
                        independent_class=ind_class,
                        lb_class=lb_class_name,
                        other_signs_in_independent_class=[
                            r for r in class_assignments[ind_class] if r != sign_reading
                        ],
                        other_signs_in_lb_class=[
                            r for r in readings if r != sign_reading
                        ],
                    ))


def _mark_agreement(
    validations: List[SignValidation],
    lb_consonant_classes: Dict[str, List[str]],
    lb_vowel_classes: Dict[str, List[str]],
) -> None:
    """Mark each sign validation with whether it agrees with LB classes.

    Agreement means: all signs sharing the same LB consonant/vowel also share
    the same independent consonant/vowel class.
    """
    # Build reading-to-validation lookup
    reading_to_val: Dict[str, SignValidation] = {}
    for sv in validations:
        if sv.lb_reading is not None:
            reading_to_val[sv.lb_reading] = sv

    # Check consonant agreement
    for lb_class_name, readings in lb_consonant_classes.items():
        matched_vals = [reading_to_val[r] for r in readings if r in reading_to_val]
        if len(matched_vals) < 2:
            for sv in matched_vals:
                sv.consonant_agrees = True  # Singleton — trivially agrees
            continue
        # All must have the same independent consonant class
        classes = {sv.independent_consonant_class for sv in matched_vals}
        agrees = len(classes) == 1
        for sv in matched_vals:
            sv.consonant_agrees = agrees

    # Check vowel agreement
    for lb_class_name, readings in lb_vowel_classes.items():
        matched_vals = [reading_to_val[r] for r in readings if r in reading_to_val]
        if len(matched_vals) < 2:
            for sv in matched_vals:
                sv.vowel_agrees = True
            continue
        classes = {sv.independent_vowel_class for sv in matched_vals}
        agrees = len(classes) == 1
        for sv in matched_vals:
            sv.vowel_agrees = agrees


def _analyze_systematicity(
    disagreements: List[Disagreement],
    validations: List[SignValidation],
) -> Tuple[List[str], bool]:
    """Analyze whether disagreements are systematic or sporadic.

    Systematic: disagreements cluster (e.g., two LB classes are consistently
    merged into one independent class, suggesting a real phonological difference).
    Sporadic: disagreements are scattered with no clear pattern.

    Returns:
        (list of descriptions, is_systematic flag)
    """
    if not disagreements:
        return ([], False)

    descriptions: List[str] = []

    # Group disagreements by (dimension, lb_class)
    by_class: Dict[Tuple[str, str], List[Disagreement]] = {}
    for d in disagreements:
        key = (d.dimension, d.lb_class)
        by_class.setdefault(key, []).append(d)

    # Check for merged classes: multiple LB classes mapping to the same
    # independent class
    by_ind_class: Dict[Tuple[str, int], set] = {}
    for d in disagreements:
        key = (d.dimension, d.independent_class)
        by_ind_class.setdefault(key, set()).add(d.lb_class)

    systematic_count = 0
    for (dim, ind_class), lb_classes_set in by_ind_class.items():
        if len(lb_classes_set) >= 2:
            systematic_count += 1
            desc = (
                f"Independent {dim} class {ind_class} merges LB classes: "
                f"{sorted(lb_classes_set)}"
            )
            descriptions.append(desc)

    # Also check for split classes: one LB class split across multiple
    # independent classes
    for (dim, lb_class), disag_list in by_class.items():
        ind_classes = {d.independent_class for d in disag_list}
        if len(ind_classes) >= 2:
            desc = (
                f"LB {dim} class '{lb_class}' is split across independent "
                f"classes: {sorted(ind_classes)}"
            )
            descriptions.append(desc)

    # Heuristic: systematic if >= 30% of disagreements involve merged/split patterns
    is_systematic = systematic_count >= max(1, len(disagreements) // 3)

    return (descriptions, is_systematic)
