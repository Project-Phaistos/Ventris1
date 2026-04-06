"""Compound suffix constraint extraction.

Extracts phonological constraints from multi-sign (compound) suffixes
in the P2 affix inventory. Two complementary analyses:

1. **Shared-head analysis**: Group compound suffixes by their first sign
   (head). The varying tail signs within each group share a consonant.
   Rationale: if head=AB01(da) produces tails ro, re, ra, the tails
   all have consonant /r/.

2. **Shared-tail analysis**: Group compound suffixes by their last sign
   (tail). The varying head signs within each group share a vowel.
   Rationale: if tail=AB27(re) produces heads da, ta, ra, ma, the heads
   all have vowel /a/.

Validated on Linear B ground truth:
  - Shared-head tails: 37.5% same-consonant (3.75x baseline of ~10%)
  - Shared-tail heads: 54.2% same-vowel (2.7x baseline of ~20%)

References:
  - Kober, A. (1946). "Inflection in Linear Class B." AJA 50(2).
  - Research log: docs/logs/2026-04-06-suffix-slot-redesign-plan.md
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CompoundSuffix:
    """A multi-sign suffix parsed into head + tail."""
    signs: List[str]
    head: str
    tail: str
    frequency: int
    n_distinct_stems: int

    @classmethod
    def from_affix_entry(cls, entry: Dict[str, Any]) -> Optional["CompoundSuffix"]:
        """Create from a P2 affix_inventory suffix entry.

        Returns None if the suffix has fewer than 2 signs or contains
        non-AB signs (e.g., R_ka logograms).
        """
        signs = entry.get("signs", [])
        if len(signs) < 2:
            return None
        # Skip suffixes containing logogram-type signs (R_ prefix)
        if any(s.startswith("R_") for s in signs):
            return None
        return cls(
            signs=signs,
            head=signs[0],
            tail=signs[-1],
            frequency=entry.get("frequency", 1),
            n_distinct_stems=entry.get("n_distinct_stems", 1),
        )


@dataclass
class ConstraintPair:
    """A phonological constraint between two signs."""
    sign_a: str
    sign_b: str
    constraint_type: str  # "same_consonant" or "same_vowel"
    confidence: float
    source_group_key: str  # The head or tail sign that groups them
    group_size: int  # Number of compound suffixes in the group
    evidence_suffixes: List[List[str]]  # The compound suffixes supporting this


@dataclass
class ConstraintGroup:
    """A group of signs sharing a head or tail, producing constraints."""
    group_key: str  # The shared head or tail sign
    group_type: str  # "shared_head" or "shared_tail"
    varying_signs: List[str]  # The tails (if shared_head) or heads (if shared_tail)
    compound_suffixes: List[CompoundSuffix]
    constraints: List[ConstraintPair]


@dataclass
class ValidationResult:
    """Linear B validation results."""
    lb_head_purity: float  # Fraction of shared-head tail pairs with same consonant
    lb_tail_purity: float  # Fraction of shared-tail head pairs with same vowel
    lb_head_pairs_total: int
    lb_head_pairs_same: int
    lb_tail_pairs_total: int
    lb_tail_pairs_same: int
    head_baseline: float  # Expected same-consonant rate under random grouping
    tail_baseline: float  # Expected same-vowel rate under random grouping
    null_head_purity: float  # Same-consonant rate with shuffled suffixes
    null_tail_purity: float  # Same-vowel rate with shuffled suffixes
    head_pass: bool
    tail_pass: bool
    null_pass: bool


@dataclass
class CompoundSuffixAnalysisResult:
    """Complete result of compound suffix analysis."""
    shared_head_groups: List[ConstraintGroup]
    shared_tail_groups: List[ConstraintGroup]
    shared_head_constraints: List[ConstraintPair]
    shared_tail_constraints: List[ConstraintPair]
    validation: Optional[ValidationResult]
    la_unknown_signs_constrained: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# CV parsing helper
# ---------------------------------------------------------------------------

def parse_cv(reading: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a CV reading into (consonant, vowel).

    Pure vowels return (None, vowel).
    CV syllables return (consonant, vowel).
    Unknown readings return (None, None).
    """
    vowels = {"a", "e", "i", "o", "u"}
    if reading in vowels:
        return (None, reading)
    if len(reading) >= 2 and reading[-1] in vowels:
        return (reading[:-1], reading[-1])
    return (None, None)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def extract_compound_suffixes(
    p2_data: Dict[str, Any],
) -> List[CompoundSuffix]:
    """Extract compound (multi-sign) suffixes from P2 affix inventory.

    Args:
        p2_data: Parsed pillar2_output.json.

    Returns:
        List of CompoundSuffix objects.
    """
    suffixes = p2_data.get("affix_inventory", {}).get("suffixes", [])
    result = []
    for entry in suffixes:
        cs = CompoundSuffix.from_affix_entry(entry)
        if cs is not None:
            result.append(cs)
    return result


