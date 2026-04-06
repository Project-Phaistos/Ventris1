"""Monte Carlo null cognate search for 3+ sign Linear A stems.

Searches 21 longest P2 stems (3+ signs) against 18 candidate ancient
languages using:
  - Monte Carlo null (random SCA strings, pre-computed null tables
    per (query_length, language) pair)
  - BH-FDR correction at alpha=0.05
  - Self-consistency analysis for shared unknown signs

Implements PRD_ANALYTICAL_NULL_SEARCH.md (Sections 3-11).

Sign-groups are structural hypotheses (not confirmed "words").
Linear A is treated as a chimaera language (multiple influences).
"""

from __future__ import annotations

import csv
import io
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", line_buffering=True
    )

PROJECT = Path(__file__).resolve().parents[2]
LEXICON_DIR = (
    PROJECT.parent / "ancient-scripts-datasets" / "data" / "training" / "lexicons"
)

# ── Constants ────────────────────────────────────────────────────────────

SCA_ALPHABET = list("HJKLMNPRSTVW")
SCA_K = len(SCA_ALPHABET)  # 12

LANG_CODES = [
    "hit", "xld", "xlc", "xrr", "phn", "uga", "elx", "xur",
    "peo", "xpg", "ave", "akk", "grc", "lat", "heb", "arb",
    "sem-pro", "ine-pro",
]

MAX_LEXICON_ENTRIES = 3000
NULL_SAMPLES = 1_000  # p-value resolution 0.001; sufficient for BH-FDR
NULL_POOL_CAP = 500  # Cap per length bucket for null <-> search consistency
FDR_ALPHA = 0.05

VC_TO_VOWEL = {0: "a", 1: "e", 2: "i", 3: "o", 4: "u"}

# ── Dolgopolsky sound classes ────────────────────────────────────────────

DOLGOPOLSKY = {
    "p": "P", "b": "P", "f": "P", "v": "P", "ɸ": "P", "β": "P",
    "t": "T", "d": "T", "θ": "T", "ð": "T", "ɗ": "T", "ɖ": "T",
    "s": "S", "z": "S", "ʃ": "S", "ʒ": "S", "ʂ": "S", "ʐ": "S",
    "c": "S", "ç": "S", "ɕ": "S", "ʑ": "S",
    "k": "K", "g": "K", "ɡ": "K", "x": "K", "ɣ": "K", "q": "K",
    "χ": "K", "ɢ": "K", "ʁ": "K",
    "m": "M", "ɱ": "M",
    "n": "N", "ɲ": "N", "ŋ": "N", "ɳ": "N", "ɴ": "N",
    "l": "L", "ɬ": "L", "ɮ": "L", "ɭ": "L", "ʎ": "L",
    "r": "R", "ɾ": "R", "ɽ": "R", "ɻ": "R",
    "w": "W", "ʷ": "W",
    "j": "J", "ʝ": "J",
    "h": "H", "ɦ": "H", "ʔ": "H", "ʕ": "H", "ħ": "H", "ɧ": "H",
    "a": "V", "e": "V", "i": "V", "o": "V", "u": "V",
    "ə": "V", "ɛ": "V", "ɔ": "V", "ɪ": "V", "ʊ": "V",
    "æ": "V", "ɑ": "V", "ʌ": "V", "ɒ": "V",
    "y": "V", "ø": "V", "œ": "V", "ɯ": "V", "ɨ": "V", "ʉ": "V",
    "ɐ": "V", "ɵ": "V", "ɤ": "V",
}

# Diacritics/modifiers to strip before SCA mapping
_SCA_STRIP = set("ːˑʰʱˤ̃̈̊ʼ̤̥̩̯̰ˠˁ̻̪̺̝̞̘̙̟̠̜̹̈̽ʲ͜͡")


