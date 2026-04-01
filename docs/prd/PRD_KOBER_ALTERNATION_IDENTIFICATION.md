# PRD: Kober Alternation Identification -- Triangulating Unknown Linear A Sign Readings

**Status:** Draft
**Depends on:** Pillar 1 outputs (alternation pairs, C-V grid, vowel assignment)
**Feeds into:** PRD_ITERATIVE_DECIPHERMENT.md (reading expansion loop), Pillar 2 (morphological decomposition), Pillar 5 (vocabulary resolution)
**Complements:** PRD_JACCARD_SIGN_CLASSIFICATION.md (paradigmatic substitutability approach)
**Date:** 2026-03-29
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Identify specific phonetic readings for unknown Linear A syllabographic signs by computationally applying Alice Kober's alternation method at scale, using 610 validated alternation pairs and 53 known Linear B anchor signs.

The current Pillar 1 pipeline uses Kober's method for two coarse tasks:
1. **Consonant row clustering** -- spectral clustering on the alternation graph groups signs into consonant classes (ARI = 0.615 against LB ground truth)
2. **Vowel column assignment** -- LB-anchored assignment achieves 95% accuracy (19/20 known signs correct)

This PRD introduces a **third, finer-grained application**: for each unknown sign, triangulate its position in the C-V grid by examining which known signs it alternates with and which it does not, then cross-reference those constraints with the P1 grid assignment to narrow the reading to 1-2 specific CV values.

**Why this matters:** The project has identified 184 P2 stems that are missing exactly ONE unknown syllable. If that one sign's reading can be determined, the stem becomes fully phonetic and available for SCA-based cross-linguistic matching in Pillar 5. Each successfully identified sign reading multiplies downstream matchable vocabulary.

**Traced to README:** "Inflectional alternation clustering (Kober's method, computationalized) -- Signs that alternate in the same word-final position across inflectional variants share a consonant (different vowels) -> place in same grid ROW."

---

## 2. Non-goals

- **No direct phonetic value assignment from external languages.** This method identifies readings by internal structural triangulation, not by matching to candidate language phonologies.
- **No new alternation detection.** This PRD consumes the existing 610 P1 alternation pairs; it does not modify the alternation detector.
- **No morphological segmentation.** Paradigm-level analysis is Pillar 2's job. This PRD uses raw alternation evidence only.
- **No claim of certainty.** Outputs are ranked hypotheses with confidence scores, not definitive assignments. Multiple readings per sign are expected.
- **No modification to the LB anchor set.** The 53 known signs in `data/sign_to_ipa.json` are treated as fixed ground truth. Expansion of the anchor set happens in PRD_ITERATIVE_DECIPHERMENT.md.

---

## 3. Background

### 3.1 Alice Kober's Method (1946-1950)

Alice Kober was a classicist at Brooklyn College who, before her death in 1950 at age 43, developed the analytical framework that made the Linear B decipherment possible. Her key papers:

- Kober, A. (1946). "Inflection in Linear Class B: 1 -- Declension." *American Journal of Archaeology* 50(2): 268-276.
- Kober, A. (1948). "The Minoan Scripts: Fact and Theory." *American Journal of Archaeology* 52(1): 82-103.

Kober observed that in an inflected language written in a consonant-vowel (CV) syllabary, grammatical endings produce a specific pattern when a word is declined or conjugated. Consider a hypothetical word "dama-" (stem) appearing in two case forms:

```
Nominative:  da-ma-to     (signs: DA, MA, TO)
Genitive:    da-ma-ta     (signs: DA, MA, TA)
```

The final signs TO and TA **alternate** -- they appear in the same position within words that are otherwise identical. Because each CV sign encodes both a consonant AND a vowel:

- TO = /to/ (consonant /t/, vowel /o/)
- TA = /ta/ (consonant /t/, vowel /a/)

The alternating signs SHARE A CONSONANT but DIFFER IN VOWEL. This is forced by the structure of a CV syllabary: when the grammatical ending changes the vowel (different case/tense/number), the sign must change, but the consonant of the syllable stays the same.

Kober catalogued these alternations by hand on index cards for hundreds of Linear B words, ultimately identifying sets of signs that belonged to the same consonant row. She called these "Kober triplets" -- groups of three or more signs related by shared consonant. This work, which she published without any phonetic value assignment, was the foundation that Michael Ventris used in 1952 to construct his decipherment grid.

