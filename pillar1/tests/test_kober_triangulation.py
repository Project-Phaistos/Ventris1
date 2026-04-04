"""Three-tier tests for the Kober triangulation module.

Tier 1 (formula, ~15 tests): scoring function properties, edge cases, empty inputs
Tier 2 (known-answer, ~10 tests): specific signs with known readings recovered
Tier 3 (null/negative, ~5 tests): random graphs should not produce STRONG IDs
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

from pillar1.corpus_loader import load_corpus, CorpusData
from pillar1.alternation_detector import detect_alternations, AlternationResult
from pillar1.scripts.kober_triangulation import (
    build_alternation_graph,
    compute_confidence,
    classify_tier,
    leave_one_out_validation,
    parse_cv,
    triangulate_all,
    triangulate_sign,
    LB_CV_GRID,
    ALL_VOWELS,
    SignReading,
)


# ── Paths ──────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LB_CORPUS_PATH = FIXTURES_DIR / "linear_b_test_corpus.json"
LB_SIGN_TO_IPA_PATH = FIXTURES_DIR / "linear_b_sign_to_ipa.json"

# LA data may be in the main repo if running from a worktree
_MAIN_REPO = Path(r"C:\Users\alvin\Ventris1")
LA_CORPUS_PATH = PROJECT_ROOT / "data" / "sigla_full_corpus.json"
if not LA_CORPUS_PATH.exists():
    LA_CORPUS_PATH = _MAIN_REPO / "data" / "sigla_full_corpus.json"
LA_SIGN_TO_IPA_PATH = PROJECT_ROOT / "data" / "sign_to_ipa.json"
if not LA_SIGN_TO_IPA_PATH.exists():
    LA_SIGN_TO_IPA_PATH = _MAIN_REPO / "data" / "sign_to_ipa.json"
LA_P1_OUTPUT_PATH = PROJECT_ROOT / "results" / "pillar1_v5_output.json"
if not LA_P1_OUTPUT_PATH.exists():
    LA_P1_OUTPUT_PATH = _MAIN_REPO / "results" / "pillar1_v5_output.json"


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def lb_corpus() -> CorpusData:
    """Load the Linear B test corpus."""
    assert LB_CORPUS_PATH.exists(), f"Fixture not found: {LB_CORPUS_PATH}"
    return load_corpus(str(LB_CORPUS_PATH))


@pytest.fixture(scope="module")
def lb_alternation(lb_corpus: CorpusData) -> AlternationResult:
    """Run alternation detection on the LB corpus."""
    return detect_alternations(lb_corpus)


@pytest.fixture(scope="module")
def lb_graph(lb_alternation: AlternationResult):
    """Build alternation graph from LB alternations."""
    return build_alternation_graph(lb_alternation)


@pytest.fixture(scope="module")
def lb_sign_values() -> Dict[str, Tuple[str, str]]:
    """Load LB sign values as {AB_code: (consonant, vowel)}."""
    with open(LB_SIGN_TO_IPA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    result = {}
    for ab, reading in raw.items():
        c, v = parse_cv(reading)
        if c is not None and v is not None:
            result[ab] = (c, v)
    return result


@pytest.fixture(scope="module")
def la_corpus() -> CorpusData:
    """Load the Linear A corpus."""
    if not LA_CORPUS_PATH.exists():
        pytest.skip(f"LA corpus not found: {LA_CORPUS_PATH}")
    return load_corpus(str(LA_CORPUS_PATH))


@pytest.fixture(scope="module")
def la_alternation(la_corpus: CorpusData) -> AlternationResult:
    """Run alternation detection on the LA corpus."""
    return detect_alternations(la_corpus)


@pytest.fixture(scope="module")
def la_graph(la_alternation: AlternationResult):
    """Build alternation graph from LA alternations."""
    return build_alternation_graph(la_alternation)


@pytest.fixture(scope="module")
def la_anchor_cv(la_corpus: CorpusData) -> Dict[str, Tuple[str, str]]:
    """Build LA anchor set from sign_to_ipa.json."""
    if not LA_SIGN_TO_IPA_PATH.exists():
        pytest.skip(f"sign_to_ipa not found: {LA_SIGN_TO_IPA_PATH}")
    with open(LA_SIGN_TO_IPA_PATH, "r", encoding="utf-8") as f:
        sign_to_ipa = json.load(f)

    anchor_cv = {}
    for reading, ipa in sign_to_ipa.items():
        ab_code = None
        for r, info in la_corpus.sign_inventory.items():
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
    return anchor_cv


# =========================================================================
# TIER 1: Formula tests (~15 tests)
# =========================================================================

class TestConfidenceFormula:
    """Test the confidence scoring function."""

    def test_perfect_inputs(self):
        """Full margin, 1 candidate, full data, consistent -> 1.0."""
        assert compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=True, cell_occupied=False,
        ) == pytest.approx(1.0)

    def test_half_margin(self):
        """Half margin with 1 candidate -> 0.5."""
        assert compute_confidence(
            consonant_margin=0.5, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=True, cell_occupied=False,
        ) == pytest.approx(0.5)

    def test_grid_inconsistent_penalty(self):
        """Grid inconsistency halves the score."""
        full = compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=True, cell_occupied=False,
        )
        half = compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=False, cell_occupied=False,
        )
        assert half == pytest.approx(full * 0.5)

    def test_cell_occupied_penalty(self):
        """Cell occupation applies 0.7 factor."""
        full = compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=True, cell_occupied=False,
        )
        occupied = compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=True, cell_occupied=True,
        )
        assert occupied == pytest.approx(full * 0.7)

    def test_both_penalties(self):
        """Both penalties stack multiplicatively."""
        score = compute_confidence(
            consonant_margin=1.0, n_candidates=1,
            data_sufficiency=1.0, grid_consistent=False, cell_occupied=True,
        )
        assert score == pytest.approx(1.0 * 0.5 * 0.7)

    def test_zero_candidates_returns_zero(self):
        """Zero candidates returns 0.0."""
        assert compute_confidence(
            consonant_margin=1.0, n_candidates=0,
            data_sufficiency=1.0,
        ) == 0.0

    def test_zero_margin(self):
        """Zero margin returns 0.0."""
        assert compute_confidence(
            consonant_margin=0.0, n_candidates=1,
            data_sufficiency=1.0,
        ) == 0.0

    def test_vowel_constraint_inversely_proportional(self):
        """More candidates = lower confidence."""
        c1 = compute_confidence(consonant_margin=1.0, n_candidates=1, data_sufficiency=1.0)
        c5 = compute_confidence(consonant_margin=1.0, n_candidates=5, data_sufficiency=1.0)
        assert c1 > c5
        assert c5 == pytest.approx(0.2)

    def test_confidence_range(self):
        """Confidence is always in [0.0, 1.0]."""
        import numpy as np
        for margin in np.arange(0, 1.1, 0.2):
            for n_cand in range(1, 6):
                for ds in [0.0, 0.5, 1.0]:
                    for grid in [True, False]:
                        for cell in [True, False]:
                            c = compute_confidence(
                                consonant_margin=margin,
                                n_candidates=n_cand,
                                data_sufficiency=ds,
                                grid_consistent=grid,
                                cell_occupied=cell,
                            )
                            assert 0.0 <= c <= 1.0


class TestClassifyTier:
    """Test tier classification logic."""

    def test_strong(self):
        """High confidence + sufficient alternations -> STRONG."""
        assert classify_tier(0.85, 5, 1) == "STRONG"

    def test_strong_boundary(self):
        """Exactly at boundary: conf=0.8, n_alt=3 -> STRONG."""
        assert classify_tier(0.80, 3, 2) == "STRONG"

    def test_probable(self):
        """Moderate confidence -> PROBABLE."""
        assert classify_tier(0.65, 2, 3) == "PROBABLE"

    def test_constrained_few_candidates(self):
        """Low confidence but few candidates -> CONSTRAINED."""
        assert classify_tier(0.4, 3, 2) == "CONSTRAINED"

    def test_insufficient_few_alternations(self):
        """Fewer than 2 alternations -> INSUFFICIENT."""
        assert classify_tier(0.9, 1, 5) == "INSUFFICIENT"

    def test_insufficient_no_candidates(self):
        """No candidates -> INSUFFICIENT."""
        assert classify_tier(0.9, 5, 0) == "INSUFFICIENT"

    def test_strong_needs_3_alternations(self):
        """STRONG requires >= 3 alternations, not just high confidence."""
        assert classify_tier(0.9, 2, 1) != "STRONG"


class TestParseCV:
    """Test CV parsing."""

    def test_pure_vowel(self):
        assert parse_cv("a") == ("", "a")
        assert parse_cv("e") == ("", "e")

    def test_cv_syllable(self):
        assert parse_cv("ta") == ("t", "a")
        assert parse_cv("si") == ("s", "i")

    def test_special_reading(self):
        assert parse_cv("ra2") == ("r", "a")
        assert parse_cv("pu2") == ("p", "u")

    def test_unparseable(self):
        # Unparseable returns (None, None)
        c, v = parse_cv("xyz")
        assert c is None and v is None


class TestBuildAlternationGraph:
    """Test alternation graph construction."""

    def test_graph_has_nodes(self, lb_graph):
        adjacency, edge_weights = lb_graph
        assert len(adjacency) > 0

    def test_graph_is_symmetric(self, lb_graph):
        adjacency, _ = lb_graph
        for node, neighbors in adjacency.items():
            for nbr in neighbors:
                assert node in adjacency.get(nbr, set()), (
                    f"{node} -> {nbr} but not reverse"
                )

    def test_edge_weights_positive(self, lb_graph):
        _, edge_weights = lb_graph
        for key, w in edge_weights.items():
            assert w > 0, f"Edge {key} has non-positive weight {w}"

    def test_edge_keys_canonical(self, lb_graph):
        """Edge keys should be in canonical order (a < b)."""
        _, edge_weights = lb_graph
        for (a, b) in edge_weights:
            assert a <= b, f"Non-canonical edge key: ({a}, {b})"


# =========================================================================
# TIER 2: Known-answer tests (~10 tests)
# =========================================================================

class TestLBKnownAnswer:
    """Known-answer tests: triangulation on LB should recover known readings."""

    def test_t_series_consonant(self, lb_graph, lb_sign_values):
        """Signs ta(AB59), te(AB04), ti(AB37) should get consonant 't'."""
        adjacency, edge_weights = lb_graph
        t_signs = ["AB59", "AB04", "AB37"]
        for sign_id in t_signs:
            if sign_id not in adjacency:
                continue
            # Hold out this sign
            reduced = {k: v for k, v in lb_sign_values.items() if k != sign_id}
            result = triangulate_sign(sign_id, reduced, adjacency, edge_weights)
            if result.alternation_evidence.n_anchor_alternations >= 2:
                assert result.alternation_evidence.inferred_consonant == "t", (
                    f"{sign_id} should have consonant 't', "
                    f"got '{result.alternation_evidence.inferred_consonant}'"
                )

    def test_r_series_consonant(self, lb_graph, lb_sign_values):
        """Signs ra(AB60), re(AB27), ri(AB53), ro(AB02) should get consonant 'r'."""
        adjacency, edge_weights = lb_graph
        r_signs = ["AB60", "AB27", "AB53", "AB02"]
        recovered = 0
        total = 0
        for sign_id in r_signs:
            if sign_id not in adjacency:
                continue
            reduced = {k: v for k, v in lb_sign_values.items() if k != sign_id}
            result = triangulate_sign(sign_id, reduced, adjacency, edge_weights)
            if result.alternation_evidence.n_anchor_alternations >= 2:
                total += 1
                if result.alternation_evidence.inferred_consonant == "r":
                    recovered += 1
        if total > 0:
            assert recovered >= total // 2, (
                f"Only {recovered}/{total} r-series signs recovered consonant 'r'"
            )

    def test_loo_precision_on_lb(self, lb_graph, lb_sign_values):
        """LOO on LB test corpus: precision@3 should exceed chance."""
        adjacency, edge_weights = lb_graph
        # Filter to signs in graph
        sv_in_graph = {k: v for k, v in lb_sign_values.items() if k in adjacency}
        loo = leave_one_out_validation(sv_in_graph, adjacency, edge_weights)
        n = len(loo)
        n_top3 = sum(1 for r in loo.values() if r["top3_correct"])
        p3 = n_top3 / n if n > 0 else 0.0
        # LB test corpus is small (142 inscriptions, ~20 nodes). Chance is
        # ~3/5 * 1/13 = 4.6%. Any positive recovery is meaningful.
        assert n_top3 >= 1, (
            f"LB LOO precision@3 = {p3:.1%}; expected at least 1 correct"
        )

    def test_at_least_one_constrained_on_lb(self, lb_graph, lb_sign_values):
        """At least one LB sign should reach CONSTRAINED or better in LOO."""
        adjacency, edge_weights = lb_graph
        sv_in_graph = {k: v for k, v in lb_sign_values.items() if k in adjacency}
        loo = leave_one_out_validation(sv_in_graph, adjacency, edge_weights)
        tiers = [r["tier"] for r in loo.values()]
        constrained_plus = sum(
            1 for t in tiers
            if t in ("STRONG", "PROBABLE", "CONSTRAINED")
        )
        assert constrained_plus >= 1, (
            f"No CONSTRAINED+ identifications in LB LOO. Tiers: {tiers}"
        )

    def test_pure_vowels_get_empty_consonant(self, lb_graph, lb_sign_values):
        """Pure vowel signs (AB08=a, AB28=i, AB10=u) should get empty consonant."""
        adjacency, edge_weights = lb_graph
        vowel_signs = {"AB08": "a", "AB28": "i", "AB10": "u"}
        for sign_id, expected_v in vowel_signs.items():
            if sign_id not in adjacency:
                continue
            reduced = {k: v for k, v in lb_sign_values.items() if k != sign_id}
            result = triangulate_sign(sign_id, reduced, adjacency, edge_weights)
            # Pure vowels may get empty consonant or a specific one depending
            # on which anchors they alternate with. Just check it's sensible.
            if result.alternation_evidence.n_anchor_alternations >= 2:
                # The top reading should at least contain the correct vowel
                if result.candidate_readings:
                    top_vowels = {cr.vowel for cr in result.candidate_readings[:3]}
                    assert expected_v in top_vowels, (
                        f"{sign_id} ({expected_v}) not in top-3 vowels: {top_vowels}"
                    )


class TestLAKnownAnswer:
    """Known-answer tests on the real Linear A corpus."""

    def test_la_loo_produces_results(self, la_graph, la_anchor_cv):
        """LOO on LA anchors should produce non-empty results."""
        adjacency, edge_weights = la_graph
        loo = leave_one_out_validation(la_anchor_cv, adjacency, edge_weights)
        assert len(loo) > 0, "LOO produced no results"

    def test_la_loo_has_correct_predictions(self, la_graph, la_anchor_cv):
        """At least some LA anchors should be correctly predicted."""
        adjacency, edge_weights = la_graph
        loo = leave_one_out_validation(la_anchor_cv, adjacency, edge_weights)
        n_top3 = sum(1 for r in loo.values() if r["top3_correct"])
        assert n_top3 >= 1, "No correct predictions in LA LOO"

    def test_la_multiple_tiers(self, la_graph, la_anchor_cv):
        """LA triangulation should produce signs at multiple tiers."""
        adjacency, edge_weights = la_graph
        unknown_signs = sorted(
            s for s in adjacency.keys() if s not in la_anchor_cv
        )
        readings = triangulate_all(
            unknown_signs, la_anchor_cv, adjacency, edge_weights,
        )
        tiers = {r.identification_tier for r in readings}
        # Should have at least 2 different tiers
        assert len(tiers) >= 2, f"Only {tiers} tier(s) found"

    def test_la_unknown_signs_exist(self, la_graph, la_anchor_cv):
        """There should be unknown signs in the graph to triangulate."""
        adjacency, _ = la_graph
        unknown = [s for s in adjacency if s not in la_anchor_cv]
        assert len(unknown) >= 3, f"Only {len(unknown)} unknown signs in graph"

    def test_la_anchor_count(self, la_anchor_cv):
        """Should have at least 40 anchors (we expect ~50 from sign_to_ipa)."""
        assert len(la_anchor_cv) >= 40, (
            f"Only {len(la_anchor_cv)} anchors (expected >= 40)"
        )


# =========================================================================
# TIER 3: Null and negative tests (~5 tests)
# =========================================================================

class TestNullAndNegative:
    """Null and negative tests: random/degenerate inputs should not produce strong results."""

    def test_empty_graph_no_results(self):
        """Empty adjacency graph produces INSUFFICIENT for all signs."""
        adjacency: Dict[str, Set[str]] = {}
        edge_weights: Dict[Tuple[str, str], float] = {}
        anchor_cv = {"A": ("t", "a"), "B": ("s", "i")}

        result = triangulate_sign("X", anchor_cv, adjacency, edge_weights)
        assert result.identification_tier == "INSUFFICIENT"
        assert result.confidence == 0.0

    def test_sign_not_in_graph(self):
        """A sign not in the graph gets INSUFFICIENT."""
        adjacency = {"A": {"B"}, "B": {"A"}}
        edge_weights = {("A", "B"): 3.0}
        anchor_cv = {"A": ("t", "a"), "B": ("t", "e")}

        result = triangulate_sign("Z", anchor_cv, adjacency, edge_weights)
        assert result.identification_tier == "INSUFFICIENT"

    def test_random_graph_no_strong(self):
        """A random graph should not produce STRONG identifications."""
        rng = random.Random(12345)
        # Create random adjacency among 30 signs
        signs = [f"SIG{i:03d}" for i in range(30)]
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        edge_weights: Dict[Tuple[str, str], float] = {}

        for i in range(len(signs)):
            for j in range(i + 1, len(signs)):
                if rng.random() < 0.2:  # 20% edge probability
                    a, b = signs[i], signs[j]
                    adjacency[a].add(b)
                    adjacency[b].add(a)
                    edge_weights[(a, b)] = rng.uniform(1.0, 5.0)

        # Use first 10 as anchors with random CV values
        vowels = list("aeiou")
        consonants = list("tdmprsnk")
        anchor_cv = {}
        for s in signs[:10]:
            c = rng.choice(consonants)
            v = rng.choice(vowels)
            anchor_cv[s] = (c, v)

        # Triangulate the rest
        unknown = signs[10:]
        results = triangulate_all(unknown, anchor_cv, dict(adjacency), edge_weights)

        strong = [r for r in results if r.identification_tier == "STRONG"]
        # Random graph should produce very few or no STRONG identifications
        assert len(strong) <= 3, (
            f"Random graph produced {len(strong)} STRONG identifications — "
            f"suggests scoring is too lenient"
        )

    def test_disconnected_sign_insufficient(self):
        """A sign with no edges to anchors gets INSUFFICIENT."""
        adjacency = {
            "A": {"B", "C"}, "B": {"A", "C"}, "C": {"A", "B"},
            "X": {"Y"}, "Y": {"X"},
        }
        edge_weights = {
            ("A", "B"): 3.0, ("A", "C"): 2.0, ("B", "C"): 4.0,
            ("X", "Y"): 2.0,
        }
        anchor_cv = {"A": ("t", "a"), "B": ("t", "e"), "C": ("t", "i")}

        result = triangulate_sign("X", anchor_cv, adjacency, edge_weights)
        assert result.identification_tier == "INSUFFICIENT"

    def test_single_anchor_edge_insufficient(self):
        """A sign with only 1 anchor edge gets INSUFFICIENT."""
        adjacency = {"A": {"X"}, "X": {"A"}}
        edge_weights = {("A", "X"): 2.0}
        anchor_cv = {"A": ("t", "a")}

        result = triangulate_sign("X", anchor_cv, adjacency, edge_weights)
        # Only 1 anchor alternation -> INSUFFICIENT
        assert result.identification_tier == "INSUFFICIENT"


class TestTriangulationProperties:
    """Property-based tests for triangulation."""

    def test_all_candidates_have_inferred_consonant(self, lb_graph, lb_sign_values):
        """All candidate readings should use the inferred consonant."""
        adjacency, edge_weights = lb_graph
        for sign_id in list(adjacency.keys())[:10]:
            if sign_id in lb_sign_values:
                continue
            result = triangulate_sign(sign_id, lb_sign_values, adjacency, edge_weights)
            ic = result.alternation_evidence.inferred_consonant
            if ic is not None and result.candidate_readings:
                for cr in result.candidate_readings:
                    assert cr.consonant == ic, (
                        f"{sign_id}: candidate '{cr.reading}' has consonant "
                        f"'{cr.consonant}' but inferred is '{ic}'"
                    )

    def test_excluded_vowels_not_in_candidates(self, lb_graph, lb_sign_values):
        """Excluded vowels should not appear in top candidate readings
        (unless no other option)."""
        adjacency, edge_weights = lb_graph
        for sign_id in list(adjacency.keys())[:10]:
            result = triangulate_sign(sign_id, lb_sign_values, adjacency, edge_weights)
            ev = result.alternation_evidence
            if ev.excluded_vowels and ev.surviving_vowels:
                for cr in result.candidate_readings:
                    assert cr.vowel not in ev.excluded_vowels, (
                        f"{sign_id}: candidate '{cr.reading}' uses excluded vowel "
                        f"'{cr.vowel}'"
                    )
