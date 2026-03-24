"""Output formatter for Pillar 2 results.

Assembles all analysis results into the interface contract JSON format
defined in PRD Section 4.1, for downstream consumption by Pillar 3
(Grammar) and Pillar 5 (Vocab Resolution).
"""

from __future__ import annotations

import json
import hashlib
import datetime
from pathlib import Path
from typing import Any, Dict

import numpy as np

from .pillar1_loader import Pillar1Output
from .segmenter import SegmentedLexicon
from .affix_extractor import AffixInventory
from .paradigm_inducer import ParadigmTable
from .word_class_hinter import WordClassResult


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
    lexicon: SegmentedLexicon,
    affix_inv: AffixInventory,
    paradigm_table: ParadigmTable,
    word_classes: WordClassResult,
    pillar1: Pillar1Output,
    corpus_hash: str,
    config: Dict[str, Any],
    seed: int = 1234,
) -> Dict[str, Any]:
    """Assemble all Pillar 2 results into the interface contract JSON.

    Args:
        lexicon: Segmented lexicon.
        affix_inv: Classified affix inventory.
        paradigm_table: Induced paradigm table.
        word_classes: Word-class hints.
        pillar1: Pillar 1 output (for provenance).
        corpus_hash: SHA-256 of the corpus file.
        config: Configuration dictionary.
        seed: Random seed.

    Returns:
        Dictionary matching the PRD Section 4.1 JSON schema.
    """
    output: Dict[str, Any] = {}

    # --- Metadata ---
    config_str = json.dumps(config, sort_keys=True, default=str)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()

    output["metadata"] = {
        "pillar": 2,
        "version": "1.0.0",
        "corpus_version": corpus_hash,
        "pillar1_version": pillar1.pillar1_hash,
        "config_hash": config_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": seed,
    }

    # --- Segmented Lexicon ---
    output["segmented_lexicon"] = [
        {
            "word_sign_ids": w.word_sign_ids,
            "segmentation": {
                "stem": w.stem,
                "suffixes": w.suffixes,
                "prefixes": w.prefixes,
                "segmentation_confidence": _safe_float(w.segmentation_confidence),
            },
            "frequency": w.frequency,
            "inscription_types": w.inscription_types,
            "method": w.method,
        }
        for w in lexicon.words
    ]

    # --- Affix Inventory ---
    output["affix_inventory"] = {
        "suffixes": [
            {
                "signs": a.signs,
                "frequency": a.frequency,
                "n_distinct_stems": a.n_distinct_stems,
                "productivity": _safe_float(a.productivity),
                "classification": a.classification,
                "paradigm_classes": a.paradigm_classes,
            }
            for a in affix_inv.suffixes
        ],
        "prefixes": [
            {
                "signs": a.signs,
                "frequency": a.frequency,
                "n_distinct_stems": a.n_distinct_stems,
                "productivity": _safe_float(a.productivity),
                "classification": a.classification,
                "paradigm_classes": a.paradigm_classes,
            }
            for a in affix_inv.prefixes
        ],
    }

    # --- Paradigm Table ---
    paradigms_json = []
    for p in paradigm_table.paradigms:
        p_json: Dict[str, Any] = {
            "class_id": p.class_id,
            "n_members": p.n_members,
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "ending_signs": s.ending_signs,
                    "frequency": s.frequency,
                    "label": s.label,
                }
                for s in p.slots
            ],
            "example_stems": [
                {
                    "stem": e.stem,
                    "attested_slots": e.attested_slots,
                    "attested_forms": e.attested_forms,
                }
                for e in p.example_stems
            ],
            "completeness": _safe_float(p.completeness),
        }

        if p.grid_analysis is not None:
            p_json["grid_analysis"] = {
                "endings_share_consonant_row": p.grid_analysis.endings_share_consonant_row,
                "consonant_class": p.grid_analysis.consonant_class,
                "vowel_classes_attested": p.grid_analysis.vowel_classes_attested,
            }

        paradigms_json.append(p_json)

    output["paradigm_table"] = {
        "n_paradigm_classes": paradigm_table.n_classes,
        "paradigms": paradigms_json,
    }

    # --- Morphological Word Classes ---
    output["morphological_word_classes"] = [
        {
            "class_id": wc.class_id,
            "label": wc.label,
            "description": wc.description,
            "n_stems": wc.n_stems,
            "paradigm_classes": wc.paradigm_classes,
        }
        for wc in word_classes.word_classes
    ]

    # --- Diagnostics ---
    n_infl = sum(1 for a in affix_inv.suffixes if a.classification == "inflectional")
    n_deriv = sum(1 for a in affix_inv.suffixes if a.classification == "derivational")
    n_ambig = sum(1 for a in affix_inv.suffixes if a.classification == "ambiguous")

    mean_completeness = 0.0
    if paradigm_table.paradigms:
        mean_completeness = sum(
            p.completeness for p in paradigm_table.paradigms
        ) / len(paradigm_table.paradigms)

    output["diagnostics"] = {
        "total_words_segmented": lexicon.total_words,
        "words_with_suffixes": lexicon.words_with_suffixes,
        "words_unsegmented": lexicon.words_unsegmented,
        "total_unique_suffixes": len(affix_inv.suffixes),
        "inflectional_suffixes": n_infl,
        "derivational_suffixes": n_deriv,
        "ambiguous_suffixes": n_ambig,
        "mean_paradigm_completeness": _safe_float(mean_completeness),
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
    """Convert a value to a JSON-safe float."""
    if val is None:
        return 0.0
    fval = float(val)
    if np.isnan(fval):
        return 0.0
    if np.isinf(fval):
        return 1e308 if fval > 0 else -1e308
    return fval
