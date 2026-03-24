"""Output formatter for Pillar 4 (Semantic Anchoring).

Assembles all analysis results into the interface contract JSON format
defined in PRD Section 4.1.  Handles numpy type conversion and writes
to disk with provenance metadata.

BIAS-FREE: Uses "sign_group" not "word" throughout.  No "deity" or
"ritual verb" labels.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from pillar4.ideogram_analyzer import IdeogramAnalysisResult
from pillar4.transaction_analyzer import TransactionAnalysisResult
from pillar4.formula_mapper import FormulaMapResult
from pillar4.place_name_finder import PlaceNameResult
from pillar4.anchor_assembler import AnchorVocabulary


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
            return sorted(obj) if all(isinstance(x, str) for x in obj) else list(obj)
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
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_anchor_vocabulary(
    anchor_vocab: AnchorVocabulary,
) -> List[Dict[str, Any]]:
    """Format anchor vocabulary for JSON output.

    Uses "sign_group_ids" not "word_sign_ids" for bias-free naming.
    """
    entries: List[Dict[str, Any]] = []

    for anchor in anchor_vocab.anchored_sign_groups:
        evidence_list = []
        for ev in anchor.evidence_chain:
            evidence_list.append({
                "source": ev.source,
                "confidence": _safe_float(ev.confidence),
                "semantic_field": ev.semantic_field,
                "detail": ev.detail,
            })

        phonetic = {}
        for pa in anchor.phonetic_anchors:
            phonetic[pa.ab_code] = pa.phonetic_value

        entries.append({
            "sign_group_ids": list(anchor.sign_group_ids),
            "transliterations": sorted(anchor.transliterations),
            "semantic_field": anchor.semantic_field,
            "confidence": _safe_float(anchor.confidence),
            "n_evidence_sources": anchor.n_evidence_sources,
            "evidence": evidence_list,
            "phonetic_anchors": phonetic if phonetic else None,
        })

    return entries


def _format_semantic_fields(
    ideogram_result: IdeogramAnalysisResult,
    anchor_vocab: AnchorVocabulary,
) -> Dict[str, Any]:
    """Format semantic fields summary."""
    fields: Dict[str, Any] = {}

    # From ideogram per-word lists
    for iwl in ideogram_result.per_ideogram_word_lists:
        if iwl.semantic_field is None:
            continue
        field_key = iwl.semantic_field
        if field_key not in fields:
            fields[field_key] = {
                "ideogram": iwl.ideogram_reading,
                "n_associated_sign_groups": len(iwl.sign_groups),
                "top_sign_groups": [],
            }
        for sg_ids, count in iwl.sign_groups[:10]:
            fields[field_key]["top_sign_groups"].append({
                "sign_group_ids": list(sg_ids),
                "co_occurrence": count,
            })

    # Add place-name fields and other fields from anchor vocab
    for anchor in anchor_vocab.anchored_sign_groups:
        sf = anchor.semantic_field
        if sf not in fields:
            fields[sf] = {
                "ideogram": None,
                "n_associated_sign_groups": 0,
                "top_sign_groups": [],
            }
        fields[sf]["n_associated_sign_groups"] += 1

    return fields


def _format_formula_atlas(
    formula_result: FormulaMapResult,
) -> Dict[str, Any]:
    """Format formula atlas for JSON output.

    BIAS-FREE: elements are labelled by frequency classification only,
    not by assumed linguistic function.
    """
    fixed = []
    semi_fixed = []
    variable = []

    for elem in formula_result.elements:
        entry = {
            "sign_group_ids": list(elem.sign_group_ids),
            "transliterations": sorted(elem.transliterations),
            "frequency_count": elem.frequency_count,
            "frequency_rate": _safe_float(elem.frequency_rate),
            "typical_position": elem.typical_position,
            "classification": elem.classification,
        }
        if elem.classification == "fixed_element":
            fixed.append(entry)
        elif elem.classification == "semi_fixed_element":
            semi_fixed.append(entry)
        else:
            variable.append(entry)

    template_slots = []
    for pos_label, elems in formula_result.template.slots:
        template_slots.append({
            "position": pos_label,
            "elements": [list(e.sign_group_ids) for e in elems],
        })

    return {
        "libation_formula": {
            "n_instances": formula_result.n_libation_inscriptions,
            "fixed_elements": fixed,
            "semi_fixed_elements": semi_fixed,
            "variable_elements": variable,
            "template_slots": template_slots,
            "template_coverage": _safe_float(
                formula_result.template.template_coverage
            ),
        },
    }


def _format_place_name_anchors(
    place_name_result: PlaceNameResult,
) -> List[Dict[str, Any]]:
    """Format place name anchors for JSON output."""
    entries: List[Dict[str, Any]] = []
    # Deduplicate by name
    seen_names: Set[str] = set()

    for match in place_name_result.found:
        if match.name in seen_names:
            continue
        seen_names.add(match.name)

        phonetic = {}
        for anchor in place_name_result.phonetic_anchors:
            if anchor.from_place_name == match.name:
                phonetic[anchor.ab_code] = anchor.phonetic_value

        entries.append({
            "sign_group_ids": match.sign_ids_config,
            "reading": "-".join(match.target_readings),
            "identified_as": match.name,
            "confidence": _safe_float(match.confidence),
            "source": match.source,
            "phonetic_anchors": phonetic,
            "site_matches_expected": match.site_matches_expected,
        })

    return entries


def _format_numerical_analysis(
    transaction_result: TransactionAnalysisResult,
) -> Dict[str, Any]:
    """Format numerical analysis for JSON output."""
    verifications = []
    for kv in transaction_result.kuro_verifications:
        verifications.append({
            "inscription_id": kv.inscription_id,
            "status": kv.status,
            "pre_kuro_sum": kv.pre_kuro_sum,
            "post_kuro_value": kv.post_kuro_value,
            "matches": kv.matches,
            "has_unparsed_pre": kv.has_unparsed_pre,
            "has_unparsed_post": kv.has_unparsed_post,
        })

    return {
        "numeral_system": "decimal_additive",
        "attested_values": {
            "A701": 1,
            "A704": 10,
            "A705": 100,
            "A707": "unparsed_fractional",
            "A708": "unparsed_fractional",
        },
        "ku_ro_totals": {
            "n_testable": transaction_result.summary.get("n_kuro_testable", 0),
            "n_matching": transaction_result.summary.get("n_kuro_matching", 0),
            "n_discrepant": transaction_result.summary.get("n_kuro_discrepant", 0),
            "n_unparsable": transaction_result.summary.get("n_kuro_unparsable", 0),
            "n_no_post_numeral": transaction_result.summary.get(
                "n_kuro_no_post_numeral", 0
            ),
        },
        "verifications": verifications,
    }


def _format_diagnostics(
    anchor_vocab: AnchorVocabulary,
    ideogram_result: IdeogramAnalysisResult,
    transaction_result: TransactionAnalysisResult,
    formula_result: FormulaMapResult,
    place_name_result: PlaceNameResult,
) -> Dict[str, Any]:
    """Format diagnostics summary."""
    # Confidence distribution
    high = sum(
        1 for a in anchor_vocab.anchored_sign_groups if a.confidence > 0.7
    )
    medium = sum(
        1 for a in anchor_vocab.anchored_sign_groups
        if 0.3 <= a.confidence <= 0.7
    )
    low = sum(
        1 for a in anchor_vocab.anchored_sign_groups if a.confidence < 0.3
    )

    # Count distinct semantic fields
    fields = set(a.semantic_field for a in anchor_vocab.anchored_sign_groups)

    return {
        "total_sign_groups_anchored": anchor_vocab.n_anchored,
        "anchor_confidence_distribution": {
            "high_gt_0.7": high,
            "medium_0.3_to_0.7": medium,
            "low_lt_0.3": low,
        },
        "semantic_fields_identified": len(fields),
        "n_named_ideograms_found": ideogram_result.n_named_ideograms_found,
        "n_sign_groups_analyzed": ideogram_result.n_sign_groups_analyzed,
        "n_inscriptions_with_kuro": transaction_result.summary.get(
            "n_inscriptions_with_kuro", 0
        ),
        "n_libation_inscriptions": formula_result.n_libation_inscriptions,
        "place_names_found": len(place_name_result.found),
        "place_names_not_found": len(place_name_result.not_found),
        "n_evidence_by_source": anchor_vocab.n_by_source,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def format_output(
    ideogram_result: IdeogramAnalysisResult,
    transaction_result: TransactionAnalysisResult,
    formula_result: FormulaMapResult,
    place_name_result: PlaceNameResult,
    anchor_vocab: AnchorVocabulary,
    corpus_hash: str,
    config: Dict[str, Any],
    seed: int = 1234,
) -> Dict[str, Any]:
    """Assemble all Pillar 4 results into the interface contract JSON.

    Matches the PRD Section 4.1 schema with field names adjusted to use
    "sign_group" not "word" where appropriate (bias removal).

    Args:
        ideogram_result: Output from ideogram_analyzer.
        transaction_result: Output from transaction_analyzer.
        formula_result: Output from formula_mapper.
        place_name_result: Output from place_name_finder.
        anchor_vocab: Output from anchor_assembler.
        corpus_hash: SHA-256 hash of the corpus file.
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
        "pillar": 4,
        "version": "1.0.0",
        "corpus_hash": corpus_hash,
        "config_hash": config_hash,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "seed": seed,
    }

    # --- Anchor Vocabulary ---
    output["anchor_vocabulary"] = _format_anchor_vocabulary(anchor_vocab)

    # --- Semantic Fields ---
    output["semantic_fields"] = _format_semantic_fields(
        ideogram_result, anchor_vocab
    )

    # --- Formula Atlas ---
    output["formula_atlas"] = _format_formula_atlas(formula_result)

    # --- Place Name Anchors ---
    output["place_name_anchors"] = _format_place_name_anchors(place_name_result)

    # --- Numerical Analysis ---
    output["numerical_analysis"] = _format_numerical_analysis(transaction_result)

    # --- Diagnostics ---
    output["diagnostics"] = _format_diagnostics(
        anchor_vocab,
        ideogram_result,
        transaction_result,
        formula_result,
        place_name_result,
    )

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
