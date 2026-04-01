# PRD: Suffix-Derived Phonological Constraints

**Status:** Draft
**Depends on:** Pillar 1 (C-V grid, vowel/consonant classes), Pillar 2 (suffix inventory, paradigm table, segmented lexicon)
**Feeds into:** Pillar 5 (vocabulary resolution -- constraining unknown sign readings), iterative decipherment loop
**Date:** 2026-03-29
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Extract phonological constraints on unknown Linear A signs by analyzing their behavior in morphological suffix positions, using Pillar 2's 29 inflectional suffixes and 2 paradigm classes.

The core principle is Alice Kober's 1946 insight: when signs alternate in the same morphological slot, they share a consonant but differ in vowel (or vice versa). Pillar 1 already applies this principle to word-final positional alternations across the entire corpus. This PRD applies it specifically to **morphologically identified suffix positions**, which provides a different and complementary source of evidence.

The practical payoff is large. The session report (2026-03-29) discovered that 184 P2 stems are missing JUST ONE syllable from having a full phonetic reading. If suffix constraints can narrow each unknown sign to a handful of candidate readings (e.g., "this sign has consonant /t/ and one of 5 vowels"), those 184 stems become usable for SCA cognate matching -- a 5x increase in matchable vocabulary.

**Traced to README:** "Cognates are tools, not goals... Structure before content... Internal structural analysis (phonology, morphology) comes before any external language comparison."

---

## 2. Non-goals

- **No phonetic value assignment.** This module produces CONSTRAINTS on sign readings (e.g., "AB77 shares a consonant with AB59"), not definitive IPA labels. Final phonetic labeling remains Pillar 5's job.
- **No external language data.** All constraints derive from internal Linear A structure. Linear B values are used ONLY for soft validation (Section 8).
- **No re-implementation of P1 or P2.** We consume their outputs directly.
- **No semantic interpretation of suffix slots.** We do not claim "slot 41 is nominative." We only claim that signs filling the same slot share phonological properties.

---

## 3. Background: How This Differs from Pillar 1

A new Claude session reading this PRD needs to understand the distinction between P1's alternation detection and this module's suffix-based analysis, because they operate on different evidence and produce different constraint types.

### 3.1 What Pillar 1 does (alternation detector)

P1's alternation detector (`pillar1/alternation_detector.py`) finds pairs of sign-groups that share a common prefix but differ in their final 1-2 signs. For example, if the corpus contains words AB59-AB06-AB37 and AB59-AB06-AB57, then (AB37, AB57) is a "same-consonant candidate" because they alternate in the same word-final position.

P1 builds an affinity matrix from ALL such pairs across the corpus and uses spectral clustering to recover consonant classes (grid rows) and vowel classes (grid columns). The current P1 output (`results/pillar1_v5_output.json`) assigns each sign to one of 4 consonant classes and 5 vowel classes, with confidence scores.

**Limitation:** P1 treats all word-final alternations equally. It does not distinguish inflectional alternation (the suffix changes because the grammatical function changes) from accidental co-occurrence (two unrelated words happen to share a prefix). P1 compensates statistically (requiring multiple independent stems per alternation pair), but the signal is diluted.

### 3.2 What suffix constraints add

This module restricts attention to positions that P2 has independently identified as **morphological suffix slots** -- positions where the alternation is not accidental but structurally motivated. This provides:

1. **Higher-confidence same-consonant evidence.** If AB37 (ti) and AB57 (ja) both fill suffix slots in the same paradigm class, the evidence that they share a consonant is morphologically grounded, not just distributional. This is strictly stronger evidence than P1's corpus-wide alternation.

2. **Cross-paradigm same-vowel evidence.** P1's alternation detector only finds same-consonant pairs (signs that share a consonant row). Suffix analysis can also identify **same-vowel pairs**: if two paradigm classes both have a "slot that carries vowel V" (the same grammatical function expressed with different consonants), the signs filling those slots share a vowel column. P1 has no mechanism for this.

3. **Constraints on signs that P1 cannot reach.** P1's alternation detector requires at least 2 independent stems showing the same alternation pair. Some signs are too rare for P1 to detect but appear in well-attested suffix positions. The morphological context compensates for low frequency.

### 3.3 Independence of provenance

