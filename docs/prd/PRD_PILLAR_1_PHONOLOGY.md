# PRD: Pillar 1 — Phonological Engine (The Computational Grid)

**Status:** Draft
**Depends on:** Nothing — this is the first pillar
**Feeds into:** Pillar 2 (morphological decomposition), Pillar 3 (distributional grammar)
**Date:** 2026-03-23
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Discover the phonological system of the Linear A script from distributional evidence alone, without assuming Linear B phonetic values as input. Produce a consonant-vowel grid, vowel/consonant inventories, phonotactic constraints, and syllable structure characterization — then measure agreement/disagreement with Linear B values post-hoc.

This pillar implements Ventris's grid methodology computationally: structure before values, internal evidence before external assumptions.

**Traced to README:** "The phonological engine should discover the sound system independently from first principles, using Linear B values only as a soft check after the fact — not as an input."

---

## 2. Non-goals

- **No phonetic value assignment.** This pillar does NOT assign IPA values to signs. It assigns abstract class labels (consonant class 1, vowel class 2). Phonetic interpretation comes later via LB soft validation and Pillar 5.
- **No cognate matching.** No external language data is used.
- **No morphological analysis.** Inflectional alternation is detected in this pillar only to build the grid — the full morphological decomposition is Pillar 2's job.
- **No interpretation of meaning.** The output is purely structural.

---

## 3. Inputs

### 3.1 Primary input: SigLA Full Linear A Corpus

**File:** `ancient-scripts-datasets/data/linear_a/sigla_full_corpus.json`
**Version:** 2.0.0 (2026-02-28)

Corpus statistics (as measured):
- 879 inscriptions
- 1,552 words (1,421 with `sign_readings`)
- 4,615 total sign tokens (3,518 syllabograms, 1,097 logograms)
- 421 unique signs total (142 syllabograms, 165 logograms, 114 unknown)
- 62 tier1 syllabograms (with established Linear B correspondences)
- 80 tier3 undeciphered syllabograms
- Average word length: 2.51 signs
- 295 inscriptions with >1 word (usable for positional analysis)

### 3.2 What the engine sees

The engine operates on **sign IDs only** (e.g., `AB08`, `AB59`), NOT on phonetic labels (e.g., `a`, `ta`). The sign-to-IPA mapping and the IPA column are explicitly excluded from the input to the core algorithms. This enforces the independent discovery requirement.

Input data structure per inscription:
```json
{
  "id": "ARKH 1a",
  "type": "Tablet",
  "words": [
    {
      "sign_readings": ["ta", "pi"],
      "ab_codes": "AB59-AB39",
      "has_damage": true
    }
  ]
}
```

**Preprocessing rules:**
- Use `ab_codes` as sign identifiers (not the alphabetic `sign_readings` which encode LB values)
- Exclude damaged words (`has_damage: true`) from positional frequency analysis (damaged words may have missing initial/final signs)
- Exclude logograms and numerals — only syllabograms are phonological units
- Exclude inscriptions with only 1 word for positional analysis (no contrast between initial/medial/final)
- Retain single-word inscriptions for bigram analysis (internal sign sequences are still informative)

### 3.3 Validation input: Linear B phonetic values (soft check only)

**File:** `sign_to_ipa.json` (34 entries) + sign inventory tier1 data (62 entries)
**Used:** ONLY in the final LB Validation step (Section 5.5), NEVER as input to discovery algorithms.

---

## 4. Outputs (Interface Contract)

Pillar 1 produces a single JSON output file that downstream pillars consume. Every field has a concrete schema.

### 4.1 Output schema

