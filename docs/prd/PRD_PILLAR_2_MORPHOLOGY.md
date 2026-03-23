# PRD: Pillar 2 — Morphological Decomposition (Automated Kober)

**Status:** Draft
**Depends on:** Pillar 1 (C-V grid, phonotactic constraints, vowel/consonant inventory)
**Feeds into:** Pillar 3 (distributional grammar), Pillar 5 (multi-source vocab resolution)
**Date:** 2026-03-23
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Decompose the Linear A lexicon into stems and affixes, induce inflectional paradigms, and characterize the morphological system — all from internal distributional evidence, constrained by Pillar 1's phonological model.

This pillar computationally automates what Kober did by hand: discovering that the language is inflected, identifying case endings, and grouping words into paradigm classes — without knowing what language it is.

**Traced to README:** "Automatic stem-affix segmentation... Paradigm induction... Case system mapping... Distinguish inflection from derivation."

---

## 2. Non-goals

- **No phonetic value assignment.** Morphemes are identified by their sign sequences (AB codes), not by phonetic labels.
- **No cognate matching.** No external language data is used to identify morphemes.
- **No semantic interpretation.** We discover that sign-group X has ending -ta and sign-group Y has ending -te — but we do NOT claim "-ta is nominative" or "-te is dative." Semantic labeling is Pillar 4/5's job.
- **No syntax.** Word order and sentence structure are Pillar 3's domain.
- **No re-implementation of Pillar 1.** We consume Pillar 1's outputs; we do not re-derive phonology.

---

## 3. Inputs

### 3.1 From Pillar 1 (interface contract)

The Pillar 1 output JSON (`results/pillar1_output.json`) provides:

| Field | What Pillar 2 uses it for |
|-------|---------------------------|
| `grid.assignments[].{sign_id, consonant_class, vowel_class, confidence}` | Constrain segmentation: affixes should not split within a CV unit; signs in the same grid row share a consonant (informing paradigm alignment) |
| `vowel_inventory.signs[]` | Identify pure vowel signs — potential segmentation points (a bare vowel sign may mark a morpheme boundary in agglutinative morphology) |
| `phonotactics.forbidden_bigrams[]` | Segmentation candidates: a position where a forbidden bigram would result is likely NOT a valid boundary |
| `phonotactics.favored_bigrams[]` | Fixed collocations (like ku-ro) should not be segmented |
| `grid.consonant_count`, `grid.vowel_count` | Used for paradigm alignment: endings in the same vowel column across different paradigms may represent the same grammatical function |

### 3.2 Raw corpus (same as Pillar 1)

**File:** `data/sigla_full_corpus.json` (SigLA v2.0.0)

