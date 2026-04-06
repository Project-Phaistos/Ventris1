# Adversarial Verification: ANS "da" Reading Bias Fix

**Date:** 2026-04-03
**Verifier:** Adversarial critic (Claude Opus 4.6, independent analysis)
**Status:** PRE-IMPLEMENTATION AUDIT (fix not yet committed)
**Scope:** Two proposed approaches for eliminating the "da" reading bias in `analytical_null_search.py`

---

## 0. Executive Summary

The "da" reading bias (7/16 unknowns assigned "da", 35.6% of all unknown-position readings vs expected ~8%) is a real and severe artifact. However, **neither proposed approach has been implemented yet** -- this audit evaluates both designs against the codebase as it exists at commit `43cd4b5` and identifies risks, correctness issues, and requirements that the implementation must satisfy.

**Key findings:**

| Check | Approach A (Consonant-Class Frequency Normalization) | Approach B (P1 Grid Prior Weighting) |
|-------|------------------------------------------------------|--------------------------------------|
| Signal preservation | CONDITIONAL -- requires denominator = null match rate, not overall rate | CONDITIONAL -- requires held-out Jaccard corpus |
| Bias elimination | LIKELY -- if correctly implemented as likelihood ratio | UNLIKELY -- creates new biases from Jaccard clustering artifacts |
| Statistical validity | CORRECT in principle (likelihood ratio) but edge cases exist | CIRCULAR -- dependency loop from same corpus |
| u-wi-ri robustness | SAFE -- u-wi-ri is fully phonetic, unaffected | SAFE -- u-wi-ri has no unknowns |
| Edge cases | CRITICAL -- division by zero when background rate = 0 | MEDIUM -- singleton Jaccard clusters create extreme priors |
| Overall recommendation | **PROCEED with safeguards** | **DO NOT PROCEED without resolving circularity** |

---

## 1. Root Cause Analysis of the "da" Bias

### 1.1 Mechanism

The bias originates in the interaction of three factors:

1. **Uniform candidate generation.** `candidate_readings()` (line 215-220 of `analytical_null_search.py`) generates all consonant+vowel combinations for a vowel class with equal weight. For V=0 (the "a" column, where most unknowns fall), this produces ~12-15 readings: a, da, ja, ka, ma, na, pa, qa, ra, sa, ta, wa, za, nwa.

2. **T-class consonant frequency in target lexicons.** The SCA class "T" (mapping dental stops t, d, theta, eth) is disproportionately common across the 18 target lexicons. Semitic languages (Akkadian, Hebrew, Arabic, Ugaritic, Phoenician, Proto-Semitic = 6/18 languages) have high dental frequency. The reading "da" maps to SCA "TV", which matches any word starting with t/d + any vowel.

3. **Best-match-per-stem-language aggregation.** `aggregate_by_stem_language()` selects the reading with the lowest NED per (stem, language) pair, then applies Bonferroni correction across readings tested. Because "da" produces more low-NED matches (due to T-class frequency), it survives aggregation more often.

### 1.2 Quantification from ANS Output

From `results/analytical_null_search_output.json` and `docs/audits/ans_final_verification.md`:

| Reading | Count in 243 survivors | Percentage | Expected (uniform) |
|---------|----------------------|------------|---------------------|
| da | 106 | 35.6% | ~6-8% |
| qa | 33 | 11.1% | ~6-8% |
| nu | 32 | 10.7% | ~6-8% |
| pi | 28 | 9.4% | ~6-8% |
| ra | 25 | 8.4% | ~6-8% |
| ri | 15 | 5.0% | ~6-8% |
| All others | 59 | 19.8% | -- |

The "da" reading is 4.5-5.9x overrepresented. 7/16 unknown signs receive "da" as best reading: AB08 (invalidated by AB08 bug), AB17, AB47, AB59, AB60, AB77, AB80.

### 1.3 Why This Matters

