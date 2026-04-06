"""
Jaccard Independent Validation on Cypriot Greek Syllabary
=========================================================

Validates the Jaccard consonant/vowel classification method on the
Cypriot Greek syllabary -- an independent CV syllabary used to write
Arcadocypriot Greek on Cyprus (~800-200 BCE).

WHY CYPRIOT:
  - True CV syllabary: each sign = one (consonant, vowel) pair
  - 55 signs, comparable to Linear B (56-74 signs)
  - Restrictive Greek phonotactics: consonant identity constrains
    which syllables can follow (same principle as Linear B)
  - Independently deciphered: known ground truth for evaluation
  - Same language family as Linear B but different script

WHAT THIS TESTS:
  The Jaccard method achieved ARI=0.342 (consonant) on Linear B but
  only ARI=0.047 on Japanese (permissive phonotactics). Cypriot Greek
  has restrictive phonotactics like Linear B but is an independent script.
  If the method achieves high ARI on Cypriot, it confirms:
    (a) The method works on CV syllabaries with restrictive phonotactics
    (b) The high ARI on Linear B is not an artifact of the specific script

DATA SOURCE:
  Idalion Tablet (ICS 217) + Palaeolexicon inscriptions
  Extracted by extract_cypriot_corpus.py
  See pillar1/tests/fixtures/cypriot_cv_corpus.json

Author: Ventris1 Project
Date: 2026-04-06
"""

from __future__ import annotations

import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import adjusted_rand_score

# Import the Jaccard pipeline functions
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jaccard_sign_classification import (
    compute_context_vectors,
    tfidf_transform,
    ppmi_transform,
    cosine_similarity_matrix,
    mutual_knn_sparsify,
    cluster_consonants,
    cluster_vowels,
    compute_ari,
    run_pipeline,
)


# ============================================================================
# CYPRIOT CORPUS LOADING
# ============================================================================

def load_cypriot_corpus(
    corpus_path: str,
    cv_map_path: str,
    min_syllables: int = 1,
) -> tuple[list[list[str]], dict[str, dict[str, str]]]:
    """Load Cypriot corpus and sign-to-CV mapping from JSON fixtures.

    Returns:
        (sign_groups, sign_info) where:
        - sign_groups: list of syllable sequences
        - sign_info: dict mapping sign ID -> {consonant, vowel}
    """
    with open(corpus_path, encoding="utf-8") as f:
        corpus = json.load(f)

    with open(cv_map_path, encoding="utf-8") as f:
        sign_info = json.load(f)

    sign_groups: list[list[str]] = []
    for entry in corpus["words"]:
        sylls = entry["syllables"]
        if len(sylls) >= min_syllables:
            sign_groups.append(sylls)

    return sign_groups, sign_info


def build_cypriot_ground_truth(
    signs: list[str],
    sign_info: dict[str, dict[str, str]],
) -> tuple[dict[str, int], dict[str, int]]:
    """Build consonant and vowel ground-truth integer labels.

    Returns (consonant_labels, vowel_labels) as dicts: sign -> int label.
    """
    cons_series: dict[str, list[str]] = defaultdict(list)
    vowel_classes: dict[str, list[str]] = defaultdict(list)

    for sign in signs:
        if sign not in sign_info:
            continue
        c = sign_info[sign]["consonant"]
        v = sign_info[sign]["vowel"]
        cons_series[c].append(sign)
        vowel_classes[v].append(sign)

    cons_label: dict[str, int] = {}
    for idx, name in enumerate(sorted(cons_series.keys())):
        for s in cons_series[name]:
            cons_label[s] = idx

    vowel_label: dict[str, int] = {}
    for idx, name in enumerate(sorted(vowel_classes.keys())):
        for s in vowel_classes[name]:
            vowel_label[s] = idx

    return cons_label, vowel_label


