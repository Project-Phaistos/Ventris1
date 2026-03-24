"""Transaction analysis and ku-ro verification for Pillar 4.

Parses numeral values using the decimal-additive system (Bennett 1950,
communis opinio) and verifies ku-ro ("total") summation records.

PRD Section 5.2: Parse numeral clusters, verify ku-ro totals, and
assign positional transaction roles to sign-groups.

CONSERVATIVE APPROACH:
- Only the most certain numeral values are parsed:
  A701 = unit (vertical strokes, value = count * 1)
  A704 = decade (horizontal bars, value = count * 10)
  A705 = centesimal (circles, value = count * 100)
- A702, A703, A706, A707, A708, A709x and all other numeral signs
  are flagged as "unparsed" — their values are NOT guessed.
- Fractional signs are flagged, not interpreted.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from pillar4.corpus_context_loader import (
    ContextCorpus,
    InscriptionContext,
    SignGroup,
    SignOccurrence,
)


# ---------------------------------------------------------------------------
# Numeral parsing (Bennett 1950, communis opinio)
# ---------------------------------------------------------------------------

# Conservative: only parse the most certain values.
# A701 = unit stroke (1), A704 = decade bar (10), A705 = centesimal circle (100)
_CERTAIN_NUMERAL_VALUES: Dict[str, int] = {
    "A701": 1,
    "A704": 10,
    "A705": 100,
}

# All numeral readings (A70x family)
_NUMERAL_RE = re.compile(r"^A70\d")


def _is_numeral(reading: str) -> bool:
    """Return True if reading is a numeral sign (A70x family)."""
    return bool(_NUMERAL_RE.match(reading))


@dataclass
class NumeralCluster:
    """A contiguous group of numeral signs in the sign sequence.

    Attributes:
        signs: List of (reading, position) pairs for each numeral sign.
        parsed_value: The summed integer value from certain numerals, or
            None if any sign in the cluster is unparsable.
        has_unparsed: True if any sign in the cluster is not in the
            certain-value set.
        start_pos: First sign position in the full sequence.
        end_pos: Last sign position in the full sequence.
        certain_components: Breakdown of parsed certain values.
        unparsed_signs: List of readings that could not be parsed.
    """
    signs: List[Tuple[str, int]]  # (reading, position_in_sequence)
    parsed_value: Optional[int]
    has_unparsed: bool
    start_pos: int
    end_pos: int
    certain_components: Dict[str, int] = field(default_factory=dict)
    unparsed_signs: List[str] = field(default_factory=list)


def _parse_numeral_cluster(signs: List[Tuple[str, int]]) -> NumeralCluster:
    """Parse a contiguous cluster of numeral signs into a value.

    Only signs in _CERTAIN_NUMERAL_VALUES contribute to the parsed total.
    If any sign is uncertain, has_unparsed is set True but parsing still
    proceeds for the certain signs.

    The parsed_value is set to None ONLY if there are zero certain signs
    (i.e. nothing can be summed at all).
    """
    if not signs:
        return NumeralCluster(
            signs=signs,
            parsed_value=None,
            has_unparsed=False,
            start_pos=-1,
            end_pos=-1,
        )

    total = 0
    has_certain = False
    has_unparsed = False
    components: Dict[str, int] = defaultdict(int)
    unparsed_list: List[str] = []

    for reading, _ in signs:
        val = _CERTAIN_NUMERAL_VALUES.get(reading)
        if val is not None:
            total += val
            has_certain = True
            components[reading] += 1
        else:
            has_unparsed = True
            unparsed_list.append(reading)

    return NumeralCluster(
        signs=signs,
        parsed_value=total if has_certain else None,
        has_unparsed=has_unparsed,
        start_pos=signs[0][1],
        end_pos=signs[-1][1],
        certain_components=dict(components),
        unparsed_signs=unparsed_list,
    )


# ---------------------------------------------------------------------------
# ku-ro detection
# ---------------------------------------------------------------------------

def _find_kuro_positions(
    sequence: List[SignOccurrence],
    kuro_sign_ids: List[str],
) -> List[int]:
    """Find positions where ku-ro appears in the sign sequence.

    ku-ro is identified by the sequence of AB-codes given in config
    (default: AB81 = ku, AB02 = ro).  We match on readings "ku" + "ro"
    since the sign_inventory maps AB81 -> "ku" and AB02 -> "ro".

    Returns a list of starting positions (index of "ku").
    """
    if len(kuro_sign_ids) < 2:
        return []

    # Build target readings from the kuro_sign_ids config
    # Common mapping: AB81 -> "ku", AB02 -> "ro"
    # But we'll also check raw readings matching the AB codes
    target_primary = ("ku", "ro")

    positions: List[int] = []
    n = len(sequence)

    for i in range(n - 1):
        r1 = sequence[i].reading
        r2 = sequence[i + 1].reading

        # Match by reading ("ku", "ro") or by AB-code
        ab1 = sequence[i].ab_code or ""
        ab2 = sequence[i + 1].ab_code or ""

        if (
            (r1 == target_primary[0] and r2 == target_primary[1])
            or (r1 == kuro_sign_ids[0] and r2 == kuro_sign_ids[1])
            or (ab1 == kuro_sign_ids[0] and ab2 == kuro_sign_ids[1])
        ):
            positions.append(i)

    return positions


# ---------------------------------------------------------------------------
# Dataclasses for results
# ---------------------------------------------------------------------------

@dataclass
class ParsedInscription:
    """An inscription with parsed numeral clusters.

    Attributes:
        inscription_id: Inscription identifier.
        numeral_clusters: All numeral clusters found in the inscription.
        has_kuro: Whether ku-ro appears in this inscription.
        kuro_positions: List of ku-ro starting positions.
    """
    inscription_id: str
    numeral_clusters: List[NumeralCluster]
    has_kuro: bool
    kuro_positions: List[int]


@dataclass
class KuroVerification:
    """Result of verifying a single ku-ro total.

    Attributes:
        inscription_id: Inscription identifier.
        kuro_position: Position of ku-ro in the sign sequence.
        pre_kuro_clusters: Numeral clusters before ku-ro.
        post_kuro_cluster: Numeral cluster immediately after ku-ro (the total).
        pre_kuro_sum: Sum of parsed pre-ku-ro values, or None if unparsable.
        post_kuro_value: Parsed value of the post-ku-ro cluster, or None.
        matches: True if pre_kuro_sum == post_kuro_value.
        status: "matching", "discrepant", "unparsable", or "no_post_numeral".
        has_unparsed_pre: Whether any pre-ku-ro cluster has unparsed signs.
        has_unparsed_post: Whether the post-ku-ro cluster has unparsed signs.
    """
    inscription_id: str
    kuro_position: int
    pre_kuro_clusters: List[NumeralCluster]
    post_kuro_cluster: Optional[NumeralCluster]
    pre_kuro_sum: Optional[int]
    post_kuro_value: Optional[int]
    matches: bool
    status: str   # "matching" | "discrepant" | "unparsable" | "no_post_numeral"
    has_unparsed_pre: bool = False
    has_unparsed_post: bool = False


@dataclass
class PositionalRole:
    """A sign-group's inferred positional role in a transaction.

    BIAS-FREE: roles are described by position relative to ideograms,
    numerals, and ku-ro markers, not by assumed linguistic function.

    Attributes:
        sign_group_ids: Tuple identifying the sign-group.
        transliteration: Transliteration string.
        role: Positional description: "pre_ideogram", "pre_numeral",
            "post_numeral", "pre_kuro", "post_kuro", "standalone".
        inscription_id: Where this role was observed.
        evidence_count: How many times this role was observed corpus-wide.
    """
    sign_group_ids: Tuple[str, ...]
    transliteration: str
    role: str
    inscription_id: str
    evidence_count: int = 1


@dataclass
class TransactionAnalysisResult:
    """Complete result of transaction / numeral analysis.

    PRD Section 5.2 output.

    Attributes:
        parsed_inscriptions: Inscriptions with parsed numeral data.
        kuro_verifications: Results of ku-ro total checks.
        positional_role_assignments: Sign-group positional roles.
        summary: Aggregate statistics.
    """
    parsed_inscriptions: List[ParsedInscription]
    kuro_verifications: List[KuroVerification]
    positional_role_assignments: List[PositionalRole]
    summary: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Cluster extraction
# ---------------------------------------------------------------------------

def _extract_numeral_clusters(
    sequence: List[SignOccurrence],
) -> List[NumeralCluster]:
    """Extract contiguous numeral clusters from a sign sequence.

    A cluster is a maximal run of consecutive numeral signs (A70x).
    """
    clusters: List[NumeralCluster] = []
    current: List[Tuple[str, int]] = []

    for occ in sequence:
        if _is_numeral(occ.reading):
            current.append((occ.reading, occ.position_in_sequence))
        else:
            if current:
                clusters.append(_parse_numeral_cluster(current))
                current = []

    if current:
        clusters.append(_parse_numeral_cluster(current))

    return clusters


# ---------------------------------------------------------------------------
# Positional role assignment
# ---------------------------------------------------------------------------

def _assign_positional_roles(
    inscription: InscriptionContext,
    kuro_positions: List[int],
) -> List[PositionalRole]:
    """Assign positional transaction roles to sign-groups.

    Roles are determined by the sign-group's position relative to
    ideograms, numerals, and ku-ro markers in the full sign sequence.
    """
    roles: List[PositionalRole] = []
    seq = inscription.full_sign_sequence

    # Build position sets for quick lookup
    numeral_positions: Set[int] = set()
    ideogram_positions: Set[int] = set()
    kuro_set: Set[int] = set()

    for occ in seq:
        if _is_numeral(occ.reading):
            numeral_positions.add(occ.position_in_sequence)
        if occ.sign_type == "named_ideogram":
            ideogram_positions.add(occ.position_in_sequence)

    for kp in kuro_positions:
        kuro_set.add(kp)
        kuro_set.add(kp + 1)  # "ro" position

    for sg in inscription.sign_groups:
        if not sg.sign_ids:
            continue

        # Try to find this sign-group in the sequence
        target = sg.sign_ids
        sg_start = -1
        sg_end = -1
        n = len(seq)
        tlen = len(target)

        for start in range(n - tlen + 1):
            match = True
            for k in range(tlen):
                if seq[start + k].reading != target[k]:
                    match = False
                    break
            if match:
                sg_start = start
                sg_end = start + tlen - 1
                break

        if sg_start < 0:
            roles.append(PositionalRole(
                sign_group_ids=sg.sign_ids,
                transliteration=sg.transliteration,
                role="standalone",
                inscription_id=inscription.id,
            ))
            continue

        # Check if this IS ku-ro
        if sg.sign_ids == ("ku", "ro") or (
            len(sg.sign_ids) >= 2
            and sg.sign_ids[-2:] == ("ku", "ro")
        ):
            roles.append(PositionalRole(
                sign_group_ids=sg.sign_ids,
                transliteration=sg.transliteration,
                role="kuro_marker",
                inscription_id=inscription.id,
            ))
            continue

        # Determine role by what's immediately after/before
        role = "standalone"

        # Check what follows after the sign-group
        next_pos = sg_end + 1
        if next_pos < n:
            if _is_numeral(seq[next_pos].reading):
                role = "pre_numeral"
            elif seq[next_pos].sign_type == "named_ideogram":
                role = "pre_ideogram"
            elif next_pos in kuro_set:
                role = "pre_kuro"

        # Check what precedes the sign-group
        prev_pos = sg_start - 1
        if prev_pos >= 0:
            if _is_numeral(seq[prev_pos].reading):
                if role == "standalone":
                    role = "post_numeral"
            elif prev_pos in kuro_set or (prev_pos - 1) in kuro_set:
                if role == "standalone":
                    role = "post_kuro"

        roles.append(PositionalRole(
            sign_group_ids=sg.sign_ids,
            transliteration=sg.transliteration,
            role=role,
            inscription_id=inscription.id,
        ))

    return roles


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze_transactions(
    corpus: ContextCorpus,
    kuro_sign_ids: Optional[List[str]] = None,
) -> TransactionAnalysisResult:
    """Parse numerals and verify ku-ro totals across the corpus.

    PRD Section 5.2 algorithm:

    1. Extract contiguous numeral clusters from each inscription's
       signs_sequence.
    2. Parse certain values (A701=1, A704=10, A705=100); flag others as
       unparsed.
    3. Find ku-ro markers and verify that pre-ku-ro numeral sum matches
       the post-ku-ro total.
    4. Assign positional roles to sign-groups based on their relationship
       to ideograms, numerals, and ku-ro.

    Args:
        corpus: Loaded ContextCorpus.
        kuro_sign_ids: AB-codes for ku-ro marker (default: ["AB81", "AB02"]).

    Returns:
        TransactionAnalysisResult with parsed inscriptions, ku-ro
        verifications, positional roles, and summary statistics.
    """
    if kuro_sign_ids is None:
        kuro_sign_ids = ["AB81", "AB02"]

    parsed_inscriptions: List[ParsedInscription] = []
    kuro_verifications: List[KuroVerification] = []
    all_roles: List[PositionalRole] = []

    n_testable = 0
    n_matching = 0
    n_discrepant = 0
    n_unparsable = 0
    n_no_post = 0

    for insc in corpus.inscriptions:
        seq = insc.full_sign_sequence
        if not seq:
            continue

        # Extract numeral clusters
        clusters = _extract_numeral_clusters(seq)

        # Find ku-ro positions
        kuro_positions = _find_kuro_positions(seq, kuro_sign_ids)
        has_kuro = len(kuro_positions) > 0

        parsed_inscriptions.append(ParsedInscription(
            inscription_id=insc.id,
            numeral_clusters=clusters,
            has_kuro=has_kuro,
            kuro_positions=kuro_positions,
        ))

        # Verify ku-ro totals
        for kuro_pos in kuro_positions:
            n_testable += 1

            # Separate clusters into pre-kuro and post-kuro
            # ku-ro occupies positions kuro_pos and kuro_pos+1
            kuro_end = kuro_pos + 1
            pre_clusters = [
                c for c in clusters if c.end_pos < kuro_pos
            ]
            post_clusters = [
                c for c in clusters if c.start_pos > kuro_end
            ]

            # The first post-kuro cluster should be the total
            post_cluster = post_clusters[0] if post_clusters else None

            if post_cluster is None:
                n_no_post += 1
                kuro_verifications.append(KuroVerification(
                    inscription_id=insc.id,
                    kuro_position=kuro_pos,
                    pre_kuro_clusters=pre_clusters,
                    post_kuro_cluster=None,
                    pre_kuro_sum=None,
                    post_kuro_value=None,
                    matches=False,
                    status="no_post_numeral",
                ))
                continue

            # Sum pre-kuro parsed values
            has_unparsed_pre = any(c.has_unparsed for c in pre_clusters)
            pre_sum: Optional[int] = None
            if pre_clusters:
                total = 0
                all_have_value = True
                for c in pre_clusters:
                    if c.parsed_value is not None:
                        total += c.parsed_value
                    else:
                        all_have_value = False
                pre_sum = total if all_have_value or total > 0 else None

            post_value = post_cluster.parsed_value
            has_unparsed_post = post_cluster.has_unparsed

            if pre_sum is None or post_value is None:
                n_unparsable += 1
                status = "unparsable"
                matches = False
            elif pre_sum == post_value:
                n_matching += 1
                status = "matching"
                matches = True
            else:
                n_discrepant += 1
                status = "discrepant"
                matches = False

            kuro_verifications.append(KuroVerification(
                inscription_id=insc.id,
                kuro_position=kuro_pos,
                pre_kuro_clusters=pre_clusters,
                post_kuro_cluster=post_cluster,
                pre_kuro_sum=pre_sum,
                post_kuro_value=post_value,
                matches=matches,
                status=status,
                has_unparsed_pre=has_unparsed_pre,
                has_unparsed_post=has_unparsed_post,
            ))

        # Assign positional roles
        roles = _assign_positional_roles(insc, kuro_positions)
        all_roles.extend(roles)

    # Aggregate role counts for evidence_count
    role_counts: Dict[Tuple[Tuple[str, ...], str], int] = defaultdict(int)
    for r in all_roles:
        role_counts[(r.sign_group_ids, r.role)] += 1

    # Update evidence counts
    for r in all_roles:
        r.evidence_count = role_counts[(r.sign_group_ids, r.role)]

    summary = {
        "n_inscriptions_with_numerals": sum(
            1 for p in parsed_inscriptions if p.numeral_clusters
        ),
        "n_inscriptions_with_kuro": sum(
            1 for p in parsed_inscriptions if p.has_kuro
        ),
        "n_kuro_testable": n_testable,
        "n_kuro_matching": n_matching,
        "n_kuro_discrepant": n_discrepant,
        "n_kuro_unparsable": n_unparsable,
        "n_kuro_no_post_numeral": n_no_post,
    }

    return TransactionAnalysisResult(
        parsed_inscriptions=parsed_inscriptions,
        kuro_verifications=kuro_verifications,
        positional_role_assignments=all_roles,
        summary=summary,
    )
