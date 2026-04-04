"""Kober triangulation: infer sign readings from alternation graph structure.

Implements the triangulation algorithm (PRD Section 6):
For each unknown sign U in the alternation graph, use its edges to known
(anchor) signs to infer consonant row, exclude/include vowel columns,
and produce candidate CV readings with confidence scores.

IMPORTANT: This module operates on AB codes, not readings.
Sign-groups are structural hypotheses, not confirmed "words."

Usage:
    python -m pillar1.scripts.kober_triangulation
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# When running from a worktree, data files are in the main repo
_MAIN_REPO = Path(r"C:\Users\alvin\Ventris1")
sys.path.insert(0, str(PROJECT_ROOT))

from pillar1.corpus_loader import load_corpus, CorpusData
from pillar1.alternation_detector import (
    detect_alternations,
    AlternationResult,
    AlternationPair,
)


# =========================================================================
# Data classes
# =========================================================================

@dataclass
class CandidateReading:
    """A candidate CV reading for an unknown sign."""
    reading: str          # e.g., "ta", "si"
    consonant: str        # e.g., "t", "" (empty for pure vowel)
    vowel: str            # e.g., "a", "e", "i", "o", "u"
    score: float          # Confidence score for this reading


@dataclass
class AlternationEvidence:
    """Evidence from alternation edges for a sign's identification."""
    n_anchor_alternations: int      # Total anchor edges
    n_anchor_non_alternations: int  # Total anchor non-edges (same-row)
    consonant_votes: Dict[str, float]  # consonant -> weighted vote count
    inferred_consonant: Optional[str]
    consonant_vote_margin: float    # Margin between top-1 and top-2
    excluded_vowels: List[str]      # Vowels excluded by alternation partners
    included_vowels: List[str]      # Vowels included by non-alternation partners
    surviving_vowels: List[str]     # Final vowel candidates


@dataclass
class GridCrossReference:
    """Cross-reference with Pillar 1 spectral grid assignment."""
    p1_consonant_class: Optional[int]
    p1_vowel_class: Optional[int]
    grid_consistent: bool
    consistency_detail: str


@dataclass
class SignReading:
    """Complete triangulation result for one sign."""
    sign_id: str
    top_reading: Optional[str]
    confidence: float
    candidate_readings: List[CandidateReading]
    alternation_evidence: AlternationEvidence
    grid_cross_reference: GridCrossReference
    identification_tier: str  # STRONG, PROBABLE, CONSTRAINED, INSUFFICIENT


# =========================================================================
# LB CV Grid — defines the consonant-vowel structure
# =========================================================================

# Full LB grid: AB_code -> (consonant, vowel)
# This is the reference grid used when LB signs serve as anchors.
LB_CV_GRID: Dict[str, Tuple[str, str]] = {
    "AB08": ("", "a"), "AB38": ("", "e"), "AB28": ("", "i"),
    "AB61": ("", "o"), "AB10": ("", "u"),
    "AB59": ("t", "a"), "AB04": ("t", "e"), "AB37": ("t", "i"),
    "AB05": ("t", "o"), "AB69": ("t", "u"),
    "AB01": ("d", "a"), "AB45": ("d", "e"), "AB07": ("d", "i"),
    "AB51": ("d", "u"),
    "AB80": ("m", "a"), "AB13": ("m", "e"), "AB73": ("m", "i"),
    "AB03": ("p", "a"), "AB39": ("p", "i"), "AB11": ("p", "o"),
    "AB50": ("p", "u"), "AB29": ("p", "u"),
    "AB60": ("r", "a"), "AB27": ("r", "e"), "AB53": ("r", "i"),
    "AB02": ("r", "o"), "AB26": ("r", "u"),
    "AB31": ("s", "a"), "AB09": ("s", "e"), "AB41": ("s", "i"),
    "AB58": ("s", "u"),
    "AB57": ("j", "a"), "AB46": ("j", "e"), "AB65": ("j", "u"),
    "AB77": ("k", "a"), "AB67": ("k", "i"), "AB81": ("k", "u"),
    "AB06": ("n", "a"), "AB24": ("n", "e"), "AB30": ("n", "i"),
    "AB55": ("n", "u"),
    "AB54": ("w", "a"), "AB40": ("w", "i"),
    "AB78": ("q", "e"), "AB16": ("q", "a"),
    "AB76": ("r", "a"),
    "AB23": ("m", "u"),
}

