"""Inflectional alternation detection (Kober's triplets).

Finds pairs of sign-groups sharing a common prefix but differing in final signs,
indicating the differing signs share a consonant (same grid row) but differ in vowel.

Mathematical basis (PRD Section 5.3):
    For words w_a = [s1,...,sk, a] and w_b = [s1,...,sk, b] where a != b,
    (a, b) is a same-consonant candidate. Evidence is weighted by number
    of independent stems showing the alternation, filtered by significance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple
from collections import defaultdict

import numpy as np
from scipy import stats as sp_stats

from .corpus_loader import CorpusData


@dataclass
class AlternationPair:
    """A pair of signs that alternate in word-final position."""
    sign_a: str
    sign_b: str
    independent_stems: int   # Number of distinct prefixes showing this alternation
    stem_examples: List[Tuple[str, str]]  # List of (prefix, word_a, word_b) examples
    expected_by_chance: float
    p_value: float
    significant: bool


@dataclass
class AlternationResult:
    """Results of inflectional alternation detection."""
    all_pairs: List[AlternationPair]
    significant_pairs: List[AlternationPair]
    affinity_matrix: np.ndarray       # N x N symmetric matrix
    sign_id_to_index: Dict[str, int]  # Maps sign_id to matrix index
    index_to_sign_id: Dict[int, str]  # Maps matrix index to sign_id
    # Diagnostics
    total_prefix_groups: int = 0
    total_candidate_pairs: int = 0
    total_significant_pairs: int = 0


def detect_alternations(
    corpus: CorpusData,
    min_shared_prefix_length: int = 1,
    max_suffix_diff_length: int = 2,
    min_independent_stems: int = 2,
    alternation_alpha: float = 0.01,
) -> AlternationResult:
    """Detect inflectional alternation pairs (Kober's triplets).

    Algorithm (PRD Section 5.3):
    1. Find all word pairs sharing a prefix of length >= min_shared_prefix_length,
       differing in the last max_suffix_diff_length signs.
    2. Count independent stems per alternation pair.
    3. Filter by significance (Poisson test vs. chance co-occurrence).
    4. Build same-consonant affinity matrix.

    Args:
        corpus: Processed corpus data.
        min_shared_prefix_length: Minimum shared prefix length in signs.
        max_suffix_diff_length: Maximum differing suffix length (1 or 2).
        min_independent_stems: Minimum independent stems for a pair to be retained.
        alternation_alpha: Significance level for pair filtering.

    Returns:
        AlternationResult with affinity matrix and pair details.
    """
    # --- Step 1: Collect all unique words (as sign ID tuples) ---
    unique_words: Set[Tuple[str, ...]] = set()
    for insc in corpus.inscriptions:
        for word in insc.words:
            sids = tuple(word.sign_ids)
            if len(sids) >= 2:  # Need at least 2 signs for prefix + suffix
                unique_words.add(sids)

    word_list = sorted(unique_words)

    # --- Step 2: Build prefix → words index ---
    # For suffix_diff_length = 1: prefix = word[:-1], suffix = word[-1]
    # For suffix_diff_length = 2: prefix = word[:-2], suffix = word[-2:]

    # Collect alternation evidence for each pair
    # Key: frozenset({sign_a, sign_b}), Value: set of prefixes
    pair_stems: Dict[frozenset, Set[Tuple[str, ...]]] = defaultdict(set)
    pair_examples: Dict[frozenset, List[Tuple[str, str, str]]] = defaultdict(list)

    for diff_len in range(1, max_suffix_diff_length + 1):
        prefix_groups: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = defaultdict(list)

        for word in word_list:
            if len(word) < min_shared_prefix_length + diff_len:
                continue
            prefix = word[:-diff_len]
            if len(prefix) >= min_shared_prefix_length:
                prefix_groups[prefix].append(word)

        # For each prefix group with 2+ words, extract alternation pairs
        for prefix, words_in_group in prefix_groups.items():
            if len(words_in_group) < 2:
                continue

            for i in range(len(words_in_group)):
                for j in range(i + 1, len(words_in_group)):
                    w_a = words_in_group[i]
                    w_b = words_in_group[j]

                    if diff_len == 1:
                        # Single sign difference
                        sign_a = w_a[-1]
                        sign_b = w_b[-1]
                        if sign_a != sign_b:
                            pair_key = frozenset({sign_a, sign_b})
                            pair_stems[pair_key].add(prefix)
                            # Weight = 1.0 for single-sign diff
                            pair_examples[pair_key].append((
                                "-".join(prefix),
                                "-".join(w_a),
                                "-".join(w_b),
                            ))
                    elif diff_len == 2:
                        # Two sign difference — generates two pairs at weight 0.5
                        a1, a2 = w_a[-2], w_a[-1]
                        b1, b2 = w_b[-2], w_b[-1]

                        if a1 != b1:
                            pk1 = frozenset({a1, b1})
                            pair_stems[pk1].add(prefix)
                            pair_examples[pk1].append((
                                "-".join(prefix),
                                "-".join(w_a),
                                "-".join(w_b),
                            ))
                        if a2 != b2:
                            pk2 = frozenset({a2, b2})
                            pair_stems[pk2].add(prefix)
                            pair_examples[pk2].append((
                                "-".join(prefix),
                                "-".join(w_a),
                                "-".join(w_b),
                            ))

    # --- Step 3: Significance filtering ---
    # Count final-position frequencies for expected calculation
    final_freq: Dict[str, int] = defaultdict(int)
    total_final = 0
    for insc in corpus.inscriptions:
        for word in insc.words:
            sids = word.sign_ids
            if len(sids) >= 2:
                final_freq[sids[-1]] += 1
                total_final += 1

    # Number of distinct prefixes with ≥ 2 continuations
    # (approximation for the null model)
    n_prefix_groups = sum(1 for stems in pair_stems.values() if len(stems) >= 1)

    all_pairs: List[AlternationPair] = []
    significant_pairs: List[AlternationPair] = []

    for pair_key, stems in pair_stems.items():
        signs = sorted(pair_key)
        if len(signs) != 2:
            continue
        sign_a, sign_b = signs

        n_stems = len(stems)

        # Expected by chance: probability that both signs appear as final sign
        # of words sharing a random prefix
        p_a = final_freq.get(sign_a, 0) / total_final if total_final > 0 else 0
        p_b = final_freq.get(sign_b, 0) / total_final if total_final > 0 else 0

        # Expected number of co-occurrences under independence
        # (rough estimate — each prefix has ~k continuations, probability both
        # a and b appear is p_a * p_b * n_prefix_groups)
        expected = p_a * p_b * n_prefix_groups * 2  # factor of 2 for symmetry

        # Poisson test: P(X >= n_stems | lambda = expected)
        if expected > 0:
            p_value = sp_stats.poisson.sf(n_stems - 1, expected)
        else:
            p_value = 0.0 if n_stems > 0 else 1.0

        is_significant = (n_stems >= min_independent_stems and
                          p_value < alternation_alpha)

        pair = AlternationPair(
            sign_a=sign_a,
            sign_b=sign_b,
            independent_stems=n_stems,
            stem_examples=pair_examples[pair_key][:5],  # Keep up to 5 examples
            expected_by_chance=expected,
            p_value=p_value,
            significant=is_significant,
        )
        all_pairs.append(pair)
        if is_significant:
            significant_pairs.append(pair)

    # --- Step 4: Build affinity matrix ---
    # Collect all sign IDs that appear in any pair
    all_sign_ids = set()
    for pair in significant_pairs:
        all_sign_ids.add(pair.sign_a)
        all_sign_ids.add(pair.sign_b)

    # Also add signs that appear in positional records (so the grid covers all signs)
    for rec in corpus.positional_records:
        all_sign_ids.add(rec.sign_id)

    sign_ids_sorted = sorted(all_sign_ids)
    sign_id_to_idx = {sid: i for i, sid in enumerate(sign_ids_sorted)}
    idx_to_sign_id = {i: sid for sid, i in sign_id_to_idx.items()}

    n = len(sign_ids_sorted)
    affinity = np.zeros((n, n), dtype=np.float64)

    for pair in significant_pairs:
        i = sign_id_to_idx[pair.sign_a]
        j = sign_id_to_idx[pair.sign_b]
        affinity[i, j] = pair.independent_stems
        affinity[j, i] = pair.independent_stems

    return AlternationResult(
        all_pairs=all_pairs,
        significant_pairs=significant_pairs,
        affinity_matrix=affinity,
        sign_id_to_index=sign_id_to_idx,
        index_to_sign_id=idx_to_sign_id,
        total_prefix_groups=n_prefix_groups,
        total_candidate_pairs=len(all_pairs),
        total_significant_pairs=len(significant_pairs),
    )
