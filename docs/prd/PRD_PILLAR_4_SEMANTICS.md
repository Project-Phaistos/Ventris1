# PRD: Pillar 4 — Semantic Anchoring (The Known Knowns)

**Status:** Draft
**Depends on:** Nothing — can run in parallel with Pillars 2-3 (but benefits from their outputs)
**Also consumes (optional):** Pillar 1 (phonotactics), Pillar 2 (segmented lexicon), Pillar 3 (functional words)
**Feeds into:** Pillar 5 (multi-source vocabulary resolution)
**Date:** 2026-03-24
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Maximize what can be learned about Linear A vocabulary from **context alone** — ideograms, numerals, transaction structure, formulaic patterns, and known place names — before any cross-language comparison.

This pillar extracts the supervised signal that most computational approaches underuse: the non-textual elements of the inscriptions (commodity ideograms, quantity numerals, totaling conventions) that constrain the meaning of adjacent words without knowing the language.

**Traced to README:** "The Linear A tablets aren't just text — they contain ideograms (pictures of grain, oil, wine, animals, people), numerals, and transaction structures. This is supervised signal that most computational approaches underuse."

---

## 2. Non-goals

- **No external language comparison.** Meanings are constrained by context, not by cognate matching.
- **No translation.** We produce "this word is a commodity name in the GRAIN semantic field" — not "this word means 'barley'."
- **No phonetic value assignment.** We operate on sign IDs.
- **No grammar.** Sentence structure is Pillar 3's domain. We identify semantic fields and formulaic elements.

---

## 3. Inputs

### 3.1 Primary: SigLA corpus with ideogram and numeral data

**File:** `data/sigla_full_corpus.json` (v2.0.0)

Key data for semantic anchoring:
- **165 logograms** (ideograms/commodity signs) in the sign inventory
- **18 numeral signs** with 310 total numeral tokens
- **Known commodity ideograms** with recognizable pictographic meanings:
  - AB30/FIC: figs (147 co-occurrence tokens)
  - AB120/GRA: grain (139 tokens)
  - AB131/VINa: wine (108 tokens)
  - AB122/OLIV: olives (91 tokens)
  - AB100/VIR: man/person (67 tokens)
- **31 inscriptions containing ku-ro** (total marker) with associated commodity logograms
- **71 libation inscriptions** with formulaic text
- **879 inscriptions** across 15+ sites

### 3.2 Inscription structure

Each inscription has:
- `signs_sequence[]`: ordered list of ALL signs (syllabograms + logograms + numerals) with type labels
- `words[]`: segmented sign-groups (syllabograms only)
- Type, site, period metadata

The critical insight: `signs_sequence` preserves the interleaving of text and ideograms/numerals that `words` strips out. A typical administrative line looks like:

```
[word1] [word2] [LOGOGRAM: FIG] [NUMERAL: 5]
```

This means word1 or word2 is semantically related to figs, and the quantity is 5.

### 3.3 Optional: Pillar 1-3 outputs

If available, these enrich the analysis:
- Pillar 1: phonotactic constraints (which sign sequences are legal words vs. possible logogram sequences)
- Pillar 2: segmented lexicon (stems vs. suffixes — the STEM of a word near a fig ideogram is the core semantic unit, not the inflected form)
- Pillar 3: functional words (these should be excluded from commodity-name analysis; word classes help interpret transaction structure)

### 3.4 Known place names (from scholarship)

Published identifications (via Linear B cognates and geographic evidence):
- PA-I-TO (AB03-AB28-AB05) = Phaistos
- I-DA (AB28-AB01) = Mount Ida
- A-DI-KI-TE (AB08-AB07-AB67-AB04) = Dikte
- DI-KI-TE (AB07-AB67-AB04) = Dikte (shorter form)
- KU-DO-NI-JA = Kydonia (attested in Linear B, possible in Linear A)
- SU-KI-RI-TA = Sybrita?

These are used as phonetic anchors (confirming LB sign values) and as geographic markers.

