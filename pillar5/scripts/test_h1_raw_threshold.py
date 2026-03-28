#!/usr/bin/env python3
"""Hypothesis 1: Raw PP score thresholding calibrated from known cognate pairs.

Instead of min-max normalization (which makes the best language always score
1.0), use the RAW per-character PP scores with an empirically determined
threshold from the validation dataset.

Steps:
1. Load all pre-computed validation fleet results (known IE language pairs).
2. Compute per-char score statistics for each pair.
3. Organize by known linguistic distance to find threshold boundaries.
4. Apply threshold to Linear A fleet results for strata analysis.
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import statistics

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FLEET_DIR = Path(r"C:\Users\alvin\ancient-scripts-datasets\data\fleet_results_v2")
LA_CLEAN_DIR = Path(r"C:\Users\alvin\ancient-scripts-datasets\data\linear_a_cognates_clean")

# Linguistic distance categories for known IE pairs
# Key: (source, target), Value: category
DISTANCE_CATEGORIES = {
    # CLOSEST: Oscan <-> Umbrian (same Osco-Umbrian branch)
    ("osc", "xum"): "CLOSEST",
    ("xum", "osc"): "CLOSEST",
    # CLOSE: Latin <-> Oscan, Latin <-> Umbrian (same Italic family)
    ("lat", "osc"): "CLOSE",
    ("lat", "xum"): "CLOSE",
    ("xum", "lat"): "CLOSE",
    # MEDIUM: Latin <-> Greek, Oscan <-> Greek, Umbrian <-> Greek (same IE, different branch)
    ("lat", "grc"): "MEDIUM",
    ("grc", "lat"): "MEDIUM",
    ("grc", "osc"): "MEDIUM",
    ("osc", "grc"): "MEDIUM_INFERRED",  # Not available, keep for completeness
    ("grc", "xum"): "MEDIUM",
    ("xum", "grc"): "MEDIUM",
    # DISTANT: Latin <-> Sanskrit, Greek <-> Sanskrit, etc. (IE but very distant)
    ("lat", "san"): "DISTANT",
    ("grc", "san"): "DISTANT",
    ("san", "osc"): "DISTANT",
    ("xum", "san"): "DISTANT",
    # UNRELATED: Anglo-Saxon pairs (Germanic vs Italic/Hellenic)
    ("lat", "ang"): "UNRELATED",
    ("grc", "ang"): "UNRELATED",
    ("osc", "ang"): "UNRELATED",
    ("san", "ang"): "UNRELATED",
    ("xum", "ang"): "UNRELATED",
}

CATEGORY_ORDER = ["CLOSEST", "CLOSE", "MEDIUM", "DISTANT", "UNRELATED"]

LANGUAGE_NAMES = {
    "lat": "Latin",
    "grc": "Greek",
    "osc": "Oscan",
    "xum": "Umbrian",
    "san": "Sanskrit",
    "ang": "Anglo-Saxon",
    # Linear A candidates
    "hit": "Hittite",
    "phn": "Phoenician",
    "uga": "Ugaritic",
    "ave": "Avestan",
    "elx": "Elamite",
    "peo": "Old Persian",
    "xld": "Lydian",
    "xur": "Hurrian",
    "xcr": "Carian",
    "xlc": "Lycian",
    "xle": "Lemnian",
    "xpg": "Phrygian",
    "xrr": "Pre-Greek",
    "ccs-pro": "Proto-Kartvelian",
    "cms": "Cypro-Minoan",
    "dra-pro": "Proto-Dravidian",
    "ine-pro": "Proto-IE",
    "sem-pro": "Proto-Semitic",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PairStats:
    """Statistics for a single validation language pair."""
    source: str
    target: str
    category: str
    n_entries: int = 0
    scores: List[float] = field(default_factory=list)
    per_char_scores: List[float] = field(default_factory=list)

    @property
    def pair_label(self) -> str:
        src_name = LANGUAGE_NAMES.get(self.source, self.source)
        tgt_name = LANGUAGE_NAMES.get(self.target, self.target)
        return f"{src_name}->{tgt_name}"

    def compute_stats(self) -> Dict[str, float]:
        if not self.per_char_scores:
            return {}
        pcs = self.per_char_scores
        return {
            "mean": statistics.mean(pcs),
            "median": statistics.median(pcs),
            "stdev": statistics.stdev(pcs) if len(pcs) > 1 else 0.0,
            "best": max(pcs),  # least negative
            "worst": min(pcs),  # most negative
            "p25": sorted(pcs)[len(pcs) // 4],
            "p75": sorted(pcs)[3 * len(pcs) // 4],
            "n": len(pcs),
        }


@dataclass
class LALanguageStats:
    """Per-char score stats for one Linear A candidate language."""
    language: str
    per_char_scores: List[float] = field(default_factory=list)

    @property
    def lang_name(self) -> str:
        return LANGUAGE_NAMES.get(self.language, self.language)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_validation_pair(tsv_path: Path) -> List[Tuple[str, float, int]]:
    """Load a validation cognate_list.tsv.

    Returns list of (lost_string, score, len_lost) tuples.
    """
    entries = []
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            lost = row.get("lost", "").strip()
            score_str = row.get("score", "").strip()
            if not lost or not score_str:
                continue
            try:
                score = float(score_str)
            except ValueError:
                continue
            # Length of the "lost" string (source word being matched)
            # Use character count of the IPA string
            lost_len = len(lost)
            if lost_len == 0:
                continue
            entries.append((lost, score, lost_len))
    return entries


def find_all_validation_pairs() -> Dict[str, Path]:
    """Find all validation cognate_list.tsv files across fleet machines.

    Returns dict mapping pair_key (e.g. "lat_vs_osc") -> Path.
    """
    pairs = {}
    for machine_dir in sorted(FLEET_DIR.iterdir()):
        val_dir = machine_dir / "outputs" / "validation"
        if not val_dir.exists():
            continue
        for pair_dir in sorted(val_dir.iterdir()):
            tsv = pair_dir / "cognate_list.tsv"
            if tsv.exists():
                pairs[pair_dir.name] = tsv
    return pairs


def load_la_clean_results() -> Dict[str, LALanguageStats]:
    """Load Linear A clean cognate TSVs.

    Format: linear_a_signs | linear_a_ipa | matched_word | score | top3_matches | ipa_length
    """
    results = {}
    for tsv_path in sorted(LA_CLEAN_DIR.glob("linear_a_vs_*_clean.tsv")):
        lang_code = tsv_path.stem.replace("linear_a_vs_", "").replace("_clean", "")
        stats = LALanguageStats(language=lang_code)
        with open(tsv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                ipa = row.get("linear_a_ipa", "").strip()
                score_str = row.get("score", "").strip()
                length_str = row.get("ipa_length", "").strip()
                if not score_str:
                    continue
                try:
                    score = float(score_str)
                except ValueError:
                    continue
                try:
                    ipa_len = int(length_str) if length_str else len(ipa)
                except ValueError:
                    ipa_len = len(ipa)
                if ipa_len > 0:
                    stats.per_char_scores.append(score / ipa_len)
        results[lang_code] = stats
    return results


def load_la_fleet_results() -> Dict[str, LALanguageStats]:
    """Load Linear A results from fleet_results_v2 (raw cognate_list.tsv).

    These are the original fleet outputs, same format as validation:
    lost | top1_known | score | top10
    """
    results = {}
    for machine_dir in sorted(FLEET_DIR.iterdir()):
        la_dir = machine_dir / "outputs" / "linear_a"
        if not la_dir.exists():
            continue
        for pair_dir in sorted(la_dir.iterdir()):
            # pair_dir name like "linear_a_vs_hit"
            lang_code = pair_dir.name.replace("linear_a_vs_", "")
            tsv = pair_dir / "cognate_list.tsv"
            if not tsv.exists():
                continue
            if lang_code not in results:
                results[lang_code] = LALanguageStats(language=lang_code)
            stats = results[lang_code]
            with open(tsv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    lost = row.get("lost", "").strip()
                    score_str = row.get("score", "").strip()
                    if not lost or not score_str:
                        continue
                    try:
                        score = float(score_str)
                    except ValueError:
                        continue
                    lost_len = len(lost)
                    if lost_len > 0:
                        stats.per_char_scores.append(score / lost_len)
    return results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_validation_pairs() -> Tuple[Dict[str, PairStats], Dict[str, List[PairStats]]]:
    """Load and analyze all validation pairs, grouped by linguistic distance."""

    pair_paths = find_all_validation_pairs()
    print(f"\n{'='*80}")
    print(f"VALIDATION FLEET RESULTS: {len(pair_paths)} pairs found")
    print(f"{'='*80}\n")

    all_stats: Dict[str, PairStats] = {}

    for pair_key, tsv_path in sorted(pair_paths.items()):
        # Parse pair key: "lat_vs_osc" -> ("lat", "osc")
        parts = pair_key.split("_vs_")
        if len(parts) != 2:
            print(f"  WARNING: Cannot parse pair key '{pair_key}', skipping")
            continue
        src, tgt = parts

        category = DISTANCE_CATEGORIES.get((src, tgt), "UNKNOWN")

        entries = load_validation_pair(tsv_path)

        ps = PairStats(source=src, target=tgt, category=category, n_entries=len(entries))
        for lost, score, lost_len in entries:
            ps.scores.append(score)
            ps.per_char_scores.append(score / lost_len)

        all_stats[pair_key] = ps

    # Group by category
    by_category: Dict[str, List[PairStats]] = defaultdict(list)
    for ps in all_stats.values():
        by_category[ps.category].append(ps)

    return all_stats, by_category


def print_pair_stats(all_stats: Dict[str, PairStats], by_category: Dict[str, List[PairStats]]):
    """Print detailed statistics organized by linguistic distance."""

    print(f"\n{'='*80}")
    print(f"PER-CHAR SCORE STATISTICS BY LINGUISTIC DISTANCE")
    print(f"(score / len(lost_string)) — higher (less negative) = better match")
    print(f"{'='*80}")

    category_summaries = {}

    for cat in CATEGORY_ORDER:
        pairs = by_category.get(cat, [])
        if not pairs:
            continue

        print(f"\n{'-'*80}")
        print(f"  {cat} PAIRS")
        print(f"{'-'*80}")

        cat_all_scores = []

        for ps in sorted(pairs, key=lambda p: p.pair_label):
            stats = ps.compute_stats()
            if not stats:
                continue
            cat_all_scores.extend(ps.per_char_scores)

            print(f"\n  {ps.pair_label} ({ps.category})")
            print(f"    N entries:  {stats['n']:,}")
            print(f"    Mean:       {stats['mean']:.4f}")
            print(f"    Median:     {stats['median']:.4f}")
            print(f"    Stdev:      {stats['stdev']:.4f}")
            print(f"    Best:       {stats['best']:.4f}")
            print(f"    Worst:      {stats['worst']:.4f}")
            print(f"    P25:        {stats['p25']:.4f}")
            print(f"    P75:        {stats['p75']:.4f}")

        if cat_all_scores:
            cat_mean = statistics.mean(cat_all_scores)
            cat_median = statistics.median(cat_all_scores)
            cat_best = max(cat_all_scores)
            category_summaries[cat] = {
                "mean": cat_mean,
                "median": cat_median,
                "best": cat_best,
                "n": len(cat_all_scores),
            }
            print(f"\n  >>> CATEGORY AGGREGATE ({cat}):")
            print(f"      Mean:   {cat_mean:.4f}")
            print(f"      Median: {cat_median:.4f}")
            print(f"      Best:   {cat_best:.4f}")
            print(f"      N:      {len(cat_all_scores):,}")

    return category_summaries


def determine_threshold(
    all_stats: Dict[str, PairStats],
    by_category: Dict[str, List[PairStats]],
    category_summaries: Dict[str, Dict[str, float]],
) -> float:
    """Determine a per-char score threshold from the validation data.

    Strategy:
    - The threshold should ACCEPT most CLOSEST and CLOSE pairs
    - It should still ACCEPT but score lower for MEDIUM pairs
    - It should REJECT most UNRELATED noise

    We use the median of the CLOSE category as the threshold, since:
    - CLOSE pairs (Latin-Oscan) are known cognate pairs within a family
    - Their median represents what a "typical real cognate" looks like
    """

    print(f"\n{'='*80}")
    print(f"THRESHOLD DETERMINATION")
    print(f"{'='*80}")

    # Collect all per-char scores by category for percentile analysis
    cat_scores = {}
    for cat in CATEGORY_ORDER:
        scores = []
        for ps in by_category.get(cat, []):
            scores.extend(ps.per_char_scores)
        if scores:
            cat_scores[cat] = sorted(scores)

    # Print category separation
    print(f"\n  Category score distributions (per-char):")
    for cat in CATEGORY_ORDER:
        if cat in cat_scores:
            s = cat_scores[cat]
            p10 = s[len(s) // 10]
            p25 = s[len(s) // 4]
            p50 = s[len(s) // 2]
            p75 = s[3 * len(s) // 4]
            p90 = s[9 * len(s) // 10]
            print(f"    {cat:12s}: P10={p10:.3f}  P25={p25:.3f}  P50={p50:.3f}  P75={p75:.3f}  P90={p90:.3f}  N={len(s):,}")

    # Threshold candidates
    print(f"\n  Threshold candidates:")

    # Option A: Median of CLOSE pairs
    close_median = category_summaries.get("CLOSE", {}).get("median", -999)
    print(f"    A) Median of CLOSE (Latin-Oscan/Umbrian):  {close_median:.4f}")

    # Option B: P25 of CLOSEST pairs (conservative: 75% of best pairs exceed this)
    if "CLOSEST" in cat_scores:
        closest_p25 = cat_scores["CLOSEST"][len(cat_scores["CLOSEST"]) // 4]
        print(f"    B) P25 of CLOSEST (Oscan-Umbrian):         {closest_p25:.4f}")
    else:
        closest_p25 = close_median

    # Option C: Midpoint between MEDIUM median and UNRELATED median (separation boundary)
    medium_med = category_summaries.get("MEDIUM", {}).get("median", -999)
    unrelated_med = category_summaries.get("UNRELATED", {}).get("median", -999)
    if medium_med > -900 and unrelated_med > -900:
        midpoint = (medium_med + unrelated_med) / 2
        print(f"    C) Midpoint MEDIUM-UNRELATED medians:      {midpoint:.4f}")

    # Option D: Best of UNRELATED (anything better than the best noise is signal)
    if "UNRELATED" in cat_scores:
        unrelated_best = max(cat_scores["UNRELATED"])
        print(f"    D) Best of UNRELATED (noise ceiling):      {unrelated_best:.4f}")

    # Option E: P75 of UNRELATED (generous: only top 25% of noise exceeds)
    if "UNRELATED" in cat_scores:
        unrelated_p75 = cat_scores["UNRELATED"][3 * len(cat_scores["UNRELATED"]) // 4]
        print(f"    E) P75 of UNRELATED:                       {unrelated_p75:.4f}")

    # DECISION: Use the median of CLOSE pairs as the primary threshold.
    # This means: "a match is worth considering if it looks at least as good
    # as a typical Latin-Oscan cognate pair."
    # Also compute a lenient threshold (P75 of MEDIUM) for broader acceptance.

    # But first: check if categories actually separate!
    print(f"\n  Category separation check:")
    for i in range(len(CATEGORY_ORDER) - 1):
        c1, c2 = CATEGORY_ORDER[i], CATEGORY_ORDER[i + 1]
        m1 = category_summaries.get(c1, {}).get("median")
        m2 = category_summaries.get(c2, {}).get("median")
        if m1 is not None and m2 is not None:
            gap = m1 - m2
            print(f"    {c1:12s} -> {c2:12s}: median gap = {gap:+.4f}")

    # Primary threshold: median of CLOSE
    threshold = close_median
    print(f"\n  >>> PRIMARY THRESHOLD (median of CLOSE): {threshold:.4f}")
    print(f"      Interpretation: per-char score must be >= {threshold:.4f}")
    print(f"      to be considered a plausible cognate match.")

    # Also compute acceptance rates at this threshold for each category
    print(f"\n  Acceptance rates at threshold {threshold:.4f}:")
    for cat in CATEGORY_ORDER:
        if cat in cat_scores:
            n_above = sum(1 for s in cat_scores[cat] if s >= threshold)
            rate = n_above / len(cat_scores[cat])
            print(f"    {cat:12s}: {n_above:>6,} / {len(cat_scores[cat]):>6,} = {rate:6.1%}")

    # Try multiple thresholds to find optimal separation
    print(f"\n  Sweep across thresholds:")
    print(f"  {'Threshold':>10s}  ", end="")
    for cat in CATEGORY_ORDER:
        if cat in cat_scores:
            print(f"  {cat:>10s}", end="")
    print()

    # Determine sweep range from data
    all_pcs = []
    for cat in CATEGORY_ORDER:
        if cat in cat_scores:
            all_pcs.extend(cat_scores[cat])
    if all_pcs:
        sweep_min = statistics.mean(all_pcs) - 2 * statistics.stdev(all_pcs)
        sweep_max = max(all_pcs)
    else:
        sweep_min, sweep_max = -10, 0

    for t in [x * 0.25 for x in range(int(sweep_min * 4), int(sweep_max * 4) + 1)]:
        print(f"  {t:>10.2f}  ", end="")
        for cat in CATEGORY_ORDER:
            if cat in cat_scores:
                n_above = sum(1 for s in cat_scores[cat] if s >= t)
                rate = n_above / len(cat_scores[cat])
                print(f"  {rate:>9.1%}", end="")
        print()

    return threshold


def apply_to_linear_a(
    threshold: float,
    la_results: Dict[str, LALanguageStats],
    source_label: str = "clean",
) -> Dict[str, Dict[str, Any]]:
    """Apply the threshold to Linear A results.

    For each candidate language, compute what fraction of LA substrings
    exceed the threshold.
    """

    print(f"\n{'='*80}")
    print(f"LINEAR A STRATA ANALYSIS ({source_label} data)")
    print(f"Threshold: {threshold:.4f} per-char")
    print(f"{'='*80}")

    la_analysis = {}

    for lang_code in sorted(la_results.keys()):
        stats = la_results[lang_code]
        pcs = stats.per_char_scores
        if not pcs:
            continue

        n_above = sum(1 for s in pcs if s >= threshold)
        frac_above = n_above / len(pcs)

        la_analysis[lang_code] = {
            "language": stats.lang_name,
            "n_total": len(pcs),
            "n_above_threshold": n_above,
            "fraction_above": frac_above,
            "mean_per_char": statistics.mean(pcs),
            "median_per_char": statistics.median(pcs),
            "best_per_char": max(pcs),
            "p75_per_char": sorted(pcs)[3 * len(pcs) // 4],
        }

    # Sort by fraction above threshold, descending
    ranked = sorted(la_analysis.items(), key=lambda x: -x[1]["fraction_above"])

    print(f"\n  {'Rank':<5s} {'Language':<20s} {'Frac Above':>10s} {'N Above':>8s} "
          f"{'N Total':>8s} {'Mean/Char':>10s} {'Median':>10s} {'Best':>10s}")
    print(f"  {'-'*91}")

    for i, (lang, info) in enumerate(ranked, 1):
        print(f"  {i:<5d} {info['language']:<20s} {info['fraction_above']:>9.1%} "
              f"{info['n_above_threshold']:>8,} {info['n_total']:>8,} "
              f"{info['mean_per_char']:>10.4f} {info['median_per_char']:>10.4f} "
              f"{info['best_per_char']:>10.4f}")

    return la_analysis


def multi_threshold_analysis(
    la_results: Dict[str, LALanguageStats],
    thresholds: Dict[str, float],
):
    """Apply multiple thresholds and compare rankings."""

    print(f"\n{'='*80}")
    print(f"MULTI-THRESHOLD COMPARISON (fraction of LA substrings above each threshold)")
    print(f"{'='*80}")

    # Compute fraction above each threshold for each language
    lang_fracs: Dict[str, Dict[str, float]] = {}
    for lang_code, stats in la_results.items():
        pcs = stats.per_char_scores
        if not pcs:
            continue
        fracs = {}
        for tname, tval in thresholds.items():
            n_above = sum(1 for s in pcs if s >= tval)
            fracs[tname] = n_above / len(pcs)
        lang_fracs[lang_code] = fracs

    # Print header
    tnames = list(thresholds.keys())
    header = f"  {'Language':<20s}"
    for tn in tnames:
        header += f"  {tn:>12s}"
    print(f"\n{header}")
    print(f"  {'-'*(20 + 14*len(tnames))}")

    # Sort by the first threshold
    first_tn = tnames[0]
    for lang_code in sorted(lang_fracs.keys(), key=lambda l: -lang_fracs[l].get(first_tn, 0)):
        name = LANGUAGE_NAMES.get(lang_code, lang_code)
        row = f"  {name:<20s}"
        for tn in tnames:
            row += f"  {lang_fracs[lang_code].get(tn, 0):>11.1%}"
        print(row)


def length_stratified_analysis(
    all_stats: Dict[str, PairStats],
    by_category: Dict[str, List[PairStats]],
):
    """Analyze per-char scores stratified by string length.

    Short strings might have systematically different per-char scores.
    """
    print(f"\n{'='*80}")
    print(f"LENGTH-STRATIFIED ANALYSIS")
    print(f"(Do short vs long strings differ in per-char score?)")
    print(f"{'='*80}")

    # Re-load data with length info for a representative pair from each category
    representative_pairs = {}
    pair_paths = find_all_validation_pairs()

    for cat in CATEGORY_ORDER:
        pairs_in_cat = by_category.get(cat, [])
        if pairs_in_cat:
            ps = pairs_in_cat[0]
            key = f"{ps.source}_vs_{ps.target}"
            if key in pair_paths:
                representative_pairs[cat] = (ps, pair_paths[key])

    for cat in CATEGORY_ORDER:
        if cat not in representative_pairs:
            continue
        ps, tsv_path = representative_pairs[cat]
        entries = load_validation_pair(tsv_path)

        # Bin by length
        bins = {"1-3": [], "4-6": [], "7-10": [], "11+": []}
        for lost, score, lost_len in entries:
            pcs = score / lost_len
            if lost_len <= 3:
                bins["1-3"].append(pcs)
            elif lost_len <= 6:
                bins["4-6"].append(pcs)
            elif lost_len <= 10:
                bins["7-10"].append(pcs)
            else:
                bins["11+"].append(pcs)

        print(f"\n  {cat} ({ps.pair_label}):")
        for bin_name in ["1-3", "4-6", "7-10", "11+"]:
            scores = bins[bin_name]
            if scores:
                m = statistics.mean(scores)
                med = statistics.median(scores)
                print(f"    Len {bin_name:>4s}: N={len(scores):>5,}  Mean={m:.4f}  Median={med:.4f}")
            else:
                print(f"    Len {bin_name:>4s}: N=    0")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 80)
    print("HYPOTHESIS 1: Raw PP Score Thresholding")
    print("Calibrated from known IE cognate pairs in validation fleet")
    print("=" * 80)

    # Step 1-2: Load and analyze validation pairs
    all_stats, by_category = analyze_validation_pairs()

    # Step 3: Print organized stats
    category_summaries = print_pair_stats(all_stats, by_category)

    # Step 3b: Length-stratified analysis
    length_stratified_analysis(all_stats, by_category)

    # Step 4: Determine threshold
    threshold = determine_threshold(all_stats, by_category, category_summaries)

    # Step 5: Apply to Linear A
    # Try both sources: clean TSVs and raw fleet results
    print(f"\n\n{'#'*80}")
    print(f"# APPLYING THRESHOLD TO LINEAR A DATA")
    print(f"{'#'*80}")

    # Load clean LA results
    la_clean = load_la_clean_results()
    if la_clean:
        la_analysis_clean = apply_to_linear_a(threshold, la_clean, "clean TSV")

    # Load raw fleet LA results
    la_fleet = load_la_fleet_results()
    if la_fleet:
        la_analysis_fleet = apply_to_linear_a(threshold, la_fleet, "raw fleet")

    # Multi-threshold comparison with the fleet data (primary source)
    la_primary = la_fleet if la_fleet else la_clean
    if la_primary:
        # Define multiple thresholds from validation data
        thresholds_to_try = {}

        # Collect category medians for threshold options
        for cat in CATEGORY_ORDER:
            cat_all = []
            for ps in by_category.get(cat, []):
                cat_all.extend(ps.per_char_scores)
            if cat_all:
                thresholds_to_try[f"{cat}_med"] = statistics.median(cat_all)

        # Add the primary threshold
        thresholds_to_try["PRIMARY"] = threshold

        multi_threshold_analysis(la_primary, thresholds_to_try)

    # Final verdict
    print(f"\n\n{'='*80}")
    print(f"VERDICT: Is raw PP thresholding viable?")
    print(f"{'='*80}")

    # Check if categories separate cleanly
    cat_medians = {}
    for cat in CATEGORY_ORDER:
        if cat in category_summaries:
            cat_medians[cat] = category_summaries[cat]["median"]

    if len(cat_medians) >= 3:
        # Check monotonic decrease
        vals = [cat_medians[c] for c in CATEGORY_ORDER if c in cat_medians]
        is_monotonic = all(vals[i] >= vals[i+1] for i in range(len(vals)-1))

        # Check separation magnitude
        if len(vals) >= 2:
            total_range = vals[0] - vals[-1]
            avg_step = total_range / (len(vals) - 1)
        else:
            total_range = 0
            avg_step = 0

        print(f"\n  Category medians (should decrease with distance):")
        for cat in CATEGORY_ORDER:
            if cat in cat_medians:
                print(f"    {cat:12s}: {cat_medians[cat]:.4f}")

        print(f"\n  Monotonic decrease: {'YES' if is_monotonic else 'NO'}")
        print(f"  Total range:        {total_range:.4f}")
        print(f"  Average step:       {avg_step:.4f}")

        if is_monotonic and total_range > 0.3:
            print(f"\n  CONCLUSION: Raw per-char PP scores DO separate by linguistic distance.")
            print(f"  The threshold of {threshold:.4f} is empirically grounded.")
        elif is_monotonic:
            print(f"\n  CONCLUSION: Ordering is correct but separation is WEAK ({total_range:.4f}).")
            print(f"  Raw thresholding may work but with noisy boundaries.")
        else:
            print(f"\n  CONCLUSION: Categories do NOT separate monotonically.")
            print(f"  Raw thresholding is NOT viable as designed.")

    # Print LA ranking summary
    if la_primary:
        print(f"\n  Linear A ranking (by fraction above threshold {threshold:.4f}):")
        la_for_rank = la_fleet if la_fleet else la_clean
        la_an = apply_to_linear_a.__wrapped__(threshold, la_for_rank, "summary") if hasattr(apply_to_linear_a, '__wrapped__') else None
        # Just recompute inline
        ranked_langs = []
        for lc, st in la_primary.items():
            pcs = st.per_char_scores
            if pcs:
                n_above = sum(1 for s in pcs if s >= threshold)
                ranked_langs.append((lc, st.lang_name, n_above / len(pcs), n_above, len(pcs)))
        ranked_langs.sort(key=lambda x: -x[2])

        for i, (lc, name, frac, n_above, n_total) in enumerate(ranked_langs, 1):
            marker = ""
            if frac > 0.5:
                marker = " <<<  MAJORITY ABOVE THRESHOLD"
            elif frac > 0.3:
                marker = " <<   substantial"
            elif frac > 0.1:
                marker = " <    moderate"
            print(f"    {i:2d}. {name:<20s} {frac:6.1%} ({n_above:,}/{n_total:,}){marker}")


if __name__ == "__main__":
    main()