### 3.2 The Cambridge Framework (Bennett 1951, Ventris 1952)

Emmett Bennett's 1951 publication of the Pylos tablets (*The Pylos Tablets: A Preliminary Transcription*) provided the systematic sign list that Kober and Ventris needed. Bennett's numbering system (which this project uses as AB-codes: AB01, AB02, ...) standardized sign identification.

Ventris combined Kober's alternation data with:
- Positional frequency analysis (which signs appear word-initially, suggesting pure vowels)
- Known place names (Knossos, Phaistos, Amnisos) as phonetic anchors
- The grid: a 2D table where rows share consonants and columns share vowels

The decipherment succeeded because the grid, once partially filled, became self-reinforcing: each new reading constrained which readings were possible for remaining signs in the same row and column.

### 3.3 Prior Art in This Project

The current session has already applied Kober's method computationally:

**Solution B (Kober alternation vowel clique):** `pillar1/scripts/kober_vowel_analysis.py` built the alternation graph from P1's 610 significant pairs and searched for the initial-position vowel clique. AB08/a was confirmed as the strongest pure vowel candidate (rank #1, 2.3x margin over #2). AB28/i at rank #9, AB10/u at rank #11. AB38/e and AB61/o were too rare to detect by alternation alone (12 and 5 total attestations respectively).

**LB-anchored vowel column assignment:** `pillar1/grid_constructor.py` function `_assign_vowel_classes()` implements Kober's principle for vowel assignment: sign X is assigned to the vowel column whose LB anchor signs it does NOT alternate with (same vowel = same column = no alternation expected). Result: vowel ARI jumped from -0.364 (frequency round-robin) to +0.242. 95% accuracy on 20 testable known signs.

**Alternation graph statistics (from `results/kober_vowel_analysis.json`):**
- 69 nodes, 610 edges
- Mean degree: 17.7, median: 18, max: 46 (AB27/re), min: 1
- 129 significant initial-position pairs
- Consonant ARI: 0.615 (against LB ground truth)
- Vowel ARI: 0.242 (Kober-anchored, against LB ground truth)

**Constrained SCA search results (session addendum):**
- Aggregate enrichment 3.2x above chance across 99 partially-phonetic stems
- Discriminative readings found: AB56->po, AB118->po, AB54->qa
- Systematic reading preferences across vowel classes (V=0 favors "ra", V=2 favors "wi", V=4 favors "pu")

These results confirm that the alternation graph contains usable structural information, but it has not yet been exploited for per-sign reading identification.

---

## 4. Inputs

### 4.1 Primary: P1 Alternation Pairs

**File:** `results/pillar1_v5_output.json`
**Section:** `alternation_pairs` (610 significant pairs)

Each pair has:
- `sign_a`, `sign_b` -- the two alternating signs
- `weighted_stems` -- number of independent stem contexts supporting the alternation
- `p_value` -- statistical significance (Bonferroni-corrected binomial test)

### 4.2 Primary: P1 Grid Assignments

**File:** `results/pillar1_v5_output.json`
**Section:** `grid.assignments` (69 assigned signs)

Each assignment has:
- `sign_id` -- the sign
- `consonant_class` -- integer (0-3, from spectral clustering)
- `vowel_class` -- integer (0-4, from Kober-anchored LB assignment)
- `confidence` -- float (0.167 to 1.0)
- `evidence_count` -- number of alternation pairs contributing

### 4.3 Primary: Known Sign Readings (LB Anchors)

**File:** `data/sign_to_ipa.json` (53 entries)

Maps reading names to IPA values. The corresponding AB-codes are available in the corpus sign inventory. These 53 signs have established Linear B phonetic values and serve as the fixed anchor set.

The LB phonetic values with full CV decomposition are defined in `kober_vowel_analysis.py` (lines 447-468):

