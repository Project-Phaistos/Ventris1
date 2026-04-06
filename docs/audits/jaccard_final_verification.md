# Final Adversarial Verification: Jaccard Sign Classification

**Date:** 2026-04-06
**Verifier:** Independent adversarial agent (Claude Opus 4.6)
**Method:** All numbers recomputed from scratch using independent script (`verify_jaccard.py`). No cached results or output JSON trusted.

---

## Executive Summary

All six numerical claims are **independently reproduced and verified**. The ARI scores, cluster counts, and test pass counts are accurate. However, the verification uncovered three methodological concerns that do not invalidate the results but must be disclosed:

1. **The null test threshold is fragile.** 30% of random seeds produce ARI values that breach the strict 0.05 threshold. The claimed seed=42 result of cons=0.001, vowel=-0.030 is the best case, not representative.
2. **Consonant k=19 is near-optimal on LB.** It sits at/near the ARI peak (k=21 yields 0.3422 vs k=19 at 0.3416). This is not definitive overfitting -- the difference is negligible -- but k is hardcoded, not data-driven.
3. **TF-IDF introduced a frequency confound that raw cosine did not have.** Spearman(freq, mean_tfidf_cosine) = 0.624 vs Spearman(freq, mean_raw_cosine) = 0.159. The TF-IDF transform amplifies the correlation between sign frequency and similarity, contrary to the audit's expectation that it would reduce the rho=0.965 raw-Jaccard confound.

---

## Claim-by-Claim Verification

### CLAIM 1: Consonant ARI = 0.342 on LB corpus (gate >= 0.30)

- **VERIFIED:** YES
- **ACTUAL VALUE:** 0.341583 (rounds to 0.3416, matches claimed 0.3416)
- **DISCREPANCY:** 0.000017 (rounding only)
- **GATE:** PASS (0.3416 >= 0.30)
- **METHOD:** Loaded both LB test corpus (448 sign-groups) and HF lexicon (2,439 sign-groups), deduplicated to 2,482. Ran `run_pipeline()` with default parameters. Computed `adjusted_rand_score()` directly via sklearn on 67 signs with ground truth. Result matches to 6 decimal places.
- **CONCERN:** See overfitting analysis below.

### CLAIM 2: Vowel ARI = 0.422 on LB corpus (gate >= 0.40)

- **VERIFIED:** YES
- **ACTUAL VALUE:** 0.421923 (rounds to 0.4219, matches claimed 0.4219)
- **DISCREPANCY:** 0.000023 (rounding only)
- **GATE:** PASS (0.4219 >= 0.40)
- **METHOD:** Same pipeline run as Claim 1. Vowel ground truth from `build_lb_ground_truth()` on 67 signs. `adjusted_rand_score()` independently computed.
- **CONCERN:** The vowel ARI is more sensitive to k than consonant ARI. At k=4, vowel ARI drops to 0.3008; at k=6, it drops to 0.3188. The gate of 0.40 is only passed at k=5 exactly.

### CLAIM 3: 3/5 major consonant series recovered (t, k, n)

- **VERIFIED:** YES
- **ACTUAL VALUE:** 3/5 -- series `['t', 'k', 'n']` recovered
- **DISCREPANCY:** None
- **METHOD:** `count_recovered_series()` with target_series=["t", "k", "r", "n", "s"]. Recovery criterion: >= 50% of series members share a cluster AND that cluster has >= 30% purity.
- **CONCERN:** The r-series and s-series are NOT recovered. Cluster C16 on LB contains t(4), r(2), s(2) -- the t-series is recovered because 4/4 t-signs share this cluster with 50% purity, but the r and s signs are fragmented. This indicates that the clustering correctly groups some series but confuses others.

### CLAIM 4: Null test: shuffled consonant ARI = 0.001, vowel ARI = -0.030

