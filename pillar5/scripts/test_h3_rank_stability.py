#!/usr/bin/env python3
"""
test_h3_rank_stability.py -- Hypothesis 3: Rank Stability Across Progressive Scan Extensions

HYPOTHESIS: A real cognate match should be STABLE across progressive scan
extensions. If "a-sa-sa" matches Lydian best, then "a-sa-sa-ra" should ALSO
match Lydian well. If the winner flips to a different language with each
extension, the original match was noise.

We test this by:
  1. Loading all LA-vs-candidate data and grouping entries into progressive
     chains (prefix sequences).
  2. For each chain, computing which language "wins" (best per-char score)
     at each extension level and measuring rank stability.
  3. Running the same analysis on Latin-vs-Oscan validation data (known
     cognate pairs should show HIGH stability).
  4. Comparing the LA stability distribution against the known-cognate baseline.

Usage:
    python pillar5/scripts/test_h3_rank_stability.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PILLAR5_DIR = SCRIPT_DIR.parent
VENTRIS_DIR = PILLAR5_DIR.parent

LA_CLEAN_DIR = Path(r"C:\Users\alvin\ancient-scripts-datasets\data\linear_a_cognates_clean")
FLEET_DIR = Path(r"C:\Users\alvin\ancient-scripts-datasets\data\fleet_results_v2")

OUTPUT_DIR = PILLAR5_DIR / "data" / "h3_rank_stability"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Data Loading: Linear A cognate data (all languages)
# ---------------------------------------------------------------------------
def load_la_combined(path: Path) -> list[dict]:
    """Load all_languages_combined.tsv -> list of dicts."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            try:
                row["score"] = float(row["score"])
                row["ipa_length"] = int(row["ipa_length"])
            except (ValueError, KeyError):
                continue
            rows.append(row)
    return rows