Relevant corpus statistics for morphological analysis:
- 1,121 words with length ≥ 2 signs (the segmentation-eligible set)
- 834 unique words
- 96 prefix groups with ≥ 2 variants (inflectional candidates from Pillar 1's alternation detector)
- Average word length: 2.51 signs (range: 2-19)
- Top final signs: ja (40 unique words), na (35), re (34), ra (32), ti (30), te (29), ta (29)

### 3.3 Inscription context

Each word occurs within an inscription that has:
- Type (Tablet, Nodule, Roundel, libation_table, etc.)
- Site (Arkhanes, Hagia Triada, Knossos, etc.)
- Co-occurring ideograms and numerals

This contextual information helps distinguish inflection from derivation (Section 5.4) and supports paradigm induction (Section 5.3).

---

## 4. Outputs (Interface Contract)

Pillar 2 produces a JSON output file consumed by Pillar 3 and Pillar 5.

### 4.1 Output schema

```json
{
  "metadata": {
    "pillar": 2,
    "version": "1.0.0",
    "corpus_version": "<SHA-256>",
    "pillar1_version": "<SHA-256 of pillar1 output>",
    "config_hash": "<SHA-256>",
    "timestamp": "ISO-8601",
    "seed": 1234
  },

  "segmented_lexicon": [
    {
      "word_sign_ids": ["AB59", "AB06", "AB37"],
      "segmentation": {
        "stem": ["AB59", "AB06"],
        "suffixes": [["AB37"]],
        "prefixes": [],
        "segmentation_confidence": 0.82
      },
      "frequency": 4,
      "inscription_types": ["Tablet"],
      "method": "morfessor_constrained"
    }
  ],

  "affix_inventory": {
    "suffixes": [
      {
        "signs": ["AB37"],
        "frequency": 30,
        "n_distinct_stems": 18,
        "productivity": 0.75,
        "classification": "inflectional",
        "paradigm_classes": [0, 2]
      }
    ],
    "prefixes": [
      {
        "signs": ["AB08"],
        "frequency": 5,
        "n_distinct_stems": 4,
        "productivity": 0.15,
        "classification": "derivational"
      }
    ]
  },

  "paradigm_table": {
    "n_paradigm_classes": 3,
    "paradigms": [
      {
        "class_id": 0,
        "n_members": 25,
        "slots": [
          {
            "slot_id": 0,
            "ending_signs": ["AB37"],
            "frequency": 15,
            "label": "slot_0"
          },
          {
            "slot_id": 1,
            "ending_signs": ["AB59"],
            "frequency": 10,
            "label": "slot_1"
          }
        ],
        "example_stems": [
          {
            "stem": ["AB59", "AB06"],
            "attested_slots": [0, 1],
            "attested_forms": [
              {"slot": 0, "full_word": ["AB59", "AB06", "AB37"]},
              {"slot": 1, "full_word": ["AB59", "AB06", "AB59"]}
            ]
          }
        ],
        "grid_analysis": {
          "endings_share_consonant_row": true,
          "consonant_class": 3,
          "vowel_classes_attested": [0, 1, 2]
        }
      }
    ]
  },

  "morphological_word_classes": [
    {
      "class_id": 0,
      "label": "declining",
      "description": "Stems that take inflectional suffixes from paradigm classes",
      "n_stems": 45,
      "paradigm_classes": [0, 1, 2]
    },
    {
      "class_id": 1,
      "label": "uninflected",
      "description": "Stems that never appear with any attested suffix",
      "n_stems": 30
    }
  ],

  "diagnostics": {
    "total_words_segmented": 834,
    "words_with_suffixes": 450,
    "words_unsegmented": 384,
    "total_unique_suffixes": 25,
    "inflectional_suffixes": 12,
    "derivational_suffixes": 8,
    "ambiguous_suffixes": 5,
    "mean_paradigm_completeness": 0.45
  }
}
```

### 4.2 What downstream pillars consume

**Pillar 3 (Grammar) uses:**
- `morphological_word_classes` — declining vs. uninflected stems inform word class induction (nouns decline, verbs conjugate, particles don't inflect)
- `paradigm_table` — agreement patterns require knowing which words share paradigm structure
- `segmented_lexicon` — stripped stems are better units for distributional analysis than full inflected forms

**Pillar 5 (Vocab Resolution) uses:**
- `segmented_lexicon` — stems (not inflected forms) are the units to match against candidate language vocabularies
- `affix_inventory` — morphological structure constrains which candidate languages are plausible (agglutinative affixes suggest Anatolian; fusional endings suggest Indo-European)
- `paradigm_table` — paradigm structure is a typological fingerprint

---

## 5. Approach

### 5.1 Step 1: Syllable-Constrained Segmentation

**Goal:** Decompose each word into a stem and zero or more affixes, respecting Pillar 1's phonotactic constraints.

**Why constrained segmentation matters:** In a CV syllabary, each sign represents a full syllable. Morpheme boundaries should align with syllable boundaries — segmenting "in the middle of a sign" is impossible. But morpheme boundaries CAN fall between signs, and the key question is WHERE.

**Algorithm: Constrained Morfessor**

We adapt the Morfessor algorithm (Creutz & Lagus 2005) with phonological constraints:

1. **Input:** All unique words as sign-ID sequences, plus Pillar 1 constraints.

2. **Minimum Description Length (MDL) objective:**
   Morfessor minimizes L(lexicon) + L(corpus | lexicon), where:
   - L(lexicon) = cost of storing the morpheme inventory (stems + affixes)
   - L(corpus | lexicon) = cost of encoding each word as a sequence of morphemes

   This naturally balances between too many morphemes (over-segmentation: every word is its own stem) and too few (under-segmentation: no morphemes, every word is atomic).

3. **Phonological constraints (from Pillar 1):**
   - **Forbidden boundary constraint:** A segmentation point that would create a forbidden bigram at the boundary is penalized (increased description length).
   - **Favored bigram constraint:** Segmenting within a favored bigram (e.g., ku-ro) is penalized.
   - **Pure vowel sign heuristic:** A bare vowel sign (from Pillar 1's vowel inventory) at the start of a suffix may signal an agglutinative morpheme boundary (common in Anatolian languages). This is a soft bonus, not a hard constraint.

4. **Output:** For each word, a segmentation into morphemes. Each morpheme is labeled as stem (longest central morpheme) or affix (shorter peripheral morpheme, prefix or suffix).

**Mathematical basis:**

The MDL cost function:

L_total = L_morphemes + L_corpus

L_morphemes = Σ_{m ∈ M} len(m) × log(|S|)    [cost of storing each morpheme's sign sequence]

L_corpus = -Σ_{w ∈ W} log P(w | M)             [negative log-likelihood of the corpus given the morpheme inventory]

where P(w | M) = Π_{m_i ∈ segmentation(w)} freq(m_i) / Σ freq(m_j)

The phonological penalty term:

L_phon = λ_phon × Σ_{boundaries} penalty(boundary)

where penalty(boundary) = 1 if the boundary creates a forbidden bigram, 0 otherwise. λ_phon is a hyperparameter controlling the strength of the constraint.

**Alternative: BPE with constraints**

If Morfessor proves too slow or unstable on the small corpus:

Byte Pair Encoding (Sennrich et al. 2016) iteratively merges the most frequent adjacent sign pair. We modify it:
- Never merge across a phonotactic boundary (forbidden bigram)
- Stop merging when the most frequent pair has frequency < min_merge_freq (prevents over-merging in a small corpus)
- After BPE, extract the merge operations as a hierarchy of morpheme formation

The BPE approach is simpler but less principled than Morfessor. We implement both and compare outputs.

### 5.2 Step 2: Suffix/Prefix Extraction

**Goal:** From the segmented lexicon, extract the inventory of attested affixes and compute their productivity.

**Algorithm:**

1. **Collect all suffixes and prefixes** from the segmented lexicon.

2. **Compute statistics for each affix:**
   - Frequency: total occurrences across the corpus
   - Type count: number of distinct stems it attaches to (n_distinct_stems)
   - Productivity: n_distinct_stems / total_possible_stems (what fraction of stems can take this affix)

3. **Filter noise:** Affixes that appear with only 1 stem are likely not real morphemes — they may be part of the stem that was over-segmented. Require n_distinct_stems ≥ 2.

### 5.3 Step 3: Paradigm Induction

**Goal:** Group stems that share the same set of possible endings into paradigm classes (like Latin's 5 declension classes).

**Algorithm: Paradigm clustering**

1. **Build a stem × suffix incidence matrix I:**
   I[s, a] = 1 if stem s is attested with suffix a, 0 otherwise.

2. **Cluster stems by their suffix pattern:**
   Two stems belong to the same paradigm class if they take the same set of suffixes (or a highly overlapping set).

   Formally: define the paradigm signature of stem s as the set {a : I[s, a] = 1}.

   Cluster stems with identical or near-identical paradigm signatures. "Near-identical" = Jaccard similarity > threshold (default 0.5).

3. **For each paradigm class:**
   - List the slots (attested suffix positions)
   - Count completeness: what fraction of stems × slots is actually attested? (Paradigms in a small corpus will be highly incomplete.)
   - List example stems with their attested forms.

4. **Grid-informed paradigm alignment (using Pillar 1):**
   Within a paradigm class, if two endings share a consonant row in the C-V grid (from Pillar 1), they likely differ only in vowel and represent different case forms of the same declension. If two endings share a vowel column, they may represent the same case across different paradigm classes.

   This alignment is diagnostic, not deterministic — it provides evidence for how many grammatical cases exist.

**Mathematical basis:**

The stem × suffix matrix I has dimensions |stems| × |suffixes|.

For paradigm clustering, we compute pairwise Jaccard distances:

d(s_i, s_j) = 1 - |sig(s_i) ∩ sig(s_j)| / |sig(s_i) ∪ sig(s_j)|

where sig(s) = {a : I[s, a] = 1} is the paradigm signature.

Cluster using agglomerative clustering with average linkage and a distance threshold t (optimized via silhouette score).

The number of paradigm classes P is determined by model selection (silhouette score over t).

### 5.4 Step 4: Inflection vs. Derivation Classification

**Goal:** Distinguish inflectional affixes (case, number, gender) from derivational affixes (word-formation).

**Criteria (from morphological typology):**

| Property | Inflectional | Derivational |
|----------|-------------|--------------|
| Productivity | High (applies to many stems) | Low (applies to few stems) |
| Paradigm regularity | Regular (fills paradigm slots predictably) | Irregular (no paradigm pattern) |
| Semantic consistency | Same grammatical function across stems | Changes word meaning/class |
| Corpus distribution | High frequency | Lower frequency |
| Position | Outermost (closest to word edge) | Inner (between stem and inflection) |

**Algorithm:**

1. **Productivity score:** productivity = n_distinct_stems / max(n_distinct_stems across all affixes)
   - High productivity (> 0.3) → likely inflectional
   - Low productivity (< 0.1) → likely derivational

2. **Paradigm regularity:** Does the affix fill a consistent slot in a paradigm?
   - If the affix appears in exactly one slot across multiple paradigm classes → inflectional
   - If it appears sporadically with no paradigm pattern → derivational

3. **Frequency-type ratio:** freq / n_distinct_stems
   - High ratio (appears many times with few stems) → stem-specific, likely part of a fixed expression
   - Moderate ratio → balanced, likely inflectional
   - Low ratio (appears few times but with many stems) → rare but productive, might be derivational

4. **Classify:** Combine criteria with a simple scoring rule (not a model — with this much data, a model would overfit):
   - If productivity > 0.3 AND paradigm_regular → "inflectional"
   - If productivity < 0.1 OR not paradigm_regular → "derivational"
   - Otherwise → "ambiguous"

### 5.5 Step 5: Morphological Word-Class Hints

**Goal:** Provide Pillar 3 with hints about which stems are nouns (decline), verbs (conjugate), or particles (don't inflect).

**Heuristics (no external language knowledge):**

1. **Uninflected words:** Stems that never appear with any suffix are candidates for particles, prepositions, or proper names. These form the "uninflected" class.

2. **Declining stems:** Stems that take inflectional suffixes from paradigm classes are candidates for nouns/adjectives. If the paradigm has 3+ slots, the language has a case system and these stems decline.

3. **Conjugating stems:** If some stems take a DIFFERENT set of affixes than declining stems (a separate paradigm family), they may be verbs. This is only detectable if the corpus contains verb forms, which is uncertain for administrative texts.

4. **Inscription-type evidence:** Stems that appear predominantly on libation tables (ritual texts) are more likely to include verbs (ritual actions) than stems on commodity tablets (mostly nouns).

**Output:** Each stem gets a `word_class_hint`: "declining", "conjugating", "uninflected", or "unknown".

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `pillar1_loader.py` | Load and validate Pillar 1 output JSON | JSON file | Typed dataclasses |
| `segmenter.py` | Constrained Morfessor + BPE segmentation | Corpus + P1 constraints | Segmented lexicon |
| `affix_extractor.py` | Extract suffix/prefix inventory with productivity | Segmented lexicon | Affix inventory |
| `paradigm_inducer.py` | Stem × suffix clustering, paradigm class induction | Segmented lexicon + grid | Paradigm table |
| `inflection_classifier.py` | Inflectional vs. derivational classification | Affix inventory + paradigms | Classified affixes |
| `word_class_hinter.py` | Morphological word-class hints | Paradigms + corpus context | Word class labels |
| `output_formatter.py` | Assemble interface contract JSON | All above | Final JSON |
| `pipeline.py` | Orchestrator | Config | Runs all steps |

---

## 7. Go/No-Go Gates

### Gate 1: Known-Answer Test on Latin (CRITICAL)

**Test:** Run the full Pillar 2 pipeline on a Latin corpus (where the morphological system is known).

**Expected results:**
- Segmentation identifies known Latin suffixes (-us, -um, -i, -o, -ae, -am, -is, -ibus, etc.)
- Paradigm induction recovers ≥ 3 of Latin's 5 declension classes (accept 3-7)
- Inflection/derivation classification correctly labels case endings as inflectional
- Productivity ranking puts high-frequency endings (-us, -um, -ae) above rare ones

**Data source:** Latin word list from published grammar, transliterated into an artificial CV syllabary (to match the syllabographic constraint). E.g., Latin "dominus" → "do-mi-nu-su" in a test syllabary. This preserves the morphological structure while matching the input format.

**On failure:** If the pipeline fails to recover ≥ 3 declension classes on Latin, the paradigm induction algorithm is too weak. Consider:
- Lowering the Jaccard threshold for paradigm merging
- Increasing the Latin test corpus size
- Trying hierarchical paradigm induction (first merge the most similar pairs, then groups)

### Gate 2: Null Test on Isolating Language (CRITICAL)

**Test:** Run on a Mandarin Chinese corpus (an isolating language with virtually no inflectional morphology), transliterated into a CV syllabary.

**Expected results:**
- Very few suffixes identified (< 5)
- No paradigm classes with ≥ 3 slots (no rich inflection)
- Nearly all stems classified as "uninflected"

**On failure:** The pipeline is hallucinating morphology. Review the segmentation algorithm — Morfessor's MDL objective should naturally avoid over-segmenting an isolating language, since the cost of the morpheme inventory outweighs the corpus compression benefit.

### Gate 3: Linear A Internal Consistency (HIGH)

**Test:** Run on the real Linear A corpus and check internal consistency:
- Identified suffixes should match the top final signs from corpus analysis (ja, na, re, ra, ti, te, ta)
- Paradigm classes should produce attested word forms (no paradigm slot that generates a word not in the corpus)
- The number of paradigm classes should be between 2 and 10 (fewer than 2 = no morphology detected; more than 10 = over-fragmentation)

### Gate 4: Pillar 1 Constraint Satisfaction (HIGH)

**Test:** Verify that all segmentation points respect Pillar 1 constraints:
- No segmentation creates a forbidden bigram at the boundary
- No segmentation splits within a favored bigram
- Affixes align with grid structure (endings in the same paradigm slot should share a consonant row more often than chance)

### Gate 5: Stability (MEDIUM)

**Test:** Run with different Morfessor hyperparameters (λ_phon ∈ {0, 1, 5, 10}) and verify:
- Core suffixes (top 5 by frequency) are identified in ≥ 4/5 configurations
- Number of paradigm classes stable to ±2

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Corpus too small for Morfessor** (834 unique words is tiny for MDL-based segmentation) | HIGH | HIGH | Fall back to BPE. Also try simple suffix-stripping (just use the alternation pairs from Pillar 1 as the suffix inventory). Compare all three approaches. |
| **Words too short for meaningful segmentation** (42% are 2-sign, meaning stem + 1 suffix at most) | HIGH | HIGH | For 2-sign words, the only possible segmentation is stem(1) + suffix(1). This is fine — it still reveals suffix patterns. 3+ sign words provide more information. |
| **Paradigm sparsity** (most stems appear with only 1-2 of their possible endings) | HIGH | HIGH | Use the Jaccard threshold to group stems with even partial overlap. Accept that paradigms will be highly incomplete (mean completeness ~30-40%). |
| **No verb morphology** (administrative texts may contain very few verbs) | MEDIUM | HIGH | Libation table texts likely contain verb forms. Weight these inscriptions more heavily in the analysis. If no verb-like paradigms emerge, report this as a finding (morphological evidence is consistent with a nominal-heavy language). |
| **Pillar 1 grid limitations** (V=1 in current output degrades grid-informed alignment) | MEDIUM | CERTAIN | Grid alignment is diagnostic, not required. Paradigm induction works on suffix patterns alone. Grid alignment becomes more valuable if Pillar 1 is rerun with V=4. Design to work without grid info and add it as an optional enrichment. |
| **Conflation of homophonous signs** (different signs that happen to look similar in AB codes) | LOW | LOW | Use AB codes strictly. If sign variants exist (e.g., ra vs ra2), treat them as distinct signs. |

---

## 9. Corpus Budget

| Data subset | Used for | Size | Notes |
|-------------|----------|------|-------|
| All unique words (len ≥ 2) | Segmentation | 834 words | Primary analysis set |
| All word tokens (len ≥ 2) | Frequency-weighted paradigm induction | 1,121 tokens | Type vs. token distinction matters |
| Inscription context | Word-class hints | 879 inscriptions | Only type/site metadata used |
| Pillar 1 alternation pairs | Seed suffix candidates | 137 pairs | From Pillar 1 output |
| Held-out: Knossos ivory scepter | Validation only | ~119 signs | Reserved |

---

## 10. Relationship to PhaiPhon (Legacy)

### What can be reused

- **PhaiPhon5 BPE segmenter:** PhaiPhon5 began implementing a BPE-based segmenter for morphological analysis. The BPE implementation can be ported and adapted. However, it was never completed (scaffolding only, implementation not started).
- **Morfessor library:** PhaiPhon5 listed `morfessor` as a dependency (pip, pure Python). This is still appropriate.

### What must be discarded

- **PhaiPhon5's 10-dimensional fingerprint approach:** PhaiPhon5 aimed to produce a morphological "fingerprint" for language comparison (10 typological features). This is a Pillar 5 concern, not Pillar 2. Pillar 2 produces raw morphological data; typological interpretation comes later.
- **PhaiPhon5's known-answer test framework** (Turkish-Finnish close, Turkish-Arabic far): This tested typological similarity, not morphological correctness. Pillar 2 needs correctness tests (Latin declensions, Mandarin isolation).

### What changed and why

PhaiPhon5 asked "does Linear A's morphological fingerprint match candidate languages?" — a cognate-first framing. Pillar 2 asks "what IS Linear A's morphological system?" — a structure-first framing. The morphological analysis is an end in itself (understanding the grammar), not a means to language identification.

---

## 11. Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. **Known-answer test on Latin fails to recover ≥ 3 declension classes** after trying both Morfessor and BPE with 3 different hyperparameter settings.
2. **Null test on Mandarin produces ≥ 3 paradigm classes with ≥ 3 slots** — the method is hallucinating morphology in an isolating language.
3. **Internal consistency check fails:** identified suffixes do NOT overlap with the top 10 final signs in the corpus (the method is finding structure unrelated to actual word endings).
4. **More than 60 person-hours spent** on Pillar 2 without passing Gate 1.