P1 operates on raw positional frequencies and bigram statistics -- purely distributional, no segmentation required. P2 operates on stem-suffix decomposition using MDL/BPE segmentation constrained by P1's phonotactics. This module uses P2's morphological output but derives constraints from suffix alternation patterns -- a different analytical lens.

The fact that P1 and this module use overlapping but different evidence means their constraints can be **cross-validated**: where they agree, confidence is high; where they disagree, investigation is warranted.

---

## 4. Inputs

### 4.1 From Pillar 2 (`results/pillar2_output.json`)

The P2 output provides the following data consumed by this module:

| Field | What this module uses it for |
|-------|------------------------------|
| `affix_inventory.suffixes[]` | The 29 inflectional suffixes (each a list of sign IDs with frequency, productivity, and paradigm class membership) |
| `paradigm_table.paradigms[]` | 2 paradigm classes with 91 and 6 slots respectively, including which signs fill each slot |
| `segmented_lexicon[]` | 787 segmented words (717 with suffixes), each with stem, suffix, and confidence |
| `diagnostics` | Corpus coverage: 787 words segmented, 29 inflectional / 35 derivational / 42 ambiguous suffixes |

**Key P2 statistics (from production output):**

The 29 inflectional suffixes, ranked by productivity (n_distinct_stems / 29):

| Rank | Sign(s) | Frequency | Distinct stems | Productivity |
|------|---------|-----------|----------------|--------------|
| 1 | AB37 | 35 | 29 | 1.000 |
| 2 | AB57 | 25 | 24 | 0.828 |
| 3 | AB60 | 27 | 22 | 0.759 |
| 4 | AB04 | 24 | 22 | 0.759 |
| 5 | AB59 | 22 | 22 | 0.759 |
| 6 | AB27 | 28 | 21 | 0.724 |
| 7 | AB73 | 22 | 21 | 0.724 |
| 8 | AB06 | 23 | 20 | 0.690 |
| 9 | AB77 | 27 | 17 | 0.586 |
| 10 | AB67 | 20 | 17 | 0.586 |
| 11 | AB26 | 26 | 16 | 0.552 |
| 12 | AB80 | 22 | 16 | 0.552 |
| 13 | AB53 | 19 | 16 | 0.552 |
| 14 | AB41 | 17 | 15 | 0.517 |
| 15 | AB07 | 22 | 14 | 0.483 |
| 16 | AB24 | 16 | 14 | 0.483 |
| 17 | AB09 | 18 | 13 | 0.448 |
| 18 | AB69 | 19 | 12 | 0.414 |
| 19 | AB51 | 14 | 12 | 0.414 |
| 20 | AB30 | 14 | 12 | 0.414 |
| 21 | AB65 | 12 | 11 | 0.379 |
| 22 | AB17 | 15 | 10 | 0.345 |
| 23 | AB01 | 15 | 10 | 0.345 |
| 24 | AB28 | 12 | 10 | 0.345 |
| 25 | AB81 | 10 | 10 | 0.345 |
| 26 | AB56 | 10 | 10 | 0.345 |
| 27 | AB39 | 10 | 10 | 0.345 |
| 28 | AB58 | 12 | 9 | 0.310 |
| 29 | AB02 | 12 | 9 | 0.310 |

Paradigm class 0 has 384 member stems across 91 slots. Paradigm class 1 has 15 members across 6 slots. The mean paradigm completeness is 12.6% (highly sparse, expected for a small corpus).

### 4.2 From Pillar 1 (`results/pillar1_v5_output.json`)

| Field | What this module uses it for |
|-------|------------------------------|
| `grid.assignments[]` | Each sign's consonant class (0-3) and vowel class (0-4) with confidence |
| `vowel_inventory.signs[]` | The 5 identified pure vowel signs (AB08, AB38, AB28, AB61, AB10) |
| `grid.consonant_count` (4), `grid.vowel_count` (5) | Grid dimensions for constraint alignment |

### 4.3 From corpus (`data/sigla_full_corpus.json`)

Sign inventory metadata: which signs have known Linear B readings (tier 1), which are undeciphered (tier 3). This determines which signs are "unknown" targets for constraint generation.

---

## 5. Approach

### 5.1 Step 1: Build Suffix Alternation Sets

