# Adversarial Audit: Analytical Null Cognate Search (PRD)

**Auditor:** Claude (adversarial critic)
**Date:** 2026-04-03
**Subject:** `docs/prd/PRD_ANALYTICAL_NULL_SEARCH.md` and supporting code
**Verdict:** 4 CRITICAL, 5 HIGH, 4 MEDIUM, 3 LOW issues found. **DO NOT PROCEED without fixing CRITICAL issues.**

---

## Executive Summary

The Analytical Null Search PRD proposes a sound high-level methodology (SCA search with analytical null and BH-FDR correction), but the implementation infrastructure contains four critical bugs that would invalidate any results produced. The most severe is a complete SCA encoding mismatch between query strings and lexicon entries -- queries use Dolgopolsky V-collapse (all vowels map to 'V') while stored lexicon SCA uses individual vowel letters (A, E, I, O, U). This means edit distances are computed between strings in two different alphabets. Additionally, the permutation null in the existing `constrained_sca_search.py` is mathematically degenerate (produces identical values for every iteration), 11-27% of IPA characters in the lexicons silently vanish during SCA conversion, and all 21 target stems are hapax legomena (frequency=1).

---

## 1. Data Source Audit

### 1.1 Lexicon File Existence

**SEVERITY: OK** -- All 18 lexicon TSV files exist and load correctly.

| Code | Entries | Verified |
|------|---------|----------|
| hit | 281 | Yes |
| xld | 693 | Yes |
| xlc | 1,098 | Yes |
| xrr | 187 | Yes |
| phn | 180 | Yes |
| uga | 467 | Yes |
| elx | 301 | Yes |
| xur | 748 | Yes |
| peo | 486 | Yes |
| xpg | 79 | Yes |
| ave | 1,926 | Yes |
| akk | 24,341 | Yes |
| grc | 121,659 | Yes |
| lat | 67,332 | Yes |
| heb | 3,824 | Yes |
| arb | 2,175 | Yes |
| sem-pro | 386 | Yes |
| ine-pro | 1,704 | Yes |

Entry counts match PRD Section 6 (Table). No empty IPA fields found.

### 1.2 SCA Column Encoding -- CRITICAL MISMATCH

**SEVERITY: CRITICAL**

**DESCRIPTION:** The pre-computed SCA column in the lexicon TSV files uses an encoding system fundamentally different from the Dolgopolsky encoding used by `ipa_to_sca()` in `constrained_sca_search.py`. Specifically:

- **Stored SCA:** Uses individual vowel letters A, E, I, O, U (alphabet size 17-20). Example: Greek `epo` -> stored SCA `EPO`.
- **Ventris1 `ipa_to_sca()`:** Collapses all vowels to `V` (alphabet size 12). Example: `epo` -> computed SCA `VPV`.

The stored SCA alphabet is `{A, B, D, E, G, H, I, K, L, M, N, O, P, R, S, T, U, W, Y}` (varies by language, 15-20 chars). The Ventris1 alphabet is `{H, J, K, L, M, N, P, R, S, T, V, W}` (12 chars). The letter `V` never appears in stored SCA. The letters `A, E, I, O, U` never appear in Ventris1 queries.

**EVIDENCE:** Comparing Greek first 5,000 entries: 5,000/5,001 show mismatches between stored and computed SCA.

```
IPA='epo'       stored_SCA='EPO'    computed_SCA='VPV'
IPA='ai̯én'      stored_SCA='AIN'    computed_SCA='VVN'
IPA='t͡s'        stored_SCA='S'      computed_SCA='TS'
```

**IMPACT:** When `load_lexicon()` uses stored SCA (which it does whenever the column is non-empty and not "-"), it returns entries in one encoding. But queries from `ipa_to_sca()` are in a different encoding. Edit distance computations between these cross-encoded strings are meaningless. Every vowel position incurs a guaranteed mismatch (V vs A/E/I/O/U), artificially inflating distances.