```json
{
  "metadata": {
    "pillar": 1,
    "version": "1.0.0",
    "corpus_version": "<SHA-256 of corpus file>",
    "config_hash": "<SHA-256 of config used>",
    "timestamp": "ISO-8601",
    "seed": 1234
  },

  "vowel_inventory": {
    "count": 4,
    "count_ci_95": [3, 5],
    "method": "positional_frequency_binomial",
    "signs": [
      {
        "sign_id": "AB08",
        "enrichment_score": 3.42,
        "p_value": 1.2e-8,
        "p_value_corrected": 7.4e-7,
        "initial_count": 45,
        "medial_count": 12,
        "final_count": 8,
        "total_count": 137,
        "classification": "pure_vowel",
        "confidence": 0.99
      }
    ]
  },

  "cv_grid": {
    "consonant_count": 14,
    "consonant_count_ci_95": [12, 16],
    "vowel_count": 4,
    "grid_method": "spectral_clustering_on_alternation_graph",
    "assignments": [
      {
        "sign_id": "AB59",
        "consonant_class": 3,
        "vowel_class": 2,
        "confidence": 0.75,
        "evidence_count": 5
      }
    ],
    "unassigned_signs": [
      {
        "sign_id": "AB16",
        "reason": "insufficient_evidence",
        "total_count": 1
      }
    ]
  },

  "phonotactic_constraints": {
    "forbidden_bigrams": [
      {
        "sign_i": "AB08",
        "sign_j": "AB61",
        "observed": 0,
        "expected": 4.2,
        "p_value": 0.015,
        "constraint_type": "vowel_hiatus"
      }
    ],
    "favored_bigrams": [
      {
        "sign_i": "AB59",
        "sign_j": "AB08",
        "observed": 18,
        "expected": 6.1,
        "p_value": 2.3e-5,
        "ratio": 2.95
      }
    ],
    "initial_only_signs": ["AB08", "AB61"],
    "never_initial_signs": [],
    "never_final_signs": []
  },

  "syllable_structure": {
    "primary_type": "CV",
    "evidence": "sign_count_combinatorics",
    "cv_sign_count": 55,
    "v_sign_count": 4,
    "cvc_evidence": "none | weak | moderate | strong",
    "sign_count_equation": "V(1+C) = 59, V=4, C=14"
  },

  "lb_validation": {
    "agreement_score": 0.82,
    "total_comparable_signs": 55,
    "matching_signs": 45,
    "disagreements": [
      {
        "sign_id": "AB41",
        "independent_consonant_class": 5,
        "independent_vowel_class": 3,
        "lb_consonant": "s",
        "lb_vowel": "i",
        "lb_consonant_class_in_grid": 7,
        "lb_vowel_class_in_grid": 2,
        "match_consonant": false,
        "match_vowel": false
      }
    ]
  },

  "dead_vowel_evidence": {
    "consecutive_same_vowel_rate": 0.45,
    "expected_by_chance": 0.25,
    "p_value": 3.1e-12,
    "interpretation": "strong evidence for dead vowel convention"
  }
}
```

### 4.2 What downstream pillars consume

**Pillar 2 (Morphology) uses:**
- `cv_grid.assignments` — to constrain morpheme segmentation at valid syllable boundaries
- `vowel_inventory.signs` — to identify which signs are pure vowels (segmentation point candidates)
- `phonotactic_constraints.forbidden_bigrams` — to validate that proposed morpheme boundaries don't create illegal sequences
- `syllable_structure` — to know the basic syllable type (CV, CVC, etc.)

**Pillar 3 (Grammar) uses:**
- `cv_grid.assignments` — for distributional analysis (signs in the same grid row/column behave similarly)
- `phonotactic_constraints` — word-initial/final constraints help identify word boundaries in unsegmented text

---

## 5. Approach

### 5.1 Step 1: Corpus Preparation

**Input:** Raw SigLA corpus
**Output:** Clean sign-sequence data in two formats:
1. **Positional format:** words with initial/medial/final position labels, excluding damaged words and single-sign words
2. **Bigram format:** all consecutive sign pairs within words, including single-word inscriptions

**Algorithm:**
```
for each inscription:
    for each word in inscription.words:
        signs = [s for s in word.sign_readings if type(s) == "syllabogram"]
        if word.has_damage: skip for positional analysis, keep for bigram
        if len(signs) < 2: skip for positional analysis

        positions:
            signs[0] → "initial"
            signs[-1] → "final"
            signs[1:-1] → "medial"

        bigrams:
            for j in range(len(signs) - 1):
                emit (signs[j], signs[j+1])
```