| Consonant Row | a | e | i | o | u |
|---|---|---|---|---|---|
| (pure vowel) | AB08 | AB38 | AB28 | AB61 | AB10 |
| /t/ | AB59 | AB04 | AB37 | AB05 | AB69 |
| /d/ | AB01 | AB45 | AB06 | -- | AB51 |
| /m/ | AB80 | AB13 | AB73 | -- | -- |
| /p/ | AB03 | -- | AB39 | AB11 | AB50 |
| /r/ | AB60 | AB27 | AB53 | AB02 | AB26 |
| /s/ | AB31 | AB09 | AB41 | -- | AB58 |
| /j/ | AB57 | AB46 | -- | -- | AB65 |
| /k/ | AB77 | -- | AB67 | -- | AB81 |
| /n/ | AB54 | AB24 | AB30 | -- | AB55 |
| /w/ | -- | -- | AB07 | -- | -- |
| /q/ | AB16 | AB78 | -- | -- | -- |

### 4.4 Secondary: Kober Vowel Analysis Results

**File:** `results/kober_vowel_analysis.json`

Contains the full alternation graph, initial-position analysis (129 pairs), vowel clique, vowel column assignment, consonant row assignment (27 rows from greedy assembly), and LB cross-reference results.

### 4.5 Secondary: Corpus

**File:** `data/sigla_full_corpus.json`

879 inscriptions, 1,552 words, 3,249 syllabogram tokens, 170 unique syllabograms. Provides the raw positional and co-occurrence data.

---

## 5. Outputs (Interface Contract)

### 5.1 Primary Output: Sign Reading Hypotheses

**File:** `results/kober_triangulation_output.json`

```json
{
  "metadata": {
    "timestamp": "...",
    "method": "kober_triangulation",
    "n_anchors_used": 53,
    "n_alternation_pairs": 610,
    "n_unknown_signs_analyzed": "...",
    "n_signs_with_readings": "..."
  },
  "sign_readings": [
    {
      "sign_id": "AB59",
      "top_reading": "ta",
      "confidence": 0.92,
      "candidate_readings": [
        {"reading": "ta", "score": 0.92, "evidence": "..."},
        {"reading": "na", "score": 0.45, "evidence": "..."}
      ],
      "alternation_evidence": {
        "alternates_with_known": ["AB08/a", "AB28/i", "AB57/ja"],
        "does_not_alternate_with": ["AB31/sa", "AB80/ma"],
        "inferred_consonant_row": "t",
        "inferred_vowel_column": "a",
        "consonant_row_confidence": 0.85,
        "vowel_column_confidence": 0.95
      },
      "grid_cross_reference": {
        "p1_consonant_class": 0,
        "p1_vowel_class": 0,
        "grid_consistent": true
      },
      "identification_tier": "STRONG"
    }
  ],
  "validation": {
    "held_out_recovery": {
      "n_held_out": "...",
      "n_recovered": "...",
      "accuracy": "..."
    }
  }
}
```

**Identification tiers:**
- `STRONG`: single reading with confidence >= 0.8, consistent with P1 grid, corroborated by >=3 anchor alternations
- `PROBABLE`: top reading with confidence >= 0.6, or 2 readings with combined confidence >= 0.85
- `CONSTRAINED`: narrowed to 2-3 readings, no single dominant candidate
- `INSUFFICIENT`: fewer than 2 anchor alternations, cannot meaningfully constrain

### 5.2 Secondary Output: Updated Candidate Reading Table

For integration with the iterative decipherment loop, produce a flat table:

```
sign_id    top_reading    confidence    tier    n_anchor_edges    constrained_to
AB59       ta             0.92          STRONG  12                [ta]
AB41       si             0.76          PROB    8                 [si, se]
AB80       ma             0.55          CONSTR  5                 [ma, na, ra]
```

---

## 6. Approach: Kober Triangulation Algorithm

### 6.1 Core Principle

In a CV syllabary with inflectional morphology, the alternation graph has a specific structure:

**Same consonant row, different vowel column:** Signs in the same consonant row but different vowel columns WILL alternate (they appear in the same stem position when the grammatical ending changes the vowel).

**Same vowel column, different consonant row:** Signs in the same vowel column but different consonant rows will NOT alternate (a change that preserves the vowel but changes the consonant would require changing the stem, not the ending).

**Same cell:** A sign does not alternate with itself.

Therefore, for an unknown sign U with known alternation partners K1, K2, ..., Kn:
- U shares a consonant row with all Ki (alternation = same consonant)
- U has a DIFFERENT vowel column from all Ki (alternation = different vowel)
- U has the SAME vowel column as signs it does NOT alternate with in the same consonant row

### 6.2 Algorithm: Triangulation