---

## 4. Outputs (Interface Contract)

### 4.1 Output schema

```json
{
  "metadata": {
    "pillar": 4,
    "version": "1.0.0",
    "corpus_version": "<SHA-256>",
    "config_hash": "<SHA-256>",
    "timestamp": "ISO-8601"
  },

  "anchor_vocabulary": [
    {
      "word_sign_ids": ["AB77", "AB03"],
      "stem_sign_ids": ["AB77"],
      "reading": "ka-pa",
      "frequency": 5,
      "semantic_field": "COMMODITY:FIG",
      "confidence": 0.75,
      "evidence": {
        "ideogram_co_occurrence": {
          "AB30/FIC": 4,
          "AB120/GRA": 0
        },
        "positional": "immediately_before_ideogram",
        "n_inscriptions": 5,
        "inscription_types": ["Tablet"]
      }
    }
  ],

  "semantic_fields": {
    "COMMODITY:FIG": {
      "ideogram": "AB30/FIC",
      "n_associated_words": 12,
      "top_words": [
        {"word": "ka-pa", "co_occurrence": 4, "exclusivity": 0.80}
      ]
    },
    "COMMODITY:GRAIN": { ... },
    "COMMODITY:WINE": { ... },
    "COMMODITY:OLIVE": { ... },
    "PERSON": { ... },
    "TRANSACTION:TOTAL": { ... },
    "TRANSACTION:DEFICIT": { ... },
    "PLACE_NAME": { ... },
    "RITUAL": { ... }
  },

  "formula_atlas": {
    "libation_formula": {
      "n_instances": 71,
      "fixed_elements": [
        {
          "word": "ja-sa-sa-ra-me",
          "position": "variable",
          "frequency": 3,
          "interpretation": "deity_name_or_epithet"
        }
      ],
      "variable_elements": [
        {
          "slot": "initial",
          "variants": ["a-ta-i-*301-wa-ja", "ta-na-i-*301-ti"],
          "interpretation": "dedicant_or_site"
        }
      ],
      "template": "[DEDICANT?] ... ja-sa-sa-ra-me ... [OFFERING?]"
    },
    "transaction_formula": {
      "n_instances": 166,
      "template": "[AGENT/NAME] [COMMODITY_WORD] [IDEOGRAM] [NUMERAL] ... ku-ro [TOTAL_NUMERAL]",
      "identified_roles": {
        "agent": "first word in line",
        "commodity_modifier": "word immediately before ideogram",
        "total_marker": "ku-ro (always precedes total numeral)"
      }
    }
  },

  "place_name_anchors": [
    {
      "word_sign_ids": ["AB03", "AB28", "AB05"],
      "reading": "pa-i-to",
      "identified_as": "Phaistos",
      "confidence": 0.95,
      "evidence": "Linear B cognate + geographic context (found at Phaistos site)",
      "phonetic_anchors": {
        "AB03": "pa",
        "AB28": "i",
        "AB05": "to"
      },
      "lb_agreement": true
    }
  ],

  "numerical_analysis": {
    "numeral_system": "decimal_additive",
    "attested_values": {
      "A701": 1,
      "A702": 2,
      "A703": 3,
      "A704": 10,
      "A705": 100,
      "A707": "fraction_or_unit"
    },
    "ku_ro_totals_verified": {
      "n_testable": 15,
      "n_correct": 12,
      "n_discrepant": 3,
      "discrepancy_words": ["modifier_candidates"]
    }
  },

  "diagnostics": {
    "total_words_anchored": 85,
    "anchor_confidence_distribution": {
      "high_gt_0.7": 25,
      "medium_0.3_to_0.7": 35,
      "low_lt_0.3": 25
    },
    "semantic_fields_identified": 9,
    "formula_instances_analyzed": 237,
    "place_names_confirmed": 3
  }
}
```

### 4.2 What Pillar 5 consumes