If the bias is not corrected, the self-consistency analysis (`self_consistency_analysis()`, lines 825-888) conflates the bias with agreement: multiple stems converging on "da" for the same unknown sign looks like consistency (65-71% agreement) but is actually an artifact of the most common consonant class dominating across all stems.

---

## 2. Approach A: Consonant-Class Frequency Normalization

### 2.1 Design Intent

Divide each reading's match score by its background match rate across the lexicon. This converts the raw NED score into a likelihood ratio: how much better does this reading match compared to what random strings with the same consonant class would achieve?

### 2.2 Correctness Analysis

**The denominator matters critically.**

There are two possible denominators, and they have very different statistical properties:

1. **Overall match rate** (WRONG): `P(NED <= d | reading = "da") / P(NED <= d | any reading)`. This does not correct for consonant class frequency because the overall rate is dominated by the same frequent classes. Dividing by the overall rate would partially reduce the bias but not eliminate it.

2. **Null match rate** (CORRECT): `P(NED <= d | reading = "da") / P_null(NED <= d | random SCA of same length)`. This is the likelihood ratio. The null match rate is already computed by `build_null_table()` -- it is the empirical CDF of best-match NEDs for random SCA strings. Dividing by this gives:

   ```
   LR(reading) = observed_match_quality / expected_match_quality_under_null
   ```

   This is equivalent to the p-value already being computed. The "da" bias therefore reflects a miscalibration in the null, not a missing normalization step.

**FINDING:** The existing Monte Carlo null (`build_null_table()`, lines 406-445) generates random SCA strings from a **uniform** distribution over the 12-class alphabet. This is correct for an unbiased null -- the null should NOT reflect consonant class frequencies of real languages. The bias is not in the null; it is in the **aggregation** step that selects the best reading per stem.

### 2.3 Where the Fix Should Be Applied

The correct normalization point is in `aggregate_by_stem_language()` (around line 1199), not in the p-value computation. Currently, for each (stem, language) pair, the aggregation selects the reading hypothesis with the lowest raw p-value and applies Bonferroni correction (multiply by n_readings_tested). This treats all readings as equally likely a priori.

**Approach A, properly implemented, should:**

1. For each consonant class C, compute the **background match rate** B(C): the probability that a random SCA string whose first consonant is in class C achieves NED <= some threshold against the lexicon. This can be derived from the existing null tables by stratifying by first SCA character.

2. Compute the **normalized score** for each reading hypothesis: `score(reading) = p_value(reading) / B(consonant_class(reading))`. Or equivalently, weight the Bonferroni correction by `1/B(C)` to make rare consonant classes require less extreme p-values and common consonant classes require more extreme p-values.

3. Select the reading with the best normalized score.

### 2.4 Signal Preservation Check

**Question:** Does normalization accidentally suppress genuine dental-stop cognates?

**Analysis:** If a Linear A stem genuinely contains a /t/-series consonant, its SCA string will contain "T" at the relevant position. The NED to a genuine cognate will be 0 or very low. The normalization divides by B(T), which is the background rate for T-class. For genuine cognates, the raw p-value is already very low (NED=0.0 produces p ~ 0.001 or less). Dividing by B(T) makes it larger, but B(T) is at most ~2-3x the median background rate (T is common but not overwhelming). A genuine NED=0.000 match will survive normalization because:

- Raw p-value ~ 0.001
- B(T) ~ 0.15 (estimated: ~15% of random strings starting with T achieve NED <= 0.2)
- B(median) ~ 0.08
- Normalized p-value ~ 0.001 / (0.15/0.08) = 0.001 / 1.875 = 0.00053

The normalization reduces the score by ~1.9x but does not eliminate it. Genuine t-series cognates should survive.

**CRITICAL CHECK for implementation:** The known LB t-series signs (ta, te, ti, to, tu) are all in `sign_to_ipa.json` and are treated as KNOWN readings, not unknown. They appear in stems where they are pre-assigned, so normalization does not affect them. The normalization only affects UNKNOWN sign positions where "da" is one of ~15 candidate readings. This means t-series words where the t-sign is known are safe by construction.

