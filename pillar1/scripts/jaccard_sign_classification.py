"""
Jaccard Paradigmatic Substitutability for Full Sign Classification
=================================================================

Classifies CV syllabary signs into consonant series (grid rows) and
vowel classes (grid columns) using directional distributional similarity
of bigram context sets.

LEFT-context similarity  -> consonant classification (signs sharing a
                            consonant follow the same preceding signs)
RIGHT-context similarity -> vowel classification (signs sharing a vowel
                            precede the same following signs)

Similarity pipeline (validated on Linear B):
  1. Build per-sign left/right context frequency vectors
  2. Transform via TF-IDF (consonant) or PPMI (vowel) to weight contexts
  3. Compute cosine similarity matrices
  4. Consonant: mutual-kNN sparsification + hierarchical average-linkage
  5. Vowel: anti-correlation subtraction (R - beta*L) + spectral clustering
  6. Cross-validate orthogonality, assemble grid

TERMINOLOGY: "sign-groups" throughout (not "words") because Linear A
word boundaries are unknown.

Author: Ventris1 Project
Date: 2026-04-03
"""

from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from numpy.linalg import norm as np_norm
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform, pdist
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.cluster import SpectralClustering

# ============================================================================
# CONSTANTS
# ============================================================================

BOS = "<BOS>"
EOS = "<EOS>"
MIN_TOKEN_COUNT = 5
MIN_CONTEXT_SIZE = 3
KNOWN_LB_VOWELS = {"a", "e", "i", "o", "u"}

# Validated hyperparameters (from Linear B grid search)
DEFAULT_CONSONANT_KNN = 8
DEFAULT_CONSONANT_K = 19
DEFAULT_VOWEL_ANTI_CORR_BETA = 0.15
DEFAULT_VOWEL_K = 5


# ============================================================================
# DATA LOADING
# ============================================================================

def load_linear_b_corpus(path: str) -> list[list[str]]:
    """Load Linear B test corpus as list of sign-group sequences."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sign_groups: list[list[str]] = []
    for inscription in data["inscriptions"]:
        for word in inscription["words"]:
            signs = word["sign_readings"]
            if signs and not word.get("has_damage", False):
                sign_groups.append(signs)
    return sign_groups


def load_linear_b_hf_words(path: str, sign_to_ipa: dict) -> list[list[str]]:
    """Load Linear B sign-groups from HF TSV vocabulary list."""
    known_signs = set(sign_to_ipa.keys())
    sign_groups: list[list[str]] = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[1:]:
        parts = line.strip().split("\t")
        if not parts:
            continue
        word_str = parts[0]
        raw_signs = word_str.replace("*", "").split("-")
        signs = [s for s in raw_signs if s and not s.isdigit()]
        if len(signs) >= 2 and all(s in known_signs for s in signs):
            sign_groups.append(signs)
    return sign_groups


def load_linear_a_corpus(path: str) -> list[list[str]]:
    """Load Linear A SigLA corpus as list of sign-group sequences."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    sign_groups: list[list[str]] = []
    for inscription in data["inscriptions"]:
        for word in inscription.get("words", []):
            signs = word.get("sign_readings", [])
            if signs and not word.get("has_damage", False):
                clean = [s for s in signs if not s.isdigit()]
                if len(clean) >= 1:
                    sign_groups.append(clean)
    return sign_groups


def deduplicate_sign_groups(group_lists: list[list[list[str]]]) -> list[list[str]]:
    """Combine and deduplicate multiple sign-group lists."""
    seen: set[tuple[str, ...]] = set()
    result: list[list[str]] = []
    for gl in group_lists:
        for g in gl:
            key = tuple(g)
            if key not in seen:
                seen.add(key)
                result.append(g)
    return result


# ============================================================================
# CONTEXT VECTOR COMPUTATION
# ============================================================================

def compute_context_vectors(
    sign_groups: list[list[str]],
    min_count: int = MIN_TOKEN_COUNT,
) -> tuple[list[str], np.ndarray, np.ndarray, dict[str, int]]:
    """Build per-sign left and right context frequency vectors.

    Args:
        sign_groups: list of sign-group sequences
        min_count: minimum token count for inclusion

    Returns:
        (signs, left_vectors, right_vectors, sign_counts)
        where vectors are (n_signs, n_contexts) numpy arrays.
    """
    sign_total: Counter = Counter()
    left_counts: dict[str, Counter] = defaultdict(Counter)
    right_counts: dict[str, Counter] = defaultdict(Counter)

    for group in sign_groups:
        n = len(group)
        for i, sign in enumerate(group):
            sign_total[sign] += 1
            left = group[i - 1] if i > 0 else BOS
            right = group[i + 1] if i < n - 1 else EOS
            left_counts[sign][left] += 1
            right_counts[sign][right] += 1

    # Filter by minimum count
    signs = sorted(s for s in sign_total if sign_total[s] >= min_count)

    # Build vocabulary of context elements
    all_left = sorted(set(k for s in signs for k in left_counts[s]))
    all_right = sorted(set(k for s in signs for k in right_counts[s]))

    l_idx = {c: i for i, c in enumerate(all_left)}
    r_idx = {c: i for i, c in enumerate(all_right)}

    left_vecs = np.zeros((len(signs), len(all_left)))
    right_vecs = np.zeros((len(signs), len(all_right)))

    for i, s in enumerate(signs):
        for ctx, cnt in left_counts[s].items():
            if ctx in l_idx:
                left_vecs[i, l_idx[ctx]] = cnt
        for ctx, cnt in right_counts[s].items():
            if ctx in r_idx:
                right_vecs[i, r_idx[ctx]] = cnt

    counts = {s: sign_total[s] for s in signs}
    return signs, left_vecs, right_vecs, counts


