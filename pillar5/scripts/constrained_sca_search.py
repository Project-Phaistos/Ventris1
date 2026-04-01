"""PhaiPhon6 constrained SCA cognate search for partially-phonetic P2 stems.

For each P2 stem with exactly 1 unknown syllable:
1. Look up the unknown sign's grid cell (vowel class) from P1 V=5 Kober grid
2. Enumerate the possible CV readings for that sign (consonant options from
   known signs in the same cell + the cell's vowel)
3. For each possible reading, construct the complete IPA string
4. SCA-encode it and search against all candidate language lexicons
5. Apply permutation null (shuffle lexicon SCA, re-score) for significance
6. If one reading yields significantly better matches, that constrains
   both the sign's identity and the cognate relationship.

Output:
  - All (reading, language, match, gloss, p-value) results per stem
  - Significant matches (p <= 0.05) highlighted
  - Self-consistency: for each unknown sign, do different stems agree?
  - Summary: how many stems produced significant matches? Which languages?
"""

import csv
import io
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)

PROJECT = Path(__file__).resolve().parents[2]
LEXICON_DIR = (
    PROJECT.parent / "ancient-scripts-datasets" / "data" / "training" / "lexicons"
)

# ── Load sign data ────────────────────────────────────────────────────────────

with open(PROJECT / "data" / "sign_to_ipa.json") as f:
    SIGN_TO_IPA: dict[str, str] = json.load(f)

with open(PROJECT / "data" / "sigla_full_corpus.json", encoding="utf-8") as f:
    CORPUS = json.load(f)

AB_TO_READING: dict[str, str] = {}
for _reading, _info in CORPUS["sign_inventory"].items():
    if isinstance(_info, dict):
        for _ab in _info.get("ab_codes", []):
            AB_TO_READING[_ab] = _reading

with open(PROJECT / "results" / "pillar1_v5_output.json") as f:
    P1 = json.load(f)

# ── Build the P1 grid lookup ─────────────────────────────────────────────────

GRID: dict[str, tuple[int, int, float]] = {}
for _a in P1["grid"]["assignments"]:
    GRID[_a["sign_id"]] = (
        _a["consonant_class"],
        _a["vowel_class"],
        _a["confidence"],
    )

# Vowel class -> vowel letter (based on pure-vowel sign assignments)
VC_TO_VOWEL = {0: "a", 1: "e", 2: "i", 3: "o", 4: "u"}

# For each vowel class, collect consonant onsets from known signs in that cell
CELL_CONSONANTS: dict[int, set[str]] = defaultdict(set)
for _a in P1["grid"]["assignments"]:
    _sid = _a["sign_id"]
    _reading = AB_TO_READING.get(_sid, _sid)
    _ipa = SIGN_TO_IPA.get(_reading)
    if _ipa and _a["consonant_class"] == 0:
        _vc = _a["vowel_class"]
        _clean = _ipa.rstrip("0123456789")
        if _clean in ("a", "e", "i", "o", "u"):
            CELL_CONSONANTS[_vc].add("")
        elif _clean.endswith(("a", "e", "i", "o", "u")):
            CELL_CONSONANTS[_vc].add(_clean[:-1])
        elif _clean == "nwa":
            CELL_CONSONANTS[_vc].add("nw")


def candidate_readings(vowel_class: int) -> list[str]:
    """Return possible CV syllable readings for a given vowel class."""
    vowel = VC_TO_VOWEL.get(vowel_class)
    if vowel is None:
        return []
    return sorted(c + vowel for c in CELL_CONSONANTS.get(vowel_class, set()))


# ── Dolgopolsky sound classes ─────────────────────────────────────────────────

DOLGOPOLSKY = {
    "p": "P", "b": "P", "f": "P", "v": "P",
    "t": "T", "d": "T", "θ": "T", "ð": "T",
    "s": "S", "z": "S", "ʃ": "S", "ʒ": "S", "ʂ": "S", "ʐ": "S",
    "k": "K", "g": "K", "x": "K", "ɣ": "K", "q": "K",
    "m": "M",
    "n": "N", "ɲ": "N", "ŋ": "N",
    "l": "L", "ɬ": "L", "ɮ": "L",
    "r": "R", "ɾ": "R", "ɽ": "R",
    "w": "W",
    "j": "J", "ʎ": "J",
    "h": "H", "ɦ": "H", "ʔ": "H",
    "a": "V", "e": "V", "i": "V", "o": "V", "u": "V",
    "ə": "V", "ɛ": "V", "ɔ": "V", "ɪ": "V", "ʊ": "V",
    "æ": "V", "ɑ": "V", "ʌ": "V", "ɒ": "V",
}