- **VERIFIED:** PARTIAL -- values at seed=42 are correct but the null test is fragile
- **ACTUAL VALUES (seed=42):** cons_ARI = +0.0013, vowel_ARI = -0.0304. Matches claims.
- **DISCREPANCY:** None at seed=42
- **CONCERN -- CRITICAL:** Testing with 20 seeds (0-19) reveals:
  - 6/20 seeds (30%) produce at least one ARI exceeding the strict 0.05 threshold
  - Seed 2: cons_ARI = 0.0626 (exceeds 0.05)
  - Seed 4: vowel_ARI = 0.0576 (exceeds 0.05)
  - Seed 14: vowel_ARI = 0.0634 (exceeds 0.05)
  - Seed 17: cons_ARI = 0.0582 (exceeds 0.05)
  - The existing test suite uses seeds [42, 0, 7, 99, 12345] with a relaxed threshold of 0.10 for the multi-seed test, but the gate threshold is 0.05. This means the null test PASSES at seed=42 but FAILS at 6 of 20 randomly selected seeds.
  - The claimed values of 0.001 and -0.030 are cherry-picked (best-case seed), not representative of the null distribution.
  - A proper null test should report the DISTRIBUTION across many seeds (e.g., "95th percentile of |ARI| across 100 shuffles"), not a single seed.

### CLAIM 5: 19 consonant clusters on Linear A, 9 with >= 3 signs

- **VERIFIED:** YES
- **ACTUAL VALUE:** 19 clusters, 9 with >= 3 signs
- **DISCREPANCY:** None
- **METHOD:** Ran `run_pipeline()` on LA corpus (847 sign-groups, 60 analyzed signs). Counted clusters and their sizes directly.
- **CLUSTER SIZES:** Sizes are 1, 1, 2, 4, 4, 2, 3, 2, 6, 2, 2, 4, 7, 7, 7, 1, 1, 1, 1. Nine clusters have >= 3 signs: {C1:3, C4:4, C5:4, C7:3, C9:6, C12:4, C13:7, C14:7, C15:7}.
- **CONCERN:** The k=19 is hardcoded as `DEFAULT_CONSONANT_K`, not determined from the LA data. Using the same k for a corpus with only 60 signs means many clusters are singletons (5 clusters with only 1 sign). This may over-fragment the data.

### CLAIM 6: 51 tests all passing

- **VERIFIED:** YES
- **ACTUAL VALUE:** 51/51 passed in 2.01 seconds
- **DISCREPANCY:** None
- **METHOD:** Ran `python -m pytest pillar1/tests/test_jaccard_classification.py -v --tb=short` independently. Full output captured.

---

## Overfitting Analysis (Step 3)

### Are k values hardcoded?

YES. The pipeline uses hardcoded defaults:
- `DEFAULT_CONSONANT_K = 19`
- `DEFAULT_VOWEL_K = 5`
- `DEFAULT_VOWEL_ANTI_CORR_BETA = 0.15`
- `DEFAULT_CONSONANT_KNN = 8`

The function `auto_select_k()` exists in the codebase but is **never called** by `run_pipeline()` or `main()`. All production runs use the hardcoded values.

### Was k=19 chosen to maximize ARI?

Plausibly yes, but the evidence is ambiguous:

**Consonant k sweep (ARI on LB):**
| k | ARI |
|---|-----|
| 10 | 0.237 |
| 13 | 0.251 |
| 15 | 0.268 |
| 17 | 0.281 |
| 18 | 0.305 |
| **19** | **0.342** |
| 20 | 0.339 |
| **21** | **0.342** |
| 23 | 0.281 |
| 25 | 0.262 |

k=19 and k=21 are virtually tied (0.3416 vs 0.3422). The ARI curve peaks sharply at k=19-21 and drops off on both sides. This is consistent with either (a) the data genuinely having ~19-21 consonant-related groupings, or (b) k being tuned to maximize ARI on the validation set.

**Mitigating factor:** LB has approximately 12 consonant series (d, j, k, m, n, p, q, r, s, t, w, z) plus pure vowels. With 67 signs and some frequency-driven splits, k=19 is within the expected range. The concern is that k was not derived from an independent criterion.

**Vowel k=5 is strongly justified:** LB has exactly 5 vowels (a, e, i, o, u), so k=5 is the linguistically correct choice.

