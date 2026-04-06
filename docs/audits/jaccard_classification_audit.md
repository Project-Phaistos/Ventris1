# Adversarial Audit: Jaccard Paradigmatic Substitutability for Full Sign Classification

**Date:** 2026-04-03
**Auditor:** Claude (adversarial critic)
**Target:** `docs/prd/PRD_JACCARD_SIGN_CLASSIFICATION.md`
**Status:** DRAFT PRD -- pre-implementation audit

---

## Executive Summary

The PRD proposes using directional Jaccard similarity (left-context for consonants, right-context for vowels) to classify Linear A syllabograms into a consonant-vowel grid. The core idea is sound in principle, but empirical testing reveals **three critical issues** that threaten viability:

1. **The signal is real but dangerously weak.** On the combined LB validation corpus, same-consonant pairs have only 12% higher left-context Jaccard than cross-series pairs (0.386 vs 0.334). Cohen's d = 0.49 (small-to-medium effect). 40% of same-consonant pairs fall BELOW the mean of the different-consonant distribution.

2. **The eigengap heuristic will fail.** On the combined corpus, the Laplacian eigengap strongly favors k=1 (gap=0.764) with no subsequent gap exceeding 0.06. The spectral structure does not support 10-15 clusters. On the test corpus alone, the eigengap suggests k=4 at best.

3. **A massive frequency confound dominates the Jaccard matrix.** Context-set-size correlates with mean Jaccard at rho=0.965. High-frequency signs have large context sets that overlap with everything, creating an artifact that swamps the phonological signal.

The approach may still yield value after mitigation (frequency normalization, alternative clustering), but the current PRD does not address these issues and will produce a false positive at validation if implemented as written.

---

## Issue 1: The Left-Context Signal Is Real but Weak

**SEVERITY: CRITICAL**

### Description

The PRD's core claim (Section 3.1) is that "signs sharing a consonant tend to follow the same set of signs" and therefore left-context Jaccard captures consonant identity. This claim is tested empirically on the combined LB corpus (test corpus + HF lexicon, 2,485 unique words, 62 classifiable CV signs).

### Evidence

| Category | Mean J_left | N pairs | Cohen's d vs baseline |
|----------|------------|---------|----------------------|
| Same consonant, diff vowel | 0.3855 | 120 | 0.487 (small-medium) |
| Same vowel, diff consonant | 0.3267 | 364 | 0.147 (negligible) |
| Different both | 0.3045 | 1401 | (baseline) |

The signal exists (permutation p < 0.0001), but:
- The effect size is small (d = 0.49)
- 40% of same-consonant pairs have J_left below the mean of the different-both distribution
- The distributions overlap heavily (same-consonant IQR: 0.214-0.543; different-both IQR: 0.159-0.429)
- The margin between same-consonant and same-vowel is only 0.059 (less than the within-group standard deviation of 0.167)

On the test corpus alone (no HF supplement), the signal is even weaker:
- Mean intra-series J_left = 0.173 (n=35)
- Mean inter-series J_left = 0.108 (n=400)
- 25.5% of all J_left pairs are exactly zero (sparsity problem)

### Impact

Standard clustering algorithms require a clear separation between intra-cluster and inter-cluster similarities. With 40% overlap, hierarchical clustering will produce many misclassifications. The ARI >= 0.30 gate may be borderline achievable on the combined corpus but is very unlikely on the test corpus alone.

### Recommendation

- **Report both combined and test-corpus-only results.** If the method only works with the HF lexicon supplement, it cannot be considered validated for the test corpus size claimed in the PRD.
- **Consider weighted Jaccard** (frequency-weighted context overlap) to amplify the signal.
- **Set a more realistic ARI expectation.** ARI >= 0.15 may be more achievable given the effect size.

---

## Issue 2: Eigengap Heuristic Will Fail -- Laplacian Does Not Support k=10-15

**SEVERITY: CRITICAL**

### Description

The PRD (Section 3.2, Step 3) proposes using the eigengap heuristic on the Laplacian of J_left to determine the number of consonant series. LB has ~12 consonant series (d, j, k, m, n, p, q, r, s, t, w, z). The eigengap should show a clear gap at k=12.

### Evidence

**Combined corpus (62 CV signs):**

| Eigenvalue index | Value | Gap to next |
|-----------------|-------|-------------|
| 0 | ~0.000 | 0.764 |
| 1 | 0.764 | 0.056 |
| 2 | 0.820 | 0.008 |
| 3 | 0.828 | 0.017 |
| 4 | 0.845 | 0.012 |
| ... | ... | < 0.016 |