def group_by_head(
    compound_suffixes: List[CompoundSuffix],
    min_group_size: int = 3,
) -> Dict[str, List[CompoundSuffix]]:
    """Group compound suffixes by their head (first sign).

    Args:
        compound_suffixes: List of compound suffixes.
        min_group_size: Minimum number of compound suffixes sharing a head
            to form a valid group.

    Returns:
        Dict mapping head sign to list of compound suffixes.
    """
    groups: Dict[str, List[CompoundSuffix]] = defaultdict(list)
    for cs in compound_suffixes:
        groups[cs.head].append(cs)
    return {k: v for k, v in groups.items() if len(v) >= min_group_size}


def group_by_tail(
    compound_suffixes: List[CompoundSuffix],
    min_group_size: int = 3,
) -> Dict[str, List[CompoundSuffix]]:
    """Group compound suffixes by their tail (last sign).

    Args:
        compound_suffixes: List of compound suffixes.
        min_group_size: Minimum number of compound suffixes sharing a tail
            to form a valid group.

    Returns:
        Dict mapping tail sign to list of compound suffixes.
    """
    groups: Dict[str, List[CompoundSuffix]] = defaultdict(list)
    for cs in compound_suffixes:
        groups[cs.tail].append(cs)
    return {k: v for k, v in groups.items() if len(v) >= min_group_size}


def _compute_confidence(group_size: int) -> float:
    """Compute confidence score for a constraint based on group size.

    Confidence scales with evidence:
      - group_size=3: 0.5 (minimum threshold)
      - group_size=4: 0.65
      - group_size=5+: 0.75+

    Formula: 0.5 + 0.25 * (1 - 1/group_size)
    Asymptotes at 0.75 as group_size -> infinity.
    """
    return 0.5 + 0.25 * (1.0 - 1.0 / group_size)


def emit_shared_head_constraints(
    head_groups: Dict[str, List[CompoundSuffix]],
) -> List[ConstraintGroup]:
    """Emit same-consonant constraints from shared-head groups.

    Within each shared-head group, the varying tails should share a
    consonant. Each pair of distinct tails produces one constraint.

    Args:
        head_groups: Dict from group_by_head().

    Returns:
        List of ConstraintGroup objects.
    """
    result = []
    for head, suffixes in sorted(head_groups.items()):
        # Collect unique tails
        tails = sorted(set(cs.tail for cs in suffixes))
        if len(tails) < 2:
            continue

        confidence = _compute_confidence(len(suffixes))
        constraints = []
        for a, b in combinations(tails, 2):
            # Find which suffixes support this pair
            evidence = [
                cs.signs for cs in suffixes
                if cs.tail in (a, b)
            ]
            constraints.append(ConstraintPair(
                sign_a=a,
                sign_b=b,
                constraint_type="same_consonant",
                confidence=confidence,
                source_group_key=head,
                group_size=len(suffixes),
                evidence_suffixes=evidence,
            ))

        result.append(ConstraintGroup(
            group_key=head,
            group_type="shared_head",
            varying_signs=tails,
            compound_suffixes=suffixes,
            constraints=constraints,
        ))
    return result


def emit_shared_tail_constraints(
    tail_groups: Dict[str, List[CompoundSuffix]],
) -> List[ConstraintGroup]:
    """Emit same-vowel constraints from shared-tail groups.

    Within each shared-tail group, the varying heads should share a
    vowel. Each pair of distinct heads produces one constraint.

    Args:
        tail_groups: Dict from group_by_tail().

    Returns:
        List of ConstraintGroup objects.
    """
    result = []
    for tail, suffixes in sorted(tail_groups.items()):
        # Collect unique heads
        heads = sorted(set(cs.head for cs in suffixes))
        if len(heads) < 2:
            continue

        confidence = _compute_confidence(len(suffixes))
        constraints = []
        for a, b in combinations(heads, 2):
            evidence = [
                cs.signs for cs in suffixes
                if cs.head in (a, b)
            ]
            constraints.append(ConstraintPair(
                sign_a=a,
                sign_b=b,
                constraint_type="same_vowel",
                confidence=confidence,
                source_group_key=tail,
                group_size=len(suffixes),
                evidence_suffixes=evidence,
            ))

        result.append(ConstraintGroup(
            group_key=tail,
            group_type="shared_tail",
            varying_signs=heads,
            compound_suffixes=suffixes,
            constraints=constraints,
        ))
    return result


