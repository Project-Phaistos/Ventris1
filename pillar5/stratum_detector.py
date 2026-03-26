"""Pillar 5 Step 6: Emergent stratum detection.

Lets vocabulary strata emerge from the data — does NOT pre-specify which
languages should appear as sources. Per README resolved design decisions:
"keep it informal and let the strata emerge from the data."

Algorithm (from PRD Section 5.6):
1. For each sign-group with a match above threshold, record best-matching language
2. Group sign-groups by best-matching language
3. Check if matches share a semantic domain
4. Sign-groups with no match -> "substrate" stratum

No mixture model. Report what we observe.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .evidence_combiner import SignGroupMatches


# Minimum sign-groups in a stratum to report it as a finding (not noise)
MIN_STRATUM_SIZE = 5

# Threshold for a match to count as "significant"
MATCH_THRESHOLD = 0.5


@dataclass
class Stratum:
    """An emergent vocabulary stratum."""

    stratum_id: int
    dominant_language: str  # Language code or "unknown_substrate"
    dominant_language_name: str
    n_sign_groups: int
    proportion: float
    semantic_domains: List[str] = field(default_factory=list)
    description: str = ""
    is_noise: bool = False  # True if < MIN_STRATUM_SIZE sign-groups


@dataclass
class StratumAnalysis:
    """Complete stratum analysis results."""

    strata: List[Stratum]
    method: str = "unsupervised_clustering_of_best_matches"
    evidence_provenance: str = "CONSENSUS_DEPENDENT"
    note: str = (
        "Strata are emergent, not pre-specified. Dominance of substrate "
        "stratum is expected if Linear A is a language isolate with "
        "contact vocabulary."
    )

    @property
    def n_strata(self) -> int:
        return len([s for s in self.strata if not s.is_noise])

    @property
    def substrate_fraction(self) -> float:
        for s in self.strata:
            if s.dominant_language == "unknown_substrate":
                return s.proportion
        return 0.0


def detect_strata(
    all_matches: List[SignGroupMatches],
    match_threshold: float = MATCH_THRESHOLD,
    min_stratum_size: int = MIN_STRATUM_SIZE,
) -> StratumAnalysis:
    """Detect emergent vocabulary strata from per-sign-group match results.

    Args:
        all_matches: List of SignGroupMatches from evidence_combiner
        match_threshold: Minimum combined_score for a match to count
        min_stratum_size: Minimum sign-groups to report as a stratum

    Returns:
        StratumAnalysis with emergent strata.
    """
    total = len(all_matches)
    if total == 0:
        return StratumAnalysis(strata=[])

    # Group by best-matching language
    lang_groups: Dict[str, List[SignGroupMatches]] = defaultdict(list)
    substrate_group: List[SignGroupMatches] = []

    for sgm in all_matches:
        if sgm.best_match is not None and sgm.best_match.combined_score >= match_threshold:
            lang_groups[sgm.best_match.language_code].append(sgm)
        else:
            substrate_group.append(sgm)

    strata: List[Stratum] = []
    stratum_id = 0

    # Substrate stratum (always first)
    if substrate_group:
        sub_domains = _extract_domains(substrate_group)
        strata.append(Stratum(
            stratum_id=stratum_id,
            dominant_language="unknown_substrate",
            dominant_language_name="Unknown Substrate",
            n_sign_groups=len(substrate_group),
            proportion=len(substrate_group) / total,
            semantic_domains=sub_domains,
            description=(
                f"Majority of vocabulary has no strong match to any candidate "
                f"language — consistent with an unattested substrate language"
                if len(substrate_group) > total * 0.5
                else f"{len(substrate_group)} sign-groups with no significant external match"
            ),
            is_noise=len(substrate_group) < min_stratum_size,
        ))
        stratum_id += 1

    # Language-specific strata, sorted by size descending
    for lang_code in sorted(lang_groups.keys(), key=lambda k: -len(lang_groups[k])):
        group = lang_groups[lang_code]
        domains = _extract_domains(group)
        lang_name = group[0].best_match.language_name if group[0].best_match else lang_code

        is_noise = len(group) < min_stratum_size
        description = _build_stratum_description(lang_name, group, domains, is_noise)

        strata.append(Stratum(
            stratum_id=stratum_id,
            dominant_language=lang_code,
            dominant_language_name=lang_name,
            n_sign_groups=len(group),
            proportion=len(group) / total,
            semantic_domains=domains,
            description=description,
            is_noise=is_noise,
        ))
        stratum_id += 1

    return StratumAnalysis(strata=strata)


def _extract_domains(matches: List[SignGroupMatches]) -> List[str]:
    """Extract the semantic domains present in a group of matches."""
    domains: Counter = Counter()
    for sgm in matches:
        if sgm.semantic_field:
            domain = sgm.semantic_field.split(":")[0]
            domains[domain] += 1
    return [d for d, _ in domains.most_common()]


def _build_stratum_description(
    lang_name: str,
    group: List[SignGroupMatches],
    domains: List[str],
    is_noise: bool,
) -> str:
    """Build a human-readable description for a stratum."""
    if is_noise:
        return (
            f"Only {len(group)} sign-groups cluster with {lang_name} — "
            f"below minimum threshold for a reliable stratum finding"
        )

    if domains:
        domain_str = ", ".join(domains[:3])
        return (
            f"{len(group)} sign-groups cluster with {lang_name}, "
            f"concentrated in {domain_str} domains"
        )

    return f"{len(group)} sign-groups cluster with {lang_name}"


def compute_compositional_portrait(
    analysis: StratumAnalysis,
) -> Dict[str, Any]:
    """Compute the compositional linguistic portrait from stratum analysis.

    Returns a dict with fraction breakdowns by language family grouping.
    """
    portrait: Dict[str, float] = {
        "substrate_fraction": 0.0,
        "anatolian_fraction": 0.0,
        "semitic_fraction": 0.0,
        "greek_fraction": 0.0,
        "other_ie_fraction": 0.0,
        "ambiguous_fraction": 0.0,
    }

    # Family classification for grouping strata
    family_map = {
        "unknown_substrate": "substrate",
        "grc": "greek", "ell": "greek",
        "akk": "semitic", "heb": "semitic", "arb": "semitic", "arc": "semitic",
        "hit": "anatolian", "xlu": "anatolian",
        "lat": "other_ie", "san": "other_ie", "got": "other_ie",
        "hun": "other", "fin": "other", "tur": "other",
        "kat": "other", "eus": "other", "cop": "other",
    }

    for stratum in analysis.strata:
        family = family_map.get(stratum.dominant_language, "ambiguous")
        key = f"{family}_fraction"
        if key in portrait:
            portrait[key] += stratum.proportion
        else:
            portrait["ambiguous_fraction"] += stratum.proportion

    # Build summary string
    parts = []
    for key, frac in portrait.items():
        if frac > 0.01:  # Only report >1%
            label = key.replace("_fraction", "").replace("_", " ")
            parts.append(f"{frac:.0%} {label}")

    portrait["summary"] = ", ".join(parts) if parts else "No significant strata detected"
    portrait["evidence_provenance"] = "CONSENSUS_DEPENDENT"

    return portrait