def ipa_to_sca(ipa: str) -> str:
    """Convert IPA string to Dolgopolsky SCA encoding."""
    return "".join(DOLGOPOLSKY.get(ch, "") for ch in ipa)


def normalized_edit_distance(s1: str, s2: str) -> float:
    """Normalized Levenshtein distance in [0, 1]."""
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


# ── Lexicon loading ───────────────────────────────────────────────────────────

MAX_LEXICON_ENTRIES = 3000


def load_lexicon(lang_code: str) -> list[dict]:
    """Load a lexicon TSV and return entries with SCA encodings."""
    path = LEXICON_DIR / f"{lang_code}.tsv"
    if not path.exists():
        return []
    entries = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            ipa = row.get("IPA", "").strip()
            if not ipa:
                continue
            sca = row.get("SCA", "").strip()
            if not sca or sca == "-":
                sca = ipa_to_sca(ipa)
            gloss = row.get("Concept_ID", "").strip()
            if gloss == "-":
                gloss = ""
            entries.append({
                "word": row.get("Word", "").strip(),
                "ipa": ipa,
                "sca": sca,
                "gloss": gloss,
            })
            if len(entries) >= MAX_LEXICON_ENTRIES:
                break
    return entries


# ── Search & null ─────────────────────────────────────────────────────────────

N_PERMS = 100
NULL_SAMPLE = 300  # subsample lexicon for null


def search_best_match(stem_sca: str, lexicon: list[dict]) -> tuple[float, dict]:
    """Find the lexicon entry with lowest SCA distance to stem_sca."""
    best_dist = 1.0
    best_entry = None
    for entry in lexicon:
        if not entry["sca"]:
            continue
        d = normalized_edit_distance(stem_sca, entry["sca"])
        if d < best_dist:
            best_dist = d
            best_entry = entry
    return best_dist, best_entry


def precompute_null_distributions(
    lexicons: dict[str, list[dict]],
    sca_lengths: set[int],
    rng: random.Random,
) -> dict[tuple[str, int], list[float]]:
    """Pre-compute null distributions for each (language, query_length) pair.

    For each (lang, length), we generate N_PERMS random SCA strings of that
    length and find each one's best match in the lexicon. The resulting
    distribution of best distances is the null.

    This is much faster than doing per-query permutation because we compute
    the null once per (lang, length) pair instead of once per (stem, reading,
    lang) triple.
    """
    SCA_ALPHABET = list("PTSKMNLRWJHV")
    null_dists: dict[tuple[str, int], list[float]] = {}

    for lc, lex in lexicons.items():
        sca_pool = [e["sca"] for e in lex if e["sca"]]
        if not sca_pool:
            continue
        # Subsample for speed
        if len(sca_pool) > NULL_SAMPLE:
            pool = rng.sample(sca_pool, NULL_SAMPLE)
        else:
            pool = sca_pool

        for qlen in sca_lengths:
            bests = []
            for _ in range(N_PERMS):
                # Generate a random SCA string of the given length
                rand_sca = "".join(rng.choice(SCA_ALPHABET) for _ in range(qlen))
                best_d = min(
                    normalized_edit_distance(rand_sca, s) for s in pool
                )
                bests.append(best_d)
            null_dists[(lc, qlen)] = sorted(bests)

    return null_dists


def p_value_from_null(
    real_dist: float, null_dist: list[float]
) -> float:
    """Compute p-value: fraction of null scores <= real_dist."""
    if not null_dist:
        return 1.0
    count = sum(1 for nd in null_dist if nd <= real_dist)
    return count / len(null_dist)


# ── Main pipeline ─────────────────────────────────────────────────────────────