The eigengap overwhelmingly selects k=1 (single cluster). The gap of 0.764 at k=1 dwarfs all subsequent gaps. No gap after k=1 exceeds 0.056. The condition number is only 1.3, meaning the non-zero eigenvalues are tightly packed in a narrow band -- there is no spectral separation between clusters.

**Test corpus only (30 CV signs):**

The eigengap selects k=1 (gap=0.337) with a secondary gap at k=4 (gap=0.124). The target k=10 has a gap of only 0.009.

### Root Cause

The Jaccard similarity matrix is nearly complete (only 1.1% zero entries on combined corpus) and nearly uniform. When context sets are large (mean = 24.3 unique left neighbors per sign on combined corpus), every sign shares contexts with almost every other sign. The resulting similarity matrix resembles a noisy all-ones matrix plus a weak signal -- exactly the regime where spectral clustering fails.

### Impact

The eigengap heuristic, which is one of the three proposed methods for selecting k (Section 3.2, Step 3.2a), will consistently select k=1 or k=2. The silhouette sweep (3.2b) is also unlikely to find an optimum at k=10-15 given the overlap documented in Issue 1.

### Recommendation

- **Do not rely on eigengap for k selection.** Use domain knowledge (k=10-15 from LB) as a fixed parameter.
- **Consider Louvain community detection** at multiple resolution parameters, which the PRD mentions as an alternative.
- **Consider applying the Jaccard method to the DISTANCE matrix (1-J) with a threshold** to sparsify it before spectral clustering. A threshold at, e.g., J < 0.3 (zeroing out weak similarities) may create cleaner spectral structure.

---

## Issue 3: Frequency Confound Dominates the Jaccard Matrix

**SEVERITY: CRITICAL**

### Description

The PRD identifies frequency confound as a MEDIUM-severity risk (Section 8, row 4) and proposes checking Spearman correlation. The actual correlations are far worse than anticipated.

### Evidence

| Correlation | Spearman rho |
|-------------|-------------|
| Sign frequency vs left-context-set-size | 0.870 |
| Sign frequency vs mean Jaccard to all others | 0.850 |
| Left-context-set-size vs mean Jaccard to all others | **0.965** |

The correlation between context-set-size and mean Jaccard is 0.965 -- nearly perfect. This means the Jaccard matrix is almost entirely determined by how many unique contexts a sign has, which is a direct function of its frequency. High-frequency signs (ka, ta, ra, to, pa) will cluster together regardless of their consonant, because they all have large context sets that overlap extensively.

The PRD's own threshold (abs(rho) > 0.5 triggers frequency normalization) is exceeded by a factor of nearly 2.

### Impact

Without frequency normalization, clustering will produce groups stratified by frequency, not by phonological class. The k-series (ka=65, ke=30, ki=14, ko=50, ku=7) spans a 9:1 frequency range; ku will be grouped with other low-frequency signs rather than with ka/ko.

### Recommendation

- **Frequency normalization is not optional -- it is BLOCKING.** Do not proceed to clustering without it.
- **Normalize by expected overlap under independence:** E[|A & B|] = |A| * |B| / |universe|. Compute the excess Jaccard above this expectation.
- **Alternatively, use log-odds ratio** instead of raw Jaccard: log(J_observed / J_expected) where J_expected is computed from marginal context frequencies.
- **As a sanity check**, verify that after normalization, rho(freq, mean_normalized_Jaccard) < 0.3.

---

## Issue 4: Right-Context Jaccard Does NOT Preferentially Capture Vowel Identity

**SEVERITY: HIGH**

### Description

The PRD (Section 3.1) claims that right-context Jaccard captures vowel identity because "signs sharing a vowel tend to precede the same set of signs" via the dead vowel convention. Empirical testing contradicts this.

### Evidence

**Right-context Jaccard on combined LB corpus:**

| Category | Mean J_right |
|----------|-------------|
| Same consonant, diff vowel | 0.378 |
| Same vowel, diff consonant | 0.348 |
| Different both | 0.322 |

Same-CONSONANT pairs score higher than same-VOWEL pairs on right-context Jaccard. The dead vowel convention is too weak (27.5% shared vowels vs 20% expected by chance = only 1.37x enrichment) to dominate the right-context signal.

Cohen's d for same-vowel vs different-both is only 0.170 (negligible effect).