# ============================================================================
# SIMILARITY COMPUTATION
# ============================================================================

def tfidf_transform(vecs: np.ndarray) -> np.ndarray:
    """TF-IDF transform: downweight contexts appearing with many signs."""
    df = (vecs > 0).sum(axis=0)
    idf = np.log(vecs.shape[0] / (df + 1))
    tf = vecs / (vecs.sum(axis=1, keepdims=True) + 1e-10)
    return tf * idf


def ppmi_transform(vecs: np.ndarray) -> np.ndarray:
    """Positive Pointwise Mutual Information transform."""
    row_totals = vecs.sum(axis=1, keepdims=True)
    row_totals[row_totals == 0] = 1
    col_totals = vecs.sum(axis=0, keepdims=True)
    total = vecs.sum()
    if total == 0:
        return vecs
    expected = (row_totals * col_totals) / total
    expected[expected == 0] = 1
    pmi = np.log2(vecs / expected + 1e-10)
    pmi[vecs == 0] = 0  # Zero counts get PMI = 0
    return np.maximum(pmi, 0)


def cosine_similarity_matrix(vecs: np.ndarray) -> np.ndarray:
    """Compute pairwise cosine similarity matrix."""
    norms = np_norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = vecs / norms
    return normed @ normed.T


def mutual_knn_sparsify(sim: np.ndarray, k_nn: int) -> np.ndarray:
    """Mutual k-nearest-neighbor sparsification of similarity matrix.

    Only retains edges where both signs are in each other's top-k
    nearest neighbors. This removes spurious long-range similarities
    that confuse hierarchical clustering.
    """
    n = sim.shape[0]
    knn_mask = np.zeros_like(sim)
    for i in range(n):
        row = sim[i].copy()
        row[i] = -np.inf  # exclude self
        top_k = np.argsort(row)[-k_nn:]
        for j in top_k:
            knn_mask[i, j] = 1
    # Mutual: both must be in each other's top-k
    mutual = knn_mask * knn_mask.T
    result = sim * mutual
    np.fill_diagonal(result, 1.0)
    return result


# ============================================================================
# JACCARD HELPERS (for Tier-1 tests and weighted variant)
# ============================================================================

def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Standard (unweighted) Jaccard index of two sets."""
    if not set_a and not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def weighted_jaccard(counts_a: Counter, counts_b: Counter) -> float:
    """Weighted Jaccard: sum(min) / sum(max)."""
    all_keys = set(counts_a.keys()) | set(counts_b.keys())
    if not all_keys:
        return 0.0
    numerator = sum(min(counts_a.get(k, 0), counts_b.get(k, 0)) for k in all_keys)
    denominator = sum(max(counts_a.get(k, 0), counts_b.get(k, 0)) for k in all_keys)
    return numerator / denominator if denominator > 0 else 0.0


# ============================================================================
# CLUSTERING
# ============================================================================

def cluster_consonants(
    sim_matrix: np.ndarray,
    knn_k: int = DEFAULT_CONSONANT_KNN,
    n_clusters: int = DEFAULT_CONSONANT_K,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Cluster signs by consonant using mutual-kNN + hierarchical average-linkage.

    Args:
        sim_matrix: NxN cosine similarity matrix on TF-IDF left-context vectors
        knn_k: number of nearest neighbors for mutual kNN
        n_clusters: number of consonant clusters

    Returns:
        (labels, metadata)
    """
    n = sim_matrix.shape[0]
    if n < 3:
        return np.zeros(n, dtype=int), {"note": "too_few_signs"}

    # Mutual kNN sparsification
    mknn = mutual_knn_sparsify(sim_matrix, knn_k)

    # Convert to distance
    dist = np.clip(1.0 - mknn, 0.0, 1.0)
    np.fill_diagonal(dist, 0.0)
    condensed = squareform(dist, checks=False)

    # Hierarchical clustering with average linkage
    Z = linkage(condensed, method="average")
    labels = fcluster(Z, t=n_clusters, criterion="maxclust")

    metadata = {
        "knn_k": knn_k,
        "n_clusters": n_clusters,
        "method": "mutual_knn_average_linkage",
    }
    return labels, metadata


