"""Pillar 1 pipeline orchestrator.

Runs all analysis steps in order to produce the Phonological Engine output:
1. Load corpus
2. Identify vowels
3. Detect alternations
4. Construct C-V grid
5. Analyze phonotactics
6. Validate against Linear B
7. Test dead vowel convention
8. Format and write output

Usage:
    python -m pillar1.pipeline --config configs/pillar1_default.yaml

All configuration is read from YAML. No hardcoded values.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .corpus_loader import load_corpus
from .vowel_identifier import identify_vowels, VowelInventory
from .alternation_detector import detect_alternations
from .grid_constructor import construct_grid
from .phonotactic_analyzer import analyze_phonotactics
from .lb_validator import validate_against_lb
from .dead_vowel_tester import test_dead_vowel
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
        raise ValueError(f"Config file must contain a YAML mapping, got {type(config)}")

    return config


def run_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full Pillar 1 pipeline.

    Args:
        config: Configuration dictionary from YAML.

    Returns:
        The assembled output dictionary.
    """
    t_start = time.time()

    # --- Step 1: Load corpus ---
    print("[Step 1/8] Loading corpus...")
    t0 = time.time()
    corpus = load_corpus(
        corpus_path=config["corpus_path"],
        sign_types_included=config.get("sign_types_included", ["syllabogram"]),
        exclude_damaged=config.get("exclude_damaged", True),
        min_word_length=config.get("min_word_length", 2),
    )
    print(f"  Loaded {corpus.total_inscriptions} inscriptions, "
          f"{corpus.total_words} words, "
          f"{corpus.unique_syllabograms} unique syllabograms. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 2: Identify vowels ---
    print("[Step 2/8] Identifying vowels...")
    t0 = time.time()
    vowel_inv = identify_vowels(
        corpus=corpus,
        alpha=config.get("alpha", 0.05),
        min_sign_frequency=config.get("min_sign_frequency", 15),
        bootstrap_n=config.get("bootstrap_n", 1000),
        seed=config.get("seed", 1234),
    )
    vowel_sign_ids = [s.sign_id for s in vowel_inv.signs]
    print(f"  Found {vowel_inv.count} vowels (CI: {vowel_inv.count_ci_95}): "
          f"{vowel_sign_ids}. ({time.time() - t0:.1f}s)")

    # Optional vowel override: explicit sign IDs or count-based
    vowel_sign_override = config.get("vowel_sign_ids", [])
    if vowel_sign_override:
        # Explicit sign IDs — use these specific signs as vowels
        # Justification: LB transfer (Packard 1974, 2:1 to 5:1 odds)
        #   + independent confirmation for a (P1 enrichment), i/u (Jaccard)
        print(f"  OVERRIDE: Using explicit vowel signs {vowel_sign_override} "
              f"(LB-transferred, independently validated for a/i/u)")
        all_stats = vowel_inv.all_sign_stats
        override_signs = []
        stats_by_id = {s.sign_id: s for s in all_stats}
        for sid in vowel_sign_override:
            stat = stats_by_id.get(sid)
            if stat is not None:
                stat.classification = "pure_vowel"
                stat.confidence = max(0.0, min(1.0, stat.enrichment_score / 3.0))
                override_signs.append(stat)
            else:
                # Sign wasn't testable (too few occurrences for statistics)
                # Create a minimal stats entry — we're using LB consensus here
                from pillar1.vowel_identifier import SignPositionalStats
                # Count occurrences from positional records
                total = sum(
                    1 for rec in corpus.positional_records
                    if rec.sign_id == sid
                )
                override_signs.append(SignPositionalStats(
                    sign_id=sid,
                    initial_count=0,
                    medial_count=0,
                    final_count=0,
                    total_count=max(total, 1),
                    enrichment_score=0.0,
                    p_value_initial=1.0,
                    p_value_medial=1.0,
                    p_value_corrected=1.0,
                    classification="pure_vowel",
                    confidence=0.5,  # CONSENSUS_ASSUMED
                ))
        vowel_inv = VowelInventory(
            count=len(override_signs),
            count_ci_95=vowel_inv.count_ci_95,
            signs=override_signs,
            all_sign_stats=all_stats,
            global_initial_rate=vowel_inv.global_initial_rate,
            global_medial_rate=vowel_inv.global_medial_rate,
            global_final_rate=vowel_inv.global_final_rate,
            n_testable_signs=vowel_inv.n_testable_signs,
        )
        print(f"  Vowels set to: {[s.sign_id for s in override_signs]}")

    # --- Step 3: Detect alternations ---
    print("[Step 3/8] Detecting inflectional alternations...")
    t0 = time.time()
    alternation = detect_alternations(
        corpus=corpus,
        min_shared_prefix_length=config.get("min_shared_prefix_length", 1),
        max_suffix_diff_length=config.get("max_suffix_diff_length", 2),
        min_independent_stems=config.get("min_independent_stems", 2),
        alternation_alpha=config.get("alternation_alpha", 0.01),
    )
    print(f"  Found {alternation.total_significant_pairs} significant pairs "
          f"from {alternation.total_candidate_pairs} candidates. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 4: Construct C-V grid ---
    print("[Step 4/8] Constructing C-V grid...")
    t0 = time.time()
    grid = construct_grid(
        alternation=alternation,
        vowel_inv=vowel_inv,
        corpus=corpus,
        clustering_method=config.get("clustering_method", "spectral"),
        min_consonant_classes=config.get("min_consonant_classes", 3),
        max_consonant_classes=config.get("max_consonant_classes", 20),
        kmeans_n_init=config.get("kmeans_n_init", 50),
        low_confidence_threshold=config.get("low_confidence_threshold", 0.3),
        seed=config.get("seed", 1234),
    )
    print(f"  Grid: {grid.consonant_count} consonant classes x "
          f"{grid.vowel_count} vowel classes. "
          f"{len(grid.assignments)} assigned, "
          f"{len(grid.unassigned_signs)} unassigned. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 5: Analyze phonotactics ---
    print("[Step 5/8] Analyzing phonotactic constraints...")
    t0 = time.time()
    phonotactics = analyze_phonotactics(
        corpus=corpus,
        alternation=alternation,
        min_expected=config.get("min_expected_bigram", 2.0),
        phonotactic_alpha=config.get("phonotactic_alpha", 0.01),
        min_sign_frequency=config.get("min_sign_frequency", 15),
    )
    print(f"  Found {phonotactics.n_forbidden} forbidden bigrams, "
          f"{phonotactics.n_favored} favored bigrams. "
          f"Positional: {len(phonotactics.initial_only_signs)} initial-only, "
          f"{len(phonotactics.never_initial_signs)} never-initial, "
          f"{len(phonotactics.never_final_signs)} never-final. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 6: Validate against LB ---
    print("[Step 6/8] Validating against Linear B...")
    t0 = time.time()
    lb_validation = validate_against_lb(
        grid=grid,
        lb_validation_path=config["lb_validation_path"],
    )
    print(f"  ARI: consonant={lb_validation.consonant_ari:.3f}, "
          f"vowel={lb_validation.vowel_ari:.3f}. "
          f"{lb_validation.n_signs_with_lb_values} signs with LB values. "
          f"{len(lb_validation.disagreements)} disagreements. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 7: Test dead vowel convention ---
    print("[Step 7/8] Testing dead vowel convention...")
    t0 = time.time()
    dead_vowel = test_dead_vowel(
        grid=grid,
        corpus=corpus,
        alpha=config.get("alpha", 0.05),
    )
    print(f"  Same-vowel rate: {dead_vowel.same_vowel_rate:.3f} "
          f"(expected: {dead_vowel.expected_rate:.3f}). "
          f"p={dead_vowel.p_value:.4g}. "
          f"{'SIGNIFICANT' if dead_vowel.significant else 'not significant'}. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 8: Format and write output ---
    print("[Step 8/8] Formatting and writing output...")
    t0 = time.time()
    output = format_output(
        vowel_inv=vowel_inv,
        grid=grid,
        phonotactics=phonotactics,
        lb_validation=lb_validation,
        dead_vowel=dead_vowel,
        corpus=corpus,
        config=config,
        seed=config.get("seed", 1234),
    )

    output_path = config.get("output_path", "results/pillar1_output.json")
    written_path = write_output(output, output_path)
    print(f"  Output written to: {written_path}. ({time.time() - t0:.1f}s)")

    total_time = time.time() - t_start
    print(f"\nPillar 1 pipeline complete. Total time: {total_time:.1f}s")

    return output


def main() -> None:
    """CLI entry point for the Pillar 1 pipeline."""
    parser = argparse.ArgumentParser(
        description="Pillar 1: Phonological Engine — The Computational Grid",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/pillar1_default.yaml",
        help="Path to YAML configuration file (default: configs/pillar1_default.yaml)",
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