**Input:** Unknown sign U, set of alternation partners A(U), set of non-alternation partners in same consonant class NA(U), grid assignments, anchor sign readings.

**Step 1 -- Collect anchor evidence.**
For sign U, identify all known signs (from the 53 anchors) that U alternates with:
```
K_alt = {K in anchors : (U, K) in alternation_pairs}
```
And all known signs that U does NOT alternate with:
```
K_no_alt = {K in anchors : (U, K) NOT in alternation_pairs AND both U and K have sufficient attestation}
```
The "sufficient attestation" guard prevents treating absence-of-evidence as evidence-of-absence for rare signs.

**Step 2 -- Consonant row inference.**
Group the known alternation partners by their LB consonant:
```
For each K in K_alt:
    consonant_votes[consonant_of(K)] += edge_weight(U, K)
```
U's consonant row is the one that receives the MOST votes from its alternation partners. The intuition: if U alternates with ta, te, ti, to, tu (all /t/-row signs), then U is overwhelmingly likely to be in the /t/ row.

But there is a subtlety: U alternates with signs in its OWN row (same consonant, different vowel). So the consonant votes should come from signs with the SAME consonant as U, and those signs should span multiple vowel columns.

More precisely: U alternates with signs that share its consonant. So if U's alternation partners include AB59/ta, AB04/te, AB37/ti, those are all /t/-row signs, and U is likely /t/-row too.

**Step 3 -- Vowel column exclusion.**
U must be in a DIFFERENT vowel column from each of its alternation partners (same consonant, different vowel):
```
excluded_vowels = {vowel_of(K) for K in K_alt if consonant_of(K) == inferred_consonant_of(U)}
```
This narrows U to the vowel columns NOT represented among its same-row alternation partners.

**Step 4 -- Vowel column inclusion (non-alternation evidence).**
U should share a vowel column with same-row signs it does NOT alternate with. If the only /t/-row sign that U does NOT alternate with is AB69/tu, then U is likely in the /u/ column:
```
included_vowels = {vowel_of(K) for K in K_no_alt if consonant_of(K) == inferred_consonant_of(U)}
```

**Step 5 -- Cross-reference with P1 grid assignment.**
Check whether U's P1 grid assignment (consonant_class, vowel_class) is consistent with the triangulated consonant row and vowel column. Consistency boosts confidence; inconsistency flags the assignment for review.

**Step 6 -- Compute candidate readings.**
The intersection of (inferred consonant row) x (surviving vowel columns) gives a set of candidate CV readings. Score each by:
- Number of supporting anchor alternations
- Strength (weighted_stems) of supporting alternations
- Consistency with P1 grid assignment
- Whether the candidate CV cell is already occupied by a known sign (if so, this reading is less likely -- but not impossible, as Linear A may have signs for the same value that Linear B does not)

**Step 7 -- Confidence scoring.**
```
confidence(reading) = (n_supporting_alternations / n_total_anchor_alternations)
                    * (1 if grid_consistent else 0.5)
                    * (0.7 if cell_already_occupied else 1.0)
```

### 6.3 Worked Example with Real Data

**Target sign: AB80 (unknown -- pretend we don't know it's /ma/)**

From `results/kober_vowel_analysis.json`, AB80's alternation partners include:
- AB08 (a, pure vowel) -- alternates, weight ~4
- AB77 (ka) -- alternates, weight ~3
- AB31 (sa) -- alternates, weight ~2
- AB51 (du) -- alternates, weight ~2
- AB57 (ja) -- alternates, weight ~3
- AB41 (si) -- alternates, weight ~3
- AB04 (te) -- alternates, weight ~2

**Step 1:** K_alt includes AB08(/a/), AB77(/ka/), AB31(/sa/), AB51(/du/), AB57(/ja/), AB41(/si/), AB04(/te/).

**Step 2 -- Consonant row inference:**
- AB08 is pure vowel (no consonant info for row)
- AB77 is /k/-row, AB31 is /s/-row, AB51 is /d/-row, AB57 is /j/-row, AB41 is /s/-row, AB04 is /t/-row
- Multiple consonant rows are represented -- this means AB80 shares its consonant row with SOME of them, and the others are from different rows alternating in initial position.
- Key insight: within a SPECIFIC suffix position, only same-row signs alternate. Across ALL positions, cross-row alternations also occur (initial-position alternations link vowels across rows). The algorithm must weight suffix-position alternations more heavily.

