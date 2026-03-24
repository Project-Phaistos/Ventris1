# PRD: Pillar 5 — Multi-Source Vocabulary Resolution (Cognates as Tools, Not Goals)

**Status:** Draft
**Depends on:** ALL of Pillars 1-4. This is the final integrative step.
**Date:** 2026-03-24
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

For each sign-group in the Linear A vocabulary that has structural and/or semantic constraints from Pillars 1-4, search simultaneously across ALL candidate ancient languages to find plausible source etymologies — then detect vocabulary strata (Anatolian layer, Semitic layer, Greek contact, unknown substrate) that emerge naturally from the data.

**This pillar does NOT ask "is Linear A related to Luwian?"** It asks: **"For each constrained sign-group, which language(s) provide plausible source etymologies, and do these sources cluster into interpretable strata?"**

The output is a compositional linguistic portrait, not a single-language ranking.

**Traced to README:** "Instead of asking 'is Linear A related to Luwian?', ask: 'For each unknown word in our partially-decoded vocabulary, which language(s) provide plausible source etymologies?'"

**Fundamental axiom (non-negotiable):** Linear A is a chimaera language with multiple major influences. The architecture MUST allow mixed provenance. Cognate matching is ONLY a tool for vocabulary resolution — never the goal and never framed as proving a genetic relationship.

---

## 2. Non-goals

- **No single-language ranking.** This pillar does NOT produce "Language X is the best match." If the data suggests one dominant source, that's a finding; if it suggests five sources in different domains, that's equally valid.
- **No genetic relationship claims.** We identify vocabulary similarities, not language phylogeny. A word matching Akkadian could be a borrowing, a shared inheritance, or a coincidence.
- **No phonetic value discovery.** We use the phonological forms established by Pillars 1+4 (with consensus dependency tags). We do not re-derive phonology.
- **No morphological analysis.** We use stems from Pillar 2. We do not re-segment.
- **No "decipherment."** We produce constrained vocabulary hypotheses, not translations.

---

## 3. Inputs

### 3.1 From Pillar 1 (phonological constraints)

| Field | Use in Pillar 5 | Provenance |
|-------|-----------------|------------|
| `grid.assignments` | Sign-group phonological form — used to compute phonological distance to candidate words | INDEPENDENT (grid from distributional clustering) |
| `vowel_inventory` | Number of vowels constrains which candidate languages are phonologically compatible | INDEPENDENT |
| `lb_validation.agreement_score` | Calibrates confidence in LB-derived phonetic readings | INDEPENDENT_VALIDATED (ARI=0.615) |
| `phonotactic_constraints` | Filter out candidate matches that violate Linear A phonotactics | INDEPENDENT |

### 3.2 From Pillar 2 (morphological constraints)

| Field | Use | Provenance |
|-------|-----|------------|
| `segmented_lexicon[].stem` | STEMS (not inflected forms) are the matching units | INDEPENDENT |
| `affix_inventory.suffixes` | Morphological typology constrains candidate language compatibility | INDEPENDENT |
| `paradigm_table` | Paradigm structure as typological fingerprint | INDEPENDENT |
| `morphological_word_classes` | declining/uninflected distinction constrains match type | INDEPENDENT |

### 3.3 From Pillar 3 (grammatical constraints)