**Beta=0.15 sensitivity:** Vowel ARI varies minimally across beta in [0.05, 0.30], ranging from 0.4148 to 0.4219. The choice of beta=0.15 is not critically tuned -- any value in this range gives similar results. At beta=0.0 (no anti-correlation), ARI still reaches 0.3865.

### Verdict on overfitting

**MILD CONCERN.** k=19 is near-optimal but not uniquely so (k=21 is equally good). The vowel parameters are robust. The main risk is that the ARI gate of 0.30 was set after knowing that k=19 achieves 0.34 -- there is no evidence of independent threshold selection.

---

## Frequency Confound Analysis (Step 6)

### Context

The prior audit (jaccard_classification_audit.md) found rho=0.965 between context-set-size and mean raw Jaccard. The builder's implementation uses TF-IDF + cosine similarity instead of raw Jaccard, which was intended to address this confound.

### Findings

| Correlation | Spearman rho | p-value |
|---|---|---|
| freq vs context_set_size | 0.871 | < 0.0001 |
| ctx_size vs mean_raw_Jaccard | 0.965 | < 0.0001 |
| freq vs mean_raw_cosine (no TF-IDF) | 0.159 | 0.192 (n.s.) |
| freq vs mean_TF-IDF_cosine | **0.624** | **< 0.0001** |
| freq vs mean_PPMI_cosine | 0.235 | 0.052 (n.s.) |

**Key finding:** Raw cosine similarity on count vectors has NEGLIGIBLE frequency confound (rho=0.159, n.s.). The TF-IDF transform INTRODUCES a statistically significant frequency confound (rho=0.624, p < 0.0001). This is the opposite of the intended effect.

**Explanation:** TF-IDF downweights contexts shared by many signs (common neighbors) and upweights rare contexts. High-frequency signs have more rare contexts simply because they appear in more positions, so TF-IDF amplifies their distinctiveness relative to low-frequency signs. This creates a systematic relationship between sign frequency and TF-IDF-cosine similarity.

**However:** The confound does not appear to prevent useful clustering, since ARI=0.342 is achieved. The phonological signal is apparently strong enough to emerge despite the frequency correlation. The confound likely increases misclassification of low-frequency signs (which get pulled toward high-frequency sign clusters) but does not dominate the clustering outcome.

### Recommendation

The builder should document that TF-IDF increased the frequency confound from rho=0.159 to rho=0.624. If frequency normalization is desired, PPMI (rho=0.235) or raw cosine (rho=0.159) would be better starting points for the consonant dimension. However, raw cosine on LB yields consonant ARI that should be independently checked to confirm it is comparable.

---

## Linear A Cluster Quality (Step 4)

### Consonant purity for clusters with known LB readings

Since the LA signs use the same syllabary names as LB, we can check whether signs sharing a cluster also share a consonant (using LB phonetic values as a proxy).

| Cluster | Signs (consonant) | Majority | Purity |
|---|---|---|---|
| C1 | e(V), ni(n), nu(n) | n | 0.67 |
| C4 | a(V), i(V), je(j), ku(k) | V | 0.50 |
| C5 | qa(q), tu(t) | -- | 0.50 |
| C6 | ta2(t), te(t) | t | **1.00** |
| C7 | du(d), si(s), ti(t) | -- | 0.33 |
| C9 | ko(k), pi(p), ri(r) | -- | 0.33 |
| C12 | ma(m), qe(q), wi(w) | -- | 0.33 |
| C13 | de(d), ja(j), o(V), ra(r), ra2(r), ru(r), sa(s) | r | 0.43 |
| C14 | da(d), ka(k), ki(k), mi(m), na(n), su(s), ta(t) | k | 0.29 |
| C15 | me(m), ne(n), pa(p), re(r), ro(r) | r | 0.40 |

**Mean purity of clusters with 2+ known signs: ~0.44**

This is significantly lower than the LB cluster purity of 0.66. Only one cluster (C6: ta2, te) achieves perfect consonant purity. Large clusters C13 (7 signs, 5 different consonants) and C14 (7 signs, 6 different consonants) are heavily mixed.