**Goal:** For each paradigm class, identify which suffix signs alternate in the same morphological context -- i.e., which signs appear as single-sign suffixes attached to the same set of stems.

**Algorithm:**

1. From P2's paradigm table, extract all single-sign suffix slots. Multi-sign suffixes (e.g., AB06+AB41, AB53+AB57) are compound suffixes -- their individual signs are NOT in suffix-alternation positions and are excluded from this step. They are analyzed separately in Step 4.

2. For each pair of single-sign suffixes (S_i, S_j) within the same paradigm class, compute the **stem overlap**: the number of stems that are attested with BOTH S_i and S_j.

   ```
   overlap(S_i, S_j) = |stems(S_i) ∩ stems(S_j)|
   ```

3. Pairs with overlap >= 2 (at least 2 independent stems showing both suffixes) form a **suffix alternation set** -- a group of signs that serve the same morphological function on the same stems, differing only in the inflectional category they express.

4. By Kober's principle, signs within a suffix alternation set **share a consonant** (they represent the same CV syllable with different vowels) OR they are pure vowels serving as endings.

**Output:** A list of suffix alternation sets, each containing 2+ signs with their pairwise stem overlap counts.

**Example of the expected reasoning:**

In Linear B, the nominative singular suffix -o (AB70) and the genitive singular suffix -jo (AB36-AB70) share the stem ko-no (ko-no-so NOM vs ko-no-si-jo GEN, Knossos). Signs that alternate in suffix position on the same stem share consonant structure. If P2 finds that AB37 and AB57 and AB60 all suffix the same set of stems, those three signs share a consonant row -- they are Ca, Ce, and Co for some consonant C.

### 5.2 Step 2: Derive Same-Consonant Constraints

**Goal:** From the suffix alternation sets, produce pairwise "same-consonant" constraints compatible with P1's grid.

**Algorithm:**

1. For each suffix alternation set {S_1, S_2, ..., S_k}:
   - Emit pairwise constraints: (S_i, S_j, "same_consonant", evidence=overlap(S_i, S_j))

2. Cross-reference with P1's grid assignments:
   - If P1 already places S_i and S_j in the same consonant class: **AGREEMENT** -- confidence boosted.
   - If P1 places them in different consonant classes: **CONFLICT** -- flag for investigation. Possible explanations: (a) P1's clustering is wrong for these signs, (b) P2's segmentation is wrong (the "suffix" is actually part of the stem), (c) the alternation is not same-consonant (it is a suppletive paradigm or derivational, not inflectional).
   - If P1 has no assignment for one or both signs (sign too rare): **NEW CONSTRAINT** -- this module provides information P1 could not.

3. Compute a combined confidence score:
   ```
   confidence_suffix = sigmoid(overlap - 2)  # Higher overlap = more confident
   confidence_combined = 1 - (1 - confidence_p1) * (1 - confidence_suffix)
   ```
   where confidence_p1 is P1's grid assignment confidence for the pair being in the same consonant class.

**Output:** A constraint table: (sign_A, sign_B, constraint_type="same_consonant", evidence_count, source="suffix_alternation", confidence, agrees_with_p1=True/False/NA).

### 5.3 Step 3: Derive Same-Vowel Constraints (Cross-Paradigm)

**Goal:** Identify signs that share a vowel class by comparing parallel morphological slots across paradigm classes.

**Algorithm:**

This step is more speculative and depends on having 2+ paradigm classes with identifiable "corresponding" slots. P2 currently finds 2 paradigm classes (class 0 with 91 slots, class 1 with 6 slots).

1. For each slot in paradigm class 1, check if there is a "corresponding" slot in class 0 -- a slot whose stems show similar distributional behavior (same inscription types, similar frequency profile). The correspondence criterion is:
   ```
   jaccard(inscription_types(slot_A), inscription_types(slot_B)) > 0.5
   AND frequency_ratio(slot_A, slot_B) in [0.25, 4.0]
   ```

2. If corresponding slots are found: the single-sign suffixes in corresponding slots across different paradigm classes express the **same grammatical function** but with different consonants (different declension classes). By Kober's column principle, they share a vowel.

3. Emit pairwise constraints: (S_i from class 0, S_j from class 1, "same_vowel", evidence="cross_paradigm_correspondence").

