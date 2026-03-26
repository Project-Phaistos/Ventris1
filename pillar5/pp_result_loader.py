"""Pillar 5 Step 2 (partial): Load Phonetic Prior fleet production run results.

Loads per-language cognate match TSVs from the PP fleet output directory.
Each TSV contains progressive-scan results: every possible substring of
the unsegmented Linear A text evaluated against a candidate language's
lexicon using the Phonetic Prior algorithm (Luo, Cao, & Barzilay, ACL 2019).

Fleet data format (one file per language):
    linear_a_signs | linear_a_ipa | matched_word | score | top3_matches | ipa_length

Or combined file with an extra leading column:
    candidate_language | linear_a_signs | linear_a_ipa | matched_word | score | top3_matches | ipa_length

Each row is a hypothesis: "if this substring is a word, its best cognate
in language X is Y with score Z."  Scores are log-likelihoods (negative;
higher = better).

Data directory:
    C:\\Users\\alvin\\ancient-scripts-datasets\\data\\linear_a_cognates_clean\\

File naming:
    linear_a_vs_{lang_code}_clean.tsv   (per-language)
    all_languages_combined.tsv           (combined, with candidate_language col)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class PPSubstringMatch:
    """A single PP alignment result for one Linear A substring vs one language.

    Each entry records: if the substring `linear_a_signs` (with IPA reading
    `linear_a_ipa`) were a word, the best cognate in `candidate_language`
    would be `matched_word` with `score` (log-likelihood).
    """

    linear_a_signs: str          # e.g. "a-da-ki-si-ka"
    linear_a_ipa: str            # e.g. "adakisika"
    candidate_language: str      # e.g. "hit", "uga"
    matched_word: str            # best-match word from target lexicon
    score: float                 # PP log-likelihood (negative; higher = better)
    top3: List[Tuple[str, float]]  # [(word, score), ...] up to 3 entries
    ipa_length: int              # len(linear_a_ipa)
    per_char_score: float        # score / ipa_length (normalized for length)


@dataclass
class PPLanguageResults:
    """All PP results for a single candidate language.

    Provides O(1) lookup of entries by linear_a_signs or linear_a_ipa
    via pre-built indices.
    """

    language_code: str
    entries: List[PPSubstringMatch] = field(default_factory=list)

    # Indices built on first access (lazy) or via build_indices()
    _by_signs: Dict[str, List[PPSubstringMatch]] = field(
        default_factory=dict, repr=False
    )
    _by_ipa: Dict[str, List[PPSubstringMatch]] = field(
        default_factory=dict, repr=False
    )
    _indices_built: bool = field(default=False, repr=False)

    @property
    def n_entries(self) -> int:
        return len(self.entries)

    def build_indices(self) -> None:
        """Build lookup indices by linear_a_signs and linear_a_ipa."""
        self._by_signs.clear()
        self._by_ipa.clear()
        for entry in self.entries:
            self._by_signs.setdefault(entry.linear_a_signs, []).append(entry)
            self._by_ipa.setdefault(entry.linear_a_ipa, []).append(entry)
        self._indices_built = True

    def _ensure_indices(self) -> None:
        if not self._indices_built:
            self.build_indices()

    def by_signs(self, signs: str) -> List[PPSubstringMatch]:
        """Look up entries by linear_a_signs string (e.g. 'a-da')."""
        self._ensure_indices()
        return self._by_signs.get(signs, [])

    def by_ipa(self, ipa: str) -> List[PPSubstringMatch]:
        """Look up entries by linear_a_ipa string (e.g. 'ada')."""
        self._ensure_indices()
        return self._by_ipa.get(ipa, [])

    def unique_signs(self) -> Set[str]:
        """Return all unique linear_a_signs strings in this language's results."""
        self._ensure_indices()
        return set(self._by_signs.keys())


def _parse_top3(top3_str: str) -> List[Tuple[str, float]]:
    """Parse the top3_matches column into a list of (word, score) tuples.

    Format: "word1 (score1); word2 (score2); word3 (score3)"
    Examples:
        "mi\u02d0 (-15.42); \u0294ani\u02d0 (-15.47); pani (-15.47)"
        "\u0263r (-10.52); xrs\u0321\u02e4 (-11.68); xns\u0321\u02e4 (-11.68)"
    """
    results: List[Tuple[str, float]] = []
    if not top3_str or top3_str.strip() == "":
        return results

    # Split on semicolons, then parse each "word (score)" chunk
    for chunk in top3_str.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue

        # Find the last parenthesized group — the score is always last
        paren_match = re.search(r'\(([^)]+)\)\s*$', chunk)
        if paren_match:
            try:
                score = float(paren_match.group(1))
            except ValueError:
                continue
            word = chunk[:paren_match.start()].strip()
            results.append((word, score))

    return results


