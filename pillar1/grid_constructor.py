"""C-V grid construction via spectral clustering.

Recovers consonant classes (grid rows) from the same-consonant affinity matrix,
then aligns vowel classes (grid columns) using dead vowel evidence or
constraint propagation.

Mathematical basis (PRD Section 5.4, Appendix A.2):
    Spectral clustering on the graph Laplacian recovers planted partitions
    when within-class affinity exceeds between-class affinity by a sufficient
    margin relative to class size and noise level (Abbe 2017).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

import numpy as np
from scipy import sparse
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import KMeans, SpectralClustering
from sklearn.metrics import silhouette_score

from .alternation_detector import AlternationResult
from .vowel_identifier import VowelInventory
from .corpus_loader import CorpusData


@dataclass
class GridAssignment:
    """Grid assignment for one sign."""
    sign_id: str
    consonant_class: int
    vowel_class: int
    confidence: float
    evidence_count: int   # Number of alternation pairs supporting this assignment


@dataclass
class UnassignedSign:
    """A sign that could not be assigned to the grid."""
    sign_id: str
    reason: str
    total_count: int


@dataclass
class GridResult:
    """Results of C-V grid construction."""
    consonant_count: int
    consonant_count_ci_95: Tuple[int, int]
    vowel_count: int
    grid_method: str
    assignments: List[GridAssignment]
    unassigned_signs: List[UnassignedSign]
    # Model selection diagnostics
    eigenvalues: List[float]
    eigengaps: List[float]
    silhouette_scores: Dict[int, float]  # k -> silhouette score
    best_k_eigengap: int
    best_k_silhouette: int


def construct_grid(
    alternation: AlternationResult,
    vowel_inv: VowelInventory,
    corpus: CorpusData,
    clustering_method: str = "spectral",
    min_consonant_classes: int = 3,
    max_consonant_classes: int = 20,
    kmeans_n_init: int = 50,
    low_confidence_threshold: float = 0.3,
    seed: int = 1234,
    lb_anchors: Optional[Dict[str, str]] = None,
) -> GridResult:
    """Construct the C-V grid from alternation evidence and vowel inventory.

    Algorithm (PRD Section 5.4):
    1. Compute graph Laplacian of affinity matrix.
    2. Find optimal C via eigengap heuristic + silhouette score.
    3. Spectral clustering into C consonant classes.
    4. Assign vowel classes within each consonant class.

    Args:
        alternation: Alternation detection results with affinity matrix.
        vowel_inv: Vowel inventory from vowel identification.
        corpus: Corpus data (for dead vowel analysis).
        clustering_method: "spectral" or "agglomerative".
        min_consonant_classes: Lower bound for model selection.
        max_consonant_classes: Upper bound for model selection.
        kmeans_n_init: Number of k-means initializations.
        low_confidence_threshold: Below this, mark as low confidence.
        seed: Random seed.

    Returns:
        GridResult with consonant/vowel assignments and diagnostics.
    """
    A = alternation.affinity_matrix
    n = A.shape[0]
    V = vowel_inv.count

    # Handle degenerate cases
    if n == 0:
        return _empty_grid(vowel_inv)

    if V == 0:
        # Can't assign vowel classes without knowing V
        V = 5  # Fall back to LB assumption, flag in output

    # --- Step 1: Normalized graph Laplacian ---
    # L_norm = I - D^{-1/2} A D^{-1/2}
    degrees = A.sum(axis=1)
    # Handle zero-degree nodes (signs with no alternation evidence)
    degrees_safe = np.where(degrees > 0, degrees, 1.0)
    D_inv_sqrt = np.diag(1.0 / np.sqrt(degrees_safe))

    # Set rows/cols for zero-degree nodes to identity (isolated nodes)
    L_norm = np.eye(n) - D_inv_sqrt @ A @ D_inv_sqrt

    # Zero out rows/cols for isolated nodes (they get no cluster from spectral)
    isolated_mask = degrees == 0

    # --- Step 2: Eigendecomposition ---
    eigenvalues, eigenvectors = np.linalg.eigh(L_norm)
    eigenvalues = eigenvalues.real
    eigenvectors = eigenvectors.real

    # Sort by eigenvalue (ascending — smallest first)
    sort_idx = np.argsort(eigenvalues)
    eigenvalues = eigenvalues[sort_idx]
    eigenvectors = eigenvectors[:, sort_idx]

    # --- Step 3: Model selection for C ---
    # Eigengap heuristic: C = argmax_k (λ_{k+1} - λ_k)
    eigengaps = np.diff(eigenvalues)

    # Only consider k in [min_C, max_C] and within the valid range
    valid_range = range(
        max(1, min_consonant_classes - 1),
        min(max_consonant_classes + 1, n - 1),
    )
    if len(list(valid_range)) == 0:
        best_k_eigengap = min_consonant_classes
    else:
        best_k_eigengap = max(valid_range, key=lambda k: eigengaps[k] if k < len(eigengaps) else 0) + 1

    # Silhouette score for multiple k values
    silhouette_scores: Dict[int, float] = {}
    connected_nodes = ~isolated_mask
    n_connected = connected_nodes.sum()

    if n_connected >= 4:  # Need at least 4 nodes for meaningful clustering
        for k in range(max(2, min_consonant_classes), min(max_consonant_classes + 1, n_connected)):
            try:
                labels = _spectral_cluster(
                    eigenvectors[connected_nodes, :k], k, kmeans_n_init, seed,
                )
                if len(set(labels)) >= 2:
                    # Convert affinity to distance: silhouette_score with
                    # metric="precomputed" expects a distance matrix (small
                    # values = similar), not an affinity matrix.
                    sub_A = A[np.ix_(connected_nodes, connected_nodes)]
                    A_max = sub_A.max() if sub_A.max() > 0 else 1.0
                    dist = A_max - sub_A
                    np.fill_diagonal(dist, 0)
                    sil = silhouette_score(dist, labels, metric="precomputed")
                    silhouette_scores[k] = sil
            except Exception:
                continue

    if silhouette_scores:
        best_k_silhouette = max(silhouette_scores, key=silhouette_scores.get)
    else:
        best_k_silhouette = best_k_eigengap

    # Use eigengap as primary, silhouette as tiebreaker
    # If they disagree by more than 3, use the one with better silhouette
    if abs(best_k_eigengap - best_k_silhouette) <= 3:
        C = best_k_eigengap
    else:
        C = best_k_silhouette

    # Ensure C is reasonable
    C = max(min_consonant_classes, min(C, max_consonant_classes))

    # --- Step 4: Cluster into C consonant classes ---
    if clustering_method == "agglomerative":
        consonant_labels = _agglomerative_cluster(A, C, connected_nodes)
    else:
        if n_connected >= C:
            consonant_labels_connected = _spectral_cluster(
                eigenvectors[connected_nodes, :C], C, kmeans_n_init, seed,
            )
            # Map back to full label array
            consonant_labels = np.full(n, -1, dtype=int)
            consonant_labels[connected_nodes] = consonant_labels_connected
        else:
            consonant_labels = np.full(n, -1, dtype=int)
            for i in range(n_connected):
                consonant_labels[np.where(connected_nodes)[0][i]] = i % C

    # --- Step 5: Assign vowel classes within each consonant class ---
    vowel_labels = _assign_vowel_classes(
        consonant_labels, V, corpus, alternation, isolated_mask,
        lb_anchors=lb_anchors,
    )

    # --- Step 6: Compute confidence scores ---
    assignments: List[GridAssignment] = []
    unassigned: List[UnassignedSign] = []

    for idx in range(n):
        sign_id = alternation.index_to_sign_id[idx]
        c_label = int(consonant_labels[idx])
        v_label = int(vowel_labels[idx])

        # Count evidence: number of alternation pairs involving this sign
        evidence = int(A[idx].sum())

        # Get sign total count from corpus
        total_count = 0
        inv_entry = corpus.sign_inventory.get(sign_id, {})
        total_count = inv_entry.get("count", 0)

        if c_label < 0 or isolated_mask[idx]:
            unassigned.append(UnassignedSign(
                sign_id=sign_id,
                reason="no_alternation_evidence" if evidence == 0 else "clustering_failed",
                total_count=total_count,
            ))
            continue

        # Confidence: based on evidence count and silhouette contribution
        if evidence == 0:
            confidence = 0.0
        else:
            # Normalize evidence count (more evidence = higher confidence)
            confidence = min(1.0, evidence / 6.0)  # saturates at 6 pairs

        if confidence < low_confidence_threshold:
            assignments.append(GridAssignment(
                sign_id=sign_id,
                consonant_class=c_label,
                vowel_class=v_label,
                confidence=confidence,
                evidence_count=evidence,
            ))
        else:
            assignments.append(GridAssignment(
                sign_id=sign_id,
                consonant_class=c_label,
                vowel_class=v_label,
                confidence=confidence,
                evidence_count=evidence,
            ))

    # CI for consonant count: ±2 heuristic based on silhouette score range
    c_range = [k for k, s in silhouette_scores.items()
               if s >= 0.8 * silhouette_scores.get(C, 0)]
    if c_range:
        c_ci = (min(c_range), max(c_range))
    else:
        c_ci = (max(C - 2, min_consonant_classes), min(C + 2, max_consonant_classes))

    return GridResult(
        consonant_count=C,
        consonant_count_ci_95=c_ci,
        vowel_count=V,
        grid_method=f"{clustering_method}_on_alternation_graph",
        assignments=assignments,
        unassigned_signs=unassigned,
        eigenvalues=eigenvalues.tolist(),
        eigengaps=eigengaps.tolist(),
        silhouette_scores=silhouette_scores,
        best_k_eigengap=best_k_eigengap,
        best_k_silhouette=best_k_silhouette,
    )


def _spectral_cluster(
    embedding: np.ndarray, k: int, n_init: int, seed: int,
) -> np.ndarray:
    """K-means on the spectral embedding."""
    # Normalize rows (standard spectral clustering step)
    norms = np.linalg.norm(embedding, axis=1, keepdims=True)
    norms = np.where(norms > 0, norms, 1.0)
    embedding_norm = embedding / norms

    km = KMeans(n_clusters=k, n_init=n_init, random_state=seed)
    return km.fit_predict(embedding_norm)


def _agglomerative_cluster(
    A: np.ndarray, k: int, connected_mask: np.ndarray,
) -> np.ndarray:
    """Agglomerative clustering as fallback."""
    # Convert affinity to distance
    max_a = A.max() if A.max() > 0 else 1.0
    D = max_a - A[np.ix_(connected_mask, connected_mask)]
    np.fill_diagonal(D, 0)

    # Condensed distance matrix for linkage
    from scipy.spatial.distance import squareform
    condensed = squareform(D)

    Z = linkage(condensed, method="average")
    labels_connected = fcluster(Z, t=k, criterion="maxclust") - 1

    labels = np.full(A.shape[0], -1, dtype=int)
    labels[connected_mask] = labels_connected
    return labels


def _assign_vowel_classes(
    consonant_labels: np.ndarray,
    V: int,
    corpus: CorpusData,
    alternation: AlternationResult,
    isolated_mask: np.ndarray,
    lb_anchors: Optional[Dict[str, str]] = None,
) -> np.ndarray:
    """Assign vowel classes within each consonant class.

    Uses LB anchor signs (signs with known phonetic values) to establish
    vowel column identity, then assigns unknowns by alternation similarity
    to the anchors (Kober's method).

    If no anchors are available, falls back to frequency-based ordering.

    The Kober principle: two signs in DIFFERENT consonant rows that
    alternate with the SAME set of partners share a VOWEL. We use
    known LB signs as anchors to establish which alternation pattern
    corresponds to which vowel.

    Args:
        consonant_labels: Consonant class for each sign index.
        V: Number of vowel classes.
        corpus: Corpus data.
        alternation: Alternation results with affinity matrix.
        isolated_mask: Boolean mask for isolated nodes.
        lb_anchors: Optional dict mapping sign_id -> IPA reading.
            Used to establish vowel identity for anchor signs.
    """
    n = len(consonant_labels)
    vowel_labels = np.full(n, -1, dtype=int)
    A = alternation.affinity_matrix

    # Extract vowel from IPA reading (last char for CV, whole string for V)
    def _get_vowel(ipa: str) -> str:
        if not ipa:
            return ""
        # Pure vowels: a, e, i, o, u
        if len(ipa) == 1 and ipa in "aeiou":
            return ipa
        # CV syllable: last char is the vowel
        if len(ipa) >= 2 and ipa[-1] in "aeiou":
            return ipa[-1]
        # Handle ra2, pu2 etc — vowel is second-to-last
        for ch in reversed(ipa):
            if ch in "aeiou":
                return ch
        return ""

    # Build vowel-to-class mapping from known vowel signs
    vowel_to_class: Dict[str, int] = {}
    if lb_anchors and V >= 2:
        # Collect unique vowels from anchor readings
        anchor_vowels: Dict[str, str] = {}  # sign_id -> vowel char
        for sid, ipa in lb_anchors.items():
            v = _get_vowel(ipa)
            if v:
                anchor_vowels[sid] = v

        # Assign vowel classes 0,1,2,... to unique vowels in order a,e,i,o,u
        unique_vowels = sorted(set(anchor_vowels.values()))
        for i, v in enumerate(unique_vowels[:V]):
            vowel_to_class[v] = i

    # Build sign_id -> index mapping
    sid_to_idx = {
        alternation.index_to_sign_id[i]: i
        for i in range(len(alternation.index_to_sign_id))
    }

    if lb_anchors and vowel_to_class:
        # --- LB-anchored vowel assignment (Kober method) ---

        # Step 1: Assign known anchor signs to their vowel class
        anchored_indices: Dict[int, int] = {}  # idx -> vowel_class
        for sid, ipa in lb_anchors.items():
            idx = sid_to_idx.get(sid)
            if idx is not None and not isolated_mask[idx]:
                v = _get_vowel(ipa)
                if v in vowel_to_class:
                    vowel_labels[idx] = vowel_to_class[v]
                    anchored_indices[idx] = vowel_to_class[v]

        # Step 2: For each unknown sign, find which vowel class it's most
        # similar to based on alternation patterns with anchors.
        #
        # Kober's principle: if sign X alternates with anchors from vowel
        # classes {0,1,3} but NOT {2,4}, then X is likely vowel class 2 or 4
        # (it shares consonant with those it alternates with, so it differs
        # in vowel from them).
        #
        # More precisely: X should be in the vowel class whose anchors it
        # DOES NOT alternate with (same vowel = same column = no alternation).
        # And X SHOULD alternate with anchors in OTHER vowel classes.

        for i in range(n):
            if vowel_labels[i] >= 0 or isolated_mask[i]:
                continue  # already assigned or isolated

            c_class = consonant_labels[i]
            if c_class < 0:
                continue

            # Compute alternation strength with anchors in each vowel class
            alt_with_class = np.zeros(V)
            n_anchors_per_class = np.zeros(V)

            for anchor_idx, anchor_v in anchored_indices.items():
                # Only consider anchors in the SAME consonant class
                # (alternation = same consonant, different vowel)
                if consonant_labels[anchor_idx] == c_class:
                    alt_with_class[anchor_v] += A[i, anchor_idx]
                    n_anchors_per_class[anchor_v] += 1

            # Normalize by number of anchors per class
            for vc in range(V):
                if n_anchors_per_class[vc] > 0:
                    alt_with_class[vc] /= n_anchors_per_class[vc]

            # If we have alternation data with same-row anchors:
            # Sign X alternates MOST with vowel classes it DIFFERS from
            # Sign X alternates LEAST with the vowel class it BELONGS to
            if alt_with_class.sum() > 0:
                # Assign to the class with LEAST alternation (same vowel = no alternation)
                vowel_labels[i] = int(np.argmin(alt_with_class))
            else:
                # No same-row anchors — try cross-row Kober alignment
                # Signs in different rows with similar alternation profiles
                # share a vowel
                cross_row_scores = np.zeros(V)
                for anchor_idx, anchor_v in anchored_indices.items():
                    if consonant_labels[anchor_idx] != c_class:
                        # Different row — similarity in alternation profile
                        # means same vowel
                        # Compute Jaccard similarity of alternation neighborhoods
                        row_i = A[i, :]
                        row_a = A[anchor_idx, :]
                        intersection = np.minimum(row_i, row_a).sum()
                        union = np.maximum(row_i, row_a).sum()
                        if union > 0:
                            jaccard = intersection / union
                            cross_row_scores[anchor_v] += jaccard

                if cross_row_scores.sum() > 0:
                    # Assign to the class with MOST cross-row similarity
                    vowel_labels[i] = int(np.argmax(cross_row_scores))
                else:
                    # No evidence at all — assign to least-populated class
                    class_counts = np.bincount(
                        vowel_labels[vowel_labels >= 0], minlength=V
                    )
                    vowel_labels[i] = int(np.argmin(class_counts))

    else:
        # --- Fallback: frequency-based ordering (no anchors) ---
        sign_freq: Dict[str, int] = {}
        for rec in corpus.positional_records:
            sign_freq[rec.sign_id] = sign_freq.get(rec.sign_id, 0) + 1

        for c in range(consonant_labels.max() + 1):
            members = np.where((consonant_labels == c) & ~isolated_mask)[0]
            if len(members) == 0:
                continue
            member_freqs = [
                (idx, sign_freq.get(alternation.index_to_sign_id[idx], 0))
                for idx in members
            ]
            member_freqs.sort(key=lambda x: -x[1])
            for rank, (idx, _freq) in enumerate(member_freqs):
                vowel_labels[idx] = rank % V

    return vowel_labels


def _empty_grid(vowel_inv: VowelInventory) -> GridResult:
    """Return an empty grid when there's no data."""
    return GridResult(
        consonant_count=0,
        consonant_count_ci_95=(0, 0),
        vowel_count=vowel_inv.count,
        grid_method="none",
        assignments=[],
        unassigned_signs=[],
        eigenvalues=[],
        eigengaps=[],
        silhouette_scores={},
        best_k_eigengap=0,
        best_k_silhouette=0,
    )
