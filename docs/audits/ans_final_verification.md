# Analytical Null Search -- Final Adversarial Verification

**Date**: 2026-04-03
**Verifier**: Adversarial audit (independent re-analysis of all claims)
**Output file**: `results/analytical_null_search_output.json`
**Test file**: `pillar5/tests/test_analytical_null.py`

---

## Claim 1: Gates 10/10 Ugaritic-Hebrew, 10/10 Greek-Latin, 3/10 English-Akkadian FP

**VERIFIED**: Partially

| Gate | Claimed | Actual (from output) | Independently Reproduced |
|------|---------|----------------------|--------------------------|
| Gate 1 (Ugaritic-Hebrew) | 10/10 PASS | 10/10 PASS | Tests pass |
| Gate 2 (Greek-Latin) | 10/10 PASS | 10/10 PASS | Tests pass |
| Gate 3 (English-Akkadian FP) | 3/10 | 3/10 (seed-dependent) | **3 to 8 across seeds** |

**CONCERN (MAJOR)**: Gate 3 is highly seed-dependent. Re-running with 5 different
seeds (42, 123, 7, 999, 2026) produced:

- Seed 42: **8/10 FP**
- Seed 123: 4/10 FP
- Seed 7: 5/10 FP
- Seed 999: 5/10 FP
- Seed 2026: 3/10 FP

The claimed "3/10" corresponds to the luckiest seed tested. The median is **5/10**,
meaning the Monte Carlo null rejects only half of obviously unrelated English words
against Akkadian. This is far worse than it appears. The gate's "PASS" threshold is
<= 5, which itself is extremely generous (a well-calibrated null should reject
all 10).

The false positive words and their Akkadian matches (seed 42):

| English Word | SCA | Akkadian Match | NED | q-value | Genuine? |
|---|---|---|---|---|---|
| computer | KVMPJVTVR | qumbutu | 0.222 | 0.010 | No (modern word) |
| basketball | PVSKVTPVL | pasuttu | 0.333 | 0.040 | No |
| elephant | VLVPVNT | Dilibat | 0.143 | 0.010 | No (proper name) |
| umbrella | VMPRVLV | Subula | 0.286 | 0.049 | No (theonym) |
| chocolate | TSVKLVT | suglutu | 0.286 | 0.049 | No |
| telephone | TVLVPVVN | Atalihan | 0.250 | 0.033 | No (anthroponym) |
| newspaper | NJVSPVVPVR | Ilu-pi-usur | 0.400 | 0.050 | No (anthroponym) |
| pineapple | PVVNVPVL | Abu-eriba | 0.250 | 0.033 | No (anthroponym) |

**Note**: Many Akkadian "matches" are proper names/theonyms, not common vocabulary.
The lexicon contains ~24,000 entries including names, massively inflating the
false-positive pool.

---

## Claim 2: FDR Survivor Rate 243/378 (64.3%)

**VERIFIED**: Yes (with caveats)

- Metadata states: `n_aggregated_hypotheses = 378`, `n_significant = 243`
- Math: 243/378 = 64.29% -- correct
- The output file contains exactly 243 results, ALL marked `significant: true`
  (non-significant results stripped from output)

**CONCERN (MAJOR)**: A 64.3% survival rate is implausibly high for a cognate
search across 18 unrelated-to-distantly-related languages. For comparison:

- q-value distribution: 0 results at q <= 0.01, 0 at q <= 0.02
- ALL 243 survivors cluster in q = 0.028-0.050
- 54 at q <= 0.03, 121 at q 0.03-0.04, 68 at q 0.04-0.05
- Zero results with highly significant q-values (all near the threshold)

This pattern -- all survivors clustered near the FDR boundary with none deeply
significant -- suggests the null is systematically too permissive rather than
detecting genuine signal. A real signal should produce a mixture of very strong
(q << 0.01) and moderate matches.

**NED distribution of 243 survivors**:

| NED Range | Count | Pct |
|-----------|-------|-----|
| 0.000 (perfect) | 32 | 13.2% |
| 0.101-0.200 | 133 | 54.7% |
| 0.201-0.300 | 62 | 25.5% |
| 0.301+ | 16 | 6.6% |

16 survivors (6.6%) have NED > 0.3, which is weak evidence. 32 perfect SCA
matches is the strongest subset.

---

## Claim 3: u-wi-ri -> Urartian "awari" (field) at NED=0.000

**VERIFIED**: Yes