ALL_VOWELS = ["a", "e", "i", "o", "u"]


def parse_cv(reading: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a CV reading string into (consonant, vowel).

    Pure vowels return ("", vowel).
    CV syllables return (consonant, vowel).
    Returns (None, None) for unparseable readings.
    """
    vowels = {"a", "e", "i", "o", "u"}
    if reading in vowels:
        return ("", reading)
    # Handle special readings like "ra2", "pu2" etc.
    clean = reading.rstrip("0123456789")
    if len(clean) >= 2 and clean[-1] in vowels:
        return (clean[:-1], clean[-1])
    return (None, None)


# =========================================================================
# Core: Build alternation graph from AlternationResult
# =========================================================================

def build_alternation_graph(
    alt: AlternationResult,
) -> Tuple[Dict[str, Set[str]], Dict[Tuple[str, str], float]]:
    """Build adjacency structures from significant alternation pairs.

    Returns:
        adjacency: sign_id -> set of neighbors
        edge_weights: (sign_a, sign_b) -> weighted_stems  (canonical order: a < b)
    """
    adjacency: Dict[str, Set[str]] = defaultdict(set)
    edge_weights: Dict[Tuple[str, str], float] = {}

    for pair in alt.significant_pairs:
        a, b = pair.sign_a, pair.sign_b
        adjacency[a].add(b)
        adjacency[b].add(a)
        key = (min(a, b), max(a, b))
        edge_weights[key] = pair.weighted_stems

    return dict(adjacency), edge_weights


# =========================================================================
# Core: Triangulation algorithm
# =========================================================================

def triangulate_sign(
    sign_id: str,
    anchor_cv: Dict[str, Tuple[str, str]],
    adjacency: Dict[str, Set[str]],
    edge_weights: Dict[Tuple[str, str], float],
    p1_grid: Optional[Dict[str, Tuple[int, int]]] = None,
    suffix_weight: float = 1.0,
    initial_weight: float = 0.5,
) -> SignReading:
    """Run the 7-step triangulation algorithm for one sign.

    Args:
        sign_id: AB code of the sign to triangulate.
        anchor_cv: Map of AB code -> (consonant, vowel) for anchor signs.
        adjacency: Full alternation graph adjacency.
        edge_weights: Edge weights in canonical order.
        p1_grid: Optional Pillar 1 grid assignments {sign_id: (c_class, v_class)}.
        suffix_weight: Weight for suffix-position alternations (default 1.0).
        initial_weight: Weight for initial-position alternations (default 0.5).

    Returns:
        SignReading with candidate readings, evidence, and confidence.
    """
    neighbors = adjacency.get(sign_id, set())
    all_graph_signs = set(adjacency.keys())

    # ── Step 1: Collect anchor evidence ──
    k_alt: Dict[str, float] = {}      # anchor signs that U alternates with -> weight
    k_no_alt: Set[str] = set()        # anchor signs that U does NOT alternate with

    for anchor_id, (c, v) in anchor_cv.items():
        if anchor_id == sign_id:
            continue
        if anchor_id not in all_graph_signs:
            continue  # Anchor not in graph; no evidence either way

        key = (min(sign_id, anchor_id), max(sign_id, anchor_id))
        if anchor_id in neighbors:
            w = edge_weights.get(key, 1.0)
            k_alt[anchor_id] = w
        else:
            k_no_alt.add(anchor_id)

    n_anchor_alt = len(k_alt)
    n_anchor_no_alt = len(k_no_alt)

    # ── Step 2: Consonant row inference ──
    # Strategy: use edge-weight ranking. Signs in the same consonant row
    # should have the STRONGEST alternation edges with U (same prefix,
    # differing only in vowel = high stem count). Cross-row edges are weaker
    # (coincidental prefix sharing).
    #
    # Algorithm:
    # 1. Rank all anchor alternation edges by weight (descending).
    # 2. Take the top-K strongest edges (K = min(2*n_vowels, n_anchors/3)).
    #    These are most likely to be same-row partners.
    # 3. Vote by consonant among these top edges, weighted by edge weight.
    # 4. Also compute mean-weight per consonant for fallback when graph is
    #    sparse (few edges total).
    consonant_votes: Dict[str, float] = defaultdict(float)
    consonant_counts: Dict[str, int] = defaultdict(int)
    for anchor_id, w in k_alt.items():
        c, v = anchor_cv[anchor_id]
        if c is not None:
            consonant_votes[c] += w
            consonant_counts[c] += 1

    # Determine graph density to choose strategy
    n_possible = len([aid for aid in anchor_cv if aid != sign_id
                      and aid in all_graph_signs])
    graph_density = n_anchor_alt / n_possible if n_possible > 0 else 0.0

    if graph_density > 0.5 and n_anchor_alt > 10:
        # DENSE GRAPH: Use top-K strongest edges for voting
        # In a CV syllabary with ~5 vowels, a sign has at most ~4 same-row
        # partners. Use top-K = 2 * expected_row_partners.
        k = min(10, max(4, n_anchor_alt // 5))
        sorted_edges = sorted(k_alt.items(), key=lambda x: -x[1])[:k]

        top_k_votes: Dict[str, float] = defaultdict(float)
        top_k_counts: Dict[str, int] = defaultdict(int)
        for anchor_id, w in sorted_edges:
            c, v = anchor_cv[anchor_id]
            if c is not None:
                top_k_votes[c] += w
                top_k_counts[c] += 1

        # Mean-normalized among top-K
        consonant_score: Dict[str, float] = {}
        for c in top_k_votes:
            consonant_score[c] = top_k_votes[c] / top_k_counts[c]
    else:
        # SPARSE GRAPH: Use mean-weight per consonant with coverage bonus
        consonant_series_size: Dict[str, int] = defaultdict(int)
        for anchor_id, (c, v) in anchor_cv.items():
            if anchor_id != sign_id and c is not None:
                consonant_series_size[c] += 1

        consonant_score = {}
        for c in consonant_votes:
            series_sz = consonant_series_size.get(c, 1)
            mean_w = consonant_votes[c] / consonant_counts[c]
            coverage = consonant_counts[c] / series_sz
            consonant_score[c] = mean_w * coverage

    inferred_consonant: Optional[str] = None
    consonant_margin = 0.0
    if consonant_score:
        sorted_votes = sorted(consonant_score.items(), key=lambda x: -x[1])
        inferred_consonant = sorted_votes[0][0]
        top_vote = sorted_votes[0][1]
        second_vote = sorted_votes[1][1] if len(sorted_votes) > 1 else 0.0
        consonant_margin = (top_vote - second_vote) / top_vote if top_vote > 0 else 0.0

    # ── Step 3: Vowel column exclusion ──
    # U must be in a DIFFERENT vowel column from same-row alternation partners
    excluded_vowels: Set[str] = set()
    if inferred_consonant is not None:
        for anchor_id, w in k_alt.items():
            c, v = anchor_cv[anchor_id]
            if c == inferred_consonant and v is not None:
                excluded_vowels.add(v)

    # ── Step 4: Vowel column inclusion ──
    # U shares a vowel column with same-row signs it does NOT alternate with
    included_vowels: Set[str] = set()
    if inferred_consonant is not None:
        for anchor_id in k_no_alt:
            c, v = anchor_cv[anchor_id]
            if c == inferred_consonant and v is not None:
                included_vowels.add(v)

    # ── Step 5: Cross-reference with P1 grid ──
    p1_c_class = None
    p1_v_class = None
    grid_consistent = True
    consistency_detail = "no_p1_grid"

    if p1_grid and sign_id in p1_grid:
        p1_c_class, p1_v_class = p1_grid[sign_id]
        # Check if any anchor with same P1 consonant class has same inferred consonant
        p1_same_class_consonants: Set[str] = set()
        for anchor_id, (c, v) in anchor_cv.items():
            if anchor_id in p1_grid:
                ac, av = p1_grid[anchor_id]
                if ac == p1_c_class and c is not None:
                    p1_same_class_consonants.add(c)

        if inferred_consonant is not None and p1_same_class_consonants:
            if inferred_consonant in p1_same_class_consonants:
                grid_consistent = True
                consistency_detail = "consonant_agrees_with_p1"
            else:
                grid_consistent = False
                consistency_detail = (
                    f"inferred={inferred_consonant}, "
                    f"p1_class_consonants={sorted(p1_same_class_consonants)}"
                )
        else:
            consistency_detail = "insufficient_p1_overlap"

    grid_xref = GridCrossReference(
        p1_consonant_class=p1_c_class,
        p1_vowel_class=p1_v_class,
        grid_consistent=grid_consistent,
        consistency_detail=consistency_detail,
    )

    # ── Step 6: Compute candidate readings ──
    surviving_vowels: List[str] = []
    if included_vowels:
        # Intersection of included vowels minus excluded vowels
        surviving_vowels = sorted(v for v in included_vowels if v not in excluded_vowels)
    if not surviving_vowels:
        # Fall back: all vowels minus excluded
        surviving_vowels = sorted(v for v in ALL_VOWELS if v not in excluded_vowels)
    if not surviving_vowels:
        # Nothing excluded leaves everything
        surviving_vowels = list(ALL_VOWELS)

    candidate_readings: List[CandidateReading] = []
    if inferred_consonant is not None:
        for v in surviving_vowels:
            reading_str = f"{inferred_consonant}{v}" if inferred_consonant else v
            candidate_readings.append(CandidateReading(
                reading=reading_str,
                consonant=inferred_consonant,
                vowel=v,
                score=0.0,  # Scored in step 7 below
            ))

    # ── Step 7: Confidence scoring ──
    # Check for cell occupation (does another anchor already have this reading?)
    anchor_readings = set()
    for aid, (c, v) in anchor_cv.items():
        if c is not None and v is not None:
            anchor_readings.add(f"{c}{v}" if c else v)

    # Confidence combines three signals:
    # 1. Consonant margin: how dominant the top consonant is (0-1)
    # 2. Vowel constraint: how many vowels survived (1/n_surviving)
    # 3. Data sufficiency: min(n_anchor_alt / 5, 1.0)
    # Final formula: margin * (1/n_candidates) * data_sufficiency * grid * cell
    n_candidates_total = len(candidate_readings)
    data_sufficiency = min(n_anchor_alt / 5.0, 1.0)

    for cr in candidate_readings:
        cell_occupied = cr.reading in anchor_readings
        cr.score = compute_confidence(
            consonant_margin=consonant_margin,
            n_candidates=n_candidates_total,
            data_sufficiency=data_sufficiency,
            grid_consistent=grid_consistent,
            cell_occupied=cell_occupied,
        )

    # Sort by score descending
    candidate_readings.sort(key=lambda x: -x.score)

    # Determine tier
    top_reading = candidate_readings[0].reading if candidate_readings else None
    top_confidence = candidate_readings[0].score if candidate_readings else 0.0
    tier = classify_tier(top_confidence, n_anchor_alt, len(candidate_readings))

    evidence = AlternationEvidence(
        n_anchor_alternations=n_anchor_alt,
        n_anchor_non_alternations=n_anchor_no_alt,
        consonant_votes=dict(consonant_votes),
        inferred_consonant=inferred_consonant,
        consonant_vote_margin=consonant_margin,
        excluded_vowels=sorted(excluded_vowels),
        included_vowels=sorted(included_vowels),
        surviving_vowels=surviving_vowels,
    )

    return SignReading(
        sign_id=sign_id,
        top_reading=top_reading,
        confidence=top_confidence,
        candidate_readings=candidate_readings,
        alternation_evidence=evidence,
        grid_cross_reference=grid_xref,
        identification_tier=tier,
    )


def compute_confidence(
    consonant_margin: float = 1.0,
    n_candidates: int = 5,
    data_sufficiency: float = 1.0,
    grid_consistent: bool = True,
    cell_occupied: bool = False,
) -> float:
    """Compute confidence score for a candidate reading.

    Combines three orthogonal signals:
    1. Consonant margin: how dominant the inferred consonant is (0-1).
       High margin = strong consonant evidence.
    2. Vowel constraint: 1/n_candidates. Fewer surviving candidates = better.
       1 candidate = 1.0, 5 candidates = 0.2.
    3. Data sufficiency: min(n_anchor_alt/5, 1.0). Enough data to trust.

    Final: consonant_margin * vowel_constraint * data_sufficiency
           * grid_factor * cell_factor

    The score is clamped to [0.0, 1.0].

    Args:
        consonant_margin: Vote margin between top and second consonant (0-1).
        n_candidates: Number of surviving vowel candidates.
        data_sufficiency: min(n_anchor_alt / 5.0, 1.0).
        grid_consistent: Whether P1 grid agrees.
        cell_occupied: Whether this CV cell is already occupied by an anchor.

    Returns:
        Confidence score in [0.0, 1.0].
    """
    if n_candidates == 0:
        return 0.0

    vowel_constraint = 1.0 / n_candidates
    grid_factor = 1.0 if grid_consistent else 0.5
    cell_factor = 0.7 if cell_occupied else 1.0

    score = consonant_margin * vowel_constraint * data_sufficiency * grid_factor * cell_factor
    return min(max(score, 0.0), 1.0)


def classify_tier(
    confidence: float,
    n_anchor_alternations: int,
    n_candidates: int,
) -> str:
    """Classify identification tier.

    STRONG: confidence >= 0.8 AND >= 3 anchor alternations
    PROBABLE: confidence >= 0.6
    CONSTRAINED: 2-3 candidate readings remaining
    INSUFFICIENT: < 2 anchor alternations or no candidates
    """
    if n_anchor_alternations < 2 or n_candidates == 0:
        return "INSUFFICIENT"
    if confidence >= 0.8 and n_anchor_alternations >= 3:
        return "STRONG"
    if confidence >= 0.6:
        return "PROBABLE"
    if 1 <= n_candidates <= 3:
        return "CONSTRAINED"
    return "INSUFFICIENT"


# =========================================================================
# Batch triangulation
# =========================================================================

def triangulate_all(
    unknown_signs: List[str],
    anchor_cv: Dict[str, Tuple[str, str]],
    adjacency: Dict[str, Set[str]],
    edge_weights: Dict[Tuple[str, str], float],
    p1_grid: Optional[Dict[str, Tuple[int, int]]] = None,
) -> List[SignReading]:
    """Run triangulation for all unknown signs.

    Args:
        unknown_signs: List of AB codes to triangulate.
        anchor_cv: Map of anchor AB code -> (consonant, vowel).
        adjacency: Full alternation graph adjacency.
        edge_weights: Edge weights (canonical order).
        p1_grid: Optional P1 grid assignments.

    Returns:
        List of SignReading results, sorted by confidence descending.
    """
    results = []
    for sign_id in unknown_signs:
        result = triangulate_sign(
            sign_id, anchor_cv, adjacency, edge_weights, p1_grid,
        )
        results.append(result)

    results.sort(key=lambda r: -r.confidence)
    return results


# =========================================================================
# Leave-one-out validation (for anchor signs with known readings)
# =========================================================================

def leave_one_out_validation(
    anchor_cv: Dict[str, Tuple[str, str]],
    adjacency: Dict[str, Set[str]],
    edge_weights: Dict[Tuple[str, str], float],
    p1_grid: Optional[Dict[str, Tuple[int, int]]] = None,
) -> Dict[str, dict]:
    """Run leave-one-out cross-validation on all anchor signs.

    For each anchor sign:
    1. Remove it from the anchor set
    2. Triangulate using remaining anchors
    3. Check if the correct reading appears in top-1, top-3, top-5

    Returns:
        Dict mapping sign_id -> {
            "true_reading": str,
            "predicted_readings": List[str],
            "top1_correct": bool,
            "top3_correct": bool,
            "top5_correct": bool,
            "confidence": float,
            "tier": str,
            "n_anchor_alt": int,
        }
    """
    results = {}

    for holdout_id in sorted(anchor_cv.keys()):
        true_c, true_v = anchor_cv[holdout_id]
        if true_c is None or true_v is None:
            continue
        true_reading = f"{true_c}{true_v}" if true_c else true_v

        # Remove holdout from anchor set
        reduced_anchors = {k: v for k, v in anchor_cv.items() if k != holdout_id}

        # Triangulate
        result = triangulate_sign(
            holdout_id, reduced_anchors, adjacency, edge_weights, p1_grid,
        )

        predicted = [cr.reading for cr in result.candidate_readings]

        results[holdout_id] = {
            "true_reading": true_reading,
            "predicted_readings": predicted[:5],
            "top1_correct": len(predicted) >= 1 and predicted[0] == true_reading,
            "top3_correct": true_reading in predicted[:3],
            "top5_correct": true_reading in predicted[:5],
            "confidence": result.confidence,
            "tier": result.identification_tier,
            "n_anchor_alt": result.alternation_evidence.n_anchor_alternations,
            "inferred_consonant": result.alternation_evidence.inferred_consonant,
        }

    return results


# =========================================================================
# Serialization helpers
# =========================================================================

def sign_reading_to_dict(sr: SignReading) -> dict:
    """Convert a SignReading to a JSON-serializable dict."""
    return {
        "sign_id": sr.sign_id,
        "top_reading": sr.top_reading,
        "confidence": sr.confidence,
        "candidate_readings": [
            {
                "reading": cr.reading,
                "consonant": cr.consonant,
                "vowel": cr.vowel,
                "score": cr.score,
            }
            for cr in sr.candidate_readings
        ],
        "alternation_evidence": {
            "n_anchor_alternations": sr.alternation_evidence.n_anchor_alternations,
            "n_anchor_non_alternations": sr.alternation_evidence.n_anchor_non_alternations,
            "consonant_votes": sr.alternation_evidence.consonant_votes,
            "inferred_consonant": sr.alternation_evidence.inferred_consonant,
            "consonant_vote_margin": sr.alternation_evidence.consonant_vote_margin,
            "excluded_vowels": sr.alternation_evidence.excluded_vowels,
            "included_vowels": sr.alternation_evidence.included_vowels,
            "surviving_vowels": sr.alternation_evidence.surviving_vowels,
        },
        "grid_cross_reference": {
            "p1_consonant_class": sr.grid_cross_reference.p1_consonant_class,
            "p1_vowel_class": sr.grid_cross_reference.p1_vowel_class,
            "grid_consistent": sr.grid_cross_reference.grid_consistent,
            "consistency_detail": sr.grid_cross_reference.consistency_detail,
        },
        "identification_tier": sr.identification_tier,
    }


# =========================================================================
# Main: Linear A production run
# =========================================================================

def run_la_triangulation() -> dict:
    """Run Kober triangulation on the Linear A corpus.

    Returns the full output dict for serialization.
    """
    print("=" * 72)
    print("  KOBER TRIANGULATION — Linear A")
    print("=" * 72)

    # Load corpus and detect alternations
    corpus_path = PROJECT_ROOT / "data" / "sigla_full_corpus.json"
    if not corpus_path.exists():
        corpus_path = _MAIN_REPO / "data" / "sigla_full_corpus.json"
    corpus = load_corpus(str(corpus_path))
    print(f"Corpus: {corpus.total_inscriptions} inscriptions, "
          f"{corpus.total_words} sign-groups")

    alt = detect_alternations(corpus)
    print(f"Alternations: {alt.total_significant_pairs} significant pairs")

    adjacency, edge_weights = build_alternation_graph(alt)
    print(f"Graph: {len(adjacency)} nodes, {len(edge_weights)} edges")

    # Build anchor set from sign_to_ipa.json
    sign_ipa_path = PROJECT_ROOT / "data" / "sign_to_ipa.json"
    if not sign_ipa_path.exists():
        sign_ipa_path = _MAIN_REPO / "data" / "sign_to_ipa.json"
    with open(sign_ipa_path, "r", encoding="utf-8") as f:
        sign_to_ipa = json.load(f)

    # Map readings to AB codes
    ab_to_reading_map: Dict[str, str] = {}
    for reading, info in corpus.sign_inventory.items():
        if isinstance(info, dict):
            for ab in info.get("ab_codes", []):
                ab_to_reading_map[ab] = reading

    # Build anchor_cv: AB code -> (consonant, vowel)
    anchor_cv: Dict[str, Tuple[str, str]] = {}
    for reading, ipa in sign_to_ipa.items():
        # Find AB code for this reading
        ab_code = None
        for r, info in corpus.sign_inventory.items():
            if r == reading and isinstance(info, dict):
                for ab in info.get("ab_codes", []):
                    ab_code = ab
                    break
            if ab_code:
                break
        if ab_code is None:
            continue
        c, v = parse_cv(reading)
        if c is not None and v is not None:
            anchor_cv[ab_code] = (c, v)

    print(f"Anchors: {len(anchor_cv)} signs with known CV values")

    # Load P1 grid
    p1_grid: Dict[str, Tuple[int, int]] = {}
    p1_path = PROJECT_ROOT / "results" / "pillar1_v5_output.json"
    if not p1_path.exists():
        p1_path = _MAIN_REPO / "results" / "pillar1_v5_output.json"
    if p1_path.exists():
        with open(p1_path, "r", encoding="utf-8") as f:
            p1_data = json.load(f)
        for a in p1_data.get("grid", {}).get("assignments", []):
            p1_grid[a["sign_id"]] = (a["consonant_class"], a["vowel_class"])
        print(f"P1 grid: {len(p1_grid)} assignments loaded")

    # Identify unknown signs (in graph but not in anchors)
    unknown_signs = sorted(
        s for s in adjacency.keys()
        if s not in anchor_cv
    )
    print(f"Unknown signs to triangulate: {len(unknown_signs)}")

    # Run LOO validation on anchors first
    print("\n--- Leave-One-Out Validation (anchors) ---")
    loo_results = leave_one_out_validation(
        anchor_cv, adjacency, edge_weights, p1_grid,
    )
    n_tested = len(loo_results)
    n_top1 = sum(1 for r in loo_results.values() if r["top1_correct"])
    n_top3 = sum(1 for r in loo_results.values() if r["top3_correct"])
    n_top5 = sum(1 for r in loo_results.values() if r["top5_correct"])
    print(f"  Tested: {n_tested} anchors")
    print(f"  Top-1 accuracy: {n_top1}/{n_tested} = {n_top1/n_tested:.1%}")
    print(f"  Top-3 accuracy: {n_top3}/{n_tested} = {n_top3/n_tested:.1%}")
    print(f"  Top-5 accuracy: {n_top5}/{n_tested} = {n_top5/n_tested:.1%}")

    # Run triangulation on unknowns
    print("\n--- Triangulating unknown signs ---")
    readings = triangulate_all(
        unknown_signs, anchor_cv, adjacency, edge_weights, p1_grid,
    )

    tier_counts = defaultdict(int)
    for r in readings:
        tier_counts[r.identification_tier] += 1

    print(f"  STRONG: {tier_counts['STRONG']}")
    print(f"  PROBABLE: {tier_counts['PROBABLE']}")
    print(f"  CONSTRAINED: {tier_counts['CONSTRAINED']}")
    print(f"  INSUFFICIENT: {tier_counts['INSUFFICIENT']}")

    # Display top results
    print("\n--- Top Identifications ---")
    for r in readings[:20]:
        cands = ", ".join(cr.reading for cr in r.candidate_readings[:3])
        print(f"  {r.sign_id}: {r.top_reading} "
              f"(conf={r.confidence:.3f}, tier={r.identification_tier}, "
              f"candidates=[{cands}])")

    # Build output
    output = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "corpus_inscriptions": corpus.total_inscriptions,
            "corpus_sign_groups": corpus.total_words,
            "n_alternation_pairs": alt.total_significant_pairs,
            "n_graph_nodes": len(adjacency),
            "n_graph_edges": len(edge_weights),
            "n_anchors": len(anchor_cv),
            "n_unknown": len(unknown_signs),
        },
        "validation": {
            "leave_one_out": {
                "n_tested": n_tested,
                "precision_at_1": n_top1 / n_tested if n_tested > 0 else 0.0,
                "precision_at_3": n_top3 / n_tested if n_tested > 0 else 0.0,
                "precision_at_5": n_top5 / n_tested if n_tested > 0 else 0.0,
                "details": loo_results,
            },
        },
        "tier_summary": dict(tier_counts),
        "sign_readings": [sign_reading_to_dict(r) for r in readings],
    }

    return output


# =========================================================================
# CLI entry point
# =========================================================================

def main():
    """Run triangulation and write results."""
    output = run_la_triangulation()

    out_path = PROJECT_ROOT / "results" / "kober_triangulation_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