def find_partial_stems() -> list[dict]:
    """Find P2 stems with exactly 1 unknown sign that is in the P1 grid."""
    with open(PROJECT / "results" / "pillar2_output.json") as f:
        p2 = json.load(f)

    results = []
    for entry in p2["segmented_lexicon"]:
        stem_ids = entry["segmentation"]["stem"]
        if len(stem_ids) < 2:
            continue

        readings = [AB_TO_READING.get(sid, sid) for sid in stem_ids]
        ipas = [SIGN_TO_IPA.get(r) for r in readings]
        unknown_indices = [i for i, ip in enumerate(ipas) if ip is None]

        if len(unknown_indices) != 1:
            continue

        idx = unknown_indices[0]
        unknown_sid = stem_ids[idx]

        if unknown_sid not in GRID:
            continue

        cc, vc, conf = GRID[unknown_sid]
        cands = candidate_readings(vc)
        if not cands:
            continue

        known_ipas = []
        for i, ip in enumerate(ipas):
            if ip is not None:
                known_ipas.append(ip.rstrip("0123456789"))
            else:
                known_ipas.append(None)

        results.append({
            "stem_ids": stem_ids,
            "readings": readings,
            "known_ipas": known_ipas,
            "unknown_idx": idx,
            "unknown_sign_id": unknown_sid,
            "vowel_class": vc,
            "grid_confidence": conf,
            "candidate_readings": cands,
            "freq": entry["frequency"],
        })

    return results


def deduplicate_stems(stems: list[dict]) -> list[dict]:
    """Deduplicate: keep highest-frequency version of each unique stem."""
    seen: dict[str, dict] = {}
    for s in stems:
        key = "-".join(s["stem_ids"])
        if key not in seen or s["freq"] > seen[key]["freq"]:
            seen[key] = s
    return list(seen.values())