**Interpretation:** If Linear A signs have the same phonetic values as their LB counterparts (which is the working assumption), then the clustering is NOT strongly recovering consonant series. Mean purity of 0.44 is only marginally above chance for clusters of size 3-7 drawn from ~12 consonant categories. However, if Linear A phonetic values differ from LB, this comparison is invalid. The low purity could indicate either (a) the method fails on LA's smaller corpus, or (b) LA sign values differ from LB values.

---

## Spot-Check of LB Clusters (Step 7)

Three LB clusters with the most known signs were examined:

**Cluster C13 (10 signs):** Contains a(V), a2(V), a3(V), au(a), di(d), e(V), i(V), ku(k), o(V), pu(p). Majority: pure vowels (V), purity 0.60. This cluster primarily captures VOWELS, not a consonant series. It groups all the pure vowel signs together, which is phonologically coherent (these signs share the distributional property of appearing in similar contexts) but does NOT represent a consonant class.

**Cluster C16 (8 signs):** Contains ra(r), ro(r), si(s), so(s), ta(t), te(t), ti(t), to(t). Majority: t, purity 0.50. This is a partial t-series recovery contaminated by r and s signs. The 4 t-signs cluster together (good) but bring along 2 r-signs and 2 s-signs (bad).

**Cluster C8 (6 signs):** Contains de(d), na(n), ne(n), ni(n), no(n), tu(t). Majority: n, purity 0.67. This is a reasonably successful n-series recovery: 4/5 n-signs cluster together. The contamination by de(d) and tu(t) is typical of frequency-mediated errors.

**Verdict:** The LB clustering shows a mix of genuine phonological signal (t and n series partially recovered) and distributional artifacts (vowels clustering together, cross-series contamination). The ARI of 0.34 accurately reflects this partial success.

---

## Overall Verification Verdict

| Claim | Status | Confidence |
|---|---|---|
| Consonant ARI = 0.342 | **VERIFIED** | High -- reproduced to 6 decimal places |
| Vowel ARI = 0.422 | **VERIFIED** | High -- reproduced to 6 decimal places |
| 3/5 series recovered | **VERIFIED** | High -- t, k, n confirmed |
| Null test values | **VERIFIED (seed=42 only)** | Medium -- 30% of seeds breach 0.05 |
| 19 LA clusters, 9 >= 3 | **VERIFIED** | High -- counts confirmed |
| 51 tests passing | **VERIFIED** | High -- all pass in 2.01s |

### Issues to Disclose

1. **Null test fragility.** The test suite's reported values are from a single favorable seed (42). Proper reporting should use the 95th percentile across many seeds. Recommendation: report "median |ARI| across 100 shuffles" and set the gate at 95th percentile < 0.10 rather than a single-seed check at < 0.05.

2. **TF-IDF frequency confound.** The TF-IDF transform increased frequency-similarity correlation from 0.159 (raw cosine) to 0.624. This should be documented. It does not prevent useful clustering but is a methodological concern.

3. **Hardcoded k.** The consonant k=19 is near-optimal on LB data but was not derived from an independent criterion. For LA application, the same k may not be appropriate for a corpus with only 60 analyzable signs.

4. **LA cluster purity is low.** Mean purity of 0.44 (assuming LB phonetic values) is marginal. The clusters should be interpreted as distributional groupings, not confident consonant-series identifications.

---

## Files Referenced

- Main script: `C:\Users\alvin\Ventris1\pillar1\scripts\jaccard_sign_classification.py`
- Test suite: `C:\Users\alvin\Ventris1\pillar1\tests\test_jaccard_classification.py`
- Output: `C:\Users\alvin\Ventris1\results\jaccard_classification_output.json`
- Verification script: `C:\Users\alvin\Ventris1\verify_jaccard.py`
- LB test corpus: `C:\Users\alvin\Ventris1\pillar1\tests\fixtures\linear_b_test_corpus.json`
- HF sign-to-IPA: `C:\Users\alvin\hf-ancient-scripts\data\linear_b\sign_to_ipa.json`
- HF LB words: `C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv`
- LA corpus: `C:\Users\alvin\Ventris1\data\sigla_full_corpus.json`
- Prior audit: `C:\Users\alvin\Ventris1\docs\audits\jaccard_classification_audit.md`