Specific examples confirm the problem. J_right(ta, ka) = 0.633 (same vowel) but J_right(ka, ke) = 0.632 (same consonant) -- indistinguishable. With context sets of size 40-52, two signs of similar frequency share ~70% of their right contexts regardless of phonological relationship.

### Impact

Right-context Jaccard cannot reliably distinguish vowel classes from consonant series. The method will conflate the two dimensions, producing a single "overall similarity" clustering rather than separate consonant and vowel partitions.

### Recommendation

- **Do not use raw right-context Jaccard for vowel classification.** The dead vowel signal is too weak.
- **The existing full-context Jaccard (F1=89%) works for vowel identification** because it asks a different question: "Is this sign a pure vowel?" (binary classification with a threshold), not "Which vowel class does this sign belong to?" (multi-class clustering). Keep the existing method for vowels.
- **If vowel classification is needed**, use the dead vowel bigram COUNTS (not just set membership) as features, or use the alternation-based method from kober_vowel_analysis.py.

---

## Issue 5: LB Validation Corpus Is Marginal for Directional Jaccard

**SEVERITY: HIGH**

### Description

The test corpus (142 inscriptions, 448 words, 1,249 tokens, 56 signs) is too small for reliable directional Jaccard on its own.

### Evidence

**Test corpus only (no HF supplement):**

| Metric | Value |
|--------|-------|
| Unique bigram types | 248 |
| Signs with >= 5 left-context neighbors | 22/56 (39%) |
| Signs with >= 3 left-context neighbors | 30/56 (54%) |
| Signs with < 3 left-context neighbors | 26/56 (46%) |
| Mean left-context set size | 3.9 |
| J_left pairs that are exactly 0 | 25.5% |

Nearly half the signs cannot be classified due to insufficient context data. The pure vowels (a, e, i, o, u) each have only 1 left-context neighbor (BOS) because they overwhelmingly appear word-initially in the test corpus. Signs like du, nu, qo, se, za, ze, zo have counts < 5 and are automatically excluded.

**Combined corpus (test + HF lexicon):**

| Metric | Value |
|--------|-------|
| Signs with >= 5 left-context neighbors | 67/84 (80%) |
| Signs with >= 3 left-context neighbors | 69/84 (82%) |
| Mean left-context set size | 24.3 |

The HF supplement transforms the picture: coverage jumps from 39% to 80%. But this introduces a different problem (Issue 6).

### Impact

If the PRD requires validation on the test corpus, only 22-30 signs are classifiable, covering only 6-10 consonant series with 2-4 signs each. This is barely above the minimum for meaningful clustering.

### Recommendation

- **The PRD must specify which corpus is the validation target.** If it is the test corpus alone, lower the coverage and ARI expectations. If it is the combined corpus, acknowledge the data-mixing issues (Issue 6).
- **Consider building a larger LB inscription corpus** from published tablet readings (Ventris & Chadwick 1973 has ~4,000 words, not 448).

---

## Issue 6: HF Lexicon Is a Vocabulary List, Not a Corpus

**SEVERITY: MEDIUM**

### Description

The HF `linear_b_words.tsv` (2,478 entries) is a vocabulary list compiled from Shannon's lexicon (2,261 entries), Wiktionary (175), and IECoR (42). Each word appears once regardless of its actual frequency in Mycenaean Greek texts. The PRD treats it as a corpus supplement without acknowledging this fundamental difference.

### Evidence

- 91% of entries come from `shannon_lexicon` (a dictionary)
- Each word appears exactly once (TYPE frequency, not TOKEN frequency)
- Rare words like `a-ke-re-mo` (possibly a hapax in the actual tablets) get the same weight as common words like `ka-ko`
- Context sets derived from the lexicon reflect lexical diversity (how many distinct words contain the bigram), not phonological regularity (how often the bigram occurs in running text)
- The combined corpus has 2,485 unique words but the test corpus has only 116 -- meaning 95% of the bigram evidence comes from the lexicon

### Impact

1. **Inflated context set sizes.** With 24.3 mean left-context neighbors (vs 3.9 for the test corpus), the lexicon dominates the signal. But lexical diversity may not correlate with phonological structure.
2. **Loss of frequency information.** The Jaccard method uses set membership (is this bigram attested?) rather than frequency (how often does it occur?). Rare words contribute equally to context sets, potentially introducing noise from unusual word formations.
3. **Deduplication hides the problem.** The PRD says "combine and deduplicate" but the 62 overlapping words (2.5% of combined) are dwarfed by the 2,431 HF-only words.