**RECOMMENDATION:** Either:
(a) Always recompute SCA from IPA using the Ventris1 `ipa_to_sca()` function, ignoring the stored column; OR
(b) Update `ipa_to_sca()` to match the stored encoding (preserve individual vowels); OR
(c) Normalize both to the same encoding before comparison.

Option (a) is simplest but loses information from the stored SCA (which handles affricates like t͡s -> S correctly while `ipa_to_sca()` incorrectly produces TS). Option (b) requires rethinking the entire SCA distance metric. Option (c) is the most robust.

### 1.3 IPA Coverage Gaps in DOLGOPOLSKY Dict

**SEVERITY: HIGH**

**DESCRIPTION:** The `DOLGOPOLSKY` dict in `constrained_sca_search.py` (lines 94-109) maps only 38 IPA characters. Across the 18 lexicons, 11-27% of IPA character tokens have no mapping and are **silently dropped** by `ipa_to_sca()`.

**EVIDENCE:** Unmapped IPA token percentages per language:

| Language | Unmapped % | Top unmapped chars |
|----------|-----------|-------------------|
| grc | 17.8% | ː (30,440), y (23,845), ʰ (23,040), ɡ (12,371) |
| akk | 20.8% | - (8,050), ː (5,574), ˤ (3,767), ɡ (2,670) |
| xld | 25.1% | various diacritics and non-standard chars |
| xur | 26.1% | uppercase letters, hyphens, digits |
| sem-pro | 22.9% | - (234), ˤ (66), ʕ (48), ħ (45) |
| ine-pro | 19.7% | ʱ (473), ɡ (411), ħ (403), ʷ (286) |

Critical missing mappings:
- **ɡ** (U+0261, IPA voiced velar stop) appears in 12+ languages but is not mapped. The DOLGOPOLSKY dict maps **g** (U+0067, ASCII) to K, but the IPA standard character is ɡ (U+0261). These are visually identical but have different codepoints.
- **ː** (length mark) is universally present and silently dropped.
- **ʕ** (pharyngeal fricative) is critical for Semitic languages (Ugaritic, Hebrew, Phoenician, Arabic, Proto-Semitic).
- **ħ** (voiceless pharyngeal fricative) is critical for Semitic and Proto-Indo-European.
- **ʰ** (aspiration) appears 23,040 times in Greek alone.
- **χ** (voiceless uvular fricative) appears 694 times in Hebrew.
- **ʁ** (uvular approximant) appears 968 times in Hebrew.

**IMPACT:** When SCA is recomputed from IPA (as happens for entries with empty SCA column -- 8 in Hittite, 69 in Akkadian, 1,772 in Greek), these characters vanish. A Greek word like `tʰeːos` ("god") becomes SCA `TVS` instead of the expected `THEVS` or similar. This changes the effective string length and creates phantom matches.

**RECOMMENDATION:** Extend the DOLGOPOLSKY dict to cover at minimum:
- ɡ (U+0261) -> K (like g)
- ʕ -> H (pharyngeal, group with laryngeals)
- ħ -> H (pharyngeal fricative)
- χ -> K (uvular fricative)
- ʁ -> R (uvular approximant, group with rhotics)
- ɸ -> P (bilabial fricative)
- β -> P (bilabial approximant/fricative)
- c -> K (voiceless palatal stop)
- ç -> S (voiceless palatal fricative)
- ʝ -> J (voiced palatal fricative)
- y -> V (close front rounded vowel)
- Ignore ː, ʰ, ʷ, ˤ and other diacritics/modifiers (strip them).

### 1.4 Lexicon Subsampling Is Not Random

**SEVERITY: HIGH**

**DESCRIPTION:** `load_lexicon()` (line 164) caps at 3,000 entries by taking the **first 3,000 rows** of the TSV file. For Greek (121,659 entries), this means:
- The first 3,000 rows contain entries sourced from `wikipron` starting from the beginning of the Greek alphabet.
- Zero entries from the capped Greek subset have `Concept_ID` values; 2,197 unique concepts exist only in rows 3,001+.
- The cap produces a biased sample covering only words starting with alpha through early beta (βαλλ-).

