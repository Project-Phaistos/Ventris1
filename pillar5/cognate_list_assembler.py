"""Pillar 5 Step 5+7: Multi-language search and cognate list assembly.

The PRIMARY DELIVERABLE of Pillar 5: per-stem cognate word lists where
each Linear A stem has a ranked list of possible cognate words from one
or more languages, each with evidence chains and confidence.

Step 5 (PRD Section 5.5): Simultaneous search across ALL candidate languages.
Step 7 (PRD Section 5.7): Final cognate list assembly with cross-reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constraint_assembler import SignGroupConstraints, ConstrainedVocabulary
from .lexicon_loader import CandidateLexicon, LexiconEntry
from .semantic_scorer import score_semantic_compatibility
from .evidence_combiner import (
    CandidateMatch,
    SignGroupMatches,
    combine_evidence,
    normalize_scores,
)


def _normalized_edit_distance(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein edit distance between two IPA strings.

    Returns a value in [0, 1] where 0 = identical, 1 = completely different.
    This is used as a FALLBACK when PP results are not available.
    """
    if not s1 or not s2:
        return 1.0
    if s1 == s2:
        return 0.0

    n, m = len(s1), len(s2)
    dp = list(range(m + 1))

    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(dp[j], dp[j - 1], prev)
            prev = temp

    return dp[m] / max(n, m)


def search_all_languages(
    constrained_vocab: ConstrainedVocabulary,
    lexicons: Dict[str, CandidateLexicon],
    pp_matches: Optional[Dict[str, Dict[str, Any]]] = None,
    min_match_threshold: float = 0.0,
    max_per_language: int = 5,
    max_edit_distance: float = 0.7,
) -> List[SignGroupMatches]:
    """Search all candidate languages simultaneously for each sign-group.

    For each constrained sign-group, searches every candidate language's
    lexicon for words within phonological distance, scores semantic
    compatibility, and produces ranked match lists.

    Args:
        constrained_vocab: Filtered vocabulary from constraint_assembler
        lexicons: Loaded candidate lexicons
        pp_matches: PP production run results indexed by language (if available)
        min_match_threshold: Minimum combined score to keep
        max_per_language: Maximum matches per language per sign-group
        max_edit_distance: Maximum normalized edit distance for a candidate

    Returns:
        List of SignGroupMatches, one per constrained sign-group.
    """
    all_results: List[SignGroupMatches] = []

    for sg in constrained_vocab.sign_groups:
        # Skip if no phonetic reading available
        stem_ipa = sg.stem_ipa_lb
        if stem_ipa is None:
            # Still include but with empty matches
            all_results.append(SignGroupMatches(
                sign_group_ids=sg.sign_group_ids,
                stem_ipa_lb=None,
                semantic_field=sg.semantic_field,
            ))
            continue

        # Search across ALL candidate languages simultaneously
        candidate_matches: List[Dict[str, Any]] = []

        for lang_code, lexicon in lexicons.items():
            # Compute phonological distances
            distances = []
            entries_with_dist: List[tuple] = []

            for entry in lexicon.entries:
                dist = _normalized_edit_distance(stem_ipa, entry.ipa)
                if dist <= max_edit_distance:
                    distances.append(1.0 - dist)  # Convert distance to score
                    entries_with_dist.append((entry, dist))

            if not entries_with_dist:
                continue

            # Normalize scores within this language
            raw_scores = [1.0 - d for _, d in entries_with_dist]
            norm_scores = normalize_scores(raw_scores)

            for (entry, dist), norm_score in zip(entries_with_dist, norm_scores):
                sem_compat = score_semantic_compatibility(
                    sg.semantic_field, entry.gloss
                )

                candidate_matches.append({
                    "language_code": lang_code,
                    "language_name": lexicon.language_name,
                    "word": entry.word,
                    "ipa": entry.ipa,
                    "gloss": entry.gloss,
                    "phonological_distance": round(dist, 4),
                    "phonological_score": norm_score,
                    "semantic_compatibility": sem_compat,
                    "evidence_provenance": sg.evidence_provenance,
                })

        # Determine semantic provenance
        sem_provenance = "CONSENSUS_DEPENDENT"
        if sg.semantic_field and "FUNCTION" in sg.semantic_field:
            sem_provenance = "CONSENSUS_CONFIRMED"
        elif sg.semantic_field and "PLACE" in sg.semantic_field:
            sem_provenance = "CONSENSUS_ASSUMED"

        # Combine evidence and score
        sgm = combine_evidence(
            sign_group_ids=sg.sign_group_ids,
            stem_ipa_lb=stem_ipa,
            semantic_field=sg.semantic_field,
            semantic_provenance=sem_provenance,
            candidate_matches=candidate_matches,
            min_match_threshold=min_match_threshold,
            max_per_language=max_per_language,
        )
        all_results.append(sgm)

    return all_results


def cross_reference_old_cognates(
    matches: List[SignGroupMatches],
    old_cognate_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Cross-reference new results against old raw cognate TSV files.

    This does NOT affect scores — purely informational provenance audit.

    Returns:
        Dict with corroboration stats.
    """
    if old_cognate_dir is None:
        return {
            "status": "skipped",
            "reason": "No old cognate directory specified",
        }

    from pathlib import Path
    import csv

    old_dir = Path(old_cognate_dir)
    if not old_dir.exists():
        return {
            "status": "skipped",
            "reason": f"Directory not found: {old_dir}",
        }

    # Load old cognate files
    old_words: Dict[str, set] = {}  # lang -> set of known words
    for tsv_path in old_dir.glob("cognates_*.tsv"):
        lang = tsv_path.stem.replace("cognates_", "")
        words = set()
        try:
            with open(tsv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    known = row.get("known", "").strip()
                    if known:
                        words.add(known)
        except Exception:
            continue
        old_words[lang] = words

    # Cross-reference
    n_corroborated = 0
    n_new_only = 0
    n_old_only = 0

    new_words_by_lang: Dict[str, set] = {}
    for sgm in matches:
        for m in sgm.matches:
            lang = m.language_code
            if lang not in new_words_by_lang:
                new_words_by_lang[lang] = set()
            new_words_by_lang[lang].add(m.word)

    for lang in set(list(old_words.keys()) + list(new_words_by_lang.keys())):
        old_set = old_words.get(lang, set())
        new_set = new_words_by_lang.get(lang, set())
        n_corroborated += len(old_set & new_set)
        n_new_only += len(new_set - old_set)
        n_old_only += len(old_set - new_set)

    return {
        "status": "completed",
        "n_corroborated": n_corroborated,
        "n_new_findings": n_new_only,
        "n_old_only": n_old_only,
        "note": "Cross-reference is informational only — does not affect scores",
    }