### Recommendation

- **Report results separately** for test-corpus-only and combined corpus.
- **Weight bigrams by token frequency** when available (the weighted Jaccard variant in Section 3.3). Bigrams attested only in the lexicon should receive lower weight than those attested in actual inscriptions.
- **Be explicit that the combined corpus is 95% lexicon** and acknowledge this in the validation report.

---

## Issue 7: Orthogonality Check Is Necessary but Not Sufficient

**SEVERITY: MEDIUM**

### Description

The PRD (Section 3.2, Step 5) proposes checking that consonant and vowel classifications have low mutual information (MI near zero) as an "orthogonality" validation. The logic is: in a true CV grid, consonant and vowel are independent dimensions.

### Flaw

Low MI between two random partitions is *expected*, not exceptional. Two random k-clusterings of N items will have MI near zero simply because they are unrelated. The orthogonality check confirms that the two classifications are *different* from each other, not that either is *correct*.

Consider: partition A groups signs by frequency quintile. Partition B groups signs alphabetically by sign name. MI(A, B) is approximately zero. Both are orthogonal and both are wrong.

### Impact

The orthogonality check (Gate 5) will pass for almost any pair of clusterings that use different features, including frequency-driven artifacts. It provides no discriminative power against the failure modes documented in Issues 1-4.

### Recommendation

- **Keep the orthogonality check but do not rely on it.** It is a weak necessary condition, not a sufficient one.
- **Add a stronger validation:** For each consonant series, verify that it contains signs from at least 3 different vowel classes (ideally all 5). For each vowel class, verify it spans at least 5 different consonant series. This "coverage" check is harder to satisfy by accident.
- **The primary validation must remain ARI against ground truth**, not MI between the two dimensions.

---

## Issue 8: Six IPA Disagreements Between Test Corpus and HF Data

**SEVERITY: MEDIUM**

### Description

The test corpus (`linear_b_test_corpus.json`) and the HF sign-to-IPA mapping (`sign_to_ipa.json`) disagree on 6 signs, all in the q-series and z-series.

### Evidence

| Sign | Test corpus IPA | HF IPA |
|------|----------------|--------|
| qa | qa | kwa |
| qe | qe | kwe |
| qo | qo | kwo |
| za | za | tsa |
| ze | ze | tse |
| zo | zo | tso |

The test corpus uses conventional shorthand (qa, za), while HF uses IPA transcriptions (kwa, tsa). Additionally, the HF file contains 16 signs not in the test corpus (a2, a3, dwe, dwo, ju, nwa, pte, pu2, qi, ra2, ra3, ro2, ta2, twe, two), and the test corpus has 2 signs (qa, je) with count=0 in its own inventory.

### Impact

For consonant classification ground truth, the disagreement matters: is `qa` in the k-series (HF: kwa -> consonant /kw/) or the q-series (TC: qa -> consonant /q/)? The PRD lists q-series as a separate series (Section 4.1, "q-series: qa, qe"), which matches the conventional treatment. But the HF data implies kw is the consonant, making these labialized variants of the k-series.

If q/z signs are misassigned to wrong ground-truth series, ARI will be penalized for correct clusterings (if the method groups qa with ka because they share labiovelar articulation).

### Recommendation

- **Standardize the ground truth.** Use the conventional series classification (q-series and z-series as separate) for ARI calculation, since this matches Mycenaean Greek phonological analysis.
- **Document the disagreement** in the validation report.
- **Handle the 16 extra HF signs** explicitly: either include them in clustering (more data) or exclude them from ARI calculation (they lack test-corpus ground truth).

---

## Issue 9: Linear A Feasibility -- 62 Classifiable Signs, 10-15 Expected Series

**SEVERITY: LOW**

### Description

The PRD (Section 5.2) estimates 45-60 classifiable signs for Linear A. Empirical analysis of the corpus gives a more precise picture.

### Evidence

| Metric | Value |
|--------|-------|
| Total words in corpus | 1,305 |
| Total sign tokens | 3,271 |
| Unique signs | 135 |
| Signs with freq >= 5 AND left-ctx >= 3 AND right-ctx >= 3 | 62 |
| Signs with freq >= 3 AND left-ctx >= 3 | 64 |
| Signs with freq >= 20 | 43 |
| Hapax signs (freq = 1) | 50 (37% of types) |
| Mean left-context set size (classifiable signs) | 15.0 |