| Field | Use | Provenance |
|-------|-----|------------|
| `word_classes` | Word class constrains candidate part-of-speech | INDEPENDENT |
| `functional_words` | Functional words are NOT matched against external lexicons (they're grammatical, not lexical) | INDEPENDENT |
| `grammar_sketch` | Typological features constrain language family compatibility | INDEPENDENT |

### 3.4 From Pillar 4 (semantic constraints)

| Field | Use | Provenance |
|-------|-----|------------|
| `anchor_vocabulary` | Sign-groups with constrained semantic fields — matched only against semantically compatible candidate entries | CONSENSUS_DEPENDENT (ideogram IDs) to INDEPENDENT (transaction roles) |
| `semantic_fields` | Constrains which candidate lexicon entries are plausible | CONSENSUS_DEPENDENT |
| `place_name_anchors` | Phonetic anchors from confirmed place names | CONSENSUS_ASSUMED (place name IDs) |

### 3.5 External: Candidate language lexicons

This is the ONLY pillar that uses external language data. Sources:

**From Project-Phaistos / ancient-scripts-datasets:**
- Cognate pair TSVs: Hittite (hit), Phoenician (phn), Avestan (ave), Proto-Indo-European (ine-pro), Proto-Semitic (sem-pro), Elamite (elx), Old Persian (peo), and others
- Phonetic Prior validation corpora: IPA word lists for ~30 ancient/modern languages
- Fleet results (Vast.ai runs): per-word cognate lists with quality scores from Phonetic Prior v1

**Required for each candidate language:**
- IPA lexicon (word → IPA transcription)
- Semantic glosses (word → English meaning, for semantic field matching)
- Source attribution and peer-review status (per Section 7 data standards)

**Candidate languages (geographically and temporally plausible for Bronze Age Crete):**

| Language | Family | Plausibility for contact | Data source |
|----------|--------|------------------------|-------------|
| Luwian | Anatolian IE | HIGH — geographic proximity, Finkelberg hypothesis | PhaiPhon corpora |
| Hittite | Anatolian IE | MEDIUM — imperial contact | ancient-scripts-datasets |
| Hurrian | Hurro-Urartian | MEDIUM — cultural contact via Near East | PhaiPhon corpora |
| Akkadian | Semitic | MEDIUM — trade lingua franca | PhaiPhon corpora |
| Proto-Greek | Hellenic IE | MEDIUM — eventual successors on Crete | PhaiPhon corpora |
| Ancient Greek | Hellenic IE | LOW-MED — anachronistic but tests continuity | PhaiPhon corpora |
| Egyptian | Afro-Asiatic | LOW-MED — trade contact | PhaiPhon corpora |
| Phoenician | Semitic | LOW-MED — maritime trade | ancient-scripts-datasets |
| Sumerian | Isolate | LOW — cultural prestige borrowing possible | PhaiPhon corpora |
| Hattic | Isolate | LOW — pre-Hittite substrate | PhaiPhon corpora |
| Eteocretan | Unknown | UNKNOWN — possibly related | PhaiPhon corpora |
| Proto-IE | Indo-European | REFERENCE — ancestral forms | ancient-scripts-datasets |

### 3.6 External: Raw cognate match files (UNTRUSTED — reference only)

**Source:** Cognate pair TSVs in `ancient-scripts-datasets/data/linear_a_cognates/` (Hittite, Phoenician, Avestan, Proto-IE, Proto-Semitic, Elamite, Old Persian, etc.) and fleet validation outputs.
**Provenance:** CONSENSUS_DEPENDENT at best. PhaiPhon model outputs are NOT trusted:
- PhaiPhon3: 2/10 falsifiability checks passed, inventory-size bias, identical training losses
- PhaiPhon4 v5: inventory-size rho=0.667 structural bias
- PhaiPhon4/5 are currently being rebuilt — previous results may be invalidated

**What IS usable:** The RAW cognate match files (TSVs with lost-known word pairs and edit distance scores). These are the output of the Luo et al. phonetic prior algorithm applied to Linear A vs. candidate languages. The raw match LISTS are data; the aggregate rankings derived from them are model outputs and are not trusted.

**How used:** Raw cognate match files may be consulted AFTER Pillar 5's own phonological matching (Step 2) to check for agreement or disagreement. They are NOT used as input to scoring. They serve as an independent cross-reference — if Pillar 5 finds a match that the raw cognate files also contain, that's mildly corroborating; if they disagree, both are reported.

**What is NOT used:**
- PhaiPhon aggregate language rankings (biased)
- PhaiPhon Bayes factors or posterior probabilities (framework assumes single-language, which violates our axiom)
- PhaiPhon training weights or model parameters
- Any PhaiPhon4/5 results (currently being rebuilt, previous results potentially invalid)

---

## 4. Outputs (Interface Contract)

### 4.1 Output schema

```json
{
  "metadata": {
    "pillar": 5,
    "version": "1.0.0",
    "corpus_version": "<SHA-256>",
    "pillar1_version": "<SHA-256>",
    "pillar2_version": "<SHA-256>",
    "pillar3_version": "<SHA-256>",
    "pillar4_version": "<SHA-256>",
    "config_hash": "<SHA-256>",
    "timestamp": "ISO-8601",
    "seed": 1234,
    "n_candidate_languages": 12
  },

  "vocabulary_resolution": [
    {
      "sign_group": ["AB77", "AB03"],
      "stem": ["AB77"],
      "reading_lb": "ka-pa",
      "frequency": 5,
      "pillar4_semantic_field": "COMMODITY:FIG",
      "pillar3_word_class": "content_word_A",
      "pillar2_morphology": "declining",
      "candidate_matches": [
        {
          "language": "Akkadian",
          "word": "kappu",
          "ipa": "kappu",
          "gloss": "wing; hand; bowl",
          "phonological_distance": 0.15,
          "semantic_compatibility": 0.3,
          "combined_score": 0.22,
          "evidence_provenance": "CONSENSUS_DEPENDENT",
          "evidence_chain": [
            "Phonological: edit distance 0.15 (LB reading ka-pa vs Akkadian kappu)",
            "Semantic: COMMODITY:FIG field does not match 'wing/hand/bowl' — weak",
            "PhaiPhon prior: not in top-50 cognate list for Akkadian"
          ]
        },
        {
          "language": "Luwian",
          "word": "unknown",
          "phonological_distance": null,
          "semantic_compatibility": null,
          "combined_score": 0.0,
          "evidence_provenance": "NO_MATCH",
          "evidence_chain": ["No Luwian word within phonological distance 0.5"]
        }
      ],
      "best_match": {
        "language": "none_significant",
        "note": "No candidate exceeds combined_score threshold 0.5"
      }
    }
  ],

  "stratum_analysis": {
    "method": "unsupervised_clustering_of_best_matches",
    "strata": [
      {
        "stratum_id": 0,
        "dominant_language": "unknown_substrate",
        "n_sign_groups": 150,
        "proportion": 0.72,
        "semantic_domains": ["TRANSACTION:*", "FORMULA:*"],
        "description": "Majority of vocabulary has no strong match to any candidate language — consistent with an unattested substrate language"
      },
      {
        "stratum_id": 1,
        "dominant_language": "Anatolian",
        "n_sign_groups": 15,
        "proportion": 0.07,
        "semantic_domains": ["PLACE:*"],
        "description": "Place names and geographic terms cluster with Anatolian languages",
        "regularity_score": 0.45,
        "borrowing_vs_inheritance": "inconclusive"
      }
    ],
    "evidence_provenance": "CONSENSUS_DEPENDENT",
    "note": "Strata are emergent, not pre-specified. Dominance of substrate stratum is expected if Linear A is a language isolate with contact vocabulary."
  },

  "compositional_portrait": {
    "summary": "Of N sign-groups with sufficient constraints, X% have no strong match to any candidate language (substrate), Y% show Anatolian affinity, Z% show Semitic affinity, W% are ambiguous between multiple sources.",
    "substrate_fraction": 0.72,
    "anatolian_fraction": 0.07,
    "semitic_fraction": 0.05,
    "greek_fraction": 0.03,
    "ambiguous_fraction": 0.13,
    "evidence_provenance": "CONSENSUS_DEPENDENT"
  },

  "diagnostics": {
    "sign_groups_resolved": 205,
    "sign_groups_with_matches": 30,
    "sign_groups_no_match": 175,
    "candidate_languages_searched": 12,
    "total_candidate_comparisons": 2460,
    "raw_cognate_corroborations": 15,
    "raw_cognate_disagreements": 3,
    "mean_combined_score": 0.18,
    "max_combined_score": 0.72
  }
}
```

---

## 5. Approach

### 5.1 Step 1: Build the Constrained Vocabulary

**Goal:** Assemble the set of sign-groups that have enough structural/semantic constraints to be meaningfully matched.

For each sign-group, gather constraints from all four upstream pillars:

```
constraints(sg) = {
    phonological_form: from P1 grid (sign IDs → abstract C-V classes),
    phonetic_reading: from LB values (CONSENSUS_ASSUMED, weighted 0.5),
    stem: from P2 segmented lexicon,
    morphological_class: from P2 (declining/uninflected),
    word_class: from P3 (content/functional),
    semantic_field: from P4 (COMMODITY:FIG, PLACE:PHAISTOS, etc.),
    is_functional: from P3 (if true, EXCLUDE from lexical matching),
    evidence_provenance: max provenance across all constraints
}
```

**Filtering:**
- Exclude functional words (Pillar 3) — these are grammatical, not lexical
- Exclude sign-groups with no constraints (no P4 anchor, no P2 stem)
- Include sign-groups that have at least ONE of: semantic field (P4), morphological class (P2), or phonetic reading (LB)

### 5.2 Step 2: Cognate Discovery via Phonetic Prior Algorithm

**Goal:** For each Pillar 2 stem, run the Phonetic Prior algorithm (Luo et al. 2021) against each candidate language lexicon to produce per-stem cognate word lists with learned character mappings.

**Why the Phonetic Prior, not naive edit distance:**

The Phonetic Prior (Luo et al. 2021, "Neural Decipherment via Minimum-Cost Flow") is validated for finding individual cognate words between a lost and known language:
- Ugaritic-Hebrew: P@1 = 0.557 (repro validation)
- 926 language pairs validated across 32 languages
- Uses 61-dimensional IPA feature vectors with 7 grouped projections
- Learns a soft character mapping via differentiable DP alignment
- Handles insertions, deletions, and systematic sound shifts

Naive normalized edit distance has none of this: no learned mapping, no IPA feature projection, no validation on ancient language pairs. For finding individual cognate words, it would be strictly inferior.

**The Phonetic Prior's failure was in EVALUATION (single-language ranking with FDR rubber-stamping and inventory-size bias), not in per-word MATCHING.** We use the matching algorithm but replace the evaluation framework entirely with our Pillar 1-4 constraint filtering.

**Algorithm:**

1. **Prepare input:**
   - Convert each Pillar 2 stem to IPA using LB values (CONSENSUS_ASSUMED, weighted accordingly)
   - Concatenate stems into an "unsegmented" IPA stream per the Phonetic Prior's expected input format
   - For each candidate language, use existing IPA lexicons from the ancient-scripts-datasets repo

2. **Run the Phonetic Prior** (phonetic-prior-v2 codebase) per candidate language:
   - The algorithm learns a character mapping matrix between Linear A IPA and the candidate language
   - It segments the unsegmented input into word boundaries via DP
   - For each identified segment, it produces a ranked list of candidate matches with quality scores

3. **Extract per-stem cognate lists:**
   - Map the Phonetic Prior's segments back to our Pillar 2 stems
   - For each stem, collect the top-N matches from each candidate language
   - Record: candidate word, IPA, gloss/meaning, quality score, learned character mapping

4. **Cross-check segmentation:**
   - Compare the Phonetic Prior's discovered word boundaries against our Pillar 2 sign-group boundaries
   - Agreement = convergent evidence that the segmentation is correct
   - Disagreement = flag for investigation (one method may be wrong)

**Output per stem:**
```json
{
  "stem": ["AB77"],
  "stem_ipa_lb": "ka",
  "candidate_matches": {
    "Akkadian": [
      {"word": "kappu", "ipa": "kappu", "gloss": "wing; hand; bowl", "quality_score": -4.2, "rank": 1},
      {"word": "karpu", "ipa": "karpu", "gloss": "vessel", "quality_score": -6.1, "rank": 2}
    ],
    "Luwian": [
      {"word": "kaluti", "ipa": "kaluti", "gloss": "cup?", "quality_score": -5.8, "rank": 1}
    ]
  },
  "segmentation_agreement_with_pillar2": true
}
```

**Compute requirement:** This step requires running the Phonetic Prior algorithm ~12 times (once per candidate language). Based on PhaiPhon3 benchmarks: ~30 minutes per language on Windows CPU with vectorized DP. Total: ~6 hours for all 12 languages. Can be parallelized.

**Provenance:** The cognate lists are CONSENSUS_DEPENDENT because they depend on LB phonetic values for the Linear A IPA input. The quality SCORES from the Phonetic Prior are its own model output and should be treated as one signal among many, not as ground truth. The character MAPPINGS learned per language are potentially informative (if Luwian's mapping shows regular correspondences while Arabic's is random, that's evidence for Luwian contact).

### 5.3 Step 3: Semantic Compatibility Scoring

**Goal:** For sign-groups with Pillar 4 semantic anchors, score how well each candidate word's meaning matches the constrained semantic field.

**Method:**

For each (sign-group, candidate word) pair where the sign-group has a semantic field:

1. Extract the candidate word's gloss/meaning from the lexicon
2. Map the gloss to a semantic category using a simple taxonomy:
   - Food/agriculture terms → COMMODITY:*
   - Geographic terms → PLACE:*
   - Person/role terms → PERSON
   - Quantity/measure terms → TRANSACTION:*
3. Score compatibility:
   - Exact semantic field match → 1.0
   - Same domain match (both COMMODITY) → 0.5
   - No match → 0.0

**For sign-groups WITHOUT semantic anchors:**
- Semantic compatibility = 0.5 (neutral — doesn't help or hurt)

### 5.4 Step 4: Combined Scoring with Evidence Weighting

**Goal:** Combine the Phonetic Prior quality score, semantic compatibility, and character mapping regularity into a single score, weighted by evidence provenance.

**Formula:**

```
combined_score(sg, w) = phon_score * w_phon + semantic * w_sem + regularity * w_reg

where:
  phon_score  = normalized Phonetic Prior quality score for (stem, word) pair
                (rescaled to [0,1] within each language run)
  semantic    = semantic compatibility from P4 anchors (0.0 to 1.0)
  regularity  = character mapping regularity for this language
                (fraction of character pairs with consistent mapping across
                multiple word matches — higher = more systematic = more likely
                real contact vs chance)
  w_phon      = 0.5  (CONSENSUS_ASSUMED — depends on LB IPA input)
  w_sem       = provenance_weight(semantic_evidence)  # 0.3-1.0 per P4 provenance
  w_reg       = 0.3  (model-derived, not independently verified)
```

Provenance weights follow Section 15 of the standards:
- INDEPENDENT evidence → weight 1.0
- CONSENSUS_CONFIRMED → weight 0.8
- CONSENSUS_ASSUMED → weight 0.5
- CONSENSUS_DEPENDENT → weight 0.3

A match driven entirely by the Phonetic Prior quality score (CONSENSUS_ASSUMED via LB) gets at most weight 0.5. A match confirmed by both Phonetic Prior AND Pillar 4 semantic field (ideogram co-occurrence, partially INDEPENDENT) gets up to 0.5 + 1.0 = much stronger. This ensures that independent structural evidence from Pillars 1-4 always dominates over the Phonetic Prior's model output.

### 5.5 Step 5: Multi-Language Simultaneous Search

**Goal:** For each constrained sign-group, search ALL candidate languages simultaneously and report the best match(es) from each.

**Algorithm:**

```
for each sign_group in constrained_vocabulary:
    matches = []
    for each candidate_language in candidate_lexicons:
        for each word in candidate_language.lexicon:
            score = combined_score(sign_group, word)
            if score > min_match_threshold:
                matches.append((candidate_language, word, score))

    # Sort by score, keep top N per language
    sign_group.candidate_matches = top_matches(matches, max_per_language=5)
```

**Critical constraint:** The search is simultaneous across ALL languages. A sign-group can match words in multiple languages. This is by design — a word with Semitic AND Anatolian matches is evidence for the chimaera hypothesis.

### 5.6 Step 6: Stratum Detection (Emergent, Not Pre-Specified)

**Goal:** Let vocabulary strata emerge from the data — do NOT pre-specify which languages should appear as sources.

**Algorithm:**

1. For each sign-group with at least one match above threshold, record its best-matching language
2. Group sign-groups by best-matching language
3. For each group, check if the matches share a semantic domain:
   - If all FIG-related words match Semitic → "Semitic commodity vocabulary" stratum
   - If all place names match Anatolian → "Anatolian place name" stratum
   - If matches are randomly distributed → no stratum (noise)

4. Compute regularity within each stratum:
   - If the same sound correspondences appear across multiple matches → regular (inheritance or systematic borrowing)
   - If correspondences are irregular → borrowing or coincidence

5. For sign-groups with no match above threshold → "substrate" stratum (words with no external cognate)

**No mixture model.** Per the resolved design decisions (README): "keep it informal and let the strata emerge from the data." We do NOT formalize a mixture model. We simply report what we observe.

### 5.7 Step 7: Cross-Reference and Cognate List Assembly

**Goal:** Assemble the final per-stem cognate word lists, cross-reference the Phonetic Prior's new results (Step 2) against the old raw cognate files, and produce the vocabulary resolution that is the primary deliverable of this pillar.

**Algorithm:**

1. **For each stem, assemble the filtered cognate list:**
   From Step 5's simultaneous search results, after filtering by semantic compatibility (Step 3) and combined scoring (Step 4):
   - Keep all matches with combined_score > threshold
   - For each match, record: candidate language, candidate word, IPA, gloss, quality score, semantic compatibility, character mapping details
   - Rank by combined_score within each language

2. **Cross-reference against old raw cognate files (informational):**
   Check the existing `linear_a_cognates/cognates_{lang}.tsv` files:
   - If the old files contain a match that the new run also found → "corroborated"
   - If the old files contain a match the new run did NOT find → "old_only" (flag for review)
   - If the new run found something the old files don't have → "new_finding"
   This cross-reference does NOT change scores. It's a provenance audit trail.

3. **Produce per-stem cognate word lists:**
   The PRIMARY OUTPUT of Pillar 5 is not a score table — it is a **vocabulary** where each Linear A stem has a ranked list of possible cognate words from one or more languages, each with evidence chains and confidence.

   This is directly usable for translation: if ku-ro has no external cognate but is anchored to FUNCTION:TOTAL_MARKER by Pillar 4, that's a vocabulary entry. If ka-pa matches Akkadian "kappu" phonologically but the semantic field disagrees, that's documented with the disagreement.

4. **Segmentation cross-check:**
   Compare the Phonetic Prior's discovered word boundaries against Pillar 2's sign-group boundaries. Report agreement rate. This is a convergent validity check on the segmentation itself.

**The cognate word lists are the core deliverable** — they are what enables translation of tablets. The stratum analysis (Step 6) and compositional portrait are secondary analyses derived from the cognate lists.

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `constraint_assembler.py` | Gather P1-P4 constraints per sign-group, filter to matchable vocabulary | P1-P4 outputs | Constrained vocabulary list |
| `lexicon_loader.py` | Load candidate language lexicons with IPA and glosses | External data files | Typed lexicon objects |
| `phonetic_prior_runner.py` | Run Phonetic Prior algorithm (Luo et al. 2021) per candidate language on Pillar 2 stems | Stems (IPA via LB) + candidate lexicons | Per-stem cognate lists with quality scores + learned character mappings |
| `semantic_scorer.py` | Score semantic compatibility using P4 anchors | Constrained vocab + cognate lists | Semantic compatibility scores |
| `evidence_combiner.py` | Weighted combination with provenance tags: phon_score + semantic + regularity | Quality scores + semantics + mapping regularity | Combined scores |
| `stratum_detector.py` | Emergent stratum detection from match patterns | Combined scores + cognate lists | Stratum analysis |
| `cognate_list_assembler.py` | Assemble final per-stem cognate word lists, cross-reference old cognate files | All above + raw cognate TSVs | Vocabulary resolution (primary deliverable) |
| `output_formatter.py` | Assemble interface contract JSON | All above | Final JSON |
| `pipeline.py` | Orchestrator | Config | Runs all steps |

---

## 7. Go/No-Go Gates

### Gate 1: Known-Answer Test — Ugaritic vs Hebrew (CRITICAL)

**Test:** Run Pillar 5 on Ugaritic (as "lost language") against a set of candidate languages including Hebrew (known to be closely related). The Phonetic Prior repro achieved P@1=0.557 for this pair.

**Expected:** Hebrew should appear as the top or near-top match for a significant fraction of Ugaritic words. The stratum analysis should show a dominant "Semitic" stratum.

**On failure:** The phonological distance or combined scoring is wrong. Debug on this known pair before touching Linear A.

### Gate 2: Null Test — Isolate Control (CRITICAL)

**Test:** Run Pillar 5 on a synthetic isolate language (random IPA words with no relationship to any candidate). No candidate language should score significantly above baseline.

**Expected:** All combined scores < 0.3. No stratum with > 10% of vocabulary. Substrate stratum > 90%.

**On failure:** The scoring is too permissive. Tighten thresholds.

### Gate 3: Chimaera Test — English Etymology (HIGH)

**Test:** Run on English vocabulary (which is known to be a chimaera: Germanic core + French/Latin superstratum + Norse contact). Feed Germanic, French, Latin, and Norse as candidate languages.

**Expected:** The stratum analysis should detect MULTIPLE strata — not one dominant language. If it assigns all English words to Germanic, the stratum detection is failing.

### Gate 4: Raw Cognate Cross-Reference Independence (HIGH)

**Test:** Verify that the raw cognate cross-reference (Step 7) does NOT affect scores. Run Pillar 5 with and without the cross-reference step. All scores and rankings must be identical. The cross-reference is purely informational.

### Gate 5: Provenance Consistency (MEDIUM)

**Test:** Every match in the output has a valid evidence_provenance tag. No SPECULATIVE tags. INDEPENDENT findings have empty consensus_dependencies.

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **LB phonetic readings are wrong for some signs** | HIGH | MEDIUM | Use abstract C-V form (INDEPENDENT) alongside LB reading (CONSENSUS_ASSUMED). Weight LB at 0.5, not 1.0. |
| **Candidate lexicons are incomplete or wrong** | HIGH | MEDIUM | Document source, coverage, and quality for each lexicon. Cross-reference multiple sources where possible. Flag matches that depend on a single lexicon entry. |
| **Semantic field matching is too coarse** | MEDIUM | HIGH | Accept coarse matching (domain-level, not word-level). A COMMODITY:FIG anchor matching any food term is useful even if not precise. |
| **Phonetic Prior biases propagate** | HIGH | MEDIUM | Cap PhaiPhon weight at 0.3. Use per-word lists only, not aggregate rankings. Flag when PhaiPhon and P1-P4 disagree. |
| **Most vocabulary has no match (substrate dominance)** | MEDIUM | HIGH | This is the correct outcome if Linear A is a language isolate with contact vocabulary. Report the substrate fraction honestly — it IS information. |
| **False cognates from chance similarity** | HIGH | HIGH | Require both phonological AND semantic compatibility for a "significant" match. Phonological similarity alone is not sufficient. Apply false discovery rate correction across all comparisons. |
| **Over-interpretation of small strata** | MEDIUM | MEDIUM | Report confidence intervals on stratum proportions. A stratum of 3 words is not a reliable finding — it could be chance. Require ≥ 5 words per stratum for it to be reported as a finding (not just noise). |

---

## 9. Corpus Budget

| Data subset | Used for | Size | Notes |
|-------------|----------|------|-------|
| All constrained sign-groups from P1-P4 | Matching vocabulary | ~205 sign-groups | From Pillar 4 anchor vocabulary |
| Candidate language lexicons | Matching targets | ~500-5000 words per language, 12 languages | External data, per data extraction standards |
| PhaiPhon cognate lists | Soft priors | ~20 languages × ~500 words | From PhaiPhon outputs (CONSENSUS_DEPENDENT) |
| Held-out: Knossos ivory scepter | Final validation | ~119 signs | After all pillars complete, apply P1-P5 and check coherence |

---

## 10. Relationship to PhaiPhon (Legacy)

### What IS reused (carefully)

- **Candidate language IPA corpora** — the IPA word lists built for PhaiPhon validation. These are DATA, not MODEL OUTPUTS, so they're as reliable as their sources (subject to data extraction standards Section 7).
- **Raw cognate match files** — TSVs in `ancient-scripts-datasets/data/linear_a_cognates/` and fleet outputs. Used ONLY as post-hoc cross-reference (Step 7), NOT as scoring input. These are untrusted model outputs.
- **Phonetic Prior v2 edit distance DP** — the algorithm itself (Luo et al. 2021) is sound and could be reused for phonological distance computation. But it would need to be reimplemented in Pillar 5's framework with provenance-tagged output, not imported from PhaiPhon.
- **PhaiPhon4/5 are currently being rebuilt** by the user. Any future validated outputs from the rebuild may be integrated, but previous PhaiPhon4/5 results are considered INVALID until the rebuild is complete.

### What is NOT reused

- **Aggregate language rankings** from PhaiPhon3/4 — these have known biases (inventory size, vocab size, FDR rubber-stamping) and are not trustworthy.
- **The framing** — PhaiPhon asked "which language is Linear A related to?" Pillar 5 asks "which words match which languages, and do patterns emerge?"
- **The single-language assumption** — PhaiPhon produced one ranking. Pillar 5 produces per-word multi-language matches.
- **Bayesian model comparison framework** — the log-BF / posterior approach assumes one true model (one language). Pillar 5 assumes mixed provenance.

### What changed and why

PhaiPhon tried to answer the wrong question (single-language affiliation) with a method that had structural biases. Pillar 5 inverts the approach:
1. Per-word matching instead of corpus-level ranking
2. Multiple simultaneous languages instead of pairwise comparison
3. Semantic constraints from Pillar 4 (PhaiPhon ignored ideograms entirely)
4. Evidence weighting by provenance (PhaiPhon treated all evidence as equal)
5. Stratum detection as the output (PhaiPhon produced a ranked list)

---

## 11. Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. **Known-answer test on Ugaritic-Hebrew fails:** Hebrew is not in the top 3 matches for > 30% of Ugaritic words, despite being the closest known relative.
2. **Null test on isolate control fails:** Any candidate language scores > 0.3 mean combined score on random data.
3. **Chimaera test on English fails:** Only one stratum detected (should be ≥ 2 for English).
4. **More than 80 person-hours spent** without passing Gate 1.

---

## 12. Appendix: Why Per-Word Matching Is Superior to Corpus-Level Ranking

### A.1 The fundamental flaw of corpus-level ranking

PhaiPhon3-5 all produced a single ranking: "Luwian #1, Hurrian #2, ..." This ranking is meaningless for a chimaera language because:

1. **Different words may come from different sources.** A corpus-level score averages over all words, washing out stratum-level signal.
2. **Ranking is dominated by confounds.** Phoneme inventory size, vocabulary size, and IPA source quality all correlate with ranking position (PhaiPhon3.4.5: inventory rho=0.667).
3. **Ranking is brittle.** PhaiPhon3.2 had Hattic #1; PhaiPhon3.4.5 had Arabic #1; PhaiPhon3.5.1 had Luwian #1. The rankings changed with every bug fix, suggesting noise dominates signal.

### A.2 Per-word matching preserves stratum signal

By matching each word individually:
1. Words from different strata can match different languages without interference
2. The stratum structure EMERGES from the per-word results — it doesn't need to be assumed
3. Confounds are reduced: inventory size affects all words equally, so it shifts all scores, but the RELATIVE ranking within a semantic domain is preserved
4. False positives are filtered by semantic compatibility (PhaiPhon had no semantic constraints at all)

### A.3 The consensus dependency layer prevents over-interpretation

Every match in Pillar 5 carries a provenance tag. A match based entirely on CONSENSUS_ASSUMED evidence (LB readings) gets weight 0.5. A match confirmed by INDEPENDENT evidence (semantic field from ideogram co-occurrence + morphological compatibility) gets weight 1.0. This prevents the system from producing confident-looking results from uncertain evidence.
