"""Pillar 5 output formatter: produces interface contract JSON.

Follows the output schema defined in PRD Section 4.1.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from .constraint_assembler import ConstrainedVocabulary
from .evidence_combiner import SignGroupMatches
from .stratum_detector import StratumAnalysis


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
        if isinstance(obj, (set, frozenset)):
            return sorted(list(obj))
        return super().default(obj)


def _safe_float(val: Any) -> float:
    """Convert to float safely, replacing NaN/Inf with 0.0."""
    if val is None:
        return 0.0
    try:
        f = float(val)
        if f != f:  # NaN check
            return 0.0
        if abs(f) == float("inf"):
            return 0.0
        return f
    except (TypeError, ValueError):
        return 0.0


def _format_vocabulary_resolution(
    all_matches: List[SignGroupMatches],
    constrained_vocab: ConstrainedVocabulary,
) -> List[Dict[str, Any]]:
    """Format per-sign-group vocabulary resolution entries."""
    entries = []

    # Build a lookup for constraints
    constraint_lookup: Dict[str, Any] = {}
    for sg in constrained_vocab.sign_groups:
        key = "|".join(s.lower() for s in sg.sign_group_ids)
        constraint_lookup[key] = sg

    for sgm in all_matches:
        key = "|".join(s.lower() for s in sgm.sign_group_ids)
        sg_constraint = constraint_lookup.get(key)

        entry: Dict[str, Any] = {
            "sign_group": sgm.sign_group_ids,
            "stem": sg_constraint.stem_sign_ids if sg_constraint else sgm.sign_group_ids,
            "reading_lb": sgm.stem_ipa_lb,
            "frequency": sg_constraint.frequency if sg_constraint else 0,
            "pillar4_semantic_field": sgm.semantic_field,
            "pillar3_word_class": sg_constraint.word_class if sg_constraint else None,
            "pillar2_morphology": sg_constraint.morphological_class if sg_constraint else None,
        }

        # Format candidate matches
        candidates = []
        for m in sgm.matches:
            candidates.append({
                "language": m.language_name,
                "language_code": m.language_code,
                "word": m.word,
                "ipa": m.ipa,
                "gloss": m.gloss,
                "phonological_distance": _safe_float(m.phonological_distance),
                "semantic_compatibility": m.semantic_compatibility,
                "combined_score": round(_safe_float(m.combined_score), 4),
                "evidence_provenance": m.evidence_provenance,
                "evidence_chain": m.evidence_chain,
            })
        entry["candidate_matches"] = candidates

        # Best match summary
        if sgm.best_match and sgm.best_match.combined_score > 0.5:
            entry["best_match"] = {
                "language": sgm.best_match.language_name,
                "language_code": sgm.best_match.language_code,
                "word": sgm.best_match.word,
                "combined_score": round(_safe_float(sgm.best_match.combined_score), 4),
            }
        else:
            entry["best_match"] = {
                "language": "none_significant",
                "note": "No candidate exceeds combined_score threshold 0.5",
            }

        entries.append(entry)

    return entries


def _format_stratum_analysis(analysis: StratumAnalysis) -> Dict[str, Any]:
    """Format stratum analysis for output."""
    strata = []
    for s in analysis.strata:
        strata.append({
            "stratum_id": s.stratum_id,
            "dominant_language": s.dominant_language,
            "dominant_language_name": s.dominant_language_name,
            "n_sign_groups": s.n_sign_groups,
            "proportion": round(s.proportion, 4),
            "semantic_domains": s.semantic_domains,
            "description": s.description,
            "is_noise": s.is_noise,
        })

    return {
        "method": analysis.method,
        "strata": strata,
        "evidence_provenance": analysis.evidence_provenance,
        "note": analysis.note,
    }


def _format_diagnostics(
    constrained_vocab: ConstrainedVocabulary,
    all_matches: List[SignGroupMatches],
    analysis: StratumAnalysis,
    crossref: Dict[str, Any],
) -> Dict[str, Any]:
    """Format diagnostic summary."""
    n_with_matches = sum(1 for m in all_matches if m.n_matches > 0)
    n_significant = sum(1 for m in all_matches if m.has_significant_match)
    all_scores = [
        m.best_match.combined_score
        for m in all_matches
        if m.best_match is not None
    ]

    return {
        "sign_groups_resolved": constrained_vocab.n_matchable,
        "sign_groups_with_matches": n_with_matches,
        "sign_groups_no_match": constrained_vocab.n_matchable - n_with_matches,
        "sign_groups_significant": n_significant,
        "n_functional_excluded": constrained_vocab.n_functional_excluded,
        "n_no_constraints": constrained_vocab.n_no_constraints,
        "acceptance_rate": round(constrained_vocab.acceptance_rate, 4),
        "candidate_languages_searched": len(set(
            m.language_code
            for sgm in all_matches
            for m in sgm.matches
        )),
        "total_candidate_comparisons": sum(m.n_matches for m in all_matches),
        "mean_combined_score": round(
            sum(all_scores) / len(all_scores), 4
        ) if all_scores else 0.0,
        "max_combined_score": round(max(all_scores), 4) if all_scores else 0.0,
        "n_strata_detected": analysis.n_strata,
        "substrate_fraction": round(analysis.substrate_fraction, 4),
        "cross_reference": crossref,
    }


def format_output(
    constrained_vocab: ConstrainedVocabulary,
    all_matches: List[SignGroupMatches],
    stratum_analysis: StratumAnalysis,
    compositional_portrait: Dict[str, Any],
    crossref: Dict[str, Any],
    corpus_hash: str,
    config: Dict[str, Any],
    seed: int,
) -> Dict[str, Any]:
    """Format the complete Pillar 5 output.

    Returns the interface contract JSON structure from PRD Section 4.1.
    """
    config_str = json.dumps(config, sort_keys=True, cls=_NumpyEncoder)
    config_hash = hashlib.sha256(config_str.encode()).hexdigest()

    # Compute upstream pillar version hashes
    p1_path = config.get("pillar1_output", "results/pillar1_output.json")
    p2_path = config.get("pillar2_output", "results/pillar2_output.json")
    p3_path = config.get("pillar3_output", "results/pillar3_output.json")
    p4_path = config.get("pillar4_output", "results/pillar4_output.json")

    def _file_hash(path: str) -> str:
        p = Path(path)
        if not p.exists():
            return "not_found"
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    output = {
        "metadata": {
            "pillar": 5,
            "version": "1.0.0",
            "corpus_version": corpus_hash,
            "pillar1_version": _file_hash(p1_path),
            "pillar2_version": _file_hash(p2_path),
            "pillar3_version": _file_hash(p3_path),
            "pillar4_version": _file_hash(p4_path),
            "config_hash": config_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "seed": seed,
            "n_candidate_languages": len(set(
                m.language_code
                for sgm in all_matches
                for m in sgm.matches
            )),
        },
        "vocabulary_resolution": _format_vocabulary_resolution(
            all_matches, constrained_vocab
        ),
        "stratum_analysis": _format_stratum_analysis(stratum_analysis),
        "compositional_portrait": compositional_portrait,
        "diagnostics": _format_diagnostics(
            constrained_vocab, all_matches, stratum_analysis, crossref
        ),
    }

    return output


def write_output(output: Dict[str, Any], output_path: str | Path) -> Path:
    """Write the output JSON to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, cls=_NumpyEncoder, ensure_ascii=False)
    return path
