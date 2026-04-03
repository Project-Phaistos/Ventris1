# PRD: Jaccard Paradigmatic Substitutability for Full Sign Classification

**Status:** Draft
**Date:** 2026-03-29
**Depends on:** Pillar 1 (Phonological Engine) -- extends it with finer consonant/vowel classification
**Feeds into:** Iterative Decipherment Loop, Pillar 2 (Morphology), Pillar 5 (Vocabulary Resolution)
**Authors:** Alvin / Claude (design session)

---

## 0. Background for New Sessions

This PRD assumes NO prior context. Everything needed to understand and execute this work is contained here.

### 0.1 The Ventris1 Project

Ventris1 is a computational decipherment pipeline for Linear A, an undeciphered Bronze Age script from Minoan Crete (~1800-1450 BCE). The project is organized into 5 "pillars":

1. **Pillar 1 (Phonological Engine):** Discovers the sound system from distributional evidence alone -- consonant-vowel grid, vowel/consonant inventories, phonotactic constraints. Uses sign IDs (AB08, AB59), NOT phonetic labels.
2. **Pillar 2 (Morphology):** Decomposes words into stems and affixes.
3. **Pillar 3 (Grammar):** Distributional grammar induction.
4. **Pillar 4 (Semantics):** Contextual meaning inference.
5. **Pillar 5 (Vocabulary Resolution):** Cross-linguistic comparison and cognate search.

### 0.2 Linear A as a CV Syllabary

Linear A is a CV (consonant-vowel) syllabary. Each sign represents either:
- A pure vowel: a, e, i, o, u (5 signs)
- A consonant-vowel pair: ta, te, ti, to, tu, ka, ke, ki, ko, ku, ... (~137 signs)

The signs are logically organized in a **grid**: rows share a consonant (the t-row: ta, te, ti, to, tu) and columns share a vowel (the a-column: a, ta, ka, na, da, ...). Recovering this grid from distributional evidence is the central goal of Pillar 1.

Linear A has ~142 syllabograms total, of which 62 have tier-1 correspondences with the deciphered Linear B script (Mycenaean Greek), and 80 are undeciphered.

### 0.3 The Corpus

- **Linear A:** SigLA Full Corpus (`data/sigla_full_corpus.json`): 879 inscriptions, 1,552 words, 3,249 syllabogram tokens, 170 unique syllabograms. Mostly administrative texts (commodity records, inventories).
- **Linear B (validation):** Test corpus (`pillar1/tests/fixtures/linear_b_test_corpus.json`): 142 inscriptions, 448 words, 1,249 tokens, 56 unique signs. Also HF dataset (`C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv`).

### 0.4 The Problem This PRD Solves

Pillar 1's spectral clustering on the alternation graph produces **4 consonant classes**, but **class 0 is a mega-class containing nearly ALL consonant types**. From the production output (`results/pillar1_v5_output.json`):

- Consonant ARI = 0.615 (moderate -- driven entirely by 3 small classes separating out)
- Vowel ARI = 0.242 (improved from -0.364 after Kober-anchored vowel assignment)
- Class 0 contains: da, ka, ja, ku, ma, na, pa, pi, qa, ra, ro, sa, se, si, su, ta, te, ti, ... (ALL consonant series mixed together)
- Classes 1-3 contain only 2-3 signs each (R_ma/R_me, R_si/R_ti, R_e/R_ja -- all rare signs)

The alternation-based method cannot separate the main consonant series because the alternation graph is too dense: mean degree = 17.7 edges per sign. When every sign alternates with every other sign, spectral clustering collapses everything into one cluster.

### 0.5 The Jaccard Vowel Discovery (Prior Work)

During the Ventris1 session (March 2026), we developed a novel method for vowel identification based on **paradigmatic substitutability** -- the idea from structural linguistics that signs with similar distributional profiles belong to the same phonological class.

**Method:** For each sign, compute the set of all (left-context, right-context) bigram pairs in which the sign appears. Then compute the Jaccard similarity between any two signs' context sets. Signs that can substitute for each other (appear in the same bigram contexts) have high Jaccard similarity.

**Results on Linear B (known-answer validation):**
- F1 = 88.9% for vowel identification
- 4/5 vowels correctly identified at 100% precision, 80% recall
- Zero false positives
- The miss (u) is explainable: Mycenaean Greek /u/ distributes anomalously (medial/final, rarely initial)

**Implementation:** `pillar1/scripts/entropy_vowel_analysis.py` -- 710 lines, includes data loading, feature computation (Shannon entropy, normalized entropy, positional frequency, bigram context sets), Jaccard matrix computation, ROC sweep for threshold selection, and both Linear B validation and Linear A application.

**Key insight that motivates this PRD:** The Jaccard method identified vowels because **pure vowel signs share context sets with each other** (they can appear in the same positions). The SAME principle should apply to consonant series: signs ta, te, ti, to, tu share LEFT-context sets because they all begin with /t/ -- the preceding sign in a word is constrained by the consonant onset, not the vowel. Similarly, signs ta, ka, na, da share RIGHT-context sets because they all end with /a/.