- Urartian lexicon (`xur.tsv`), line 12: `awari\tawari\tAWARI\twiktionary\tfield\t-`
- `ipa_to_sca("uwiri")` = `VWVRV`
- `ipa_to_sca("awari")` = `VWVRV`
- `NED("VWVRV", "VWVRV")` = 0.000 -- **confirmed exact match**
- Source: Wiktionary -- **legitimate reference**
- Gloss: "field" -- **a common Urartian word, well-attested**

**Uniqueness check**: 7 entries in the Urartian lexicon have NED <= 0.2 to "uwiri":

| NED | Word | IPA | Gloss | Source |
|-----|------|-----|-------|--------|
| 0.000 | awari | awari | field | wiktionary |
| 0.200 | atara | atara | also? | oracc_ecut |
| 0.200 | euri | euri | lord | oracc_ecut |
| 0.200 | salari | salari | a profession? | oracc_ecut |
| 0.200 | saluri | saluri | plum | wiktionary |
| 0.200 | sehiri | sexiri | alive | oracc_ecut |
| 0.200 | sukuri | sukuri | with me? | oracc_ecut |

**awari is uniquely close** (NED=0.000 vs next-best NED=0.200). This is a
genuine, well-separated match.

**CONCERN (MINOR)**: While the SCA match is perfect, the actual phonemes differ:
u-w-i-r-i vs a-w-a-r-i. The vowels u/i map to the same SCA class V as a.
Dolgopolsky SCA conflates all vowels to "V", so any CVCVC pattern with the
same consonants w,r would match. The match is real at the SCA level but
whether it represents genuine linguistic affinity requires further analysis.

---

## Claim 4: 52 Tests All Passing

**VERIFIED**: Yes

```
52 passed in 410.12s (0:06:50)
```

All 52 tests pass. Full breakdown:

- TestNEDProperties: 8/8
- TestIPAToSCA: 6/6
- TestBHFDR: 8/8
- TestAnalyticalPvalue: 7/7
- TestAggregateByStomLanguage: 8/8
- TestNullDistribution: 5/5
- TestGate1UgariticHebrew: 2/2
- TestGate2GreekLatin: 2/2
- TestGate3FalsePositive: 2/2
- TestRandomSCANegativeControl: 4/4

**CONCERN (MINOR)**: Gate 3 test uses `assert g3["false_positives"] <= 5`, which
is extremely generous. The test passes even with 5/10 false positives. A stricter
threshold (e.g., <= 1) would fail most seeds.

---

## Step 5: AB08 Bug Status

**VERIFIED**: AB08 bug is PRESENT in analytical_null_search.py

The corpus file `data/sigla_full_corpus.json` contains TWO entries for AB08:

1. Under reading `"a"`: `confidence: "tier1"`, `ipa: "a"`, `count: 137`
2. Under its own key `"AB08"`: `confidence: "tier3_undeciphered"`, `ipa: "X121"`, `count: 3`

The `load_corpus()` function iterates the sign inventory and maps
`ab_to_reading[ab] = reading`. Since the second entry comes later, it
**overwrites** the correct mapping `AB08 -> "a"` with `AB08 -> "AB08"`.

**Impact**:

- 4 stems treat AB08 as unknown when it should be fixed as "a":
  - `AB08-AB29-AB06` (unknowns=[0]): 16 survivors affected
  - `AB08-AB06-AB55-AB41-AB57` (unknowns=[0,3]): 12 survivors affected
  - `AB08-AB41-AB58-AB11` (unknowns=[0,1]): 10 survivors affected
  - `AB08-AB67-AB39-AB38` (unknowns=[0,1]): 10 survivors affected
- **48 of 243 survivors (19.8%) used incorrect readings for AB08**
- These 48 results tested "da", "qa", "ra" at position 0 when the correct
  value is "a" (SCA = "V"). Results for these 4 stems are INVALID.
- AB08's identification as "best_reading: da" (31/48 = 65%) in the sign
  identifications table is **an artifact of the bug**, not a discovery.

---

## Step 6: Signal Quality Assessment

### 6a. "da" Dominance Bias

7 out of 16 unknown signs (43.8%) receive "da" as their best reading:
AB08, AB17, AB47, AB59, AB60, AB77, AB80.

Overall reading distribution for unknown sign positions across all 243 survivors:

| Reading | Count | Pct | Expected if Uniform |
|---------|-------|-----|---------------------|
| da | 106 | 35.6% | ~6-8% |
| qa | 33 | 11.1% | ~6-8% |
| nu | 32 | 10.7% | ~6-8% |
| pi | 28 | 9.4% | ~6-8% |
| ra | 25 | 8.4% | ~6-8% |
| ri | 15 | 5.0% | ~6-8% |
| All others | 59 | 19.8% | -- |

"da" appears at 35.6% of unknown positions -- 4-5x the expected rate under a
uniform distribution. This dominance is suspicious and likely reflects that "d"
(SCA class T) is the most common consonant onset across the 18 target lexicons,
not a genuine property of Linear A.

### 6b. Sign Reading Consistency

No sign achieves "CONFIRMED" confidence. Best consistency scores:

- AB61 = po (86%, but only 1 stem)
- AB37 = pi (71%, 1 stem)
- AB17 = da (71%, 1 stem)
- AB77 = da (71%, 1 stem)

Signs appearing in 2+ stems show lower consistency:
- AB08 = da (65%, 4 stems) -- **invalidated by bug**
- AB59 = da (67%, 3 stems)
- AB60 = da (50%, 2 stems)

The consistency scores are modest, and almost all "multi-stem" identifications
converge on "da" -- which is the bias, not the signal.

### 6c. Language Distribution

Survivors are spread nearly uniformly across all 18 languages (2-18 per language).
No single language dominates, which is consistent with noise (every language
matches equally well) rather than signal (one or two languages should dominate).

### 6d. q-value Concentration

All 243 survivors have q-values between 0.028 and 0.050. Zero results have
q < 0.01. This means every result barely passes the significance threshold.
A genuine signal would produce a bimodal distribution with some very strong
matches (q << 0.01).

---

## Summary Verdict

| # | Claim | Verified | Actual | Severity |
|---|-------|----------|--------|----------|
| 1a | Gate 1: 10/10 Ugaritic-Hebrew | YES | 10/10 | -- |
| 1b | Gate 2: 10/10 Greek-Latin | YES | 10/10 | -- |
| 1c | Gate 3: 3/10 English-Akkadian FP | MISLEADING | 3-8/10 (seed-dependent, median ~5) | MAJOR |
| 2 | FDR survivor rate 243/378 (64.3%) | YES (math correct) | 243/378, but all q near 0.05 | MAJOR |
| 3 | u-wi-ri -> awari at NED=0.000 | YES | Perfect SCA match, legitimate word | MINOR |
| 4 | 52 tests passing | YES | 52/52 | -- |
| -- | AB08 bug in analytical_null_search.py | BUG CONFIRMED | 48/243 (19.8%) survivors invalid | CRITICAL |
| -- | "da" reading bias | BIAS CONFIRMED | 35.6% of unknowns = da (expected ~8%) | MAJOR |
| -- | No deeply significant results | CONFIRMED | All q in [0.028, 0.050] | MAJOR |

### Overall Assessment

The Analytical Null Search infrastructure works correctly at the formula and
test level. Gates 1-2 confirm the method can detect known cognates. However:

1. **AB08 bug**: 19.8% of survivors are invalid because AB08 is incorrectly
   treated as unknown. This is the same class of bug previously fixed in
   `constrained_sca_search.py` but not propagated to `analytical_null_search.py`.

2. **Permissive null**: Gate 3 shows 3-8/10 false positives depending on seed.
   The 64.3% survivor rate with all q-values near 0.05 and no deeply significant
   results suggests the null is too weak to distinguish signal from noise at
   the current resolution (M=1000 Monte Carlo samples).

3. **"da" bias**: 7/16 signs get "da" as best reading, representing a
   systematic bias toward the most common consonant class in the target
   lexicons, not genuine phonetic identification.

4. **The u-wi-ri -> awari match is genuine** at the SCA level and is the
   strongest individual finding. It should be preserved through any re-analysis.

### Recommended Actions

- P0: Fix AB08 in `load_corpus()` or `sigla_full_corpus.json` (remove duplicate
  entry or prioritize tier1 over tier3). Re-run search.
- P0: Increase NULL_SAMPLES from 1000 to 10000+ for finer p-value resolution.
- P1: Tighten Gate 3 threshold to <= 2 and require seed-stability (pass on
  95% of seeds).
- P1: Investigate why "da" dominates -- likely a frequency artifact of T-class
  consonants in Semitic/Anatolian lexicons.
- P2: Report q-value distribution honestly. Cluster near 0.05 = weak evidence.