**Step 3 -- Vowel exclusion (within the inferred row):**
If we tentatively assign AB80 to the /m/-row (its true identity): AB80 alternates with AB73/mi and AB13/me (checking the full graph). It does NOT alternate with AB80 itself. The excluded vowels are {i, e} (from mi, me).

**Step 4 -- Vowel inclusion:**
The /m/-row signs that AB80 does NOT alternate with (because they share its vowel) would be other /ma/ signs -- but there is only one /ma/ sign. However, from the P1 grid: AB80 is in vowel class 0, which corresponds to the /a/ column.

**Step 5 -- Cross-reference:**
P1 grid: AB80 is consonant_class 0, vowel_class 0, confidence 1.0, evidence_count 91.
The inferred consonant row is /m/ and the inferred vowel column is /a/.
Result: AB80 = /ma/. Correct.

**Step 6 -- Candidate readings:** {ma} -- only one survivor after exclusion.

### 6.4 Handling Complications

**6.4.1 Consonant mega-class problem.**
The current P1 grid has a single dominant consonant class (class 0) containing most signs. This is because the alternation graph is too dense for spectral clustering to separate more than 4 classes. The Kober triangulation partially bypasses this problem because it works with individual anchor signs, not with spectral classes. However, the consonant row inference in Step 2 will be noisier when the P1 consonant class is uninformative.

Mitigation: Use the greedy consonant row assembly from `kober_vowel_analysis.py` (27 rows) instead of the P1 spectral clustering (4 classes). The greedy rows are finer-grained.

**6.4.2 Sparse alternation evidence.**
Many signs have few alternation partners (min degree = 1 in the graph). Signs with fewer than 3 anchor alternations cannot be meaningfully triangulated.

Mitigation: Report these as `INSUFFICIENT` tier. They may benefit from the Jaccard method (PRD_JACCARD_SIGN_CLASSIFICATION.md) which uses bigram context rather than alternation.

**6.4.3 Initial-position vs. suffix-position alternations.**
The 610 P1 alternation pairs include both suffix-position (Kober-type, same consonant row) and initial-position (vowel-type, same vowel column) alternations. The algorithm must distinguish these, because:
- Suffix-position alternation: U shares consonant with partner (same row)
- Initial-position alternation: U shares vowel context with partner (may be different row)

Mitigation: Use the initial-position analysis from `results/kober_vowel_analysis.json` (129 pairs) to flag initial-position alternations and weight them differently. Alternatively, restrict Step 2 to suffix-only alternations for consonant row inference.

**6.4.4 Signs shared between Linear A and Linear B that may differ.**
The fundamental axiom (README) is that Linear A = Minoan, not Greek. Some signs may have different phonetic values in Linear A than in Linear B. The triangulation method is partly robust to this because it works from structural position, not from assumed values -- but the anchor values are LB-assumed.

Mitigation: Flag any sign where the triangulated reading is inconsistent with the P1 grid assignment as a potential LA/LB divergence candidate.

---

## 7. Validation: Linear B Held-Out Recovery

The gold standard for this method is whether it can recover known sign readings from partial information.

### 7.1 Leave-K-Out Cross-Validation on LB Signs

**Protocol:**
1. From the 53 known signs, select K signs as "unknown" (held-out).
2. Run the Kober triangulation algorithm using the remaining 53-K signs as anchors.
3. For each held-out sign, record the top-1 and top-3 predicted readings.
4. Measure accuracy: what fraction of held-out signs are correctly identified?

**Test configurations:**
- Leave-1-out (K=1, 53 trials): measures per-sign recovery with maximum anchor support
- Leave-5-out (K=5, sampled 100 times): measures robustness to reduced anchor density
- Leave-10-out (K=10, sampled 50 times): stress test -- can the method work with ~43 anchors?

### 7.2 Expected Performance

The method should achieve:
- **Top-1 accuracy >= 60%** on leave-1-out (32+ of 53 signs correctly identified)
- **Top-3 accuracy >= 80%** on leave-1-out (42+ of 53 signs have correct reading in top 3)
- **Top-1 accuracy >= 40%** on leave-5-out (degradation expected with fewer anchors)