**Caution:** This step will likely produce very few constraints given that class 1 has only 15 members and 6 slots. It is included for completeness and becomes more valuable if P2 is rerun with finer paradigm granularity in the future.

### 5.4 Step 4: Analyze Compound Suffixes

**Goal:** Extract constraints from multi-sign suffixes (e.g., AB06+AB41, AB53+AB57, AB73+AB06).

**Algorithm:**

P2's paradigm table includes compound suffix slots (e.g., slot 14: AB06+AB41, slot 57: AB53+AB57). These are important because:

1. **Head-modifier structure.** In a CV syllabary, a compound suffix like AB53+AB57 likely decomposes as a "base suffix" (AB53) plus a "secondary suffix" (AB57). If AB53 alone is also an attested suffix (it is: slot 53, freq 16), then AB57 in position 2 of the compound modifies the base suffix. This constrains AB57 as a morphological operator (possibly a plural marker, a case stacker, etc.).

2. **Shared-head analysis.** Compound suffixes that share the same first sign (e.g., AB06+AB41 and AB06+AB69 and AB73+AB06) group by their head. The varying second signs are in alternation with each other, producing same-consonant constraints on the second position.

3. **Shared-tail analysis.** Compound suffixes that share the same last sign but differ in the first (e.g., AB07+AB60 and AB67+AB60) produce same-consonant constraints on the first position.

**Algorithm:**

1. Extract all compound (multi-sign) suffix slots from the paradigm table.
2. Group by shared first sign (head) -- the varying tails are a suffix alternation set.
3. Group by shared last sign (tail) -- the varying heads are a suffix alternation set.
4. Apply the same-consonant constraint logic from Step 2 to each group.

### 5.5 Step 5: Propagate Constraints to Unknown Signs

**Goal:** For each undeciphered sign that appears in suffix positions, narrow its possible readings using the accumulated constraints.

**Algorithm:**

1. Start with P1's grid assignment for each sign: consonant class C in {0,1,2,3}, vowel class V in {0,1,2,3,4}.

2. Apply suffix constraints:
   - Same-consonant constraints: if sign X is constrained to share a consonant with sign Y, and Y has a known LB reading (e.g., AB37 = ti, consonant /t/), then X has consonant /t/.
   - Same-vowel constraints: similarly propagate vowel identity.
   - Each constraint narrows the candidate set for the unknown sign.

3. Cross-reference with the `sign_to_ipa.json` mappings (53 known signs as of the session report). For each unknown sign:
   - Start with 4 * 5 = 20 possible grid cells.
   - P1 grid assignment narrows to 1 cell (if confident) or a few cells.
   - Suffix constraints may independently confirm or conflict with P1's assignment.
   - Known LB readings of constraining signs translate abstract grid classes to actual phonetic values.

4. Output for each unknown sign: a ranked list of candidate readings with confidence scores.

**Constraint propagation math:**

For an unknown sign U with prior P1 assignment (C_p1, V_p1, conf_p1):

```
P(U = Ca_x Vo_y) = P_p1(C=x) * P_p1(V=y) * prod(P_suffix(constraint_k | C=x, V=y))
```

where each suffix constraint is a likelihood term:
- same_consonant(U, S) where S has known C=c: P(constraint | C=c) = 1.0, P(constraint | C != c) = epsilon
- same_vowel(U, S) where S has known V=v: analogous

Normalize to get a posterior distribution over the 20 grid cells.

### 5.6 Step 6: Identify Recoverable Stems

**Goal:** Re-tally the 184 one-sign-missing stems from the session report to see how many now have full phonetic readings (or constrained-enough readings for SCA matching).

**Algorithm:**