def main():
    rng = random.Random(42)
    t0 = time.time()

    # ── Find partial stems ────────────────────────────────────────────────
    raw_stems = find_partial_stems()
    stems = deduplicate_stems(raw_stems)
    stems.sort(key=lambda s: -s["freq"])

    print("PhaiPhon6: Constrained SCA Cognate Search")
    print("=" * 78)
    print(f"P2 stems with exactly 1 unknown sign (in P1 grid): {len(stems)}")
    print()

    vc_counts = defaultdict(int)
    for s in stems:
        vc_counts[s["vowel_class"]] += 1
    for vc in sorted(vc_counts):
        v = VC_TO_VOWEL[vc]
        cands = candidate_readings(vc)
        print(f"  V={vc} ({v}): {vc_counts[vc]} stems, candidates={cands}")

    # ── Load lexicons ─────────────────────────────────────────────────────
    lang_codes = [
        "hit", "xld", "xlc", "xrr", "phn", "uga", "elx", "xur",
        "peo", "xpg", "ave", "akk", "grc", "lat", "heb", "arb",
        "sem-pro", "ine-pro",
    ]

    print(f"\nLoading {len(lang_codes)} lexicons...")
    lexicons: dict[str, list[dict]] = {}
    for lc in lang_codes:
        lex = load_lexicon(lc)
        if lex:
            lexicons[lc] = lex
            print(f"  {lc}: {len(lex)} entries")

    # ── Pre-compute all possible SCA lengths ──────────────────────────────
    all_sca_lengths: set[int] = set()
    for stem in stems:
        for cand in stem["candidate_readings"]:
            parts = list(stem["known_ipas"])
            parts[stem["unknown_idx"]] = cand
            ipa = "".join(p for p in parts)
            sca = ipa_to_sca(ipa)
            if sca:
                all_sca_lengths.add(len(sca))

    print(f"\nPre-computing null distributions for {len(all_sca_lengths)} "
          f"SCA lengths x {len(lexicons)} languages...")
    null_dists = precompute_null_distributions(lexicons, all_sca_lengths, rng)
    print(f"  Done ({time.time() - t0:.0f}s elapsed)")

    print(f"\n{'=' * 78}")
    print(f"SEARCHING {len(stems)} partially-phonetic stems")
    print(f"  across {len(lexicons)} languages")
    print(f"  with {N_PERMS} permutations per null")
    print(f"{'=' * 78}")

    # ── Per-stem search ───────────────────────────────────────────────────
    all_results: list[dict] = []
    sign_reading_votes: dict[str, dict[str, list]] = defaultdict(
        lambda: defaultdict(list)
    )

    for stem_i, stem in enumerate(stems):
        stem_label = "-".join(stem["readings"])
        vc = stem["vowel_class"]
        v_letter = VC_TO_VOWEL[vc]
        elapsed = time.time() - t0

        print(f"\n{'─' * 78}")
        print(
            f"[{stem_i + 1}/{len(stems)}] Stem: {stem_label}  "
            f"(unknown={stem['unknown_sign_id']}, V={vc}({v_letter}), "
            f"freq={stem['freq']})  [{elapsed:.0f}s elapsed]"
        )
        print(f"  Candidate readings: {stem['candidate_readings']}")

        best_reading_results: list[dict] = []

        for cand_reading in stem["candidate_readings"]:
            ipa_parts = list(stem["known_ipas"])
            ipa_parts[stem["unknown_idx"]] = cand_reading
            complete_ipa = "".join(p for p in ipa_parts)
            complete_sca = ipa_to_sca(complete_ipa)

            if not complete_sca:
                continue

            sca_len = len(complete_sca)
            reading_lang_results: list[dict] = []

            for lc, lex in lexicons.items():
                best_dist, best_entry = search_best_match(complete_sca, lex)
                if best_entry is None:
                    continue

                # Look up pre-computed null
                null_key = (lc, sca_len)
                nd = null_dists.get(null_key, [])
                p_val = p_value_from_null(best_dist, nd)

                result = {
                    "stem": stem_label,
                    "stem_ids": stem["stem_ids"],
                    "unknown_sign_id": stem["unknown_sign_id"],
                    "candidate_reading": cand_reading,
                    "complete_ipa": complete_ipa,
                    "complete_sca": complete_sca,
                    "lang": lc,
                    "best_word": best_entry["word"],
                    "best_ipa": best_entry["ipa"],
                    "best_sca": best_entry["sca"],
                    "gloss": best_entry["gloss"],
                    "sca_dist": best_dist,
                    "p_value": p_val,
                }
                all_results.append(result)
                reading_lang_results.append(result)

            if reading_lang_results:
                reading_lang_results.sort(key=lambda r: r["sca_dist"])
                sig_count = sum(
                    1 for r in reading_lang_results if r["p_value"] <= 0.05
                )
                best = reading_lang_results[0]
                best_reading_results.append({
                    "reading": cand_reading,
                    "ipa": complete_ipa,
                    "sca": complete_sca,
                    "best_dist": best["sca_dist"],
                    "best_lang": best["lang"],
                    "best_word": best["best_word"],
                    "best_gloss": best["gloss"],
                    "best_p": best["p_value"],
                    "n_sig": sig_count,
                    "all_langs": reading_lang_results,
                })

        # Print comparison table
        if best_reading_results:
            best_reading_results.sort(key=lambda r: -r["n_sig"])
            print(
                f"  {'Reading':8s} {'IPA':12s} {'SCA':8s} "
                f"{'BestLang':8s} {'BestWord':15s} {'Gloss':18s} "
                f"{'Dist':>5s} {'p':>5s} {'#sig'}"
            )
            print(f"  {'-' * 90}")
            for br in best_reading_results:
                g = br["best_gloss"][:16] if br["best_gloss"] else "-"
                sig_mark = (
                    " ***" if br["n_sig"] >= 3
                    else " **" if br["n_sig"] >= 2
                    else " *" if br["n_sig"] >= 1
                    else ""
                )
                print(
                    f"  {br['reading']:8s} {br['ipa']:12s} {br['sca']:8s} "
                    f"{br['best_lang']:8s} {br['best_word']:15s} {g:18s} "
                    f"{br['best_dist']:>5.3f} {br['best_p']:>5.2f} "
                    f"{br['n_sig']}{sig_mark}"
                )

            # Show significant matches for the best reading
            winner = best_reading_results[0]
            if winner["n_sig"] > 0:
                print(f"\n  Significant matches for reading '{winner['reading']}':")
                for r in winner["all_langs"]:
                    if r["p_value"] <= 0.05:
                        g = r["gloss"][:20] if r["gloss"] else "-"
                        print(
                            f"    {r['lang']:8s} {r['best_word']:15s} "
                            f"{r['best_ipa']:15s} {g:22s} "
                            f"dist={r['sca_dist']:.3f} p={r['p_value']:.3f}"
                        )

            # Record votes for self-consistency
            for br in best_reading_results:
                if br["n_sig"] > 0:
                    sign_reading_votes[stem["unknown_sign_id"]][
                        br["reading"]
                    ].append({
                        "stem": stem_label,
                        "n_sig": br["n_sig"],
                        "best_dist": br["best_dist"],
                    })

    # ── Self-consistency analysis ─────────────────────────────────────────
    print(f"\n{'=' * 78}")
    print("SELF-CONSISTENCY ANALYSIS")
    print("For each unknown sign, do different stems agree on its reading?")
    print(f"{'=' * 78}")

    for sign_id in sorted(sign_reading_votes.keys()):
        votes = sign_reading_votes[sign_id]
        total_stems = sum(len(v) for v in votes.values())
        print(f"\n  {sign_id} ({total_stems} stems with significant matches):")
        for reading in sorted(votes.keys(), key=lambda r: -len(votes[r])):
            stems_for_reading = votes[reading]
            n = len(stems_for_reading)
            avg_sig = sum(s["n_sig"] for s in stems_for_reading) / n
            avg_dist = sum(s["best_dist"] for s in stems_for_reading) / n
            print(
                f"    {reading:8s}: {n} stems agree, "
                f"avg #sig={avg_sig:.1f}, avg best_dist={avg_dist:.3f}"
            )
            for s in stems_for_reading:
                print(
                    f"      stem={s['stem']:30s} #sig={s['n_sig']} "
                    f"best_dist={s['best_dist']:.3f}"
                )

    if not sign_reading_votes:
        print("  No signs had significant matches across multiple readings.")

    # ── Overall significance summary ──────────────────────────────────────
    print(f"\n{'=' * 78}")
    print("SIGNIFICANCE SUMMARY")
    print(f"{'=' * 78}")

    sig_results = [r for r in all_results if r["p_value"] <= 0.05]
    print(f"\nTotal comparisons: {len(all_results)}")
    print(f"Significant at p <= 0.05: {len(sig_results)}")

    # By language
    sig_by_lang = defaultdict(list)
    for r in sig_results:
        sig_by_lang[r["lang"]].append(r)

    print(f"\nSignificant matches by language (p <= 0.05):")
    for lc in sorted(sig_by_lang, key=lambda k: -len(sig_by_lang[k])):
        matches = sig_by_lang[lc]
        print(f"\n  {lc} ({len(matches)} matches):")
        for m in sorted(matches, key=lambda x: x["sca_dist"])[:10]:
            g = m["gloss"][:20] if m["gloss"] else "-"
            print(
                f"    LA {m['stem']:25s} [{m['candidate_reading']:4s}] -> "
                f"{m['best_word']:15s} ({g:20s}) "
                f"dist={m['sca_dist']:.3f} p={m['p_value']:.3f}"
            )
        if len(matches) > 10:
            print(f"    ... and {len(matches) - 10} more")

    if not sig_by_lang:
        print("  No significant matches found at p <= 0.05")

    # By reading
    sig_by_reading = defaultdict(list)
    for r in sig_results:
        sig_by_reading[r["candidate_reading"]].append(r)

    print(f"\nSignificant matches by candidate reading:")
    for rd in sorted(sig_by_reading, key=lambda k: -len(sig_by_reading[k])):
        matches = sig_by_reading[rd]
        unique_stems = len(set(m["stem"] for m in matches))
        unique_langs = len(set(m["lang"] for m in matches))
        print(
            f"  {rd:6s}: {len(matches)} matches across "
            f"{unique_stems} stems and {unique_langs} languages"
        )

    # By unknown sign
    sig_by_sign = defaultdict(lambda: defaultdict(int))
    for r in sig_results:
        sig_by_sign[r["unknown_sign_id"]][r["candidate_reading"]] += 1

    print(f"\nSignificant match counts by unknown sign and reading:")
    for sign_id in sorted(sig_by_sign):
        readings = sig_by_sign[sign_id]
        total = sum(readings.values())
        best_reading = max(readings, key=readings.get)
        print(
            f"  {sign_id:10s} total={total:3d}  "
            f"best_reading={best_reading:6s} ({readings[best_reading]})"
        )
        for rd in sorted(readings, key=lambda k: -readings[k]):
            print(f"    {rd:6s}: {readings[rd]}")

    # ── Discriminative power: signs where one reading clearly wins ────────
    print(f"\n{'=' * 78}")
    print("DISCRIMINATIVE SIGNS (one reading dominates)")
    print(f"{'=' * 78}")

    for sign_id in sorted(sig_by_sign):
        readings = sig_by_sign[sign_id]
        if len(readings) < 2:
            if sum(readings.values()) >= 2:
                rd = list(readings.keys())[0]
                print(
                    f"  {sign_id}: ONLY '{rd}' produced significant matches "
                    f"({readings[rd]} hits)"
                )
            continue
        vals = sorted(readings.values(), reverse=True)
        if vals[0] >= 2 * vals[1] and vals[0] >= 3:
            best = max(readings, key=readings.get)
            print(
                f"  {sign_id}: '{best}' dominates with {readings[best]} hits "
                f"(next best: {vals[1]})"
            )

    elapsed = time.time() - t0
    print(f"\n{'=' * 78}")
    print(f"DONE ({elapsed:.0f}s total)")
    print(f"{'=' * 78}")


if __name__ == "__main__":
    main()