def load_la_per_language(la_dir: Path) -> dict[str, list[dict]]:
    """Load individual LA-vs-LANG files -> {lang_code: [rows]}."""
    result = {}
    for tsv_file in sorted(la_dir.glob("linear_a_vs_*_clean.tsv")):
        # Extract lang code from filename: linear_a_vs_XLD_clean.tsv -> xld
        parts = tsv_file.stem.split("_vs_")
        if len(parts) < 2:
            continue
        lang_code = parts[1].replace("_clean", "")
        rows = []
        with open(tsv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                try:
                    row["score"] = float(row["score"])
                    row["ipa_length"] = int(row["ipa_length"])
                except (ValueError, KeyError):
                    continue
                row["candidate_language"] = lang_code
                rows.append(row)
        result[lang_code] = rows
    return result


# ---------------------------------------------------------------------------
# Data Loading: Validation (Latin-vs-Oscan)
# ---------------------------------------------------------------------------
def load_lat_vs_osc(fleet_dir: Path) -> list[dict]:
    """Load lat_vs_osc cognate_list.tsv from the first available machine."""
    for machine_dir in sorted(fleet_dir.iterdir()):
        tsv = machine_dir / "outputs" / "validation" / "lat_vs_osc" / "cognate_list.tsv"
        if tsv.exists():
            rows = []
            with open(tsv, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    try:
                        row["score"] = float(row["score"])
                    except (ValueError, KeyError):
                        continue
                    rows.append(row)
            print(f"  Loaded {len(rows)} lat_vs_osc rows from {machine_dir.name}")
            return rows
    raise FileNotFoundError("No lat_vs_osc cognate_list.tsv found in fleet_results_v2")


# ---------------------------------------------------------------------------
# Chain Detection
# ---------------------------------------------------------------------------
def build_progressive_chains_la(all_lang_data: dict[str, list[dict]]) -> dict[str, list[str]]:
    """
    Build progressive chains from LA sign sequences.

    A chain is a set of sign sequences where each is a prefix of the next:
      a-da-da -> a-da-da-u -> a-da-da-u-t -> a-da-da-u-ti -> ...

    Returns: {chain_root: [seq1, seq2, ...]} sorted by length.
    """
    # Collect all unique sign sequences across all languages
    all_signs = set()
    for lang, rows in all_lang_data.items():
        for row in rows:
            all_signs.add(row["linear_a_signs"])

    all_signs = sorted(all_signs)

    # Build chains: group sign sequences that are progressive extensions
    # A sign sequence X is a prefix of Y if Y starts with X + "-"
    chains: dict[str, list[str]] = {}

    for sign_seq in all_signs:
        # Find the chain this belongs to
        placed = False
        for root, members in chains.items():
            # Check if this sequence extends any member of this chain
            if sign_seq.startswith(root + "-") or sign_seq == root:
                members.append(sign_seq)
                placed = True
                break
            # Check if this sequence IS a prefix of the root
            if root.startswith(sign_seq + "-"):
                # This is a new shorter root; rekey the chain
                members.insert(0, sign_seq)
                chains[sign_seq] = members
                del chains[root]
                placed = True
                break

        if not placed:
            chains[sign_seq] = [sign_seq]

    # Now refine: we need proper prefix chains, not just any grouping.
    # Rebuild more carefully.
    chains = {}
    sorted_signs = sorted(all_signs, key=lambda s: (len(s), s))

    assigned = set()
    for sign_seq in sorted_signs:
        if sign_seq in assigned:
            continue
        # Start a new chain with this as root
        chain = [sign_seq]
        assigned.add(sign_seq)
        # Find all extensions
        for other in sorted_signs:
            if other in assigned:
                continue
            if other.startswith(sign_seq + "-"):
                # Check it's a genuine extension of the last chain member
                # (i.e., each step adds exactly one syllable)
                chain.append(other)
                assigned.add(other)

        if len(chain) > 1:
            chains[sign_seq] = sorted(chain, key=len)

    return chains


def build_progressive_chains_validation(rows: list[dict]) -> dict[str, list[str]]:
    """
    Build progressive chains from Latin progressive scan data.

    The "lost" column contains progressively extended character sequences:
      abu -> abue -> abuer -> abueru -> ...

    Returns: {chain_root: [seq1, seq2, ...]} sorted by length.
    """
    all_seqs = sorted(set(row["lost"] for row in rows))

    chains: dict[str, list[str]] = {}
    assigned = set()

    sorted_seqs = sorted(all_seqs, key=lambda s: (len(s), s))

    for seq in sorted_seqs:
        if seq in assigned:
            continue
        chain = [seq]
        assigned.add(seq)
        for other in sorted_seqs:
            if other in assigned:
                continue
            if other.startswith(seq):
                chain.append(other)
                assigned.add(other)

        if len(chain) > 1:
            chains[seq] = sorted(chain, key=len)

    return chains


# ---------------------------------------------------------------------------
# Rank Stability Computation (LA data)
# ---------------------------------------------------------------------------
def compute_la_stability(
    chains: dict[str, list[str]],
    all_lang_data: dict[str, list[dict]],
    min_chain_length: int = 3,
) -> list[dict]:
    """
    For each chain, determine which language "wins" at each extension level.

    Winner = language with the best per-character score at that level.
    Per-char score = raw_score / ipa_length.

    Stability = fraction of pairwise consecutive extensions that agree on the
    winning language.

    Returns list of chain analysis results.
    """
    # Build lookup: (sign_seq, lang) -> (score, ipa_length, matched_word)
    lookup: dict[tuple[str, str], tuple[float, int, str]] = {}
    for lang, rows in all_lang_data.items():
        for row in rows:
            key = (row["linear_a_signs"], lang)
            lookup[key] = (row["score"], row["ipa_length"], row.get("matched_word", ""))

    results = []
    for root, chain_members in chains.items():
        if len(chain_members) < min_chain_length:
            continue

        # For each extension level, find the winning language
        winners = []
        winner_details = []
        for sign_seq in chain_members:
            best_lang = None
            best_per_char = float("-inf")
            lang_scores = {}
            for lang in all_lang_data:
                key = (sign_seq, lang)
                if key in lookup:
                    score, ipa_len, matched = lookup[key]
                    per_char = score / ipa_len if ipa_len > 0 else float("-inf")
                    lang_scores[lang] = per_char
                    if per_char > best_per_char:
                        best_per_char = per_char
                        best_lang = lang

            if best_lang is not None:
                winners.append(best_lang)
                winner_details.append({
                    "sign_seq": sign_seq,
                    "winner": best_lang,
                    "per_char_score": best_per_char,
                    "all_scores": lang_scores,
                })

        if len(winners) < min_chain_length:
            continue

        # Compute stability: fraction of consecutive pairs that agree
        agreements = sum(1 for i in range(len(winners) - 1) if winners[i] == winners[i + 1])
        stability = agreements / (len(winners) - 1) if len(winners) > 1 else 0.0

        # Also compute "dominant language" fraction
        from collections import Counter
        lang_counts = Counter(winners)
        dominant_lang, dominant_count = lang_counts.most_common(1)[0]
        dominance = dominant_count / len(winners)

        # Count number of distinct winners
        n_distinct = len(set(winners))

        results.append({
            "chain_root": root,
            "chain_length": len(winners),
            "stability": stability,
            "dominance": dominance,
            "dominant_language": dominant_lang,
            "n_distinct_winners": n_distinct,
            "winners": winners,
            "details": winner_details,
        })

    return results


# ---------------------------------------------------------------------------
# Rank Stability for Validation (single-language progressive scan)
# ---------------------------------------------------------------------------
def compute_validation_stability(
    chains: dict[str, list[str]],
    rows: list[dict],
    min_chain_length: int = 3,
) -> list[dict]:
    """
    For validation data (lat_vs_osc), each row has a "lost" (Latin form), a
    "top1_known" (best Oscan match), and "score".

    We measure stability of the top-1 Oscan word across extensions.
    If the same Oscan word keeps winning, stability is high.
    """
    # Build lookup: lost_form -> (top1, score)
    lookup: dict[str, tuple[str, float]] = {}
    for row in rows:
        lost = row["lost"]
        top1 = row["top1_known"]
        score = row["score"]
        lookup[lost] = (top1, score)

    results = []
    for root, chain_members in chains.items():
        if len(chain_members) < min_chain_length:
            continue

        winners = []
        for seq in chain_members:
            if seq in lookup:
                top1, score = lookup[seq]
                winners.append(top1)

        if len(winners) < min_chain_length:
            continue

        # Stability: fraction of consecutive pairs that agree
        agreements = sum(1 for i in range(len(winners) - 1) if winners[i] == winners[i + 1])
        stability = agreements / (len(winners) - 1) if len(winners) > 1 else 0.0

        from collections import Counter
        lang_counts = Counter(winners)
        dominant_word, dominant_count = lang_counts.most_common(1)[0]
        dominance = dominant_count / len(winners)
        n_distinct = len(set(winners))

        results.append({
            "chain_root": root,
            "chain_length": len(winners),
            "stability": stability,
            "dominance": dominance,
            "dominant_match": dominant_word,
            "n_distinct_winners": n_distinct,
            "winners": winners,
        })

    return results


# ---------------------------------------------------------------------------
# Analysis and Reporting
# ---------------------------------------------------------------------------
def histogram_text(values: list[float], bins: int = 10, width: int = 50) -> str:
    """Create a simple text histogram."""
    if not values:
        return "  (no data)\n"

    bin_edges = [i / bins for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        idx = min(int(v * bins), bins - 1)
        counts[idx] += 1

    max_count = max(counts) if counts else 1
    lines = []
    for i in range(bins):
        lo = bin_edges[i]
        hi = bin_edges[i + 1]
        bar_len = int(counts[i] / max_count * width) if max_count > 0 else 0
        bar = "#" * bar_len
        lines.append(f"  [{lo:.1f}-{hi:.1f}) {counts[i]:4d} |{bar}")
    return "\n".join(lines)


def percentile(values: list[float], p: float) -> float:
    """Compute the p-th percentile (0-100)."""
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = (len(sorted_v) - 1) * p / 100.0
    lo = int(idx)
    hi = min(lo + 1, len(sorted_v) - 1)
    frac = idx - lo
    return sorted_v[lo] * (1 - frac) + sorted_v[hi] * frac


def compute_la_word_stability(
    chains: dict[str, list[str]],
    all_lang_data: dict[str, list[dict]],
    min_chain_length: int = 3,
) -> dict[str, list[float]]:
    """
    For each language independently, measure whether the best-matched WORD
    stays the same across progressive extensions.

    This is directly comparable to the Latin-vs-Oscan validation metric.

    Returns: {lang_code: [stability_values]}
    """
    result: dict[str, list[float]] = defaultdict(list)

    for lang, rows in all_lang_data.items():
        # Build lookup: sign_seq -> (matched_word, score, ipa_length)
        lookup: dict[str, tuple[str, float, int]] = {}
        for row in rows:
            lookup[row["linear_a_signs"]] = (
                row.get("matched_word", ""),
                row["score"],
                row["ipa_length"],
            )

        for root, chain_members in chains.items():
            if len(chain_members) < min_chain_length:
                continue

            winners = []
            for sign_seq in chain_members:
                if sign_seq in lookup:
                    word, score, ipa_len = lookup[sign_seq]
                    winners.append(word)

            if len(winners) < min_chain_length:
                continue

            agreements = sum(1 for i in range(len(winners) - 1) if winners[i] == winners[i + 1])
            stability = agreements / (len(winners) - 1) if len(winners) > 1 else 0.0
            result[lang].append(stability)

    return dict(result)


def analyze_and_report(
    la_results: list[dict],
    val_results: list[dict],
    la_word_stability: dict[str, list[float]] | None = None,
    all_lang_data: dict[str, list[dict]] | None = None,
) -> str:
    """Generate the full analysis report."""
    lines = []
    lines.append("=" * 72)
    lines.append("HYPOTHESIS 3: RANK STABILITY ACROSS PROGRESSIVE SCAN EXTENSIONS")
    lines.append("=" * 72)

    # -----------------------------------------------------------------------
    # Part 1: LA Overall Stability Distribution
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 1: LINEAR A -- OVERALL STABILITY DISTRIBUTION")
    lines.append("-" * 72)

    la_stabilities = [r["stability"] for r in la_results]
    la_dominances = [r["dominance"] for r in la_results]

    lines.append(f"\n  Total chains analyzed: {len(la_results)}")
    if la_stabilities:
        lines.append(f"  Mean stability:       {sum(la_stabilities)/len(la_stabilities):.4f}")
        lines.append(f"  Median stability:     {percentile(la_stabilities, 50):.4f}")
        lines.append(f"  Std dev:              {(sum((s - sum(la_stabilities)/len(la_stabilities))**2 for s in la_stabilities)/len(la_stabilities))**0.5:.4f}")
        lines.append(f"  25th percentile:      {percentile(la_stabilities, 25):.4f}")
        lines.append(f"  75th percentile:      {percentile(la_stabilities, 75):.4f}")

    lines.append(f"\n  Stability histogram (consecutive-winner agreement):")
    lines.append(histogram_text(la_stabilities))

    lines.append(f"\n  Dominance histogram (fraction of extensions won by dominant lang):")
    lines.append(histogram_text(la_dominances))

    # -----------------------------------------------------------------------
    # Part 2: Per-Language Stability (LA)
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 2: LINEAR A -- PER-LANGUAGE STABILITY")
    lines.append("-" * 72)

    lang_stabilities: dict[str, list[float]] = defaultdict(list)
    for r in la_results:
        lang_stabilities[r["dominant_language"]].append(r["stability"])

    lines.append(f"\n  {'Language':<12} {'Count':>6} {'Mean Stab':>10} {'Median':>8} {'High(>0.8)':>10} {'Low(<0.3)':>10}")
    lines.append("  " + "-" * 62)
    for lang in sorted(lang_stabilities.keys(), key=lambda l: -sum(lang_stabilities[l]) / len(lang_stabilities[l])):
        stabs = lang_stabilities[lang]
        mean_s = sum(stabs) / len(stabs)
        median_s = percentile(stabs, 50)
        high = sum(1 for s in stabs if s > 0.8)
        low = sum(1 for s in stabs if s < 0.3)
        lines.append(f"  {lang:<12} {len(stabs):>6} {mean_s:>10.4f} {median_s:>8.4f} {high:>10} {low:>10}")

    # -----------------------------------------------------------------------
    # Part 3: High-Stability Chains (stability > 0.8)
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 3: HIGH-STABILITY CHAINS (stability > 0.8)")
    lines.append("-" * 72)

    high_stab = [r for r in la_results if r["stability"] > 0.8]
    lines.append(f"\n  Chains with stability > 0.8: {len(high_stab)} / {len(la_results)}")

    if high_stab:
        from collections import Counter
        high_langs = Counter(r["dominant_language"] for r in high_stab)
        lines.append(f"\n  Language distribution in high-stability chains:")
        for lang, count in high_langs.most_common():
            pct = 100.0 * count / len(high_stab)
            lines.append(f"    {lang:<12} {count:>4} ({pct:5.1f}%)")

        # Show top 10 highest-stability chains
        lines.append(f"\n  Top 10 highest-stability chains:")
        for r in sorted(high_stab, key=lambda x: (-x["stability"], -x["chain_length"]))[:10]:
            lines.append(f"    root={r['chain_root']:<30} len={r['chain_length']:>2} "
                         f"stab={r['stability']:.3f} dom={r['dominant_language']:<8} "
                         f"winners={r['winners']}")

    # -----------------------------------------------------------------------
    # Part 4: Low-Stability Chains (stability < 0.3)
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 4: LOW-STABILITY CHAINS (stability < 0.3)")
    lines.append("-" * 72)

    low_stab = [r for r in la_results if r["stability"] < 0.3]
    lines.append(f"\n  Chains with stability < 0.3: {len(low_stab)} / {len(la_results)}")

    if low_stab:
        from collections import Counter
        low_langs = Counter(r["dominant_language"] for r in low_stab)
        lines.append(f"\n  Language distribution in low-stability chains:")
        for lang, count in low_langs.most_common():
            pct = 100.0 * count / len(low_stab)
            lines.append(f"    {lang:<12} {count:>4} ({pct:5.1f}%)")

        # Show a few examples
        lines.append(f"\n  Sample low-stability chains (first 5):")
        for r in sorted(low_stab, key=lambda x: x["stability"])[:5]:
            lines.append(f"    root={r['chain_root']:<30} len={r['chain_length']:>2} "
                         f"stab={r['stability']:.3f} n_distinct={r['n_distinct_winners']} "
                         f"winners={r['winners']}")

    # -----------------------------------------------------------------------
    # Part 5: Validation Baseline (Latin-vs-Oscan)
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 5: VALIDATION BASELINE -- LATIN vs OSCAN (KNOWN COGNATES)")
    lines.append("-" * 72)

    val_stabilities = [r["stability"] for r in val_results]

    lines.append(f"\n  Total chains analyzed: {len(val_results)}")
    if val_stabilities:
        lines.append(f"  Mean stability:       {sum(val_stabilities)/len(val_stabilities):.4f}")
        lines.append(f"  Median stability:     {percentile(val_stabilities, 50):.4f}")
        lines.append(f"  Std dev:              {(sum((s - sum(val_stabilities)/len(val_stabilities))**2 for s in val_stabilities)/len(val_stabilities))**0.5:.4f}")
        lines.append(f"  25th percentile:      {percentile(val_stabilities, 25):.4f}")
        lines.append(f"  75th percentile:      {percentile(val_stabilities, 75):.4f}")

    lines.append(f"\n  Stability histogram (consecutive-winner agreement):")
    lines.append(histogram_text(val_stabilities))

    # How many high-stability chains?
    val_high = sum(1 for s in val_stabilities if s > 0.8)
    val_low = sum(1 for s in val_stabilities if s < 0.3)
    lines.append(f"\n  High stability (>0.8): {val_high} / {len(val_results)} ({100*val_high/len(val_results) if val_results else 0:.1f}%)")
    lines.append(f"  Low stability  (<0.3): {val_low} / {len(val_results)} ({100*val_low/len(val_results) if val_results else 0:.1f}%)")

    # -----------------------------------------------------------------------
    # Part 6: Head-to-Head Comparison
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 6: HEAD-TO-HEAD COMPARISON")
    lines.append("-" * 72)

    if la_stabilities and val_stabilities:
        la_mean = sum(la_stabilities) / len(la_stabilities)
        val_mean = sum(val_stabilities) / len(val_stabilities)
        la_median = percentile(la_stabilities, 50)
        val_median = percentile(val_stabilities, 50)

        la_high_pct = 100 * sum(1 for s in la_stabilities if s > 0.8) / len(la_stabilities)
        val_high_pct = 100 * sum(1 for s in val_stabilities if s > 0.8) / len(val_stabilities)

        la_low_pct = 100 * sum(1 for s in la_stabilities if s < 0.3) / len(la_stabilities)
        val_low_pct = 100 * sum(1 for s in val_stabilities if s < 0.3) / len(val_stabilities)

        lines.append(f"\n  {'Metric':<30} {'LA (all langs)':>15} {'Lat-vs-Osc':>15}")
        lines.append("  " + "-" * 62)
        lines.append(f"  {'Mean stability':<30} {la_mean:>15.4f} {val_mean:>15.4f}")
        lines.append(f"  {'Median stability':<30} {la_median:>15.4f} {val_median:>15.4f}")
        lines.append(f"  {'% chains stab > 0.8':<30} {la_high_pct:>14.1f}% {val_high_pct:>14.1f}%")
        lines.append(f"  {'% chains stab < 0.3':<30} {la_low_pct:>14.1f}% {val_low_pct:>14.1f}%")

        # Effect size (Cohen's d)
        la_var = sum((s - la_mean) ** 2 for s in la_stabilities) / len(la_stabilities)
        val_var = sum((s - val_mean) ** 2 for s in val_stabilities) / len(val_stabilities)
        pooled_std = ((la_var + val_var) / 2) ** 0.5
        if pooled_std > 0:
            cohens_d = (val_mean - la_mean) / pooled_std
            lines.append(f"\n  Cohen's d (Validation - LA): {cohens_d:.4f}")
            if abs(cohens_d) < 0.2:
                lines.append("  Interpretation: NEGLIGIBLE effect size -- distributions are similar")
            elif abs(cohens_d) < 0.5:
                lines.append("  Interpretation: SMALL effect size")
            elif abs(cohens_d) < 0.8:
                lines.append("  Interpretation: MEDIUM effect size")
            else:
                lines.append("  Interpretation: LARGE effect size -- distributions are very different")

        # Mann-Whitney U test (non-parametric)
        # Simple implementation without scipy
        n1 = len(la_stabilities)
        n2 = len(val_stabilities)

        # Compute U statistic
        u1 = 0
        for v in val_stabilities:
            for l in la_stabilities:
                if v > l:
                    u1 += 1
                elif v == l:
                    u1 += 0.5

        u_stat = u1
        expected_u = n1 * n2 / 2
        std_u = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
        if std_u > 0:
            z_score = (u_stat - expected_u) / std_u
            lines.append(f"\n  Mann-Whitney U test:")
            lines.append(f"    U = {u_stat:.0f}, z = {z_score:.4f}")
            if abs(z_score) > 2.576:
                lines.append(f"    p < 0.01 (highly significant)")
            elif abs(z_score) > 1.96:
                lines.append(f"    p < 0.05 (significant)")
            else:
                lines.append(f"    p >= 0.05 (not significant)")

    # -----------------------------------------------------------------------
    # Part 7: Lydian-Specific Analysis
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 7: LYDIAN-SPECIFIC STABILITY ANALYSIS")
    lines.append("-" * 72)

    # Chains where Lydian is the dominant winner
    lydian_chains = [r for r in la_results if r["dominant_language"] == "xld"]
    lines.append(f"\n  Chains where Lydian (xld) is dominant: {len(lydian_chains)} / {len(la_results)}")

    if lydian_chains:
        lyd_stabs = [r["stability"] for r in lydian_chains]
        lines.append(f"  Mean stability: {sum(lyd_stabs)/len(lyd_stabs):.4f}")
        lines.append(f"  Median stability: {percentile(lyd_stabs, 50):.4f}")
        lyd_high = sum(1 for s in lyd_stabs if s > 0.8)
        lines.append(f"  High stability (>0.8): {lyd_high} ({100*lyd_high/len(lyd_stabs):.1f}%)")

    # How often does Lydian appear in ANY position across all chains?
    lydian_appearances = 0
    lydian_wins_total = 0
    for r in la_results:
        for w in r["winners"]:
            if w == "xld":
                lydian_wins_total += 1
            lydian_appearances += 1

    if lydian_appearances > 0:
        lines.append(f"\n  Lydian win rate across all extension steps: "
                     f"{lydian_wins_total}/{lydian_appearances} "
                     f"({100*lydian_wins_total/lydian_appearances:.2f}%)")

    # -----------------------------------------------------------------------
    # Part 8: Chain-Length Effect
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 8: CHAIN LENGTH vs STABILITY")
    lines.append("-" * 72)

    # Group by chain length
    length_stab: dict[int, list[float]] = defaultdict(list)
    for r in la_results:
        length_stab[r["chain_length"]].append(r["stability"])

    lines.append(f"\n  {'Chain Len':>10} {'Count':>6} {'Mean Stab':>10} {'Median':>8}")
    lines.append("  " + "-" * 38)
    for length in sorted(length_stab.keys()):
        stabs = length_stab[length]
        mean_s = sum(stabs) / len(stabs)
        median_s = percentile(stabs, 50)
        lines.append(f"  {length:>10} {len(stabs):>6} {mean_s:>10.4f} {median_s:>8.4f}")

    # -----------------------------------------------------------------------
    # Part 9: Cross-Language Stability Comparison
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 9: DOES ANY LA LANGUAGE BEHAVE LIKE A KNOWN COGNATE?")
    lines.append("-" * 72)

    if val_stabilities:
        val_mean = sum(val_stabilities) / len(val_stabilities)
        val_std = (sum((s - val_mean) ** 2 for s in val_stabilities) / len(val_stabilities)) ** 0.5

        lines.append(f"\n  Validation baseline: mean={val_mean:.4f}, std={val_std:.4f}")
        lines.append(f"\n  Per-language comparison (languages with >=5 dominant chains):")
        lines.append(f"  {'Language':<12} {'Mean Stab':>10} {'Delta from Val':>15} {'Verdict':>15}")
        lines.append("  " + "-" * 56)

        for lang in sorted(lang_stabilities.keys()):
            stabs = lang_stabilities[lang]
            if len(stabs) < 5:
                continue
            lang_mean = sum(stabs) / len(stabs)
            delta = lang_mean - val_mean
            if lang_mean >= val_mean - val_std:
                verdict = "COGNATE-LIKE"
            elif lang_mean >= val_mean - 2 * val_std:
                verdict = "WEAK SIGNAL"
            else:
                verdict = "NOISE-LIKE"
            lines.append(f"  {lang:<12} {lang_mean:>10.4f} {delta:>+15.4f} {verdict:>15}")

    # -----------------------------------------------------------------------
    # Part 10: Within-Language Word Stability (apples-to-apples with validation)
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 10: WITHIN-LANGUAGE WORD STABILITY (APPLES-TO-APPLES)")
    lines.append("-" * 72)
    lines.append("""
  NOTE: Parts 1-6 compare LANGUAGE stability (LA, 18 candidates) against
  WORD stability (validation, many Oscan words). These are different metrics.
  This section computes WORD stability for LA: does the same matched word
  persist across extensions within each language? This is directly comparable
  to the Latin-vs-Oscan validation.""")

    if la_word_stability is not None:
        for lang_code, word_stabs in sorted(la_word_stability.items()):
            if len(word_stabs) < 3:
                continue
            mean_ws = sum(word_stabs) / len(word_stabs)
            median_ws = percentile(word_stabs, 50)
            high_ws = sum(1 for s in word_stabs if s > 0.8)
            low_ws = sum(1 for s in word_stabs if s < 0.3)
            lines.append(f"  {lang_code:<12} chains={len(word_stabs):>4}  mean={mean_ws:.4f}  "
                         f"median={median_ws:.4f}  high(>0.8)={high_ws:>3}  low(<0.3)={low_ws:>3}")

        # Overall LA word stability
        all_ws = []
        for stabs in la_word_stability.values():
            all_ws.extend(stabs)

        if all_ws and val_stabilities:
            la_ws_mean = sum(all_ws) / len(all_ws)
            val_mean_cmp = sum(val_stabilities) / len(val_stabilities)

            lines.append(f"\n  Overall LA word stability:  mean={la_ws_mean:.4f} (n={len(all_ws)})")
            lines.append(f"  Validation word stability: mean={val_mean_cmp:.4f} (n={len(val_stabilities)})")
            delta = la_ws_mean - val_mean_cmp
            lines.append(f"  Delta: {delta:+.4f}")

            la_ws_var = sum((s - la_ws_mean) ** 2 for s in all_ws) / len(all_ws)
            val_var = sum((s - val_mean_cmp) ** 2 for s in val_stabilities) / len(val_stabilities)
            pooled = ((la_ws_var + val_var) / 2) ** 0.5
            if pooled > 0:
                d = (val_mean_cmp - la_ws_mean) / pooled
                lines.append(f"  Cohen's d (val - LA word): {d:.4f}")

    # -----------------------------------------------------------------------
    # Part 11: Noise Baseline -- Random Language Assignment
    # -----------------------------------------------------------------------
    lines.append("\n" + "-" * 72)
    lines.append("PART 11: NOISE BASELINE -- EXPECTED STABILITY UNDER RANDOM ASSIGNMENT")
    lines.append("-" * 72)

    n_langs = len(all_lang_data) if all_lang_data is not None else 18
    # If the winning language is random (uniform over k languages), the
    # probability that two consecutive extensions agree = 1/k.
    # For a chain of length n, expected stability = 1/k.
    expected_random = 1.0 / n_langs
    lines.append(f"\n  Number of candidate languages: {n_langs}")
    lines.append(f"  Expected stability under random assignment: {expected_random:.4f}")
    if la_stabilities:
        la_mean_cmp = sum(la_stabilities) / len(la_stabilities)
        lines.append(f"  Observed LA mean stability: {la_mean_cmp:.4f}")
        lines.append(f"  Ratio (observed / random): {la_mean_cmp / expected_random:.2f}x")
        lines.append(f"  --> LA stability is {la_mean_cmp / expected_random:.1f}x higher than pure noise.")
        lines.append(f"  --> This means language wins are NOT random, but it could be driven")
        lines.append(f"      by systematic bias (e.g., Lydian's larger phoneme inventory)")
        lines.append(f"      rather than genuine cognate signal.")

    # -----------------------------------------------------------------------
    # Conclusions
    # -----------------------------------------------------------------------
    lines.append("\n" + "=" * 72)
    lines.append("CONCLUSIONS")
    lines.append("=" * 72)

    if la_stabilities and val_stabilities:
        la_mean = sum(la_stabilities) / len(la_stabilities)
        val_mean = sum(val_stabilities) / len(val_stabilities)

        la_high_frac = sum(1 for s in la_stabilities if s > 0.8) / len(la_stabilities)
        val_high_frac = sum(1 for s in val_stabilities if s > 0.8) / len(val_stabilities)

        lines.append("")
        if la_mean > val_mean * 0.9:
            lines.append("  [FINDING] LA stability is COMPARABLE to known-cognate stability.")
            lines.append("            This suggests rank stability CANNOT distinguish signal from noise")
            lines.append("            in this dataset, OR the LA data contains genuine cognate signal.")
        elif la_mean > val_mean * 0.7:
            lines.append("  [FINDING] LA stability is MODERATELY LOWER than known-cognate stability.")
            lines.append("            The progressive scan has some stability, but less than expected")
            lines.append("            for true cognates.")
        else:
            lines.append("  [FINDING] LA stability is MUCH LOWER than known-cognate stability.")
            lines.append("            This is consistent with the LA matches being noise.")

        if la_high_frac > 0.3:
            lines.append(f"\n  [FINDING] {la_high_frac*100:.1f}% of LA chains have high stability (>0.8).")
            lines.append("            If validated, these could be genuine cognate candidates.")
        else:
            lines.append(f"\n  [FINDING] Only {la_high_frac*100:.1f}% of LA chains have high stability (>0.8).")

        # Check if any language stands out
        if lang_stabilities:
            best_lang = max(lang_stabilities.keys(),
                           key=lambda l: sum(lang_stabilities[l]) / len(lang_stabilities[l])
                           if len(lang_stabilities[l]) >= 5 else 0)
            best_mean = sum(lang_stabilities[best_lang]) / len(lang_stabilities[best_lang])
            lines.append(f"\n  [FINDING] Highest-stability language: {best_lang} "
                         f"(mean={best_mean:.4f})")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("Loading data...")

    # 1. Load LA data per language
    print("  Loading LA per-language data...")
    la_data = load_la_per_language(LA_CLEAN_DIR)
    total_rows = sum(len(rows) for rows in la_data.values())
    print(f"  Loaded {len(la_data)} languages, {total_rows} total rows")

    # 2. Build progressive chains for LA
    print("\n  Building LA progressive chains...")
    la_chains = build_progressive_chains_la(la_data)
    print(f"  Found {len(la_chains)} chains (with >=2 members)")
    chain_lengths = [len(v) for v in la_chains.values()]
    if chain_lengths:
        print(f"  Chain length range: {min(chain_lengths)}-{max(chain_lengths)}, "
              f"mean={sum(chain_lengths)/len(chain_lengths):.1f}")

    # 3. Compute LA stability
    print("\n  Computing LA rank stability...")
    la_results = compute_la_stability(la_chains, la_data, min_chain_length=3)
    print(f"  Analyzed {len(la_results)} chains (min length 3)")

    # 4. Load validation data (Latin-vs-Oscan)
    print("\n  Loading Latin-vs-Oscan validation data...")
    val_rows = load_lat_vs_osc(FLEET_DIR)

    # 5. Build validation progressive chains
    print("  Building validation progressive chains...")
    val_chains = build_progressive_chains_validation(val_rows)
    print(f"  Found {len(val_chains)} chains")

    # 6. Compute validation stability
    print("  Computing validation rank stability...")
    val_results = compute_validation_stability(val_chains, val_rows, min_chain_length=3)
    print(f"  Analyzed {len(val_results)} chains")

    # 6b. Compute within-language word stability (apples-to-apples)
    print("  Computing within-language word stability...")
    la_word_stab = compute_la_word_stability(la_chains, la_data, min_chain_length=3)
    total_word_chains = sum(len(v) for v in la_word_stab.values())
    print(f"  Computed word stability for {len(la_word_stab)} languages, {total_word_chains} total chain-language pairs")

    # 7. Generate report
    print("\nGenerating report...\n")
    report = analyze_and_report(la_results, val_results, la_word_stab, la_data)
    print(report)

    # 8. Save report
    report_path = OUTPUT_DIR / "h3_rank_stability_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")

    # 9. Save raw results as JSON for downstream use
    json_path = OUTPUT_DIR / "h3_rank_stability_results.json"
    save_data = {
        "la_summary": {
            "n_chains": len(la_results),
            "mean_stability": sum(r["stability"] for r in la_results) / len(la_results) if la_results else 0,
            "per_language": {},
        },
        "validation_summary": {
            "n_chains": len(val_results),
            "mean_stability": sum(r["stability"] for r in val_results) / len(val_results) if val_results else 0,
        },
        "high_stability_chains": [
            {
                "chain_root": r["chain_root"],
                "stability": r["stability"],
                "dominant_language": r["dominant_language"],
                "chain_length": r["chain_length"],
                "winners": r["winners"],
            }
            for r in la_results if r["stability"] > 0.8
        ],
    }

    # Per-language summary
    lang_stabilities: dict[str, list[float]] = defaultdict(list)
    for r in la_results:
        lang_stabilities[r["dominant_language"]].append(r["stability"])
    for lang, stabs in lang_stabilities.items():
        save_data["la_summary"]["per_language"][lang] = {
            "count": len(stabs),
            "mean_stability": sum(stabs) / len(stabs),
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {json_path}")


if __name__ == "__main__":
    main()
