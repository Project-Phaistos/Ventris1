"""Output formatter for Pillar 1 results.

Implements PRD Section 4.1: assembles all analysis results into the
interface contract JSON format for downstream consumption by Pillar 2
and other modules.

The output JSON includes:
- Vowel inventory (count, CI, sign list)
- C-V grid (consonant/vowel assignments, model selection diagnostics)
- Phonotactic constraints (forbidden/favored bigrams, positional constraints)
- LB validation scores (ARI, disagreements)
- Dead vowel test results
- Metadata (corpus hash, config hash, timestamp, seed)
"""

from __future__ import annotations

import json
import hashlib
import datetime
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .vowel_identifier import VowelInventory
from .grid_constructor import GridResult
from .phonotactic_analyzer import PhonotacticResult
from .lb_validator import LBValidationResult
from .dead_vowel_tester import DeadVowelResult
from .corpus_loader import CorpusData


class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def format_output(
    vowel_inv: VowelInventory,
    grid: GridResult,
    phonotactics: PhonotacticResult,
    lb_validation: LBValidationResult,
    dead_vowel: DeadVowelResult,
    corpus: CorpusData,
    config: Dict[str, Any],
    seed: int = 1234,
) -> Dict[str, Any]:
    """Assemble all results into the interface contract JSON.

    Args:
        vowel_inv: Vowel identification results.
        grid: Grid construction results.
        phonotactics: Phonotactic analysis results.
        lb_validation: LB validation results.
        dead_vowel: Dead vowel test results.
        corpus: Corpus data (for metadata).
        config: Configuration dictionary (for config hash).
        seed: Random seed used.

    Returns:
        Dictionary matching the PRD Section 4.1 JSON schema.
    """
    output: Dict[str, Any] = {}

    # --- Metadata ---
    config_str = json.dumps(config, sort_keys=True, default=str)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()

    output["metadata"] = {
        "corpus_hash": corpus.corpus_hash,
        "config_hash": config_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": seed,
        "corpus_stats": {
            "total_inscriptions": corpus.total_inscriptions,
            "total_words": corpus.total_words,
            "total_syllabogram_tokens": corpus.total_syllabogram_tokens,
            "unique_syllabograms": corpus.unique_syllabograms,
            "words_used_positional": corpus.words_used_positional,
            "words_used_bigram": corpus.words_used_bigram,
        },
    }

    # --- Vowel Inventory ---
    output["vowel_inventory"] = {
        "count": vowel_inv.count,
        "count_ci_95": list(vowel_inv.count_ci_95),
        "method": vowel_inv.method,
        "signs": [
            {
                "sign_id": s.sign_id,
                "enrichment_score": _safe_float(s.enrichment_score),
                "p_value_corrected": _safe_float(s.p_value_corrected),
                "confidence": _safe_float(s.confidence),
                "initial_count": s.initial_count,
                "medial_count": s.medial_count,
                "final_count": s.final_count,
                "total_count": s.total_count,
            }
            for s in vowel_inv.signs
        ],
        "diagnostics": {
            "global_initial_rate": _safe_float(vowel_inv.global_initial_rate),
            "global_medial_rate": _safe_float(vowel_inv.global_medial_rate),
            "global_final_rate": _safe_float(vowel_inv.global_final_rate),
            "n_testable_signs": vowel_inv.n_testable_signs,
        },
    }

    # --- C-V Grid ---
    output["grid"] = {
        "consonant_count": grid.consonant_count,
        "consonant_count_ci_95": list(grid.consonant_count_ci_95),
        "vowel_count": grid.vowel_count,
        "method": grid.grid_method,
        "assignments": [
            {
                "sign_id": a.sign_id,
                "consonant_class": a.consonant_class,
                "vowel_class": a.vowel_class,
                "confidence": _safe_float(a.confidence),
                "evidence_count": a.evidence_count,
            }
            for a in grid.assignments
        ],
        "unassigned_signs": [
            {
                "sign_id": u.sign_id,
                "reason": u.reason,
                "total_count": u.total_count,
            }
            for u in grid.unassigned_signs
        ],
        "model_selection": {
            "eigenvalues": [_safe_float(v) for v in grid.eigenvalues[:30]],
            "eigengaps": [_safe_float(v) for v in grid.eigengaps[:30]],
            "silhouette_scores": {
                str(k): _safe_float(v) for k, v in grid.silhouette_scores.items()
            },
            "best_k_eigengap": grid.best_k_eigengap,
            "best_k_silhouette": grid.best_k_silhouette,
        },
    }

    # --- Phonotactic Constraints ---
    output["phonotactics"] = {
        "forbidden_bigrams": [
            {
                "sign_i": c.sign_i,
                "sign_j": c.sign_j,
                "observed": c.observed,
                "expected": _safe_float(c.expected),
                "std_residual": _safe_float(c.std_residual),
                "p_value_corrected": _safe_float(c.p_value_corrected),
            }
            for c in phonotactics.forbidden_bigrams
        ],
        "favored_bigrams": [
            {
                "sign_i": c.sign_i,
                "sign_j": c.sign_j,
                "observed": c.observed,
                "expected": _safe_float(c.expected),
                "std_residual": _safe_float(c.std_residual),
                "p_value_corrected": _safe_float(c.p_value_corrected),
            }
            for c in phonotactics.favored_bigrams
        ],
        "positional_constraints": {
            "initial_only": [
                {
                    "sign_id": c.sign_id,
                    "initial_count": c.initial_count,
                    "total_count": c.total_count,
                }
                for c in phonotactics.initial_only_signs
            ],
            "never_initial": [
                {
                    "sign_id": c.sign_id,
                    "total_count": c.total_count,
                }
                for c in phonotactics.never_initial_signs
            ],
            "never_final": [
                {
                    "sign_id": c.sign_id,
                    "total_count": c.total_count,
                }
                for c in phonotactics.never_final_signs
            ],
        },
        "diagnostics": {
            "total_bigrams": phonotactics.total_bigrams,
            "unique_bigrams": phonotactics.unique_bigrams,
            "n_testable_cells": phonotactics.n_testable_cells,
            "n_forbidden": phonotactics.n_forbidden,
            "n_favored": phonotactics.n_favored,
        },
    }

    # --- LB Validation ---
    output["lb_validation"] = {
        "consonant_ari": _safe_float(lb_validation.consonant_ari),
        "vowel_ari": _safe_float(lb_validation.vowel_ari),
        "n_signs_with_lb_values": lb_validation.n_signs_with_lb_values,
        "n_signs_validated": lb_validation.n_signs_validated,
        "disagreements": [
            {
                "sign_id": d.sign_id,
                "dimension": d.dimension,
                "independent_class": d.independent_class,
                "lb_class": d.lb_class,
            }
            for d in lb_validation.disagreements
        ],
        "systematic_disagreements": lb_validation.systematic_disagreements,
        "is_systematic": lb_validation.is_systematic,
    }

    # --- Dead Vowel Test ---
    output["dead_vowel"] = {
        "same_vowel_rate": _safe_float(dead_vowel.same_vowel_rate),
        "expected_rate": _safe_float(dead_vowel.expected_rate),
        "n_consecutive_pairs": dead_vowel.n_consecutive_pairs,
        "n_same_vowel": dead_vowel.n_same_vowel,
        "p_value": _safe_float(dead_vowel.p_value),
        "significant": dead_vowel.significant,
        "effect_size": _safe_float(dead_vowel.effect_size),
        "vowel_count": dead_vowel.vowel_count,
        "per_vowel_rates": {
            str(k): _safe_float(v)
            for k, v in dead_vowel.per_vowel_rates.items()
        },
    }

    return output


def write_output(
    output: Dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Write the output dictionary to a JSON file.

    Creates parent directories if they don't exist.

    Args:
        output: The assembled output dictionary.
        output_path: Path to write the JSON file.

    Returns:
        The resolved output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, cls=_NumpyEncoder)

    return output_path


def _safe_float(val: Any) -> float:
    """Convert a value to a JSON-safe float.

    Handles inf, -inf, and NaN by converting to None-safe representations.
    """
    if val is None:
        return 0.0
    fval = float(val)
    if np.isnan(fval):
        return 0.0
    if np.isinf(fval):
        return 1e308 if fval > 0 else -1e308
    return fval
