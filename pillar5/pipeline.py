"""Pillar 5 pipeline orchestrator (Multi-Source Vocabulary Resolution).

Runs all vocabulary resolution steps in order:
1. Load config from YAML
2. Assemble constraints from Pillars 1-4
3. Load candidate language lexicons
4. Load Phonetic Prior results (if available)
5. Search all languages simultaneously
6. Detect emergent strata
7. Cross-reference old cognate files
8. Format and write output

Usage:
    python -m pillar5.pipeline --config configs/pillar5_default.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .constraint_assembler import assemble_constraints
from .lexicon_loader import load_all_lexicons, audit_gloss_availability
from .pp_result_loader import load_pp_results
from .cognate_list_assembler import search_all_languages, cross_reference_old_cognates
from .stratum_detector import detect_strata, compute_compositional_portrait
from .output_formatter import format_output, write_output


def load_config(config_path: str | Path) -> Dict[str, Any]:
    """Load pipeline configuration from a YAML file."""
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
    if not path.exists():
        return "corpus_not_found"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full Pillar 5 pipeline.

    Args:
        config: Configuration dictionary from YAML.

    Returns:
        The assembled output dictionary.
    """
    t_start = time.time()
    seed = config.get("seed", 1234)
    corpus_path = config.get("corpus_path", "data/sigla_full_corpus.json")
    corpus_hash = _compute_corpus_hash(corpus_path)

    # --- Step 1: Assemble constraints from P1-P4 ---
    print("[Step 1/8] Assembling constraints from Pillars 1-4...")
    t0 = time.time()
    constrained_vocab = assemble_constraints(
        p1_path=config.get("pillar1_output", "results/pillar1_output.json"),
        p2_path=config.get("pillar2_output", "results/pillar2_output.json"),
        p3_path=config.get("pillar3_output", "results/pillar3_output.json"),
        p4_path=config.get("pillar4_output", "results/pillar4_output.json"),
        sign_to_ipa_path=config.get("sign_to_ipa_path", "data/sign_to_ipa.json"),
        corpus_path=config.get("corpus_path", "data/sigla_full_corpus.json"),
    )
    print(
        f"  {constrained_vocab.n_total_in_corpus} total sign-groups, "
        f"{constrained_vocab.n_functional_excluded} functional excluded, "
        f"{constrained_vocab.n_no_constraints} no constraints, "
        f"{constrained_vocab.n_matchable} matchable. "
        f"Acceptance rate: {constrained_vocab.acceptance_rate:.1%}. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 2: Load candidate language lexicons ---
    print("[Step 2/8] Loading candidate language lexicons...")
    t0 = time.time()
    lexicon_dir = config.get(
        "lexicon_dir",
        "../ancient-scripts-datasets/data/training/lexicons"
    )
    language_codes = config.get("candidate_languages", None)
    max_entries = config.get("max_lexicon_entries", 0)

    lexicons = load_all_lexicons(
        lexicon_dir, language_codes, max_entries_per_language=max_entries
    )
    print(
        f"  Loaded {len(lexicons)} lexicons: "
        + ", ".join(
            f"{k} ({v.n_entries} entries, {v.gloss_coverage:.0%} glosses)"
            for k, v in sorted(lexicons.items())
        )
        + f" ({time.time() - t0:.1f}s)"
    )

    # Audit gloss availability
    gloss_audit = audit_gloss_availability(lexicons)
    usable = sum(1 for g in gloss_audit if g["usable_for_semantic"])
    print(f"  Gloss audit: {usable}/{len(gloss_audit)} languages usable for semantic scoring")

    # --- Step 3: Load PP results (if available) ---
    print("[Step 3/8] Loading Phonetic Prior results...")
    t0 = time.time()
    pp_output_dir = config.get("pp_output_dir", "")
    pp_results = load_pp_results(pp_output_dir, language_codes) if pp_output_dir else {}
    if pp_results:
        print(
            f"  Loaded PP results for {len(pp_results)} languages. "
            f"({time.time() - t0:.1f}s)"
        )
    else:
        print(
            f"  No PP results available — using edit distance fallback. "
            f"({time.time() - t0:.1f}s)"
        )

    # --- Step 4: Multi-language simultaneous search ---
    print("[Step 4/8] Searching all languages simultaneously...")
    t0 = time.time()
    all_matches = search_all_languages(
        constrained_vocab=constrained_vocab,
        lexicons=lexicons,
        pp_matches=None,  # TODO: wire in PP results when available
        min_match_threshold=config.get("min_match_threshold", 0.0),
        max_per_language=config.get("max_per_language", 5),
        max_edit_distance=config.get("max_edit_distance", 0.7),
    )
    n_with = sum(1 for m in all_matches if m.n_matches > 0)
    n_sig = sum(1 for m in all_matches if m.has_significant_match)
    print(
        f"  {len(all_matches)} sign-groups searched, "
        f"{n_with} with candidate matches, "
        f"{n_sig} with significant matches. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 5: Detect emergent strata ---
    print("[Step 5/8] Detecting emergent vocabulary strata...")
    t0 = time.time()
    stratum_analysis = detect_strata(
        all_matches,
        match_threshold=config.get("stratum_threshold", 0.5),
        min_stratum_size=config.get("min_stratum_size", 5),
    )
    portrait = compute_compositional_portrait(stratum_analysis)
    print(
        f"  {stratum_analysis.n_strata} strata detected. "
        f"Substrate fraction: {stratum_analysis.substrate_fraction:.1%}. "
        f"({time.time() - t0:.1f}s)"
    )
    for s in stratum_analysis.strata:
        if not s.is_noise:
            print(f"    Stratum {s.stratum_id}: {s.dominant_language_name} "
                  f"({s.n_sign_groups} sign-groups, {s.proportion:.1%})")

    # --- Step 6: Cross-reference old cognate files ---
    print("[Step 6/8] Cross-referencing old cognate files...")
    t0 = time.time()
    old_cognate_dir = config.get("old_cognate_dir", "")
    crossref = cross_reference_old_cognates(
        all_matches, old_cognate_dir if old_cognate_dir else None
    )
    print(f"  {crossref.get('status', 'unknown')}. ({time.time() - t0:.1f}s)")

    # --- Step 7: Format output ---
    print("[Step 7/8] Formatting output...")
    t0 = time.time()
    output = format_output(
        constrained_vocab=constrained_vocab,
        all_matches=all_matches,
        stratum_analysis=stratum_analysis,
        compositional_portrait=portrait,
        crossref=crossref,
        corpus_hash=corpus_hash,
        config=config,
        seed=seed,
    )
    print(f"  ({time.time() - t0:.1f}s)")

    # --- Step 8: Write output ---
    print("[Step 8/8] Writing output...")
    t0 = time.time()
    output_path = config.get("output_path", "results/pillar5_output.json")
    written_path = write_output(output, output_path)
    print(f"  Output written to: {written_path}. ({time.time() - t0:.1f}s)")

    total_time = time.time() - t_start
    print(f"\nPillar 5 pipeline complete. Total time: {total_time:.1f}s")

    # Print top matches
    top_matches = sorted(
        [m for m in all_matches if m.best_match is not None],
        key=lambda m: -m.best_match.combined_score,
    )[:10]
    if top_matches:
        print(f"\nTop vocabulary matches:")
        for sgm in top_matches:
            bm = sgm.best_match
            ids = "-".join(sgm.sign_group_ids)
            print(
                f"  {ids} ({sgm.stem_ipa_lb}): "
                f"{bm.language_name} '{bm.word}' ({bm.ipa}) "
                f"[score={bm.combined_score:.3f}, "
                f"sem={sgm.semantic_field or 'none'}]"
            )

    return output


def main() -> None:
    """CLI entry point for the Pillar 5 pipeline."""
    parser = argparse.ArgumentParser(
        description="Pillar 5: Multi-Source Vocabulary Resolution",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/pillar5_default.yaml",
        help=(
            "Path to YAML configuration file "
            "(default: configs/pillar5_default.yaml)"
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
