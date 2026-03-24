"""Word class induction via SVD + agglomerative clustering.

PRD Section 5.2: Cluster stems into grammatical classes based on
distributional similarity.

1. Apply TruncatedSVD for dimensionality reduction (denoise sparse PPMI).
2. Agglomerative clustering (Ward linkage) on the reduced representation.
3. Model selection for k using silhouette + morphological coherence.
4. Label clusters based on dominant morphological profile.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.distance import pdist
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from .data_loader import Pillar2Data
from .profile_builder import ProfileMatrix


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class WordClassDescription:
    """Description of an induced word class.

    PRD Section 5.2 (step 4): Each cluster gets a descriptive label
    based on its dominant morphological profile and positional signature.
    """
    class_id: int
    suggested_label: str
    n_members: int
    morphological_profile: str
    positional_profile: Dict[str, float]
    top_members: List[Dict[str, Any]]
    distributional_signature: Dict[str, Any]


@dataclass
class WordClassResult:
    """Result of word class induction.

    Contains the cluster assignments, class descriptions, and model
    selection diagnostics.

    Attributes:
        n_classes: Selected number of word classes.
        assignments: Mapping from stem tuple to class_id.
        classes: Detailed description per class.
        silhouette: Silhouette score for the selected k.
        silhouette_curve: Silhouette scores for all tested k values.
        morph_coherence_curve: Morphological coherence for all tested k.
        combined_score_curve: Combined scores for all tested k.
        svd_explained_variance: Explained variance ratio per SVD component.
        reduced_matrix: The SVD-reduced feature matrix (n_stems x d).
    """
    n_classes: int
    assignments: Dict[Tuple[str, ...], int]
    classes: List[WordClassDescription]
    silhouette: float
    silhouette_curve: Dict[int, float] = field(default_factory=dict)
    morph_coherence_curve: Dict[int, float] = field(default_factory=dict)
    combined_score_curve: Dict[int, float] = field(default_factory=dict)
    svd_explained_variance: List[float] = field(default_factory=list)
    reduced_matrix: Optional[np.ndarray] = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: Dict[str, Any] = {
    "min_k": 3,
    "max_k": 10,
    "svd_target_variance": 0.80,  # Explained variance threshold
    "svd_max_components": 20,     # Maximum SVD dimensions
    "svd_min_components": 5,      # Minimum SVD dimensions
    "silhouette_weight": 0.5,     # Weight for silhouette in model selection
    "morph_coherence_weight": 0.5, # Weight for morphological coherence
    "label_threshold": 0.60,      # Fraction threshold for labeling a cluster
    "top_members_per_class": 10,  # Number of top members to report
    "random_state": 42,
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _select_svd_components(
    feature_matrix: np.ndarray,
    target_variance: float,
    max_components: int,
    min_components: int,
    random_state: int,
) -> Tuple[np.ndarray, TruncatedSVD]:
    """Apply TruncatedSVD and select number of components.

    PRD Section 5.2 (step 2): Apply Truncated SVD to reduce X to d
    dimensions, selected by explained variance threshold of 80%.

    Args:
        feature_matrix: The stem x feature matrix.
        target_variance: Cumulative explained variance target.
        max_components: Upper bound on components.
        min_components: Lower bound on components.
        random_state: Random seed for reproducibility.

    Returns:
        (reduced_matrix, svd_model)
    """
    n_samples, n_features = feature_matrix.shape
    # Can't have more components than min(n_samples, n_features) - 1
    max_possible = min(n_samples, n_features) - 1
    max_components = min(max_components, max_possible)
    max_components = max(max_components, 1)

    # Fit with max_components first, then select
    svd = TruncatedSVD(n_components=max_components, random_state=random_state)
    reduced = svd.fit_transform(feature_matrix)

    # Find minimum d that explains target_variance
    cumvar = np.cumsum(svd.explained_variance_ratio_)
    d = max_components
    for i, cv in enumerate(cumvar):
        if cv >= target_variance:
            d = i + 1
            break

    d = max(d, min_components)
    d = min(d, max_components)

    return reduced[:, :d], svd


def _morphological_coherence(
    labels: np.ndarray,
    stems: List[Tuple[str, ...]],
    pillar2: Pillar2Data,
) -> float:
    """Compute morphological coherence for a clustering.

    PRD Section 5.2 (model selection): morphological_coherence(k) =
    mean over clusters of max_label_fraction, where max_label_fraction
    is the fraction of the cluster's members that share the most common
    Pillar 2 word_class_hint.

    Args:
        labels: Cluster assignments (array of ints).
        stems: Ordered list of stem tuples.
        pillar2: Pillar 2 data for word class hints.

    Returns:
        Mean max_label_fraction across clusters (0.0 to 1.0).
    """
    unique_labels = set(labels)
    if not unique_labels:
        return 0.0

    coherences: List[float] = []

    for k in unique_labels:
        cluster_stems = [stems[i] for i in range(len(stems)) if labels[i] == k]
        if not cluster_stems:
            continue

        hint_counts: Counter = Counter()
        for stem in cluster_stems:
            hint = pillar2.stem_to_word_class.get(stem, "unknown")
            hint_counts[hint] += 1

        max_fraction = max(hint_counts.values()) / len(cluster_stems)
        coherences.append(max_fraction)

    return float(np.mean(coherences)) if coherences else 0.0


def _label_cluster(
    cluster_stems: List[Tuple[str, ...]],
    cluster_id: int,
    pillar2: Pillar2Data,
    profiles: ProfileMatrix,
    threshold: float,
    top_n: int,
) -> WordClassDescription:
    """Generate a descriptive label and profile for a cluster.

    PRD Section 5.2 (step 4): Label based on dominant morphological profile:
    - >60% declining -> content_word_X
    - >60% uninflected -> functional / particle
    - otherwise -> content_word_X
    """
    # Count morphological hints
    hint_counts: Counter = Counter()
    for stem in cluster_stems:
        hint = pillar2.stem_to_word_class.get(stem, "unknown")
        hint_counts[hint] += 1

    total = len(cluster_stems)
    dominant_hint = hint_counts.most_common(1)[0][0] if hint_counts else "unknown"
    dominant_frac = hint_counts[dominant_hint] / total if total > 0 else 0.0

    # Generate label
    if dominant_hint == "declining" and dominant_frac >= threshold:
        label = f"content_word_{chr(65 + cluster_id)}"
        morph_profile = "declining"
    elif dominant_hint == "uninflected" and dominant_frac >= threshold:
        label = "functional"
        morph_profile = "uninflected"
    else:
        label = f"content_word_{chr(65 + cluster_id)}"
        morph_profile = "mixed"

    # Positional profile (mean across cluster members)
    pos_profile: Dict[str, float] = {
        "mean_position": 0.5,
        "initial_rate": 0.0,
        "final_rate": 0.0,
        "pre_numeral_rate": 0.0,
    }

    pos_feature_map = {
        "pos:relative_position": "mean_position",
        "pos:is_initial": "initial_rate",
        "pos:is_final": "final_rate",
        "pos:is_pre_numeral": "pre_numeral_rate",
    }

    for feat_name, profile_key in pos_feature_map.items():
        if feat_name in profiles.feature_names:
            col_idx = profiles.feature_names.index(feat_name)
            values = []
            for stem in cluster_stems:
                if stem in profiles.stem_index:
                    row_idx = profiles.stem_index[stem]
                    values.append(profiles.feature_matrix[row_idx, col_idx])
            if values:
                pos_profile[profile_key] = float(np.mean(values))

    # Top members by frequency
    freq_sorted = sorted(
        cluster_stems,
        key=lambda s: profiles.stem_frequencies.get(s, 0),
        reverse=True,
    )[:top_n]
    top_members = [
        {
            "stem": list(s),
            "frequency": profiles.stem_frequencies.get(s, 0),
        }
        for s in freq_sorted
    ]

    return WordClassDescription(
        class_id=cluster_id,
        suggested_label=label,
        n_members=total,
        morphological_profile=morph_profile,
        positional_profile=pos_profile,
        top_members=top_members,
        distributional_signature={
            "dominant_hint": dominant_hint,
            "dominant_fraction": round(dominant_frac, 3),
            "hint_distribution": dict(hint_counts),
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def induce_word_classes(
    profiles: ProfileMatrix,
    pillar2: Pillar2Data,
    config: Optional[Dict[str, Any]] = None,
) -> WordClassResult:
    """Induce word classes via SVD + agglomerative clustering.

    PRD Section 5.2: Full pipeline from feature matrix to labeled word
    classes with model selection.

    Args:
        profiles: Distributional profile matrix from profile_builder.
        pillar2: Pillar 2 data for morphological constraints.
        config: Optional configuration overrides.

    Returns:
        WordClassResult with assignments, class descriptions, and
        model selection diagnostics.
    """
    cfg = {**_DEFAULT_CONFIG, **(config or {})}
    min_k = cfg["min_k"]
    max_k = cfg["max_k"]
    random_state = cfg["random_state"]
    sil_weight = cfg["silhouette_weight"]
    morph_weight = cfg["morph_coherence_weight"]
    label_threshold = cfg["label_threshold"]
    top_members = cfg["top_members_per_class"]

    stems = profiles.stems
    feature_matrix = profiles.feature_matrix

    if len(stems) < min_k:
        # Not enough stems for clustering
        assignments = {s: 0 for s in stems}
        desc = _label_cluster(
            stems, 0, pillar2, profiles, label_threshold, top_members
        )
        return WordClassResult(
            n_classes=1,
            assignments=assignments,
            classes=[desc],
            silhouette=0.0,
        )

    # --- Step 1: Standardize features ---
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(feature_matrix)

    # Replace NaNs (from zero-variance features) with 0
    X_scaled = np.nan_to_num(X_scaled, nan=0.0)

    # --- Step 2: SVD dimensionality reduction ---
    X_reduced, svd = _select_svd_components(
        X_scaled,
        target_variance=cfg["svd_target_variance"],
        max_components=cfg["svd_max_components"],
        min_components=cfg["svd_min_components"],
        random_state=random_state,
    )

    # --- Step 3: Model selection over k ---
    max_k = min(max_k, len(stems) - 1)
    max_k = max(max_k, min_k)

    silhouette_curve: Dict[int, float] = {}
    morph_coherence_curve: Dict[int, float] = {}
    combined_curve: Dict[int, float] = {}

    best_k = min_k
    best_score = -np.inf
    best_labels: Optional[np.ndarray] = None

    for k in range(min_k, max_k + 1):
        clustering = AgglomerativeClustering(
            n_clusters=k, linkage="ward"
        )
        labels = clustering.fit_predict(X_reduced)

        # Silhouette score (requires at least 2 clusters with >1 member)
        unique_labels = set(labels)
        if len(unique_labels) >= 2:
            sil = silhouette_score(X_reduced, labels)
        else:
            sil = 0.0
        silhouette_curve[k] = sil

        # Morphological coherence
        mc = _morphological_coherence(labels, stems, pillar2)
        morph_coherence_curve[k] = mc

        # Combined score (PRD: 0.5*silhouette + 0.5*morph_coherence)
        combined = sil_weight * sil + morph_weight * mc
        combined_curve[k] = combined

        if combined > best_score:
            best_score = combined
            best_k = k
            best_labels = labels.copy()

    if best_labels is None:
        # Fallback: single cluster
        best_labels = np.zeros(len(stems), dtype=int)
        best_k = 1

    # --- Step 4: Build results ---
    assignments: Dict[Tuple[str, ...], int] = {}
    cluster_stems_map: Dict[int, List[Tuple[str, ...]]] = {}

    for i, stem in enumerate(stems):
        cid = int(best_labels[i])
        assignments[stem] = cid
        if cid not in cluster_stems_map:
            cluster_stems_map[cid] = []
        cluster_stems_map[cid].append(stem)

    # Label and describe each cluster
    classes: List[WordClassDescription] = []
    for cid in sorted(cluster_stems_map.keys()):
        desc = _label_cluster(
            cluster_stems_map[cid], cid, pillar2, profiles,
            label_threshold, top_members,
        )
        classes.append(desc)

    return WordClassResult(
        n_classes=best_k,
        assignments=assignments,
        classes=classes,
        silhouette=silhouette_curve.get(best_k, 0.0),
        silhouette_curve=silhouette_curve,
        morph_coherence_curve=morph_coherence_curve,
        combined_score_curve=combined_curve,
        svd_explained_variance=svd.explained_variance_ratio_.tolist(),
        reduced_matrix=X_reduced,
    )
