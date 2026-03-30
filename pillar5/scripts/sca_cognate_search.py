"""PhaiPhon6 prototype: SCA-based cognate search for fully-phonetic P2 stems.

Takes the 16 unique P2 stems with full LB phonetic readings and searches
all candidate language lexicons using Sound Class Assignment (SCA) distance.

SCA maps all IPA to ~20 Dolgopolsky sound classes, then computes normalized
edit distance in this reduced space. Zero learnable parameters = zero
inventory bias.

Includes permutation null: for each language, shuffles the SCA column and
re-scores to establish what "chance" looks like. A match is significant
only if the real score is better than 95% of shuffled scores.
"""

import csv
import json
import random
import sys
import io
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT = Path(__file__).resolve().parents[2]
LEXICON_DIR = PROJECT.parent / "ancient-scripts-datasets" / "data" / "training" / "lexicons"

# The 34 known LB sign readings -> IPA
with open(PROJECT / "data" / "sign_to_ipa.json") as f:
    SIGN_TO_IPA = json.load(f)

# Dolgopolsky sound classes (standard 10-class system)
# Maps IPA characters to broad sound classes
# Reference: Dolgopolsky 1964, as used in ASJP/LingPy
DOLGOPOLSKY = {
    'p': 'P', 'b': 'P', 'f': 'P', 'v': 'P',
    't': 'T', 'd': 'T', 'θ': 'T', 'ð': 'T',
    's': 'S', 'z': 'S', 'ʃ': 'S', 'ʒ': 'S', 'ʂ': 'S', 'ʐ': 'S',
    'k': 'K', 'g': 'K', 'x': 'K', 'ɣ': 'K', 'q': 'K',
    'm': 'M',
    'n': 'N', 'ɲ': 'N', 'ŋ': 'N',
    'l': 'L', 'ɬ': 'L', 'ɮ': 'L',
    'r': 'R', 'ɾ': 'R', 'ɽ': 'R',
    'w': 'W',
    'j': 'J', 'ʎ': 'J',
    'h': 'H', 'ɦ': 'H', 'ʔ': 'H',
    # Vowels all map to one class
    'a': 'V', 'e': 'V', 'i': 'V', 'o': 'V', 'u': 'V',
    'ə': 'V', 'ɛ': 'V', 'ɔ': 'V', 'ɪ': 'V', 'ʊ': 'V',
    'æ': 'V', 'ɑ': 'V', 'ʌ': 'V', 'ɒ': 'V',
}


def ipa_to_sca(ipa: str) -> str:
    """Convert an IPA string to SCA (Sound Class Assignment) encoding."""
    result = []
    for ch in ipa:
        sc = DOLGOPOLSKY.get(ch)
        if sc is not None:
            result.append(sc)
        # Skip diacritics, length marks, tones, etc.
    return ''.join(result)


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


def sca_distance(ipa1: str, ipa2: str) -> float:
    """SCA-based distance between two IPA strings."""
    sca1 = ipa_to_sca(ipa1)
    sca2 = ipa_to_sca(ipa2)
    if not sca1 or not sca2:
        return 1.0
    return normalized_edit_distance(sca1, sca2)


def load_lexicon_sca(lang_code: str, max_entries: int = 0):
    """Load a lexicon and return entries with SCA encodings."""
    path = LEXICON_DIR / f"{lang_code}.tsv"
    if not path.exists():
        return []
    entries = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            word = row.get('Word', '').strip()
            ipa = row.get('IPA', '').strip()
            sca = row.get('SCA', '').strip()
            gloss = row.get('Concept_ID', '').strip()
            if not ipa:
                continue
            if not sca or sca == '-':
                sca = ipa_to_sca(ipa)
            if gloss == '-':
                gloss = ''
            entries.append({
                'word': word,
                'ipa': ipa,
                'sca': sca,
                'gloss': gloss,
            })
            if max_entries > 0 and len(entries) >= max_entries:
                break
    return entries


def search_one_stem(stem_ipa: str, lexicon: list, top_k: int = 10):
    """Search a lexicon for the closest SCA matches to a stem."""
    stem_sca = ipa_to_sca(stem_ipa)
    if not stem_sca:
        return []

    scored = []
    for entry in lexicon:
        dist = normalized_edit_distance(stem_sca, entry['sca'])
        scored.append((dist, entry))

    scored.sort(key=lambda x: x[0])
    return scored[:top_k]


def permutation_null(stem_ipa: str, lexicon: list, n_perms: int = 200):
    """Compute null distribution by shuffling lexicon SCA strings."""
    stem_sca = ipa_to_sca(stem_ipa)
    if not stem_sca:
        return 1.0

    rng = random.Random(42)
    null_best_dists = []

    for _ in range(n_perms):
        # Shuffle the SCA column (break word-SCA correspondence)
        shuffled_scas = [e['sca'] for e in lexicon]
        rng.shuffle(shuffled_scas)
        best_dist = min(
            normalized_edit_distance(stem_sca, s) for s in shuffled_scas if s
        ) if shuffled_scas else 1.0
        null_best_dists.append(best_dist)

    return sorted(null_best_dists)