---

## 1. Objective

Classify all ~142 Linear A syllabograms into:
1. **Consonant series** (grid rows): groups of signs sharing the same consonant onset (e.g., {ta, te, ti, to, tu} = t-series)
2. **Vowel classes** (grid columns): groups of signs sharing the same vowel nucleus (e.g., {a, ta, ka, na, da} = a-column)

using ONLY distributional evidence from the corpus, with NO external phonetic assumptions.

This extends the validated Jaccard paradigmatic substitutability method from binary vowel/consonant classification to full grid reconstruction. The output is a refined C-V grid with finer consonant groupings than P1's spectral clustering currently achieves.

### 1.1 Success Criteria

On Linear B (known-answer test):
- **Consonant series ARI >= 0.50** (substantially above P1's effective 0.0 within class 0)
- **Vowel class ARI >= 0.40** (above P1's 0.242)
- **Combined (mean of consonant + vowel ARI) >= 0.45**

On Linear A:
- Produces >= 6 consonant series with >= 3 signs each (vs. P1's 1 mega-class + 3 singletons)
- At least 3 consonant series are internally consistent when spot-checked against LB values (for the 62 tier-1 signs with known LB correspondences)

---

## 2. Non-Goals

- **No phonetic value assignment.** This classifies signs into abstract groups (consonant-class-7, vowel-class-3), not phonetic labels (/t/, /a/). Phonetic labeling is a downstream task.
- **No external language data.** No cognate lexicons, no IPA mappings. Purely internal distributional analysis.
- **No replacement of P1.** This module AUGMENTS Pillar 1 output. The existing alternation-based grid is preserved; Jaccard classification provides an independent second opinion that can be combined.
- **No novel clustering algorithms.** Use standard methods (hierarchical clustering, spectral clustering, community detection) on the Jaccard similarity matrix. The novelty is in the FEATURE (directional Jaccard), not the clustering.
- **No morphological analysis.** We operate on raw sign sequences. Morpheme boundaries are Pillar 2's concern.

---

## 3. Method

### 3.1 Core Insight: Directional Context Sets

In a CV syllabary, a sign's phonological identity has two components: its consonant onset and its vowel nucleus. These components manifest differently in left vs. right bigram contexts.

**Left-context Jaccard (for consonant classification):**
Signs sharing a consonant tend to follow the same set of signs. In a word like `X-ta` vs. `X-te`, the preceding sign X is constrained by the consonant /t/ of the following sign (because the preceding sign must end a syllable that transitions into /t/). Therefore:
- `left_context(sign) = {s : (s, sign) is an observed bigram}`
- `J_left(sign_a, sign_b) = |left_context(a) & left_context(b)| / |left_context(a) | left_context(b)|`
- High J_left => signs share a consonant => same grid row

**Right-context Jaccard (for vowel classification):**
Signs sharing a vowel tend to precede the same set of signs. In a word like `ta-X` vs. `ka-X`, the following sign X is constrained by the vowel /a/ of the preceding sign (dead vowel convention: consecutive CV signs often share a vowel). Therefore:
- `right_context(sign) = {s : (sign, s) is an observed bigram}`
- `J_right(sign_a, sign_b) = |right_context(a) & right_context(b)| / |right_context(a) | right_context(b)|`
- High J_right => signs share a vowel => same grid column

**Full-context Jaccard (for general similarity):**
The existing method uses (left, right) tuples as context. This captures BOTH consonant and vowel similarity simultaneously:
- `context(sign) = {(l, r) : l-sign-r is an observed trigram}`
- `J_full(sign_a, sign_b) = |context(a) & context(b)| / |context(a) | context(b)|`
- High J_full => signs share BOTH consonant AND vowel (near-duplicates or free variants)

### 3.2 Algorithm

#### Step 0: Data Preparation

Load the corpus and extract sign sequences. Apply the same preprocessing as `entropy_vowel_analysis.py`:
- Exclude damaged words
- Exclude logograms and numerals (syllabograms only)
- Include BOS (beginning-of-sequence) and EOS (end-of-sequence) as boundary markers
- Minimum token count threshold: signs with fewer than 5 occurrences are excluded (configurable)

#### Step 1: Compute Directional Context Sets

For each sign s with sufficient frequency:
1. `left_context(s)` = set of unique signs (including BOS) that immediately precede s
2. `right_context(s)` = set of unique signs (including EOS) that immediately follow s
3. `full_context(s)` = set of unique (left, right) bigram tuples around s

Record counts alongside sets for potential weighted variants.

#### Step 2: Compute Pairwise Jaccard Matrices

Compute three N x N Jaccard similarity matrices (where N = number of signs with sufficient data):
1. `J_left[i, j]` = Jaccard of left_context sets
2. `J_right[i, j]` = Jaccard of right_context sets
3. `J_full[i, j]` = Jaccard of full_context sets (already implemented)

These are symmetric, non-negative matrices with diagonal = 1.0.

#### Step 3: Consonant Series Discovery (via J_left)

1. **Hierarchical clustering** on `J_left` using average linkage (UPGMA). Use `1 - J_left` as the distance metric.
2. **Determine the number of consonant series** via:
   a. Eigengap heuristic on the Laplacian of `J_left`
   b. Silhouette score sweep for k = 5..20
   c. Gap statistic vs. uniform null
   d. Cross-reference with the sign count equation: if V=5 vowels and N=142 syllabograms, then C = (N-V)/V = ~27 consonant series. However, many signs are rare or unclassifiable, so expect 10-15 populated series.
3. **Cut the dendrogram** at the level corresponding to the best k.
4. **Post-process:** Merge any cluster with < 2 signs into the nearest neighbor cluster (singletons are unreliable). Flag remaining singletons as "unclassified."

**Alternative clustering:** If hierarchical clustering is unstable, use spectral clustering on `J_left` or Louvain community detection (which automatically selects k by maximizing modularity).

#### Step 4: Vowel Class Discovery (via J_right)

Same procedure as Step 3, but using `J_right`:
1. Hierarchical clustering on `1 - J_right`
2. Determine number of vowel classes (expect V=3 to 5 based on prior work)
3. Cut dendrogram, post-process

#### Step 5: Cross-Validation Between Directions

The consonant and vowel classifications should be **orthogonal**: signs in the same consonant series should be in DIFFERENT vowel classes (they share a consonant but differ in vowel), and vice versa.

Check: For each consonant series, verify that it contains signs from >= 2 different vowel classes. If a consonant series contains signs from only 1 vowel class, the consonant classification may be wrong (or the series has only 1 attested vowel).

Check: For each vowel class, verify that it contains signs from >= 2 different consonant series. A vowel class with only 1 consonant series is suspicious.

Compute the **orthogonality score**: mutual information between consonant and vowel assignments. In a perfect grid, MI should be near zero (consonant and vowel are independent).

#### Step 6: Grid Assembly

Combine consonant series (from Step 3) and vowel classes (from Step 4) into a 2D grid. Each cell (c, v) should contain 0 or 1 signs. Cells with 2+ signs indicate:
- Free variants (signs used interchangeably)
- Misclassification
- Non-CV signs (CVC, CVCV)

Output the grid as a structured JSON matching the P1 output schema, with finer consonant_class labels.

#### Step 7: Ensemble with P1

Combine the Jaccard-based classification with P1's alternation-based classification:
1. For signs where both methods agree: high confidence
2. For signs where methods disagree: flag for manual review, use evidence counts to break ties
3. For signs classified by Jaccard but not P1 (rare signs that lack alternation evidence but have sufficient bigram data): accept Jaccard classification at lower confidence

### 3.3 Weighted Jaccard Variant

The basic Jaccard treats all context elements equally. A weighted variant may improve performance:

`J_weighted(a, b) = sum(min(w_a(x), w_b(x))) / sum(max(w_a(x), w_b(x)))`

where `w_a(x)` is the frequency of context element x for sign a. This gives more weight to frequent contexts (more reliable) and less to hapax contexts (more noisy).

Implement both unweighted and weighted variants. Compare on LB validation.

### 3.4 Minimum Context Set Size

Signs with very small context sets (e.g., a sign that appears in only 2 unique left contexts) will have unreliable Jaccard similarities (high variance, dominated by noise). Set a minimum:
- `min_left_contexts = 3` (sign must have >= 3 unique left neighbors)
- `min_right_contexts = 3` (same for right)

Signs below these thresholds are excluded from clustering and marked "insufficient_data."

---

## 4. Validation Plan

### Validation Protocol

**BLOCKING REQUIREMENT:** No method may be applied to Linear A until it passes
ALL validation gates below on known-answer corpora. A "smoke test" on 5-10
entries is NOT sufficient. Each gate requires a FULL-CORPUS run.

**Data sources for validation:**
- Linear B corpus: `pillar1/tests/fixtures/linear_b_test_corpus.json` (primary)
- Linear B HF data: `C:\Users\alvin\hf-ancient-scripts\data\linear_b\` (supplementary -- MUST be included for full-corpus coverage)
- Linear B sign values: `C:\Users\alvin\hf-ancient-scripts\data\linear_b\sign_to_ipa.json`
- Latin test corpus: `pillar2/tests/fixtures/latin_cv_corpus.json`
- Additional corpora: invoke `data-extraction` skill if needed (follow 7-step adversarial pipeline)

**Reporting:** Each validation run must report:
1. Corpus size (inscriptions, words, unique signs)
2. Full metric (ARI, precision@k, F1) with confidence interval
3. Comparison to null baseline (shuffled corpus)
4. Any failure modes or edge cases discovered

### 4.1 Known-Answer Test: FULL Linear B Corpus (BLOCKING)

Linear B is the ideal validation corpus because:
- The phonological system is fully known (5 vowels, ~15 consonant series)
- The script is closely related to Linear A (shares many signs)
- A test corpus exists: `pillar1/tests/fixtures/linear_b_test_corpus.json` (142 inscriptions, 448 words, 56 unique signs)
- A supplementary HF dataset exists: `C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv`

**IMPORTANT: This must be a FULL-CORPUS run.** Both the test corpus AND the HF supplementary data must be loaded and deduplicated. Running on a 5-10 word subset is NOT acceptable.

**Procedure:**
1. Load the FULL LB corpus: combine `pillar1/tests/fixtures/linear_b_test_corpus.json` AND `C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv` using the deduplication function from `entropy_vowel_analysis.py`
2. Run LEFT-context Jaccard (J_left) on ALL LB syllabograms in the combined corpus
3. Cluster to discover consonant series
4. Compare discovered consonant series against known LB consonant rows using ARI
5. Compare discovered vowel classes against known LB vowel columns using ARI
6. Report precision/recall/F1 per consonant series and per vowel class

**Consonant series ground truth (must recover these):**
The method must recover LB's known consonant series with ARI >= 0.30. Specifically, the following series must be identified as distinct clusters:
- t-series: ta, te, ti, to, tu (5 signs)
- k-series: ka, ke, ki, ko, ku (5 signs)
- r-series: ra, re, ri, ro, ru (5+ signs)
- n-series: na, ne, ni, no, nu (5 signs)
- s-series: sa, se, si, so, su (4-5 signs)
At minimum, 3 of these 5 major series must be recovered as distinct clusters.

**Ground truth for LB (full):** From the sign inventory:
- Vowels: a, e, i, o, u (5 signs)
- Consonant series: d-series (da, de, di, do, du), k-series (ka, ke, ki, ko, ku), n-series (na, ne, ni, no, nu), p-series (pa, pe, pi, po, pu), r-series (ra, re, ri, ro, ru), s-series (sa, se, si, so, su), t-series (ta, te, ti, to, tu), m-series (ma, me, mi, mo, mu), j-series (ja, je, jo), w-series (wa, we, wi, wo), q-series (qa, qe), z-series (za, ze)

**Expected challenges:**
- LB corpus is only 1,249 tokens with 56 unique signs -- some signs will have too few bigrams for reliable Jaccard. The HF supplementary data mitigates this.
- Some consonant series may be underrepresented (e.g., z-series has very few tokens)
- The dead vowel convention in Mycenaean Greek is strong, which helps right-context Jaccard but may not be universal

### 4.2 Second Language Test: Cypriot Syllabary or Synthetic CV Corpus (BLOCKING)

**Rationale:** A single validation corpus (Linear B) is insufficient. The method must demonstrate generalization on at least one additional CV syllabary.

**Option A -- Cypriot Syllabary (preferred):**
If Cypriot Greek syllabary data is available locally at `C:\Users\alvin\hf-ancient-scripts\data\` or can be downloaded:
1. Invoke `data-extraction` skill. Source: Unicode CLDR Cypriot entries, Wiktionary Cypriot Greek inscriptions, or the Edalion tablet inscription. Follow the 7-step adversarial pipeline.
2. Run LEFT-context Jaccard on the Cypriot corpus
3. Compare against known Cypriot syllabary consonant/vowel structure
4. Report ARI for both consonant and vowel classification

**Option B -- Japanese hiragana as synthetic CV corpus (fallback):**
If Cypriot data is not available:
1. Construct a synthetic CV corpus from Japanese hiragana mapped to CV structure. Source: frequency-ranked Japanese word list from Wiktionary or BCCWJ corpus.
2. Map each hiragana character to its CV decomposition (ka, ki, ku, ke, ko -> k-series, etc.)
3. Run LEFT-context Jaccard and verify consonant series recovery
4. Report ARI

**Pass criterion:** Consonant ARI >= 0.20 on the second language (lower threshold acceptable due to different script/language properties).

### 4.3 Null Test: Shuffled Corpus (BLOCKING)

Randomly permute signs within each word (destroying all positional structure) and run the pipeline on the FULL LB corpus. Expected:
- All Jaccard similarities converge toward a uniform baseline
- No meaningful clusters emerge
- ARI ~ 0.0 against known LB grid (must be < 0.05)

**BLOCKING:** If the shuffled corpus produces ARI >= 0.05, the method is detecting an artifact, not phonological structure. The method MUST NOT proceed to Linear A until this test passes.

This confirms the method detects real structure, not frequency artifacts.

### 4.4 Ablation Tests

1. **Left-only vs. Right-only vs. Full:** Which directional Jaccard best recovers consonant series? Vowel classes?
2. **Weighted vs. Unweighted:** Does frequency weighting improve ARI?
3. **Minimum frequency threshold:** Sweep from 3 to 15 tokens; measure ARI and coverage tradeoff
4. **BOS/EOS inclusion:** Does including boundary markers help or hurt?

---

## 5. Linear A Application

### 5.1 Procedure

After validation on Linear B:
1. Load the Linear A SigLA corpus (`data/sigla_full_corpus.json`)
2. Run the full Jaccard classification pipeline
3. Output the refined grid

### 5.2 Expected Results

- 170 unique syllabograms in corpus, of which ~45-60 have sufficient data (>= 5 tokens AND >= 3 unique contexts per direction)
- Expect 8-15 consonant series (not all 27 theoretical series will be populated with enough evidence)
- Expect 3-5 vowel classes
- The 62 tier-1 signs (with LB correspondences) provide partial ground truth for spot-checking

### 5.3 Cross-Reference with P1

Compare the Jaccard grid against the existing P1 v5 output:
- Do the Jaccard consonant series split P1's mega-class (consonant_class 0) into meaningful subgroups?
- Do the Jaccard vowel classes align with P1's 5 Kober-anchored vowel columns?
- Where they disagree, which has more evidence?

### 5.4 Output Format

Produce a JSON file matching the P1 output schema (see `docs/prd/PRD_PILLAR_1_PHONOLOGY.md` Section 4.1) with:
- `grid.assignments[].consonant_class` -- Jaccard-based consonant series (finer than P1)
- `grid.assignments[].vowel_class` -- Jaccard-based vowel class
- `grid.assignments[].jaccard_confidence` -- confidence from clustering (silhouette score of this sign within its cluster)
- `grid.assignments[].p1_consonant_class` -- original P1 class for cross-reference
- `grid.assignments[].p1_agreement` -- boolean, whether Jaccard and P1 agree

---

## 6. Go/No-Go Gates

### Gate 1: FULL-CORPUS Left-Context Jaccard Recovers at Least 3 LB Consonant Series (CRITICAL -- BLOCKING)

**Test:** On the FULL combined LB corpus (test corpus + HF supplementary data, deduplicated), compute J_left and cluster. At least 3 of the ~15 known consonant series must be recovered as distinct clusters (ARI contribution > 0 from those 3).

**BLOCKING:** This gate MUST use the FULL combined corpus. A run on a subset or a 5-word sample does NOT satisfy this gate. The validation report must state the total number of inscriptions, words, and unique signs processed.

**Threshold:** Consonant ARI >= 0.30 on LB.

**On failure:** The left-context signal is too weak at this corpus size. Options:
- Try weighted Jaccard (may boost signal)
- Try combining J_left with alternation evidence from P1
- If ARI < 0.10 after all variants: KILL this approach for consonant classification (vowel classification via J_right may still work)

### Gate 1b: Second Language Validation (BLOCKING)

**Test:** Run the LEFT-context Jaccard pipeline on a second CV syllabary corpus (Cypriot Greek or synthetic Japanese hiragana -- see Section 4.2). The method must produce consonant ARI >= 0.20 on the second language.

**BLOCKING:** Method does NOT proceed to Linear A until this gate passes. If no second language corpus is available locally, invoke `data-extraction` skill to obtain one before proceeding.

**On failure:** Method is overfitting to Linear B's specific distributional properties. Investigate whether the failure is corpus-size-related (second corpus too small) or structural (the method exploits LB-specific phonotactic patterns).

### Gate 2: J_right Matches or Exceeds Existing Vowel Identification (HIGH)

**Test:** On the FULL combined LB corpus, J_right-based vowel classification achieves F1 >= 80% (matching the existing cliquishness method from `entropy_vowel_analysis.py`).

**Threshold:** Vowel F1 >= 80% on LB.

**On failure:** J_right alone is weaker than the full-context cliquishness. Use J_right as supplementary evidence only, keep the existing vowel method as primary.

### Gate 3: Null Test Passes (CRITICAL -- BLOCKING)

**Test:** Shuffled FULL LB corpus produces no meaningful clusters (ARI < 0.05).

**BLOCKING:** Must run on the FULL corpus (not a subset). If ARI >= 0.05, the method detects an artifact and MUST NOT be applied to Linear A.

**On failure:** The method is detecting an artifact (likely frequency-based, not distributional). Debug by checking whether high-frequency signs cluster together regardless of phonological class.

### Gate 4: Jaccard Splits P1 Mega-Class on Linear A (HIGH)

**Test:** On Linear A, the Jaccard consonant classification splits P1's consonant_class 0 into >= 3 subgroups with >= 3 signs each.

**On failure:** Either the LA corpus is too small for directional Jaccard, or the mega-class is genuinely a single phonological class (unlikely given ~10+ known consonant series in LB). If failure: try combining Jaccard with alternation weights as a joint similarity metric.

### Gate 5: Orthogonality Check (MEDIUM)

**Test:** The discovered consonant and vowel classifications are approximately independent. Normalized mutual information (NMI) between consonant_class and vowel_class <= 0.30.

**On failure:** The two dimensions are conflated -- the clustering is picking up overall sign similarity rather than separating consonant from vowel. May need to decorrelate: first cluster on J_left for consonants, then within each consonant cluster, subcluster on J_right for vowels (sequential rather than parallel).

---

## 7. Academic References

### 7.1 Foundational Work

- **Kober, A. E. (1946).** "Inflection in Linear Class B: 1 -- Declension." *American Journal of Archaeology*, 50(2), 268-276. The original method for discovering consonant rows through inflectional alternation in Linear B. P1's alternation detector is a direct computational implementation of Kober's hand method.

- **Ventris, M. (1952).** "Decipherment of Linear B -- Work Note 20." The grid methodology: structure before values, internal evidence before external assumptions. The consonant-vowel grid is the central analytical artifact.

### 7.2 Distributional Linguistics

- **Harris, Z. S. (1954).** "Distributional structure." *Word*, 10(2-3), 146-162. The foundational paper on distributional semantics: "You shall know a word by the company it keeps" (later attributed to Firth 1957). Paradigmatic substitutability -- words that appear in the same contexts belong to the same distributional class -- is the theoretical basis for the Jaccard method.

- **Firth, J. R. (1957).** "A synopsis of linguistic theory 1930-1955." *Studies in Linguistic Analysis*, 1-32. "You shall know a word by the company it keeps." The distributional hypothesis.

### 7.3 Computational Methods

- **List, J.-M. (2012).** "SCA -- Sound-Class-Based Phonetic Alignment." In *New Directions in Logic, Language and Computation*. Springer. Dolgopolsky sound classes for phonetic comparison. Used in the Ventris1 SCA cognate search module (not directly related to Jaccard, but part of the broader pipeline).

- **Jaccard, P. (1912).** "The distribution of the flora in the alpine zone." *New Phytologist*, 11(2), 37-50. The original Jaccard similarity index, applied here to distributional context sets rather than botanical species sets.

- **Abbe, E. (2017).** "Community detection and stochastic block models: recent developments." *Journal of Machine Learning Research*, 18(177), 1-86. Theoretical guarantees for spectral clustering on noisy affinity matrices. Relevant to the clustering step.

### 7.4 Prior Work in This Session

- **Jaccard Vowel Analysis (2026-03-29):** Implemented in `pillar1/scripts/entropy_vowel_analysis.py`. Validated at F1=89% on Linear B. Full results documented in `docs/logs/2026-03-29-to-04-01-full-session-report.md`, Section 9.

- **Kober Vowel Analysis (2026-03-30):** Implemented in `pillar1/scripts/kober_vowel_analysis.py`. Uses P1 alternation pairs to identify initial-position vowel clique. AB08/a confirmed unambiguously (rank #1, 2.3x margin). Limitation: alternation graph too dense for consonant separation.

- **Pillar 1 v5 Production Run (2026-03-30):** Results in `results/pillar1_v5_output.json`. 4 consonant classes, class 0 = mega-class. Consonant ARI = 0.615, Vowel ARI = 0.242.

---

## 8. Risks

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Corpus too small for directional Jaccard** -- splitting contexts into left/right halves the data per dimension. With 3,249 tokens and 170 types, some signs may have < 3 unique left OR right contexts. | HIGH | MEDIUM | Set minimum context thresholds. Report coverage (% of signs classifiable). Fall back to full-context Jaccard for signs with insufficient directional data. Combine LB test corpus with HF lexicon for validation. |
| **Left-context does not separate consonants** -- if Linear A phonotactics are permissive (any consonant can follow any consonant), left-context sets will be uniform across all signs, giving Jaccard ~ 1.0 for everything. | HIGH | LOW-MEDIUM | Validate on LB first (Mycenaean Greek has known phonotactic constraints). If LB left-context Jaccard is near-uniform, the approach fails for consonant classification. |
| **Dead vowel convention confounds right-context** -- if Linear A uses dead vowels strongly, right-context similarity reflects shared vowels (intended) BUT ALSO shared dead-vowel patterns that may be idiosyncratic to word structure, not phonology. | MEDIUM | MEDIUM | Compare weighted vs. unweighted Jaccard. The dead vowel effect should make right-context BETTER for vowel classification, not worse. |
| **Frequency confound** -- high-frequency signs appear in more contexts, inflating their Jaccard similarity to other high-frequency signs regardless of phonological class. | MEDIUM | HIGH | Test: compute Spearman correlation between sign frequency and mean Jaccard similarity. If abs(rho) > 0.5, add frequency normalization (divide context set sizes by expected overlap under independence). |
| **Clustering instability** -- with small sample sizes, hierarchical clustering may produce very different trees depending on minor perturbations. | MEDIUM | MEDIUM | Bootstrap stability analysis: resample inscriptions 100 times, run clustering, report which sign pairs are co-clustered in >= 80% of bootstrap replicates (consensus clustering). |
| **Consonant series with < V signs** -- some rare consonant series (e.g., the z-series in LB) will have only 1-2 attested signs, making them undetectable. | LOW | HIGH | Accept partial coverage. Report which signs could not be classified and why. The goal is to classify the frequent signs correctly, not to achieve 100% coverage. |

---

## 9. Integration: How This Feeds the Iterative Decipherment Loop

### 9.1 The Bottleneck

As documented in the session report (Section 8), the fundamental bottleneck for Linear A decipherment is:
- 53 of 142 syllabograms have known phonetic values (from LB transfer)
- This produces mostly 1-2 syllable stems -- too short for cross-linguistic comparison
- 184 stems are missing JUST ONE unknown syllable -- if we could narrow that unknown to 2-3 candidate readings (instead of 80+), those stems become searchable

### 9.2 How Jaccard Classification Helps

Currently, P1's mega-class assigns each unknown sign to 1 of 10+ possible consonants (10 candidate readings). If the Jaccard method narrows this to 1 of 2-3 consonants (one consonant series), the candidate readings drop to 2-3 per sign.

Example:
- Unknown sign AB99 is in P1 class 0 (mega-class) with vowel-class 2 (i-class)
- P1 constraint: AB99 could be any of {di, ki, mi, ni, pi, ri, si, ti, wi, zi} -- 10 candidates
- Jaccard consonant series 7 contains {AB59/ta, AB04/te, AB37/ti, AB99, AB05, AB50}
- If Jaccard series 7 corresponds to the t-series: AB99 = ti (1 candidate!)
- Even without phonetic labeling, constraining AB99 to series 7 (5 candidates) instead of class 0 (10+ candidates) reduces the search space 2-5x

### 9.3 The Iterative Loop

1. **Jaccard classification** narrows unknown signs to consonant series + vowel class (this PRD)
2. **Constrained SCA search** uses the narrowed candidates to search the 184 one-unknown stems against candidate lexicons (18 languages)
3. **Cognate identification** finds stems that match specific words in known languages
4. **Reading confirmation** -- if stem X-AB99-Y matches a known word when AB99=ti but not when AB99=ki, this confirms AB99's reading
5. **Bootstrap** -- newly confirmed readings feed back into step 1, enlarging the known set and enabling longer stem matching

Each cycle adds readings, which enables longer stems, which enables better matching, which confirms more readings. The Jaccard classification is the ENTRY POINT to this loop because it provides the initial narrowing without requiring any external data.

### 9.4 Downstream Impact

If Jaccard classification achieves even moderate success (narrows each unknown to a consonant series of 5 signs):
- The 184 one-unknown stems become searchable with 5 candidate readings each (instead of 80+)
- At 5 candidates x 18 languages, this is 16,560 comparisons (tractable) vs. 265,680 (intractable with proper multiple testing correction)
- SCA matching at 3+ syllable length has demonstrated discriminative power (unlike the 2-syllable stems that failed in the constrained search)

---

## 10. Implementation Notes

### 10.1 Key Files

| File | Role |
|------|------|
| `pillar1/scripts/entropy_vowel_analysis.py` | Existing Jaccard implementation (full-context only). Start here -- extend with directional variants. |
| `pillar1/scripts/kober_vowel_analysis.py` | Alternation-based analysis. Cross-reference results. |
| `pillar1/grid_constructor.py` | P1 grid construction module. The output format to match. |
| `pillar1/corpus_loader.py` | Corpus loading utilities. Reuse for data preparation. |
| `pillar1/tests/fixtures/linear_b_test_corpus.json` | LB validation corpus (142 inscriptions, 448 words). |
| `data/sigla_full_corpus.json` | Linear A production corpus (879 inscriptions, 1,552 words). |
| `results/pillar1_v5_output.json` | Current P1 output to compare against. |
| `C:\Users\alvin\hf-ancient-scripts\data\linear_b\linear_b_words.tsv` | Additional LB words for validation corpus augmentation. |
| `C:\Users\alvin\hf-ancient-scripts\data\linear_b\sign_to_ipa.json` | Sign-to-IPA mapping (for loading HF LB data). |

### 10.2 Dependencies

- `numpy` -- matrix operations
- `scipy` -- hierarchical clustering (`scipy.cluster.hierarchy`), distance metrics
- `sklearn` -- ARI (`sklearn.metrics.adjusted_rand_score`), silhouette score, spectral clustering
- All already installed in the Ventris1 environment (used by P1).

### 10.3 Suggested Module Structure

```
pillar1/
  scripts/
    jaccard_sign_classification.py   # NEW: main analysis script
  jaccard_classifier.py              # NEW: reusable module (if warranted)
```

Or extend `entropy_vowel_analysis.py` with directional Jaccard functions. Prefer extending the existing file if the additions are < 300 lines; create a new file if larger.

### 10.4 Output Files

- `results/jaccard_classification_lb.json` -- LB validation results with ARI scores
- `results/jaccard_classification_la.json` -- LA production results
- Both should include the full Jaccard matrices (for downstream inspection) and clustering diagnostics

---

## 11. Sprint Plan

### Sprint 1: Directional Jaccard on Linear B (Validation)

**Goal:** Implement left/right context Jaccard and validate on LB.
**Gate:** Gate 1 (consonant ARI >= 0.30) and Gate 2 (vowel F1 >= 80%).
**Deliverable:** `jaccard_sign_classification.py` with LB results.

Tasks:
1. Extend context set computation to separate left/right/full
2. Compute J_left and J_right matrices
3. Cluster J_left for consonant series (hierarchical + spectral)
4. Cluster J_right for vowel classes
5. Evaluate against known LB grid (ARI, per-class P/R/F1)
6. Run null test (shuffled corpus)
7. Run ablation tests (weighted vs. unweighted, BOS/EOS, min frequency)

### Sprint 2: Linear A Application

**Goal:** Apply validated method to Linear A corpus.
**Gate:** Gate 4 (splits mega-class into >= 3 subgroups).
**Deliverable:** `results/jaccard_classification_la.json`.

Tasks:
1. Run pipeline on LA corpus
2. Cross-reference with P1 v5 output
3. Inspect consonant series for internal consistency (spot-check against LB values for tier-1 signs)
4. Produce the refined grid

### Sprint 3: Ensemble and Integration

**Goal:** Combine Jaccard classification with P1 alternation-based classification.
**Gate:** Gate 5 (orthogonality check).
**Deliverable:** Updated P1 output with finer consonant classes.

Tasks:
1. Implement ensemble logic (agreement scoring, tie-breaking)
2. Produce combined grid
3. Feed narrowed sign candidates into constrained SCA search (integration with Pillar 5)
4. Document results and publish to the iterative decipherment loop

---

## 12. Kill Criteria

Abandon this approach if:

1. **Gate 1 fails after all variants tried** (unweighted, weighted, combined with alternation). Left-context Jaccard cannot recover consonant structure from this corpus. The data may simply be too sparse.
2. **Gate 3 fails** (null test produces structured output). The method detects frequency artifacts, not phonological structure.
3. **LB consonant ARI < 0.10 after Sprint 1.** The directional Jaccard is no better than random for consonant classification.
4. **More than 20 person-hours on Sprint 1** without passing Gate 1.

If killed, the Jaccard method retains its value for VOWEL identification (validated at F1=89%) but should not be extended to consonant classification. Consonant series discovery would need a fundamentally different approach (e.g., neural embedding of sign sequences, or larger corpus from new inscription discoveries).

---

## Appendix A: Mathematical Details

### A.1 Why Left-Context Identifies Consonant Onset

In a CV syllabary with dead vowel convention, consider the bigram `s1-s2` within a word. Let `s1 = C1V1` and `s2 = C2V2`.

The transition probability `P(s2 | s1)` can be decomposed:
```
P(s2 | s1) = P(C2V2 | C1V1) = P(C2 | C1, V1) * P(V2 | C2, C1, V1)
```

Under the simplifying assumption that consonant transitions are primarily determined by the consonant of the following sign (phonotactic constraint on consonant clusters):
```
P(C2 | C1, V1) ~ P(C2 | context)  -- depends on C2's phonological class
```

Therefore, signs sharing C2 (same consonant onset) will tend to follow the same set of preceding signs, making their left-context sets similar.

Under the dead vowel convention:
```
P(V2 | C2, C1, V1) ~ P(V2 = V1)  -- vowel harmony/copying
```

This means V2 is partially determined by V1, NOT by C2. So the left-context set is driven by C2 (the consonant onset), not V2 (the vowel). This is why J_left should separate consonant series.

### A.2 Expected Jaccard Similarity Under Null

For two signs with left-context sets of sizes |A| and |B| drawn uniformly from a universe of U possible left-context types:

```
E[J(A, B)] = E[|A & B|] / E[|A | B|]
```

Under independence (null hypothesis of no phonological structure):
```
E[|A & B|] ~ |A| * |B| / U
E[|A | B|] ~ |A| + |B| - |A| * |B| / U
E[J_null] ~ (|A| * |B| / U) / (|A| + |B| - |A| * |B| / U)
```

For the LA corpus with U ~ 45 frequent signs and typical context set sizes |A| ~ |B| ~ 15:
```
E[J_null] ~ (15 * 15 / 45) / (15 + 15 - 15 * 15 / 45) = 5 / 25 = 0.20
```

Consonant-sharing signs should have J_left substantially above 0.20 (perhaps 0.40-0.60). Signs from different consonant series should be near or below 0.20.

### A.3 Relation to Information-Theoretic Measures

Jaccard similarity of context sets is related to but distinct from:
- **Mutual Information:** MI measures total shared information between two distributions; Jaccard measures overlap of supports (sets).
- **Cosine Similarity of Context Vectors:** If we represent each sign as a frequency vector over contexts, cosine similarity captures both support overlap AND frequency correlation. Jaccard is a special case where frequencies are binarized.
- **Jensen-Shannon Divergence:** Measures distributional distance. Lower JSD ~ higher distributional similarity. JSD operates on probability distributions; Jaccard operates on sets.

Jaccard was chosen over these alternatives because:
1. It is simple and interpretable
2. It is robust to frequency effects (binary set membership, not frequency-weighted)
3. It was already validated for vowel identification (F1=89%)
4. It avoids the estimation issues of MI and JSD with sparse data (many zero-frequency context elements)

The weighted Jaccard variant (Section 3.3) bridges toward cosine similarity while retaining the robustness of set-based overlap.