**Expected yield:**
- Positional data: ~800-1000 multi-sign undamaged words
- Bigram data: ~2000-2500 sign pairs

### 5.2 Step 2: Vowel Identification via Positional Frequency

**Mathematical foundation:**

In a CV syllabary, words beginning with a vowel require a pure vowel sign (V) in initial position. Words beginning with a consonant use a CV sign. Therefore, pure vowel signs are *enriched* in word-initial position relative to their overall frequency.

For each sign s_i (i = 1, ..., N where N = number of distinct syllabograms):

Let:
- n_i = total occurrences of s_i across all positions
- k_i = occurrences of s_i in word-initial position
- p_0 = (total initial-position tokens) / (total sign tokens) = global initial rate

**Null hypothesis H_0:** Sign s_i appears initially at the corpus-wide base rate.
Under H_0: k_i ~ Binomial(n_i, p_0)

**Alternative H_1:** Sign s_i is a pure vowel sign and appears initially more often.

**Test statistic:** One-sided binomial test
p_value_i = P(X ≥ k_i | X ~ Bin(n_i, p_0))

**Multiple testing correction:** Bonferroni at α = 0.05
Reject H_0 if p_value_i < α / N

**Enrichment score:**
E_i = (k_i / n_i) / p_0

Pure vowel signs should have E_i >> 1 (typically 2-4x enrichment).

**Cross-validation with medial depletion:**
Pure vowel signs should also be *depleted* in medial position (in a CV syllabary, mid-word vowels are written as part of CV compounds, not as bare V signs — except under dead vowel convention).

For each candidate pure vowel (signs passing the initial enrichment test):
- m_i = occurrences in medial position
- p_med = global medial rate
- One-sided binomial test for depletion: P(X ≤ m_i | X ~ Bin(n_i, p_med))

Signs enriched initially AND depleted medially = high-confidence pure vowels.

**Vowel count determination:**
V_est = number of signs that pass BOTH tests (initial enrichment + medial depletion)
Bootstrap 95% CI: resample inscriptions with replacement 1000 times, repeat the test, report 2.5th and 97.5th percentiles of V_est.

**Statistical power analysis:**
With n_i ≈ 100 (typical for frequent signs), p_0 ≈ 0.3 (rough initial rate), and true enrichment of 2x (p_1 = 0.6), the power of the binomial test at α/N ≈ 0.0008 is:
Power = P(reject H_0 | H_1 true) ≈ P(X ≥ x_crit | X ~ Bin(100, 0.6))
This exceeds 0.99 for the given parameters. For rare signs (n_i < 20), power drops below 0.5, so rare signs cannot be reliably classified — they are labeled "insufficient_evidence."

**Minimum frequency threshold:** Signs with n_i < 15 are excluded from positional analysis and marked as unclassifiable. With n_i = 15 and the Bonferroni threshold, the test has negligible power for enrichment < 3x, making it unreliable.

### 5.3 Step 3: Inflectional Alternation Detection (Kober's Triplets)

**Goal:** Find pairs of signs that alternate in word-final position, indicating they share a consonant (same grid row) but differ in vowel.

**Algorithm:**

1. **Find shared-prefix pairs:**
   For all pairs of words (w_a, w_b) in the corpus where:
   - Both have length ≥ 2 signs
   - They share a common prefix of length ≥ 1 sign
   - They differ only in the final sign

   Formally: w_a = [s_1, ..., s_k, a] and w_b = [s_1, ..., s_k, b] where a ≠ b.

   Record the pair (a, b) as a "same-consonant" candidate with evidence weight = 1.

2. **Extended triplets (suffix length 2):**
   Also find pairs where the last TWO signs differ:
   w_a = [s_1, ..., s_k, a_1, a_2] and w_b = [s_1, ..., s_k, b_1, b_2]

   If a_1 ≠ b_1 and a_2 ≠ b_2, this gives two same-consonant pairs: (a_1, b_1) and (a_2, b_2), each with weight 0.5 (lower confidence because the prefix match is shorter relative to word length).

