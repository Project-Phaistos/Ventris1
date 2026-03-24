"""Pillar 4 pipeline orchestrator (Semantic Anchoring).

Runs all semantic anchoring steps in order:
1. Load config from YAML
2. Load corpus context (corpus_context_loader)
3. Analyze ideogram co-occurrence (ideogram_analyzer)
4. Analyze transaction structure (transaction_analyzer)
5. Map libation formulas (formula_mapper)
6. Find place names (place_name_finder)
7. Assemble anchor vocabulary (anchor_assembler)
8. Format and write output (output_formatter)

Usage:
    python -m pillar4.pipeline --config configs/pillar4_default.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .corpus_context_loader import load_context_corpus
from .ideogram_analyzer import analyze_ideograms
from .transaction_analyzer import analyze_transactions
from .formula_mapper import map_formulas
from .place_name_finder import find_place_names
from .anchor_assembler import assemble_anchors
from .output_formatter import format_output, write_output


def load_config(config_path: str | Path) -> Dict[str, Any]:
    """Load pipeline configuration from a YAML file.

    Args:
        config_path: Path to the YAML config file.

    Returns:
        Configuration dictionary.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        yaml.YAMLError: If the YAML is malformed.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(
            f"Config file must contain a YAML mapping, got {type(config)}"
        )

    return config


