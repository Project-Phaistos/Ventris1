"""Syllable-constrained segmentation for Linear A lexicon.

Implements PRD Section 5.1: Decomposes words into stems and affixes,
respecting Pillar 1's phonotactic constraints.

Given the tiny corpus (834 unique words, average 2.51 signs), the primary
method is suffix-stripping — the simplest approach that can work on this
data. BPE is provided as an alternative.

Sign IDs are AB codes (e.g., "AB59", "AB06").
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from pillar1.corpus_loader import CorpusData, Inscription, Word
from .pillar1_loader import Pillar1Output


@dataclass
class SegmentedWord:
    """A word decomposed into stem + affixes."""
    word_sign_ids: List[str]
    stem: List[str]
    suffixes: List[List[str]]
    prefixes: List[List[str]]
    segmentation_confidence: float
    frequency: int
    inscription_types: List[str]
    method: str


@dataclass
class SegmentedLexicon:
    """The full segmented lexicon."""
    words: List[SegmentedWord]
    # Diagnostics
    total_words: int = 0
    words_with_suffixes: int = 0
    words_unsegmented: int = 0


def segment_corpus(
    corpus: CorpusData,
    pillar1: Pillar1Output,
    method: str = "suffix_strip",
    min_word_length: int = 2,
    min_suffix_frequency: int = 3,
    min_suffix_stems: int = 2,
    max_suffix_length: int = 3,
    lambda_phon: float = 1.0,
    bpe_min_merge_freq: int = 3,
    bpe_max_merges: int = 100,
) -> SegmentedLexicon:
    """Segment the corpus into stems and affixes.

    Args:
        corpus: The loaded corpus data.
        pillar1: Pillar 1 output with phonotactic constraints.
        method: Segmentation method — "suffix_strip" or "bpe".
        min_word_length: Minimum signs for a word to be segmented.
        min_suffix_frequency: Minimum corpus occurrences for a suffix.
        min_suffix_stems: Minimum distinct stems for a suffix to be retained.
        max_suffix_length: Maximum suffix length in signs.
        lambda_phon: Phonological constraint penalty weight.
        bpe_min_merge_freq: Minimum frequency for a BPE merge.
        bpe_max_merges: Maximum number of BPE merges.

    Returns:
        SegmentedLexicon with all words decomposed.
    """
    # Collect unique words with their frequencies and inscription types
    word_info = _collect_word_info(corpus, min_word_length)

    if method == "suffix_strip":
        segmented = _suffix_strip_segment(
            word_info=word_info,
            pillar1=pillar1,
            min_suffix_frequency=min_suffix_frequency,
            min_suffix_stems=min_suffix_stems,
            max_suffix_length=max_suffix_length,
            lambda_phon=lambda_phon,
        )
    elif method == "bpe":
        segmented = _bpe_segment(
            word_info=word_info,
            pillar1=pillar1,
            bpe_min_merge_freq=bpe_min_merge_freq,
            bpe_max_merges=bpe_max_merges,
            lambda_phon=lambda_phon,
        )
    else:
        raise ValueError(f"Unknown segmentation method: {method!r}. "
                         f"Use 'suffix_strip' or 'bpe'.")

    # Build lexicon
    words_with_suf = sum(1 for w in segmented if w.suffixes)
    words_unseg = sum(1 for w in segmented if not w.suffixes and not w.prefixes)

    return SegmentedLexicon(
        words=segmented,
        total_words=len(segmented),
        words_with_suffixes=words_with_suf,
        words_unsegmented=words_unseg,
    )


# ---------------------------------------------------------------------------
# Internal: Word collection
# ---------------------------------------------------------------------------

@dataclass
class _WordInfo:
    """Internal word info for segmentation."""
    sign_ids: Tuple[str, ...]
    frequency: int
    inscription_types: List[str]


def _collect_word_info(
    corpus: CorpusData,
    min_word_length: int,
) -> Dict[Tuple[str, ...], _WordInfo]:
    """Collect unique words with frequency and inscription types."""
    info: Dict[Tuple[str, ...], _WordInfo] = {}

    for insc in corpus.inscriptions:
        for word in insc.words:
            sids = tuple(word.sign_ids)
            if len(sids) < min_word_length:
                continue
            if sids not in info:
                info[sids] = _WordInfo(
                    sign_ids=sids,
                    frequency=0,
                    inscription_types=[],
                )
            info[sids].frequency += 1
            if insc.type not in info[sids].inscription_types:
                info[sids].inscription_types.append(insc.type)

    return info


# ---------------------------------------------------------------------------
# Method 1: Suffix stripping
# ---------------------------------------------------------------------------

def _suffix_strip_segment(
    word_info: Dict[Tuple[str, ...], _WordInfo],
    pillar1: Pillar1Output,
    min_suffix_frequency: int,
    min_suffix_stems: int,
    max_suffix_length: int,
    lambda_phon: float,
) -> List[SegmentedWord]:
    """Segment words by identifying productive suffixes.

    Algorithm:
    1. For each suffix length (1, 2, ...):
       - Collect all final sign sequences and the distinct stems they appear with
       - A sequence qualifies as a suffix if it meets frequency and stem thresholds
    2. For each word, try to strip the longest matching suffix
    3. Check Pillar 1 constraints at the boundary
    """
    # --- Step 1: Discover suffixes ---
    # suffix_candidate -> set of stems (word[:-suffix_len])
    suffix_stems: Dict[Tuple[str, ...], Set[Tuple[str, ...]]] = defaultdict(set)
    suffix_freq: Dict[Tuple[str, ...], int] = defaultdict(int)

    for word_sids, winfo in word_info.items():
        for suf_len in range(1, min(max_suffix_length, len(word_sids)) + 1):
            if len(word_sids) - suf_len < 1:
                # Stem must have at least 1 sign
                continue
            suffix = word_sids[-suf_len:]
            stem = word_sids[:-suf_len]
            suffix_stems[suffix].add(stem)
            suffix_freq[suffix] += winfo.frequency

    # Filter: keep suffixes that meet both frequency and stem count thresholds
    valid_suffixes: Dict[Tuple[str, ...], int] = {}
    for suffix, stems in suffix_stems.items():
        n_stems = len(stems)
        freq = suffix_freq[suffix]
        if n_stems >= min_suffix_stems and freq >= min_suffix_frequency:
            valid_suffixes[suffix] = n_stems

    # --- Step 2: Segment each word ---
    segmented: List[SegmentedWord] = []

    for word_sids, winfo in sorted(word_info.items()):
        best_suffix: Optional[Tuple[str, ...]] = None
        best_score = -1.0

        # Try longest suffix first (greedy)
        for suf_len in range(min(max_suffix_length, len(word_sids) - 1), 0, -1):
            candidate = word_sids[-suf_len:]
            if candidate not in valid_suffixes:
                continue

            stem_part = word_sids[:-suf_len]

            # Check Pillar 1 constraints at the boundary
            if not _check_boundary(stem_part, candidate, pillar1, lambda_phon):
                continue

            # Score: prefer longer suffixes with more stems, penalize boundary violations
            n_stems = valid_suffixes[candidate]
            score = n_stems * (1.0 + 0.1 * suf_len)
            if score > best_score:
                best_score = score
                best_suffix = candidate

        if best_suffix is not None:
            stem = list(word_sids[:-len(best_suffix)])
            suffixes = [list(best_suffix)]
            # Confidence based on number of distinct stems for this suffix
            n_stems = valid_suffixes[best_suffix]
            confidence = min(1.0, n_stems / 10.0)
        else:
            stem = list(word_sids)
            suffixes = []
            confidence = 0.0

        segmented.append(SegmentedWord(
            word_sign_ids=list(word_sids),
            stem=stem,
            suffixes=suffixes,
            prefixes=[],
            segmentation_confidence=confidence,
            frequency=winfo.frequency,
            inscription_types=winfo.inscription_types,
            method="suffix_strip",
        ))

    return segmented


def _check_boundary(
    stem: Tuple[str, ...],
    suffix: Tuple[str, ...],
    pillar1: Pillar1Output,
    lambda_phon: float,
) -> bool:
    """Check if a segmentation boundary is valid given Pillar 1 constraints.

    Returns False if:
    - The boundary creates a forbidden bigram (stem[-1], suffix[0])
    - The boundary splits within a favored bigram
    """
    if not stem or not suffix:
        return True

    boundary_pair = (stem[-1], suffix[0])

    # Forbidden bigram at boundary: reject
    if boundary_pair in pillar1.forbidden_bigram_set:
        return False

    # Favored bigram at boundary: this means the boundary SPLITS a
    # favored pair — reject (don't segment within a favored collocation)
    if boundary_pair in pillar1.favored_bigram_set:
        return False

    return True


# ---------------------------------------------------------------------------
# Method 2: BPE (reverse — find common pairs, split at non-common boundaries)
# ---------------------------------------------------------------------------

def _bpe_segment(
    word_info: Dict[Tuple[str, ...], _WordInfo],
    pillar1: Pillar1Output,
    bpe_min_merge_freq: int,
    bpe_max_merges: int,
    lambda_phon: float,
) -> List[SegmentedWord]:
    """Segment using reverse BPE.

    Standard BPE merges the most frequent pair. Reverse BPE:
    1. Count all adjacent sign pairs and their frequencies.
    2. Sort pairs by frequency (descending) — high-frequency pairs are
       likely within-morpheme.
    3. For each word, segment at positions where adjacent pair frequency
       is below a threshold.

    This identifies morpheme boundaries as the "weak links" in sign sequences.
    """
    # Count pair frequencies (weighted by word frequency)
    pair_freq: Dict[Tuple[str, str], int] = defaultdict(int)
    for word_sids, winfo in word_info.items():
        for i in range(len(word_sids) - 1):
            pair = (word_sids[i], word_sids[i + 1])
            pair_freq[pair] += winfo.frequency

    # Find the merge threshold: top N pairs by frequency
    sorted_pairs = sorted(pair_freq.items(), key=lambda x: -x[1])
    merged_pairs: Set[Tuple[str, str]] = set()

    for pair, freq in sorted_pairs[:bpe_max_merges]:
        if freq < bpe_min_merge_freq:
            break
        # Don't merge across forbidden bigrams
        if pair in pillar1.forbidden_bigram_set:
            continue
        merged_pairs.add(pair)

    # For each word, find boundaries where adjacent pair is NOT in merged_pairs
    segmented: List[SegmentedWord] = []

    for word_sids, winfo in sorted(word_info.items()):
        if len(word_sids) < 2:
            segmented.append(SegmentedWord(
                word_sign_ids=list(word_sids),
                stem=list(word_sids),
                suffixes=[],
                prefixes=[],
                segmentation_confidence=0.0,
                frequency=winfo.frequency,
                inscription_types=winfo.inscription_types,
                method="bpe",
            ))
            continue

        # Find split points
        splits: List[int] = []  # indices where we split AFTER position i
        for i in range(len(word_sids) - 1):
            pair = (word_sids[i], word_sids[i + 1])
            # Split if pair is NOT commonly merged AND not a favored bigram
            if pair not in merged_pairs and pair not in pillar1.favored_bigram_set:
                splits.append(i + 1)

        if not splits:
            # No splits — whole word is stem
            segmented.append(SegmentedWord(
                word_sign_ids=list(word_sids),
                stem=list(word_sids),
                suffixes=[],
                prefixes=[],
                segmentation_confidence=0.0,
                frequency=winfo.frequency,
                inscription_types=winfo.inscription_types,
                method="bpe",
            ))
        else:
            # Split into morphemes; first morpheme is stem, rest are suffixes
            morphemes: List[List[str]] = []
            prev = 0
            for sp in splits:
                morphemes.append(list(word_sids[prev:sp]))
                prev = sp
            morphemes.append(list(word_sids[prev:]))

            # Stem = longest morpheme (heuristic: stems are longer than affixes)
            stem_idx = max(range(len(morphemes)), key=lambda i: len(morphemes[i]))
            stem = morphemes[stem_idx]
            prefixes = morphemes[:stem_idx] if stem_idx > 0 else []
            suffixes = morphemes[stem_idx + 1:] if stem_idx < len(morphemes) - 1 else []

            confidence = min(1.0, len(splits) * 0.3)

            segmented.append(SegmentedWord(
                word_sign_ids=list(word_sids),
                stem=stem,
                suffixes=suffixes,
                prefixes=prefixes,
                segmentation_confidence=confidence,
                frequency=winfo.frequency,
                inscription_types=winfo.inscription_types,
                method="bpe",
            ))

    return segmented