3. **Build the same-consonant affinity matrix A_c:**
   A_c is an N × N symmetric matrix where:
   A_c[i, j] = total evidence weight for signs i and j sharing a consonant

   A_c[i, j] = Σ (weights from all independent stems showing the (i, j) alternation)

   "Independent stems" = distinct prefixes. If the same prefix yields the same (i, j) pair multiple times (e.g., from different inscriptions), count each distinct prefix once.

**Statistical validation of alternation pairs:**

Not all shared-prefix pairs are genuine inflectional variants — some are coincidental. To filter noise:

For each pair (a, b) with A_c[a, b] = w:

**Null model:** Under random co-occurrence, the expected number of shared-prefix pairs ending in (a, b) depends on the frequencies of a and b in final position and the number of distinct prefixes.

E[w] = (number of distinct prefixes with ≥ 2 attested continuations) × P(a in final) × P(b in final)

**Test:** If w significantly exceeds E[w] (Poisson test or permutation test), the alternation is likely genuine.

Set a minimum threshold: only retain pairs where w ≥ 2 (at least 2 independent stems show the alternation) AND the pair passes the significance test at α = 0.01.

### 5.4 Step 4: Grid Construction via Spectral Clustering

**Goal:** From the same-consonant affinity matrix A_c, recover C consonant classes (grid rows).

**Algorithm:**

1. **Graph Laplacian:**
   - D = diagonal degree matrix: D[i, i] = Σ_j A_c[i, j]
   - L_norm = I - D^{-1/2} A_c D^{-1/2} (normalized Laplacian)

2. **Eigengap heuristic for C:**
   - Compute eigenvalues λ_1 ≤ λ_2 ≤ ... ≤ λ_N of L_norm
   - The number of consonant classes C = argmax_k (λ_{k+1} - λ_k) for k in [2, N/2]
   - Report the eigengap spectrum for manual inspection

3. **Spectral clustering:**
   - Take the first C eigenvectors of L_norm
   - Run k-means on the N × C eigenvector matrix
   - Each cluster = one consonant class

4. **Model selection cross-check:**
   Repeat with alternative methods:
   - Silhouette score for k = 2, 3, ..., 20
   - BIC for Gaussian mixture model on the eigenvector embedding
   - Report the range of plausible C values across methods

5. **Vowel class assignment:**
   Once consonant classes are determined, assign vowel classes:
   - Within each consonant class (grid row), the signs differ only in vowel
   - The number of signs per row should equal V (the vowel count from Step 2)
   - If a row has more than V signs, the extra signs may be CVC or variant forms
   - If a row has fewer than V signs, some vowel slots are unattested

6. **Cross-row vowel alignment (same-vowel evidence):**

   **Dead vowel method:** In a CV syllabary using the dead vowel convention, consecutive CV signs within a word often share the same vowel. This creates same-vowel evidence:

   For each bigram (s_i, s_j) within a word:
   - If s_i and s_j are in different consonant classes, the bigram frequency reveals whether they share a vowel
   - Under the dead vowel convention: P(same vowel | consecutive) > P(same vowel | random)

   Build a same-vowel affinity matrix A_v:
   A_v[i, j] = (observed consecutive co-occurrence of i, j) / (expected under independence) - 1

   Positive values suggest same vowel; negative values suggest different vowels.

   Cluster A_v within each consonant class to align vowel assignments across rows.

   **Alternative method (if dead vowel evidence is weak):**
   Use the constraint that V was independently determined in Step 2. Assign vowel classes to maximize consistency: the same vowel class should appear in the same column position across all consonant rows.

**Confidence scores:**
For each sign's grid assignment (c, v):
- confidence = min(consonant_confidence, vowel_confidence)
- consonant_confidence = silhouette score of the sign within its consonant cluster
- vowel_confidence = strength of vowel alignment evidence