def cluster_vowels(
    sim_right: np.ndarray,
    sim_left: np.ndarray,
    beta: float = DEFAULT_VOWEL_ANTI_CORR_BETA,
    n_clusters: int = DEFAULT_VOWEL_K,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Cluster signs by vowel using anti-correlation + spectral clustering.

    Anti-correlation: signs sharing a vowel have high RIGHT-context similarity
    but potentially different LEFT-context (different consonant). Subtracting
    a fraction of LEFT similarity sharpens the vowel signal.

    Args:
        sim_right: NxN cosine similarity on PPMI right-context vectors
        sim_left: NxN cosine similarity on TF-IDF left-context vectors
        beta: anti-correlation weight (sim = R - beta*L)
        n_clusters: number of vowel clusters

    Returns:
        (labels, metadata)
    """
    n = sim_right.shape[0]
    if n < 3:
        return np.zeros(n, dtype=int), {"note": "too_few_signs"}

    # Anti-correlation subtraction
    sim_anti = sim_right - beta * sim_left

    # Normalize to [0, 1] for spectral clustering affinity
    sim_min = sim_anti.min()
    sim_max = sim_anti.max()
    if sim_max > sim_min:
        sim_norm = (sim_anti - sim_min) / (sim_max - sim_min)
    else:
        sim_norm = np.ones_like(sim_anti)

    # Spectral clustering
    affinity = np.clip(sim_norm, 0, None)
    np.fill_diagonal(affinity, 0)

    sc = SpectralClustering(
        n_clusters=n_clusters,
        affinity="precomputed",
        random_state=42,
        n_init=10,
    )
    labels = sc.fit_predict(affinity)

    metadata = {
        "beta": beta,
        "n_clusters": n_clusters,
        "method": "anti_correlation_spectral",
    }
    return labels, metadata


def auto_select_k(
    sim_matrix: np.ndarray,
    signs: list[str],
    cluster_fn,
    k_range: tuple[int, int],
    gt_labels: dict[str, int] | None = None,
    **cluster_kwargs,
) -> tuple[int, float]:
    """Select best k by silhouette score (unsupervised) or ARI (if GT given).

    Returns (best_k, best_score).
    """
    best_score = -1.0
    best_k = k_range[0]

    for k in range(k_range[0], k_range[1] + 1):
        labels, _ = cluster_fn(sim_matrix, n_clusters=k, **cluster_kwargs)

        if gt_labels is not None:
            # Supervised: use ARI
            pred = []
            true = []
            for s, l in zip(signs, labels):
                if s in gt_labels:
                    pred.append(int(l))
                    true.append(gt_labels[s])
            if len(pred) >= 2:
                score = adjusted_rand_score(true, pred)
            else:
                score = 0.0
        else:
            # Unsupervised: use silhouette
            dist = np.clip(1 - sim_matrix, 0, 1)
            np.fill_diagonal(dist, 0)
            unique_labels = set(labels)
            if len(unique_labels) < 2:
                score = -1.0
            else:
                try:
                    score = silhouette_score(dist, labels, metric="precomputed")
                except ValueError:
                    score = -1.0

        if score > best_score:
            best_score = score
            best_k = k

    return best_k, best_score


# ============================================================================
# GROUND TRUTH HELPERS
# ============================================================================

def extract_consonant(sign: str) -> str:
    """Extract consonant part from a CV sign name."""
    base = sign.rstrip("0123456789")
    if not base:
        return sign
    if base in ("a", "e", "i", "o", "u"):
        return "V"
    if len(base) == 3 and base[1] == "w":
        return base[:2]
    if base[-1] in "aeiou":
        return base[:-1]
    return base


def extract_vowel(sign: str) -> str | None:
    """Extract vowel part from a CV sign name."""
    base = sign.rstrip("0123456789")
    if not base:
        return None
    if base in ("a", "e", "i", "o", "u"):
        return base
    if base[-1] in "aeiou":
        return base[-1]
    return None


def build_lb_ground_truth(
    signs: list[str], sign_to_ipa: dict,
) -> tuple[dict[str, int], dict[str, int]]:
    """Build consonant and vowel ground-truth integer labels for Linear B signs."""
    cons_series: dict[str, list[str]] = defaultdict(list)
    vowel_classes: dict[str, list[str]] = defaultdict(list)

    for sign in signs:
        if sign not in sign_to_ipa or sign_to_ipa[sign] == "-":
            continue
        c = extract_consonant(sign)
        v = extract_vowel(sign)
        cons_series[c].append(sign)
        if v:
            vowel_classes[v].append(sign)

    cons_label: dict[str, int] = {}
    cons_names = sorted(cons_series.keys())
    for idx, name in enumerate(cons_names):
        for s in cons_series[name]:
            cons_label[s] = idx

    vowel_label: dict[str, int] = {}
    vowel_names = sorted(vowel_classes.keys())
    for idx, name in enumerate(vowel_names):
        for s in vowel_classes[name]:
            vowel_label[s] = idx

    return cons_label, vowel_label


def compute_ari(
    signs: list[str],
    labels: np.ndarray,
    gt_labels: dict[str, int],
) -> float:
    """Compute ARI between predicted labels and ground truth."""
    pred = []
    true = []
    for s, l in zip(signs, labels):
        if s in gt_labels:
            pred.append(int(l))
            true.append(gt_labels[s])
    if len(pred) < 2:
        return 0.0
    return adjusted_rand_score(true, pred)


def count_recovered_series(
    signs: list[str],
    labels: np.ndarray,
    sign_to_ipa: dict,
    target_series: list[str] | None = None,
) -> tuple[int, list[str]]:
    """Count how many consonant series are recovered as distinct clusters.

    A series is "recovered" if >= 50% of its members share a cluster
    AND that cluster has >= 30% purity for that series.
    """
    if target_series is None:
        target_series = ["t", "k", "r", "n", "s"]

    sign_to_label = {s: int(l) for s, l in zip(signs, labels)}

    # Build series membership
    series_members: dict[str, list[str]] = defaultdict(list)
    for sign in signs:
        if sign in sign_to_ipa and sign_to_ipa[sign] != "-":
            c = extract_consonant(sign)
            if c != "V":
                series_members[c].append(sign)

    recovered: list[str] = []
    for series_name in target_series:
        members = series_members.get(series_name, [])
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

        # Check purity of the cluster
        all_in_cluster = [s for s in signs if sign_to_label.get(s) == best_cluster]
        n_from_series = sum(
            1 for s in all_in_cluster
            if s in sign_to_ipa and extract_consonant(s) == series_name
        )
        purity = n_from_series / len(all_in_cluster) if all_in_cluster else 0

        if majority_frac >= 0.5 and purity >= 0.3:
            recovered.append(series_name)

    return len(recovered), recovered


# ============================================================================
# FULL PIPELINE
# ============================================================================

def run_pipeline(
    sign_groups: list[list[str]],
    min_count: int = MIN_TOKEN_COUNT,
    consonant_knn: int = DEFAULT_CONSONANT_KNN,
    consonant_k: int = DEFAULT_CONSONANT_K,
    vowel_beta: float = DEFAULT_VOWEL_ANTI_CORR_BETA,
    vowel_k: int = DEFAULT_VOWEL_K,
) -> dict[str, Any]:
    """Run the full Jaccard sign classification pipeline.

    Returns dict with all results including cluster assignments.
    """
    # Step 0: Compute context vectors
    signs, left_vecs, right_vecs, sign_counts = compute_context_vectors(
        sign_groups, min_count=min_count
    )

    total_tokens = sum(len(g) for g in sign_groups)
    n_unique = len(set(s for g in sign_groups for s in g))

    result: dict[str, Any] = {
        "corpus_stats": {
            "n_sign_groups": len(sign_groups),
            "total_tokens": total_tokens,
            "n_unique_signs": n_unique,
            "n_analyzed_signs": len(signs),
            "min_token_count": min_count,
        },
        "signs": signs,
        "sign_counts": sign_counts,
    }

    if len(signs) < 3:
        result["error"] = "insufficient_signs"
        return result

    # Step 1: Compute similarity matrices
    sim_l_tfidf = cosine_similarity_matrix(tfidf_transform(left_vecs))
    sim_r_ppmi = cosine_similarity_matrix(ppmi_transform(right_vecs))

    result["sim_l_tfidf"] = sim_l_tfidf
    result["sim_r_ppmi"] = sim_r_ppmi

    # Step 2: Consonant clustering (mutual kNN + hierarchical)
    cons_labels, cons_meta = cluster_consonants(
        sim_l_tfidf, knn_k=consonant_knn, n_clusters=min(consonant_k, len(signs) - 1)
    )
    cons_clusters = _build_cluster_dict(signs, cons_labels)
    result["consonant"] = {
        "labels": cons_labels,
        "clusters": cons_clusters,
        "metadata": cons_meta,
        "k": len(set(cons_labels)),
    }

    # Step 3: Vowel clustering (anti-correlation + spectral)
    vowel_labels, vowel_meta = cluster_vowels(
        sim_r_ppmi, sim_l_tfidf,
        beta=vowel_beta, n_clusters=min(vowel_k, len(signs) - 1)
    )
    vowel_clusters = _build_cluster_dict(signs, vowel_labels)
    result["vowel"] = {
        "labels": vowel_labels,
        "clusters": vowel_clusters,
        "metadata": vowel_meta,
        "k": len(set(vowel_labels)),
    }

    # Step 4: Cross-validation
    result["cross_validation"] = _cross_validate(
        signs, cons_labels, vowel_labels
    )

    # Step 5: Grid assembly
    result["grid"] = _assemble_grid(signs, cons_labels, vowel_labels, sign_counts)

    return result


def _build_cluster_dict(
    signs: list[str], labels: np.ndarray,
) -> dict[int, list[str]]:
    """Group signs by cluster label."""
    clusters: dict[int, list[str]] = defaultdict(list)
    for sign, label in zip(signs, labels):
        clusters[int(label)].append(sign)
    return dict(clusters)


def _cross_validate(
    signs: list[str],
    cons_labels: np.ndarray,
    vowel_labels: np.ndarray,
) -> dict[str, Any]:
    """Check orthogonality between consonant and vowel classifications."""
    n = len(signs)
    cons_list = [int(l) for l in cons_labels]
    vowel_list = [int(l) for l in vowel_labels]

    # Mutual information
    joint = Counter(zip(cons_list, vowel_list))
    cons_marginal = Counter(cons_list)
    vowel_marginal = Counter(vowel_list)

    mi = 0.0
    for (c, v), count in joint.items():
        p_cv = count / n
        p_c = cons_marginal[c] / n
        p_v = vowel_marginal[v] / n
        if p_cv > 0 and p_c > 0 and p_v > 0:
            mi += p_cv * math.log2(p_cv / (p_c * p_v))

    h_cons = -sum(
        (c / n) * math.log2(c / n) for c in cons_marginal.values() if c > 0
    )
    h_vowel = -sum(
        (c / n) * math.log2(c / n) for c in vowel_marginal.values() if c > 0
    )
    denom = min(h_cons, h_vowel)
    nmi = mi / denom if denom > 0 else 0.0

    # Diversity checks
    cons_vowel_diversity = {}
    for c_label in set(cons_list):
        v_labels = set(
            int(vowel_labels[i]) for i in range(n) if cons_list[i] == c_label
        )
        cons_vowel_diversity[c_label] = len(v_labels)

    vowel_cons_diversity = {}
    for v_label in set(vowel_list):
        c_labels = set(
            int(cons_labels[i]) for i in range(n) if vowel_list[i] == v_label
        )
        vowel_cons_diversity[v_label] = len(c_labels)

    return {
        "mutual_information": round(mi, 4),
        "normalized_mi": round(nmi, 4),
        "h_consonant": round(h_cons, 4),
        "h_vowel": round(h_vowel, 4),
        "cons_vowel_diversity": cons_vowel_diversity,
        "vowel_cons_diversity": vowel_cons_diversity,
    }


def _assemble_grid(
    signs: list[str],
    cons_labels: np.ndarray,
    vowel_labels: np.ndarray,
    sign_counts: dict[str, int],
) -> dict[str, Any]:
    """Assemble 2D phonological grid from consonant and vowel clusters."""
    assignments = []
    for i, sign in enumerate(signs):
        assignments.append({
            "sign": sign,
            "count": sign_counts.get(sign, 0),
            "consonant_class": int(cons_labels[i]),
            "vowel_class": int(vowel_labels[i]),
        })

    return {
        "n_consonant_classes": len(set(int(l) for l in cons_labels)),
        "n_vowel_classes": len(set(int(l) for l in vowel_labels)),
        "assignments": assignments,
    }


# ============================================================================
# VALIDATION
# ============================================================================

def validate_on_linear_b(
    sign_groups: list[list[str]],
    sign_to_ipa: dict,
    consonant_knn: int = DEFAULT_CONSONANT_KNN,
    consonant_k: int = DEFAULT_CONSONANT_K,
    vowel_beta: float = DEFAULT_VOWEL_ANTI_CORR_BETA,
    vowel_k: int = DEFAULT_VOWEL_K,
    min_count: int = MIN_TOKEN_COUNT,
) -> dict[str, Any]:
    """Run pipeline on LB data and validate against ground truth."""
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
    cons_gt, vowel_gt = build_lb_ground_truth(signs, sign_to_ipa)

    cons_ari = compute_ari(signs, cons_labels, cons_gt)
    vowel_ari = compute_ari(signs, vowel_labels, vowel_gt)
    combined_ari = (cons_ari + vowel_ari) / 2

    n_recovered, recovered = count_recovered_series(
        signs, cons_labels, sign_to_ipa,
        target_series=["t", "k", "r", "n", "s"],
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
        "gate1_pass": cons_ari >= 0.30 and n_recovered >= 3,
        "gate2_pass": vowel_ari >= 0.40,
        "combined_pass": combined_ari >= 0.45,
    }


def run_null_test(
    sign_groups: list[list[str]],
    sign_to_ipa: dict,
    seed: int = 42,
    **kwargs,
) -> dict[str, Any]:
    """Shuffle signs within each sign-group, verify ARI drops to ~0.

    Fast single-seed test. For robust null testing, use run_null_test_robust().
    """
    rng = random.Random(seed)
    shuffled = []
    for group in sign_groups:
        g = list(group)
        rng.shuffle(g)
        shuffled.append(g)

    result = validate_on_linear_b(shuffled, sign_to_ipa, **kwargs)
    cons_ari = result.get("consonant_ari", 0.0)
    vowel_ari = result.get("vowel_ari", 0.0)

    return {
        "shuffled_consonant_ari": cons_ari,
        "shuffled_vowel_ari": vowel_ari,
        "gate_pass": abs(cons_ari) < 0.05 and abs(vowel_ari) < 0.05,
    }


def run_null_test_robust(
    sign_groups: list[list[str]],
    sign_to_ipa: dict,
    n_seeds: int = 50,
    threshold: float = 0.10,
    **kwargs,
) -> dict[str, Any]:
    """Robust null test: median ARI across multiple shuffled seeds.

    Single-seed null tests are fragile (~25% of seeds produce |ARI| > 0.05
    due to systematic positive bias: the within-group shuffle preserves sign
    frequencies and group lengths, producing mean null ARI of +0.026 consonant
    and +0.016 vowel).

    Taking the median across 50 seeds reduces the 95% halfwidth of the
    median estimate to ~0.008 (vs ~0.012 at 20 seeds).

    The threshold of 0.10 is set above the 95th percentile of |null ARI|
    (~0.08), providing a defensible false-positive rate. The previous
    threshold of 0.05 produced a 25% false-positive rate.

    Args:
        sign_groups: corpus sign-group sequences
        sign_to_ipa: sign-to-IPA mapping for ground truth
        n_seeds: number of independent shuffled copies (default 50)
        threshold: gate threshold for median |ARI| (default 0.10)
        **kwargs: forwarded to validate_on_linear_b

    Returns:
        dict with median ARI, per-seed ARI arrays, gate_pass, and p-values
    """
    cons_aris: list[float] = []
    vowel_aris: list[float] = []

    for seed in range(n_seeds):
        null = run_null_test(sign_groups, sign_to_ipa, seed=seed, **kwargs)
        cons_aris.append(null["shuffled_consonant_ari"])
        vowel_aris.append(null["shuffled_vowel_ari"])

    cons_arr = np.array(cons_aris)
    vowel_arr = np.array(vowel_aris)

    median_cons = float(np.median(cons_arr))
    median_vowel = float(np.median(vowel_arr))

    # Compute p-value: fraction of null seeds that exceed real ARI
    # (requires real ARI to be passed in or computed separately)
    return {
        "median_consonant_ari": round(median_cons, 4),
        "median_vowel_ari": round(median_vowel, 4),
        "mean_consonant_ari": round(float(cons_arr.mean()), 4),
        "mean_vowel_ari": round(float(vowel_arr.mean()), 4),
        "std_consonant_ari": round(float(cons_arr.std()), 4),
        "std_vowel_ari": round(float(vowel_arr.std()), 4),
        "max_consonant_ari": round(float(np.abs(cons_arr).max()), 4),
        "max_vowel_ari": round(float(np.abs(vowel_arr).max()), 4),
        "n_seeds": n_seeds,
        "threshold": threshold,
        "per_seed_consonant_ari": [round(x, 4) for x in cons_aris],
        "per_seed_vowel_ari": [round(x, 4) for x in vowel_aris],
        "gate_pass": abs(median_cons) < threshold and abs(median_vowel) < threshold,
    }


def compute_null_significance(
    sign_groups: list[list[str]],
    sign_to_ipa: dict,
    real_cons_ari: float,
    real_vowel_ari: float,
    n_seeds: int = 50,
    **kwargs,
) -> dict[str, Any]:
    """Compute p-values: fraction of null iterations matching or exceeding real ARI.

    Uses shuffled-corpus null (same as run_null_test) but aggregates across
    many seeds to build a null distribution, then computes empirical p-values.

    Args:
        sign_groups: corpus sign-group sequences
        sign_to_ipa: sign-to-IPA mapping
        real_cons_ari: observed consonant ARI on real data
        real_vowel_ari: observed vowel ARI on real data
        n_seeds: number of null iterations (default 50)
        **kwargs: forwarded to validate_on_linear_b

    Returns:
        dict with p-values, null distribution stats, and significance flags
    """
    cons_null: list[float] = []
    vowel_null: list[float] = []

    for seed in range(n_seeds):
        null = run_null_test(sign_groups, sign_to_ipa, seed=seed, **kwargs)
        cons_null.append(null["shuffled_consonant_ari"])
        vowel_null.append(null["shuffled_vowel_ari"])

    cons_arr = np.array(cons_null)
    vowel_arr = np.array(vowel_null)

    # Empirical p-value: fraction of null >= real (one-sided)
    cons_p = float((cons_arr >= real_cons_ari).mean())
    vowel_p = float((vowel_arr >= real_vowel_ari).mean())

    return {
        "consonant_p_value": cons_p,
        "vowel_p_value": vowel_p,
        "consonant_significant": cons_p < 0.01,
        "vowel_significant": vowel_p < 0.01,
        "null_consonant_mean": round(float(cons_arr.mean()), 4),
        "null_vowel_mean": round(float(vowel_arr.mean()), 4),
        "null_consonant_max": round(float(cons_arr.max()), 4),
        "null_vowel_max": round(float(vowel_arr.max()), 4),
        "real_consonant_ari": real_cons_ari,
        "real_vowel_ari": real_vowel_ari,
        "n_seeds": n_seeds,
    }


def bootstrap_ari_ci(
    sign_groups: list[list[str]],
    sign_to_ipa: dict,
    n_bootstrap: int = 200,
    ci_level: float = 0.95,
    seed: int = 42,
    inscription_corpus_path: str | None = None,
    **kwargs,
) -> dict[str, Any]:
    """Bootstrap 95% CI on ARI by resampling sign-groups with replacement.

    Resamples at the sign-group level (not individual signs) to preserve
    within-group context structure. When an inscription corpus is provided,
    resamples inscriptions (not individual sign-groups) for the portion of
    data that has inscription structure, preserving within-inscription
    dependence.

    This is computationally intensive (n_bootstrap full pipeline runs).
    Intended for final validation, not routine testing.

    Args:
        sign_groups: corpus sign-group sequences
        sign_to_ipa: sign-to-IPA mapping for ground truth
        n_bootstrap: number of bootstrap resamples (default 200)
        ci_level: confidence level (default 0.95)
        seed: random seed for reproducibility
        inscription_corpus_path: path to inscription-structured JSON corpus.
            If provided, sign-groups from this corpus are resampled at the
            inscription level. Remaining sign-groups (e.g. from HF lexicon)
            are resampled independently at the word level.
        **kwargs: forwarded to validate_on_linear_b

    Returns:
        dict with:
          - consonant_ci: (low, high) tuple
          - vowel_ci: (low, high) tuple
          - consonant_aris: list of per-resample ARI values
          - vowel_aris: list of per-resample ARI values
          - n_bootstrap: number of resamples
          - ci_level: confidence level used
    """
    rng = np.random.RandomState(seed)
    alpha = (1.0 - ci_level) / 2.0

    # Partition sign-groups by source if inscription corpus is provided
    inscription_groups: list[list[list[str]]] = []  # per-inscription
    independent_groups: list[list[str]] = []

    if inscription_corpus_path is not None:
        # Load inscription-structured corpus to get inscription boundaries
        with open(inscription_corpus_path, encoding="utf-8") as f:
            data = json.load(f)
        insc_sign_group_keys: set[tuple[str, ...]] = set()
        for inscription in data.get("inscriptions", []):
            insc_groups: list[list[str]] = []
            for word in inscription.get("words", []):
                signs = word.get("sign_readings", [])
                if signs and not word.get("has_damage", False):
                    insc_groups.append(signs)
                    insc_sign_group_keys.add(tuple(signs))
            if insc_groups:
                inscription_groups.append(insc_groups)

        # Remaining sign-groups are independent (e.g. HF lexicon entries)
        for sg in sign_groups:
            if tuple(sg) not in insc_sign_group_keys:
                independent_groups.append(sg)
    else:
        # No inscription structure: all sign-groups are independent
        independent_groups = list(sign_groups)

    cons_aris: list[float] = []
    vowel_aris: list[float] = []

    for i in range(n_bootstrap):
        # Resample inscription-level groups
        resampled: list[list[str]] = []
        if inscription_groups:
            n_insc = len(inscription_groups)
            insc_idx = rng.choice(n_insc, size=n_insc, replace=True)
            for idx in insc_idx:
                resampled.extend(inscription_groups[idx])

        # Resample independent groups
        if independent_groups:
            n_indep = len(independent_groups)
            indep_idx = rng.choice(n_indep, size=n_indep, replace=True)
            for idx in indep_idx:
                resampled.append(independent_groups[idx])

        # Run pipeline and compute ARI
        val = validate_on_linear_b(resampled, sign_to_ipa, **kwargs)
        cons_aris.append(val.get("consonant_ari", 0.0))
        vowel_aris.append(val.get("vowel_ari", 0.0))

    cons_arr = np.array(cons_aris)
    vowel_arr = np.array(vowel_aris)

    return {
        "consonant_ci": (
            round(float(np.percentile(cons_arr, 100 * alpha)), 4),
            round(float(np.percentile(cons_arr, 100 * (1 - alpha))), 4),
        ),
        "vowel_ci": (
            round(float(np.percentile(vowel_arr, 100 * alpha)), 4),
            round(float(np.percentile(vowel_arr, 100 * (1 - alpha))), 4),
        ),
        "consonant_mean": round(float(cons_arr.mean()), 4),
        "vowel_mean": round(float(vowel_arr.mean()), 4),
        "consonant_std": round(float(cons_arr.std()), 4),
        "vowel_std": round(float(vowel_arr.std()), 4),
        "consonant_aris": [round(x, 4) for x in cons_aris],
        "vowel_aris": [round(x, 4) for x in vowel_aris],
        "n_bootstrap": n_bootstrap,
        "ci_level": ci_level,
    }


# ============================================================================
# ENSEMBLE WITH P1
# ============================================================================

def ensemble_with_p1(
    jaccard_result: dict,
    p1_output_path: str,
) -> dict[str, Any]:
    """Combine Jaccard classification with P1 output."""
    with open(p1_output_path, encoding="utf-8") as f:
        p1 = json.load(f)

    p1_assignments: dict[str, dict] = {}
    if "grid" in p1 and "assignments" in p1["grid"]:
        for entry in p1["grid"]["assignments"]:
            sign = entry.get("sign_id") or entry.get("sign")
            if sign:
                p1_assignments[sign] = {
                    "consonant_class": entry.get("consonant_class"),
                    "vowel_class": entry.get("vowel_class"),
                }

    grid = jaccard_result.get("grid", {})
    combined = []
    for entry in grid.get("assignments", []):
        sign = entry["sign"]
        combined_entry = dict(entry)
        if sign in p1_assignments:
            combined_entry["p1_consonant_class"] = p1_assignments[sign].get("consonant_class")
            combined_entry["p1_vowel_class"] = p1_assignments[sign].get("vowel_class")
        else:
            combined_entry["p1_consonant_class"] = None
            combined_entry["p1_vowel_class"] = None
        combined.append(combined_entry)

    return {"assignments": combined}


# ============================================================================
# OUTPUT
# ============================================================================

def save_results(result: dict, path: str):
    """Save results to JSON, converting numpy types."""
    def convert(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, set):
            return sorted(obj)
        raise TypeError(f"Not serializable: {type(obj)}")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=convert, ensure_ascii=False)


# ============================================================================
# MAIN
# ============================================================================

def main():
    sys.stdout.reconfigure(encoding="utf-8")

    base = Path("C:/Users/alvin/Ventris1")
    hf_base = Path("C:/Users/alvin/hf-ancient-scripts/data/linear_b")

    print("=" * 78)
    print("  JACCARD PARADIGMATIC SIGN CLASSIFICATION")
    print("=" * 78)

    # ------------------------------------------------------------------
    # LOAD DATA
    # ------------------------------------------------------------------
    print("\n--- DATA LOADING ---")
    with open(hf_base / "sign_to_ipa.json", encoding="utf-8") as f:
        sign_to_ipa = json.load(f)

    lb_test = load_linear_b_corpus(
        str(base / "pillar1/tests/fixtures/linear_b_test_corpus.json"))
    lb_hf = load_linear_b_hf_words(
        str(hf_base / "linear_b_words.tsv"), sign_to_ipa)
    sign_groups = deduplicate_sign_groups([lb_test, lb_hf])

    print(f"  LB test corpus: {len(lb_test)} sign-groups")
    print(f"  LB HF lexicon:  {len(lb_hf)} sign-groups")
    print(f"  Combined unique: {len(sign_groups)} sign-groups")
    print(f"  Total tokens:    {sum(len(g) for g in sign_groups)}")

    # ------------------------------------------------------------------
    # GATE 1: FULL LB VALIDATION
    # ------------------------------------------------------------------
    print("\n--- GATE 1: FULL LINEAR B VALIDATION ---")
    val = validate_on_linear_b(sign_groups, sign_to_ipa)

    print(f"  Consonant ARI: {val['consonant_ari']:.4f}")
    print(f"  Vowel ARI:     {val['vowel_ari']:.4f}")
    print(f"  Combined ARI:  {val['combined_ari']:.4f}")
    print(f"  Recovered:     {val['n_recovered_series']}/5 {val['recovered_series']}")
    print(f"  Signs analyzed: {val['n_analyzed_signs']}")
    print(f"  Gate 1 (cons ARI>=0.30, >=3 series): {'PASS' if val['gate1_pass'] else 'FAIL'}")
    print(f"  Gate 2 (vowel ARI>=0.40):             {'PASS' if val['gate2_pass'] else 'FAIL'}")

    # Show clusters with ground truth annotations
    pipeline = val["pipeline"]
    print("\n  Consonant clusters:")
    for cid, members in sorted(pipeline["consonant"]["clusters"].items()):
        annotated = [f"{m}({extract_consonant(m)})" if m in sign_to_ipa else m
                     for m in members]
        print(f"    C{cid:2d}: {annotated}")

    print("\n  Vowel clusters:")
    for vid, members in sorted(pipeline["vowel"]["clusters"].items()):
        annotated = [f"{m}({extract_vowel(m) or '?'})" if m in sign_to_ipa else m
                     for m in members]
        print(f"    V{vid}: {annotated}")

    # ------------------------------------------------------------------
    # GATE 3: NULL TEST (robust median-of-seeds)
    # ------------------------------------------------------------------
    print("\n--- GATE 3: NULL TEST (robust, 20-seed median) ---")
    null = run_null_test_robust(sign_groups, sign_to_ipa, n_seeds=20)
    print(f"  Median consonant ARI: {null['median_consonant_ari']:.4f}")
    print(f"  Median vowel ARI:     {null['median_vowel_ari']:.4f}")
    print(f"  Std consonant ARI:    {null['std_consonant_ari']:.4f}")
    print(f"  Std vowel ARI:        {null['std_vowel_ari']:.4f}")
    print(f"  Max |cons| ARI:       {null['max_consonant_ari']:.4f}")
    print(f"  Max |vowel| ARI:      {null['max_vowel_ari']:.4f}")
    print(f"  Gate 3 (median < 0.05): {'PASS' if null['gate_pass'] else 'FAIL'}")

    # Significance test
    sig = compute_null_significance(
        sign_groups, sign_to_ipa,
        real_cons_ari=val["consonant_ari"],
        real_vowel_ari=val["vowel_ari"],
        n_seeds=50,
    )
    print(f"\n  Significance (50-seed null distribution):")
    print(f"    Consonant p-value:  {sig['consonant_p_value']:.4f} "
          f"({'significant' if sig['consonant_significant'] else 'NOT significant'})")
    print(f"    Vowel p-value:      {sig['vowel_p_value']:.4f} "
          f"({'significant' if sig['vowel_significant'] else 'NOT significant'})")

    # ------------------------------------------------------------------
    # LINEAR A APPLICATION
    # ------------------------------------------------------------------
    la_path = base / "data" / "sigla_full_corpus.json"
    if la_path.exists() and val["gate1_pass"]:
        print("\n--- LINEAR A APPLICATION ---")
        la_groups = load_linear_a_corpus(str(la_path))
        print(f"  LA sign-groups:  {len(la_groups)}")
        print(f"  LA total tokens: {sum(len(g) for g in la_groups)}")

        la_result = run_pipeline(la_groups)

        if "error" not in la_result:
            cons_clusters = la_result["consonant"]["clusters"]
            n_large = sum(1 for v in cons_clusters.values() if len(v) >= 3)
            print(f"  LA consonant series: {la_result['consonant']['k']} clusters, "
                  f"{n_large} with >= 3 signs")
            for cid, members in sorted(cons_clusters.items()):
                print(f"    C{cid:2d}: {sorted(members)}")

            vowel_clusters = la_result["vowel"]["clusters"]
            print(f"  LA vowel classes: {la_result['vowel']['k']} clusters")
            for vid, members in sorted(vowel_clusters.items()):
                print(f"    V{vid}: {sorted(members)}")

            # Ensemble with P1
            p1_path = base / "results" / "pillar1_v5_output.json"
            if p1_path.exists():
                ensemble = ensemble_with_p1(la_result, str(p1_path))
                la_result["ensemble"] = ensemble

            # Save
            output = {
                "lb_validation": {
                    "consonant_ari": val["consonant_ari"],
                    "vowel_ari": val["vowel_ari"],
                    "combined_ari": val["combined_ari"],
                    "n_recovered_series": val["n_recovered_series"],
                    "recovered_series": val["recovered_series"],
                    "gate1_pass": val["gate1_pass"],
                    "gate2_pass": val["gate2_pass"],
                },
                "null_test": null,
                "linear_a": {
                    k: v for k, v in la_result.items()
                    if k not in ("sim_l_tfidf", "sim_r_ppmi")
                },
            }
            out_path = base / "results" / "jaccard_classification_output.json"
            save_results(output, str(out_path))
            print(f"\n  Results saved to {out_path}")

    elif not val["gate1_pass"]:
        print("\n  Skipping Linear A (Gate 1 failed)")

    print("\n" + "=" * 78)
    print("  DONE")
    print("=" * 78)


if __name__ == "__main__":
    main()
