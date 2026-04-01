# PRD: Pillar 1 Consonant Class Discrimination Fix

**Status:** Draft
**Date:** 2026-03-29
**Authors:** Alvin / Claude (design session)
**Depends on:** Pillar 1 v5 (current vowel-fixed grid)
**Feeds into:** Constrained SCA search, Pillar 5 vocabulary resolution, iterative decipherment loop

---

## 1. Background and Context

### 1.1 What is Ventris1?

Ventris1 is a computational decipherment system for Linear A, the undeciphered Bronze Age Cretan script (~1800-1450 BCE). It is organized into 5 pillars:

1. **Pillar 1 (Phonological Engine)** -- Discovers the consonant-vowel grid from distributional evidence
2. **Pillar 2 (Morphological Decomposition)** -- Identifies stems and suffixes
3. **Pillar 3 (Distributional Grammar)** -- Infers word classes and syntax
4. **Pillar 4 (Semantic Anchoring)** -- Assigns meanings via ideograms and context
5. **Pillar 5 (Multi-Source Vocabulary Resolution)** -- Matches Linear A words to candidate languages

The system follows Michael Ventris's original methodology for Linear B: discover structure before assigning values, use internal evidence before external assumptions.

### 1.2 The C-V Grid Concept

Linear A is a syllabary where each sign represents a consonant-vowel (CV) pair. The goal of Pillar 1 is to organize the ~142 syllabograms into a grid:

- **Rows** = consonant classes (signs sharing the same consonant, e.g., ta/te/ti/to/tu)
- **Columns** = vowel classes (signs sharing the same vowel, e.g., ta/ka/na/sa/ra)

Ventris used inflectional alternations to build this grid for Linear B. If two words share a prefix but differ in the final sign (e.g., `ko-no-so` and `ko-no-si`), the differing signs (`so` and `si`) likely share a consonant (s) but differ in vowel. This "same-consonant" evidence is used to cluster signs into consonant rows.

### 1.3 The Corpus

The corpus is the SigLA Full Linear A Corpus (`data/sigla_full_corpus.json`):
- 879 inscriptions, 1,552 words, 170 unique syllabograms
- Average word length: 2.51 signs (very short)
- Most inscriptions are administrative lists (commodity + quantity)

### 1.4 Linear B Validation

53 of the 142 syllabograms have known phonetic values inherited from Linear B (via `data/sign_to_ipa.json`). These are used ONLY for post-hoc validation (Adjusted Rand Index / ARI), never as input to the clustering. The exception is Kober-style vowel anchoring (see below).

### 1.5 Current State: Vowels Fixed, Consonants Broken

The vowel assignment was fixed in the 2026-03-29 session:

- **V=5 vowels** established via triple cross-validation:
  - AB08/a: INDEPENDENT (enrichment 2.72, p=4.2e-10, Kober rank #1, Jaccard #1)
  - AB28/i: INDEPENDENT_VALIDATED (Kober rank #9, Jaccard top 6, LB confirms)
  - AB10/u: INDEPENDENT_VALIDATED (Kober rank #11, Jaccard top 6, LB confirms)
  - AB38/e: CONSENSUS_ASSUMED (too rare at 14 tokens for independent detection)
  - AB61/o: CONSENSUS_ASSUMED (too rare at 6 tokens for independent detection)
- **Kober-anchored vowel column assignment** using LB signs to seed vowel identity, then assigning unknowns by alternation profile similarity.
- **Vowel ARI: +0.242** (up from -0.364 before Kober anchoring). 19/20 known signs correctly assigned (95% accuracy).

But the **consonant clustering is catastrophically broken**:

- The spectral clustering finds **4 consonant classes** (eigengap k=4, silhouette k=4)
- **Class 0 contains 63 of 69 assigned signs (91%)**
- Class 0 includes ALL known consonant types: d, j, k, m, n, p, q, r, s, t, w
- Classes 1-3 have 2 signs each, all unknown
- The grid provides **ZERO consonant discrimination**

The consonant ARI of 0.615 reported in the output is misleading: it is computed on only 6 signs that have LB values and happen to be in the grid. Of those 6, the 4 in class 0 trivially agree with each other because they are ALL in the same class.

---

## 2. Objective

Improve consonant class discrimination from the current 1 mega-class + 3 singletons to **6-8 meaningfully distinct consonant classes**, each containing signs that share an actual consonant.

With 5 vowel classes already established, an 8C x 5V = 40-cell grid would constrain each unknown sign to ~2 possible phonetic readings -- enough for viable cognate matching in the iterative decipherment loop.

### 2.1 Success Criteria

| Metric | Current | Target | Stretch |
|--------|---------|--------|---------|
| Largest consonant class share | 91% (63/69) | < 30% | < 20% |
| Number of classes with >= 3 signs | 1 | >= 6 | >= 8 |
| Consonant ARI (on >= 15 LB signs) | unmeasurable | > 0.15 | > 0.30 |
| Unknown signs constrained to <= 5 readings | ~0% | >= 50% | >= 70% |

### 2.2 Non-Goals

- This PRD does NOT assign phonetic values to consonant classes. The output is abstract labels (C0, C1, ..., C7), not "this is the t-row."
- This PRD does NOT change the vowel assignment (that is fixed and working).
- This PRD does NOT modify Pillars 2-5.

---

## 3. Diagnosis: Why Spectral Clustering Fails

### 3.1 The Alternation Graph is Too Dense

The alternation detector (`pillar1/alternation_detector.py`) builds a same-consonant affinity matrix from inflectional alternations. A pair (sign_a, sign_b) is included if:
1. They appear as final signs of words sharing a prefix (Kober's triplets)
2. The alternation is observed from >= 2 independent stems (`min_independent_stems=2`)
3. The co-occurrence exceeds chance expectation (Poisson test, alpha=0.01)

The problem: the resulting graph has **mean degree ~17.7 out of 69 nodes** (25.6% density). Nearly every sign alternates with nearly every other sign. This makes the graph look almost like a complete graph, with no clean cuts for spectral clustering to find.

Evidence from the eigenvalue spectrum (from `results/pillar1_v5_output.json`):
- First 4 eigenvalues are ~0 (the trivial zero eigenvalues from connected components)
- Then a JUMP to 0.496 (eigengap = 0.496)
- After that, eigenvalues increase smoothly with no clear gap: 0.645, 0.697, 0.747, 0.764, 0.787...
- Silhouette scores are uniformly terrible: 0.093 (k=3), **0.101 (k=4, best)**, 0.093 (k=5), declining to 0.011 (k=8)

A silhouette score of 0.101 means the clustering is barely above random. The spectral algorithm correctly identifies k=4 as the "best" partition, but "best" in this case means "least terrible" -- the graph simply does not have natural clusters.

### 3.2 Root Causes

**Cause 1: Permissive alternation detection.** The threshold `min_independent_stems=2` is too low for this corpus. With 1,552 words and an average length of 2.51 signs, many pairs of frequent signs will share 2+ prefixes by chance, even after the Poisson significance test. The Poisson null model assumes independence of sign positions, which is violated by the frequency distribution (a few signs dominate: AB06 appears 122 times, AB27 appears 134 times).

**Cause 2: Binary affinity matrix.** The matrix stores `weighted_stems` (1.0 for diff_len=1, 0.5 for diff_len=2) but treats all significant pairs equally. A pair observed from 20 independent stems gets the same graph edge as a pair observed from 2 stems. This discards the signal-to-noise gradient.

**Cause 3: Corpus sparsity.** With only 1,552 words and average length 2.51, the alternation signal is inherently noisy. True same-consonant pairs may only alternate 2-3 times, while false positives from frequent signs may also appear 2-3 times. The signal-to-noise ratio is close to 1.

**Cause 4: Spectral clustering assumes assortative community structure.** It looks for groups where within-group affinity exceeds between-group affinity. But in a near-complete graph, this assumption breaks down. The planted partition model (Abbe 2017) requires within-class edge probability to exceed between-class probability by O(sqrt(log n / n)), which may not hold here.

---

## 4. Proposed Approaches

This PRD proposes 5 approaches in priority order. They are not mutually exclusive -- the final solution will likely combine elements from multiple approaches.

### 4.1 Approach A: Tighten Alternation Detection Thresholds

**Rationale:** Reduce graph density so that only high-confidence alternation pairs survive. If the graph has degree ~5-8 instead of ~18, spectral clustering (or any community detection) has a much better chance of finding real structure.

**Changes to `pillar1/alternation_detector.py`:**

1. **Increase `min_independent_stems` from 2 to 3 or 4.** This removes weak pairs that may be chance co-occurrences.

2. **Apply Benjamini-Hochberg FDR instead of raw Poisson p-value.** The current alpha=0.01 per-pair test does not correct for multiple comparisons. With ~2,000 candidate pairs, ~20 false positives are expected. BH-FDR at q=0.05 or q=0.01 would control the false discovery rate.

3. **Frequency-adjusted null model.** The current Poisson lambda uses `p_a * p_b * n_branching_prefixes`, which underestimates co-occurrence for very frequent signs. Add a frequency-tier correction: pairs of top-20 signs should have a higher null expectation.

4. **Log-likelihood ratio filter.** After Poisson significance, additionally require that the observed count exceeds expected by a factor of >= 3 (log-likelihood ratio >= 1.1). This removes pairs that are barely significant.

**Expected outcome:** Graph density drops from ~25% to ~5-10%. Many weak edges removed. Remaining edges are high-confidence same-consonant evidence.

**Risk:** Over-filtering may remove real same-consonant pairs, leaving many signs disconnected from the graph (already 101/170 signs are unassigned due to zero alternation evidence).

### 4.2 Approach B: Weighted Edges and Continuous Affinity

**Rationale:** Instead of binary edges, use the full strength of alternation evidence as edge weights. Spectral clustering on a weighted graph can exploit the signal gradient.

**Changes to `pillar1/grid_constructor.py`:**

1. **Use weighted affinity matrix directly.** The affinity matrix already stores `weighted_stems`, but the current code treats any non-zero entry as an edge. Instead, use the raw weight values (which range from 1.0 to ~20.0) as continuous edge weights.

2. **Apply a sparsification kernel.** Compute the k-nearest-neighbor graph (k=5 or k=7) from the weighted affinity matrix. This keeps only the strongest connections for each sign, naturally sparsifying the graph.

3. **Gaussian kernel transformation.** Convert raw stem counts to affinities via `exp(-d^2 / (2 * sigma^2))` where `d = max_weight - weight`. This amplifies the distinction between strong and weak alternations.

4. **Combine with negative evidence.** Signs that appear in many of the same positions but NEVER alternate may have positive evidence of being in the SAME consonant class (or different classes). Currently, absence of alternation is treated as zero, not as negative evidence.

**Expected outcome:** The weighted graph has clearer community structure because strong same-consonant pairs (10+ stems) are heavily weighted while marginal pairs (2 stems) have near-zero weight.

**Risk:** If true same-consonant pairs happen to have low stem counts (because one sign is rare), they may be downweighted and lost.

### 4.3 Approach C: Jaccard Paradigmatic Substitutability

**Rationale:** This method was already validated for vowel identification with F1=89% on Linear B (see session report section 9). The same principle can be adapted for consonant classification.

**Core principle:** Two signs that can substitute for each other in the same positions (same left and right bigram contexts) are paradigmatic equivalents -- they belong to the same structural slot. For consonant classification, signs that appear in the same bigram environments but NEVER in the same word-final alternation are candidates for the SAME consonant class (same row, different column).

**Algorithm:**

1. For each sign S, compute its **bigram context set**: the set of (left_neighbor, right_neighbor) pairs where S appears.

2. For each pair of signs (A, B), compute the **Jaccard similarity** of their bigram context sets: `J(A,B) = |contexts(A) intersect contexts(B)| / |contexts(A) union contexts(B)|`.

3. Signs with high Jaccard similarity AND that alternate (appear in Kober triplets) share a consonant (same row, different vowel).

4. Signs with high Jaccard similarity AND that do NOT alternate may share BOTH consonant and vowel (same cell) or may be in the same column but different rows.

5. Use the combination of Jaccard similarity and alternation evidence to build a more informative affinity matrix.

**Changes:** New module `pillar1/jaccard_consonant_classifier.py`. Integrates with grid_constructor as an alternative or supplement to spectral clustering.

**Expected outcome:** Jaccard similarity provides an independent signal that is orthogonal to alternation counts. Combining both signals should improve class separation.

**Risk:** The corpus may be too small for reliable bigram context sets (many signs appear < 15 times). Jaccard similarity is undefined for signs with empty context sets.

### 4.4 Approach D: LB Anchor Seeding for Consonant Classes

**Rationale:** The Kober-anchored method worked brilliantly for vowel columns (ARI -0.364 to +0.242, 95% accuracy). Apply the same principle to consonant rows: use the 53 known LB signs to seed consonant classes, then propagate to unknowns.

**Algorithm:**

1. **Group LB signs by consonant.** From `data/sign_to_ipa.json`, extract the consonant component of each reading. This gives us known consonant classes:
   - t-class: ta, te, ti, to, tu (5 signs)
   - k-class: ka, ke, ki, ko, ku (5 signs)
   - s-class: sa, se, si, su (4 signs)
   - r-class: ra, re, ri, ro, ru, ra2 (6 signs)
   - n-class: na, ne, ni, nu, nwa (5 signs)
   - d-class: da, de, di, du (4 signs)
   - m-class: ma, me, mi, mu (4 signs)
   - p-class: pa, pi, po, pu, pu2 (5 signs)
   - w-class: wa, wi (2 signs)
   - j-class: ja, je, ju (3 signs)
   - q-class: qa, qe (2 signs)
   - z-class: za (1 sign)
   - Pure vowels: a, e, i, o, u (5 signs)

2. **Compute each unknown sign's alternation profile with each LB consonant class.** If unknown sign X alternates with ta, te, ti but NOT to, tu, then X likely has consonant "t" (it shares a consonant with those signs).

   Wait -- this is WRONG. Alternation means SAME consonant, DIFFERENT vowel. So if X alternates with ta, te, ti, it means X shares consonant "t" with them.

3. **For each unknown sign X, score each consonant class c:**
   `score(X, c) = sum of alternation weights between X and all LB signs in class c`

4. **Assign X to the consonant class with the highest score**, if the score exceeds a significance threshold.

5. **Create new classes for signs that don't match any LB class well** (these may represent consonants that exist in Linear A but not in Linear B, e.g., the hypothesized Minoan consonants).

**Changes to `pillar1/grid_constructor.py`:** Add an `lb_consonant_seeding` mode alongside spectral clustering.

**Expected outcome:** The 53 LB signs provide strong seeds for ~12 consonant classes. Unknown signs that alternate with known signs get assigned to those classes. This directly leverages the 53 known values.

**CRITICAL PROVENANCE NOTE:** This approach uses LB values as INPUT to consonant classification, not just as post-hoc validation. This must be clearly documented as a CONSENSUS_ASSUMED dependency, not independent discovery. The Pillar 1 PRD originally required that LB values be used "only as a soft check after the fact." This approach relaxes that requirement. The justification is pragmatic: independent discovery produced zero consonant discrimination, so LB-seeded classification is the only viable path to a useful grid. The ARI validation metric becomes meaningless for consonant rows if LB values were used as input.

**Risk:** Circular validation -- if we use LB consonants as input, we cannot use consonant ARI as a validation metric. We need a held-out validation strategy (e.g., leave-one-out cross-validation on LB signs).

### 4.5 Approach E: Community Detection Algorithms

**Rationale:** Spectral clustering assumes globular, well-separated clusters. Community detection algorithms (Louvain, Leiden, label propagation) are designed for graphs with overlapping or irregularly shaped communities and may find structure that spectral clustering misses.

**Options:**

1. **Louvain algorithm** (Blondel et al. 2008): Optimizes modularity via greedy agglomeration. Good at finding natural community structure without specifying k in advance. Available via `python-louvain` or `networkx.community`.

2. **Leiden algorithm** (Traag et al. 2019): Improved version of Louvain with guaranteed connected communities. Available via `leidenalg` package.

3. **Stochastic Block Model (SBM)** fitting: Fits a generative model to the graph and infers the optimal number of blocks. More principled than modularity-based methods. Available via `graph-tool` (complex dependency) or custom implementation.

4. **Resolution parameter sweep:** Louvain/Leiden have a resolution parameter that controls community granularity. Sweep from coarse (few communities) to fine (many communities) and pick the resolution that maximizes agreement with the known LB consonant classes on held-out signs.

**Changes:** New clustering option in `pillar1/grid_constructor.py`. Add `clustering_method: "louvain"` or `clustering_method: "leiden"` alongside existing "spectral" and "agglomerative".

**Expected outcome:** Community detection may find 6-12 communities in the alternation graph that correspond to consonant classes, even in a dense graph.

**Risk:** If the graph is truly near-complete with uniform edge weights, no algorithm can find meaningful structure. The issue may be in the graph construction (Approaches A/B), not in the clustering algorithm (Approach E).

---

## 5. Implementation Plan

### Phase 1: Diagnostic Sprint (1 session)

Before implementing fixes, quantify the problem precisely.

**Tasks:**
1. Count the degree distribution of the alternation graph (histogram).
2. Compute graph density (edges / max_possible_edges).
3. For each LB sign pair with the same known consonant, check whether they have an alternation edge (true positive rate).
4. For each LB sign pair with different known consonants, check whether they have an alternation edge (false positive rate).
5. Compute the true positive rate vs. false positive rate at different stem count thresholds (ROC curve for the alternation detector).
6. Determine the optimal threshold that maximizes same-consonant recall while minimizing cross-consonant false positives.

**Output:** `results/consonant_diagnostic.json` with graph statistics, ROC curve data, and recommended threshold.

**Go/No-Go Gate 1:** If the ROC AUC > 0.65, the alternation signal contains usable consonant information and tightening thresholds (Approach A) is viable. If AUC < 0.55, the alternation signal is too noisy and we must rely on Approach D (LB seeding) as the primary method.

### Phase 2: Threshold Optimization + Weighted Graph (1 session)

**Tasks:**
1. Implement BH-FDR correction in `alternation_detector.py`.
2. Implement frequency-adjusted null model.
3. Implement weighted affinity with kNN sparsification in `grid_constructor.py`.
4. Implement Louvain/Leiden community detection option.
5. Sweep parameters: `min_independent_stems` in {2,3,4,5}, FDR q in {0.01, 0.05}, kNN k in {3,5,7,10}.
6. For each parameter combination, run the grid constructor and measure:
   - Number of consonant classes with >= 3 members
   - Largest class share
   - Consonant ARI against LB (on the ~20 LB signs that are in the grid)
   - Number of disconnected signs

**Output:** `results/consonant_sweep_results.json` with all parameter combinations and metrics.

**Go/No-Go Gate 2:** If any parameter combination achieves consonant ARI > 0.15 with >= 6 classes, proceed to Phase 3 using that configuration. If not, proceed to Phase 3 with Approach D (LB seeding) as the primary method.

### Phase 3: LB Consonant Seeding (1 session)

**Tasks:**
1. Implement `lb_consonant_seeding` mode in `grid_constructor.py`.
2. Group the 53 LB signs into consonant classes (12 classes + pure vowels).
3. For each unknown sign, compute alternation profile scores against each LB consonant class.
4. Assign unknown signs to the best-matching class or create new classes.
5. Implement leave-one-out cross-validation: for each LB sign, remove it from the seeds and check if it gets assigned to the correct class.
6. Implement Jaccard consonant similarity (`pillar1/jaccard_consonant_classifier.py`) as a secondary signal.
7. Combine alternation-based and Jaccard-based scores for final assignment.

**Output:** Updated `results/pillar1_v6_output.json` with improved consonant classes.

**Go/No-Go Gate 3:** Leave-one-out accuracy >= 70% on LB signs. At least 6 consonant classes with >= 3 members each.

### Phase 4: Integration and Validation (1 session)

**Tasks:**
1. Update `pillar1/pipeline.py` to support the new consonant classification method.
2. Add config option `consonant_method: "lb_seeded"` (alongside existing `"spectral"`).
3. Run the full pipeline end-to-end and verify all tests pass.
4. Measure downstream impact: count how many P2 stems gain constrained readings.
5. Document the CONSENSUS_ASSUMED dependency clearly in the output metadata.
6. Run the constrained SCA search with the improved grid to verify that consonant discrimination actually reduces the collision rate.

**Output:** Updated config `configs/pillar1_v6_consonant_fix.yaml`, updated test suite, downstream impact report.

---

## 6. Validation Strategy

### 6.1 Primary Validation: Leave-One-Out Cross-Validation

Because Approach D uses LB values as input, the standard ARI validation becomes circular. Instead:

1. For each of the ~20 LB signs that appear in the alternation graph:
   a. Remove it from the LB anchor set
   b. Run consonant classification using the remaining LB signs as seeds
   c. Check if the held-out sign is assigned to the correct consonant class
2. Report leave-one-out accuracy and confusion matrix.

**Target:** >= 70% leave-one-out accuracy.

### 6.2 Secondary Validation: Downstream Impact

The real test is whether improved consonant discrimination enables better cognate matching:

1. Count how many signs are constrained to <= 5 possible readings (from the grid cell).
2. Count how many P2 stems gain full phonetic transcription (because their one unknown sign is now constrained).
3. Run the constrained SCA search on these newly-constrained stems and check whether the per-pair p-values improve.

**Target:** >= 50% of assigned signs constrained to <= 5 readings. >= 10 new fully-constrained P2 stems.

### 6.3 Tertiary Validation: Structural Coherence

1. Dead vowel test: same-vowel consecutive pair rate should still be significant (currently p=1.6e-5).
2. Phonotactic coherence: forbidden bigrams should still be detected.
3. Grid should not degenerate (no class with > 30% of signs).

---

## 7. Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| LB consonant seeding makes validation circular | HIGH | Use leave-one-out CV instead of ARI. Document CONSENSUS_ASSUMED provenance. |
| Alternation signal is pure noise (ROC AUC < 0.55) | HIGH | Fall back to LB seeding only (Approach D). Accept CONSENSUS_ASSUMED dependency. |
| Over-tightening thresholds disconnects too many signs | MEDIUM | Track unassigned sign count. If > 60% unassigned, relax thresholds. |
| Community detection finds too many/few communities | MEDIUM | Use resolution parameter sweep with LB cross-validation to tune. |
| Linear A consonant system differs from Linear B | MEDIUM | Allow "unmatched" class for signs that don't fit any LB consonant. These may represent Minoan-specific consonants (e.g., palatalized series). |
| Jaccard context sets too sparse for rare signs | MEDIUM | Restrict Jaccard analysis to signs with >= 10 corpus occurrences. |
| New dependencies (python-louvain, leidenalg) | LOW | Both are pure Python, pip-installable, no C extensions needed (important: this Windows environment lacks MSVC build tools). |

---

## 8. How This Feeds Into the Iterative Decipherment Loop

The iterative decipherment loop is the viable path to decipherment identified in the 2026-03-29 session report. It works as follows:

```
P1 Grid (constrained readings per sign)
  |
  v
P2 Stems + P1 Grid --> Partially phonetic stems with constrained unknowns
  |
  v
SCA Search against candidate lexicons --> Cognate hypotheses
  |
  v
Best cognate matches --> Resolve unknown signs (pick the reading that produces the cognate)
  |
  v
Feed resolved signs back into P1 Grid --> More signs known --> more stems constrained
  |
  v
Repeat until convergence
```

**Current bottleneck:** The consonant mega-class means each unknown sign has ~12 possible consonant values, giving ~60 possible readings per sign (12C x 5V). With 2-sign unknown stems, this produces 3,600 candidate transcriptions per stem -- far too many for meaningful cognate discrimination.

**After this fix:** If we achieve 8 consonant classes, each unknown sign has ~1-2 possible consonant values, giving ~5-10 possible readings per sign. For 2-sign unknown stems, this produces 25-100 candidates -- manageable for SCA matching. For 1-sign unknown stems (the 184 "one-missing-syllable" stems), this produces 5-10 candidates -- excellent for discrimination.

This is the single highest-leverage improvement for the entire decipherment system.

---

## 9. Key Files

| File | Purpose |
|------|---------|
| `pillar1/grid_constructor.py` | Current spectral clustering code (primary modification target) |
| `pillar1/alternation_detector.py` | Alternation pair detection (threshold tuning target) |
| `pillar1/pipeline.py` | Pipeline orchestrator (integration point) |
| `pillar1/vowel_identifier.py` | Vowel identification (DO NOT MODIFY -- this is working) |
| `pillar1/lb_validator.py` | LB validation (needs update for leave-one-out CV) |
| `data/sign_to_ipa.json` | 53 known LB sign readings (consonant seed source) |
| `data/sigla_full_corpus.json` | Full corpus (879 inscriptions, 1,552 words) |
| `configs/pillar1_v5_lb_vowels.yaml` | Current config (V=5, spectral clustering) |
| `results/pillar1_v5_output.json` | Current output (4 consonant classes, 91% in class 0) |
| `docs/logs/2026-03-29-to-04-01-full-session-report.md` | Session report with full context |
| `docs/logs/2026-03-27-pillar-weakness-audit.md` | Weakness audit identifying P1 consonant issue |

---

## 10. Summary of Current Eigenvalue/Silhouette Evidence

For reference, these are the actual numbers from the v5 output that demonstrate the problem:

**Eigenvalues (first 10):** 0.0, 0.0, 0.0, 0.0, 0.496, 0.645, 0.697, 0.747, 0.764, 0.787

The first 4 zeros indicate ~4 connected components (or near-zero eigenvalues from the dense graph). The jump at index 4 (eigengap=0.496) is why the algorithm picks k=4. After that, eigenvalues increase smoothly with no secondary gap, meaning there is no clean 6-8 class structure visible to spectral methods.

**Silhouette scores:** k=3: 0.093, k=4: 0.101, k=5: 0.093, k=6: 0.053, k=7: 0.036, k=8: 0.011, k=9: 0.022, k=10: 0.051

All silhouette scores are near zero (a well-clustered graph would show 0.5+). The scores DECREASE as k increases, confirming that the graph resists fine-grained partitioning.

**Class sizes (current k=4):** Class 0: 63 signs, Class 1: 2 signs (R_ma, R_me), Class 2: 2 signs (R_si, R_ti), Class 3: 2 signs (R_e, R_ja)

The 3 non-trivial classes contain only "R_" prefix signs (signs identified by their reading name rather than AB code), suggesting these are artifacts of the corpus loader's sign ID namespace, not real phonological groupings.