# ---------------------------------------------------------------------------
# LB Validation
# ---------------------------------------------------------------------------

def validate_on_lb(
    compound_suffixes: List[CompoundSuffix],
    lb_sign_to_ipa: Dict[str, str],
    min_group_size: int = 2,
    seed: int = 42,
    n_shuffles: int = 1000,
) -> ValidationResult:
    """Validate compound suffix constraints against Linear B ground truth.

    Uses a lower min_group_size (2) for validation to include more data
    points, since we are evaluating statistical properties, not emitting
    production constraints.

    Args:
        compound_suffixes: List of compound suffixes.
        lb_sign_to_ipa: Dict mapping AB codes to IPA readings.
        min_group_size: Minimum group size for validation groups.
        seed: Random seed for null test.
        n_shuffles: Number of shuffle iterations for null test.

    Returns:
        ValidationResult with purity scores and pass/fail gates.
    """
    # --- Shared-head tails: check same-consonant ---
    head_groups = group_by_head(compound_suffixes, min_group_size=min_group_size)
    head_total = 0
    head_same = 0

    for head, suffixes in head_groups.items():
        tails = sorted(set(cs.tail for cs in suffixes))
        # Resolve to consonants via LB
        tail_consonants = []
        for t in tails:
            reading = lb_sign_to_ipa.get(t)
            if reading:
                c, v = parse_cv(reading)
                if c is not None:
                    tail_consonants.append(c)

        if len(tail_consonants) >= 2:
            for i in range(len(tail_consonants)):
                for j in range(i + 1, len(tail_consonants)):
                    head_total += 1
                    if tail_consonants[i] == tail_consonants[j]:
                        head_same += 1

    # --- Shared-tail heads: check same-vowel ---
    tail_groups = group_by_tail(compound_suffixes, min_group_size=min_group_size)
    tail_total = 0
    tail_same = 0

    for tail, suffixes in tail_groups.items():
        heads = sorted(set(cs.head for cs in suffixes))
        head_vowels = []
        for h in heads:
            reading = lb_sign_to_ipa.get(h)
            if reading:
                c, v = parse_cv(reading)
                if v is not None:
                    head_vowels.append(v)

        if len(head_vowels) >= 2:
            for i in range(len(head_vowels)):
                for j in range(i + 1, len(head_vowels)):
                    tail_total += 1
                    if head_vowels[i] == head_vowels[j]:
                        tail_same += 1

    lb_head_purity = head_same / head_total if head_total > 0 else 0.0
    lb_tail_purity = tail_same / tail_total if tail_total > 0 else 0.0

    # --- Compute baselines ---
    # Baseline: how often do random pairs of LB signs share C or V?
    all_signs_in_suffixes = set()
    for cs in compound_suffixes:
        all_signs_in_suffixes.update(cs.signs)

    consonants_pool = []
    vowels_pool = []
    for sign_id in all_signs_in_suffixes:
        reading = lb_sign_to_ipa.get(sign_id)
        if reading:
            c, v = parse_cv(reading)
            if c is not None:
                consonants_pool.append(c)
            if v is not None:
                vowels_pool.append(v)

    # Baseline same-consonant rate
    c_pairs_total = 0
    c_pairs_same = 0
    unique_consonants = list(set(consonants_pool))
    for i in range(len(consonants_pool)):
        for j in range(i + 1, len(consonants_pool)):
            c_pairs_total += 1
            if consonants_pool[i] == consonants_pool[j]:
                c_pairs_same += 1

    head_baseline = c_pairs_same / c_pairs_total if c_pairs_total > 0 else 0.0

    # Baseline same-vowel rate
    v_pairs_total = 0
    v_pairs_same = 0
    for i in range(len(vowels_pool)):
        for j in range(i + 1, len(vowels_pool)):
            v_pairs_total += 1
            if vowels_pool[i] == vowels_pool[j]:
                v_pairs_same += 1

    tail_baseline = v_pairs_same / v_pairs_total if v_pairs_total > 0 else 0.0

    # --- Null test: shuffle suffix assignments ---
    rng = random.Random(seed)
    null_head_purities = []
    null_tail_purities = []

    # Build a pool of (head, tail) pairs from actual compound suffixes
    actual_pairs = [(cs.head, cs.tail) for cs in compound_suffixes if len(cs.signs) == 2]
    all_heads = [p[0] for p in actual_pairs]
    all_tails = [p[1] for p in actual_pairs]

    for _ in range(n_shuffles):
        # Shuffle head-tail assignments
        shuffled_tails = all_tails[:]
        rng.shuffle(shuffled_tails)
        shuffled_pairs = list(zip(all_heads, shuffled_tails))

        # Re-group by head
        sh_groups: Dict[str, List[str]] = defaultdict(list)
        for h, t in shuffled_pairs:
            sh_groups[h].append(t)

        sh_total = 0
        sh_same = 0
        for h, tails in sh_groups.items():
            if len(tails) < min_group_size:
                continue
            unique_tails = sorted(set(tails))
            tail_cs = []
            for t in unique_tails:
                reading = lb_sign_to_ipa.get(t)
                if reading:
                    c, v = parse_cv(reading)
                    if c is not None:
                        tail_cs.append(c)
            if len(tail_cs) >= 2:
                for i in range(len(tail_cs)):
                    for j in range(i + 1, len(tail_cs)):
                        sh_total += 1
                        if tail_cs[i] == tail_cs[j]:
                            sh_same += 1
        null_head_purities.append(sh_same / sh_total if sh_total > 0 else 0.0)

        # Re-group by tail
        st_groups: Dict[str, List[str]] = defaultdict(list)
        for h, t in shuffled_pairs:
            st_groups[t].append(h)

        st_total = 0
        st_same = 0
        for t, heads in st_groups.items():
            if len(heads) < min_group_size:
                continue
            unique_heads = sorted(set(heads))
            head_vs = []
            for hh in unique_heads:
                reading = lb_sign_to_ipa.get(hh)
                if reading:
                    c, v = parse_cv(reading)
                    if v is not None:
                        head_vs.append(v)
            if len(head_vs) >= 2:
                for i in range(len(head_vs)):
                    for j in range(i + 1, len(head_vs)):
                        st_total += 1
                        if head_vs[i] == head_vs[j]:
                            st_same += 1
        null_tail_purities.append(st_same / st_total if st_total > 0 else 0.0)

    null_head_purity = sum(null_head_purities) / len(null_head_purities) if null_head_purities else 0.0
    null_tail_purity = sum(null_tail_purities) / len(null_tail_purities) if null_tail_purities else 0.0

    # --- Pass/fail gates ---
    # Head: >= 30% vs ~10% baseline
    head_pass = lb_head_purity >= 0.30 and (head_total >= 5)
    # Tail: >= 40% vs ~20% baseline
    tail_pass = lb_tail_purity >= 0.40 and (tail_total >= 5)
    # Null: shuffled purity should be <= 2x actual purity
    null_pass = (
        (null_head_purity < lb_head_purity * 0.8 if lb_head_purity > 0 else True)
        and (null_tail_purity < lb_tail_purity * 0.8 if lb_tail_purity > 0 else True)
    )

    return ValidationResult(
        lb_head_purity=lb_head_purity,
        lb_tail_purity=lb_tail_purity,
        lb_head_pairs_total=head_total,
        lb_head_pairs_same=head_same,
        lb_tail_pairs_total=tail_total,
        lb_tail_pairs_same=tail_same,
        head_baseline=head_baseline,
        tail_baseline=tail_baseline,
        null_head_purity=null_head_purity,
        null_tail_purity=null_tail_purity,
        head_pass=head_pass,
        tail_pass=tail_pass,
        null_pass=null_pass,
    )