1. Load the segmented lexicon from P2.
2. For each stem, check how many of its signs now have constrained readings (known LB reading OR suffix-constrained to <= 3 candidate readings).
3. A stem is "SCA-matchable" if ALL its signs have constrained readings -- the combinatorial explosion of matching all possible readings is tractable (e.g., 3 candidates per sign, 3-sign stem = 27 possible readings, easily searched).
4. Report: how many of the 184 one-sign-missing stems became matchable, and how many additional stems (previously missing 2+ signs) crossed the threshold.

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `suffix_constraint_extractor.py` | Steps 1-4: build alternation sets, derive same-consonant and same-vowel constraints, analyze compounds | P2 output JSON + P1 output JSON | Constraint table |
| `constraint_propagator.py` | Step 5: propagate constraints to unknown signs, produce candidate readings | Constraint table + sign_to_ipa.json + corpus sign inventory | Per-sign candidate readings |
| `stem_recovery_tally.py` | Step 6: re-tally matchable stems | Candidate readings + P2 segmented lexicon | Recovery statistics |
| `lb_validation.py` | Gate 1: validate on Linear B suffix patterns | Linear B suffix data | Agreement score |
| `pipeline.py` | Orchestrator | Config YAML | Runs all steps, produces JSON output |

### 6.1 Output Schema

```json
{
  "metadata": {
    "module": "suffix_constraints",
    "version": "1.0.0",
    "pillar1_hash": "<SHA-256 of P1 output>",
    "pillar2_hash": "<SHA-256 of P2 output>",
    "timestamp": "ISO-8601"
  },

  "suffix_alternation_sets": [
    {
      "set_id": 0,
      "paradigm_class": 0,
      "signs": ["AB37", "AB57", "AB60"],
      "pairwise_overlaps": [
        {"sign_a": "AB37", "sign_b": "AB57", "overlap": 8},
        {"sign_a": "AB37", "sign_b": "AB60", "overlap": 6},
        {"sign_a": "AB57", "sign_b": "AB60", "overlap": 5}
      ],
      "constraint_type": "same_consonant",
      "confidence": 0.92
    }
  ],

  "constraints": [
    {
      "sign_a": "AB37",
      "sign_b": "AB57",
      "type": "same_consonant",
      "source": "suffix_alternation",
      "evidence_count": 8,
      "confidence": 0.88,
      "agrees_with_p1": true,
      "p1_consonant_a": 0,
      "p1_consonant_b": 0
    }
  ],

  "sign_candidates": [
    {
      "sign_id": "AB77",
      "is_unknown": true,
      "p1_assignment": {"consonant_class": 0, "vowel_class": 2, "confidence": 1.0},
      "suffix_constraints": [
        {"constraining_sign": "AB37", "type": "same_consonant", "confidence": 0.88}
      ],
      "candidate_readings": [
        {"consonant": "t", "vowel": "i", "probability": 0.35},
        {"consonant": "t", "vowel": "e", "probability": 0.30}
      ],
      "n_candidates": 2
    }
  ],

  "stem_recovery": {
    "total_stems": 787,
    "previously_matchable": 37,
    "newly_matchable": 0,
    "one_sign_missing_before": 184,
    "one_sign_missing_after": 0,
    "improvement_ratio": 0.0
  },

  "diagnostics": {
    "total_alternation_sets": 0,
    "total_constraints_emitted": 0,
    "constraints_agreeing_with_p1": 0,
    "constraints_conflicting_with_p1": 0,
    "constraints_new_for_p1": 0,
    "unknown_signs_constrained": 0
  }
}
```

(The zeros above are placeholders -- actual values to be filled by the implementation.)

---

## 7. Go/No-Go Gates

### Gate 1: Linear B Suffix Validation (CRITICAL)

**Test:** Apply the suffix constraint extraction algorithm to a Linear B corpus (where suffix phonetic values are KNOWN) and check whether the extracted same-consonant constraints are correct.

**Data source:** Linear B has well-documented inflectional suffixes. Key examples from Mycenaean Greek:

- Nominative -o (AB70), genitive -o-jo (AB70-AB36), dative -o-i (AB70-AB28): these three single-sign suffixes alternate in the same paradigm. AB70 (/o/) is a pure vowel, so these three slots do NOT share a consonant -- they share a vowel. The algorithm must detect this correctly (same-vowel constraint, not same-consonant).
- First declension: -a (AB08), -a-o (AB08-AB70), -a-i (AB08-AB28): AB08 is a pure vowel. Same pattern.
- Third declension: -e (AB38), -e-o (AB38-AB70): AB38 is a pure vowel.

**Expected result:** The algorithm correctly identifies pure vowel suffixes as same-VOWEL alternation sets (not same-consonant). For CV suffixes (e.g., -ti vs -to), the algorithm correctly identifies them as same-consonant sets. Agreement with known Linear B phonetic values >= 80%.

