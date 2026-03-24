"""Pillar 2 pipeline orchestrator.

Runs all morphological analysis steps in order:
1. Load Pillar 1 output (phonological constraints)
2. Load corpus
3. Segment words into stems + affixes
4. Extract affix inventory with productivity
5. Induce paradigm classes
6. Classify inflection vs. derivation
7. Hint word classes
8. Format and write output

Usage:
    python -m pillar2.pipeline --config configs/pillar2_default.yaml

All configuration is read from YAML. No hardcoded values.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict

import yaml

from pillar1.corpus_loader import load_corpus
from .pillar1_loader import load_pillar1
from .segmenter import segment_corpus
from .affix_extractor import extract_affixes
from .paradigm_inducer import induce_paradigms
from .inflection_classifier import classify_affixes
from .word_class_hinter import hint_word_classes
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
    """Run the full Pillar 2 pipeline.

    Args:
        config: Configuration dictionary from YAML.

    Returns:
        The assembled output dictionary.
    """
    t_start = time.time()

    # --- Step 1: Load Pillar 1 output ---
    print("[Step 1/8] Loading Pillar 1 output...")
    t0 = time.time()
    pillar1 = load_pillar1(config["pillar1_output_path"])
    print(f"  Loaded {len(pillar1.grid_assignments)} grid assignments, "
          f"{len(pillar1.vowel_signs)} vowel signs, "
          f"{len(pillar1.favored_bigrams)} favored bigrams, "
          f"{len(pillar1.forbidden_bigrams)} forbidden bigrams. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 2: Load corpus ---
    print("[Step 2/8] Loading corpus...")
    t0 = time.time()
    corpus = load_corpus(
        corpus_path=config["corpus_path"],
        sign_types_included=["syllabogram"],
        exclude_damaged=True,
        min_word_length=config.get("min_word_length", 2),
    )
    print(f"  Loaded {corpus.total_inscriptions} inscriptions, "
          f"{corpus.total_words} words, "
          f"{corpus.unique_syllabograms} unique syllabograms. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 3: Segment corpus ---
    print("[Step 3/8] Segmenting corpus...")
    t0 = time.time()
    lexicon = segment_corpus(
        corpus=corpus,
        pillar1=pillar1,
        method=config.get("segmentation_method", "suffix_strip"),
        min_word_length=config.get("min_word_length", 2),
        min_suffix_frequency=config.get("min_suffix_frequency", 3),
        min_suffix_stems=config.get("min_suffix_stems", 2),
        max_suffix_length=config.get("max_suffix_length", 3),
        lambda_phon=config.get("lambda_phon", 1.0),
        bpe_min_merge_freq=config.get("bpe_min_merge_freq", 3),
        bpe_max_merges=config.get("bpe_max_merges", 100),
    )
    print(f"  Segmented {lexicon.total_words} unique words: "
          f"{lexicon.words_with_suffixes} with suffixes, "
          f"{lexicon.words_unsegmented} unsegmented. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 4: Extract affixes ---
    print("[Step 4/8] Extracting affix inventory...")
    t0 = time.time()
    affix_inv = extract_affixes(
        lexicon=lexicon,
        min_affix_stems=config.get("min_affix_stems", 2),
    )
    print(f"  Found {len(affix_inv.suffixes)} suffixes, "
          f"{len(affix_inv.prefixes)} prefixes. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 5: Induce paradigms ---
    print("[Step 5/8] Inducing paradigm classes...")
    t0 = time.time()
    paradigm_table = induce_paradigms(
        lexicon=lexicon,
        affix_inv=affix_inv,
        pillar1=pillar1,
        jaccard_threshold=config.get("jaccard_threshold", 0.3),
        min_paradigm_members=config.get("min_paradigm_members", 2),
        min_paradigm_slots=config.get("min_paradigm_slots", 2),
        max_paradigm_classes=config.get("max_paradigm_classes", 15),
    )
    print(f"  Induced {paradigm_table.n_classes} paradigm classes. "
          f"({time.time() - t0:.1f}s)")

    # --- Step 6: Classify inflection vs. derivation ---
    print("[Step 6/8] Classifying affixes...")
    t0 = time.time()
    affix_inv = classify_affixes(
        affix_inv=affix_inv,
        paradigm_table=paradigm_table,
        inflectional_threshold=config.get("inflectional_productivity_threshold", 0.3),
        derivational_threshold=config.get("derivational_productivity_threshold", 0.1),
    )
    n_infl = sum(1 for a in affix_inv.suffixes if a.classification == "inflectional")
    n_deriv = sum(1 for a in affix_inv.suffixes if a.classification == "derivational")
    n_ambig = sum(1 for a in affix_inv.suffixes if a.classification == "ambiguous")
    print(f"  Classified: {n_infl} inflectional, {n_deriv} derivational, "
          f"{n_ambig} ambiguous. ({time.time() - t0:.1f}s)")

    # --- Step 7: Hint word classes ---
    print("[Step 7/8] Hinting word classes...")
    t0 = time.time()
    wc_result = hint_word_classes(
        lexicon=lexicon,
        affix_inv=affix_inv,
        paradigm_table=paradigm_table,
    )
    for wc in wc_result.word_classes:
        print(f"  {wc.label}: {wc.n_stems} stems")
    print(f"  ({time.time() - t0:.1f}s)")

    # --- Step 8: Format and write output ---
    print("[Step 8/8] Formatting and writing output...")
    t0 = time.time()
    output = format_output(
        lexicon=lexicon,
        affix_inv=affix_inv,
        paradigm_table=paradigm_table,
        word_classes=wc_result,
        pillar1=pillar1,
        corpus_hash=corpus.corpus_hash,
        config=config,
        seed=config.get("seed", 1234),
    )

    output_path = config.get("output_path", "results/pillar2_output.json")
    written_path = write_output(output, output_path)
    print(f"  Output written to: {written_path}. ({time.time() - t0:.1f}s)")

    total_time = time.time() - t_start
    print(f"\nPillar 2 pipeline complete. Total time: {total_time:.1f}s")

    return output


def main() -> None:
    """CLI entry point for the Pillar 2 pipeline."""
    parser = argparse.ArgumentParser(
        description="Pillar 2: Morphological Decomposition — Automated Kober",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="configs/pillar2_default.yaml",
        help="Path to YAML configuration file (default: configs/pillar2_default.yaml)",
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