def count_recovered_cypriot_series(
    signs: list[str],
    labels: np.ndarray,
    sign_info: dict[str, dict[str, str]],
) -> tuple[int, list[str]]:
    """Count how many consonant series are recovered as distinct clusters.

    A series is "recovered" if >= 50% of its members share a cluster
    AND that cluster has >= 30% purity for that series.

    Tests all series that have >= 2 members in the analyzed set.
    """
    sign_to_label = {s: int(l) for s, l in zip(signs, labels)}

    # Build series membership
    series_members: dict[str, list[str]] = defaultdict(list)
    for sign in signs:
        if sign in sign_info:
            c = sign_info[sign]["consonant"]
            series_members[c].append(sign)

    recovered: list[str] = []
    for series_name, members in sorted(series_members.items()):
        if len(members) < 2:
            continue

        cluster_counts: Counter = Counter()
        for m in members:
            if m in sign_to_label:
                cluster_counts[sign_to_label[m]] += 1

        if not cluster_counts:
            continue

        best_cluster, best_count = cluster_counts.most_common(1)[0]
        labeled_total = sum(cluster_counts.values())
        majority_frac = best_count / labeled_total

        # Check purity
        all_in_cluster = [s for s in signs if sign_to_label.get(s) == best_cluster]
        n_from_series = sum(
            1 for s in all_in_cluster
            if s in sign_info and sign_info[s]["consonant"] == series_name
        )
        purity = n_from_series / len(all_in_cluster) if all_in_cluster else 0

        if majority_frac >= 0.5 and purity >= 0.3:
            recovered.append(series_name)

    return len(recovered), recovered


# ============================================================================
# VALIDATION PIPELINE
# ============================================================================

def validate_on_cypriot(
    sign_groups: list[list[str]],
    sign_info: dict[str, dict[str, str]],
    consonant_k: int = 13,    # 13 series (V, j, k, l, m, n, p, r, s, t, w, x, z)
    vowel_k: int = 5,         # 5 vowels (a, e, i, o, u)
    consonant_knn: int = 6,   # Smaller than LB (8) due to smaller corpus
    vowel_beta: float = 0.15,
    min_count: int = 3,        # Lower threshold due to smaller corpus (~1000 tokens)
) -> dict[str, Any]:
    """Run Jaccard pipeline on Cypriot data and evaluate."""
    pipeline = run_pipeline(
        sign_groups,
        min_count=min_count,
        consonant_knn=consonant_knn,
        consonant_k=consonant_k,
        vowel_beta=vowel_beta,
        vowel_k=vowel_k,
    )

    if "error" in pipeline:
        return {"pipeline": pipeline, "consonant_ari": 0.0, "vowel_ari": 0.0}

    signs = pipeline["signs"]
    cons_labels = pipeline["consonant"]["labels"]
    vowel_labels = pipeline["vowel"]["labels"]

    # Build ground truth
    cons_gt, vowel_gt = build_cypriot_ground_truth(signs, sign_info)

    cons_ari = compute_ari(signs, cons_labels, cons_gt)
    vowel_ari = compute_ari(signs, vowel_labels, vowel_gt)
    combined_ari = (cons_ari + vowel_ari) / 2

    n_recovered, recovered = count_recovered_cypriot_series(
        signs, cons_labels, sign_info,
    )

    return {
        "pipeline": pipeline,
        "consonant_ari": round(cons_ari, 4),
        "vowel_ari": round(vowel_ari, 4),
        "combined_ari": round(combined_ari, 4),
        "consonant_k": pipeline["consonant"]["k"],
        "vowel_k": pipeline["vowel"]["k"],
        "n_analyzed_signs": len(signs),
        "n_recovered_series": n_recovered,
        "recovered_series": recovered,
    }