**EVIDENCE:** 
```
Words at row 2995-3005: ['βαλλήν', 'βαλλήν', 'βαλλίζω', ...]
Unique concepts in first 3k: 0
Unique concepts in rest: 2,197
```

**IMPACT:** The null distribution is computed against an alphabetically biased subsample, not a representative sample of the language's vocabulary. Words starting with later letters are entirely absent. This biases both real match distances and null distributions.

**RECOMMENDATION:** If capping is needed, use random sampling (seeded for reproducibility) or frequency-weighted sampling. Do not take first-N rows.

### 1.5 Encoding Consistency

**SEVERITY: LOW** -- No BOM detected. Mixed line endings (CRLF for wiktionary-sourced files, LF for northeuralex-sourced). Python's `csv` module handles both, so this is cosmetic.

### 1.6 HF SDK Repo Consistency

**SEVERITY: MEDIUM**

**DESCRIPTION:** The HF SDK repo (`ancient-scripts-datasets-NEW/`) contains a proper IPA parser (`src/ancient_scripts_data/ipa.py`) that handles tie bars, combining diacritics, length marks, and modifier letters correctly. Ventris1 does NOT use this parser. Instead, it uses the naive character-by-character `ipa_to_sca()` which drops all diacritics.

The HF SDK parser would correctly segment `tʰeːos` into `['tʰ', 'eː', 'o', 's']` (4 segments) while the Ventris1 function processes character-by-character and drops ʰ and ː entirely.

**RECOMMENDATION:** Import and use the HF SDK's `parse_ipa_segments()` to properly segment IPA before applying Dolgopolsky class mapping per segment (not per character).

---

## 2. Code Review

### 2.1 Permutation Null Is Degenerate -- CRITICAL

**SEVERITY: CRITICAL**

**DESCRIPTION:** The `permutation_null()` function in `constrained_sca_search.py` (lines 187-206) is mathematically degenerate. It:
1. Extracts the SCA strings from the lexicon into `sca_pool`.
2. Subsamples to `NULL_CAP` (500) entries if needed (done ONCE).
3. Loops `N_PERMS` (100) times, shuffling `sca_pool` each iteration.
4. Computes `min(NED(query, s) for s in sca_pool)` each iteration.

**The `min()` function is invariant to ordering.** Shuffling a list and then taking the minimum gives the same result every time. The null distribution is a single constant value repeated 100 times.

**EVIDENCE:** Simulation confirms all 10 shuffle iterations produce identical values:
```python
results = [0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25]
All identical? True
```

**IMPACT:** The p-value computation `sum(1 for nd in null_dist if nd <= best_dist) / len(null_dist)` produces only two possible values: 0.0 (if real best < subsampled best, which happens when `search_lexicon` uses more entries than `NULL_CAP`) or 1.0 (if real best >= subsampled best). This explains the existing results showing `p=0.000` for everything -- the search uses the full lexicon (up to 3,000 entries) while the null uses only 500, so the real best is always at least as good.

**NOTE:** The PRD addresses this by proposing a Monte Carlo null with random SCA strings instead of shuffled lexicon entries. This is the correct approach. However, the PRD implementation sketch (Section 4.3) still has issues (see Section 4 below).

**RECOMMENDATION:** The new analytical null search MUST NOT reuse the `permutation_null()` function. The proposed Monte Carlo approach is fundamentally sound but must fix the SCA encoding mismatch (Issue 1.2) first.

### 2.2 `ipa_to_sca()` Drops Valid Phonemes

**SEVERITY: HIGH** (see 1.3 for details)

The function at line 112 strips any character not in the `DOLGOPOLSKY` dict. For the affricate `t͡s`, it produces `TS` (two SCA chars) instead of the correct `S` (one SCA char, sibilant class). This inflates SCA string lengths for languages with affricates (Greek, Latin, many others).