def _compute_corpus_hash(corpus_path: str | Path) -> str:
    """Compute SHA-256 hash of the corpus file for provenance tracking."""
    path = Path(corpus_path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full Pillar 4 pipeline.

    Args:
        config: Configuration dictionary from YAML.

    Returns:
        The assembled output dictionary.
    """
    t_start = time.time()
    seed = config.get("seed", 1234)
    corpus_path = config.get("corpus_path", "data/sigla_full_corpus.json")

    # --- Step 1: Load corpus context ---
    print("[Step 1/8] Loading corpus context...")
    t0 = time.time()
    corpus = load_context_corpus(corpus_path)
    corpus_hash = _compute_corpus_hash(corpus_path)
    print(
        f"  Loaded {corpus.n_inscriptions} inscriptions, "
        f"{len(corpus.ideogram_inventory)} named ideograms, "
        f"{len(corpus.numeral_inventory)} numeral types, "
        f"{len(corpus.unknown_logogram_inventory)} unknown logograms. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 2: Analyze ideogram co-occurrence ---
    print("[Step 2/8] Analyzing ideogram co-occurrence...")
    t0 = time.time()
    ideogram_result = analyze_ideograms(
        corpus,
        adjacency_window=config.get("ideogram_adjacency_window", 3),
        min_co_occurrence=config.get("min_co_occurrence", 2),
        min_exclusivity=config.get("min_exclusivity", 0.3),
        co_occurrence_alpha=config.get("co_occurrence_alpha", 0.05),
    )
    print(
        f"  Found {ideogram_result.n_named_ideograms_found} named ideograms, "
        f"analyzed {ideogram_result.n_sign_groups_analyzed} sign-groups, "
        f"{len(ideogram_result.semantic_field_assignments)} semantic field "
        f"assignments. ({time.time() - t0:.1f}s)"
    )

    # --- Step 3: Analyze transaction structure ---
    print("[Step 3/8] Analyzing transaction structure...")
    t0 = time.time()
    transaction_result = analyze_transactions(
        corpus,
        kuro_sign_ids=config.get("kuro_sign_ids", ["AB81", "AB02"]),
    )
    summary = transaction_result.summary
    print(
        f"  {summary.get('n_inscriptions_with_numerals', 0)} inscriptions "
        f"with numerals, "
        f"{summary.get('n_inscriptions_with_kuro', 0)} with ku-ro. "
        f"Totals: {summary.get('n_kuro_matching', 0)} matching, "
        f"{summary.get('n_kuro_discrepant', 0)} discrepant, "
        f"{summary.get('n_kuro_unparsable', 0)} unparsable. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 4: Map libation formulas ---
    print("[Step 4/8] Mapping libation formulas...")
    t0 = time.time()
    formula_result = map_formulas(
        corpus,
        libation_inscription_types=config.get(
            "libation_inscription_types", None
        ),
        fixed_element_threshold=config.get("fixed_element_threshold", 0.20),
        variable_element_threshold=config.get(
            "variable_element_threshold", 0.05
        ),
    )
    print(
        f"  {formula_result.n_libation_inscriptions} libation inscriptions, "
        f"{formula_result.n_fixed_elements} fixed elements, "
        f"{formula_result.n_semi_fixed_elements} semi-fixed, "
        f"{formula_result.n_variable_elements} variable. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 5: Find place names ---
    print("[Step 5/8] Finding confirmed place names...")
    t0 = time.time()
    place_name_result = find_place_names(
        corpus,
        confirmed_place_names=config.get("confirmed_place_names", None),
    )
    print(
        f"  Found {len(place_name_result.found)} matches for "
        f"{len(place_name_result.found) + len(place_name_result.not_found)} "
        f"place names. "
        f"{len(place_name_result.phonetic_anchors)} phonetic anchors. "
        f"({time.time() - t0:.1f}s)"
    )
    for match in place_name_result.found:
        site_info = (
            " (site matches!)" if match.site_matches_expected else ""
        )
        print(
            f"    {match.name}: found in {match.inscription_id} "
            f"at {match.site}{site_info}"
        )
    for nf in place_name_result.not_found:
        print(f"    {nf.name}: NOT FOUND in corpus")

    # --- Step 6: Assemble anchor vocabulary ---
    print("[Step 6/8] Assembling anchor vocabulary...")
    t0 = time.time()
    anchor_vocab = assemble_anchors(
        ideogram_result=ideogram_result,
        transaction_result=transaction_result,
        formula_result=formula_result,
        place_name_result=place_name_result,
        min_anchor_confidence=config.get("min_anchor_confidence", 0.3),
    )
    print(
        f"  {anchor_vocab.n_anchored} sign-groups anchored "
        f"(from {anchor_vocab.n_total_sign_groups} with any evidence). "
        f"By source: {dict(anchor_vocab.n_by_source)}. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 7: Format output ---
    print("[Step 7/8] Formatting output...")
    t0 = time.time()
    output = format_output(
        ideogram_result=ideogram_result,
        transaction_result=transaction_result,
        formula_result=formula_result,
        place_name_result=place_name_result,
        anchor_vocab=anchor_vocab,
        corpus_hash=corpus_hash,
        config=config,
        seed=seed,
    )
    print(f"  ({time.time() - t0:.1f}s)")

    # --- Step 8: Write output ---
    print("[Step 8/8] Writing output...")
    t0 = time.time()
    output_path = config.get("output_path", "results/pillar4_output.json")
    written_path = write_output(output, output_path)
    print(f"  Output written to: {written_path}. ({time.time() - t0:.1f}s)")

    total_time = time.time() - t_start
    print(f"\nPillar 4 pipeline complete. Total time: {total_time:.1f}s")

    # Print top anchors
    print(f"\nTop anchored sign-groups:")
    for anchor in anchor_vocab.anchored_sign_groups[:10]:
        translits = ", ".join(sorted(anchor.transliterations)[:3])
        print(
            f"  {'-'.join(anchor.sign_group_ids)}: "
            f"{anchor.semantic_field} "
            f"(conf={anchor.confidence:.2f}, "
            f"sources={anchor.n_evidence_sources}) "
            f"[{translits}]"
        )

    return output


def main() -> None:
    """CLI entry point for the Pillar 4 pipeline."""
    parser = argparse.ArgumentParser(
        description="Pillar 4: Semantic Anchoring",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/pillar4_default.yaml",
        help=(
            "Path to YAML configuration file "
            "(default: configs/pillar4_default.yaml)"
        ),
    )
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        run_pipeline(config)
    except Exception as e:
        print(f"\nPipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