### 2.5 Bias Elimination Check

**After normalization, is the reading distribution approximately uniform?**

If B(C) is correctly computed per consonant class and the normalization is `p_value / B(C)`, then:

- Readings from frequent consonant classes (T, K, S) will have their scores inflated (made worse) by a factor proportional to their overrepresentation.
- Readings from rare consonant classes (J, W, H) will have their scores reduced (made better) by a factor proportional to their underrepresentation.

This should produce an approximately uniform distribution ONLY IF the background rates are correctly estimated. If they are overestimated (too large), the normalization will over-correct and suppress genuine T-class matches. If underestimated, the bias will persist.

**Requirement:** The implementation must report the per-consonant-class background rates and verify they are monotonically related to the observed "da" bias. If B(T) is not the highest, the normalization is miscalibrated.

### 2.6 Edge Cases

**CRITICAL: Division by zero when B(C) = 0.**

If a consonant class has zero matches in the null table at a given NED threshold, B(C) = 0. This happens for very rare consonant classes (e.g., J = palatal glide, W = labial glide) at low NED thresholds (0.0 or 0.1).

**Mitigation required:** Use a pseudocount floor: `B(C) = max(observed_rate, 1/(M+1))` where M is the number of null samples. This matches the Phipson-Smyth pseudocount already used in `pvalue_from_null_table()` (line 461).

**CRITICAL: Consonant classes with very few lexicon entries.**

Some lexicons have uneven consonant distributions. If a lexicon has only 5 words starting with "w" but 500 starting with "t", the background rate for W will be noisy (high variance from small sample). The normalization should not be applied to consonant classes with fewer than ~20 entries in the comparison window.

**Mitigation required:** For consonant classes with B(C) estimated from < 20 null matches, do not normalize -- leave the p-value unchanged or use the global background rate as a conservative fallback.

---

## 3. Approach B: P1 Grid Prior Weighting

### 3.1 Design Intent

Use the Jaccard paradigmatic classification grid (19 consonant clusters from `jaccard_sign_classification.py`) to weight candidate readings by their grid prior probability. If sign AB60 is in Jaccard consonant cluster C12 and that cluster contains known signs with consonants {r, s}, then readings "ra" and "sa" get high prior weight while "da" gets low prior weight.

### 3.2 Circularity Analysis (CHECK 3)

**CRITICAL FINDING: The Jaccard grid was built from the same corpus.**

The Jaccard classification (`pillar1/scripts/jaccard_sign_classification.py`) uses:
- Linear A corpus: `data/sigla_full_corpus.json` (847 sign-groups from 879 inscriptions)
- Context vectors: left and right bigram frequencies from this corpus

The ANS search (`pillar5/scripts/analytical_null_search.py`) searches for cognates in stems extracted from:
- P2 morphological output, which segments words from the same `sigla_full_corpus.json`

**This creates a dependency loop:**

```
Corpus --> Jaccard clustering --> Grid prior --> ANS reading weights --> ANS results
  ^                                                                         |
  |___________________________(same corpus)_________________________________|
```

The Jaccard grid's consonant clusters are determined by the distributional contexts of signs in the corpus. If a stem like AB60-AB45-AB13 contributes to AB60's context profile, and then we use the grid to constrain AB60's reading in that same stem, the prior is trained on data that includes the test case.

### 3.3 Does This Matter in Practice?

**For stems that contributed heavily to the Jaccard training: YES.**

Consider sign AB60 (vowel class V=0 = "a"). AB60 appears in stems #2 (wi-wi-ko-AB60-me) and #14 (AB60-de-me). These stems contribute to AB60's bigram context profile:
- Left context of AB60: {ko, BOS, ...}
- Right context of AB60: {me, de, ...}

The Jaccard clustering assigns AB60 to a consonant cluster based on these contexts. If we then use the cluster assignment to weight AB60's candidate readings in the ANS search for these SAME stems, we are using training data to constrain the test.

