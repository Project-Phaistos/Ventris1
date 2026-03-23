"""Tests for pillar1.grid_constructor — C-V grid via spectral clustering."""

from __future__ import annotations

import numpy as np
import pytest

from pillar1.grid_constructor import GridResult
from pillar1.vowel_identifier import VowelInventory
from pillar1.alternation_detector import AlternationResult


# ── Consonant class assignments ────────────────────────────────────────

def test_grid_assigns_consonant_classes(grid_result: GridResult) -> None:
    """Assignments on real data must have consonant_class >= 0."""
    assert len(grid_result.assignments) > 0, "Expected >0 grid assignments"
    for a in grid_result.assignments:
        assert a.consonant_class >= 0, (
            f"Sign {a.sign_id} has consonant_class={a.consonant_class} (expected >= 0)"
        )


# ── Vowel count consistency ───────────────────────────────────────────

def test_grid_vowel_count_matches_inventory(
    grid_result: GridResult,
    vowel_result: VowelInventory,
) -> None:
    """Grid's vowel_count should match the vowel inventory's count
    (or the fallback of 5 if the inventory found 0)."""
    expected = vowel_result.count if vowel_result.count > 0 else 5
    assert grid_result.vowel_count == expected, (
        f"Grid vowel_count={grid_result.vowel_count}, "
        f"expected {expected} from VowelInventory"
    )


# ── Eigenvalue ordering ───────────────────────────────────────────────

def test_eigenvalues_are_sorted(grid_result: GridResult) -> None:
    """Eigenvalues from the graph Laplacian must be in ascending order."""
    if len(grid_result.eigenvalues) < 2:
        pytest.skip("Fewer than 2 eigenvalues — degenerate case")

    evals = grid_result.eigenvalues
    for i in range(len(evals) - 1):
        assert evals[i] <= evals[i + 1] + 1e-10, (
            f"Eigenvalue {i} ({evals[i]:.6f}) > eigenvalue {i+1} ({evals[i+1]:.6f}) "
            f"— not sorted ascending"
        )


# ── Silhouette scores computed ─────────────────────────────────────────

def test_silhouette_scores_computed(grid_result: GridResult) -> None:
    """At least some silhouette scores should be computed for model
    selection (unless the graph is too small)."""
    if grid_result.consonant_count == 0:
        pytest.skip("Empty grid — no silhouette scores expected")

    assert len(grid_result.silhouette_scores) > 0, (
        "Expected at least one silhouette score to be computed "
        "for model selection"
    )


# ── Isolated signs are unassigned ──────────────────────────────────────

def test_isolated_signs_are_unassigned(
    grid_result: GridResult,
    alternation_result: AlternationResult,
) -> None:
    """Signs with 0 alternation evidence (zero row/column in the affinity
    matrix) must appear in unassigned_signs, not in assignments."""
    A = alternation_result.affinity_matrix
    idx_to_sign = alternation_result.index_to_sign_id

    # Find signs with zero total affinity
    zero_evidence_signs = set()
    for idx in range(A.shape[0]):
        if A[idx].sum() == 0:
            zero_evidence_signs.add(idx_to_sign[idx])

    assigned_signs = {a.sign_id for a in grid_result.assignments}
    unassigned_signs = {u.sign_id for u in grid_result.unassigned_signs}

    for sid in zero_evidence_signs:
        assert sid not in assigned_signs, (
            f"Sign {sid} has 0 alternation evidence but was assigned to grid"
        )
        assert sid in unassigned_signs, (
            f"Sign {sid} has 0 alternation evidence but is missing from unassigned_signs"
        )