Signs with confidence < 0.3 are marked as "low_confidence" in the output.

### 5.5 Step 5: Phonotactic Constraint Discovery

**Goal:** Identify which sign sequences are forbidden (phonotactic gaps) and which are favored.

**Algorithm:**

1. **Build bigram frequency matrix B:**
   B[i, j] = count of sign j immediately following sign i, across all words

2. **Expected frequencies under independence:**
   E[i, j] = (row_total_i × col_total_j) / grand_total

3. **Standardized residuals:**
   R[i, j] = (B[i, j] - E[i, j]) / sqrt(E[i, j])

   Large positive R: favored bigram
   Large negative R (or B[i,j] = 0 with E >> 0): forbidden bigram

4. **Statistical test for forbidden bigrams:**
   For each cell where B[i, j] = 0 and E[i, j] ≥ 2:
   P(X = 0 | X ~ Poisson(E[i,j]))

   Reject independence if p < 0.01 / (N × N) (Bonferroni for all cells)

5. **Phonotactic constraint interpretation:**
   - V-V forbidden bigrams → no vowel hiatus
   - Certain CV-CV forbidden patterns → onset restrictions
   - Position-specific constraints (never-initial, never-final) from Step 2 positional data

6. **Syllable boundary inference:**
   - At positions where phonotactic constraints are strongest (lowest transition probability), syllable boundaries are likely
   - This gives Pillar 2 guidance on where to segment within a word

### 5.6 Step 6: Linear B Soft Validation

**Goal:** Compare the independently-constructed grid against Linear B phonetic values.

**Algorithm:**

1. **Map LB values to grid cells:**
   For each sign with a known LB value (e.g., LB says AB59 = "ta"):
   - LB consonant = "t"
   - LB vowel = "a"

   Group LB consonants: all signs that LB assigns to the same consonant form a "LB consonant class."
   Group LB vowels: all signs that LB assigns to the same vowel form a "LB vowel class."

2. **Compute agreement:**
   For each sign s with both an independent grid assignment and an LB value:
   - consonant_match = (s's independent consonant class contains the same signs as s's LB consonant class)
   - vowel_match = (s's independent vowel class contains the same signs as s's LB vowel class)

   More precisely, use the Adjusted Rand Index (ARI) between independent clustering and LB clustering:
   - ARI_consonant = adjusted_rand_index(independent_consonant_classes, lb_consonant_classes)
   - ARI_vowel = adjusted_rand_index(independent_vowel_classes, lb_vowel_classes)

   ARI = 1.0 means perfect agreement. ARI = 0.0 means chance-level agreement.

3. **Disagreement analysis:**
   For each sign where independent ≠ LB:
   - Document the disagreement
   - Check whether the disagreement is systematic (all signs with LB consonant "x" are in a different independent class) or sporadic (random mismatches)
   - Systematic disagreements suggest Minoan phonology differs from Greek in that dimension
   - Sporadic disagreements suggest noise or insufficient evidence

### 5.7 Step 7: Dead Vowel Convention Test

**Goal:** Determine whether Linear A uses the dead vowel convention (as Linear B does).

**Algorithm:**

Using the vowel assignments from Step 4:

1. For each consecutive sign pair (s_i, s_j) within a word, check whether they have the same vowel class.
2. same_vowel_rate = (count of same-vowel consecutive pairs) / (total consecutive pairs)
3. expected_rate = 1/V (if vowels were assigned randomly among V classes)
4. Chi-squared test or binomial test for same_vowel_rate > expected_rate

If significantly higher: evidence for dead vowel convention.
If not significantly different: no dead vowel convention (or vowel assignments are wrong).

