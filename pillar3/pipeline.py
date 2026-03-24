"""Pillar 3 pipeline orchestrator.

Runs all distributional grammar induction steps in order:
1. Load config from YAML
2. Load all data (data_loader.load_all)
3. Build distributional profiles (profile_builder)
4. Induce word classes (word_class_inducer)
5. Analyze word order (word_order_analyzer)
6. Detect agreement (agreement_detector)
7. Find functional words (functional_word_finder)
8. Build grammar sketch (grammar_sketch_builder)
9. Format and write output (output_formatter)

Usage:
    python -m pillar3.pipeline --config configs/pillar3_default.yaml
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from .data_loader import load_all
from .profile_builder import build_profiles
from .word_class_inducer import induce_word_classes
from .word_order_analyzer import analyze_word_order
from .agreement_detector import detect_agreement
from .functional_word_finder import find_functional_words
from .grammar_sketch_builder import build_grammar_sketch
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


def run_pipeline(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full Pillar 3 pipeline.

    Args:
        config: Configuration dictionary from YAML.

    Returns:
        The assembled output dictionary.
    """
    t_start = time.time()
    seed = config.get("seed", 1234)

    # --- Step 1: Load all data ---
    print("[Step 1/9] Loading all data...")
    t0 = time.time()
    data = load_all(
        pillar1_path=config.get("pillar1_output_path", "results/pillar1_output.json"),
        pillar2_path=config.get("pillar2_output_path", "results/pillar2_output.json"),
        corpus_path=config.get("corpus_path", "data/sigla_full_corpus.json"),
    )
    print(
        f"  Loaded {len(data.inscriptions)} inscriptions, "
        f"{len(data.pillar2.segmented_lexicon)} segmented words, "
        f"{len(data.pillar1.grid_assignments)} grid assignments. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 2: Build distributional profiles ---
    print("[Step 2/9] Building distributional profiles...")
    t0 = time.time()
    profile_config = {
        "min_stem_frequency": config.get("min_stem_frequency", 2),
        "top_k_contexts": config.get("n_top_contexts", 20),
        "ppmi_smoothing": 0.75,
    }
    profiles = build_profiles(data, config=profile_config)
    print(
        f"  Built profiles for {len(profiles.stems)} stems "
        f"({profiles.feature_matrix.shape[1]} features). "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 3: Induce word classes ---
    print("[Step 3/9] Inducing word classes...")
    t0 = time.time()
    wc_config = {
        "min_k": config.get("min_word_classes", 3),
        "max_k": config.get("max_word_classes", 10),
        "svd_target_variance": config.get("svd_variance_threshold", 0.80),
        "svd_max_components": config.get("svd_n_components", 15),
        "svd_min_components": 5,
        "silhouette_weight": 1.0 - config.get("morphological_coherence_weight", 0.3),
        "morph_coherence_weight": config.get("morphological_coherence_weight", 0.3),
        "random_state": seed,
    }
    word_classes = induce_word_classes(
        profiles, data.pillar2, config=wc_config
    )
    print(
        f"  Induced {word_classes.n_classes} word classes "
        f"(silhouette={word_classes.silhouette:.3f}). "
        f"({time.time() - t0:.1f}s)"
    )
    for cls in word_classes.classes:
        print(f"    Class {cls.class_id} ({cls.suggested_label}): "
              f"{cls.n_members} members, profile={cls.morphological_profile}")

    # --- Step 4: Analyze word order ---
    print("[Step 4/9] Analyzing word order...")
    t0 = time.time()
    wo_config = {
        "min_words_per_inscription": config.get("min_inscription_words", 3),
        "min_pair_count": 3,
        "alpha": config.get("word_order_alpha", 0.01),
    }
    word_order = analyze_word_order(data, word_classes, config=wo_config)
    n_sig = sum(1 for po in word_order.pairwise_orders if po.p_value < 0.05)
    print(
        f"  Analyzed {word_order.n_bigrams_analyzed} class bigrams from "
        f"{word_order.n_inscriptions_used} inscriptions. "
        f"{n_sig} significant orderings. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 5: Detect agreement ---
    print("[Step 5/9] Detecting agreement patterns...")
    t0 = time.time()
    ag_config = {
        "min_adjacent_pairs": config.get("min_adjacent_pairs", 5),
        "alpha": config.get("agreement_alpha", 0.01),
    }
    agreement = detect_agreement(data, word_classes, config=ag_config)
    print(
        f"  Tested {agreement.n_pairs_tested} class pairs. "
        f"{agreement.n_pairs_significant} significant agreement patterns. "
        f"Expected rate by chance: {agreement.expected_rate:.4f}. "
        f"({time.time() - t0:.1f}s)"
    )

    # --- Step 6: Find functional words ---
    print("[Step 6/9] Finding functional words...")
    t0 = time.time()
    fw_config = {
        "max_length": config.get("max_functional_word_length", 2),
        "min_freq": config.get("min_functional_word_freq", 5),
        "min_inscriptions": config.get("min_functional_word_inscriptions", 5),
    }
    functional_words = find_functional_words(
        data, word_classes=word_classes, config=fw_config
    )
    print(
        f"  Screened {functional_words.n_candidates_screened} candidates, "
        f"identified {functional_words.n_functional} functional words. "
        f"({time.time() - t0:.1f}s)"
    )
    for fw in functional_words.functional_words[:5]:
        print(f"    {fw.reading}: {fw.classification} "
              f"(freq={fw.frequency}, inscriptions={fw.n_inscriptions})")

    # --- Step 7: Build grammar sketch ---
    print("[Step 7/9] Building grammar sketch...")
    t0 = time.time()
    grammar_sketch = build_grammar_sketch(
        word_classes=word_classes,
        word_order=word_order,
        agreement=agreement,
        functional_words=functional_words,
        pillar2=data.pillar2,
    )
    print(f"  {grammar_sketch.summary}")
    print(f"  ({time.time() - t0:.1f}s)")

    # --- Step 8: Format output ---
    print("[Step 8/9] Formatting output...")
    t0 = time.time()
    output = format_output(
        word_classes=word_classes,
        word_order=word_order,
        agreement=agreement,
        functional_words=functional_words,
        grammar_sketch=grammar_sketch,
        corpus_hash=data.corpus_hash,
        pillar1_hash=data.pillar1.pillar1_hash,
        pillar2_hash=data.pillar2.pillar2_hash,
        config=config,
        seed=seed,
    )
    print(f"  ({time.time() - t0:.1f}s)")

    # --- Step 9: Write output ---
    print("[Step 9/9] Writing output...")
    t0 = time.time()
    output_path = config.get("output_path", "results/pillar3_output.json")
    written_path = write_output(output, output_path)
    print(f"  Output written to: {written_path}. ({time.time() - t0:.1f}s)")

    total_time = time.time() - t_start
    print(f"\nPillar 3 pipeline complete. Total time: {total_time:.1f}s")

    return output


def main() -> None:
    """CLI entry point for the Pillar 3 pipeline."""
    parser = argparse.ArgumentParser(
        description="Pillar 3: Distributional Grammar Induction",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/pillar3_default.yaml",
        help="Path to YAML configuration file (default: configs/pillar3_default.yaml)",
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