These thresholds are informed by:
- The Kober-anchored vowel assignment already achieves 95% vowel accuracy on 20 testable signs
- Consonant ARI = 0.615 suggests consonant row identification is good but not perfect
- Combining vowel (95% accurate) and consonant (61.5% ARI) evidence should yield 50-70% joint accuracy for the full CV reading

### 7.3 Linear B Corpus Validation (Optional, Higher Confidence)

If Linear B corpus data is available (Pylos/Knossos tablets), run the full pipeline on Linear B:
1. Detect alternations in the Linear B corpus
2. Hold out K signs
3. Triangulate readings for held-out signs
4. Measure against known Linear B values (100% ground truth available)

This provides a clean validation on a fully deciphered script.

---

## 8. Expected Yield

### 8.1 How Many Signs Could Be Identified

From the alternation graph statistics:
- 69 signs have alternation evidence (in the graph)
- 53 are already known (LB anchors)
- **16 unknown signs have alternation evidence** and are candidates for triangulation

Of these 16, yield depends on alternation density:
- Signs with degree >= 5 and >= 3 anchor alternation partners: likely STRONG or PROBABLE identification (~5-8 signs)
- Signs with degree 3-4 and >= 2 anchor partners: likely CONSTRAINED (~3-5 signs)
- Signs with degree 1-2: likely INSUFFICIENT (~3-5 signs)

**Conservative estimate: 5-10 unknown signs with actionable readings** (STRONG or PROBABLE tier).

### 8.2 Downstream Impact

Each new sign reading unlocks stems for SCA matching:
- 184 P2 stems are missing exactly ONE unknown syllable
- If that one sign is among the 5-10 identified, the stem becomes fully phonetic
- A single identified sign might unlock 5-20 stems (depending on sign frequency)
- Example: AB80 appears in 91 alternation contexts. If it's common in P2 stems, identifying it could unlock 10+ stems.

The leverage is multiplicative: 5 new sign readings could unlock 25-100 new fully-phonetic stems, transforming the SCA search from 37 matchable stems to 60-130+.

---

## 9. Go/No-Go Gates

### Gate 1: LB Held-Out Recovery (MUST PASS)

**Test:** Leave-1-out cross-validation on 53 known signs.
**Pass criterion:** Top-3 accuracy >= 70%.
**Fail action:** If top-3 accuracy < 70%, the triangulation method is unreliable. Investigate whether the problem is consonant row inference (use greedy rows instead of spectral), vowel column inference (increase weight on non-alternation evidence), or insufficient alternation density. If accuracy < 50% after tuning, the method is not viable and should be abandoned in favor of Jaccard-based identification.

### Gate 2: Self-Consistency Check (MUST PASS)

**Test:** For each sign identified as STRONG or PROBABLE, verify that its reading is consistent with all alternation evidence. Specifically: if sign U is identified as CV reading /Ca/, then every known sign it alternates with should be in the same consonant row (/C/) and a different vowel column (not /a/).
**Pass criterion:** >= 90% of STRONG/PROBABLE identifications are self-consistent.
**Fail action:** Inconsistent identifications indicate a bug in the algorithm or bad alternation data. Debug individual cases.

### Gate 3: Non-Triviality (SHOULD PASS)

**Test:** At least 3 unknown signs receive STRONG or PROBABLE identifications.
**Pass criterion:** n_STRONG + n_PROBABLE >= 3.
**Fail action:** If fewer than 3 signs can be identified, the method works in principle (Gates 1-2 passed) but the Linear A alternation graph is too sparse for meaningful yield. Proceed to PRD_JACCARD_SIGN_CLASSIFICATION.md for an alternative approach. The two methods may produce complementary results.

### Gate 4: No Pathological Degeneration (MUST PASS)

**Test:** The algorithm does not assign the same reading to multiple unknown signs (which would indicate the scoring is dominated by a single feature).
**Pass criterion:** All STRONG identifications are unique readings. PROBABLE identifications have at most 2 signs sharing a reading.
**Fail action:** If pathological, the scoring function is collapsing. Add diversity penalties or review the consonant row inference.

---

## 10. Components

### 10.1 Module: `pillar1/scripts/kober_triangulation.py`

Main entry point. Orchestrates the triangulation pipeline:
1. Load P1 alternation pairs and grid assignments
2. Load anchor sign readings
3. For each unknown sign in the alternation graph:
   a. Collect anchor alternation evidence
   b. Infer consonant row
   c. Exclude/include vowel columns
   d. Score candidate readings
   e. Assign confidence and tier
