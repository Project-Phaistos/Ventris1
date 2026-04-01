# PRD: Iterative Decipherment Loop

**Status:** Draft
**Depends on:** Pillar 1 (phonological grid), Pillar 2 (morphological segmentation), Pillar 4 (semantic anchors), Pillar 5 (SCA matching infrastructure)
**Feeds into:** All pillars (feedback loop refines P1 grid, unlocks P2 stems, informs P5 vocabulary)
**Date:** 2026-03-29
**Authors:** Alvin / Claude (design session)

---

## Background for New Sessions

This PRD is part of the **Ventris1** project, which deciphers Linear A (the undeciphered Minoan script, c. 1800-1450 BCE) through five structural pillars:

| Pillar | Name | What it does | Current state |
|--------|------|-------------|---------------|
| P1 | Phonological Engine | Discovers the sound system from distributional evidence; produces a consonant-vowel grid | **V=5 grid complete**: 4 consonant classes x 5 vowel classes, Kober-anchored, ARI=0.615 vs LB, 95% vowel accuracy on 20 known signs |
| P2 | Morphological Decomposition | Segments sign-groups into stems + affixes | **787 entries**, 106 suffixes, validated on Latin known-answer |
| P3 | Distributional Grammar | Induces word classes and syntax | 1 dominant cluster + 6 singletons; functional words identified |
| P4 | Semantic Anchoring | Constrains meanings from ideograms, numerals, formulae | 34 high-confidence anchors, 106 low-confidence |
| P5 | Multi-Source Vocabulary Resolution | Searches candidate languages for cognates | SCA infrastructure built; constrained search shows 3.2x enrichment above chance |

### The Fundamental Bottleneck

Only **53 of 142 syllabograms** have known phonetic values (transferred from Linear B). This produces stems of 1-2 syllables (2-4 SCA characters) -- too short for cross-linguistic matching by ANY method. After 11 approaches attempted and documented in `docs/logs/2026-03-29-to-04-01-full-session-report.md`, the root cause is clear: **data sparsity, not algorithm choice**.

### The Leverage Point