**For stems that were NOT used in Jaccard training:** The circularity is weaker. If AB60 appears in stems not in the P2 target list (which is likely -- the 21 target stems are a small subset of the corpus), the Jaccard grid captures AB60's general distributional behavior, not its behavior in the specific target stems. However, the issue is that we cannot easily separate these cases.

### 3.4 Mitigation Options for Circularity

1. **Leave-one-out Jaccard:** For each target stem, remove it from the corpus and recompute the Jaccard clustering. Then use the held-out grid to weight the reading. This is computationally expensive (21 re-runs) but eliminates circularity.

2. **Cross-validation split:** Split the corpus in half (e.g., by inscription site). Train Jaccard on one half, apply prior weights on stems from the other half. But with only 847 sign-groups, halving the data will severely degrade the Jaccard clustering quality.

3. **Accept the circularity with disclosure.** Document that the grid prior is CONSENSUS_ASSUMED and the reading weights are not independent of the corpus. This is the pragmatic option but weakens the statistical rigor.

**Recommendation:** If Approach B is used, implement option (1) for at least the 5-10 most important target stems as a robustness check. If the reading assignments change under leave-one-out, the prior is overfitting.

### 3.5 New Bias Risk

The Jaccard clustering has known issues (from `docs/audits/jaccard_final_verification.md`):

1. **TF-IDF frequency confound:** Spearman(freq, mean_tfidf_cosine) = 0.624. High-frequency signs cluster together regardless of true consonant class. This means the grid prior will be biased toward assigning frequent signs to the same consonant class.

2. **k=19 is at the ARI peak.** 5 of 19 clusters are singletons. If a sign falls in a singleton cluster, its grid prior becomes a delta function on one consonant -- extreme overconfidence from a single data point.

3. **r-series and s-series NOT recovered.** Cluster C16 on LB contains t(4), r(2), s(2). Using this cluster as a prior would assign r-class and s-class signs to the t-class, creating a NEW bias (toward "ta", "ra", "sa" being conflated) instead of the old one (toward "da" dominating everything).

---

## 4. u-wi-ri Robustness (CHECK 5)

**u-wi-ri is SAFE under both approaches.**