def run_null_test(
    sign_groups: list[list[str]],
    sign_info: dict[str, dict[str, str]],
    seed: int = 42,
    **kwargs,
) -> dict[str, Any]:
    """Shuffle signs within each word, verify ARI drops to ~0."""
    rng = random.Random(seed)
    shuffled = []
    for group in sign_groups:
        g = list(group)
        rng.shuffle(g)
        shuffled.append(g)

    result = validate_on_cypriot(shuffled, sign_info, **kwargs)
    return {
        "shuffled_consonant_ari": result.get("consonant_ari", 0.0),
        "shuffled_vowel_ari": result.get("vowel_ari", 0.0),
        "gate_pass": abs(result.get("consonant_ari", 0.0)) < 0.10
                     and abs(result.get("vowel_ari", 0.0)) < 0.10,
    }


def run_k_sweep(
    sign_groups: list[list[str]],
    sign_info: dict[str, dict[str, str]],
    k_range: range | None = None,
) -> dict[str, Any]:
    """Sweep consonant_k to find optimal and report robustness."""
    if k_range is None:
        k_range = range(5, 20)

    results = []
    for k in k_range:
        r = validate_on_cypriot(sign_groups, sign_info, consonant_k=k)
        results.append({
            "k": k,
            "cons_ari": r["consonant_ari"],
            "vowel_ari": r["vowel_ari"],
            "n_recovered": r["n_recovered_series"],
        })
        print(f"    k={k:2d}  cons_ARI={r['consonant_ari']:.4f}  "
              f"vowel_ARI={r['vowel_ari']:.4f}  "
              f"recovered={r['n_recovered_series']}")

    best = max(results, key=lambda x: x["cons_ari"])
    return {
        "sweep_results": results,
        "best_k": best["k"],
        "best_cons_ari": best["cons_ari"],
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    sys.stdout.reconfigure(encoding="utf-8")

    base = Path("C:/Users/alvin/Ventris1")
    fixture_dir = base / "pillar1" / "tests" / "fixtures"
    corpus_path = fixture_dir / "cypriot_cv_corpus.json"
    cv_map_path = fixture_dir / "cypriot_sign_to_cv.json"
    results_dir = base / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 78)
    print("  JACCARD INDEPENDENT VALIDATION: CYPRIOT GREEK SYLLABARY")
    print("=" * 78)

    # ------------------------------------------------------------------
    # STEP 1: LOAD CORPUS
    # ------------------------------------------------------------------
    print("\n--- STEP 1: LOAD CYPRIOT CORPUS ---")
    t0 = time.time()

    sign_groups, sign_info = load_cypriot_corpus(
        str(corpus_path),
        str(cv_map_path),
        min_syllables=1,
    )

    total_tokens = sum(len(g) for g in sign_groups)
    n_unique = len(set(s for g in sign_groups for s in g))

    print(f"  Source: {corpus_path}")
    print(f"  Words loaded: {len(sign_groups)}")
    print(f"  Total syllable tokens: {total_tokens}")
    print(f"  Unique syllable types: {n_unique}")

    # Ground truth stats
    cons_series: dict[str, list[str]] = defaultdict(list)
    vowel_classes: dict[str, list[str]] = defaultdict(list)
    for sign in sign_info:
        cons_series[sign_info[sign]["consonant"]].append(sign)
        vowel_classes[sign_info[sign]["vowel"]].append(sign)

    print(f"  Ground truth consonant series: {len(cons_series)} "
          f"({sorted(cons_series.keys())})")
    print(f"  Ground truth vowel classes: {len(vowel_classes)} "
          f"({sorted(vowel_classes.keys())})")
    print(f"  Load time: {time.time() - t0:.2f}s")

    # ------------------------------------------------------------------
    # STEP 2: RUN JACCARD PIPELINE (default k)
    # ------------------------------------------------------------------
    print("\n--- STEP 2: RUN JACCARD PIPELINE (default hyperparameters) ---")
    t1 = time.time()

    val = validate_on_cypriot(
        sign_groups,
        sign_info,
        consonant_k=13,
        vowel_k=5,
        consonant_knn=6,
        vowel_beta=0.15,
        min_count=3,
    )

    pipeline_time = time.time() - t1

    print(f"\n  Pipeline completed in {pipeline_time:.2f}s")
    print(f"  Signs analyzed: {val['n_analyzed_signs']}")
    print(f"\n  === RESULTS ===")
    print(f"  Consonant ARI: {val['consonant_ari']:.4f}")
    print(f"  Vowel ARI:     {val['vowel_ari']:.4f}")
    print(f"  Combined ARI:  {val['combined_ari']:.4f}")
    print(f"  Recovered consonant series: {val['n_recovered_series']} "
          f"{val['recovered_series']}")

    # ------------------------------------------------------------------
    # STEP 3: K-SWEEP
    # ------------------------------------------------------------------
    print("\n--- STEP 3: CONSONANT K-SWEEP ---")
    sweep = run_k_sweep(sign_groups, sign_info, k_range=range(5, 18))
    print(f"\n  Best k: {sweep['best_k']} (cons_ARI={sweep['best_cons_ari']:.4f})")

    # ------------------------------------------------------------------
    # STEP 4: NULL TEST (shuffled corpus)
    # ------------------------------------------------------------------
    print("\n--- STEP 4: NULL TEST (shuffled corpus) ---")
    null_result = run_null_test(sign_groups, sign_info)
    print(f"  Shuffled consonant ARI: {null_result['shuffled_consonant_ari']:.4f}")
    print(f"  Shuffled vowel ARI:     {null_result['shuffled_vowel_ari']:.4f}")
    print(f"  Null gate: {'PASS' if null_result['gate_pass'] else 'FAIL'}")

    # ------------------------------------------------------------------
    # STEP 5: COMPARISON WITH LINEAR B AND JAPANESE
    # ------------------------------------------------------------------
    print("\n--- STEP 5: CROSS-SCRIPT COMPARISON ---")
    print(f"  {'Script':<20} {'Cons ARI':>10} {'Vowel ARI':>10} {'Phonotactics':>15}")
    print(f"  {'-'*55}")
    print(f"  {'Linear B':.<20} {'0.3420':>10} {'0.4220':>10} {'Restrictive':>15}")
    print(f"  {'Cypriot Greek':.<20} {val['consonant_ari']:>10.4f} {val['vowel_ari']:>10.4f} {'Restrictive':>15}")
    print(f"  {'Japanese':.<20} {'0.0470':>10} {'-0.0130':>10} {'Permissive':>15}")

    # ------------------------------------------------------------------
    # STEP 6: SAVE RESULTS
    # ------------------------------------------------------------------
    print("\n--- STEP 6: SAVE RESULTS ---")
    results = {
        "script": "Cypriot Greek Syllabary",
        "corpus_source": "Idalion Tablet (ICS 217) + Palaeolexicon",
        "n_sign_groups": len(sign_groups),
        "n_sign_tokens": total_tokens,
        "n_unique_signs": n_unique,
        "n_analyzed_signs": val["n_analyzed_signs"],
        "default_run": {
            "consonant_ari": val["consonant_ari"],
            "vowel_ari": val["vowel_ari"],
            "combined_ari": val["combined_ari"],
            "consonant_k": 13,
            "vowel_k": 5,
            "consonant_knn": 6,
            "vowel_beta": 0.15,
            "min_count": 3,
            "n_recovered_series": val["n_recovered_series"],
            "recovered_series": val["recovered_series"],
        },
        "k_sweep": {
            "best_k": sweep["best_k"],
            "best_cons_ari": sweep["best_cons_ari"],
            "all_results": sweep["sweep_results"],
        },
        "null_test": null_result,
        "comparison": {
            "linear_b": {"consonant_ari": 0.342, "vowel_ari": 0.422, "phonotactics": "restrictive"},
            "cypriot": {"consonant_ari": val["consonant_ari"], "vowel_ari": val["vowel_ari"], "phonotactics": "restrictive"},
            "japanese": {"consonant_ari": 0.047, "vowel_ari": -0.013, "phonotactics": "permissive"},
        },
    }

    results_path = results_dir / "cypriot_jaccard_validation.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Results saved: {results_path}")

    print("\n" + "=" * 78)
    print("  VALIDATION COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()
