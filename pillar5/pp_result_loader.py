"""Pillar 5 Step 2 (partial): Load Phonetic Prior production run results.

Loads per-language cognate match JSONs from the PP production run output
directory. Each JSON contains per-inscription cognate lists with quality
scores from the Phonetic Prior algorithm (Luo, Cao, & Barzilay, ACL 2019).

Expected output format from ventris1_production_run.py:
    {
        "language": "grc",
        "n_steps": 1000,
        "restart": 0,
        "best_objective": -42.5,
        "cognate_list": [
            {
                "line_index": 0,
                "lost_text": "tapi ki ara ...",
                "segments": [...] or "top_matches": [...]
            }
        ]
    }

If PP results are not yet available, this module returns empty results
so the pipeline can still run with phonological edit distance fallback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class PPWordMatch:
    """A single cognate match from the Phonetic Prior."""

    known_word: str
    quality_score: float
    rank: int = 0


@dataclass
class PPInscriptionResult:
    """PP results for a single inscription line."""

    line_index: int
    lost_text: str
    top_matches: List[PPWordMatch] = field(default_factory=list)
    total_quality: Optional[float] = None
    error: Optional[str] = None


@dataclass
class PPLanguageResult:
    """PP results for a single candidate language."""

    language_code: str
    n_steps: int = 0
    restart: int = 0
    best_objective: float = 0.0
    inscriptions: List[PPInscriptionResult] = field(default_factory=list)

    @property
    def n_inscriptions(self) -> int:
        return len(self.inscriptions)

    @property
    def n_with_matches(self) -> int:
        return sum(1 for i in self.inscriptions if i.top_matches)


def load_pp_results(
    output_dir: str | Path,
    language_codes: Optional[List[str]] = None,
) -> Dict[str, PPLanguageResult]:
    """Load PP production run results from output directory.

    Args:
        output_dir: Directory containing cognates_{lang}.json files
        language_codes: Which languages to load (None = all found)

    Returns:
        Dict mapping language code to PPLanguageResult.
        Returns empty dict if output directory doesn't exist.
    """
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return {}

    results: Dict[str, PPLanguageResult] = {}

    # Find all cognate result files
    for json_path in sorted(output_dir.glob("cognates_*.json")):
        lang_code = json_path.stem.replace("cognates_", "")
        if language_codes is not None and lang_code not in language_codes:
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        result = _parse_pp_result(lang_code, data)
        if result is not None:
            results[lang_code] = result

    return results


def _parse_pp_result(
    lang_code: str, data: Dict[str, Any]
) -> Optional[PPLanguageResult]:
    """Parse a single PP result JSON into typed objects."""
    if not isinstance(data, dict):
        return None

    inscriptions: List[PPInscriptionResult] = []

    for entry in data.get("cognate_list", []):
        if not isinstance(entry, dict):
            continue

        error = entry.get("error")
        if error:
            inscriptions.append(PPInscriptionResult(
                line_index=entry.get("line_index", -1),
                lost_text=entry.get("lost_text", ""),
                error=error,
            ))
            continue

        # Parse matches from either format
        top_matches = _parse_matches(entry)

        inscriptions.append(PPInscriptionResult(
            line_index=entry.get("line_index", -1),
            lost_text=entry.get("lost_text", ""),
            top_matches=top_matches,
            total_quality=entry.get("total_quality"),
        ))

    return PPLanguageResult(
        language_code=lang_code,
        n_steps=data.get("n_steps", 0),
        restart=data.get("restart", 0),
        best_objective=data.get("best_objective", 0.0),
        inscriptions=inscriptions,
    )


def _parse_matches(entry: Dict[str, Any]) -> List[PPWordMatch]:
    """Parse matches from either segments or top_matches format."""
    matches: List[PPWordMatch] = []
    rank = 0

    # Format 1: segments with per-segment matches
    if "segments" in entry:
        for seg in entry["segments"]:
            if isinstance(seg, dict):
                for m in seg.get("top_matches", []):
                    rank += 1
                    matches.append(PPWordMatch(
                        known_word=m.get("known_word", ""),
                        quality_score=m.get("quality_score", 0.0),
                        rank=rank,
                    ))

    # Format 2: flat top_matches
    elif "top_matches" in entry:
        for m in entry["top_matches"]:
            rank += 1
            matches.append(PPWordMatch(
                known_word=m.get("known_word", ""),
                quality_score=m.get("quality_score", 0.0),
                rank=rank,
            ))

    return matches


def build_stem_cognate_index(
    pp_results: Dict[str, PPLanguageResult],
) -> Dict[str, Dict[str, List[PPWordMatch]]]:
    """Build an index of cognate matches keyed by known_word across all languages.

    Returns:
        Dict[language_code, Dict[known_word, List[PPWordMatch]]]
        This allows looking up which known words appeared as matches.
    """
    index: Dict[str, Dict[str, List[PPWordMatch]]] = {}

    for lang_code, result in pp_results.items():
        word_index: Dict[str, List[PPWordMatch]] = {}
        for insc in result.inscriptions:
            for match in insc.top_matches:
                if match.known_word not in word_index:
                    word_index[match.known_word] = []
                word_index[match.known_word].append(match)
        index[lang_code] = word_index

    return index