**On failure:** The algorithm is confusing vowel alternation with consonant alternation. Root cause: not accounting for pure vowel signs identified by P1. Fix: exclude pure vowel signs from same-consonant constraint sets; create a separate "vowel suffix" category.

### Gate 2: Constraint-P1 Agreement (HIGH)

**Test:** Of all suffix-derived same-consonant constraints, what fraction agrees with P1's grid assignments?

**Expected result:** Agreement >= 70%. (Lower threshold than Gate 1 because P1's grid uses only 4 consonant classes, so some real same-consonant pairs may be split across P1's coarser clustering.)

**On failure (agreement < 50%):** Either P2's segmentation is producing spurious suffixes, or P1's grid is too coarse. Investigate the disagreeing pairs individually. If most disagreements involve low-confidence P1 assignments (confidence < 0.5), the suffix constraints are likely correct and should override P1.

### Gate 3: Non-Trivial Constraint Count (HIGH)

**Test:** The module must produce at least 5 suffix-derived constraints that are NOT already present in P1's grid.

**Rationale:** If the module only rediscovers what P1 already found, it adds no value. The justification for this module is that it provides constraints P1 cannot -- either on signs P1 lacks evidence for, or higher-confidence constraints on signs P1 assigned with low confidence.

**Expected result:** >= 5 new constraints (signs constrained by suffix analysis that P1 assigned with confidence < 0.5 or did not assign at all).

**On failure:** The suffix data is redundant with P1's alternation data. This is not a code bug -- it means the morphological structure does not provide additional phonological signal beyond what positional alternation already captures. In this case, the module's value is limited to cross-validation of P1.

### Gate 4: Stem Recovery Improvement (MEDIUM)

**Test:** The number of SCA-matchable stems (stems where all signs have constrained-enough readings) increases by at least 10% after applying suffix constraints.

**Expected result:** Previously matchable stems = 37 (from session report). Target: >= 41 matchable stems (4+ new).

