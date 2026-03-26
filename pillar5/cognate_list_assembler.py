"""Pillar 5 Step 5+7: Multi-language search and cognate list assembly.

The PRIMARY DELIVERABLE of Pillar 5: per-substring cognate word lists where
each Linear A substring hypothesis has a ranked list of possible cognate
words from one or more languages, each with evidence chains and confidence.

CRITICAL: Linear A is UNSEGMENTED.  We do NOT know where words start and
end.  The Phonetic Prior algorithm evaluates ALL possible substrings of
the unsegmented text.  Each entry is a HYPOTHESIS: "if this substring is
a word, its best cognate in Language X is Y with score Z."  These
progressive-scan results are the correct output, not a flaw.

Step 5 (PRD Section 5.5): Iterate over PP substrings across all languages.
Step 7 (PRD Section 5.7): Final cognate list assembly with cross-reference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from .constraint_assembler import ConstrainedVocabulary, SignGroupConstraints
from .lexicon_loader import CandidateLexicon, LexiconEntry
from .pp_result_loader import PPLanguageResults, PPSubstringMatch, find_p2_convergence
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

    BACKWARD-COMPATIBLE FALLBACK: Uses edit-distance matching when PP
    fleet results are not available.  For PP-based search, use
    ``search_from_pp_results()`` instead.

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
            entries_with_dist: List[tuple] = []

            for entry in lexicon.entries:
                dist = _normalized_edit_distance(stem_ipa, entry.ipa)
                if dist <= max_edit_distance:
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


def _build_p2_sign_groups_set(
    constrained_vocab: ConstrainedVocabulary,
) -> Set[str]:
    """Build a set of P2 sign-group strings for convergence checking.

    Converts each sign-group's sign_group_ids (e.g. ["a", "da", "ki"])
    into the hyphenated form used by PP results (e.g. "a-da-ki").
    """
    p2_set: Set[str] = set()
    for sg in constrained_vocab.sign_groups:
        # Join sign IDs with hyphens to match PP notation
        sign_str = "-".join(sg.sign_group_ids)
        p2_set.add(sign_str)
    return p2_set


def load_supplementary_glosses(
    gloss_dir: str,
) -> Dict[str, Dict[str, str]]:
    """Load supplementary gloss TSVs extracted from academic sources.

    These TSVs (from eDiAna, IDS, eCUT) have format:
        word\\ttranslation\\tsource\\tsource_url

    Returns:
        Dict[lang_code -> Dict[word -> translation]]
        Language is inferred from filename pattern.
    """
    import csv
    from pathlib import Path

    gloss_dir = Path(gloss_dir)
    if not gloss_dir.exists():
        return {}

    # Map filename patterns to language codes
    file_lang_map = {
        "ediana_lydian": "xld",
        "ids_elamite": "elx",
        "ecut_urartian": "xur",
    }

    result: Dict[str, Dict[str, str]] = {}
    for tsv_path in gloss_dir.glob("*_glosses.tsv"):
        # Determine language from filename
        lang_code = None
        for pattern, code in file_lang_map.items():
            if pattern in tsv_path.stem:
                lang_code = code
                break
        if lang_code is None:
            continue

        word_to_gloss: Dict[str, str] = {}
        with open(tsv_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or line.startswith("word\t"):
                    continue
                parts = line.strip().split("\t")
                if len(parts) >= 2 and parts[0] and parts[1]:
                    word_to_gloss[parts[0]] = parts[1]

        result[lang_code] = word_to_gloss

    return result


# Module-level cache for supplementary glosses
_supplementary_glosses: Optional[Dict[str, Dict[str, str]]] = None


def _lookup_gloss(
    matched_word: str,
    lang_code: str,
    lexicons: Dict[str, CandidateLexicon],
) -> Optional[str]:
    """Look up the English gloss for a matched word in its language's lexicon.

    Checks the main lexicon first, then supplementary glosses from
    academic extractions (eDiAna, IDS, eCUT).

    Args:
        matched_word: The target-language word from the PP result.
        lang_code: The language code (e.g. "hit", "uga").
        lexicons: All loaded candidate lexicons.

    Returns:
        The English gloss string, or None if not found.
    """
    # Check main lexicon first
    lexicon = lexicons.get(lang_code)
    if lexicon is not None:
        for entry in lexicon.entries:
            if entry.word == matched_word or entry.ipa == matched_word:
                return entry.gloss

    # Check supplementary glosses (eDiAna, IDS, eCUT)
    if _supplementary_glosses is not None:
        lang_glosses = _supplementary_glosses.get(lang_code, {})
        if matched_word in lang_glosses:
            return lang_glosses[matched_word]
        # Try partial match: PP matched words may have suffixes/prefixes
        # that differ from dictionary headwords
        for headword, gloss in lang_glosses.items():
            if matched_word.startswith(headword.rstrip("-")) or headword.rstrip("-").startswith(matched_word):
                return gloss

    return None


def search_from_pp_results(
    pp_results: Dict[str, PPLanguageResults],
    constrained_vocab: ConstrainedVocabulary,
    lexicons: Dict[str, CandidateLexicon],
    min_per_char_score: float = -3.0,
    max_per_language: int = 5,
    min_match_threshold: float = 0.0,
) -> List[SignGroupMatches]:
    """Search all languages using pre-computed PP fleet results.

    Instead of computing edit distances against lexicons on the fly, this
    function iterates over the PP progressive-scan results.  Each unique
    Linear A substring is treated as a word-boundary hypothesis.

    For each substring:
    1. Collect its PP scores across all 18 languages.
    2. Filter by min_per_char_score (score / ipa_length).
    3. Normalize per-char scores to [0, 1] via min-max across languages.
    4. Look up matched words in lexicons for glosses (semantic scoring).
    5. Cross-reference against P2 segments for convergent evidence.
    6. Combine phonological + semantic scores via evidence_combiner.

    Args:
        pp_results: Dict[lang_code -> PPLanguageResults] from load_fleet_results.
        constrained_vocab: P2 constrained vocabulary (used for convergence check).
        lexicons: Loaded candidate lexicons (used for gloss lookup).
        min_per_char_score: Minimum per-character score to keep a match.
            PP scores are log-likelihoods (negative), so this is a floor
            (e.g. -3.0 filters out very poor alignments).
        max_per_language: Maximum matches per language per substring.
        min_match_threshold: Minimum combined score to keep after evidence
            combination.

    Returns:
        List of SignGroupMatches, one per unique PP substring.
        Sorted by number of matches descending (most-matched substrings first).
    """
    if not pp_results:
        return []

    # Build P2 sign-group set for convergence checking
    p2_sign_groups = _build_p2_sign_groups_set(constrained_vocab)

    # Build P4 semantic anchor index: hyphenated sign string -> semantic field
    p4_anchor_index: Dict[str, str] = {}
    for sg in constrained_vocab.sign_groups:
        if sg.semantic_field:
            anchor_str = "-".join(sg.sign_group_ids)
            p4_anchor_index[anchor_str] = sg.semantic_field

    # Collect all unique substrings across all languages.
    # Each substring appears once per language in the PP fleet output.
    all_signs: Set[str] = set()
    for lang_results in pp_results.values():
        all_signs.update(lang_results.unique_signs())

    # For each unique substring, gather cross-language evidence
    all_results: List[SignGroupMatches] = []

    for signs_str in sorted(all_signs):
        # Collect per-char scores across all languages for this substring
        per_lang_entries: Dict[str, PPSubstringMatch] = {}
        per_char_scores: List[float] = []

        for lang_code, lang_results in pp_results.items():
            entries = lang_results.by_signs(signs_str)
            if not entries:
                continue
            # Take the best entry for this substring in this language
            best = max(entries, key=lambda e: e.score)
            if best.per_char_score < min_per_char_score:
                continue
            per_lang_entries[lang_code] = best
            per_char_scores.append(best.per_char_score)

        if not per_lang_entries:
            continue

        # Normalize per-char scores to [0, 1] across languages
        norm_scores = normalize_scores(per_char_scores)
        lang_codes_ordered = list(per_lang_entries.keys())
        norm_map = dict(zip(lang_codes_ordered, norm_scores))

        # Get the IPA reading from the first entry (same across languages)
        first_entry = next(iter(per_lang_entries.values()))
        linear_a_ipa = first_entry.linear_a_ipa

        # Check for P2 convergent evidence
        has_p2_convergence = find_p2_convergence(signs_str, p2_sign_groups)

        # Build candidate matches for evidence_combiner
        candidate_matches: List[Dict[str, Any]] = []

        for lang_code, pp_entry in per_lang_entries.items():
            phon_score = norm_map[lang_code]

            # Look up gloss in lexicon for semantic scoring
            gloss = _lookup_gloss(pp_entry.matched_word, lang_code, lexicons)

            # Semantic compatibility: check if any P4 anchor is contained
            # within this PP substring (exact match or substring containment).
            # PP scans are progressive and may extend through known words.
            semantic_field = None
            if signs_str in p4_anchor_index:
                semantic_field = p4_anchor_index[signs_str]
            else:
                # Check if any P4 anchor is a substring of this PP entry
                for anchor_signs, anchor_field in p4_anchor_index.items():
                    if anchor_signs in signs_str:
                        semantic_field = anchor_field
                        break

            sem_compat = score_semantic_compatibility(semantic_field, gloss)

            # Language name from lexicon metadata, fallback to code
            lang_name = lang_code
            if lang_code in lexicons:
                lang_name = lexicons[lang_code].language_name

            # Evidence provenance: higher if P2 convergent
            if has_p2_convergence:
                evidence_prov = "CONSENSUS_CONFIRMED"
            else:
                evidence_prov = "CONSENSUS_ASSUMED"

            candidate_matches.append({
                "language_code": lang_code,
                "language_name": lang_name,
                "word": pp_entry.matched_word,
                "ipa": pp_entry.linear_a_ipa,
                "gloss": gloss,
                "phonological_distance": None,
                "phonological_score": phon_score,
                "semantic_compatibility": sem_compat,
                "evidence_provenance": evidence_prov,
                "pp_raw_score": pp_entry.score,
                "pp_per_char_score": pp_entry.per_char_score,
                "pp_top3": pp_entry.top3,
                "p2_convergent": has_p2_convergence,
            })

        # Determine semantic provenance from the best available info
        sem_provenance = "CONSENSUS_DEPENDENT"
        if has_p2_convergence:
            sem_provenance = "CONSENSUS_CONFIRMED"

        # Use the sign string split by hyphens as the sign_group_ids
        sign_group_ids = signs_str.split("-")

        # Combine evidence and score
        sgm = combine_evidence(
            sign_group_ids=sign_group_ids,
            stem_ipa_lb=linear_a_ipa,
            semantic_field=None,  # substring-level; semantic from per-match
            semantic_provenance=sem_provenance,
            candidate_matches=candidate_matches,
            min_match_threshold=min_match_threshold,
            max_per_language=max_per_language,
        )

        all_results.append(sgm)

    # Sort by number of matches descending, then alphabetically for stability
    all_results.sort(
        key=lambda sgm: (-sgm.n_matches, "|".join(sgm.sign_group_ids))
    )

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