**184 P2 stems are missing just 1 syllable.** If we can constrain each unknown sign to 2-5 possible readings (using P1's grid), we can enumerate all possibilities and test them. P1's Kober-anchored grid already constrains unknown signs: each grid cell (consonant class x vowel class) maps to a small set of candidate CV readings.

### Why a Loop Works

Sign identification and cognate matching are NOT separate problems -- they are a **feedback loop**:

```
Unknown sign constrained by grid  -->  Enumerate readings for partial stems
         ^                                        |
         |                                        v
Accept converging evidence     <--  SCA-match against candidate lexicons
         |
         v
Newly-known sign unlocks MORE stems  -->  repeat
```

Each iteration makes the next one more powerful: every new sign reading unlocks multiple stems (because signs recur), and every new cognate match provides evidence for the sign reading that produced it.

### Key Reference Files

| File | Description |
|------|-------------|
| `results/pillar1_v5_output.json` | P1 grid: 4C x 5V, 69 signs assigned, Kober-anchored vowels |
| `results/pillar2_output.json` | P2 segmented lexicon: 787 entries, 184 missing exactly 1 syllable |
| `data/sign_to_ipa.json` | 53 known sign-to-IPA mappings (LB transfer) |
| `data/sigla_full_corpus.json` | SigLA corpus: 879 inscriptions, 1552 words, 170 unique syllabograms |
| `pillar5/scripts/constrained_sca_search.py` | Existing constrained search (single-pass, no iteration) |
| `pillar5/scripts/sca_cognate_search.py` | SCA distance + permutation null infrastructure |
| `../ancient-scripts-datasets/data/training/lexicons/` | 1,177 lexicon files; 18 candidate languages used (hit, xld, xlc, xrr, phn, uga, elx, xur, peo, xpg, ave, akk, grc, lat, heb, arb, sem-pro, ine-pro) |
| `docs/logs/2026-03-29-to-04-01-full-session-report.md` | Full session report documenting 11 failed/partial approaches |
| `docs/logs/2026-03-27-pillar-weakness-audit.md` | Honest weakness audit of all 5 pillars |
| `docs/logs/2026-03-29-constrained-search-approach.md` | Constrained search approach design document |
| `STANDARDS_AND_PROCEDURES.md` | Project standards: 3-tier testing, data provenance, adversarial audits |

### Project Axioms (Non-Negotiable)

1. **No single-cognate assumption.** Linear A is a chimaera language with multiple influences. Architecture must allow mixed provenance.
2. **Structure before content.** Internal structural analysis comes before external language comparison.
3. **Cognates are tools, not goals.** Cross-language matching serves vocabulary resolution, never proving genetic relationships.
4. **Falsifiable gates.** Every component has go/no-go gates with concrete pass/fail criteria.
5. **Independent phonological discovery.** LB values are soft validation, not input. However, at this stage P1 has already been validated (ARI=0.615) and LB transfer values are used as the known-sign baseline.

---

## 1. Objective

Build an iterative feedback loop that simultaneously **identifies unknown signs** and **finds cognate matches** by exploiting the constraint that each sign must have a SINGLE consistent reading across all stems where it appears.

The loop takes partially-phonetic stems (stems where some signs have known readings and some do not), enumerates constrained possible readings for the unknown signs (using P1's grid), tests each reading against candidate language lexicons (using SCA distance), and accepts new sign readings when evidence **converges** across multiple independent stems.

Each accepted sign reading feeds back into the system, converting previously-unsearchable stems into searchable ones, enabling the next iteration.

**Traced to README:** "Cognates are tools, not goals" -- here, cognate matches are the EVIDENCE used to constrain sign readings, and sign readings are the PRODUCT that feeds downstream vocabulary resolution.

---

## 2. Non-Goals

- **No single-language verdict.** The loop does NOT determine which language Linear A "is." Different stems may match different languages. This is expected under the chimaera hypothesis.
- **No morphological re-analysis.** Stems come from P2's segmentation. The loop does not re-segment.
- **No grid re-computation mid-loop.** The P1 grid is fixed input. Future work may close the outer loop (accepted readings improve the grid), but this PRD covers only the inner loop.
- **No semantic scoring.** The current implementation uses only phonological (SCA) distance. Semantic constraints from P4 are a future enhancement (see Section 8, Risk R5).
- **No probabilistic sign-value estimation.** We accept or reject candidate readings via hard evidence thresholds, not Bayesian posterior distributions over sign values. Bayesian approaches are a potential future refinement but add complexity that is premature at this stage.
- **No automated corpus re-reading.** Accepted sign readings are recorded as hypotheses, not written back into `sign_to_ipa.json` automatically. Human review gates each promotion.

---

## 3. Inputs

### 3.1 From Pillar 1: Phonological Grid

**File:** `results/pillar1_v5_output.json`

| Field | Use | Provenance |
|-------|-----|------------|
| `grid.assignments[].sign_id` | Identifies which grid cell an unknown sign occupies | INDEPENDENT (spectral clustering on alternation graph) |
| `grid.assignments[].vowel_class` | Constrains the vowel of the unknown sign to one of {a, e, i, o, u} | INDEPENDENT_VALIDATED (Kober-anchored, 95% accuracy on 20 known signs) |
| `grid.assignments[].consonant_class` | Groups signs into consonant classes (currently 4 classes, class 0 dominant) | INDEPENDENT (ARI=0.615 vs LB) |
| `grid.assignments[].confidence` | Filters low-confidence assignments | INDEPENDENT |
| `grid.vowel_count` | 5 (validated via triple cross-reference: LB transfer, Kober alternations, Jaccard substitutability) | INDEPENDENT_VALIDATED |
| `grid.consonant_count` | 4 (CI=[3,5]) | INDEPENDENT |

**How constraints are derived:** For each unknown sign assigned to grid cell (C_x, V_y), the candidate readings are the set of CV syllables where:
- The vowel is `VC_TO_VOWEL[V_y]` (one of a/e/i/o/u)
- The consonant is drawn from the set of consonants observed among KNOWN signs in the SAME vowel class

This narrows each unknown from ~50+ possible readings down to **2-5 candidates** per sign.

**Current constraint quality:** Vowel class assignment is reliable (95% accuracy). Consonant class assignment is weaker -- class 0 contains 91% of signs. This means consonant constraints provide minimal discrimination in the current grid. The loop must work primarily from vowel constraints, with consonant agreement as a secondary signal.

### 3.2 From Pillar 2: Segmented Lexicon

**File:** `results/pillar2_output.json`

| Field | Use | Provenance |
|-------|-----|------------|
| `segmented_lexicon[].segmentation.stem` | List of sign IDs forming each stem | INDEPENDENT (suffix-strip, validated on Latin) |
| `segmented_lexicon[].frequency` | Prioritizes high-frequency stems (more attestations = more cross-validation opportunities) | INDEPENDENT |
| `segmented_lexicon[].word_sign_ids` | Full sign-group for context | INDEPENDENT |

**Key statistics:**
- 787 total segmented entries
- 184 stems missing exactly 1 syllable (the primary search pool)
- 37 stems fully phonetic (baseline for validation)
- Remaining stems missing 2+ syllables (future iterations only)

### 3.3 From Pillar 4: Semantic Anchors (Optional Enhancement)

**File:** `results/pillar4_output.json`

Not used in the core loop algorithm (see Non-Goals), but available for future semantic filtering:
- 34 high-confidence anchors with constrained semantic fields
- If a stem has a P4 anchor, cognate matches can be filtered to semantically compatible entries

### 3.4 Known Sign Readings

**File:** `data/sign_to_ipa.json`

53 syllabograms with established IPA values from Linear B transfer. These are the "known" signs that make partial stems searchable. Every iteration potentially adds to this set.

### 3.5 Candidate Language Lexicons

**Directory:** `../ancient-scripts-datasets/data/training/lexicons/`

18 candidate languages with IPA and SCA columns:

| Code | Language | Entries | Relevance |
|------|----------|---------|-----------|
| hit | Hittite | ~800 | Anatolian, Bronze Age contemporary |
| xld | Lydian | ~700 | Anatolian |
| xlc | Lycian | ~400 | Anatolian |
| xrr | Eteocretan | ~100 | Same island, possible substrate |
| phn | Phoenician | ~300 | Semitic, Levantine trade |
| uga | Ugaritic | ~500 | Semitic, Bronze Age |
| elx | Elamite | ~340 | Isolate, Near Eastern |
| xur | Urartian | ~600 | Hurro-Urartian |
| peo | Old Persian | ~200 | Indo-Iranian |
| xpg | Phrygian | ~100 | Paleo-Balkan |
| ave | Avestan | ~700 | Indo-Iranian |
| akk | Akkadian | ~600 | Semitic, lingua franca |
| grc | Ancient Greek | ~800 | Contact language, LB substrate |
| lat | Latin | ~1000 | IE control (expected weak match) |
| heb | Hebrew | ~500 | Semitic |
| arb | Arabic | ~500 | Semitic control |
| sem-pro | Proto-Semitic | ~300 | Reconstructed |
| ine-pro | Proto-Indo-European | ~400 | Reconstructed |

**Provenance:** All lexicons sourced from peer-reviewed databases (NorthEuraLex, IDS, ABVD, eDiAna, IDS, eCUT/ORACC) via the dual-agent adversarial extraction pipeline documented in `STANDARDS_AND_PROCEDURES.md` Section 7.

### 3.6 Corpus Context

**File:** `data/sigla_full_corpus.json`

- `sign_inventory`: Maps AB codes to reading names (e.g., AB08 -> "a", AB59 -> "ta")
- Used to bridge P1 sign IDs to P2 readings to `sign_to_ipa.json` IPA values

---

## 4. Outputs (Interface Contract)

### 4.1 Per-Iteration Output

```json
{
  "iteration": 1,
  "timestamp": "2026-MM-DDTHH:MM:SSZ",
  "config_hash": "<sha256>",
  "input_known_signs": 53,
  "input_searchable_stems": 184,
  "comparisons_performed": 11040,
  "results": {
    "sign_candidates": [
      {
        "sign_id": "AB56",
        "grid_cell": {"consonant_class": 0, "vowel_class": 3},
        "candidate_readings": ["po", "do", "no", "ro"],
        "evidence": [
          {
            "stem_ids": ["AB59", "AB56", "AB08"],
            "stem_reading": "ta-po-a",
            "best_match": {
              "language": "grc",
              "word": "...",
              "ipa": "...",
              "sca_distance": 0.167,
              "p_value_analytical": 0.003,
              "gloss": "..."
            }
          }
        ],
        "n_stems_supporting": 5,
        "n_stems_contradicting": 1,
        "consistency_ratio": 0.833,
        "best_reading": "po",
        "verdict": "ACCEPT" | "PROVISIONAL" | "INSUFFICIENT" | "CONTRADICTORY"
      }
    ],
    "cognate_hypotheses": [
      {
        "la_stem": "ta-po-a",
        "la_sign_ids": ["AB59", "AB56", "AB08"],
        "match_language": "grc",
        "match_word": "...",
        "match_ipa": "...",
        "sca_distance": 0.167,
        "p_value": 0.003,
        "semantic_compatibility": null,
        "depends_on_sign_readings": ["AB56=po"]
      }
    ]
  },
  "summary": {
    "signs_accepted": 2,
    "signs_provisional": 5,
    "signs_insufficient": 40,
    "signs_contradictory": 3,
    "new_searchable_stems": 28,
    "cumulative_known_signs": 55,
    "convergence_metric": 0.04
  }
}
```

### 4.2 Cross-Iteration Summary

```json
{
  "total_iterations": 4,
  "convergence_history": [0.04, 0.02, 0.005, 0.001],
  "cumulative_accepted_signs": [2, 5, 6, 6],
  "cumulative_searchable_stems": [212, 278, 295, 295],
  "final_sign_readings": {
    "AB56": {"reading": "po", "confidence": "ACCEPTED", "iteration_accepted": 1, "n_supporting_stems": 5},
    "AB118": {"reading": "po", "confidence": "ACCEPTED", "iteration_accepted": 1, "n_supporting_stems": 3}
  },
  "kill_criteria_triggered": false,
  "termination_reason": "convergence"
}
```

### 4.3 Consumers

| Consumer | What they use | Why |
|----------|--------------|-----|
| P1 (future outer loop) | Accepted sign readings | Validate/refine grid assignments |
| P2 | Newly phonetic stems | Re-analyze morphological patterns with richer data |
| P5 | Cognate hypotheses | Feed into vocabulary strata detection |
| Human reviewer | Full evidence chains | Gate promotion from PROVISIONAL to ACCEPTED |

---

## 5. Algorithm

### Step A: Initialize Constraint Tables

**Input:** P1 grid assignments, known sign-to-IPA mappings, P2 segmented lexicon.

**Process:**
1. Load the P1 grid. For each vowel class V_y (0=a, 1=e, 2=i, 3=o, 4=u), collect the set of consonant onsets observed among KNOWN signs in that class:
   ```
   CELL_CONSONANTS[V_y] = {onset(sign) : sign in known_signs AND grid[sign].vowel_class == V_y}
   ```
   Example: If known signs in V=0 (a-class) include da, ja, ka, na, pa, ra, sa, ta, wa, then CELL_CONSONANTS[0] = {d, j, k, n, p, r, s, t, w} plus "" (for pure vowel a).

2. For each unknown sign assigned to V_y, its candidate readings are:
   ```
   candidates(sign) = {c + vowel(V_y) : c in CELL_CONSONANTS[V_y]}
   ```
   This typically yields 2-10 candidates per sign.

3. Identify the **search pool**: all P2 stems where:
   - The stem has >= 2 sign IDs
   - Exactly N_unknown signs lack IPA values (iteration 1: N_unknown = 1)
   - Each unknown sign has a grid assignment with candidates

4. Deduplicate stems (same sign-ID sequence -> keep highest-frequency instance).

5. Sort stems by frequency descending (high-frequency stems searched first for maximum cross-validation).

**Output:** Search pool (list of stems with their candidate reading enumerations).

**Existing implementation:** `constrained_sca_search.py::find_partial_stems()` and `candidate_readings()` already do this. The iterative loop wraps this initialization.

### Step B: Enumerate and Search

**Input:** Search pool from Step A, candidate language lexicons.

**Process:** For each stem in the search pool, for each candidate reading of each unknown sign:

1. **Construct complete IPA:** Replace the unknown sign(s) with the candidate reading to form a complete IPA string.
   ```
   stem = [ta, ???, a]   with ???.vowel_class = 3 (o-class)
   candidate = "po"  ->  complete_ipa = "tapoa"
   candidate = "do"  ->  complete_ipa = "tadoa"
   ...
   ```

2. **SCA-encode:** Convert complete IPA to Dolgopolsky sound classes.
   ```
   "tapoa" -> "TVPVV"   (t->T, a->V, p->P, o->V, a->V)
   ```

3. **Search each lexicon:** For each of the 18 candidate languages, find the best SCA match (minimum normalized Levenshtein distance in SCA space).

4. **Compute significance:** Use an **analytical null** (not permutation null) to determine whether the best match is better than chance.

   **Why analytical, not permutation:** The constrained search (session report, Section 11) found that permutation nulls with 100 permutations have minimum achievable p-value = 0.01, but Bonferroni correction across thousands of comparisons requires thresholds of ~4.5x10^-6. The permutation null is incompatible with the required multiple testing correction. An analytical null based on the SCA collision probability at a given string length provides continuous p-values.

   **Analytical null computation:**
   - For SCA strings of length L, the probability of a random match at distance d or better against a lexicon of size N is computed from the SCA alphabet size (10 consonant classes + 1 vowel class = 11 symbols) and the edit distance distribution under random draws.
   - Specifically: P(dist <= d | L_query, L_target, N_lexicon) using the combinatorial model from List (2012) "LexStat" framework.
   - BH-FDR (Benjamini-Hochberg False Discovery Rate) correction applied across all comparisons within each iteration, controlling FDR at q=0.05.

**Output:** For each (stem, candidate_reading, language) triple: SCA distance, analytical p-value, best-match word and gloss.

**Performance estimate:** 184 stems x ~5 readings x 18 languages = ~16,560 comparisons per iteration. At ~10ms per comparison (SCA distance is O(L^2) with L~6), this is ~3 minutes per iteration.

### Step C: Score and Filter

**Input:** Raw comparison results from Step B.

**Process:**

1. **Apply BH-FDR** at q=0.05 across all comparisons in this iteration. This controls the expected proportion of false discoveries among rejected nulls.

2. **Filter to significant matches:** Retain only (stem, reading, language) triples that survive FDR correction.

3. **Minimum SCA length gate:** Reject any match where the SCA-encoded query has fewer than 6 characters (corresponding to 3+ CV syllables). Below this length, the SCA collision rate is too high for discrimination (84% collision rate at 4 chars, per session report Section 11).

4. **Enrichment filter:** For each unknown sign, compute the enrichment ratio:
   ```
   enrichment = (observed significant matches for this reading) / (expected under uniform random reading assignment)
   ```
   The constrained search found 3.2x aggregate enrichment. Individual readings must show enrichment > 2.0 to be considered non-random.

### Step D: Evaluate Sign-Reading Convergence

**Input:** Filtered significant matches from Step C.

**Process:** For each unknown sign that appears in multiple stems:

1. **Collect votes:** Each stem with a significant match "votes" for the reading that produced the match. A vote carries weight proportional to the negative log of its p-value (stronger evidence = higher weight).

2. **Consistency check:** The SAME sign must get the SAME reading across ALL stems where it appears. This is the key constraint that makes the loop powerful -- it is astronomically unlikely for the wrong reading to produce significant matches consistently across 3+ independent stems.

   Compute the **consistency ratio** for each sign:
   ```
   consistency = (votes for best reading) / (total votes across all readings)
   ```

3. **Classify each sign:**

   | Verdict | Criteria | Action |
   |---------|----------|--------|
   | **ACCEPT** | >= 3 independent stems agree on the same reading, consistency >= 0.8, best reading has enrichment > 2.0 | Promote to known sign for next iteration |
   | **PROVISIONAL** | 2 stems agree, consistency >= 0.7 | Carry forward, may promote in future iteration |
   | **INSUFFICIENT** | 0-1 stems with significant matches | No evidence; sign remains unknown |
   | **CONTRADICTORY** | 2+ readings each supported by 2+ stems, consistency < 0.6 | Flag for investigation (may indicate context-dependent reading or grid error) |

4. **Cross-sign consistency:** If two unknown signs are constrained to the same reading (e.g., both assigned "po"), check whether the stems containing each sign produce matches in the same language family. Convergence across signs strengthens both; divergence weakens both.

### Step E: Update and Iterate

**Input:** ACCEPT and PROVISIONAL sign readings from Step D.

**Process:**

1. **Promote ACCEPTED signs:** Add to the known-sign set (`sign_to_ipa.json` in-memory copy, NOT written to disk until human review).

2. **Recompute search pool:** With newly-known signs, stems that previously had 2 unknowns now have 1 unknown (and enter the search pool), and stems that had 1 unknown now have 0 unknowns (and become fully-phonetic baseline stems).

3. **Update constraint tables:** The newly-known signs expand `CELL_CONSONANTS` -- their consonant onsets become available as candidates for other unknown signs in the same vowel class.

4. **Compute convergence metric:**
   ```
   convergence = (new signs ACCEPTED this iteration) / (total unknown signs remaining)
   ```
   If convergence < 0.001 (fewer than 1 new sign per 1000 unknowns), the loop is exhausted.

5. **Iterate:** Return to Step A with the expanded known-sign set.

### Pseudocode Summary

```python
known_signs = load("sign_to_ipa.json")  # 53 initial
grid = load("pillar1_v5_output.json")
stems = load("pillar2_output.json")
lexicons = load_all_lexicons()

for iteration in range(MAX_ITERATIONS):
    # Step A
    constraints = build_constraint_tables(grid, known_signs)
    search_pool = find_partial_stems(stems, known_signs, constraints, max_unknown=1)

    if not search_pool:
        break  # No more searchable stems

    # Step B
    results = []
    for stem in search_pool:
        for reading in constraints[stem.unknown_sign]:
            for lang, lex in lexicons.items():
                ipa = construct_ipa(stem, reading)
                sca = ipa_to_sca(ipa)
                if len(sca) < MIN_SCA_LENGTH:
                    continue
                dist, match = search_lexicon(sca, lex)
                p = analytical_null_pvalue(dist, len(sca), len(lex))
                results.append((stem, reading, lang, dist, p, match))

    # Step C
    significant = apply_bh_fdr(results, q=0.05)
    significant = [r for r in significant if enrichment(r) > 2.0]

    # Step D
    verdicts = evaluate_convergence(significant)
    accepted = [v for v in verdicts if v.verdict == "ACCEPT"]

    # Step E
    for sign in accepted:
        known_signs[sign.sign_id] = sign.best_reading

    convergence = len(accepted) / max(1, count_unknown(grid, known_signs))
    log_iteration(iteration, verdicts, convergence)

    if convergence < CONVERGENCE_THRESHOLD:
        break

write_output(all_iterations)
```

---

## 6. Go/No-Go Gates

### Gate 0: Pre-Iteration Sanity (run BEFORE the loop starts)

| Check | Pass criterion | On failure |
|-------|----------------|------------|
| P1 grid loaded, >= 50 signs assigned | `len(grid.assignments) >= 50` | BLOCK -- P1 output insufficient |
| Known signs >= 50 | `len(sign_to_ipa) >= 50` | BLOCK -- insufficient baseline |
| Search pool >= 100 stems | `len(search_pool) >= 100` | WARN -- loop may lack statistical power |
| At least 10 stems have SCA length >= 6 | Count stems with 3+ sign stems | BLOCK -- SCA discrimination impossible below 6 chars |
| All 18 candidate lexicons load | Each lexicon has >= 50 entries | WARN -- missing lexicons reduce power |
| Analytical null produces p < 0.001 for known cognate pair | Test on Greek-Latin known pair | BLOCK -- null model is broken |

### Gate 1: Per-Iteration Known-Answer Validation

**Purpose:** Before trusting ANY accepted sign readings from iteration N, validate that the loop correctly handles signs whose values are already known.

**Method:** Hold out 5 randomly-selected known signs (remove them from `sign_to_ipa.json` for this iteration only). Run the loop. Check:

| Check | Pass criterion | On failure |
|-------|----------------|------------|
| Held-out signs recovered correctly | >= 3/5 correct readings (or INSUFFICIENT, never wrong) | BLOCK iteration output -- loop is producing false positives |
| No held-out sign gets CONTRADICTORY | 0 CONTRADICTORY verdicts for held-out signs | WARN -- grid or search has systematic error |
| False positive rate on held-out signs | 0 signs assigned an INCORRECT reading with ACCEPT verdict | BLOCK -- acceptance criteria too loose |

**Critical requirement:** It is acceptable for the loop to return INSUFFICIENT for a held-out sign (it may lack enough stems). It is NOT acceptable for the loop to ACCEPT a wrong reading. The false-positive rate must be 0% on known signs.

### Gate 2: Null Corpus Test

**Purpose:** Verify the loop does not "discover" sign readings from random data.

**Method:** Replace `sign_to_ipa.json` with a randomly permuted version (shuffle IPA values across sign IDs). Run one iteration.

| Check | Pass criterion | On failure |
|-------|----------------|------------|
| No signs ACCEPTED | 0 ACCEPT verdicts | BLOCK -- loop is hallucinating |
| PROVISIONAL count < 3 | Near-zero provisional verdicts | WARN -- acceptance threshold may be too loose |

### Gate 3: Cross-Iteration Monotonicity

**Purpose:** Each iteration should not REVERSE a previous iteration's accepted reading.

| Check | Pass criterion | On failure |
|-------|----------------|------------|
| No reading changes | Once ACCEPTED, a sign's reading never changes | BLOCK -- evidence aggregation is inconsistent |
| Searchable stems monotonically increase | `searchable_stems[i] >= searchable_stems[i-1]` | BLOCK -- logic error in pool expansion |

---

## 7. Components/Modules

### 7.1 Module: `iterative_loop.py` (Orchestrator)

**Responsibility:** Runs the outer iteration loop. Manages state across iterations. Calls all other modules. Writes per-iteration and cross-iteration output.

**Interface:**
```python
def run_iterative_decipherment(
    p1_output_path: Path,
    p2_output_path: Path,
    sign_to_ipa_path: Path,
    lexicon_dir: Path,
    config: IterativeConfig,
    output_dir: Path,
) -> CrossIterationSummary:
```

### 7.2 Module: `constraint_builder.py` (Step A)

**Responsibility:** Builds constraint tables from P1 grid. Identifies search pool from P2 stems. Computes candidate readings for each unknown sign.

**Key functions:**
- `build_cell_consonants(grid, known_signs) -> dict[int, set[str]]`
- `candidate_readings(vowel_class, cell_consonants) -> list[str]`
- `find_searchable_stems(p2_lexicon, known_signs, grid, max_unknown=1) -> list[SearchableStem]`

**Reuses:** Logic from `constrained_sca_search.py::find_partial_stems()` and `candidate_readings()`.

### 7.3 Module: `sca_matcher.py` (Step B)

**Responsibility:** SCA encoding, lexicon search, analytical null computation.

**Key functions:**
- `ipa_to_sca(ipa: str) -> str` -- Dolgopolsky 10-class encoding
- `normalized_edit_distance(s1: str, s2: str) -> float` -- Levenshtein in [0,1]
- `search_lexicon(query_sca: str, lexicon: list[LexEntry], top_k=3) -> list[Match]`
- `analytical_p_value(distance: float, query_len: int, lexicon_size: int) -> float`

**Reuses:** SCA infrastructure from `sca_cognate_search.py` (Dolgopolsky map, edit distance, lexicon loading). Replaces permutation null with analytical null.

**Analytical null derivation:** The probability that a random SCA string of length L matches a uniformly random SCA string of length L at normalized edit distance <= d, given an alphabet of size A=11 (10 consonant sound classes + 1 vowel class), is:

```
P(NED <= d | L, A) = sum over all edit sequences with cost <= d*L of:
    product of (1/A) for each substitution, insertion probability, deletion probability
```

In practice, use the empirical distribution from List (2012) LexStat framework, or compute via Monte Carlo calibration at startup (generate 10,000 random SCA pairs of each length L in {4..12}, record NED distribution, fit parametric model). This one-time calibration takes ~5 seconds.

For a lexicon of size N, the probability of the best match having distance <= d is:
```
P(min_dist <= d | L, N, A) = 1 - (1 - P(NED <= d | L, A))^N
```

### 7.4 Module: `convergence_evaluator.py` (Steps C-D)

**Responsibility:** Applies FDR correction, evaluates cross-stem convergence for each sign, classifies signs into ACCEPT/PROVISIONAL/INSUFFICIENT/CONTRADICTORY.

**Key functions:**
- `apply_bh_fdr(results: list[MatchResult], q=0.05) -> list[MatchResult]`
- `compute_sign_votes(significant_matches: list[MatchResult]) -> dict[str, SignVotes]`
- `classify_sign(votes: SignVotes) -> SignVerdict`
- `cross_sign_consistency(verdicts: list[SignVerdict]) -> list[SignVerdict]`

### 7.5 Module: `iteration_state.py` (Step E)

**Responsibility:** Manages mutable state across iterations. Tracks which signs have been accepted, computes convergence, decides whether to continue.

**Key functions:**
- `promote_signs(accepted: list[SignVerdict], known_signs: dict) -> dict`
- `compute_convergence(n_accepted: int, n_unknown: int) -> float`
- `should_continue(convergence: float, iteration: int, config: IterativeConfig) -> bool`

### 7.6 Module: `validation.py` (Gates)

**Responsibility:** Implements all go/no-go gates. Run before the loop (Gate 0), after each iteration (Gate 1), and as a standalone null test (Gate 2).

**Key functions:**
- `gate0_sanity(grid, known_signs, search_pool, lexicons) -> GateResult`
- `gate1_known_answer(loop_fn, known_signs, n_holdout=5) -> GateResult`
- `gate2_null_corpus(loop_fn, grid, sign_to_ipa) -> GateResult`
- `gate3_monotonicity(iteration_history) -> GateResult`

### 7.7 Configuration

```yaml
# iterative_decipherment.yaml
max_iterations: 10
min_sca_length: 6                    # Minimum SCA chars for a comparison to count
max_unknown_per_stem: 1              # Start with 1; future: relax to 2
bh_fdr_q: 0.05                      # FDR control level
min_enrichment: 2.0                  # Minimum enrichment ratio to consider non-random
accept_min_stems: 3                  # Minimum independent stems for ACCEPT
accept_min_consistency: 0.8          # Minimum consistency ratio for ACCEPT
provisional_min_stems: 2             # Minimum independent stems for PROVISIONAL
provisional_min_consistency: 0.7     # Minimum consistency ratio for PROVISIONAL
convergence_threshold: 0.001         # Stop when fewer than 0.1% of unknowns resolved per iteration
holdout_n: 5                         # Number of known signs to hold out for Gate 1
seed: 42                             # For reproducibility
candidate_languages:                 # ISO codes of lexicons to search
  - hit
  - xld
  - xlc
  - xrr
  - phn
  - uga
  - elx
  - xur
  - peo
  - xpg
  - ave
  - akk
  - grc
  - lat
  - heb
  - arb
  - sem-pro
  - ine-pro
```

---

## 8. Risks and Mitigations

### R1: Consonant class 0 is a mega-class (91% of signs)

**Impact:** HIGH -- consonant constraints provide almost no discrimination. Most unknown signs have the same consonant class, so "same consonant class" is nearly vacuous.

**Mitigation:** The loop currently relies primarily on VOWEL class constraints (5 classes, 95% accuracy). Consonant agreement is a secondary consistency check, not a filter. Future work: refine P1 grid with BH-FDR instead of Bonferroni to produce finer consonant classes.

**Monitoring:** Track what fraction of ACCEPT verdicts would change if consonant constraints were removed entirely. If >90%, consonant constraints are not contributing and this is honest.

### R2: SCA collision rate at short string lengths

**Impact:** HIGH -- At 4 SCA characters (2-syllable stems), 84% of random strings collide. Even at 6 characters, collision rates may be substantial.

**Mitigation:** The `min_sca_length: 6` gate excludes stems below 3 syllables. The analytical null explicitly accounts for string length -- shorter strings require proportionally lower distances to be significant. The enrichment filter (>2.0) provides a second line of defense.

**Monitoring:** Log the SCA length distribution of significant matches. If most significant matches come from length-6 strings (the minimum), the collision rate concern is active. Require length-8+ for ACCEPT verdicts in that case.

### R3: Combinatorial explosion with multiple unknowns per stem

**Impact:** MEDIUM -- With 1 unknown and ~5 candidates, each stem generates ~5 readings. With 2 unknowns, it is ~25. With 3, ~125. Multiplied by 18 languages, this grows rapidly.

**Mitigation:** Start with `max_unknown_per_stem: 1` (184 stems). Only expand to 2 unknowns after the first iteration adds known signs (reducing the number of 2-unknown stems that need enumeration). Never go above 2 unknowns -- the false positive rate scales combinatorially and the evidence per reading becomes too thin.

### R4: Chimaera language confound

**Impact:** MEDIUM -- If Linear A vocabulary comes from multiple sources, the same sign may participate in stems that match DIFFERENT languages. This is expected and is NOT an error, but it complicates convergence evaluation because the consistency check expects one reading to dominate across all stems.

**Mitigation:** The consistency check is applied to SIGN READINGS, not to LANGUAGE matches. A sign should still have a single reading regardless of which language the stem matches. If sign AB56 produces matches to Greek in stem X and to Hittite in stem Y, that is fine as long as both matches agree that AB56 = "po". The multi-language signal actually STRENGTHENS confidence in the sign reading.

### R5: No semantic filtering

**Impact:** LOW-MEDIUM -- Without semantic constraints, the loop treats all lexicon entries equally. A match between a Linear A grain term and a candidate-language word for "horse" would be accepted purely on phonological grounds.

**Mitigation:** This is a deliberate simplification for the first implementation. P4 anchors cover only ~140 sign-groups (many with low confidence), so semantic filtering would reduce the search pool substantially. Adding semantic filters is a future enhancement: for stems with P4 anchors, restrict lexicon search to semantically compatible entries.

### R6: Grid error propagation

**Impact:** MEDIUM -- If P1's grid assigns a sign to the wrong vowel class (5% error rate), the correct reading will not be among the candidates, and the loop will either return INSUFFICIENT (best case) or ACCEPT a wrong reading (worst case).

**Mitigation:** Gate 1 (known-answer validation) catches systematic grid errors -- if held-out known signs are misassigned, the grid error rate is higher than expected. Additionally, the CONTRADICTORY verdict flags signs where evidence is split, which can indicate grid errors. The 95% vowel accuracy means ~1 in 20 signs may be misclassified; with 184 stems, ~9 stems may have wrong candidates. At 3-stem minimum for ACCEPT, the probability of 3 independent wrong assignments converging on the same wrong reading is (0.05)^3 = 0.0125%.

### R7: Lexicon quality variation

**Impact:** LOW -- Larger lexicons (Latin: ~1000 entries) are more likely to contain chance matches than smaller ones (Eteocretan: ~100). The analytical null accounts for lexicon size, but systematic quality differences (clean IPA vs. noisy IPA) are not modeled.

**Mitigation:** The enrichment filter normalizes by expected false positive rate, which scales with lexicon size. Monitor per-language match rates and flag any language whose match rate deviates more than 3 sigma from size-predicted expectation.

---

## 9. Kill Criteria

The iterative loop should be **terminated and its results discarded** if any of the following conditions are met:

| Kill criterion | Detection method | Why it is fatal |
|----------------|------------------|-----------------|
| Gate 1 false positive: a known sign is ACCEPTED with a WRONG reading | Known-answer holdout test | The acceptance criteria are too loose; all ACCEPT verdicts are suspect |
| Gate 2 fails: random-permuted corpus produces >= 1 ACCEPT | Null corpus test | The loop is extracting structure from noise, not signal |
| Iteration 1 accepts > 20% of unknown signs | Count accepted signs | Implausibly high -- likely a systematic scoring error (cf. PhaiPhon 3.4.5's FDR rubber-stamping 558/559 pairs) |
| All accepted readings favor a single language | Language distribution of supporting matches | Inventory-size bias is dominating (cf. PhaiPhon 3.5.1 where Arabic ranked #1 due to phoneme inventory) |
| Accepted sign creates logical impossibility | Check that no two distinct signs are assigned the same reading within the same consonant class | Grid structure violation |

---

## 10. Convergence Criteria

The loop terminates (successfully) when:

1. **Primary criterion:** `convergence_metric < 0.001` for two consecutive iterations. This means fewer than 0.1% of remaining unknowns are being resolved, indicating the low-hanging fruit has been picked.

2. **Secondary criterion:** `max_iterations` reached (default 10). Safety cap to prevent runaway computation.

3. **Tertiary criterion:** Search pool is empty (no stems with exactly `max_unknown` unknowns remain). All available stems have been exhausted.

**Expected convergence trajectory:**
- Iteration 1: 2-5 signs ACCEPTED (from the 184 one-unknown stems with the strongest cross-stem agreement)
- Iteration 2: 1-3 more signs ACCEPTED (newly unlocked stems from iteration 1)
- Iteration 3: 0-1 signs ACCEPTED (diminishing returns)
- Iteration 4+: Likely converged

**Total expected yield:** 3-10 new sign readings (conservative). This would increase known signs from 53 to 56-63, unlocking an estimated 20-60 additional fully-phonetic stems for Pillar 5's vocabulary resolution.

**Why the yield is modest:** Most of the 89 unknown signs lack sufficient attestation (appear in too few stems) to accumulate 3 independent supporting matches. The loop works best for frequently-attested unknown signs that appear in long (3+ syllable) stems alongside multiple known signs.

---

## 11. Acceptance Criteria for New Sign Readings

This section defines exactly how much evidence is "enough" to accept a new sign reading. The thresholds are calibrated to be conservative -- false positives (accepting a wrong reading) are far more damaging than false negatives (missing a correct reading), because wrong readings propagate through subsequent iterations and contaminate downstream work.

### 11.1 Evidence Required for ACCEPT

ALL of the following must hold simultaneously:

1. **Minimum independent stems:** >= 3 P2 stems containing this unknown sign must produce significant matches (after BH-FDR correction) when the candidate reading is substituted.

2. **Consistency:** The consistency ratio (votes for best reading / total votes) must be >= 0.8. In practice, this means if 4 stems have significant matches, at least 4 must agree on the same reading (with at most 1 dissenter).

3. **Enrichment:** The best reading must show enrichment > 2.0 above the expected false positive rate. This means the observed match rate is at least twice what random chance predicts.

4. **Minimum SCA length:** At least 2 of the supporting stems must have SCA-encoded length >= 6 (3+ syllables). Supporting evidence from very short stems is not sufficient on its own.

5. **No logical contradiction:** The reading must not create a duplicate within the same grid cell (two signs in the same C-V cell having the same reading), unless they are established homophones.

### 11.2 Evidence Required for PROVISIONAL

Either of:
- 2 independent stems agree, consistency >= 0.7, enrichment > 1.5
- 1 stem with exceptionally strong evidence (p < 0.001 after FDR, SCA length >= 8)

PROVISIONAL readings are NOT promoted to known signs. They are carried forward as hypotheses that may be confirmed in future iterations if new stems become available.

### 11.3 Why These Thresholds

The 3-stem minimum is derived from the false-positive analysis:
- Under the null hypothesis (wrong reading), the probability of a significant SCA match at FDR q=0.05 is, by definition, <= 0.05.
- The probability of 3 independent stems ALL producing significant matches for the SAME wrong reading, when each stem has ~5 candidate readings, is at most:
  ```
  P(3 agreements on wrong reading) <= C(n,3) * (0.05/5)^3 = C(n,3) * 10^-6
  ```
  For n=10 stems, this is ~1.2 x 10^-4. Acceptably low.

- The 0.8 consistency requirement further reduces this, since even under the alternative hypothesis (correct reading), some stems may not produce significant matches (insufficient SCA length, lexicon gaps). Requiring 80% agreement is robust to these data gaps.

### 11.4 Promotion Workflow

```
INSUFFICIENT  ->  (next iteration adds evidence)  ->  PROVISIONAL
PROVISIONAL   ->  (next iteration adds evidence)  ->  ACCEPT (automated)
ACCEPT        ->  (human review)                  ->  CONFIRMED (written to sign_to_ipa.json)
```

The final CONFIRMED step requires human review because:
- The reading must be checked against broader epigraphic knowledge
- The supporting cognate matches must be assessed for plausibility
- The grid cell assignment should be rechecked

---

## 12. Testing Strategy

Following `STANDARDS_AND_PROCEDURES.md` Section 8 (3-tier testing):

### Tier 1: Formula/Unit Tests (~30 tests, <1s each)

- `test_constraint_builder.py`: Candidate reading generation, search pool identification
- `test_sca_matcher.py`: SCA encoding, edit distance, analytical null p-values
- `test_convergence_evaluator.py`: FDR correction, vote counting, verdict classification
- `test_iteration_state.py`: Sign promotion, convergence computation, termination logic

### Tier 2: Known-Answer Tests (~10 tests, ~30s each)

- **Linear B recovery test:** Remove 10 known LB sign values, run 1 iteration on Linear B corpus data. Must recover >= 6/10 correctly, 0/10 incorrectly.
- **Synthetic test:** Create a synthetic corpus with known structure, run the full loop. Must converge to correct readings within 3 iterations.
- **Planted signal test:** In the real Linear A data, remove 5 known signs, plant their readings as "unknown." Run loop. Must recover >= 3/5 (or INSUFFICIENT), never ACCEPT a wrong reading.

### Tier 3: Null/Adversarial Tests (~5 tests, ~60s each)

- **Random permutation test (Gate 2):** Shuffled IPA values produce 0 ACCEPT verdicts.
- **Random corpus test:** Run on corpus of randomly-generated sign sequences. 0 ACCEPT verdicts.
- **Invariance test:** Results must be identical across runs with same seed.
- **Lexicon ablation test:** Remove 1 lexicon at a time. No ACCEPT verdict should depend on a single language (chimaera assumption).

---

## 13. Corpus Budget

The iterative loop operates on the **full P2 segmented lexicon** (787 entries from 879 inscriptions). It does NOT consume or modify corpus data -- it only reads P1/P2 outputs and external lexicons.

The **Knossos ivory scepter** (119 signs) is part of P4's held-out set and is NOT included in P2's segmented lexicon. The loop will not touch it.

---

## 14. Relationship to Previous Work

### What is reused from Pillar 5 / PhaiPhon6

| Component | Source | Changes |
|-----------|--------|---------|
| Dolgopolsky SCA encoding | `sca_cognate_search.py` | None -- reused verbatim |
| Normalized edit distance | `sca_cognate_search.py` | None |
| Lexicon loading | `constrained_sca_search.py` | None |
| Constraint table building | `constrained_sca_search.py` | Extracted into `constraint_builder.py` |
| Stem search pool | `constrained_sca_search.py::find_partial_stems()` | Extended with iteration-aware state |

### What is NEW

| Component | Why new |
|-----------|---------|
| Iterative loop | `constrained_sca_search.py` is single-pass; the loop adds feedback |
| Analytical null | Replaces permutation null (incompatible with BH-FDR at required thresholds) |
| Convergence evaluator | New: cross-stem consistency analysis + verdict classification |
| Known-answer validation (Gate 1) | New: holdout-based false positive detection |
| Null corpus test (Gate 2) | New: structural defense against noise-mining |

### What is DISCARDED from PhaiPhon 1-5

| Component | Why discarded |
|-----------|---------------|
| Phonetic Prior (PP) fleet scores | Measure IPA inventory compatibility, not cognacy (session report Section 5) |
| Bayes factors / log-BF aggregation | FDR rubber-stamped 558/559 pairs in PhaiPhon 3.4.5 |
| Transition matrix JSD | Fatal mass leakage bug, inventory-size confound (PhaiPhon4 v5) |
| Language-level ranking | The loop ranks SIGN READINGS, not languages. Language matches are evidence, not output. |

---

## 15. Open Questions

1. **Analytical null calibration:** Should the null be calibrated against the specific lexicons used (empirical null) or against a theoretical random model? The empirical approach is more accurate but requires re-calibration if lexicons change.

2. **Multi-language evidence aggregation:** When the same sign reading produces significant matches in 3 different languages for 3 different stems, should this count as 3 independent pieces of evidence (current design) or should matches from the same language be weighted higher (within-family coherence)?

3. **Iteration relaxation:** After iteration 1 (max_unknown=1), should iteration 2 attempt max_unknown=2 for stems that now have only 1 unknown (due to promoted signs)? Or should max_unknown=1 be maintained throughout? The former is more aggressive; the latter is safer.

4. **Consonant class refinement:** Should the outer loop (future work) re-run P1 with accepted sign readings as additional anchors? This would produce finer consonant classes, improving constraints for subsequent iterations. Deferred to a future PRD.

5. **Jaccard substitutability integration:** The novel Jaccard vowel identification method (F1=89% on Linear B) could provide INDEPENDENT evidence for sign readings, complementing the SCA cognate evidence. Should this be a parallel evidence stream in Step D? Deferred pending analysis of correlation between Jaccard and SCA evidence.
