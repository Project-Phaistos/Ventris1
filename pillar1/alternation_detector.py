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
    weighted_stems: float    # Sum of weights (1.0 for diff_len=1, 0.5 for diff_len=2)
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
    min_shared_prefix_length: int = 2,
    max_suffix_diff_length: int = 2,
    min_independent_stems: int = 2,
    alternation_alpha: float = 0.01,
) -> AlternationResult:
    """Detect inflectional alternation pairs (Kober's triplets).

    Algorithm (PRD Section 5.3):
    1. Find all sign-group pairs sharing a prefix of length >= min_shared_prefix_length,
       differing in the last max_suffix_diff_length signs.
    2. Count independent stems per alternation pair.
    3. Filter by significance (Poisson test vs. chance co-occurrence).
    4. Build same-consonant affinity matrix.

    NOTE (2026-04-03): Default min_shared_prefix_length raised from 1 to 2.
    With prefix=1, 2-sign groups contribute "alternation" evidence when they are
    just different sign-groups sharing an initial syllable (not a stem). This
    produced 610 pairs indistinguishable from a shuffled corpus (609 mean).
    With prefix=2, sign-groups must be >= 3 signs to contribute evidence,
    ensuring the shared prefix is at least a 2-sign stem.

    Args:
        corpus: Processed corpus data.
        min_shared_prefix_length: Minimum shared prefix length in signs.
            Default 2 requires >= 3-sign groups for evidence (genuine stems).
            Use 1 for legacy behavior (includes 2-sign groups, mostly artifacts).
        max_suffix_diff_length: Maximum differing suffix length (1 or 2).
            When 2, only the FINAL-position pair is extracted (penultimate
            position differences are stem changes, not suffix alternations).
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
    # Track weight per (pair_key, prefix) — diff_len=1 has weight 1.0, diff_len=2 has weight 0.5
    pair_stem_weights: Dict[frozenset, Dict[Tuple[str, ...], float]] = defaultdict(
        lambda: defaultdict(float)
    )

    # Count distinct prefixes with >= 2 continuations (for null model)
    n_branching_prefixes = 0

    for diff_len in range(1, max_suffix_diff_length + 1):
        prefix_groups: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = defaultdict(list)

        for word in word_list:
            if len(word) < min_shared_prefix_length + diff_len:
                continue
            prefix = word[:-diff_len]
            if len(prefix) >= min_shared_prefix_length:
                prefix_groups[prefix].append(word)

        # Count prefixes with >= 2 words (branching prefixes) for null model
        n_branching_prefixes += sum(
            1 for words_in_group in prefix_groups.values()
            if len(words_in_group) >= 2
        )

        # For each prefix group with 2+ words, extract alternation pairs
        for prefix, words_in_group in prefix_groups.items():
            if len(words_in_group) < 2:
                continue

            # Determine weight based on diff_len
            weight = 1.0 if diff_len == 1 else 0.5

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
                            pair_stem_weights[pair_key][prefix] = max(
                                pair_stem_weights[pair_key][prefix], weight,
                            )
                            pair_examples[pair_key].append((
                                "-".join(prefix),
                                "-".join(w_a),
                                "-".join(w_b),
                            ))
                    elif diff_len == 2:
                        # Two sign difference — only the FINAL position pair
                        # is a genuine suffix alternation. The penultimate
                        # pair (a1 vs b1) is a stem-position difference, NOT
                        # suffix alternation evidence.
                        # (2026-04-03 fix: previously both pairs were kept,
                        # inflating pair count with stem-position artifacts.)
                        a2 = w_a[-1]
                        b2 = w_b[-1]

                        if a2 != b2:
                            pk2 = frozenset({a2, b2})
                            pair_stems[pk2].add(prefix)
                            pair_stem_weights[pk2][prefix] = max(
                                pair_stem_weights[pk2][prefix], weight,
                            )
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

    # Number of distinct prefixes with >= 2 continuations (branching prefixes)
    # used in the null model for expected co-occurrence calculation.
    # n_branching_prefixes was accumulated in the loop above.

    all_pairs: List[AlternationPair] = []
    significant_pairs: List[AlternationPair] = []

    for pair_key, stems in pair_stems.items():
        signs = sorted(pair_key)
        if len(signs) != 2:
            continue
        sign_a, sign_b = signs

        n_stems = len(stems)
        # Weighted stem count: sum of weights per prefix
        w_stems = sum(pair_stem_weights[pair_key].values())

        # Expected by chance: probability that both signs appear as final sign
        # of words sharing a random prefix
        p_a = final_freq.get(sign_a, 0) / total_final if total_final > 0 else 0
        p_b = final_freq.get(sign_b, 0) / total_final if total_final > 0 else 0

        # Expected number of co-occurrences under independence
        # E[w] = n_branching_prefixes * P(a in final) * P(b in final)
        # No symmetry factor: pairs are stored as frozensets (unordered)
        expected = p_a * p_b * n_branching_prefixes

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
            weighted_stems=w_stems,
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
        affinity[i, j] = pair.weighted_stems
        affinity[j, i] = pair.weighted_stems

    return AlternationResult(
        all_pairs=all_pairs,
        significant_pairs=significant_pairs,
        affinity_matrix=affinity,
        sign_id_to_index=sign_id_to_idx,
        index_to_sign_id=idx_to_sign_id,
        total_prefix_groups=n_branching_prefixes,
        total_candidate_pairs=len(all_pairs),
        total_significant_pairs=len(significant_pairs),
    )