# ---------------------------------------------------------------------------
# LA unknown signs
# ---------------------------------------------------------------------------

def find_la_unknown_signs_constrained(
    head_constraint_groups: List[ConstraintGroup],
    tail_constraint_groups: List[ConstraintGroup],
    lb_sign_to_ipa: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Identify Linear A signs that gain new constraints.

    A sign is "unknown" if it has no LB reading. This function collects
    all constraints touching at least one unknown sign.

    Args:
        head_constraint_groups: Shared-head constraint groups.
        tail_constraint_groups: Shared-tail constraint groups.
        lb_sign_to_ipa: Known LB readings (AB code -> IPA).

    Returns:
        List of dicts describing constrained unknown signs.
    """
    unknown_constraints: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    all_groups = (
        [(g, "same_consonant") for g in head_constraint_groups]
        + [(g, "same_vowel") for g in tail_constraint_groups]
    )

    for group, ctype in all_groups:
        for constraint in group.constraints:
            a_known = constraint.sign_a in lb_sign_to_ipa
            b_known = constraint.sign_b in lb_sign_to_ipa

            # At least one sign must be unknown
            if a_known and b_known:
                continue

            for sign_id in (constraint.sign_a, constraint.sign_b):
                if sign_id not in lb_sign_to_ipa:
                    # This unknown sign has a constraint
                    partner = (
                        constraint.sign_b
                        if sign_id == constraint.sign_a
                        else constraint.sign_a
                    )
                    partner_reading = lb_sign_to_ipa.get(partner)
                    unknown_constraints[sign_id].append({
                        "constraint_type": ctype,
                        "partner_sign": partner,
                        "partner_reading": partner_reading,
                        "confidence": constraint.confidence,
                        "source_group_key": constraint.source_group_key,
                    })

    result = []
    for sign_id, constraints in sorted(unknown_constraints.items()):
        result.append({
            "sign_id": sign_id,
            "n_constraints": len(constraints),
            "constraints": constraints,
        })
    return result


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_compound_suffix_analysis(
    p2_data: Dict[str, Any],
    lb_sign_to_ipa: Dict[str, str],
    min_group_size: int = 3,
    seed: int = 42,
    n_shuffles: int = 1000,
) -> CompoundSuffixAnalysisResult:
    """Run the complete compound suffix constraint extraction pipeline.

    Args:
        p2_data: Parsed pillar2_output.json.
        lb_sign_to_ipa: Dict mapping AB codes to IPA readings.
        min_group_size: Minimum group size for emitting production constraints.
        seed: Random seed for null test.
        n_shuffles: Number of shuffle iterations for null test.

    Returns:
        CompoundSuffixAnalysisResult with all constraints and validation.
    """
    # Step 1: Extract compound suffixes
    compound_suffixes = extract_compound_suffixes(p2_data)

    # Step 2: Group and emit constraints (production threshold)
    head_groups = group_by_head(compound_suffixes, min_group_size=min_group_size)
    tail_groups = group_by_tail(compound_suffixes, min_group_size=min_group_size)

    head_constraint_groups = emit_shared_head_constraints(head_groups)
    tail_constraint_groups = emit_shared_tail_constraints(tail_groups)

    # Flatten constraints
    all_head_constraints = []
    for g in head_constraint_groups:
        all_head_constraints.extend(g.constraints)

    all_tail_constraints = []
    for g in tail_constraint_groups:
        all_tail_constraints.extend(g.constraints)

    # Step 3: Validate on LB
    validation = validate_on_lb(
        compound_suffixes,
        lb_sign_to_ipa,
        min_group_size=2,  # Lower threshold for validation
        seed=seed,
        n_shuffles=n_shuffles,
    )

    # Step 4: Find LA unknown signs that gain constraints
    la_unknown = find_la_unknown_signs_constrained(
        head_constraint_groups,
        tail_constraint_groups,
        lb_sign_to_ipa,
    )

    return CompoundSuffixAnalysisResult(
        shared_head_groups=head_constraint_groups,
        shared_tail_groups=tail_constraint_groups,
        shared_head_constraints=all_head_constraints,
        shared_tail_constraints=all_tail_constraints,
        validation=validation,
        la_unknown_signs_constrained=la_unknown,
    )


# ---------------------------------------------------------------------------
# Output serialization
# ---------------------------------------------------------------------------

def serialize_result(result: CompoundSuffixAnalysisResult) -> Dict[str, Any]:
    """Serialize analysis result to JSON-compatible dict.

    Args:
        result: The analysis result.

    Returns:
        Dict suitable for json.dump().
    """
    def _serialize_constraint(c: ConstraintPair) -> Dict[str, Any]:
        return {
            "sign_a": c.sign_a,
            "sign_b": c.sign_b,
            "constraint_type": c.constraint_type,
            "confidence": round(c.confidence, 4),
            "source_group_key": c.source_group_key,
            "group_size": c.group_size,
            "evidence_suffixes": c.evidence_suffixes,
        }

    def _serialize_group(g: ConstraintGroup) -> Dict[str, Any]:
        return {
            "group_key": g.group_key,
            "group_type": g.group_type,
            "varying_signs": g.varying_signs,
            "n_suffixes": len(g.compound_suffixes),
            "constraints": [_serialize_constraint(c) for c in g.constraints],
        }

    output: Dict[str, Any] = {
        "shared_head_constraints": [
            _serialize_constraint(c) for c in result.shared_head_constraints
        ],
        "shared_tail_constraints": [
            _serialize_constraint(c) for c in result.shared_tail_constraints
        ],
        "shared_head_groups": [
            _serialize_group(g) for g in result.shared_head_groups
        ],
        "shared_tail_groups": [
            _serialize_group(g) for g in result.shared_tail_groups
        ],
    }

    if result.validation is not None:
        v = result.validation
        output["validation"] = {
            "lb_head_purity": round(v.lb_head_purity, 4),
            "lb_tail_purity": round(v.lb_tail_purity, 4),
            "lb_head_pairs_total": v.lb_head_pairs_total,
            "lb_head_pairs_same": v.lb_head_pairs_same,
            "lb_tail_pairs_total": v.lb_tail_pairs_total,
            "lb_tail_pairs_same": v.lb_tail_pairs_same,
            "head_baseline": round(v.head_baseline, 4),
            "tail_baseline": round(v.tail_baseline, 4),
            "null_head_purity": round(v.null_head_purity, 4),
            "null_tail_purity": round(v.null_tail_purity, 4),
            "head_pass": v.head_pass,
            "tail_pass": v.tail_pass,
            "null_pass": v.null_pass,
        }

    output["la_unknown_signs_constrained"] = result.la_unknown_signs_constrained

    return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(
    p2_path: str = "results/pillar2_output.json",
    lb_path: str = "pillar1/tests/fixtures/linear_b_sign_to_ipa.json",
    output_path: str = "results/compound_suffix_constraints.json",
    min_group_size: int = 3,
    seed: int = 42,
) -> None:
    """Run compound suffix analysis and write results.

    Args:
        p2_path: Path to pillar2_output.json.
        lb_path: Path to linear_b_sign_to_ipa.json.
        output_path: Path for output JSON.
        min_group_size: Minimum group size for production constraints.
        seed: Random seed for null test.
    """
    p2_path_obj = Path(p2_path)
    lb_path_obj = Path(lb_path)

    if not p2_path_obj.exists():
        raise FileNotFoundError(f"P2 output not found: {p2_path}")
    if not lb_path_obj.exists():
        raise FileNotFoundError(f"LB sign-to-IPA not found: {lb_path}")

    with open(p2_path_obj, "r", encoding="utf-8") as f:
        p2_data = json.load(f)
    with open(lb_path_obj, "r", encoding="utf-8") as f:
        lb_sign_to_ipa = json.load(f)

    print("[CompoundSuffixAnalyzer] Running compound suffix analysis...")

    result = run_compound_suffix_analysis(
        p2_data=p2_data,
        lb_sign_to_ipa=lb_sign_to_ipa,
        min_group_size=min_group_size,
        seed=seed,
    )

    output = serialize_result(result)

    # Print summary
    v = result.validation
    print(f"  Compound suffixes found: {len(extract_compound_suffixes(p2_data))}")
    print(f"  Shared-head groups (>= {min_group_size}): {len(result.shared_head_groups)}")
    print(f"  Shared-tail groups (>= {min_group_size}): {len(result.shared_tail_groups)}")
    print(f"  Same-consonant constraints: {len(result.shared_head_constraints)}")
    print(f"  Same-vowel constraints: {len(result.shared_tail_constraints)}")
    if v is not None:
        print(f"  LB Validation:")
        print(f"    Head purity (same-C): {v.lb_head_purity:.1%} "
              f"({v.lb_head_pairs_same}/{v.lb_head_pairs_total}) "
              f"[baseline: {v.head_baseline:.1%}] "
              f"{'PASS' if v.head_pass else 'FAIL'}")
        print(f"    Tail purity (same-V): {v.lb_tail_purity:.1%} "
              f"({v.lb_tail_pairs_same}/{v.lb_tail_pairs_total}) "
              f"[baseline: {v.tail_baseline:.1%}] "
              f"{'PASS' if v.tail_pass else 'FAIL'}")
        print(f"    Null test: head={v.null_head_purity:.1%} "
              f"tail={v.null_tail_purity:.1%} "
              f"{'PASS' if v.null_pass else 'FAIL'}")
    print(f"  LA unknown signs with new constraints: "
          f"{len(result.la_unknown_signs_constrained)}")

    # Write output
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path_obj, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"  Output written to: {output_path}")


if __name__ == "__main__":
    main()