- `anchor_vocabulary` — words with constrained meanings that Pillar 5 can match against candidate language lexicons. A word anchored to COMMODITY:FIG should match a fig/fruit word in the candidate language.
- `semantic_fields` — the semantic field constrains which candidate entries are plausible.
- `formula_atlas` — formulaic structure helps distinguish fixed terms (deity names, ritual verbs) from variable terms (personal names, places).
- `place_name_anchors` — confirmed phonetic values from place names provide additional LB validation and constrain Pillar 5's phonological matching.

---

## 5. Approach

### 5.1 Step 1: Ideogram Co-occurrence Analysis

**Goal:** For each word in the corpus, compute how often it appears adjacent to each commodity ideogram.

**Algorithm:**

1. **Build word-ideogram co-occurrence matrix C:**
   For each inscription, walk through `signs_sequence`. When a syllabogram word is followed (within 3 sign positions) by a logogram:
   - Record C[word, logogram] += 1
   - Record the positional relationship (immediately_before, same_line, nearby)

2. **Compute exclusivity scores:**
   For each (word, ideogram) pair:
   - exclusivity(word, ideogram) = C[word, ideogram] / Σ_all_ideograms C[word, ·]
   - High exclusivity (> 0.5) means the word appears predominantly with one commodity → strong semantic anchor

3. **Assign semantic fields:**
   Map ideograms to semantic fields:
   - AB30/FIC → COMMODITY:FIG
   - AB120/GRA → COMMODITY:GRAIN
   - AB131/VINa → COMMODITY:WINE
   - AB122/OLIV → COMMODITY:OLIVE
   - AB100/VIR → PERSON

   A word gets the semantic field of its highest-exclusivity ideogram.

4. **Distinguish semantic roles:**
   Words adjacent to ideograms can be:
   - **Commodity names/types:** appear exclusively with one ideogram type
   - **Place names:** appear with multiple ideogram types (a place produces figs AND grain)
   - **Personal names:** appear with VIR ideogram and/or in agent position
   - **Modifiers:** appear with one ideogram but also in modifier position (before the commodity name)

**Mathematical basis:**

The co-occurrence matrix C has dimensions |words| × |ideograms|.

Exclusivity = C[w, g] / row_sum(w), equivalent to P(ideogram=g | word=w).

Significance test: For each (word, ideogram) pair, compare C[w, g] against expected under independence:

E[w, g] = (row_sum(w) × col_sum(g)) / grand_total

Chi-squared test or Fisher's exact test for enrichment. Bonferroni correct across all (word, ideogram) pairs.

### 5.2 Step 2: Transaction Structure Analysis

**Goal:** Identify the template structure of administrative tablet entries and assign roles to word positions.

**Algorithm:**

1. **Identify totaling lines:**
   Lines containing ku-ro (AB81-AB02) are totaling lines. The numerals after ku-ro should sum to the numerals in the preceding lines.

2. **Parse numeral values:**
   The Linear A numeral system is decimal-additive (same as Linear B):
   - Vertical strokes (A701) = units
   - Horizontal bars (A704) = tens
   - Circles (A705) = hundreds
   - Fractions (A707, A708) = fractional units

   For each inscription, attempt to parse numeral clusters into integer values.

3. **Verify totals:**
   For inscriptions with ku-ro and parseable numerals:
   - Sum all pre-ku-ro numeral values
   - Compare to the post-ku-ro numeral value
   - If they match: the total is correct, confirming the transaction structure
   - If they don't match: the discrepancy reveals either:
     - A modifier word that changes the quantity (half, double)
     - A unit conversion
     - A damaged/missing entry

4. **Assign positional roles in transaction template:**
   ```
   [AGENT] [COMMODITY_MODIFIER?] IDEOGRAM NUMERAL ... ku-ro IDEOGRAM NUMERAL
   ```
   - First word before an ideogram cluster → agent/name
   - Last word before ideogram → commodity modifier or type specifier
   - Word after ku-ro → total or summary term

### 5.3 Step 3: Libation Formula Mapping

**Goal:** Map all variants of the libation formula, identifying fixed vs. variable elements.