def load_fleet_results(
    cognate_dir: str | Path,
    languages: Optional[List[str]] = None,
) -> Dict[str, PPLanguageResults]:
    """Load PP fleet production run results from the cognate directory.

    Reads per-language TSV files (linear_a_vs_{lang}_clean.tsv) from
    `cognate_dir`.  Each file contains progressive-scan results: every
    possible substring of the unsegmented Linear A text matched against
    that language's lexicon.

    Args:
        cognate_dir: Directory containing linear_a_vs_{lang}_clean.tsv files.
        languages: Restrict to these language codes (None = load all found).

    Returns:
        Dict mapping language code -> PPLanguageResults.
        Returns empty dict if the directory does not exist.
    """
    cognate_dir = Path(cognate_dir)
    if not cognate_dir.exists():
        return {}

    results: Dict[str, PPLanguageResults] = {}

    for tsv_path in sorted(cognate_dir.glob("linear_a_vs_*_clean.tsv")):
        # Extract language code from filename: linear_a_vs_{lang}_clean.tsv
        lang_code = tsv_path.stem.replace("linear_a_vs_", "").replace("_clean", "")
        if not lang_code:
            continue
        if languages is not None and lang_code not in languages:
            continue

        lang_results = _load_single_language(tsv_path, lang_code)
        if lang_results is not None:
            results[lang_code] = lang_results

    return results


def _load_single_language(
    tsv_path: Path,
    lang_code: str,
) -> Optional[PPLanguageResults]:
    """Load a single per-language cognate TSV file.

    TSV header: linear_a_signs | linear_a_ipa | matched_word | score | top3_matches | ipa_length

    Returns:
        PPLanguageResults with all entries parsed and indices built,
        or None if the file could not be read.
    """
    entries: List[PPSubstringMatch] = []

    try:
        with open(tsv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                signs = row.get("linear_a_signs", "").strip()
                ipa = row.get("linear_a_ipa", "").strip()
                matched_word = row.get("matched_word", "").strip()
                score_str = row.get("score", "").strip()
                top3_str = row.get("top3_matches", "").strip()
                length_str = row.get("ipa_length", "").strip()

                if not signs or not ipa or not score_str:
                    continue

                try:
                    score = float(score_str)
                except ValueError:
                    continue

                try:
                    ipa_length = int(length_str) if length_str else len(ipa)
                except ValueError:
                    ipa_length = len(ipa)

                # Guard against division by zero
                per_char = score / ipa_length if ipa_length > 0 else score

                top3 = _parse_top3(top3_str)

                entries.append(PPSubstringMatch(
                    linear_a_signs=signs,
                    linear_a_ipa=ipa,
                    candidate_language=lang_code,
                    matched_word=matched_word,
                    score=score,
                    top3=top3,
                    ipa_length=ipa_length,
                    per_char_score=per_char,
                ))
    except OSError:
        return None

    lang_results = PPLanguageResults(
        language_code=lang_code,
        entries=entries,
    )
    lang_results.build_indices()
    return lang_results


def find_p2_convergence(
    pp_signs_str: str,
    p2_sign_groups_set: Set[str],
) -> bool:
    """Check if a PP substring matches any Pillar 2 sign-group exactly.

    This tests for convergent evidence: did the PP progressive scan
    independently identify a substring that P2 morphological analysis
    also identified as a word boundary?

    Args:
        pp_signs_str: A PP substring in sign notation (e.g. "a-da-ki").
        p2_sign_groups_set: Set of P2 sign-group strings in the same
            notation (e.g. {"a-da-ki", "ku-ro", ...}).

    Returns:
        True if pp_signs_str is found in p2_sign_groups_set.
    """
    return pp_signs_str in p2_sign_groups_set


def get_all_unique_substrings(
    pp_results: Dict[str, PPLanguageResults],
) -> Set[str]:
    """Collect all unique linear_a_signs strings across all languages.

    Since the PP fleet evaluates the same set of substrings against every
    language, the set of substrings should be identical across languages.
    This function unions them defensively.

    Returns:
        Set of all unique linear_a_signs strings.
    """
    all_signs: Set[str] = set()
    for lang_results in pp_results.values():
        all_signs.update(lang_results.unique_signs())
    return all_signs


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

def load_pp_results(
    output_dir: str | Path,
    language_codes: Optional[List[str]] = None,
) -> Dict[str, PPLanguageResults]:
    """Backward-compatible alias for ``load_fleet_results``.

    The old API expected JSON files; this now delegates to the fleet
    TSV loader.  Returns empty dict if the directory does not exist
    (same contract as before).
    """
    return load_fleet_results(output_dir, languages=language_codes)