4. Run self-consistency checks
5. Output results to JSON

### 10.2 Module: `pillar1/scripts/kober_triangulation_validation.py`

Held-out validation module:
1. Leave-K-out cross-validation on known signs
2. Accuracy reporting (top-1, top-3, per-tier)
3. Confusion analysis (which consonant rows and vowel columns are most confused)
4. Gate pass/fail evaluation

### 10.3 Integration: Updated `pillar1/pipeline.py`

Add triangulation as an optional post-processing step after grid construction. Gate on P1 pipeline completion (requires alternation pairs, grid assignments, and LB anchor loading).

### 10.4 Test Suite: `pillar1/tests/test_kober_triangulation.py`

Three-tier tests following project conventions:
- **Formula correctness** (~15 tests): scoring function properties, edge cases, empty inputs
- **Known-answer** (~10 tests): specific signs with known readings should be recovered
- **Null/negative** (~5 tests): signs with no alternation evidence should return INSUFFICIENT; random graphs should not produce STRONG identifications

---

## 11. Relationship to Complementary Methods

### 11.1 Jaccard Paradigmatic Substitutability (PRD_JACCARD_SIGN_CLASSIFICATION.md)

The Jaccard method (validated in this session at F1=89% on Linear B for vowel identification) operates on a fundamentally different signal: two signs are similar if they appear in similar bigram contexts (paradigmatic substitutability). This is a distributional/contextual signal, not an alternation/morphological signal.

The methods are **complementary, not competing:**
- Kober triangulation works best for signs with **rich alternation evidence** (high degree in the alternation graph, many anchor alternation partners)
- Jaccard works best for signs with **rich contextual evidence** (high frequency, diverse bigram contexts)
- Some signs will have both types of evidence -> strongest identification
- Some signs will have one but not the other -> each method covers the other's blind spots

**Integration strategy:** Run both methods independently, then combine results. When both agree on a reading, confidence is highest. When they disagree, investigate why -- the disagreement itself is informative.

### 11.2 Iterative Decipherment Loop (PRD_ITERATIVE_DECIPHERMENT.md)

This PRD is a single pass of the identification step. The iterative decipherment PRD defines the full loop:

```
1. Run Kober triangulation -> identify N new signs
2. Add identified signs to anchor set (53 + N anchors)
3. Re-run P1 pipeline with expanded anchors
4. Re-run Kober triangulation with denser anchor coverage
5. Repeat until convergence (no new STRONG identifications)
```

Each iteration should identify additional signs because:
- More anchors -> more anchor alternation partners for remaining unknowns
- More anchors -> finer consonant row discrimination
- More anchors -> more vowel column evidence

The convergence criterion is: an iteration produces zero new STRONG identifications. At that point, the alternation graph's structural information has been fully exploited.

---

## 12. Risks and Mitigations

### Risk 1: Alternation Graph Too Dense for Consonant Row Separation

**Severity:** HIGH
**Description:** Mean degree 17.7 means each sign alternates with ~18 others. In a well-structured CV syllabary with 12 consonants and 5 vowels, a sign should alternate with at most 4 signs in its own row (same consonant, 4 other vowels) plus vowel-class alternations from initial position. The observed density is much higher than the theoretical maximum for pure within-row alternation, suggesting many alternation edges are noise or cross-row.
**Mitigation:** Weight suffix-position alternations heavily over initial-position alternations. Use the greedy consonant row assembly (27 rows, from `kober_vowel_analysis.py`) which has already produced consonant ARI = 0.615. Filter alternation pairs by weighted_stems >= 2 (stronger evidence only).

### Risk 2: Insufficient Unknown Signs in the Alternation Graph

**Severity:** MEDIUM
**Description:** Only 16 unknown signs have alternation evidence. The remaining ~60 unknown syllabograms have no alternation evidence at all (listed in `unassigned_signs` in P1 output). The method cannot reach these signs.
**Mitigation:** This is a known limitation, not a failure. The 16 reachable signs, if successfully identified, still unlock significant downstream vocabulary. For the unreachable signs, the Jaccard method and/or future corpus expansion are needed.

### Risk 3: LB Value Assumption Errors

