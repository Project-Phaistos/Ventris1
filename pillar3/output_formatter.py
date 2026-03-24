"""Output formatter for Pillar 3 results.

Assembles all analysis results into the interface contract JSON format
defined in PRD Section 4.1.  Handles numpy type conversion and writes
to disk with provenance metadata.
"""

from __future__ import annotations

import json
import hashlib
import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from .word_class_inducer import WordClassResult
from .word_order_analyzer import WordOrderResult
from .agreement_detector import AgreementResult
from .functional_word_finder import FunctionalWordResult
from .grammar_sketch_builder import GrammarSketch


# ---------------------------------------------------------------------------
# Numpy-aware JSON encoder
# ---------------------------------------------------------------------------

class _NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy types to Python native types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        if isinstance(obj, tuple):
            return list(obj)
        return super().default(obj)


def _safe_float(val: Any) -> float:
    """Convert a value to a JSON-safe float."""
    if val is None:
        return 0.0
    fval = float(val)
    if np.isnan(fval):
        return 0.0
    if np.isinf(fval):
        return 1e308 if fval > 0 else -1e308
    return fval


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_output(
    word_classes: WordClassResult,
    word_order: WordOrderResult,
    agreement: AgreementResult,
    functional_words: FunctionalWordResult,
    grammar_sketch: GrammarSketch,
    corpus_hash: str,
    pillar1_hash: str,
    pillar2_hash: str,
    config: Dict[str, Any],
    seed: int = 1234,
) -> Dict[str, Any]:
    """Assemble all Pillar 3 results into the interface contract JSON.

    Args:
        word_classes: Induced word classes.
        word_order: Word order analysis.
        agreement: Agreement detection results.
        functional_words: Functional word identification results.
        grammar_sketch: Synthesised grammar sketch.
        corpus_hash: SHA-256 hash of the corpus file.
        pillar1_hash: SHA-256 hash of the Pillar 1 output file.
        pillar2_hash: SHA-256 hash of the Pillar 2 output file.
        config: Pipeline configuration dictionary.
        seed: Random seed used.

    Returns:
        Dictionary matching the PRD Section 4.1 JSON schema.
    """
    output: Dict[str, Any] = {}

    # --- Metadata ---
    config_str = json.dumps(config, sort_keys=True, default=str)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()

    output["metadata"] = {
        "pillar": 3,
        "version": "1.0.0",
        "corpus_hash": corpus_hash,
        "pillar1_version": pillar1_hash,
        "pillar2_version": pillar2_hash,
        "config_hash": config_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": seed,
    }

    # --- Grammar Sketch (top-level summary) ---
    output["grammar_sketch"] = {
        "is_inflected": grammar_sketch.is_inflected,
        "estimated_word_classes": grammar_sketch.estimated_word_classes,
        "word_order_type": grammar_sketch.word_order_type,
        "has_agreement": grammar_sketch.has_agreement,
        "n_functional_words": grammar_sketch.n_functional_words,
        "summary": grammar_sketch.summary,
        "details": grammar_sketch.details,
    }

    # --- Word Classes ---
    output["word_classes"] = {
        "n_classes": word_classes.n_classes,
        "silhouette": _safe_float(word_classes.silhouette),
        "silhouette_curve": {
            str(k): _safe_float(v) for k, v in word_classes.silhouette_curve.items()
        },
        "morph_coherence_curve": {
            str(k): _safe_float(v) for k, v in word_classes.morph_coherence_curve.items()
        },
        "combined_score_curve": {
            str(k): _safe_float(v) for k, v in word_classes.combined_score_curve.items()
        },
        "svd_explained_variance": [
            _safe_float(v) for v in word_classes.svd_explained_variance
        ],
        "classes": [
            {
                "class_id": cls.class_id,
                "suggested_label": cls.suggested_label,
                "n_members": cls.n_members,
                "morphological_profile": cls.morphological_profile,
                "positional_profile": {
                    k: _safe_float(v) for k, v in cls.positional_profile.items()
                },
                "top_members": cls.top_members,
                "distributional_signature": cls.distributional_signature,
            }
            for cls in word_classes.classes
        ],
        "assignments": {
            "-".join(k): v for k, v in word_classes.assignments.items()
        },
    }

    # --- Word Order ---
    output["word_order"] = {
        "n_classes": word_order.n_classes,
        "n_inscriptions_used": word_order.n_inscriptions_used,
        "n_bigrams_analyzed": word_order.n_bigrams_analyzed,
        "precedence_matrix": word_order.precedence_matrix.tolist(),
        "pairwise_orders": [
            {
                "class_a": po.class_a,
                "class_b": po.class_b,
                "a_before_b_count": po.a_before_b_count,
                "b_before_a_count": po.b_before_a_count,
                "direction_ratio": _safe_float(po.direction_ratio),
                "p_value": _safe_float(po.p_value),
            }
            for po in word_order.pairwise_orders
        ],
        "position_stats": [
            {
                "class_id": ps.class_id,
                "mean_relative_position": _safe_float(ps.mean_relative_position),
                "std_relative_position": _safe_float(ps.std_relative_position),
                "n_observations": ps.n_observations,
            }
            for ps in word_order.position_stats
        ],
    }

    # --- Agreement ---
    output["agreement"] = {
        "expected_rate": _safe_float(agreement.expected_rate),
        "n_pairs_tested": agreement.n_pairs_tested,
        "n_pairs_significant": agreement.n_pairs_significant,
        "significant_patterns": [
            {
                "word_pair_classes": list(p.word_pair_classes),
                "shared_suffix_rate": _safe_float(p.shared_suffix_rate),
                "expected_by_chance": _safe_float(p.expected_by_chance),
                "p_value": _safe_float(p.p_value),
                "p_value_raw": _safe_float(p.p_value_raw),
                "n_adjacent_pairs": p.n_adjacent_pairs,
                "n_same_suffix": p.n_same_suffix,
                "interpretation": p.interpretation,
            }
            for p in agreement.patterns
        ],
        "all_pair_stats": [
            {
                "word_pair_classes": list(p.word_pair_classes),
                "shared_suffix_rate": _safe_float(p.shared_suffix_rate),
                "expected_by_chance": _safe_float(p.expected_by_chance),
                "p_value": _safe_float(p.p_value),
                "n_adjacent_pairs": p.n_adjacent_pairs,
                "n_same_suffix": p.n_same_suffix,
            }
            for p in agreement.all_pair_stats
        ],
    }

    # --- Functional Words ---
    output["functional_words"] = {
        "n_candidates_screened": functional_words.n_candidates_screened,
        "n_functional": functional_words.n_functional,
        "words": [
            {
                "word_sign_ids": fw.word_sign_ids,
                "reading": fw.reading,
                "frequency": fw.frequency,
                "n_inscriptions": fw.n_inscriptions,
                "positional_profile": fw.positional_profile,
                "classification": fw.classification,
                "evidence": fw.evidence,
                "word_class_id": fw.word_class_id,
                "word_class_label": fw.word_class_label,
            }
            for fw in functional_words.functional_words
        ],
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