### 2.3 `normalized_edit_distance()` Implementation

**SEVERITY: OK** -- The Levenshtein DP implementation (lines 116-133) is correct. Space-optimized O(m) with proper initialization, substitution cost, and normalization by `max(n, m)`.

### 2.4 AB08 Reading Lookup Bug -- CRITICAL

**SEVERITY: CRITICAL**

**DESCRIPTION:** The corpus `sigla_full_corpus.json` has two entries for AB08 in its `sign_inventory`: one under reading `"a"` and one under reading `"AB08"`. The `ab_to_reading` construction loop (lines 48-52) iterates over both entries. Because `"AB08"` appears later in the dict, it overwrites the earlier mapping `AB08 -> "a"` with `AB08 -> "AB08"`.

**EVIDENCE:**
```
Mapping AB08 -> reading='a' (was: none)
Mapping AB08 -> reading='AB08' (was: a)
Final AB08 reading: AB08
```

**IMPACT:** AB08 is identified by P1 as the strongest vowel candidate (enrichment_score=2.718, confidence=0.906). In Linear B, AB08 definitively = 'a'. But because of this lookup bug, AB08 is treated as "unknown" throughout the entire pipeline. This affects **4 of the 21 target stems** (stems #5, #17, #18, #19), needlessly adding ~72 comparisons per language (4 stems x 18 languages x ~1 reading that should be fixed = 72 wasted hypothesis tests that are actually just 'a').

**RECOMMENDATION:** Fix the corpus data by removing the duplicate `"AB08"` entry from `sign_inventory`, or fix the lookup code to prefer the phonetic reading over the AB-code self-reference.

### 2.5 `sign_to_ipa.json` Contains Invalid IPA

**SEVERITY: LOW**

Entries `*301` -> `Θ` (U+0398, Greek capital theta) and `*56` -> `Φ` (U+03A6, Greek capital phi) are not valid IPA symbols. IPA uses lowercase θ (U+03B8) and ɸ (U+0278). Neither `Θ` nor `Φ` is in the DOLGOPOLSKY dict, so they would produce empty SCA strings.

These signs do not appear in any of the 21 target stems, so this is low-impact for this PRD, but indicates broader data quality issues.

---

## 3. Conceptual Issues

### 3.1 All 21 Target Stems Are Hapax Legomena -- CRITICAL

**SEVERITY: CRITICAL**

**DESCRIPTION:** Every single one of the 21 target stems has frequency=1 in the corpus. They each appear in exactly one inscription.

**EVIDENCE:** Direct query of P2 output confirms all 21 stems have `frequency: 1`.

**IMPACT:** A hapax legomenon could be:
- A genuine rare word
- A scribal error or correction
- An abbreviation
- A non-linguistic mark or ideogram misread as syllabograms
- An artifact of P2's segmentation algorithm

Building a decipherment argument on sign-groups that appear only once is extraordinarily fragile. Even one misread or incorrectly segmented sign-group would invalidate any result derived from it.

The PRD does not acknowledge this. The session report (Section 8) mentions "184 stems missing just one syllable" but does not flag the hapax issue.

**RECOMMENDATION:** 
1. Add a frequency filter: only use stems with frequency >= 2. This dramatically reduces the target set but increases reliability.
2. If frequency >= 2 yields too few 3+ sign stems, document this as a data limitation rather than proceeding with hapax stems.
3. At minimum, report hapax status prominently in the output and weight results by stem frequency.

### 3.2 SCA Vowel Collapse Discards P1 Information

**SEVERITY: MEDIUM** (acknowledged in PRD Section 7.1)

The PRD correctly notes that SCA maps all vowels to V, discarding vowel class information from P1. However, it underestimates the impact. The P1 grid assigns each unknown sign to a specific vowel class (e.g., AB60 -> V=0 "a"). This is the most reliable piece of phonological information available for these signs (95% accuracy on known signs). Collapsing it to V throws away the single strongest constraint.

**RECOMMENDATION:** Use a modified distance metric that:
- Maps consonants to Dolgopolsky classes as usual
- Maps vowels to their P1 vowel class (a=0, e=1, i=2, o=3, u=4) or at minimum distinguishes vowel from consonant (partial credit)
This would be straightforward: extend the SCA alphabet from 12 to 16 characters (HJKLMNPRST + 5 vowels).

### 3.3 "Words" vs Sign-Groups

**SEVERITY: MEDIUM**

The PRD and code consistently use the term "stems" (from P2 morphological segmentation), which is appropriate. However, the underlying assumption is that P2's segmentation is correct -- that these sign-groups represent actual morphological units. P2 uses a suffix-stripping approach with `segmentation_confidence: 1.0` for many entries, which likely reflects the algorithm's confidence in the segmentation pattern, not the probability that the sign-group is a real word.

Linear A word boundaries are unknown. The "sign-groups" in the corpus are separated by word-dividers on the original inscriptions, which is a reasonably reliable word boundary indicator. The P2 segmentation then further splits these into stems and affixes. This two-layer assumption (word-divider = word boundary, P2 segmentation = correct morphology) is shakier than the PRD acknowledges.

---

## 4. Statistical Method Audit

### 4.1 Monte Carlo Resolution vs BH-FDR -- HIGH

**SEVERITY: HIGH**

**DESCRIPTION:** The PRD settles on M=10,000 Monte Carlo samples (Section 10.3) after noting that M=100,000 is too slow. With m=12,780 comparisons, the minimum achievable p-value is 1/10,000 = 10^-4. But the BH-FDR threshold for the most significant result (rank 1) is:

```
(1/12780) * 0.05 = 3.91 x 10^-6
```

This is 25x smaller than the minimum achievable p-value. The most significant result CANNOT pass BH-FDR even if zero null samples match it, because the p-value is recorded as 1/M = 10^-4, not 0.

**EVIDENCE:** Mathematical analysis shows:
- Minimum passable rank: k >= 26 (i.e., at least 26 results must ALL have p=0/M to survive)
- For a result with true p-value of 10^-4, the probability of observing p=0 with M=10,000 is only 0.368

**IMPACT:** The method systematically fails to detect real cognates unless there are 26+ true positives, all with true p-values near zero. This is extremely unlikely given the signal-to-noise ratio acknowledged in the PRD.

**RECOMMENDATION:** Either:
(a) Use M=100,000 or more (requires the performance optimizations in Section 4.4 -- pre-computed null tables);
(b) Use the analytical formula (Method B) which provides exact p-values without Monte Carlo sampling;
(c) Use a pseudocount: p = (null_count + 1) / (M + 1) to avoid p=0 (standard practice in permutation testing).

### 4.2 BH-FDR Q-Value Formula

**SEVERITY: LOW**

The PRD's q-value formula in Section 5.2, step 5 reads: `q_(i) = min(p_(i) * m / i, 1.0), corrected for monotonicity`. The text says "corrected for monotonicity" but the formula shown does NOT implement the correction. The correct formula is applied backwards from rank m to rank 1: `q_(i) = min(p_(i) * m / i, q_(i+1))`. The PRD's formula can produce non-monotonic q-values.

**EVIDENCE:** For p-values [0.0001, 0.005, 0.0051, 0.04, 0.05], the PRD formula gives q = [0.0005, 0.0125, **0.0085**, 0.0500, 0.0500] which is non-monotonic (0.0125 > 0.0085). The correct formula gives [0.0005, **0.0085**, 0.0085, 0.0500, 0.0500].

**RECOMMENDATION:** Fix the formula in the PRD to explicitly show the backward pass.

### 4.3 PRDS Assumption Partially Violated

**SEVERITY: MEDIUM**

The PRD claims BH-FDR is valid because "shared lexicon entries create positive correlations" (PRDS). This is true for comparisons of different stems against the same language. However, comparisons of different readings for the SAME stem against the SAME language have NEGATIVE dependency: only one reading can be correct, so if reading A yields a good match, reading B is implicitly excluded.

**EVIDENCE:** ~458,000 comparison pairs (0.65% of all pairs) have negative dependency, primarily from the 2-unknown stems with ~100 reading combinations each.

**IMPACT:** Moderate. The fraction of negatively-dependent pairs is small enough that BH-FDR likely remains approximately valid, but the theoretical guarantee is broken.

**RECOMMENDATION:** Either use the BY procedure (valid under arbitrary dependency, costs a factor of log(m) ~ 9.5 in threshold), or restructure the hypothesis testing: test each (stem, language) pair as a single hypothesis using the BEST reading, then apply BH-FDR across (stem, language) pairs only. This reduces m from ~12,780 to ~378 and eliminates the negative dependency entirely.

### 4.4 Analytical Formula Errors

**SEVERITY: MEDIUM**

The PRD's analytical formula (Section 4.2, Method B) uses:
```
V(L, d, K) = sum_{i=0}^{d} C(L, i) * (K-1)^i
```

This counts **substitutions only** (Hamming ball volume). But `normalized_edit_distance()` uses Levenshtein distance, which also allows insertions and deletions. The formula underestimates the edit-distance ball volume by approximately 20% for d=1.

Additionally, the formula uses K=12 (Dolgopolsky alphabet), but the actual stored SCA uses K=17-20. This makes collision probability estimates 7.4x too high.

---

## 5. Validation Gate Audit

### 5.1 Gates 1 and 2: Cognate Pairs Not Specified

**SEVERITY: HIGH**

The PRD says to use "10 known Ugaritic-Hebrew cognate pairs" (Gate 1) and "10 known Latin-Oscan cognate pairs" (Gate 2) but does NOT list them. The implementation checklist says "curate 10 known cognate pairs" -- this is left as a TODO.

**IMPACT:** The gates cannot be evaluated because the test data does not exist. When eventually curated, the pairs must be:
- Sourced from published comparative linguistics literature (not invented)
- Using IPA transcriptions from the actual lexicon files (not hardcoded ideal forms)
- Covering a range of word lengths and phonological patterns

**RECOMMENDATION:** Specify the cognate pairs in the PRD with citations. For Gate 1, use established Northwest Semitic cognate lists (e.g., Segert 1984 "A Basic Grammar of the Ugaritic Language", or Huehnergard 2012 "An Introduction to the Comparative Study of the Semitic Languages"). For Gate 2, note that an Oscan lexicon (`osc.tsv`) exists in the dataset -- use it rather than the Greek-Latin fallback.

### 5.2 Gate 3: English-Akkadian Is Not Zero-Cognate

**SEVERITY: HIGH**

The PRD's false positive control uses "10 random English words" against Akkadian. This assumes English and Akkadian are unrelated, but:

1. English has numerous Semitic loanwords via Arabic (algorithm, algebra, alcohol, cotton, lemon, orange, sugar, zero, etc.)
2. English and Akkadian are both connected through Indo-European-Semitic contact and shared Wanderwort

If any of these loanwords are selected as "random" test words, the gate produces false negatives (real cognates incorrectly treated as expected negatives).

**RECOMMENDATION:** Use a genuinely unrelated language pair with zero known contact: Quechua-Akkadian, Navajo-Akkadian, or Basque-Hittite. Alternatively, use synthetic random strings (which have guaranteed zero cognate relationship with any language).

### 5.3 Gate Pass Criteria May Be Too Lenient

**SEVERITY: LOW**

Gate 1 requires 5/10 cognates recovered at FDR q < 0.10. Gate 3 requires 0/10 false positives at q < 0.05. These use different FDR thresholds (0.10 vs 0.05), which is inconsistent. More importantly, Gate 1's 50% recovery rate is very low for closely related languages like Ugaritic and Hebrew. If only half of known cognates survive FDR, the method is quite weak.

---

## 6. Output and Results

No analytical null search results have been produced yet. The existing `constrained_sca_results.txt` uses the broken permutation null and shows `p=0.000` for nearly everything, confirming the degenerate null finding (Issue 2.1).

---

## Issue Summary Table

| # | Severity | Area | Issue | Section |
|---|----------|------|-------|---------|
| 1 | CRITICAL | Data | SCA encoding mismatch: query uses V-collapse, lexicon uses AEIOU | 1.2 |
| 2 | CRITICAL | Code | Permutation null is degenerate (min is order-invariant) | 2.1 |
| 3 | CRITICAL | Code | AB08 reading overwritten by duplicate corpus entry | 2.4 |
| 4 | CRITICAL | Data | All 21 target stems are hapax legomena (freq=1) | 3.1 |
| 5 | HIGH | Data | 11-27% of IPA chars silently dropped by DOLGOPOLSKY dict | 1.3 |
| 6 | HIGH | Data | Lexicon cap takes first-N rows, not random sample | 1.4 |
| 7 | HIGH | Stats | M=10,000 Monte Carlo insufficient for BH-FDR with m=12,780 | 4.1 |
| 8 | HIGH | Gates | Cognate pairs for Gates 1-2 not specified | 5.1 |
| 9 | HIGH | Gates | Gate 3 English-Akkadian pair is not truly zero-cognate | 5.2 |
| 10 | MEDIUM | Data | HF SDK's proper IPA parser not used; naive char-by-char instead | 1.6 |
| 11 | MEDIUM | Concept | SCA vowel collapse discards P1 vowel class information | 3.2 |
| 12 | MEDIUM | Stats | PRDS assumption partially violated by mutually-exclusive readings | 4.3 |
| 13 | MEDIUM | Stats | Analytical formula counts substitutions only, not Levenshtein | 4.4 |
| 14 | LOW | Data | sign_to_ipa.json has uppercase Greek Theta/Phi (not IPA) | 2.5 |
| 15 | LOW | Stats | BH-FDR q-value formula in PRD doesn't show monotonicity correction | 4.2 |
| 16 | LOW | Gates | Gate pass criteria use inconsistent FDR thresholds | 5.3 |

---

## Recommended Fix Order

1. **Fix SCA encoding mismatch** (Issue 1) -- nothing else matters until queries and lexicon entries use the same alphabet.
2. **Fix AB08 reading bug** (Issue 3) -- reduces unnecessary comparisons and uses the strongest available phonological evidence.
3. **Extend DOLGOPOLSKY dict** (Issue 5) -- covers the most common unmapped IPA characters.
4. **Implement proper IPA segmentation** (Issue 10) -- use HF SDK's `parse_ipa_segments()` before class mapping.
5. **Fix lexicon subsampling** (Issue 6) -- random or frequency-weighted, not first-N.
6. **Increase M or use analytical formula** (Issue 7) -- M=100,000 minimum, or use exact p-values.
7. **Specify validation gate test data** (Issue 8) -- cite comparative linguistics sources.
8. **Replace Gate 3 language pair** (Issue 9) -- use genuinely unrelated languages.
9. **Add frequency filtering or weighting** (Issue 4) -- acknowledge and mitigate hapax fragility.
10. **Consider restructured hypothesis testing** (Issue 12) -- test best reading per stem per language, not all readings independently.

---

## Conclusion

The PRD demonstrates good methodological thinking -- the shift from permutation null to analytical null is correct, the choice of BH-FDR over Bonferroni is appropriate, and the self-consistency check is a valuable safeguard. However, the implementation infrastructure has fundamental bugs that would silently invalidate results. The SCA encoding mismatch alone means that no edit distance computed by this system is meaningful. Fix the four CRITICAL issues before writing any implementation code.