**Severity:** LOW-MEDIUM
**Description:** Some Linear A signs may have different phonetic values than their Linear B counterparts. If an anchor sign has a wrong assumed value, the triangulation from that anchor will propagate the error.
**Mitigation:** The cross-validation in Gate 1 partially addresses this: if an anchor value is wrong, the leave-1-out test for THAT sign will fail, flagging it. Additionally, signs whose triangulated reading is inconsistent with multiple independent anchor chains are flagged as potential LA/LB divergence candidates.

### Risk 4: Circular Reasoning with P1 Grid

**Severity:** LOW
**Description:** The P1 grid was constructed using the same alternation data that triangulation uses. If the grid assignment is wrong, cross-referencing with it in Step 5 reinforces the error.
**Mitigation:** The triangulation algorithm should produce its reading hypotheses BEFORE consulting the P1 grid. The grid cross-reference is a post-hoc consistency check, not an input to the scoring. Readings that are strong from triangulation alone but inconsistent with the grid are MORE interesting, not less (they suggest the grid assignment for that sign is wrong).

### Risk 5: Overfitting to Alternation Noise

**Severity:** MEDIUM
**Description:** With 610 pairs and 69 signs, the alternation graph may contain false positive edges (pairs that pass the significance test but are not real same-consonant alternations). These would inject wrong consonant row evidence.
**Mitigation:** Use only pairs with weighted_stems >= 2. The strongest pairs (weighted_stems >= 4) alone provide sufficient evidence for the highest-degree signs. Report per-sign evidence breakdown so that identifications based on a single strong edge vs. many weak edges can be distinguished.

---

## 13. Corpus Budget

This PRD consumes no additional corpus data beyond what P1 already uses. The 610 alternation pairs and the grid assignments are pre-computed outputs of the P1 pipeline. The triangulation algorithm is purely analytical -- it operates on graph structure, not on raw corpus tokens.

There is no data split concern: the same alternation pairs are used for both grid construction (P1) and triangulation (this PRD). This is acceptable because the two analyses answer different questions (grid: "what are the abstract classes?" vs. triangulation: "what is this specific sign's reading?"). However, the held-out validation (Section 7) MUST use a proper held-out set (removed from both grid construction and triangulation) to avoid inflated accuracy.

---

## 14. Relationship to PhaiPhon (Legacy)

PhaiPhon 1-5 operated on a fundamentally different paradigm: external language comparison to identify Linear A's genetic affiliation. None of the PhaiPhon components attempted internal sign reading identification.

The closest PhaiPhon analog is PhaiPhon4's vowel inventory estimation (V=3.7 effective vowels), which provides a soft constraint on the number of vowel columns. This PRD uses V=5 (the triple-validated result from the current session), which is independent of PhaiPhon4's estimate.

Nothing from PhaiPhon 1-5 is reusable for this PRD. The approach is entirely new.

---

## 15. Implementation Priority

This PRD should be implemented BEFORE PRD_ITERATIVE_DECIPHERMENT.md because the iterative loop depends on having a working sign identification module. It can be implemented IN PARALLEL with PRD_JACCARD_SIGN_CLASSIFICATION.md since the two methods are independent.

**Estimated implementation effort:** 1-2 sessions.
- Session 1: Core triangulation algorithm + validation framework
- Session 2: Tuning, gate evaluation, integration with P1 pipeline

---

## 16. Key References

1. Kober, A. (1946). "Inflection in Linear Class B: 1 -- Declension." *AJA* 50(2): 268-276.
2. Kober, A. (1948). "The Minoan Scripts: Fact and Theory." *AJA* 52(1): 82-103.
3. Bennett, E.L. (1951). *The Pylos Tablets: A Preliminary Transcription.* Princeton UP.
4. Ventris, M. (1952). "Deciphering the Minoan Linear B Script." (*Work Notes* 1-20, personal distribution).
5. Chadwick, J. (1958). *The Decipherment of Linear B.* Cambridge UP. (Historical account of Kober's and Ventris's methods.)
6. Packard, D.W. (1974). *Minoan Linear A.* University of California Press. (Transfer probability of LB values to LA at 2:1 to 5:1 odds.)
7. Godart, L. and Olivier, J.-P. (1976-1985). *Recueil des inscriptions en lineaire A.* (GORILA, standard LA corpus.)
8. Younger, J.G. "Linear A Texts in Phonetic Transcription." (SigLA database, corpus source.)