This serves as an internal consistency check on the vowel assignments: if the grid is correct AND Minoan uses dead vowels, the rate should be elevated. If the grid is correct but Minoan doesn't use dead vowels, the rate should be at chance. If the rate is significantly BELOW chance, the vowel assignments may be wrong.

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `corpus_loader.py` | Read SigLA JSON, filter to syllabograms, separate positional vs. bigram data | Raw JSON | Clean sign sequences with position labels |
| `vowel_identifier.py` | Positional frequency analysis, binomial tests, vowel count estimation | Positional data | Vowel inventory with CIs |
| `alternation_detector.py` | Find Kober's triplets, build same-consonant affinity matrix, significance filtering | Clean sign sequences | Affinity matrix A_c |
| `grid_constructor.py` | Spectral clustering, model selection for C, vowel alignment | A_c + vowel inventory | C-V grid assignments |
| `phonotactic_analyzer.py` | Bigram statistics, forbidden/favored sequences, syllable boundary inference | Bigram data + grid | Phonotactic constraints |
| `lb_validator.py` | Compare grid against LB values, compute ARI, analyze disagreements | Grid + LB data | Agreement score + disagreement report |
| `dead_vowel_tester.py` | Test for dead vowel convention | Grid + bigram data | Dead vowel evidence |
| `output_formatter.py` | Assemble all outputs into interface contract JSON | All above | Final JSON |

---

## 7. Go/No-Go Gates

### Gate 1: Known-Answer Test on Linear B (CRITICAL)

**Test:** Run the entire Pillar 1 pipeline on a Linear B corpus (Mycenaean Greek tablets, where the phonological system is known).

**Expected results:**
- Vowel count: 5 (a, e, i, o, u). Accept 4-6.
- Consonant count: 12-17 (known Linear B grid has ~15 consonant series). Accept 10-20.
- Pure vowel identification: ≥ 4 of the 5 pure vowel signs correctly identified.
- ARI between independent grid and known grid: ≥ 0.5 (moderate agreement).

**On failure:**
- If vowel count is wrong: review the positional frequency analysis. The Linear B corpus is larger and should give clearer signal.
- If ARI < 0.3: the clustering algorithm is not recovering the grid structure. Review eigengap heuristic, consider alternative clustering methods.
- If ARI < 0.1: the approach is fundamentally flawed. Invoke kill criteria.

**Data source:** DAMOS database or published Linear B sign frequency tables. Must be ingested following Section 7 (Data Extraction Standards).

### Gate 2: Null Test on Random Permutation (CRITICAL)

**Test:** Randomly permute the signs within each word (destroying positional and inflectional structure) and run the pipeline.

**Expected results:**
- No signs pass the pure vowel test (no significant initial enrichment after Bonferroni correction).
- Eigengap heuristic shows no clear cluster count (flat eigenvalue spectrum).
- ARI ≈ 0 between random-data grid and LB values.

**On failure:**
- If the pipeline produces structured-looking output from random data, it's detecting an artifact. Review for methodological bias (e.g., frequency effects masquerading as positional effects).

### Gate 3: Stability Test (HIGH)

**Test:** Run the pipeline 10 times with different random seeds (for k-means initialization in spectral clustering) and with bootstrap-resampled inscriptions.

**Expected results:**
- Vowel count stable across runs (same value ≥ 8/10 times).
- Consonant count stable to ±2 across runs.
- Core grid assignments (high-frequency signs) stable: ≥ 80% of signs with n > 50 get the same grid cell in ≥ 8/10 runs.

**On failure:**
- If V fluctuates: the positional frequency signal is marginal. Increase the significance threshold or accept a wider CI.
- If C fluctuates: the alternation evidence is too sparse. May need to relax the minimum evidence threshold or accept a range rather than a point estimate.

### Gate 4: Confound Check (HIGH)

**Test:** Check whether the vowel identification is confounded by sign frequency.

**Expected:** Pure vowel signs are not simply the most frequent signs. If the 5 most frequent signs happen to be the pure vowels, the enrichment test may be detecting frequency effects, not positional effects. Compute Spearman correlation between enrichment score and total frequency.

**Expected:** |ρ| < 0.5