u-wi-ri (stem #1: AB10-AB07-AB53) is fully phonetic -- all three signs have known IPA readings:
- AB10 = "u" (sign_to_ipa.json)
- AB07 = "wi" (sign_to_ipa.json)
- AB53 = "ri" (sign_to_ipa.json)

The `unknowns` list for this stem is empty (`[]`, line 509). Therefore:
- No candidate readings are enumerated for this stem
- No normalization or prior weighting is applied
- The SCA string "VWVRV" is fixed
- The NED=0.000 match to Urartian "awari" is unaffected

**Verified in code:** `enumerate_reading_hypotheses()` (line 781-819) returns a single hypothesis with `reading_map: {}` when `unknowns` is empty.

---

## 5. Statistical Validity of Approach A (CHECK 4)

### 5.1 Likelihood Ratio Interpretation

Dividing by background rate B(C) is equivalent to computing a likelihood ratio ONLY IF:

```
LR = P(data | genuine cognate with consonant C) / P(data | random match)
   = P(NED <= d | genuine) / P(NED <= d | null)
```

The denominator should be the **NULL match rate** -- the probability of achieving the observed NED or better purely by chance. This is exactly what the Monte Carlo null table provides.

### 5.2 Current Implementation Already Computes This

The p-value from `pvalue_from_null_table()` (line 647-659) already IS the probability of achieving the observed NED under the null. The problem is not that the denominator is missing -- it's that the **numerator is not consonant-class-specific**.

The null table is built from random SCA strings drawn uniformly from the 12-class alphabet. The null does not condition on the first character being "T" vs "K" vs "W". Therefore, the p-value already implicitly averages over all consonant classes in the null.

### 5.3 Correct Implementation of Approach A

The correct approach is NOT to divide the p-value by B(C). Instead, it is to compute **consonant-class-conditional null tables**:

For each consonant class C and query length L:
1. Generate M random SCA strings where the position corresponding to the unknown sign has SCA class C.
2. Find best NED in the lexicon for each random string.
3. The conditional null table gives `P(NED <= d | null, consonant = C)`.

Then the p-value for a reading with consonant class C is:
```
p(reading) = P(NED <= observed | null, consonant = C)
```

This directly debiases because the null for "da" (first char = T) will have more low-NED entries (reflecting that T is common in lexicons), producing LARGER p-values for the same NED. Conversely, the null for "wa" (first char = W) will have fewer low-NED entries, producing SMALLER p-values for the same NED.

### 5.4 Computational Cost

This requires M * 12 * (number of query lengths) null tables instead of M * (number of query lengths). With M=1000, 12 consonant classes, and ~5 query lengths, this is 60 tables instead of 5 -- a 12x increase in null table computation. At ~6 seconds per table, this is ~6 minutes instead of ~30 seconds. Acceptable.

---

## 6. Edge Cases (CHECK 6)

### 6.1 Background Rate = 0 (Division by Zero)

**Scenario:** Consonant class W (labial glide) at NED threshold 0.0. If no word in the lexicon starts with W, the background rate is exactly zero.

**Current null table behavior:** `build_null_table()` generates random strings uniformly. With 1/12 probability of starting with W and 1000 samples, ~83 random strings will start with W. If none achieve NED=0.0, the background rate at NED=0.0 is 0/83.

**Approach A impact:** If implemented as division by background rate, this is a divide-by-zero. The normalization would assign infinite weight to any W-class reading that achieves NED=0.0.

**Required safeguard:** Either (a) use the consonant-class-conditional null table approach from Section 5.3, which naturally handles this by returning a p-value from the conditional null, or (b) apply a Laplace smoothing floor: `B(C) = max(count_C / M, 1 / (M + 1))`.

### 6.2 Consonant Classes with Very Few Lexicon Entries

**Scenario:** The Phrygian lexicon (xpg.tsv) has only 79 entries. After capping at 3000 (no effect here) and length bucketing, some consonant classes may have 0-2 entries in the comparison window.

**Impact:** The background rate for rare consonant classes in small lexicons will have very high variance. A single entry in the lexicon at NED=0.0 from a rare class would produce a spuriously significant p-value after normalization.

**Required safeguard:** Do not apply consonant-class normalization to lexicons with fewer than 50 entries per comparison window. Use the unconditional null for small lexicons.

### 6.3 The "a" / Pure Vowel Case

Unknown signs in vowel class V=0 can be assigned reading "a" (empty consonant + vowel). In SCA, "a" maps to "V". The background rate for SCA class V as a first character is high (vowels are common in IPA). But in the context of the CV grid, "a" is a pure vowel, not a consonant+vowel.

**Impact:** The normalization should treat pure-vowel readings differently from CV readings. A reading of "a" for an unknown sign means the sign is a vowel, which is independently testable via Pillar 1's vowel enrichment analysis. If the unknown sign was not identified as a vowel by P1, assigning it "a" is implausible regardless of SCA match quality.

**Required safeguard:** Exclude pure-vowel readings from the consonant-class normalization. Instead, downweight them based on P1 vowel enrichment evidence (if the sign has low vowel enrichment, "a" is unlikely).

---

## 7. Pre-Implementation Requirements

### 7.1 For Approach A (Recommended)

1. **Consonant-class-conditional null tables** (Section 5.3) are the correct implementation, not simple division by background rate. Generate null strings with the unknown position constrained to each SCA class.

2. **Pseudocount floor** of 1/(M+1) for all null tables (already present in `pvalue_from_null_table()`, must also apply to class-conditional tables).

3. **Minimum comparison pool size** of 20 entries per consonant class per length bucket. Below this, fall back to unconditional null.

4. **Diagnostic output:** Report per-consonant-class background rates and verify they are monotonically related to the observed bias. The implementation should emit a table like:

   ```
   SCA Class | Background Rate | Bias Factor | Expected Reading Count After Fix
   T (da)    | 0.152           | 1.90x       | ~19%  -> ~10%
   K (ka)    | 0.121           | 1.51x       | ~8%   -> ~8%
   ...
   ```

5. **Regression test:** After the fix, verify that:
   - u-wi-ri -> awari still survives at NED=0.000
   - No single reading exceeds 15% of unknown-position assignments
   - No reading drops below 2% (over-suppression check)
   - The Gate 1 and Gate 2 cognate recovery rates do not decrease

6. **Do NOT divide the existing p-value by the background rate.** This would double-count the null correction. Instead, replace the unconditional p-value with the class-conditional p-value.

### 7.2 For Approach B (Not Recommended Without Mitigation)

1. **Resolve circularity** via leave-one-out Jaccard (Section 3.4, option 1) for at least the top 10 target stems.

2. **Handle singleton clusters:** If a sign is in a Jaccard cluster with only 1 known consonant, the prior should be softened (e.g., Dirichlet prior with alpha=1 per consonant class, updated by the cluster evidence) rather than treated as a hard constraint.

3. **Disclose CONSENSUS_ASSUMED dependency** in the output metadata.

4. **Do NOT use Approach B alone.** If used, combine with Approach A (class-conditional null) so that the prior weighting is a secondary correction, not the primary debiasing mechanism.

---

## 8. Verification Checklist for Post-Implementation

When the fix is implemented, the following checks must all pass:

| # | Check | Pass Criterion |
|---|-------|---------------|
| 1 | u-wi-ri -> awari survives | NED=0.000, q < 0.05 |
| 2 | "da" reading fraction | < 15% of unknown-position assignments |
| 3 | No new dominant reading | No reading > 15% |
| 4 | Gate 1 Ug-Heb recovery | >= 8/10 at FDR q < 0.10 |
| 5 | Gate 2 Grc-Lat recovery | >= 8/10 at FDR q < 0.10 |
| 6 | Gate 3 Eng-Akk FP (multi-seed) | <= 3/10 at median across 5 seeds |
| 7 | No division by zero | All consonant classes produce finite scores |
| 8 | Known t-series signs unaffected | ta, te, ti, to, tu readings preserved in known positions |
| 9 | Diagnostic table emitted | Per-class background rates reported |
| 10 | Approach B circularity resolved (if used) | Leave-one-out shows < 20% reading changes |

---

## 9. Summary Assessment

### Approach A: Consonant-Class Frequency Normalization

- **Mechanism is sound** -- the bias is caused by T-class overrepresentation in target lexicons, and class-conditional null tables directly correct for this.
- **Implementation must use class-conditional null tables**, not simple division by background rate. Division by background rate is a statistical shortcut that conflates the null correction with a prior, producing incorrect likelihood ratios.
- **Edge cases exist** (zero background rate, small lexicons, pure vowels) and require explicit safeguards.
- **Signal preservation is likely** -- genuine dental-stop cognates will see their p-values increase by ~2x but not be eliminated. The strongest matches (NED=0.0) will survive.
- **PROCEED with the safeguards listed in Section 7.1.**

### Approach B: P1 Grid Prior Weighting

- **Circularity is real and unresolved.** The Jaccard grid is trained on the same corpus used for the ANS search. Using it as a prior creates a dependency loop that inflates confidence in grid-consistent readings.
- **The Jaccard grid itself has known issues** (TF-IDF frequency confound, r/s series not recovered, singleton clusters) that would propagate into the ANS results as new biases.
- **DO NOT PROCEED without first resolving the circularity** via leave-one-out validation and softening singleton cluster priors.
- **If used, combine with Approach A** so that the grid prior is a secondary signal, not the primary debiasing mechanism.