**On failure:** The constraints are not strong enough to push unknown signs below the 3-candidate-reading threshold. Consider: (a) relaxing the threshold to 5 candidates, (b) combining suffix constraints with other evidence sources (bigram constraints, ideogram co-occurrence from P4).

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Paradigm sparsity collapses alternation sets.** P2's mean paradigm completeness is 12.6%, meaning most stems appear with only 1 suffix. This means very few stem pairs are attested with BOTH suffix S_i and S_j, yielding near-zero overlaps. | HIGH | HIGH | Lower the overlap threshold to 1 (accept single-stem evidence with lower confidence). Also aggregate across the full segmented lexicon, not just within paradigm class boundaries -- two stems not assigned to the same paradigm class may still share suffixes. |
| **P2's single mega-class absorbs all signal.** Paradigm class 0 has 384 members and 91 slots. This is likely a single amorphous class rather than a true paradigm -- the Jaccard threshold was too permissive. All suffixes are in this class, so cross-paradigm (same-vowel) analysis has minimal data. | HIGH | HIGH | For same-consonant constraints, this is not a problem (we compare suffixes within the class). For same-vowel constraints, re-run P2 with a tighter Jaccard threshold (0.5 instead of 0.3) to produce finer-grained paradigm classes. Design the module to work with any number of paradigm classes. |
| **Pure vowel suffixes contaminate same-consonant sets.** If a pure vowel sign (e.g., AB08 = /a/) serves as a suffix, it should NOT be placed in a same-consonant set with CV suffixes. P1's vowel inventory identifies 5 pure vowels, but some may be missed. | MEDIUM | MEDIUM | Before building alternation sets, exclude signs from P1's vowel inventory. Also exclude signs with very high initial-position frequency (P1's vowel identification criterion). Run Gate 1 (LB validation) specifically to catch this failure mode. |
| **Compound suffixes are misanalyzed.** P2 may have identified single-morpheme signs as compound suffixes (over-segmentation) or missed compound suffixes (under-segmentation). | MEDIUM | MEDIUM | Weight compound suffix constraints lower (0.5x multiplier on confidence). Validate by checking whether compound suffix patterns mirror known Linear B compound suffix patterns. |
| **Circular reasoning with P1.** P2's segmentation is constrained by P1's phonotactics. If P1's grid is wrong, P2's suffixes are wrong, and suffix-derived constraints would reinforce the error. | MEDIUM | LOW | The cross-validation logic in Step 2 explicitly flags P1 conflicts. If > 30% of suffix constraints conflict with P1, this signals a systemic problem rather than individual errors, and the module should HALT with a diagnostic report rather than emit conflicting constraints. |
| **Too few unknown signs in suffix positions.** If most suffix signs already have known LB readings, the module constrains signs that are already known -- providing validation but no new information. | LOW | MEDIUM | Quantify upfront: how many of the 29 inflectional suffix signs lack LB readings? If < 5, the module's primary value is cross-validation rather than new discovery. Still valuable but with lower practical impact on stem recovery. |

---

## 9. Corpus Budget

This module consumes the **same corpus data** as P1 and P2 -- it does not require additional corpus splits. It operates on P1 and P2's output JSON files, not on the raw corpus directly.

The only new data requirement is a **Linear B suffix corpus** for Gate 1 validation. This can be constructed from published Mycenaean Greek grammars (e.g., Ventris & Chadwick 1973, "Documents in Mycenaean Greek") by extracting attested inflectional suffixes and their paradigm patterns. Estimated size: 30-50 suffix patterns across 3-5 declension/conjugation classes.

---

## 10. Relationship to PhaiPhon (legacy)

PhaiPhon3-5 operated on phonetic matching between Linear A and candidate languages. It did not use morphological structure at all -- suffixes were treated as opaque sequences of phonemes to be matched holistically.

This module takes the opposite approach: suffixes are structural objects whose internal phonological relationships constrain sign readings. No PhaiPhon code is reusable here. The only PhaiPhon output that feeds in indirectly is PhaiPhon4's vowel count estimate (V~3.7), which is consistent with but independent from P1's V=5 analysis.

---

## 11. Integration with the Iterative Decipherment Loop

The suffix constraint module is designed to plug into the iterative loop described in the README:

```
P1 grid  -->  P2 suffixes  -->  SUFFIX CONSTRAINTS (this module)
    |                                    |
    v                                    v
P1 grid (refined)  <--  more constrained sign readings
    |                                    |
    v                                    v
P2 suffixes (refined)  -->  more matchable stems
    |                                    |
    v                                    v
P5 cognate matching  -->  tentative phonetic values
    |                                    |
    v                                    v
   Confirm/revise P1 grid with new evidence
```

Specifically:

1. **This module runs AFTER P1 v5 and P2 v1.** It consumes their outputs.
2. **Its output feeds P5** by expanding the set of matchable stems (stems with constrained-enough readings for SCA search).
3. **P5 results feed back** by tentatively assigning phonetic values to matched stems, which can be used to refine P1's grid (e.g., if P5 finds that stem AB26-AB77 matches Luwian /ru-ti/, this confirms AB77 has consonant /t/).
4. **The refined P1 grid can be used to re-run P2** with tighter constraints, producing better suffixes, which produce better suffix constraints -- a virtuous cycle.

The module must therefore be **idempotent and re-runnable**: given new P1/P2 outputs, it produces updated constraints without manual intervention.

---

## 12. Key Files

| File | Description |
|------|-------------|
| `results/pillar1_v5_output.json` | P1 output: C-V grid, vowel inventory, phonotactics |
| `results/pillar2_output.json` | P2 output: segmented lexicon, suffix inventory, paradigm table |
| `pillar1/alternation_detector.py` | P1's alternation detection (for understanding what it already does) |
| `pillar1/grid_constructor.py` | P1's spectral clustering grid construction |
| `pillar2/affix_extractor.py` | P2's suffix extraction with productivity scoring |
| `pillar2/paradigm_inducer.py` | P2's paradigm induction via Jaccard clustering |
| `data/sigla_full_corpus.json` | Raw Linear A corpus (879 inscriptions, 1552 words) |
| `STANDARDS_AND_PROCEDURES.md` | Project standards, PRD template, axioms |
| `docs/logs/2026-03-29-to-04-01-full-session-report.md` | Session report with P2 phonetic tally discovery (184 one-sign-missing stems) |