**Algorithm:**

1. **Collect all libation inscriptions** (71 in the corpus, types containing "libation").

2. **Align word sequences:**
   Use multiple sequence alignment (simplified — not biological MSA, but positional alignment):
   - Find the most common word at each position across all libation inscriptions
   - Words appearing in > 30% of libation texts at the same relative position → "fixed element"
   - Words appearing in < 10% → "variable element" (probably personal names, specific offerings)

3. **Identify formula components:**
   - **Deity name candidates:** Words that appear in most libation texts but never on administrative tablets
   - **Ritual verb candidates:** Words that appear in libation texts in a consistent position (e.g., always 2nd or 3rd) and never with commodity ideograms
   - **Offering terms:** Words in libation texts that also appear on tablets near commodity ideograms
   - **Site/dedicant names:** Words unique to one or two libation texts, appearing in initial position

4. **Build the template:**
   A formulaic template showing which positions are fixed and which vary.

**Key libation formula words (from corpus analysis):**
- ja-sa-sa-ra-me (freq=3): appears in multiple libation texts → candidate deity name or epithet
- a-ta-i-*301-wa-ja (freq=1 in libation): possible dedicant or ritual description
- i-pi-na-ma (freq=2): appears in libation context → possible offering or ritual term

### 5.4 Step 4: Place Name Identification and Phonetic Anchoring

**Goal:** Confirm known place names and use them to validate phonetic values.

**Algorithm:**

1. **Search for known place names** in the corpus using their AB code sequences:
   - PA-I-TO: [AB03, AB28, AB05] → Phaistos
   - I-DA: [AB28, AB01] → Mount Ida
   - A-DI-KI-TE: [AB08, AB07, AB67, AB04] → Dikte

2. **For each confirmed place name:**
   - Record which sites it appears at (a place name found at its own site is strong confirmation)
   - Record its position in inscriptions (place names often appear in specific slots)
   - Extract phonetic anchors: each sign in the place name gets a confirmed phonetic value

3. **Search for potential new place names:**
   Words that:
   - Appear at only 1-2 sites
   - Appear with multiple commodity ideograms (a place produces various goods)
   - Don't take inflectional suffixes (proper names often don't decline, or decline differently)
   - Match known Cretan place names when read with LB values

### 5.5 Step 5: Anchor Vocabulary Assembly

**Goal:** Combine all evidence sources into a unified anchor vocabulary with confidence scores.

**Algorithm:**

For each word in the corpus, compute an anchor score from multiple evidence streams:

1. **Ideogram evidence** (Step 1): exclusivity × log(co-occurrence count)
2. **Transaction evidence** (Step 2): positional role confidence
3. **Formula evidence** (Step 3): if it appears in the libation formula, is it fixed or variable?
4. **Place name evidence** (Step 4): if it matches a known place name
5. **Pillar 2 evidence** (if available): stem identity (strip inflection to get the base form)
6. **Pillar 3 evidence** (if available): word class (functional words are not commodity names)

Combine into a confidence score:
```
confidence = max(ideogram_score, transaction_score, formula_score, place_name_score)
```

Words with confidence > 0.3 are included in the anchor vocabulary. Each gets a semantic field label and a ranked list of evidence.

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `corpus_context_loader.py` | Load corpus with full sign sequences (including ideograms/numerals), parse inscription structure | Raw corpus JSON | Typed inscription data with sign-type annotations |
| `ideogram_analyzer.py` | Word-ideogram co-occurrence, exclusivity scores, semantic field assignment | Corpus + ideogram inventory | Co-occurrence matrix, semantic field assignments |
| `transaction_analyzer.py` | Parse numeral values, verify ku-ro totals, assign positional roles | Corpus with numerals | Transaction templates, total verification report |
| `formula_mapper.py` | Align libation formula variants, identify fixed/variable elements | Libation inscriptions | Formula atlas with templates |
| `place_name_finder.py` | Search for known place names, extract phonetic anchors, find candidates | Corpus + known place name list | Place name anchors |
| `anchor_assembler.py` | Combine all evidence streams, compute confidence, build anchor vocabulary | All above + optional P2/P3 | Anchor vocabulary |
| `output_formatter.py` | Assemble interface contract JSON | All above | Final JSON |
| `pipeline.py` | Orchestrator | Config | Runs all steps |