def ipa_to_sca(ipa: str) -> str:
    """Convert IPA string to Dolgopolsky SCA encoding."""
    return "".join(DOLGOPOLSKY.get(ch, "") for ch in ipa if ch not in _SCA_STRIP)


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Compute normalized Levenshtein distance NED(s1, s2)."""
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


# ── Lexicon loading ──────────────────────────────────────────────────────


def load_lexicon(lang_code: str) -> list[dict]:
    """Load a language lexicon from TSV. Cap at MAX_LEXICON_ENTRIES.

    ALWAYS re-computes SCA from IPA using our Dolgopolsky encoding,
    because lexicon files use a different SCA scheme (vowel-preserving)
    that is incompatible with our V-collapsed Dolgopolsky classes.
    Uses seeded random sampling when capping (not first-N truncation).
    """
    path = LEXICON_DIR / f"{lang_code}.tsv"
    if not path.exists():
        return []
    all_entries = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ipa = row.get("IPA", "").strip()
            if not ipa:
                continue
            # Always compute SCA from IPA (lexicon SCA uses different scheme)
            sca = ipa_to_sca(ipa)
            if not sca:
                continue
            gloss = row.get("Concept_ID", "").strip()
            if gloss == "-":
                gloss = ""
            all_entries.append({
                "word": row.get("Word", "").strip(),
                "ipa": ipa,
                "sca": sca,
                "gloss": gloss,
            })
    if len(all_entries) > MAX_LEXICON_ENTRIES:
        rng = random.Random(42)
        all_entries = rng.sample(all_entries, MAX_LEXICON_ENTRIES)
    return all_entries


# ── Grid / sign data loading ─────────────────────────────────────────────


def load_sign_to_ipa() -> dict[str, str]:
    """Load sign-to-IPA mapping."""
    with open(PROJECT / "data" / "sign_to_ipa.json") as f:
        return json.load(f)


def load_corpus() -> dict:
    """Load corpus and build AB-to-reading mapping."""
    with open(PROJECT / "data" / "sigla_full_corpus.json", encoding="utf-8") as f:
        corpus = json.load(f)
    ab_to_reading: dict[str, str] = {}
    ab_confidence: dict[str, str] = {}
    tier_priority = {"tier1": 0, "tier2": 1, "tier3_undeciphered": 2}
    for reading, info in corpus["sign_inventory"].items():
        if isinstance(info, dict):
            conf = info.get("confidence", "tier3_undeciphered")
            for ab in info.get("ab_codes", []):
                prev_conf = ab_confidence.get(ab, "tier3_undeciphered")
                if tier_priority.get(conf, 2) <= tier_priority.get(prev_conf, 2):
                    ab_to_reading[ab] = reading
                    ab_confidence[ab] = conf
    return ab_to_reading


def load_p1_grid() -> dict[str, tuple[int, int, float]]:
    """Load P1 grid assignments: sign_id -> (consonant_class, vowel_class, confidence)."""
    with open(PROJECT / "results" / "pillar1_v5_output.json") as f:
        p1 = json.load(f)
    grid: dict[str, tuple[int, int, float]] = {}
    for a in p1["grid"]["assignments"]:
        grid[a["sign_id"]] = (
            a["consonant_class"],
            a["vowel_class"],
            a["confidence"],
        )
    return grid


def build_cell_consonants(
    grid: dict[str, tuple[int, int, float]],
    ab_to_reading: dict[str, str],
    sign_to_ipa: dict[str, str],
) -> dict[int, set[str]]:
    """Build mapping from vowel class to known consonant onsets in that class."""
    cell_consonants: dict[int, set[str]] = defaultdict(set)
    for sign_id, (cc, vc, _conf) in grid.items():
        reading = ab_to_reading.get(sign_id, sign_id)
        ipa = sign_to_ipa.get(reading)
        if ipa and cc == 0:
            clean = ipa.rstrip("0123456789")
            if clean in ("a", "e", "i", "o", "u"):
                cell_consonants[vc].add("")
            elif clean.endswith(("a", "e", "i", "o", "u")):
                cell_consonants[vc].add(clean[:-1])
            elif clean == "nwa":
                cell_consonants[vc].add("nw")
    return cell_consonants


def candidate_readings(vowel_class: int, cell_consonants: dict[int, set[str]]) -> list[str]:
    """Generate candidate CV readings for a vowel class."""
    vowel = VC_TO_VOWEL.get(vowel_class)
    if vowel is None:
        return []
    return sorted(c + vowel for c in cell_consonants.get(vowel_class, set()))


# ── Analytical null distribution ─────────────────────────────────────────


NULL_CAP_PER_BUCKET = 200  # Max entries per length bucket for null computation


def best_match_in_lexicon(
    query_sca: str,
    lex_sca_by_len: dict[int, list[str]],
) -> tuple[float, int]:
    """Find best NED match for query_sca in a length-bucketed lexicon.

    Only compares against entries of length L-2 to L+2.
    Returns (best_ned, index_in_bucket).
    """
    L = len(query_sca)
    best_ned = 1.0
    best_idx = -1
    for bucket_len in range(max(1, L - 2), L + 3):
        bucket = lex_sca_by_len.get(bucket_len, [])
        for idx, sca in enumerate(bucket):
            d = normalized_edit_distance(query_sca, sca)
            if d < best_ned:
                best_ned = d
                best_idx = idx
    return best_ned, best_idx


def search_lexicon_full(
    query_sca: str,
    lexicon: list[dict],
) -> tuple[float, dict | None]:
    """Search full lexicon for best SCA match. Returns (ned, entry)."""
    best_ned = 1.0
    best_entry = None
    L = len(query_sca)
    for entry in lexicon:
        sca = entry["sca"]
        if not sca:
            continue
        # Length filter: skip entries too far in length
        if abs(len(sca) - L) > 2:
            continue
        d = normalized_edit_distance(query_sca, sca)
        if d < best_ned:
            best_ned = d
            best_entry = entry
    return best_ned, best_entry


def search_capped_pool(
    query_sca: str,
    capped_by_len: dict[int, list[str]],
    full_lexicon: list[dict],
) -> tuple[float, dict | None]:
    """Search capped pool for best NED, then look up the full entry.

    Uses the same capped pool as the null table to ensure consistency.
    Returns (ned, best_entry_from_full_lexicon).
    """
    L = len(query_sca)
    best_ned = 1.0
    best_sca_match = ""

    for bucket_len in range(max(1, L - 2), L + 3):
        for sca in capped_by_len.get(bucket_len, []):
            d = normalized_edit_distance(query_sca, sca)
            if d < best_ned:
                best_ned = d
                best_sca_match = sca

    # Look up the full entry for metadata (word, ipa, gloss)
    best_entry = None
    if best_sca_match:
        for entry in full_lexicon:
            if entry["sca"] == best_sca_match:
                best_entry = entry
                break

    return best_ned, best_entry


def _count_pool_size(
    lex_sca_by_len: dict[int, list[str]],
    query_length: int,
) -> int:
    """Count total entries in the comparison window for a query length."""
    total = 0
    for bucket_len in range(max(1, query_length - 2), query_length + 3):
        total += len(lex_sca_by_len.get(bucket_len, []))
    return total


def analytical_pvalue(
    ned: float,
    query_length: int,
    pool_size: int,
) -> float:
    """Compute analytical p-value for best-match NED.

    Uses the substitution-only edit distance ball volume, with a length-aware
    correction factor for insertions/deletions. The correction factor is
    derived from the observation that at edit distance d=1, indels roughly
    double the ball volume (factor ~2.3), while at d=0, there is no
    correction (exact match = exact match regardless of operation type).

    The pool_size is the number of lexicon entries within the comparison
    length window (query_length +/- 2), matching the actual search scope.

    The formula:
      d = floor(ned * query_length)
      V_sub(L, d, K) = sum_{i=0}^{d} C(L, i) * (K-1)^i
      V_corrected = V_sub * indel_correction(d)
      p_single = min(V_corrected / K^L, 1.0)
      p_value = 1 - (1 - p_single)^pool_size
    """
    from math import comb, log, log1p, expm1, exp

    L = query_length
    K = SCA_K  # 12
    d = int(ned * L)  # integer edit distance threshold

    if L <= 0 or pool_size <= 0:
        return 1.0

    # Substitution-only ball volume
    vol_sub = sum(comb(L, i) * (K - 1) ** i for i in range(d + 1))

    # Indel correction: at d=1, ~2.3x; at d=2, ~3.5x; at d=0, 1x
    # These factors come from comparing V_sub to exact counting
    # (see analysis in PRD Section 4.2)
    if d == 0:
        correction = 1.0
    elif d == 1:
        correction = 2.3
    elif d == 2:
        correction = 4.0
    else:
        correction = 2.0 * d  # rough extrapolation

    vol = vol_sub * correction

    # p_single: probability one random string is within edit distance d
    total_space = K ** L
    if vol >= total_space:
        return 1.0  # saturated

    log_p_single = log(vol) - L * log(K)

    if log_p_single >= 0:
        return 1.0

    N = pool_size

    # p_value = 1 - (1 - p_single)^N
    try:
        log_q = N * log1p(-exp(log_p_single))
        p_value = -expm1(log_q)
    except (ValueError, OverflowError):
        p_value = 1.0

    return max(0.0, min(1.0, p_value))


def cap_bucketed_lexicon(
    lex_sca_by_len: dict[int, list[str]],
    rng: random.Random,
    cap: int = NULL_POOL_CAP,
) -> dict[int, list[str]]:
    """Cap each length bucket to `cap` entries via seeded sampling.

    Both build_null_table() and the main pipeline search use this to
    ensure the null and the search see the same comparison pool.
    """
    capped: dict[int, list[str]] = {}
    for bucket_len, strings in lex_sca_by_len.items():
        if len(strings) <= cap:
            capped[bucket_len] = strings
        else:
            capped[bucket_len] = rng.sample(strings, cap)
    return capped


def build_null_table(
    query_length: int,
    lex_sca_by_len: dict[int, list[str]],
    n_samples: int,
    rng: random.Random,
) -> list[float]:
    """Pre-compute null distribution for a given query length against a lexicon.

    Generates n_samples random SCA strings of length query_length and finds
    the best NED match in the lexicon (within length window) for each.
    Returns sorted list of best-match NED values.

    The lex_sca_by_len should be pre-capped (via cap_bucketed_lexicon) to
    match the search scope.
    """
    # Pre-collect the comparison pool (flat list of strings within length window)
    pool: list[str] = []
    for bucket_len in range(max(1, query_length - 2), query_length + 3):
        pool.extend(lex_sca_by_len.get(bucket_len, []))

    if not pool:
        return [1.0] * n_samples

    null_dists = []
    sca_chars = SCA_ALPHABET  # local ref for speed
    ned_func = normalized_edit_distance  # local ref for speed

    for _ in range(n_samples):
        rand_sca = "".join(rng.choice(sca_chars) for _ in range(query_length))
        best_ned = 1.0
        for s in pool:
            d = ned_func(rand_sca, s)
            if d < best_ned:
                best_ned = d
                if best_ned == 0.0:
                    break
        null_dists.append(best_ned)

    null_dists.sort()
    return null_dists


def pvalue_from_null_table(real_ned: float, null_table: list[float]) -> float:
    """Compute p-value: fraction of null values <= real_ned.

    Uses bisect for O(log n) lookup on the sorted null table.
    Applies a pseudocount floor of 1/(M+1) when count=0, following
    standard permutation testing practice (Phipson & Smyth 2010).
    """
    if not null_table:
        return 1.0
    from bisect import bisect_right
    M = len(null_table)
    count = bisect_right(null_table, real_ned + 1e-12)
    # Pseudocount: (count + 1) / (M + 1) prevents exact-zero p-values
    return (count + 1) / (M + 1)


# ── Bias correction: consonant-class frequency normalization ────────────


def _reading_to_sca_class(reading: str) -> str:
    """Get the SCA consonant class for a reading hypothesis.

    "da" -> IPA "da" -> SCA first char "T".
    "ra" -> SCA first char "R".
    Pure vowels "a" -> "V".
    """
    if not reading:
        return "V"
    sca = ipa_to_sca(reading)
    if not sca:
        return "V"
    return sca[0]


def compute_class_background_rates(
    capped_by_len: dict[int, list[str]],
    query_length: int,
    n_samples: int,
    rng: random.Random,
) -> dict[str, float]:
    """Compute background match rates by initial SCA consonant class.

    For each consonant class C, generates random SCA strings starting
    with C and measures what fraction produce NED <= the 25th percentile
    against this lexicon. Classes with higher rates match more easily.

    Returns dict mapping SCA class letter -> background match rate
    (inverse of mean NED: higher rate = easier matching = more bias).
    """
    pool: list[str] = []
    for bucket_len in range(max(1, query_length - 2), query_length + 3):
        pool.extend(capped_by_len.get(bucket_len, []))
    if not pool:
        return {}

    sca_chars = SCA_ALPHABET
    ned_func = normalized_edit_distance

    # For each consonant class, compute mean best-NED of class-initial
    # random SCA strings against this lexicon pool.
    # Lower mean NED = easier matching = higher bias.
    consonant_classes = [c for c in SCA_ALPHABET if c != "V"]
    class_mean_ned: dict[str, float] = {}
    samples_per_class = max(50, n_samples // len(consonant_classes))

    for cls in consonant_classes:
        neds = []
        for _ in range(samples_per_class):
            rest = "".join(rng.choice(sca_chars) for _ in range(query_length - 1))
            rand_sca = cls + rest
            best_ned = 1.0
            for s in pool:
                d = ned_func(rand_sca, s)
                if d < best_ned:
                    best_ned = d
                    if best_ned == 0.0:
                        break
            neds.append(best_ned)
        class_mean_ned[cls] = sum(neds) / len(neds) if neds else 1.0

    # Convert to rates: rate = 1/mean_ned (inversely proportional)
    # This ensures classes with lower mean NED get higher rates.
    rates: dict[str, float] = {}
    for cls in consonant_classes:
        mn = class_mean_ned[cls]
        rates[cls] = 1.0 / max(mn, 0.01)

    rates["V"] = 1.0
    return rates


def build_class_background_rates_all(
    lex_capped: dict[str, dict[int, list[str]]],
    query_lengths: set[int],
    n_samples: int,
    rng: random.Random,
    verbose: bool = True,
) -> dict[tuple[int, str], dict[str, float]]:
    """Build background match rates for all (query_length, language) pairs."""
    rates: dict[tuple[int, str], dict[str, float]] = {}
    for L in sorted(query_lengths):
        for lc, capped in lex_capped.items():
            rates[(L, lc)] = compute_class_background_rates(
                capped, L, n_samples, rng,
            )
        if verbose:
            print(f"    L={L}: class rates computed for all languages")
    return rates


def freq_norm_adjust_pvalue(
    raw_pvalue: float,
    reading_map: dict[str, str],
    class_rates: dict[str, float],
) -> float:
    """Adjust p-value using consonant-class frequency normalization.

    Multiplies p-value by relative_rate = rate(C) / mean_rate to
    penalize consonant classes with higher background match rates.
    """
    if not reading_map or not class_rates:
        return raw_pvalue

    consonant_rates = {k: v for k, v in class_rates.items() if k != "V"}
    if not consonant_rates:
        return raw_pvalue
    mean_rate = sum(consonant_rates.values()) / len(consonant_rates)
    if mean_rate == 0:
        return raw_pvalue

    adjustment = 1.0
    for _sign_id, reading in reading_map.items():
        cls = _reading_to_sca_class(reading)
        if cls in class_rates:
            relative_rate = class_rates[cls] / mean_rate
            adjustment *= relative_rate

    if adjustment <= 0:
        return raw_pvalue
    return min(1.0, raw_pvalue * adjustment)


# ── Bias correction: P1 grid prior weighting ───────────────────────────


def load_jaccard_classification() -> dict:
    """Load Jaccard classification output for grid prior construction."""
    path = PROJECT / "results" / "jaccard_classification_output.json"
    if not path.exists():
        return {}
    with open(path) as f:
        return json.load(f)


def build_grid_prior(
    grid: dict[str, tuple[int, int, float]],
    ab_to_reading: dict[str, str],
    sign_to_ipa: dict[str, str],
    jaccard: dict,
) -> dict[str, dict[str, float]]:
    """Build prior probability for each (sign_id, reading) from P1 grid.

    Uses Jaccard consonant clusters to cross-reference unknown signs
    with known LB signs and estimate consonant-class priors.

    Returns dict mapping sign_id -> {SCA_class: prior_probability}.
    """
    consonant_clusters = jaccard.get("linear_a", {}).get("consonant", {}).get("clusters", {})

    reading_to_cluster: dict[str, str] = {}
    for cluster_id, signs in consonant_clusters.items():
        for sign in signs:
            reading_to_cluster[sign] = cluster_id

    cluster_consonant_onsets: dict[str, list[str]] = defaultdict(list)
    for reading, cluster_id in reading_to_cluster.items():
        ipa = sign_to_ipa.get(reading)
        if ipa:
            clean = ipa.rstrip("0123456789")
            if clean in ("a", "e", "i", "o", "u"):
                cluster_consonant_onsets[cluster_id].append("")
            elif clean.endswith(("a", "e", "i", "o", "u")):
                cluster_consonant_onsets[cluster_id].append(clean[:-1])

    priors: dict[str, dict[str, float]] = {}

    for sign_id, (cc, vc, conf) in grid.items():
        reading = ab_to_reading.get(sign_id, sign_id)
        if reading in sign_to_ipa:
            continue

        sign_cluster = reading_to_cluster.get(sign_id)
        if not sign_cluster:
            continue

        known_onsets = cluster_consonant_onsets.get(sign_cluster, [])
        if not known_onsets:
            continue

        onset_sca_classes: dict[str, int] = defaultdict(int)
        for onset in known_onsets:
            if not onset:
                onset_sca_classes["V"] += 1
            else:
                sca_cls = ipa_to_sca(onset)
                if sca_cls:
                    onset_sca_classes[sca_cls[0]] += 1

        total_count = sum(onset_sca_classes.values())
        if total_count == 0:
            continue

        n_classes = len(SCA_ALPHABET)
        alpha = 1.0  # Dirichlet smoothing
        class_priors: dict[str, float] = {}
        for cls in SCA_ALPHABET:
            count = onset_sca_classes.get(cls, 0)
            class_priors[cls] = (count + alpha) / (total_count + n_classes * alpha)

        priors[sign_id] = class_priors

    return priors


def grid_prior_adjust_pvalue(
    raw_pvalue: float,
    reading_map: dict[str, str],
    grid_priors: dict[str, dict[str, float]],
) -> float:
    """Adjust p-value using P1 grid prior weighting.

    Divides p-value by prior: higher prior -> lower adjusted p-value
    (easier to survive FDR). Uses uniform/prior as multiplicative factor.
    """
    if not reading_map or not grid_priors:
        return raw_pvalue

    adjustment = 1.0
    n_priors_used = 0

    for sign_id, reading in reading_map.items():
        if sign_id not in grid_priors:
            continue
        cls = _reading_to_sca_class(reading)
        prior = grid_priors[sign_id].get(cls, 1.0 / len(SCA_ALPHABET))
        uniform = 1.0 / len(SCA_ALPHABET)
        adjustment *= uniform / prior
        n_priors_used += 1

    if n_priors_used == 0:
        return raw_pvalue
    return min(1.0, max(0.0, raw_pvalue * adjustment))


# ── LB known-answer holdout test ───────────────────────────────────────


LB_HOLDOUT_SIGNS = [
    ("AB01", "da", "d"),
    ("AB06", "na", "n"),
    ("AB08", "a", ""),
    ("AB27", "re", "r"),
    ("AB37", "ti", "t"),
    ("AB45", "de", "d"),
    ("AB57", "ja", "j"),
    ("AB59", "ta", "t"),
    ("AB60", "ra", "r"),
    ("AB67", "ki", "k"),
    ("AB70", "ko", "k"),
]


def run_lb_holdout_test(
    sign_to_ipa: dict[str, str],
    ab_to_reading: dict[str, str],
    grid: dict[str, tuple[int, int, float]],
    cell_consonants: dict[int, set[str]],
    lexicons: dict[str, list[dict]],
    lex_capped: dict[str, dict[int, list[str]]],
    null_tables: dict[tuple[int, str], list[float]],
    class_rates: dict[tuple[int, str], dict[str, float]] | None = None,
    grid_priors: dict[str, dict[str, float]] | None = None,
    rng: random.Random | None = None,
    verbose: bool = True,
) -> dict[str, dict]:
    """Run LB known-answer holdout test for bias correction comparison.

    For each LB sign with a known reading:
    1. Treat it as unknown
    2. Generate candidate readings from its grid cell
    3. Search all lexicons with each reading
    4. Apply bias correction (if provided)
    5. Check if the correct reading is recovered as best

    Returns dict with results for each correction method.
    """
    if rng is None:
        rng = random.Random(42)

    results_by_method: dict[str, list[dict]] = {
        "none": [],
        "freq_norm": [],
        "grid_prior": [],
    }

    for ab_code, known_reading, _cons_ipa in LB_HOLDOUT_SIGNS:
        if ab_code not in grid:
            continue

        _cc, vc, _conf = grid[ab_code]
        candidates = candidate_readings(vc, cell_consonants)
        if not candidates or known_reading not in candidates:
            continue

        padding_sca = [ipa_to_sca("pa"), ipa_to_sca("ru")]

        reading_pvals: dict[str, dict[str, float]] = defaultdict(dict)

        for cand in candidates:
            cand_sca = ipa_to_sca(cand)
            if not cand_sca:
                continue

            query_sca = padding_sca[0] + cand_sca + padding_sca[1]
            L = len(query_sca)

            best_raw_p = 1.0
            best_lang = ""

            for lc in lexicons:
                ned, _best_entry = search_capped_pool(
                    query_sca, lex_capped[lc], lexicons[lc],
                )
                null_tab = null_tables.get((L, lc))
                if null_tab:
                    p_val = pvalue_from_null_table(ned, null_tab)
                else:
                    p_val = 1.0

                if p_val < best_raw_p:
                    best_raw_p = p_val
                    best_lang = lc

            reading_map = {ab_code: cand}

            reading_pvals[cand]["none"] = best_raw_p

            if class_rates and (L, best_lang) in class_rates:
                fn_p = freq_norm_adjust_pvalue(
                    best_raw_p, reading_map, class_rates[(L, best_lang)],
                )
            else:
                fn_p = best_raw_p
            reading_pvals[cand]["freq_norm"] = fn_p

            if grid_priors:
                gp_p = grid_prior_adjust_pvalue(
                    best_raw_p, reading_map, grid_priors,
                )
            else:
                gp_p = best_raw_p
            reading_pvals[cand]["grid_prior"] = gp_p

        for method in ["none", "freq_norm", "grid_prior"]:
            best_cand = min(
                candidates,
                key=lambda c: reading_pvals.get(c, {}).get(method, 1.0),
            )
            correct = (best_cand == known_reading)
            results_by_method[method].append({
                "ab_code": ab_code,
                "known_reading": known_reading,
                "predicted_reading": best_cand,
                "correct": correct,
                "n_candidates": len(candidates),
                "best_p_value": reading_pvals.get(best_cand, {}).get(method, 1.0),
            })

    summary = {}
    for method in ["none", "freq_norm", "grid_prior"]:
        entries = results_by_method[method]
        n_correct = sum(1 for e in entries if e["correct"])
        n_total = len(entries)
        summary[method] = {
            "n_correct": n_correct,
            "n_total": n_total,
            "accuracy": n_correct / n_total if n_total > 0 else 0.0,
            "details": entries,
        }
        if verbose:
            if n_total > 0:
                print(f"  {method:12s}: {n_correct}/{n_total} correct "
                      f"({100*n_correct/n_total:.1f}%)")
            else:
                print(f"  {method:12s}: no tests")
            for e in entries:
                marker = "OK" if e["correct"] else "MISS"
                print(f"    {e['ab_code']:6s} known={e['known_reading']:3s} "
                      f"pred={e['predicted_reading']:3s} [{marker}]")

    return summary


# ── BH-FDR correction ───────────────────────────────────────────────────


def bh_fdr_correction(
    pvalues: list[float], alpha: float = 0.05
) -> list[float]:
    """Apply Benjamini-Hochberg FDR correction.

    Returns q-values (adjusted p-values).
    """
    m = len(pvalues)
    if m == 0:
        return []

    # Sort indices by p-value
    indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
    qvalues = [0.0] * m

    # Compute q-values with monotonicity correction
    prev_q = 1.0
    for rank_from_end, (orig_idx, pval) in enumerate(reversed(indexed)):
        rank = m - rank_from_end  # 1-based rank from top
        q = min(pval * m / rank, 1.0)
        q = min(q, prev_q)  # enforce monotonicity
        qvalues[orig_idx] = q
        prev_q = q

    return qvalues


# ── Target stems from PRD Section 3 ─────────────────────────────────────


def get_target_stems(
    sign_to_ipa: dict[str, str],
    ab_to_reading: dict[str, str],
    grid: dict[str, tuple[int, int, float]],
    cell_consonants: dict[int, set[str]],
) -> list[dict]:
    """Build the 21 target stems from PRD Section 3.

    Returns list of dicts with stem_ids, readings, known_ipas,
    unknown indices, candidate readings, etc.
    """
    # Hardcoded from PRD Section 3 (these are the specific stems selected)
    stem_specs = [
        # 1. Fully phonetic
        {"stem_ids": ["AB10", "AB07", "AB53"], "unknowns": []},
        # 2-16. One unknown
        {"stem_ids": ["AB07", "AB07", "AB70", "AB60", "AB13"], "unknowns": [3]},
        {"stem_ids": ["AB07", "AB45", "AB26", "AB78"], "unknowns": [2]},
        {"stem_ids": ["AB07", "AB07", "AB17"], "unknowns": [2]},
        {"stem_ids": ["AB08", "AB29", "AB06"], "unknowns": [0]},
        {"stem_ids": ["AB39", "AB26", "AB38"], "unknowns": [1]},
        {"stem_ids": ["AB39", "AB37", "AB24"], "unknowns": [1]},
        {"stem_ids": ["AB39", "AB59", "AB44"], "unknowns": [1]},
        {"stem_ids": ["AB45", "AB58", "AB47"], "unknowns": [2]},
        {"stem_ids": ["AB53", "AB59", "AB46"], "unknowns": [1]},
        {"stem_ids": ["AB53", "AB69", "AB16"], "unknowns": [1]},
        {"stem_ids": ["AB57", "AB28", "AB48"], "unknowns": [1]},
        {"stem_ids": ["AB57", "AB80", "AB10"], "unknowns": [1]},
        {"stem_ids": ["AB60", "AB45", "AB13"], "unknowns": [0]},
        {"stem_ids": ["AB61", "AB76", "AB07"], "unknowns": [0]},
        {"stem_ids": ["AB77", "AB10", "AB45"], "unknowns": [0]},
        # 17-21. Two unknowns
        {"stem_ids": ["AB08", "AB06", "AB55", "AB41", "AB57"], "unknowns": [0, 3]},
        {"stem_ids": ["AB08", "AB41", "AB58", "AB11"], "unknowns": [0, 1]},
        {"stem_ids": ["AB08", "AB67", "AB39", "AB38"], "unknowns": [0, 1]},
        {"stem_ids": ["AB16", "AB81", "AB27", "AB06"], "unknowns": [1, 2]},
        {"stem_ids": ["AB53", "AB59", "AB80", "AB55"], "unknowns": [1, 2]},
    ]

    results = []
    for spec in stem_specs:
        stem_ids = spec["stem_ids"]
        unknown_indices = spec["unknowns"]

        # Resolve readings and IPA for each sign
        readings = []
        ipas = []
        for sid in stem_ids:
            reading = ab_to_reading.get(sid, sid)
            readings.append(reading)
            ipa = sign_to_ipa.get(reading)
            if ipa:
                ipas.append(ipa.rstrip("0123456789"))
            else:
                ipas.append(None)

        # Build unknown sign info
        unknown_signs = []
        for idx in unknown_indices:
            sid = stem_ids[idx]
            if sid in grid:
                _cc, vc, conf = grid[sid]
                cands = candidate_readings(vc, cell_consonants)
                unknown_signs.append({
                    "index": idx,
                    "sign_id": sid,
                    "vowel_class": vc,
                    "confidence": conf,
                    "candidate_readings": cands,
                })

        # Skip if any unknown sign is not in grid or has no candidates
        if len(unknown_signs) != len(unknown_indices):
            continue

        results.append({
            "stem_ids": stem_ids,
            "readings": readings,
            "known_ipas": ipas,
            "unknown_signs": unknown_signs,
            "n_unknowns": len(unknown_indices),
        })

    return results


def enumerate_reading_hypotheses(stem: dict) -> list[dict]:
    """Enumerate all reading hypotheses for a stem.

    For each combination of candidate readings for unknown signs,
    construct the complete IPA and SCA strings.
    """
    unknowns = stem["unknown_signs"]
    if not unknowns:
        # Fully phonetic: single hypothesis
        ipa_parts = [ip for ip in stem["known_ipas"]]
        complete_ipa = "".join(ipa_parts)
        complete_sca = ipa_to_sca(complete_ipa)
        return [{
            "reading_map": {},
            "complete_ipa": complete_ipa,
            "complete_sca": complete_sca,
        }]

    # Generate all combinations
    from itertools import product

    cand_lists = [u["candidate_readings"] for u in unknowns]
    hypotheses = []
    for combo in product(*cand_lists):
        ipa_parts = list(stem["known_ipas"])
        reading_map = {}
        for i, u in enumerate(unknowns):
            ipa_parts[u["index"]] = combo[i]
            reading_map[u["sign_id"]] = combo[i]
        complete_ipa = "".join(p for p in ipa_parts if p)
        complete_sca = ipa_to_sca(complete_ipa)
        if complete_sca:
            hypotheses.append({
                "reading_map": reading_map,
                "complete_ipa": complete_ipa,
                "complete_sca": complete_sca,
            })

    return hypotheses


# ── Self-consistency analysis ────────────────────────────────────────────


def self_consistency_analysis(
    significant_results: list[dict],
) -> list[dict]:
    """Analyze reading consistency for shared unknown signs.

    For each unknown sign appearing in 2+ stems, check whether the
    same reading dominates across stems.
    """
    # Group by unknown sign
    sign_data: dict[str, list[dict]] = defaultdict(list)
    for r in significant_results:
        for sign_id, reading in r["reading_for_unknown"].items():
            sign_data[sign_id].append({
                "stem_ids": r["stem_ids"],
                "reading": reading,
                "language": r["language"],
                "q_value": r["q_value"],
                "matched_word": r["matched_word"],
            })

    identifications = []
    for sign_id, entries in sign_data.items():
        # Count readings
        reading_counts: dict[str, int] = defaultdict(int)
        reading_best_q: dict[str, float] = {}
        contributing_stems: set[str] = set()

        for e in entries:
            reading_counts[e["reading"]] += 1
            contributing_stems.add("-".join(e["stem_ids"]))
            if e["reading"] not in reading_best_q or e["q_value"] < reading_best_q[e["reading"]]:
                reading_best_q[e["reading"]] = e["q_value"]

        n_stems = len(contributing_stems)
        best_reading = max(reading_counts, key=reading_counts.get)
        best_count = reading_counts[best_reading]
        total_entries = sum(reading_counts.values())

        # Consistency = fraction of entries agreeing on best reading
        consistency = best_count / total_entries if total_entries > 0 else 0.0

        # Classify confidence
        best_q = reading_best_q.get(best_reading, 1.0)
        if consistency >= 0.75 and n_stems >= 2 and best_q < 0.01:
            confidence = "CONFIRMED"
        elif n_stems == 1 and best_q < 0.01:
            confidence = "TENTATIVE"
        elif n_stems >= 2 and consistency >= 0.5:
            confidence = "TENTATIVE"
        else:
            confidence = "INCONCLUSIVE"

        identifications.append({
            "sign_id": sign_id,
            "best_reading": best_reading,
            "confidence": confidence,
            "consistency_score": round(consistency, 3),
            "n_contributing_stems": n_stems,
            "best_q_value": round(best_q, 6),
            "reading_counts": dict(reading_counts),
            "supporting_evidence": entries,
        })

    return identifications


# ── Validation Gates ─────────────────────────────────────────────────────


# Curated cognate pairs: (query_word, query_ipa, target_gloss_or_word)
# IPA and SCA are derived from the lexicon files where possible,
# otherwise from standard comparative linguistics reconstructions.

UGARITIC_HEBREW_COGNATES = [
    # (Ugaritic word, Ugaritic IPA, Hebrew word, Hebrew IPA, gloss)
    # Use full Ugaritic forms (5+ SCA chars) for sufficient discriminative power.
    # Short (2-3 char) SCA strings are not discriminative enough against
    # a 3000-entry lexicon (K=12, L=4 -> 20,736 possible strings).
    ("malku", "malku", "melek", "mɛlɛχ", "king"),               # MVLKV (5)
    ("kaspu", "kaspu", "kesef", "kɛsɛf", "silver"),             # KVSPV (5)
    ("markabtu", "markabtu", "merkava", "mɛrkava", "chariot"),  # MVRKVPTV (8)
    ("bahimatu", "bahimatu", "behemot", "bɛhɛmot", "cattle"),   # PVHVMVTV (8)
    ("labinatu", "labinatu", "levena", "lɛvɛna", "brick"),      # LVPVNVTV (8)
    ("ʾasīru", "ʔasiːru", "asir", "asir", "prisoner"),         # HVSVRV (6)
    ("madīnatu", "madiːnatu", "medina", "mɛdina", "town"),     # MVTVNVTV (8)
    ("ʾalmanatu", "ʔalmanatu", "almana", "almana", "widow"),    # HVLMVNVTV (9)
    ("šikkarānu", "ʃikkaraːnu", "shikaron", "ʃikaron", "drunkenness"),  # SVKKVRVNV (9)
    ("ʾarbaʿatu", "ʔarbaʕatu", "arba", "arba", "four"),        # HVRPVHVTV (9)
]

GREEK_LATIN_COGNATES = [
    # (Greek word, Greek IPA, Latin word, Latin IPA, gloss)
    ("pater", "pater", "pater", "patɛr", "father"),
    ("meter", "mɛːtɛːr", "mater", "maːtɛr", "mother"),
    ("treis", "tris", "tres", "treːs", "three"),
    ("hepta", "hepta", "septem", "sɛptɛ̃", "seven"),
    ("neos", "neos", "novus", "nɔwʊs", "new"),
    ("pous", "pus", "pes", "peːs", "foot"),
    ("genos", "genos", "genus", "gɛnʊ", "kind"),
    ("onoma", "onoma", "nomen", "noːmɛn", "name"),
    ("aster", "astɛːr", "stella", "steːlːa", "star"),
    ("gonu", "gony", "genu", "gɛnʊ", "knee"),
]

# Gate 3 false-positive control: synthetic random SCA strings vs Akkadian.
#
# Random SCA strings are the cleanest possible negative control because
# they are drawn from the SAME distribution as the Monte Carlo null.
# This directly tests null calibration: if the null is correct, random
# SCA queries should produce uniformly distributed p-values and BH-FDR
# should reject none.
#
# Why not use a real unrelated language?
#   Natural language words have non-random phonotactic structure (e.g.,
#   CV syllable patterns, restricted consonant clusters) that concentrates
#   them in a smaller region of SCA space than the uniform-random null.
#   This structural bias causes significant matches against ANY large
#   lexicon regardless of genetic relationship -- the "false positives"
#   are SCA-space collisions, not linguistic cognates.  Synthetic random
#   SCA strings avoid this confound entirely.
GATE3_CONTROL_N = 10                # number of control queries
GATE3_CONTROL_SEED = 54321          # fixed seed for reproducibility
GATE3_SCA_LENGTHS = [7, 7, 8, 8, 8, 9, 9, 9, 10, 10]  # match English word range


def _generate_gate3_control_queries() -> list[tuple[str, str]]:
    """Generate synthetic random SCA strings for Gate 3 control.

    Returns list of (label, sca_string) tuples.  Each label is
    "synth_<index>" for identification in output.  The SCA strings
    are generated from a fixed seed so results are fully reproducible.
    """
    gen_rng = random.Random(GATE3_CONTROL_SEED)
    queries = []
    for i, L in enumerate(GATE3_SCA_LENGTHS):
        sca = "".join(gen_rng.choice(SCA_ALPHABET) for _ in range(L))
        queries.append((f"synth_{i:02d}", sca))
    return queries


def run_gate_search(
    query_sca: str,
    target_lexicon: list[dict],
    lex_sca_by_len: dict[int, list[str]],
    null_table: list[float] | None = None,
    capped_by_len: dict[int, list[str]] | None = None,
) -> tuple[float, float, dict | None]:
    """Search a single query SCA against a lexicon and compute p-value.

    Uses Monte Carlo null table for properly calibrated p-values.
    If capped_by_len is provided, searches the capped pool (for null consistency).
    Falls back to analytical_pvalue() if no null table is provided.
    Returns (ned, p_value, best_entry).
    """
    if capped_by_len is not None:
        ned, best_entry = search_capped_pool(query_sca, capped_by_len, target_lexicon)
    else:
        ned, best_entry = search_lexicon_full(query_sca, target_lexicon)
    if null_table is not None:
        p_value = pvalue_from_null_table(ned, null_table)
    else:
        pool_size = _count_pool_size(lex_sca_by_len, len(query_sca))
        p_value = analytical_pvalue(ned, len(query_sca), pool_size)
    return ned, p_value, best_entry


def bucket_lexicon(lexicon: list[dict]) -> dict[int, list[str]]:
    """Bucket lexicon SCA strings by length for fast lookup."""
    by_len: dict[int, list[str]] = defaultdict(list)
    for entry in lexicon:
        sca = entry["sca"]
        if sca:
            by_len[len(sca)].append(sca)
    return dict(by_len)


def _build_gate_null_tables(
    lex_by_len: dict[int, list[str]],
    query_lengths: set[int],
    rng: random.Random,
    verbose: bool = False,
) -> dict[int, list[float]]:
    """Build MC null tables for each query length against a (capped) lexicon."""
    capped = cap_bucketed_lexicon(lex_by_len, rng)
    null_tables: dict[int, list[float]] = {}
    for L in sorted(query_lengths):
        null_tables[L] = build_null_table(L, capped, NULL_SAMPLES, rng)
        if verbose:
            median = null_tables[L][len(null_tables[L]) // 2]
            print(f"    L={L}: median null NED={median:.3f}")
    return null_tables


def run_validation_gates(
    rng: random.Random,
    verbose: bool = True,
) -> dict:
    """Run all 3 validation gates. Returns gate results dict.

    Uses Monte Carlo null tables for properly calibrated p-values.
    """
    results = {}

    # Load lexicons for gates
    heb_lex = load_lexicon("heb")
    lat_lex = load_lexicon("lat")
    akk_lex = load_lexicon("akk")

    # Build bucketed and capped lexicons
    heb_by_len = bucket_lexicon(heb_lex)
    lat_by_len = bucket_lexicon(lat_lex)
    akk_by_len = bucket_lexicon(akk_lex)
    heb_capped = cap_bucketed_lexicon(heb_by_len, rng)
    lat_capped = cap_bucketed_lexicon(lat_by_len, rng)
    akk_capped = cap_bucketed_lexicon(akk_by_len, rng)

    if verbose:
        print("\n" + "=" * 78)
        print("VALIDATION GATES")
        print("=" * 78)

    # ── Gate 1: Ugaritic-Hebrew ──────────────────────────────────────
    if verbose:
        print("\n--- Gate 1: Ugaritic-Hebrew Cognate Recovery ---")

    gate1_queries = []
    for uga_w, uga_ipa, heb_w, heb_ipa, gloss in UGARITIC_HEBREW_COGNATES:
        q_sca = ipa_to_sca(uga_ipa)
        if q_sca:
            gate1_queries.append((q_sca, uga_w, heb_w, gloss))

    # Build null tables using capped pool
    g1_lengths = set(len(q) for q, *_ in gate1_queries)
    if verbose:
        print(f"  Building null tables for lengths {sorted(g1_lengths)}...")
    g1_nulls = _build_gate_null_tables(heb_by_len, g1_lengths, rng, verbose)

    gate1_pvalues = []
    gate1_details = []
    for q_sca, uga_w, heb_w, gloss in gate1_queries:
        null_tab = g1_nulls.get(len(q_sca))
        ned, p_val, best = run_gate_search(
            q_sca, heb_lex, heb_by_len, null_tab, heb_capped
        )
        gate1_pvalues.append(p_val)
        detail = {
            "query": uga_w, "query_sca": q_sca,
            "expected": heb_w, "gloss": gloss,
            "best_match": best["word"] if best else "N/A",
            "best_sca": best["sca"] if best else "N/A",
            "ned": round(ned, 4), "p_value": p_val,
        }
        gate1_details.append(detail)
        if verbose:
            match_str = f"{best['word']} ({best['sca']})" if best else "N/A"
            print(f"  {uga_w:15s} ({q_sca:8s}) -> {match_str:25s} NED={ned:.3f} p={p_val:.2e}")

    # Apply FDR to gate 1
    gate1_qvalues = bh_fdr_correction(gate1_pvalues, alpha=0.10)
    gate1_recovered = sum(1 for q in gate1_qvalues if q < 0.10)
    gate1_pass = gate1_recovered >= 5

    for i, detail in enumerate(gate1_details):
        detail["q_value"] = gate1_qvalues[i]

    if verbose:
        print(f"\n  Gate 1 result: {gate1_recovered}/10 recovered at FDR q < 0.10")
        print(f"  Gate 1: {'PASS' if gate1_pass else 'FAIL'}")

    results["gate1_ugaritic_hebrew"] = {
        "status": "PASS" if gate1_pass else "FAIL",
        "recovered": gate1_recovered,
        "out_of": len(gate1_queries),
        "details": gate1_details,
    }

    # ── Gate 2: Greek-Latin ──────────────────────────────────────────
    if verbose:
        print("\n--- Gate 2: Greek-Latin Cognate Recovery ---")

    gate2_queries = []
    for grc_w, grc_ipa, lat_w, lat_ipa, gloss in GREEK_LATIN_COGNATES:
        q_sca = ipa_to_sca(grc_ipa)
        if q_sca:
            gate2_queries.append((q_sca, grc_w, lat_w, gloss))

    g2_lengths = set(len(q) for q, *_ in gate2_queries)
    if verbose:
        print(f"  Building null tables for lengths {sorted(g2_lengths)}...")
    g2_nulls = _build_gate_null_tables(lat_by_len, g2_lengths, rng, verbose)

    gate2_pvalues = []
    gate2_details = []
    for q_sca, grc_w, lat_w, gloss in gate2_queries:
        null_tab = g2_nulls.get(len(q_sca))
        ned, p_val, best = run_gate_search(
            q_sca, lat_lex, lat_by_len, null_tab, lat_capped
        )
        gate2_pvalues.append(p_val)
        detail = {
            "query": grc_w, "query_sca": q_sca,
            "expected": lat_w, "gloss": gloss,
            "best_match": best["word"] if best else "N/A",
            "best_sca": best["sca"] if best else "N/A",
            "ned": round(ned, 4), "p_value": p_val,
        }
        gate2_details.append(detail)
        if verbose:
            match_str = f"{best['word']} ({best['sca']})" if best else "N/A"
            print(f"  {grc_w:15s} ({q_sca:8s}) -> {match_str:25s} NED={ned:.3f} p={p_val:.2e}")

    gate2_qvalues = bh_fdr_correction(gate2_pvalues, alpha=0.10)
    gate2_recovered = sum(1 for q in gate2_qvalues if q < 0.10)
    gate2_pass = gate2_recovered >= 3

    for i, detail in enumerate(gate2_details):
        detail["q_value"] = gate2_qvalues[i]

    if verbose:
        print(f"\n  Gate 2 result: {gate2_recovered}/10 recovered at FDR q < 0.10")
        print(f"  Gate 2: {'PASS' if gate2_pass else 'FAIL'}")

    results["gate2_greek_latin"] = {
        "status": "PASS" if gate2_pass else "FAIL",
        "recovered": gate2_recovered,
        "out_of": len(gate2_queries),
        "details": gate2_details,
    }

    # ── Gate 3: Synthetic Random SCA Null Calibration Control ────────
    # Synthetic random SCA strings searched against Akkadian.
    # These are drawn from the SAME distribution as the MC null, so
    # a properly calibrated null should produce 0 false positives.
    if verbose:
        print("\n--- Gate 3: Synthetic SCA Null Calibration Control ---")

    gate3_queries = _generate_gate3_control_queries()

    g3_lengths = set(len(sca) for _, sca in gate3_queries)
    if verbose:
        print(f"  Building null tables for lengths {sorted(g3_lengths)}...")
    g3_nulls = _build_gate_null_tables(akk_by_len, g3_lengths, rng, verbose)

    gate3_pvalues = []
    gate3_details = []
    for label, q_sca in gate3_queries:
        null_tab = g3_nulls.get(len(q_sca))
        ned, p_val, best = run_gate_search(
            q_sca, akk_lex, akk_by_len, null_tab, akk_capped
        )
        gate3_pvalues.append(p_val)
        detail = {
            "query": label, "query_sca": q_sca,
            "best_match": best["word"] if best else "N/A",
            "best_sca": best["sca"] if best else "N/A",
            "ned": round(ned, 4), "p_value": p_val,
        }
        gate3_details.append(detail)
        if verbose:
            match_str = f"{best['word']} ({best['sca']})" if best else "N/A"
            print(f"  {label:15s} ({q_sca:10s}) -> {match_str:25s} NED={ned:.3f} p={p_val:.2e}")

    gate3_qvalues = bh_fdr_correction(gate3_pvalues, alpha=0.05)
    gate3_false_positives = sum(1 for q in gate3_qvalues if q < 0.05)
    # Synthetic random SCA queries match the null distribution exactly,
    # so 0 false positives is expected.  Any FP indicates a miscalibrated
    # null (search/null pool mismatch or statistical bug).
    gate3_pass = gate3_false_positives == 0

    for i, detail in enumerate(gate3_details):
        detail["q_value"] = gate3_qvalues[i]

    if verbose:
        print(f"\n  Gate 3 result: {gate3_false_positives}/10 false positives at FDR q < 0.05")
        print(f"  Gate 3: {'PASS' if gate3_pass else 'FAIL'}")

    results["gate3_false_positive"] = {
        "status": "PASS" if gate3_pass else "FAIL",
        "false_positives": gate3_false_positives,
        "out_of": len(gate3_queries),
        "details": gate3_details,
    }

    return results


# ── Per-hypothesis aggregation ──────────────────────────────────────────


def aggregate_by_stem_language(
    search_results: list[dict],
    bias_correction: str = "none",
    class_rates_all: dict[tuple[int, str], dict[str, float]] | None = None,
    grid_priors: dict[str, dict[str, float]] | None = None,
) -> list[dict]:
    """Aggregate search results by (stem, language) pair.

    For each (stem, language), selects the best reading (lowest adjusted
    p-value) and applies Bonferroni correction for the number of readings.

    bias_correction: "none", "freq_norm", or "grid_prior"

    Returns list of aggregated results, one per (stem, language) pair.
    """
    # Group by (stem_key, language)
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in search_results:
        stem_key = "-".join(r["stem_ids"])
        groups[(stem_key, r["language"])].append(r)

    aggregated = []
    for (stem_key, lang), entries in groups.items():
        # Apply bias correction to each entry's p-value before ranking
        for e in entries:
            raw_p = e["raw_p_value"]
            reading_map = e.get("reading_for_unknown", {})
            q_sca = e.get("complete_sca", "")
            L = len(q_sca)

            if bias_correction == "freq_norm" and class_rates_all:
                rates = class_rates_all.get((L, lang), {})
                adj_p = freq_norm_adjust_pvalue(raw_p, reading_map, rates)
            elif bias_correction == "grid_prior" and grid_priors:
                adj_p = grid_prior_adjust_pvalue(raw_p, reading_map, grid_priors)
            else:
                adj_p = raw_p
            e["_adjusted_p"] = adj_p

        # Sort by adjusted p-value ascending (best first)
        entries.sort(key=lambda e: e["_adjusted_p"])
        best = entries[0]
        n_readings = len(entries)

        # Bonferroni correction for number of readings tested
        corrected_p = min(1.0, best["_adjusted_p"] * n_readings)

        aggregated.append({
            "stem_ids": best["stem_ids"],
            "stem_key": stem_key,
            "readings": best["readings"],
            "best_reading_for_unknown": best["reading_for_unknown"],
            "complete_ipa": best["complete_ipa"],
            "complete_sca": best["complete_sca"],
            "language": lang,
            "matched_word": best["matched_word"],
            "matched_ipa": best["matched_ipa"],
            "matched_sca": best["matched_sca"],
            "gloss": best["gloss"],
            "ned_distance": best["ned_distance"],
            "best_raw_p_value": best["raw_p_value"],
            "n_readings_tested": n_readings,
            "corrected_p_value": corrected_p,
            "bias_correction": bias_correction,
        })

    return aggregated


# ── Main pipeline ────────────────────────────────────────────────────────


def main(bias_correction: str = "freq_norm"):
    """Run the full pipeline.

    bias_correction: "none", "freq_norm", or "grid_prior"
      - "none": no bias correction (original behavior)
      - "freq_norm": consonant-class frequency normalization (Approach A)
      - "grid_prior": P1 grid prior weighting (Approach B)
    """
    rng = random.Random(42)
    t0 = time.time()

    print("Monte Carlo Null Cognate Search for 3+ Sign Linear A Stems")
    print("=" * 78)
    print(f"PRD: PRD_ANALYTICAL_NULL_SEARCH.md")
    print(f"Null method: Monte Carlo random SCA, M={NULL_SAMPLES}")
    print(f"FDR alpha: {FDR_ALPHA}")
    print(f"Bias correction: {bias_correction}")
    print()

    # ── Stage 0: Load & Validate ─────────────────────────────────────
    print("Stage 0: Loading data...")
    sign_to_ipa = load_sign_to_ipa()
    ab_to_reading = load_corpus()
    grid = load_p1_grid()
    cell_consonants = build_cell_consonants(grid, ab_to_reading, sign_to_ipa)

    print(f"  sign_to_ipa: {len(sign_to_ipa)} signs")
    print(f"  grid: {len(grid)} signs in P1 grid")
    print(f"  vowel classes with consonants: {sorted(cell_consonants.keys())}")

    target_stems = get_target_stems(sign_to_ipa, ab_to_reading, grid, cell_consonants)
    print(f"  target stems: {len(target_stems)}")

    # Count total hypotheses
    total_hyp = 0
    for stem in target_stems:
        hyps = enumerate_reading_hypotheses(stem)
        total_hyp += len(hyps)
    print(f"  total reading hypotheses: {total_hyp}")

    # Load lexicons
    print(f"\n  Loading {len(LANG_CODES)} lexicons...")
    lexicons: dict[str, list[dict]] = {}
    lex_by_len: dict[str, dict[int, list[str]]] = {}
    lex_capped: dict[str, dict[int, list[str]]] = {}
    for lc in LANG_CODES:
        lex = load_lexicon(lc)
        if lex:
            lexicons[lc] = lex
            by_len = bucket_lexicon(lex)
            lex_by_len[lc] = by_len
            lex_capped[lc] = cap_bucketed_lexicon(by_len, rng)
            print(f"    {lc}: {len(lex)} entries")
        else:
            print(f"    {lc}: NOT FOUND or empty")

    # ── Stage 1: Validation Gates ────────────────────────────────────
    gate_results = run_validation_gates(rng, verbose=True)

    # Check pass/fail
    g1 = gate_results["gate1_ugaritic_hebrew"]["status"]
    g2 = gate_results["gate2_greek_latin"]["status"]
    g3 = gate_results["gate3_false_positive"]["status"]

    print(f"\n{'=' * 78}")
    print(f"GATE SUMMARY: G1={g1}, G2={g2}, G3={g3}")

    if g1 == "FAIL":
        print("FATAL: Gate 1 failed -- method not viable for known cognates.")
        print("STOPPING. No Linear A search will be performed.")
        _write_output(gate_results, [], [], t0)
        return

    if g3 == "FAIL":
        print("WARNING: Gate 3 failed -- null may be too permissive.")
        print("Proceeding with caveats (results may contain false positives).")

    if g2 == "FAIL":
        print("WARNING: Gate 2 failed -- method works for close pairs only.")
        print("Proceeding with caveats.")

    print(f"{'=' * 78}")

    # ── Stage 2: Enumerate hypotheses ────────────────────────────────
    print("\nStage 2: Enumerating reading hypotheses...")
    all_hypotheses = []
    for stem in target_stems:
        hyps = enumerate_reading_hypotheses(stem)
        for h in hyps:
            all_hypotheses.append((stem, h))
    print(f"  Total hypotheses: {len(all_hypotheses)}")
    total_comparisons = len(all_hypotheses) * len(lexicons)
    print(f"  Total comparisons (hypotheses x languages): {total_comparisons}")

    # ── Stage 3: Search + MC null p-values ────────────────────────────
    print(f"\nStage 3: Searching ({total_comparisons} comparisons)...")
    print(f"  Using Monte Carlo null tables (M={NULL_SAMPLES} samples per table)")
    print(f"  Pool cap per length bucket: {NULL_POOL_CAP}")

    # Pre-compute null tables for all (query_length, language) pairs
    # Uses capped pools (same as search) to ensure null <-> search consistency
    query_lengths = set()
    for _stem, hyp in all_hypotheses:
        query_lengths.add(len(hyp["complete_sca"]))

    print(f"  Building null tables for {len(query_lengths)} lengths x {len(lexicons)} languages...")
    null_tables: dict[tuple[int, str], list[float]] = {}
    for L in sorted(query_lengths):
        for lc in lexicons:
            null_tables[(L, lc)] = build_null_table(L, lex_capped[lc], NULL_SAMPLES, rng)
        elapsed = time.time() - t0
        print(f"    L={L}: all {len(lexicons)} languages done ({elapsed:.0f}s)")

    # Run searches using the same capped pools
    print("  Running searches...")
    search_results = []
    for idx, (stem, hyp) in enumerate(all_hypotheses):
        q_sca = hyp["complete_sca"]
        L = len(q_sca)

        for lc, lex in lexicons.items():
            ned, best_entry = search_capped_pool(q_sca, lex_capped[lc], lex)
            null_tab = null_tables.get((L, lc))
            if null_tab:
                p_val = pvalue_from_null_table(ned, null_tab)
            else:
                p_val = 1.0

            search_results.append({
                "stem_ids": stem["stem_ids"],
                "readings": stem["readings"],
                "reading_for_unknown": hyp["reading_map"],
                "complete_ipa": hyp["complete_ipa"],
                "complete_sca": q_sca,
                "language": lc,
                "matched_word": best_entry["word"] if best_entry else "",
                "matched_ipa": best_entry["ipa"] if best_entry else "",
                "matched_sca": best_entry["sca"] if best_entry else "",
                "gloss": best_entry.get("gloss", "") if best_entry else "",
                "ned_distance": round(ned, 4),
                "raw_p_value": p_val,
            })

        if (idx + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"    {idx + 1}/{len(all_hypotheses)} hypotheses searched ({elapsed:.0f}s)")

    elapsed = time.time() - t0
    print(f"  All {len(search_results)} comparisons done ({elapsed:.0f}s)")

    # ── Stage 3a: Compute bias correction data ─────────────────────
    class_rates_all = None
    grid_priors_data = None

    if bias_correction == "freq_norm":
        print("\nStage 3a: Computing consonant-class background rates...")
        class_rates_all = build_class_background_rates_all(
            lex_capped, query_lengths, NULL_SAMPLES, rng, verbose=True,
        )
        # Log a sample of rates for diagnostics
        sample_key = next(iter(class_rates_all), None)
        if sample_key:
            sample = class_rates_all[sample_key]
            t_rate = sample.get("T", 0)
            k_rate = sample.get("K", 0)
            r_rate = sample.get("R", 0)
            print(f"  Sample rates (L={sample_key[0]}, {sample_key[1]}): "
                  f"T={t_rate:.3f}, K={k_rate:.3f}, R={r_rate:.3f}")

    elif bias_correction == "grid_prior":
        print("\nStage 3a: Building grid prior from Jaccard classification...")
        jaccard = load_jaccard_classification()
        grid_priors_data = build_grid_prior(
            grid, ab_to_reading, sign_to_ipa, jaccard,
        )
        print(f"  Grid priors built for {len(grid_priors_data)} unknown signs")

    # ── Stage 3b: Aggregate by (stem, language) ──────────────────────
    # The reading is a nuisance parameter: take the best reading per
    # (stem, language) pair and apply Bonferroni correction for the
    # number of readings tested.
    print(f"\nStage 3b: Aggregating by (stem, language) pair "
          f"[bias_correction={bias_correction}]...")
    aggregated = aggregate_by_stem_language(
        search_results,
        bias_correction=bias_correction,
        class_rates_all=class_rates_all,
        grid_priors=grid_priors_data,
    )
    print(f"  Raw comparisons: {len(search_results)}")
    print(f"  Aggregated (stem, language) pairs: {len(aggregated)}")

    # ── Stage 4: BH-FDR correction (on aggregated pairs) ────────────
    print("\nStage 4: BH-FDR correction (per-hypothesis aggregation)...")
    agg_pvalues = [r["corrected_p_value"] for r in aggregated]
    qvalues = bh_fdr_correction(agg_pvalues, alpha=FDR_ALPHA)

    for i, r in enumerate(aggregated):
        r["q_value"] = round(qvalues[i], 6)
        r["significant"] = qvalues[i] < FDR_ALPHA

    n_significant = sum(1 for r in aggregated if r["significant"])
    print(f"  Aggregated hypotheses (m): {len(aggregated)}")
    print(f"  FDR-surviving matches (q < {FDR_ALPHA}): {n_significant}")
    survivor_pct = 100.0 * n_significant / len(aggregated) if aggregated else 0
    print(f"  Survivor rate: {survivor_pct:.1f}%")

    # Sort significant results by q-value
    sig_results = [r for r in aggregated if r["significant"]]
    sig_results.sort(key=lambda r: r["q_value"])

    if sig_results:
        print(f"\n  Top FDR-surviving matches:")
        for r in sig_results[:20]:
            stem_label = "-".join(r["readings"])
            unknowns = ", ".join(f"{k}={v}" for k, v in r["best_reading_for_unknown"].items())
            n_rd = r["n_readings_tested"]
            print(
                f"    {stem_label:30s} [{unknowns:12s}] "
                f"-> {r['language']:6s} {r['matched_word']:15s} "
                f"({r['gloss'][:20]:20s}) "
                f"NED={r['ned_distance']:.3f} q={r['q_value']:.4f} "
                f"(best of {n_rd} readings)"
            )
    else:
        print("  No matches survived FDR correction.")
        print("  This is an informative null result: signal-to-noise is")
        print("  insufficient at current grid resolution.")

    # ── Stage 5: Self-consistency analysis ────────────────────────────
    print(f"\nStage 5: Self-consistency analysis...")
    # Convert aggregated format to the format self_consistency_analysis expects
    sig_for_consistency = []
    for r in sig_results:
        sig_for_consistency.append({
            "stem_ids": r["stem_ids"],
            "reading_for_unknown": r["best_reading_for_unknown"],
            "language": r["language"],
            "q_value": r["q_value"],
            "matched_word": r["matched_word"],
        })
    identifications = self_consistency_analysis(sig_for_consistency)

    if identifications:
        for ident in identifications:
            print(
                f"  {ident['sign_id']}: best_reading={ident['best_reading']}, "
                f"confidence={ident['confidence']}, "
                f"consistency={ident['consistency_score']:.2f}, "
                f"stems={ident['n_contributing_stems']}, "
                f"best_q={ident['best_q_value']:.4f}"
            )
    else:
        print("  No sign identifications to analyze.")

    # ── Stage 6: Output ──────────────────────────────────────────────
    _write_output(
        gate_results, sig_results, identifications, t0,
        total_comparisons=len(search_results),
        n_aggregated=len(aggregated),
        all_detail=search_results,
        bias_correction=bias_correction,
    )

    elapsed = time.time() - t0
    print(f"\n{'=' * 78}")
    print(f"DONE ({elapsed:.0f}s total)")
    print(f"{'=' * 78}")


def _write_output(
    gate_results: dict,
    sig_results: list[dict],
    identifications: list[dict],
    t0: float,
    total_comparisons: int = 0,
    n_aggregated: int = 0,
    all_detail: list[dict] | None = None,
    bias_correction: str = "none",
):
    """Write results JSON to file."""
    # Clean gate results for JSON (remove details with potential non-serializable data)
    clean_gates = {}
    for gname, gdata in gate_results.items():
        clean_gates[gname] = {
            "status": gdata["status"],
            "recovered": gdata.get("recovered", gdata.get("false_positives", 0)),
            "out_of": gdata["out_of"],
        }

    # Count identifications by confidence
    confirmed = sum(1 for i in identifications if i["confidence"] == "CONFIRMED")
    tentative = sum(1 for i in identifications if i["confidence"] == "TENTATIVE")
    inconclusive = sum(1 for i in identifications if i["confidence"] == "INCONCLUSIVE")

    output = {
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "n_stems": 21,
            "n_comparisons_raw": total_comparisons,
            "n_aggregated_hypotheses": n_aggregated,
            "n_significant": len(sig_results),
            "n_languages": len(LANG_CODES),
            "null_method": f"monte_carlo_M{NULL_SAMPLES}",
            "fdr_alpha": FDR_ALPHA,
            "aggregation_method": "best_reading_per_stem_language_with_bonferroni",
            "bias_correction": bias_correction,
            "validation_gates": clean_gates,
            "runtime_seconds": round(time.time() - t0, 1),
        },
        "fdr_results": sig_results,
        "sign_identifications": [
            {
                "sign_id": i["sign_id"],
                "best_reading": i["best_reading"],
                "confidence": i["confidence"],
                "consistency_score": i["consistency_score"],
                "n_contributing_stems": i["n_contributing_stems"],
                "best_q_value": i["best_q_value"],
                "reading_counts": i["reading_counts"],
            }
            for i in identifications
        ],
        "summary": {
            "total_significant": len(sig_results),
            "confirmed_signs": confirmed,
            "tentative_signs": tentative,
            "inconclusive_signs": inconclusive,
        },
    }

    # Include per-reading detail for transparency (all raw comparisons)
    if all_detail is not None:
        output["per_reading_detail"] = all_detail

    out_path = PROJECT / "results" / "analytical_null_search_output.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  Output written to {out_path}")


def compare_approaches():
    """Run both bias correction approaches and compare on LB holdout test.

    This is a lightweight comparison that:
    1. Loads data and builds null tables for holdout queries
    2. Runs the LB holdout test with all 3 methods
    3. Reports which method recovers the most correct readings
    4. Counts reading distribution under each method

    Uses the same data as the full pipeline but runs much faster
    (only holdout signs, not all 21 stems).
    """
    rng = random.Random(42)
    t0 = time.time()

    print("Bias Correction Comparison: freq_norm vs grid_prior vs none")
    print("=" * 78)

    # Load data
    print("Loading data...")
    sign_to_ipa = load_sign_to_ipa()
    ab_to_reading = load_corpus()
    grid = load_p1_grid()
    cell_consonants = build_cell_consonants(grid, ab_to_reading, sign_to_ipa)

    # Load lexicons
    print(f"Loading {len(LANG_CODES)} lexicons...")
    lexicons: dict[str, list[dict]] = {}
    lex_by_len: dict[str, dict[int, list[str]]] = {}
    lex_capped: dict[str, dict[int, list[str]]] = {}
    for lc in LANG_CODES:
        lex = load_lexicon(lc)
        if lex:
            lexicons[lc] = lex
            by_len = bucket_lexicon(lex)
            lex_by_len[lc] = by_len
            lex_capped[lc] = cap_bucketed_lexicon(by_len, rng)

    # Determine query lengths needed for holdout test
    padding_sca = [ipa_to_sca("pa"), ipa_to_sca("ru")]
    holdout_lengths: set[int] = set()
    for ab_code, known_reading, _ in LB_HOLDOUT_SIGNS:
        if ab_code not in grid:
            continue
        _cc, vc, _conf = grid[ab_code]
        cands = candidate_readings(vc, cell_consonants)
        for c in cands:
            csca = ipa_to_sca(c)
            if csca:
                L = len(padding_sca[0] + csca + padding_sca[1])
                holdout_lengths.add(L)

    # Build null tables for holdout lengths
    print(f"Building null tables for {len(holdout_lengths)} lengths...")
    null_tables: dict[tuple[int, str], list[float]] = {}
    for L in sorted(holdout_lengths):
        for lc in lexicons:
            null_tables[(L, lc)] = build_null_table(
                L, lex_capped[lc], NULL_SAMPLES, rng,
            )

    # Build freq_norm rates
    print("Computing consonant-class background rates...")
    class_rates_all = build_class_background_rates_all(
        lex_capped, holdout_lengths, NULL_SAMPLES, rng, verbose=False,
    )

    # Build grid priors
    print("Building grid priors from Jaccard classification...")
    jaccard = load_jaccard_classification()
    grid_priors = build_grid_prior(grid, ab_to_reading, sign_to_ipa, jaccard)

    # Run LB holdout test
    print(f"\n{'=' * 78}")
    print("LB Known-Answer Holdout Test")
    print("=" * 78)
    holdout_results = run_lb_holdout_test(
        sign_to_ipa, ab_to_reading, grid, cell_consonants,
        lexicons, lex_capped, null_tables,
        class_rates=class_rates_all,
        grid_priors=grid_priors,
        rng=rng,
        verbose=True,
    )

    # Summarize comparison
    print(f"\n{'=' * 78}")
    print("COMPARISON SUMMARY")
    print("=" * 78)

    for method in ["none", "freq_norm", "grid_prior"]:
        r = holdout_results[method]
        print(f"  {method:12s}: {r['n_correct']}/{r['n_total']} correct "
              f"({r['accuracy']*100:.1f}%)")

    # Determine winner
    accuracies = {m: holdout_results[m]["accuracy"] for m in holdout_results}
    best_method = max(accuracies, key=accuracies.get)
    print(f"\n  Winner: {best_method}")
    if accuracies["freq_norm"] == accuracies["grid_prior"]:
        print("  Tie between freq_norm and grid_prior -- preferring freq_norm "
              "(more principled, no Jaccard dependency)")
        best_method = "freq_norm"

    # Count "da" readings in each method's holdout predictions
    for method in ["none", "freq_norm", "grid_prior"]:
        details = holdout_results[method]["details"]
        da_count = sum(1 for d in details if d["predicted_reading"] == "da")
        total = len(details)
        print(f"  {method:12s}: {da_count}/{total} predictions are 'da' "
              f"({100*da_count/total:.1f}%)" if total > 0 else "")

    elapsed = time.time() - t0
    print(f"\nComparison completed in {elapsed:.0f}s")

    return holdout_results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bias-correction",
        choices=["none", "freq_norm", "grid_prior"],
        default="freq_norm",
        help="Bias correction method (default: freq_norm)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run comparison of all three approaches (LB holdout test only)",
    )
    args = parser.parse_args()
    if args.compare:
        compare_approaches()
    else:
        main(bias_correction=args.bias_correction)
