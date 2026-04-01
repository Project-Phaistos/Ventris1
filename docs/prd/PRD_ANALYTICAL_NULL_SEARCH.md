# PRD: Analytical Null Cognate Search for 3+ Sign Linear A Stems

**Status:** Draft
**Date:** 2026-03-29
**Depends on:** Pillar 1 (P1 v5 grid), Pillar 2 (P2 segmented lexicon), sign_to_ipa.json
**Authors:** Alvin / Claude (design session)

---

## 0. Context for New Sessions

This PRD is part of the **Ventris1** project (`C:\Users\alvin\Ventris1\`), a computational pipeline for analyzing Linear A, the undeciphered Minoan script (~1800-1450 BCE). The pipeline has 5 pillars:

- **Pillar 1 (P1):** Phonological analysis -- produces a Kober-style grid assigning each Linear A sign to a consonant class and vowel class. Output: `results/pillar1_v5_output.json`.
- **Pillar 2 (P2):** Morphological segmentation -- splits Linear A words into stems and affixes. Output: `results/pillar2_output.json`.
- **Pillars 3-4:** Grammar and semantics (not directly used here).
- **Pillar 5:** Multi-source vocabulary resolution -- searches candidate language lexicons for cognate matches.

Linear A shares ~80% of its sign inventory with Linear B, which was deciphered by Michael Ventris in 1952. Linear B signs have known phonetic readings (e.g., AB08 = "a", AB27 = "re", AB07 = "wi"). Some signs in Linear A likely had the same readings as Linear B (the "LB transfer" assumption, supported by Packard 1974 at 2:1 to 5:1 odds). We currently have **54 signs with known/assumed IPA values** (`data/sign_to_ipa.json`).

The P1 grid assigns unknown signs to grid cells (consonant class x vowel class), constraining them to 2-5 possible CV readings per cell. For example, if sign AB60 is in vowel class 0 (the "a" column), its reading is one of {da, ka, ma, na, ra, sa, ta, wa, za, ...} depending on which consonant class it falls in. Currently P1 uses a single mega consonant class (C0), so all consonants are candidates for each unknown sign.

**Key file locations:**
- Project root: `C:\Users\alvin\Ventris1\`
- Sign-to-IPA mapping: `data/sign_to_ipa.json` (54 known sign readings)
- P1 grid output: `results/pillar1_v5_output.json`
- P2 morphology output: `results/pillar2_output.json`
- Corpus: `data/sigla_full_corpus.json` (879 inscriptions, 926 words)
- Candidate lexicons: `../ancient-scripts-datasets/data/training/lexicons/` (18 TSV files, each with Word/IPA/SCA/Concept_ID columns)
- Existing constrained search: `pillar5/scripts/constrained_sca_search.py`
- SCA search prototype: `pillar5/scripts/sca_cognate_search.py`
- Adversarial critique: `docs/logs/2026-03-27-hypothesis-test-results.md`
- Full session report: `docs/logs/2026-03-29-to-04-01-full-session-report.md`

### What was tried and why it failed

Eleven approaches were attempted for phonetic matching (documented in `docs/logs/2026-03-29-to-04-01-full-session-report.md`). The most promising was a **constrained SCA search** that showed **3.2x enrichment above chance** in aggregate (1,112 significant matches vs 346 expected false positives). However, an adversarial critique identified 3 fatal flaws:

1. **SCA too coarse at 2-sign stem length:** 4-character SCA strings have an 84% collision rate -- nearly every query matches some word in every language by chance.
2. **Permutation null insufficient:** With only 100-200 permutations, the minimum achievable p-value is 0.005-0.01. After Bonferroni correction across thousands of comparisons, the significance threshold is ~4.5x10^-6. The permutation null literally cannot produce p-values small enough.
3. **Grid consonant classes too broad:** All signs are in a single consonant mega-class (C0), so every unknown sign has 10+ candidate readings, inflating the multiple testing burden.

**This PRD addresses flaws 1 and 2.** Flaw 3 (consonant class resolution) is deferred to iterative refinement.

---

## 1. Objective

Find statistically significant cognate matches between Linear A stems of 3 or more signs and words in 18 candidate ancient languages, using:
- **Longer stems** (3+ signs = 6+ SCA characters) for sufficient discriminative power
- **Analytical null distributions** for arbitrarily precise p-values
- **BH-FDR correction** for proper multiple testing control

**Expected yield:** 1-3 candidate sign identifications with proper statistical support (FDR-corrected q < 0.05). Even 0 significant results is a valid finding -- it would mean the signal-to-noise ratio is insufficient at current grid resolution.

---

## 2. Non-Goals

- **Not a full decipherment system.** This is a focused one-shot search on the longest available stems. An iterative decipherment loop (where successful identifications feed back to unlock more stems) will be specified in a future `PRD_ITERATIVE_DECIPHERMENT.md`.
- **No consonant class refinement.** We use the P1 grid as-is (single C0 mega-class). Finer consonant discrimination is a separate workstream.
- **No new phonetic value discovery beyond what's in sign_to_ipa.json.** We use the 54 known readings. The search may SUGGEST new readings, but they are hypotheses to be validated, not established facts.
- **No morphological re-analysis.** We use P2 stems as-is.
- **No semantic scoring.** Pure phonological distance only. Semantic plausibility is a manual post-hoc check on any significant results.
- **No single-language ranking.** We are not asking "which language is Linear A related to?" We are asking "do any specific stem-word pairs survive FDR correction?"

---

## 3. The 21 Target Stems

Extracted from P2 output (`results/pillar2_output.json`) by selecting all stems with 3+ signs where at least one sign has a known IPA reading and unknown signs appear in the P1 grid.

### 3.1 Fully Phonetic (all signs known) -- 1 stem

| # | Stem IDs | Readings | IPA | SCA | SCA Len |
|---|----------|----------|-----|-----|---------|
| 1 | AB10-AB07-AB53 | u-wi-ri | u.wi.ri | VWVRV | 5 |

### 3.2 Partially Phonetic, 1 Unknown (in grid) -- 15 stems

| # | Stem IDs | Readings | IPA (? = unknown) | Unknown Sign | Vowel Class |
|---|----------|----------|--------------------|-------------|-------------|
| 2 | AB07-AB07-AB70-AB60-AB13 | wi-wi-ko-?-me | wi.wi.ko.?.me | AB60 | V=0 (a) |
| 3 | AB07-AB45-AB26-AB78 | wi-de-?-qe | wi.de.?.qe | AB26 | V=4 (u) |
| 4 | AB07-AB07-AB17 | wi-wi-? | wi.wi.? | AB17 | V=0 (a) |
| 5 | AB08-AB29-AB06 | ?-pu2-di | ?.pu.di | AB08 | V=0 (a) |
| 6 | AB39-AB26-AB38 | pi-?-e | pi.?.e | AB26 | V=4 (u) |
| 7 | AB39-AB37-AB24 | pi-?-ne | pi.?.ne | AB37 | V=2 (i) |
| 8 | AB39-AB59-AB44 | pi-?-ke | pi.?.ke | AB59 | V=0 (a) |
| 9 | AB45-AB58-AB47 | de-su-? | de.su.? | AB47 | V=0 (a) |
| 10 | AB53-AB59-AB46 | ri-?-je | ri.?.je | AB59 | V=0 (a) |
| 11 | AB53-AB69-AB16 | ri-?-qa | ri.?.qa | AB69 | V=4 (u) |
| 12 | AB57-AB28-AB48 | ja-?-nwa | ja.?.nwa | AB28 | V=2 (i) |
| 13 | AB57-AB80-AB10 | ja-?-u | ja.?.u | AB80 | V=0 (a) |
| 14 | AB60-AB45-AB13 | ?-de-me | ?.de.me | AB60 | V=0 (a) |
| 15 | AB61-AB76-AB07 | ?-ra2-wi | ?.ra.wi | AB61 | V=3 (o) |
| 16 | AB77-AB10-AB45 | ?-u-de | ?.u.de | AB77 | V=0 (a) |

### 3.3 Partially Phonetic, 2 Unknowns (both in grid) -- 5 stems

| # | Stem IDs | Readings | IPA (? = unknown) | Unknown Signs | Vowel Classes |
|---|----------|----------|--------------------|--------------|---------------|
| 17 | AB08-AB06-AB55-AB41-AB57 | ?-di-nu-?-ja | ?.di.nu.?.ja | AB08, AB41 | V=0(a), V=2(i) |
| 18 | AB08-AB41-AB58-AB11 | ?-?-su-po | ?.?.su.po | AB08, AB41 | V=0(a), V=2(i) |
| 19 | AB08-AB67-AB39-AB38 | ?-?-pi-e | ?.?.pi.e | AB08, AB67 | V=0(a), V=2(i) |
| 20 | AB16-AB81-AB27-AB06 | qa-?-?-di | qa.?.?.di | AB81, AB27 | V=4(u), V=1(e) |
| 21 | AB53-AB59-AB80-AB55 | ri-?-?-nu | ri.?.?.nu | AB59, AB80 | V=0(a), V=0(a) |

### 3.4 Stem Properties

- **SCA string lengths** (with unknowns filled): 5-12 characters. The 2-sign stems that failed had only 4 SCA chars. These 3+ sign stems have 6+ chars, which dramatically reduces collision probability.
- **Collision rate estimate:** For SCA alphabet K=12 and string length L=6, the probability two random strings match at edit distance <= 1 is approximately (L * (K-1) + 1) / K^L = 67/2,985,984 ~ 0.002%. Compare to 84% at L=4.
- **Candidate readings per unknown sign:** 5-15 depending on vowel class (all consonants in C0 + the cell's vowel). Typical: ~10 readings per unknown.
- **Total comparisons (upper bound):** 21 stems x ~10 readings/unknown x 18 languages = ~3,780 for 1-unknown stems. For 2-unknown stems, ~10x10 = 100 reading combinations each, adding ~5 x 100 x 18 = 9,000. Grand total: ~12,780 comparisons.

---

## 4. Analytical Null Distribution

### 4.1 The Problem with Permutation Nulls

The existing `constrained_sca_search.py` uses 100 permutations per null. This means:
- Minimum achievable p-value: 1/100 = 0.01
- After BH-FDR correction with ~12,780 comparisons, even the most generous FDR threshold requires raw p-values << 0.01
- The permutation null is too coarse by orders of magnitude

### 4.2 Analytical Approach: Empirical Null via Random SCA Sampling

Rather than shuffling the real lexicon (which preserves phonotactic structure and inflates false positives), generate the null distribution analytically:

**Method A -- Monte Carlo with large N (recommended for v1):**

For a query SCA string Q of length L, and a lexicon of N entries:
1. Generate M = 100,000 random SCA strings of length L, drawn uniformly from the 12-class SCA alphabet.
2. For each random string, compute the minimum normalized edit distance to the same lexicon.
3. The null distribution is the empirical CDF of these M minimum distances.
4. The p-value for a real match distance d is: P(D_null <= d) = (count of null distances <= d) / M.

This gives p-value resolution of 1/100,000 = 10^-5, which is sufficient for BH-FDR with ~12,780 tests.

**Why uniform random SCA strings (not shuffled lexicon):**
- Shuffled lexicon preserves language-specific phonotactic patterns (e.g., Akkadian's preference for CVC syllables), which inflates match rates for phonotactically similar queries.
- Uniform random strings are the correct null for "does this SCA string match any word in this lexicon better than a random string of the same length would?" -- a pure phonological coincidence null.

**Method B -- Analytical formula (optional refinement):**

For a query string Q of length L over alphabet of size K, the expected number of strings at edit distance <= d in a pool of N strings of comparable length is approximately:

```
E[matches at dist <= d] ~ N * V(L, d, K) / K^L
```

where V(L, d, K) is the volume of the edit distance ball of radius d around a string of length L. For normalized edit distance threshold t = d/L:

```
V(L, d=floor(t*L), K) = sum_{i=0}^{d} C(L, i) * (K-1)^i   [substitutions only, lower bound]
```

The exact distribution of the minimum edit distance over N independent random strings follows:

```
P(min_dist > d) = (1 - V(L,d,K)/K^L)^N
p-value = P(min_dist <= d) = 1 - (1 - V(L,d,K)/K^L)^N
```

Reference: Lippert et al. (2002) "Distributional Regimes for the Number of k-Word Matches Between Two Random Sequences" (covers the analogous substring matching case). For edit distance on full strings, see Durbin et al. (1998) "Biological Sequence Analysis" Ch. 5.

**Note on length matching:** Lexicon entries vary in length (2-15 SCA chars). The null must account for this. Two options:
- **(a)** Group lexicon entries by SCA length and compute separate nulls per length bucket, then combine (more precise but complex).
- **(b)** Use the actual length distribution from the lexicon when generating random SCA strings (sample lengths from the lexicon's empirical length distribution). **Recommended for v1.**

### 4.3 Implementation Sketch

```python
def analytical_null_pvalue(
    query_sca: str,
    lexicon_sca_strings: list[str],
    n_samples: int = 100_000,
    rng: random.Random = None,
) -> float:
    """Compute p-value for best match distance using analytical null.

    Generates n_samples random SCA strings with the same length distribution
    as the lexicon, finds the best match for each, and returns the fraction
    that are as good or better than the real best match.
    """
    K = 12  # SCA alphabet size
    SCA_ALPHABET = list("HJKLMNPRSTVW")
    L_query = len(query_sca)

    # Real best match
    real_best = min(
        normalized_edit_distance(query_sca, s)
        for s in lexicon_sca_strings if s
    )

    # Null distribution: random queries against same lexicon
    # Sample lengths from lexicon's empirical distribution
    lex_lengths = [len(s) for s in lexicon_sca_strings if s]

    null_count = 0
    for _ in range(n_samples):
        # Random SCA string of same length as query
        rand_sca = ''.join(rng.choice(SCA_ALPHABET) for _ in range(L_query))
        rand_best = min(
            normalized_edit_distance(rand_sca, s)
            for s in lexicon_sca_strings if s
        )
        if rand_best <= real_best:
            null_count += 1

    return null_count / n_samples
```

### 4.4 Performance Considerations

With N_lexicon entries per language and M=100,000 null samples, the inner loop is M * N_lexicon edit distance computations per (stem, reading, language) triple. For the largest lexicons:
- Greek (grc): 121,660 entries --> 100,000 * 121,660 = 12.2 billion edit distance ops. **Too slow.**

**Mitigation: SCA length bucketing + early termination.**
1. Pre-sort lexicon entries by SCA length.
2. For a query of length L, only compare against entries of length L-2 to L+2 (entries outside this range cannot achieve low normalized edit distance).
3. Use the analytical formula (Method B, Section 4.2) for large lexicons, falling back to Monte Carlo only for medium-sized ones.
4. Cap lexicon at 3,000 entries per language (the existing `constrained_sca_search.py` uses this cap).

**Alternative: pre-compute null tables.** For each (query_length, lexicon_size, lexicon_length_distribution) triple, the null CDF can be pre-computed once and reused across all queries of the same length. Since query lengths cluster around 6, 8, 10, this is ~3 tables per language.

---

## 5. BH-FDR Correction Procedure

### 5.1 Why BH-FDR, Not Bonferroni

Bonferroni controls the family-wise error rate (FWER) -- the probability of even ONE false positive. With ~12,780 comparisons, Bonferroni threshold = 0.05 / 12,780 = 3.9 x 10^-6. This is extremely conservative for an exploratory search.

Benjamini-Hochberg FDR controls the expected FALSE DISCOVERY RATE -- the fraction of reported discoveries that are false. At FDR=0.05, we accept that up to 5% of reported matches may be false positives. This is appropriate for generating hypotheses to be validated.

### 5.2 Procedure

1. Collect all p-values from all (stem, reading, language) comparisons.
2. Sort p-values in ascending order: p_(1) <= p_(2) <= ... <= p_(m) where m = total comparisons.
3. Find the largest k such that p_(k) <= (k/m) * alpha, where alpha = 0.05.
4. Reject all hypotheses with p_(i) <= p_(k) for i = 1, ..., k.
5. Report q-values (adjusted p-values): q_(i) = min(p_(i) * m / i, 1.0), corrected for monotonicity.

### 5.3 Multiple Testing Structure

The comparisons are NOT independent -- they share:
- The same lexicons (correlates p-values across stems within a language)
- The same unknown signs across different stems (correlates readings)

BH-FDR is valid under positive regression dependency (PRDS), which holds here because shared lexicon entries create positive correlations. Use the standard BH procedure, not the more conservative BY variant.

---

## 6. Candidate Lexicons

18 candidate languages, stored as TSV files in `../ancient-scripts-datasets/data/training/lexicons/`:

| Code | Language | Entries | Rationale |
|------|----------|---------|-----------|
| hit | Hittite | 281 | Dominant Anatolian power, trade contacts with Crete |
| xld | Lydian | 693 | Anatolian, possible substrate connection |
| xlc | Lycian | 1,098 | Anatolian, geographic proximity |
| xrr | Eteocretan | 187 | Successor script on Crete itself |
| phn | Phoenician | 180 | Semitic maritime trade partner |
| uga | Ugaritic | 467 | Semitic cuneiform, near-contemporary |
| elx | Elamite | 301 | Non-IE isolate, possible deep contact |
| xur | Urartian | 748 | Near Eastern, possible trade contact |
| peo | Old Persian | 486 | IE but late; phonological reference |
| xpg | Phrygian | 79 | Anatolian/Balkan, possible substrate |
| ave | Avestan | 1,926 | IE, phonologically conservative |
| akk | Akkadian | 24,341 | Semitic administrative language, known LA loanwords |
| grc | Ancient Greek | 121,659 | Linear B language, shared sign inventory |
| lat | Latin | 67,332 | IE reference, large lexicon |
| heb | Hebrew | 3,824 | Semitic, well-attested |
| arb | Arabic | 2,175 | Semitic, large consonant inventory |
| sem-pro | Proto-Semitic | 386 | Reconstructed Semitic ancestor |
| ine-pro | Proto-Indo-European | 1,704 | Reconstructed IE ancestor |

**Lexicon format** (TSV columns): `Word`, `IPA`, `SCA`, `Source`, `Concept_ID`, `Cognate_Set_ID`

The `SCA` column contains pre-computed Dolgopolsky sound class encodings. If missing or "-", compute on-the-fly from the `IPA` column.

**Lexicon cap:** 3,000 entries per language (existing practice from `constrained_sca_search.py`). Greek and Latin are subsampled. Consider frequency-weighted sampling to retain common vocabulary.

---

## 7. SCA Distance Metric

### 7.1 Dolgopolsky Sound Classes

The SCA (Sound Class Assignment) system maps all IPA phonemes to 12 broad classes:

| Class | Phonemes | Description |
|-------|----------|-------------|
| P | p, b, f, v | Labial stops/fricatives |
| T | t, d, (theta, eth) | Dental stops/fricatives |
| S | s, z, (esh, ezh) | Sibilants |
| K | k, g, x, q | Velar/uvular stops/fricatives |
| M | m | Labial nasal |
| N | n, (ny, ng) | Other nasals |
| L | l | Laterals |
| R | r | Rhotics |
| W | w | Labial glide |
| J | j | Palatal glide |
| H | h, (glottal stop) | Laryngeals |
| V | a, e, i, o, u, (schwa, etc.) | All vowels |

**Critical limitation:** All vowels collapse to V. This means SCA cannot distinguish "pa" from "pi" -- both encode as PV. This is a design feature (vowels are less stable across time/borrowing) but it means vowel class information from P1 is **not used** in the SCA comparison. A future refinement could weight vowel matches differently.

### 7.2 Normalized Edit Distance

```
NED(s1, s2) = levenshtein_distance(s1, s2) / max(len(s1), len(s2))
```

Range: [0, 1]. 0 = identical, 1 = completely different.

The existing implementation in `constrained_sca_search.py` (lines 116-133) is correct and efficient (O(n*m) DP).

---

## 8. Go/No-Go Validation Gates

Before running on Linear A stems, validate the method on KNOWN cognate pairs.

### Gate 1: Ugaritic-Hebrew Cognate Recovery

Ugaritic and Hebrew are closely related Northwest Semitic languages with well-established cognate pairs.

**Test:** Take 10 known Ugaritic-Hebrew cognate pairs. For each Ugaritic word:
1. Compute SCA encoding.
2. Search the Hebrew lexicon using the analytical null.
3. Check whether the known Hebrew cognate appears in the top-5 matches.
4. Check whether the p-value is significant after FDR correction.

**Pass criterion:** At least 5/10 known cognates recovered at FDR q < 0.10.

**Rationale:** If the method cannot recover known cognates between closely related languages with similar-length words, it has no hope on Linear A.

### Gate 2: Latin-Oscan Cognate Recovery

Latin and Oscan are Italic languages with documented cognate pairs.

**Test:** Same procedure as Gate 1, using Latin words against the Oscan entries (if available as a separate lexicon, or substitute with Proto-Italic reconstructions).

**Pass criterion:** At least 3/10 known cognates recovered at FDR q < 0.10.

**Fallback if Oscan data unavailable:** Use Greek-Latin known cognates (e.g., Greek pater / Latin pater, Greek meter / Latin mater). These are more distant but well-documented.

### Gate 3: False Positive Control

**Test:** Search 10 random English words (encoded as SCA) against the Akkadian lexicon. English and Akkadian have zero cognate relationship.

**Pass criterion:** 0 out of 10 survive FDR correction at q < 0.05.

**Rationale:** If unrelated languages produce FDR-surviving matches, the null is miscalibrated.

### Decision Matrix

| Gate 1 | Gate 2 | Gate 3 | Decision |
|--------|--------|--------|----------|
| PASS | PASS | PASS | Proceed to LA search |
| PASS | PASS | FAIL | Null is too permissive -- recalibrate |
| PASS | FAIL | PASS | Method works for close pairs only -- proceed with caveats |
| FAIL | any | any | Method is not viable -- STOP |

---

## 9. Self-Consistency Check

Multiple stems share the same unknown sign. If the search assigns sign AB60 the reading "ra" based on stem #2 but "ka" based on stem #14, that's inconsistent and both results are suspect.

### 9.1 Shared Unknown Signs

From the target stem list, signs that appear as unknowns in multiple stems:

| Sign | Vowel Class | Appears in Stems |
|------|-------------|-----------------|
| AB60 | V=0 (a) | #2, #14 |
| AB26 | V=4 (u) | #3, #6 |
| AB59 | V=0 (a) | #8, #10, #21 |
| AB08 | V=0 (a) | #5, #17, #18, #19 |
| AB41 | V=2 (i) | #17, #18 |
| AB80 | V=0 (a) | #13, #21 |

### 9.2 Consistency Scoring

After all searches complete, for each unknown sign that appears in 2+ stems:

1. Collect the set of (reading, language, q-value) triples from FDR-surviving matches.
2. Check whether the same reading dominates across stems.
3. Report a **consistency score**: (# stems where best reading agrees) / (# stems with any FDR-surviving match).

A sign identification is **CONFIRMED** only if:
- Consistency score >= 0.75 (at least 3/4 of contributing stems agree)
- At least 2 independent stems contribute
- At least one match has q < 0.01

A sign identification is **TENTATIVE** if:
- Only 1 stem contributes, but with q < 0.01
- OR 2+ stems contribute with consistency >= 0.5

Everything else is **INCONCLUSIVE**.

---

## 10. Pipeline Architecture

### 10.1 Stages

```
Stage 0: Load & Validate
  - Load P1 grid, P2 lexicon, sign_to_ipa.json, corpus
  - Extract the 21 target stems (3+ signs, at least 1 known reading, unknowns in grid)
  - Pre-compute candidate readings for each unknown sign from grid cell

Stage 1: Validation Gates
  - Run Gates 1-3 (Section 8)
  - If any gate fails: STOP, report failure, do not proceed

Stage 2: Enumerate All Hypotheses
  - For each stem, for each combination of candidate readings for unknown signs:
    - Construct complete IPA string
    - Compute SCA encoding
    - Record (stem_id, reading_hypothesis, sca_string) triple

Stage 3: Search
  - For each (stem, reading, language) triple:
    - Find best SCA match in the language's lexicon
    - Compute analytical null p-value
  - Total: ~12,780 comparisons (estimate)

Stage 4: FDR Correction
  - Collect all p-values
  - Apply BH-FDR at alpha = 0.05
  - Report q-values

Stage 5: Self-Consistency
  - For shared unknown signs, check reading agreement across stems
  - Classify identifications as CONFIRMED / TENTATIVE / INCONCLUSIVE

Stage 6: Output
  - Write results JSON (Section 11)
  - Print summary table to stdout
```

### 10.2 Script Location

`pillar5/scripts/analytical_null_search.py`

Reuse from existing code:
- `normalized_edit_distance()` from `constrained_sca_search.py`
- `ipa_to_sca()` and `DOLGOPOLSKY` dict from `constrained_sca_search.py`
- `load_lexicon()` from `constrained_sca_search.py`
- `find_partial_stems()` logic from `constrained_sca_search.py` (modified for 3+ signs)
- Grid loading and candidate reading enumeration from `constrained_sca_search.py`

### 10.3 Runtime Estimate

With lexicon cap of 3,000 entries:
- Per comparison: 3,000 edit distance calculations (real) + 100,000 * 3,000 (null) = 300M ops. Even at 1M ops/sec, this is 300 seconds per comparison. **Too slow for M=100,000.**

**Revised approach: M=10,000 with pre-computed null tables.**
- Pre-compute null CDF for each (query_length, language) pair once.
- ~18 languages * ~5 distinct query lengths = ~90 null tables.
- Each null table: 10,000 samples * 3,000 lexicon comparisons = 30M ops. At ~5M edit-dist/sec in Python: ~6 seconds per table, ~540 seconds total for all tables.
- Then each real comparison is just 1 lookup: O(1).
- Total: ~10 minutes for null tables + ~12,780 real searches (instant).
- **Target: under 15 minutes on local Windows CPU.**

---

## 11. Output Format

### 11.1 JSON Output

```json
{
  "metadata": {
    "timestamp": "2026-XX-XX...",
    "n_stems": 21,
    "n_comparisons": 12780,
    "n_languages": 18,
    "null_method": "monte_carlo_random_sca",
    "null_samples": 10000,
    "fdr_alpha": 0.05,
    "validation_gates": {
      "gate1_ugaritic_hebrew": {"status": "PASS", "recovered": 6, "out_of": 10},
      "gate2_latin_oscan": {"status": "PASS", "recovered": 4, "out_of": 10},
      "gate3_false_positive": {"status": "PASS", "false_positives": 0, "out_of": 10}
    }
  },
  "fdr_results": [
    {
      "stem_ids": ["AB07", "AB07", "AB70", "AB60", "AB13"],
      "readings": ["wi", "wi", "ko", "ra", "me"],
      "reading_for_unknown": {"AB60": "ra"},
      "complete_ipa": "wiwi.ko.ra.me",
      "complete_sca": "WVWVKVRVMV",
      "language": "hit",
      "matched_word": "...",
      "matched_ipa": "...",
      "matched_sca": "...",
      "gloss": "...",
      "ned_distance": 0.200,
      "raw_p_value": 0.00012,
      "q_value": 0.034,
      "significant": true
    }
  ],
  "sign_identifications": [
    {
      "sign_id": "AB60",
      "best_reading": "ra",
      "confidence": "TENTATIVE",
      "consistency_score": 0.5,
      "n_contributing_stems": 2,
      "best_q_value": 0.034,
      "supporting_evidence": [...]
    }
  ],
  "summary": {
    "total_significant": 3,
    "confirmed_signs": 0,
    "tentative_signs": 2,
    "inconclusive_signs": 4
  }
}
```

### 11.2 Stdout Summary

Human-readable table showing:
1. Validation gate results (PASS/FAIL)
2. FDR-surviving matches sorted by q-value
3. Self-consistency analysis per unknown sign
4. Sign identification summary (CONFIRMED / TENTATIVE / INCONCLUSIVE)

---

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Zero FDR-surviving matches | HIGH | Low (valid null result) | Report as "insufficient signal at current grid resolution." Proceed to iterative decipherment. |
| Analytical null too conservative (uniform random SCA strings are easier to match than real language phonotactics) | MEDIUM | Lost true positives | Validate on Gates 1-2. If known cognates don't survive, the null is too stringent. Fallback: use language-specific phonotactic models for null generation. |
| Analytical null too permissive (real words have structure that random strings lack) | LOW | False discoveries | Gate 3 catches this. Also: real language words tend to have lower entropy than random strings, so the null should be conservative, not permissive. |
| Consonant mega-class inflates reading space | HIGH | Dilutes signal across too many readings | Accepted for v1. Mitigation: weight readings by prior probability from P1 grid confidence scores. |
| SCA vowel collapse loses discriminative power | MEDIUM | Can't distinguish candidates differing only in vowel quality | Accepted limitation of SCA. Future: use finer-grained distance metric (ASJP or custom) that partially distinguishes vowels. |
| Large lexicons (Greek, Latin) dominate by chance | MEDIUM | False language attribution | Length-matched null handles this: larger lexicons produce more chances for spurious matches, but the null distribution also shifts accordingly. Monitor: if Greek/Latin dominate FDR results, check whether they also dominate the null. |
| Stem segmentation errors in P2 | LOW | Wrong SCA strings | P2 segmentation confidence scores are available; filter out stems with seg_conf < 0.5 as a sensitivity check. |
| 2-unknown stems have combinatorial explosion | MEDIUM | Computation and multiple testing burden | 5 stems with 2 unknowns contribute ~9,000 of ~12,780 comparisons. Consider running 1-unknown stems first and only adding 2-unknown stems if signal is found. |

---

## 13. Success Criteria

| Level | Criterion | Interpretation |
|-------|-----------|----------------|
| **Full success** | 1+ CONFIRMED sign identifications (consistency >= 0.75, 2+ stems, q < 0.01) | Genuine decipherment progress. Feeds into iterative loop. |
| **Partial success** | 1+ TENTATIVE identifications (1 stem at q < 0.01, or 2+ stems at q < 0.05) | Hypotheses worth investigating further. |
| **Informative failure** | 0 FDR-surviving matches, but validation gates all pass | Signal-to-noise ratio insufficient at current grid resolution. Quantifies the gap. |
| **Method failure** | Validation gates fail | Method not viable even for known cognates. Abandon this approach entirely. |

---

## 14. Implementation Checklist

- [ ] Write `pillar5/scripts/analytical_null_search.py`
- [ ] Implement Gate 1 (Ugaritic-Hebrew known cognates) -- need to curate 10 known cognate pairs
- [ ] Implement Gate 2 (Latin-Oscan or Greek-Latin known cognates) -- curate pairs
- [ ] Implement Gate 3 (English-Akkadian false positive control)
- [ ] Implement analytical null p-value computation with pre-computed null tables
- [ ] Implement BH-FDR correction
- [ ] Implement self-consistency analysis
- [ ] Run validation gates -- GO/NO-GO decision
- [ ] Run full search on 21 target stems
- [ ] Write results to `results/analytical_null_search_output.json`
- [ ] Document findings in `docs/logs/`