**On failure:** The enrichment score is confounded with frequency. Add a frequency-adjusted enrichment metric (e.g., regress out frequency before testing for positional enrichment).

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Corpus too small for reliable clustering** (3,518 syllabogram tokens, ~60 frequent signs) | HIGH | MEDIUM | Use bootstrap CIs to quantify uncertainty. Report ranges, not point estimates. Accept that rare signs (n < 15) are unclassifiable. |
| **Administrative texts have limited inflectional diversity** (mostly commodity records with nouns in 1-2 cases) | HIGH | HIGH | Supplement tablet data with libation table data (ritual texts, likely more verb forms and case diversity). Report the number of independent stems supporting each alternation pair. |
| **Logograms misclassified as syllabograms** | MEDIUM | LOW | The SigLA corpus already classifies signs by type. Use only signs with type="syllabogram". For undeciphered signs, apply the positional frequency test — logograms should show no positional enrichment. |
| **Linear A is not a pure CV syllabary** (some signs may be CVC, V, or CVCV) | MEDIUM | MEDIUM | The sign count equation V(1+C) = N provides a consistency check. If N is not well-explained by any (V, C) pair with V = identified vowel count, some signs may not be CV. Flag anomalies. |
| **Dead vowel convention does not apply** (Minoan may not use dead vowels) | LOW | MEDIUM | The dead vowel test (Step 7) is diagnostic, not assumed. If the dead vowel convention doesn't hold, vowel alignment across consonant rows is harder but still possible via the alternative method in Step 4.6. |
| **Word boundaries are unreliable** (some inscriptions lack word dividers) | MEDIUM | MEDIUM | Use only inscriptions with explicit word boundaries for positional analysis. Unsegmented inscriptions are used only for bigram analysis (which doesn't require word boundaries). |

---

## 9. Corpus Budget

| Data subset | Used for | Token count | % of corpus |
|-------------|----------|-------------|-------------|
| Multi-sign undamaged words from multi-word inscriptions | Positional frequency analysis | ~800-1000 words (~2500 tokens) | ~70% of syllabogram tokens |
| All within-word consecutive sign pairs | Bigram analysis | ~2000-2500 pairs | Derived from above |
| All words with length ≥ 2 | Inflectional alternation detection | ~1100 words | 77% of words |
| Held-out: Knossos ivory scepter | Validation only (not used in Pillar 1) | ~119 signs | Reserved |

No competition with other pillars — all pillars read the full corpus. The held-out set (ivory scepter) is excluded from all pillars until final validation.

---

## 10. Relationship to PhaiPhon (Legacy)

### What can be reused

- **SigLA corpus loader:** The ingestion code from the ancient-scripts-datasets pipeline can be adapted. The corpus format is the same.
- **IPA feature infrastructure:** Not used in Pillar 1 (we operate on sign IDs, not IPA), but may be useful in Pillar 5.
- **PhaiPhon4 vowel count analysis:** PhaiPhon4 found V ≈ 3.7 (3 core + 1 marginal) via a different method (gradient-based optimization on transition matrices). This provides an independent reference point for cross-validation — if Pillar 1's distributional analysis also finds V ≈ 4, that's convergent evidence.

### What must be discarded

- **All phonetic prior machinery** (Luo et al. reproduction, character mapping logits, edit distance DP). These assume a single known target language and are architecturally incompatible with the independent discovery requirement.
- **All Bayes factor / ranking infrastructure** (PhaiPhon3). This is Pillar 5's domain, not Pillar 1's.
- **LB phonetic value hard-assignment.** PhaiPhon1-5 all used LB values as hard input. Pillar 1 treats them as post-hoc validation only.

### What changed and why

PhaiPhon treated phonology as a preprocessing step (apply LB values, convert to IPA, feed to model). Ventris1 Pillar 1 treats phonology as the FIRST DISCOVERY STEP — the system must be characterized before any values are assigned. This inverts the relationship: instead of "assume values → analyze," it's "analyze → discover values → validate against LB."

---

## 11. Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. **Known-answer test on Linear B fails to recover ≥ 3 of 5 vowels AND ARI < 0.2** after 3 implementation attempts with different clustering algorithms.
2. **Null test on random data produces structured output** (≥ 2 "pure vowels" identified, or ARI > 0.15 between random grid and LB) — indicating the method detects artifacts, not structure.
3. **More than 40 person-hours spent** on Pillar 1 implementation without passing Gate 1.
4. **Bootstrap CI for V includes both 2 and 7+** — the method cannot distinguish between radically different vowel counts, indicating insufficient signal.

---

## 12. Appendix: Mathematical Proofs and Derivations

### A.1 Why positional frequency identifies pure vowels in a CV syllabary

**Claim:** In a CV syllabary with V pure vowel signs and C×V consonant-vowel signs, pure vowel signs are enriched in word-initial position.

**Proof sketch:**

Let the language have vowel probability p_v (probability that a randomly chosen syllable starts with a vowel) and consonant probability 1 - p_v.

Word-initial syllable:
- With probability p_v, the word starts with a vowel → the initial sign is one of V pure vowel signs
- With probability 1 - p_v, the word starts with a consonant → the initial sign is one of C×V CV signs

Expected initial frequency of a specific pure vowel sign (assuming uniform within vowels):
f_init_vowel = p_v / V

Expected initial frequency of a specific CV sign (assuming uniform within CV):
f_init_cv = (1 - p_v) / (C × V)

Enrichment ratio:
E = f_init_vowel / f_init_cv = p_v × C × V / ((1 - p_v) × V) = p_v × C / (1 - p_v)

For C = 14, p_v = 0.3 (typical): E = 0.3 × 14 / 0.7 = 6.0

This means pure vowel signs appear ~6x more often initially than CV signs (relative to their overall frequency), which is easily detectable with a binomial test.

**Caveat:** This assumes uniform distribution within vowels and within CV signs, which is not realistic. In practice, some vowels and some CV combinations are more frequent. The enrichment ratio will vary per sign, but the qualitative effect (vowel signs enriched initially) holds as long as p_v > 0 and C > 1.

### A.2 Spectral clustering recovers the consonant grid

**Claim:** If the same-consonant affinity matrix A_c has block structure (signs within the same consonant class have high affinity, signs across classes have low affinity), spectral clustering with the correct k recovers the true classes.

**Formal guarantee (simplified):** Under the planted partition model, if the within-class edge probability p and between-class edge probability q satisfy:

(p - q) > C × sqrt(p × log(N) / n_min)

where n_min is the smallest class size, then spectral clustering recovers the true partition with high probability (Abbe 2017, community detection in random graphs).

For our case:
- N ≈ 60 signs
- C ≈ 14 consonant classes
- n_min ≈ V ≈ 4 signs per class
- p depends on the number of alternation pairs (higher is better)

The constraint becomes: we need enough alternation evidence (high p) to distinguish within-class from between-class. With only ~185 potentially inflecting stems and sparse evidence, this is the primary risk.

**Mitigation:** If spectral clustering is unstable, fall back to:
1. Agglomerative clustering with average linkage (more robust to noise)
2. Manual inspection of the top eigenvectors (as Ventris would have done — looking at the grid by eye)
3. Accept a partial grid (only assign high-confidence signs, leave others unassigned)

### A.3 Sign count equation and syllabary type

**Claim:** The total number of phonetic signs N constrains the (V, C) pair.

For a pure CV syllabary: N = V + C × V = V(1 + C)

Given the SigLA corpus has 62 tier1 syllabograms:

| V | C = (N/V) - 1 | Plausibility |
|---|----------------|--------------|
| 3 | 19.7 → 20 | HIGH — consistent with 3-vowel system (a, i, u), many consonants |
| 4 | 14.5 → 14-15 | HIGH — consistent with 3+1 marginal vowel (PhaiPhon4 result) |
| 5 | 11.4 → 11 | MEDIUM — Linear B assumption, fewer consonants |
| 6 | 9.3 → 9 | LOW — few consonants for a syllabary |

The independently determined V (from Step 2) selects the corresponding C, providing a consistency check on the grid dimensions.