def main():
    # Load P2 stems
    with open(PROJECT / "results" / "pillar2_output.json") as f:
        p2 = json.load(f)
    with open(PROJECT / "data" / "sigla_full_corpus.json", encoding='utf-8') as f:
        corpus_data = json.load(f)
    ab_to_reading = {}
    for reading, info in corpus_data['sign_inventory'].items():
        if isinstance(info, dict):
            for ab in info.get('ab_codes', []):
                ab_to_reading[ab] = reading

    # Extract the 16 unique fully-phonetic stems
    stems = {}
    for entry in p2['segmented_lexicon']:
        stem_ids = entry['segmentation']['stem']
        readings = [ab_to_reading.get(sid, sid) for sid in stem_ids]
        ipas = [SIGN_TO_IPA.get(r) for r in readings]
        if all(p is not None for p in ipas):
            ipa = ''.join(ipas)
            key = '-'.join(readings)
            if key not in stems or entry['frequency'] > stems[key]['freq']:
                stems[key] = {
                    'reading': key,
                    'ipa': ipa,
                    'sca': ipa_to_sca(ipa),
                    'freq': entry['frequency'],
                }

    print(f"PhaiPhon6 Prototype: SCA Cognate Search")
    print(f"=" * 70)
    print(f"Fully-phonetic P2 stems: {len(stems)}")

    # Candidate languages
    lang_codes = [
        'hit', 'xld', 'xlc', 'xrr', 'phn', 'uga', 'elx', 'xur',
        'peo', 'xpg', 'ave', 'akk', 'grc', 'lat', 'heb', 'arb',
        'sem-pro', 'ine-pro',
    ]

    # Load lexicons
    print(f"Loading {len(lang_codes)} lexicons...")
    lexicons = {}
    for lc in lang_codes:
        lex = load_lexicon_sca(lc)
        if lex:
            lexicons[lc] = lex
            print(f"  {lc}: {len(lex)} entries")

    print(f"\n{'=' * 70}")
    print(f"SEARCHING {len(stems)} stems against {len(lexicons)} languages")
    print(f"{'=' * 70}\n")

    all_results = []

    for stem_key, stem_info in sorted(stems.items(), key=lambda x: -x[1]['freq']):
        print(f"\n--- LA stem: {stem_info['reading']} (IPA: {stem_info['ipa']}, "
              f"SCA: {stem_info['sca']}, freq={stem_info['freq']}) ---")

        best_per_lang = []

        for lc, lex in lexicons.items():
            # Real search
            top_matches = search_one_stem(stem_info['ipa'], lex, top_k=3)
            if not top_matches:
                continue
            best_dist = top_matches[0][0]
            best_word = top_matches[0][1]

            # Permutation null
            null_dists = permutation_null(stem_info['ipa'], lex, n_perms=200)
            # p-value: fraction of null scores <= real score (lower dist = better)
            p_value = sum(1 for nd in null_dists if nd <= best_dist) / len(null_dists)

            best_per_lang.append({
                'lang': lc,
                'word': best_word['word'],
                'ipa': best_word['ipa'],
                'gloss': best_word['gloss'],
                'sca_dist': best_dist,
                'p_value': p_value,
                'null_median': null_dists[len(null_dists) // 2],
                'top3': [(d, e['word'], e['ipa'], e['gloss']) for d, e in top_matches],
            })

            all_results.append({
                'stem': stem_info['reading'],
                'stem_ipa': stem_info['ipa'],
                'lang': lc,
                'best_word': best_word['word'],
                'best_ipa': best_word['ipa'],
                'gloss': best_word['gloss'],
                'sca_dist': best_dist,
                'p_value': p_value,
            })

        # Sort by SCA distance (best first)
        best_per_lang.sort(key=lambda x: x['sca_dist'])

        # Show top 5 with significance
        print(f"  {'Lang':8s} {'Word':18s} {'IPA':15s} {'Gloss':20s} {'Dist':>5s} {'p-val':>6s} {'Sig?'}")
        print(f"  {'-'*80}")
        for m in best_per_lang[:8]:
            sig = '***' if m['p_value'] <= 0.01 else '**' if m['p_value'] <= 0.05 else '*' if m['p_value'] <= 0.10 else ''
            gloss = m['gloss'][:18] if m['gloss'] else '-'
            print(f"  {m['lang']:8s} {m['word']:18s} {m['ipa']:15s} {gloss:20s} {m['sca_dist']:>5.3f} {m['p_value']:>6.3f} {sig}")

    # Summary: how many significant matches per language
    print(f"\n{'=' * 70}")
    print(f"SIGNIFICANCE SUMMARY (p <= 0.05)")
    print(f"{'=' * 70}")

    sig_by_lang = defaultdict(list)
    for r in all_results:
        if r['p_value'] <= 0.05:
            sig_by_lang[r['lang']].append(r)

    for lc in sorted(sig_by_lang.keys(), key=lambda k: -len(sig_by_lang[k])):
        matches = sig_by_lang[lc]
        print(f"\n  {lc} ({len(matches)} significant matches):")
        for m in matches:
            print(f"    LA {m['stem']:12s} -> {m['best_word']:15s} ({m['gloss'][:20] if m['gloss'] else '-':20s}) dist={m['sca_dist']:.3f} p={m['p_value']:.3f}")

    if not sig_by_lang:
        print("  No significant matches found at p <= 0.05")

    # Also report p <= 0.10
    sig10 = defaultdict(list)
    for r in all_results:
        if r['p_value'] <= 0.10:
            sig10[r['lang']].append(r)

    print(f"\n  Total significant at p <= 0.05: {sum(len(v) for v in sig_by_lang.values())}")
    print(f"  Total significant at p <= 0.10: {sum(len(v) for v in sig10.values())}")
    print(f"  Total comparisons: {len(all_results)}")


if __name__ == '__main__':
    main()
