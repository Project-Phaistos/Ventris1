"""Pillar 5 Step 4: Combined scoring with evidence weighting.

Combines phonological distance (from PP or edit distance) and semantic
compatibility into a single confidence score, weighted by evidence provenance.

Formula (from PRD Section 5.4):
    combined_score = phon_score * w_phon + semantic * w_sem

where:
    phon_score  = normalized quality score [0,1] (best=1.0, worst=0.0)
    semantic    = semantic compatibility (0.0, 0.5, or 1.0; None if unavailable)
    w_phon      = 0.5 (CONSENSUS_ASSUMED — depends on LB IPA input)
    w_sem       = provenance_weight(P4 semantic evidence)

This formula is ad hoc and validated via Gate 1 (Ugaritic-Hebrew known-answer test).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constraint_assembler import PROVENANCE_WEIGHTS


# Default weight for phonological score (CONSENSUS_ASSUMED since it depends
# on LB phonetic values)
W_PHON = 0.5


@dataclass
class CandidateMatch:
    """A single candidate word matched against a Linear A sign-group."""

    language_code: str
    language_name: str
    word: str
    ipa: str
    gloss: Optional[str]

    # Phonological distance (from PP or edit distance)
    phonological_distance: Optional[float] = None
    # Normalized phonological score [0,1] within this language
    phonological_score: float = 0.0

    # Semantic compatibility from P4 anchors
    semantic_compatibility: Optional[float] = None

    # Combined score
    combined_score: float = 0.0

    # Evidence chain for provenance
    evidence_provenance: str = "CONSENSUS_DEPENDENT"
    evidence_chain: List[str] = field(default_factory=list)


@dataclass
class SignGroupMatches:
    """All candidate matches for a single sign-group."""

    sign_group_ids: List[str]
    stem_ipa_lb: Optional[str]
    semantic_field: Optional[str]
    matches: List[CandidateMatch] = field(default_factory=list)
    best_match: Optional[CandidateMatch] = None

    @property
    def n_matches(self) -> int:
        return len(self.matches)

    @property
    def has_significant_match(self) -> bool:
        """True if any match exceeds the significance threshold."""
        return self.best_match is not None and self.best_match.combined_score > 0.5


def normalize_scores(
    raw_scores: List[float],
) -> List[float]:
    """Normalize raw phonological scores to [0, 1] within a set.

    Higher is better. Uses min-max normalization:
        normalized = (score - min) / (max - min)

    For phonological distances (lower = closer), negate before normalizing.
    For quality scores (higher = better), use directly.
    """
    if not raw_scores:
        return []
    if len(raw_scores) == 1:
        return [1.0]  # Single score is always "best"

    min_s = min(raw_scores)
    max_s = max(raw_scores)
    spread = max_s - min_s

    if spread == 0:
        return [0.5] * len(raw_scores)  # All equal

    return [(s - min_s) / spread for s in raw_scores]


def compute_combined_score(
    phonological_score: float,
    semantic_compatibility: Optional[float],
    semantic_provenance: str = "CONSENSUS_DEPENDENT",
) -> float:
    """Compute combined score from phonological and semantic evidence.

    Args:
        phonological_score: Normalized [0,1] phonological match score
        semantic_compatibility: 0.0/0.5/1.0 or None if unavailable
        semantic_provenance: Evidence provenance tag for semantic evidence

    Returns:
        Combined score in [0, 1].
    """
    phon_component = phonological_score * W_PHON

    if semantic_compatibility is None:
        # Phonology only — lower confidence
        return phon_component

    w_sem = PROVENANCE_WEIGHTS.get(semantic_provenance, 0.3)
    sem_component = semantic_compatibility * w_sem

    return phon_component + sem_component


def combine_evidence(
    sign_group_ids: List[str],
    stem_ipa_lb: Optional[str],
    semantic_field: Optional[str],
    semantic_provenance: str,
    candidate_matches: List[Dict[str, Any]],
    min_match_threshold: float = 0.0,
    max_per_language: int = 5,
) -> SignGroupMatches:
    """Combine phonological and semantic scores for all candidates.

    Args:
        sign_group_ids: The sign-group being matched
        stem_ipa_lb: IPA reading of the stem (LB values)
        semantic_field: P4 semantic anchor (if any)
        semantic_provenance: Provenance tag for the semantic field
        candidate_matches: List of dicts with keys:
            language_code, language_name, word, ipa, gloss,
            phonological_score, semantic_compatibility
        min_match_threshold: Minimum combined score to keep a match
        max_per_language: Maximum matches to keep per language

    Returns:
        SignGroupMatches with all matches scored and ranked.
    """
    scored_matches: List[CandidateMatch] = []

    for cm in candidate_matches:
        phon_score = cm.get("phonological_score", 0.0)
        sem_compat = cm.get("semantic_compatibility")

        combined = compute_combined_score(
            phon_score, sem_compat, semantic_provenance
        )

        if combined < min_match_threshold:
            continue

        # Build evidence chain
        evidence_chain = []
        if stem_ipa_lb:
            evidence_chain.append(
                f"Phonological: score {phon_score:.3f} "
                f"(LB reading {stem_ipa_lb} vs {cm.get('language_name', '?')} {cm.get('ipa', '?')})"
            )
        if sem_compat is not None:
            evidence_chain.append(
                f"Semantic: {semantic_field} vs gloss '{cm.get('gloss', '?')}' "
                f"-> compatibility {sem_compat:.1f}"
            )
        else:
            evidence_chain.append("Semantic: no gloss available (null)")

        match = CandidateMatch(
            language_code=cm.get("language_code", ""),
            language_name=cm.get("language_name", ""),
            word=cm.get("word", ""),
            ipa=cm.get("ipa", ""),
            gloss=cm.get("gloss"),
            phonological_distance=cm.get("phonological_distance"),
            phonological_score=phon_score,
            semantic_compatibility=sem_compat,
            combined_score=combined,
            evidence_provenance=cm.get("evidence_provenance", "CONSENSUS_DEPENDENT"),
            evidence_chain=evidence_chain,
        )
        scored_matches.append(match)

    # Sort by combined score descending
    scored_matches.sort(key=lambda m: -m.combined_score)

    # Limit per language
    if max_per_language > 0:
        per_lang_counts: Dict[str, int] = {}
        filtered = []
        for m in scored_matches:
            count = per_lang_counts.get(m.language_code, 0)
            if count < max_per_language:
                filtered.append(m)
                per_lang_counts[m.language_code] = count + 1
        scored_matches = filtered

    best = scored_matches[0] if scored_matches else None

    return SignGroupMatches(
        sign_group_ids=sign_group_ids,
        stem_ipa_lb=stem_ipa_lb,
        semantic_field=semantic_field,
        matches=scored_matches,
        best_match=best,
    )