---

## 7. Go/No-Go Gates

### Gate 1: ku-ro Total Verification (CRITICAL)

**Test:** Parse numerals in inscriptions containing ku-ro and verify that pre-ku-ro entries sum to the post-ku-ro total.

**Expected:** ≥ 60% of testable inscriptions have correct totals (some will have damage, missing entries, or fractional values that we can't parse).

**On failure:** The numeral parsing is wrong. Review the value assignments for numeral signs. Cross-reference with Bennett's (1950) and Younger's numeral analysis.

### Gate 2: Ideogram Semantic Fields Are Non-Random (CRITICAL)

**Test:** Compare the word-ideogram co-occurrence matrix against a null model (random permutation of ideogram positions).

**Expected:** The real co-occurrence matrix has significantly higher exclusivity scores than the null (many words appear with only one ideogram type, not randomly distributed across ideogram types). Kolmogorov-Smirnov test on exclusivity distribution: real > null at p < 0.01.

### Gate 3: Known Place Name Recovery (HIGH)

**Test:** Search for PA-I-TO, I-DA, and A-DI-KI-TE in the corpus.

**Expected:** At least 2 of 3 are found. PA-I-TO should appear at or near the Phaistos site. I-DA should appear in contexts consistent with a mountain/sanctuary name.

**On failure:** The corpus may use different spellings or the SigLA transcription may not match the expected AB codes. Check for variant spellings.

### Gate 4: Libation Formula Fixed Elements Are Consistent (HIGH)

**Test:** The words identified as "fixed" in the libation formula should appear in > 30% of libation inscriptions. Variable elements should appear in < 10%.

**On failure:** The formula alignment is too loose or too strict. Adjust the fixed/variable thresholds.

### Gate 5: Anchor Vocabulary Cross-Validation with Pillar 3 (MEDIUM)

**Test:** Functional words identified by Pillar 3 (ku-ro, ki-ro, si) should NOT be in the commodity anchor vocabulary. They should be in TRANSACTION:TOTAL, TRANSACTION:DEFICIT, or similar functional semantic fields.

**On failure:** The semantic field assignment is conflating functional words with content words. Add a filter that excludes Pillar 3 functional words from commodity fields.

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Ideograms not reliably parsed from signs_sequence** (SigLA may not consistently label logograms) | HIGH | MEDIUM | Cross-validate logogram identification against the sign_inventory type field. Manual spot-check 20 inscriptions. |
| **Numeral parsing is wrong** (fractional values are uncertain) | HIGH | MEDIUM | Only use integer numeral values (units + tens + hundreds) for total verification. Flag fractions as unparsed. Compare against published numeral analyses. |
| **Libation formula is too variable for alignment** (71 inscriptions may have many unique variants) | MEDIUM | HIGH | Accept a loose template. Identify only the most consistent elements (frequency > 20% threshold). The formula atlas documents variability, not just the consensus. |
| **Place names not in corpus** (PA-I-TO might not appear in SigLA) | MEDIUM | MEDIUM | pa-i-to appears 2 times in the corpus. If key place names are absent, use the phonetic anchoring from the place names that ARE present. |
| **Semantic field assignment is circular** (we assume ideogram meanings from Linear B) | LOW | LOW | The ideogram meanings (FIG, GRAIN, WINE, OLIVE) are established from pictographic evidence (the signs look like what they represent) and are accepted across the field. This is not LB-dependent. |
| **Over-anchoring** (assigning semantic fields to words that happen to co-occur with ideograms by chance) | MEDIUM | MEDIUM | Require statistical significance (Fisher's exact test) for ideogram co-occurrence. Require exclusivity > 0.3 and co-occurrence count ≥ 2. |

---

## 9. Corpus Budget

| Data subset | Used for | Size | Notes |
|-------------|----------|------|-------|
| All inscriptions with ideograms | Ideogram co-occurrence | ~400 inscriptions | Primary semantic signal |
| Inscriptions with ku-ro + numerals | Transaction analysis | 31 inscriptions | Total verification |
| Libation inscriptions | Formula mapping | 71 inscriptions | Ritual vocabulary |
| All words near ideograms | Anchor vocabulary | ~200-300 words | Words within 3 signs of an ideogram |
| Known place names | Phonetic anchoring | 3-5 names | PA-I-TO, I-DA, A-DI-KI-TE, etc. |
| Held-out: Knossos ivory scepter | Validation only | ~119 signs | Reserved |

---

## 10. Relationship to PhaiPhon (Legacy)

### What can be reused

- **Libation table data:** The ancient-scripts-datasets repo contains `libation_tables.json` and `libation_formula_signs.json` from previous work. These can supplement the SigLA corpus data.
- **Sign inventory with ideogram labels:** The SigLA corpus already maps logograms to known ideogram names (FIC, GRA, VINa, OLIV, VIR).

### What must be discarded

- **PhaiPhon's phonetic prior approach** treated the entire corpus as undifferentiated text. Pillar 4 explicitly leverages the non-textual elements (ideograms, numerals) that PhaiPhon ignored.
- **PhaiPhon's single-language framing** is irrelevant here. Pillar 4 is entirely language-independent — the semantic anchoring works regardless of what language Linear A is.

### What changed and why

PhaiPhon treated Linear A as a sequence of phonetic signs to be matched against candidate languages. Pillar 4 recognizes that the inscriptions are structured documents with multiple information channels (text + ideograms + numerals + layout). Exploiting all channels simultaneously produces meaning constraints that are independent of language identification.

---

## 11. Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. **ku-ro total verification succeeds in < 30% of testable inscriptions** — our numeral parsing is fundamentally wrong and cannot be fixed from published literature.
2. **Ideogram co-occurrence exclusivity is not significantly different from random** (KS test p > 0.05) — there is no semantic signal in the word-ideogram adjacency.
3. **Fewer than 10 words can be anchored** with confidence > 0.3 — the corpus is too damaged/sparse for semantic anchoring to work.
4. **More than 40 person-hours spent** without passing Gate 1.

---

## 12. Appendix: Ideogram Semantics Are Script-Independent

### A.1 Why ideogram meanings are reliable

The commodity ideograms in Linear A are **pictographic** — they visually resemble what they represent:
- The FIG sign looks like a fig (or fig branch)
- The GRAIN sign shows a grain stalk
- The WINE sign shows a wine vessel
- The OLIVE sign shows an olive branch
- The VIR sign shows a human figure

These identifications do NOT depend on Linear B or on knowing the language. They are established by:
1. Pictographic resemblance (Evans 1909, Bennett 1950)
2. Archaeological context (tablets found in storage magazines with the corresponding commodities)
3. Consistency across sites and periods
4. Cross-reference with Linear B ideograms (which confirm the pictographic interpretations)

This makes ideogram-based semantic anchoring one of the most reliable tools available for Linear A. The meaning of the IDEOGRAM is known; the question is which WORDS co-occur with it and in what relationship.

### A.2 The transaction template is archaeologically motivated

The administrative structure of Linear A tablets is well-established (Schoep 2002, Younger 2000):
- Most tablets are records of economic transactions: receipts, disbursements, inventories
- The typical format is: name/agent + commodity + quantity, repeated for multiple entries, ending with a total (ku-ro)
- This is confirmed by:
  - Tablet shapes (page-shaped tablets have multiple entries; leaf-shaped have one)
  - Finding locations (tablets found in administrative archives)
  - Seal impressions (associated with bureaucratic control)

The transaction template is not hypothetical — it is observed in the physical archaeology.