62 classifiable signs is better than the PRD's lower estimate of 45, supporting feasibility. With 10-15 expected consonant series, this gives 4-6 signs per series on average -- barely sufficient for clustering but workable.

However, 50 signs (37%) are hapax legomena and will be completely unclassifiable. The PRD should explicitly state the expected coverage fraction (~45% of signs classifiable, covering ~85% of tokens).

### Impact

The Linear A application is feasible in terms of data quantity. The limiting factor is not corpus size but the weakness of the left-context signal (Issues 1-4), which is a methodological problem independent of corpus size.

### Recommendation

- **Revise coverage estimates** to reflect the empirical 62/135 = 46% classifiability rate.
- **Focus validation on whether the method works with the available effect size**, not on whether there is enough data.

---

## Issue 10: Linkage Method Selection

**SEVERITY: LOW**

### Description

The PRD specifies average linkage (UPGMA) for hierarchical clustering (Section 3.2, Step 3.1) without justification. The choice of linkage method materially affects results with overlapping distributions.

### Analysis

- **Average linkage** (PRD choice): Sensitive to the mean distance between clusters. With the heavy distribution overlap documented in Issue 1, average linkage will merge phonologically distinct series that happen to have similar mean Jaccards.
- **Complete linkage** (conservative): Merges clusters only when ALL pairs are close. Better at preserving small, tight clusters but may over-split series where one sign has atypical frequency.
- **Ward's method**: Minimizes within-cluster variance. Often best for roughly spherical clusters in Euclidean space, but 1-Jaccard is not Euclidean (it is a proper metric but not embeddable in Euclidean space without distortion).

### Recommendation

- **Test all three linkage methods** (average, complete, Ward's) and report which yields the best ARI.
- **Ward's method may be inappropriate** for Jaccard distance; flag this if used.

---

## Issue 11: The 1-Jaccard Distance Metric

**SEVERITY: LOW**

### Description

The PRD uses 1-Jaccard as a distance metric for hierarchical clustering. This is mathematically sound.

### Verification

Binary Jaccard distance d(A,B) = 1 - |A intersect B| / |A union B| = |A symmetric-difference B| / |A union B| satisfies:
1. d(A,A) = 0 (identity)
2. d(A,B) = d(B,A) (symmetry)
3. d(A,B) >= 0 (non-negativity)
4. d(A,B) + d(B,C) >= d(A,C) (triangle inequality -- proven by Levandowsky & Winter 1971)

This is a proper metric. sklearn's silhouette_score accepts precomputed distance matrices and will work correctly with 1-Jaccard.

### No issue found.

---

## Summary of Recommendations

### BLOCKING (must fix before implementation):

1. **Implement frequency normalization** before computing Jaccard similarities. Without it, the frequency confound (rho=0.965) will dominate clustering.
2. **Do not use eigengap for cluster count selection.** Use domain knowledge (k=10-15 for LB) or silhouette sweep as primary.
3. **Validate on test corpus separately from combined corpus.** If the method only works with the HF lexicon, document this limitation.

### HIGH PRIORITY (fix or investigate):

4. **Reconsider right-context Jaccard for vowel classification.** The empirical evidence shows it captures consonant identity more than vowel identity. The dead vowel convention is too weak (1.37x chance) to create a usable signal.
5. **Standardize ground truth** across test corpus and HF data files (q/z series IPA disagreement).

### MEDIUM PRIORITY (improve):

6. **Strengthen the orthogonality check** with a coverage requirement (each consonant series must span >= 3 vowel classes).
7. **Report separate results** for test-corpus-only and combined-corpus analyses.
8. **Consider weighted Jaccard** from the start, not as a fallback.

### LOW PRIORITY (note):

9. **Test multiple linkage methods** (average, complete, Ward's).
10. **Document expected coverage** for Linear A (~46% of signs, ~85% of tokens).

---

## Methodology Notes

All empirical analyses in this audit were performed on:
- `pillar1/tests/fixtures/linear_b_test_corpus.json` (142 inscriptions, 448 words, 56 signs)
- `C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv` (2,478 entries)
- `C:\Users\alvin\hf-ancient-scripts\data\linear_b\sign_to_ipa.json` (74 signs)
- `data/linear_a_full_corpus.txt` (434 lines, 1,305 words, 3,271 tokens, 135 unique signs)

Computations used Python 3.13 with numpy. Permutation tests used 10,000 iterations with seed 42. Effect sizes reported as Cohen's d with pooled standard deviation. Spearman correlations computed via rank-based formula.
