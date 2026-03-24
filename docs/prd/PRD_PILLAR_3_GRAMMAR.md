# PRD: Pillar 3 — Distributional Grammar (Word Classes and Syntax)

**Status:** Draft
**Depends on:** Pillar 2 (segmented lexicon, paradigm table, morphological word-class hints)
**Also uses:** Pillar 1 (C-V grid, phonotactic constraints)
**Feeds into:** Pillar 5 (multi-source vocabulary resolution)
**Date:** 2026-03-23
**Authors:** Alvin / Claude (design session)

---

## 1. Objective

Induce grammatical categories (word classes), discover word order patterns, detect agreement phenomena, and identify functional words — all from internal distributional evidence, combining positional statistics with Pillar 2's morphological structure.

The output is a grammar sketch: what are the parts of speech, how are they ordered, and what functional words glue them together — without knowing what language Linear A is.

**Traced to README:** "Use distributional semantics — words that appear in the same contexts belong to the same class — to induce grammatical categories without any external language knowledge."

---

## 2. Non-goals

- **No semantic interpretation.** We discover that word class A tends to precede word class B — we do NOT claim "A is subject and B is verb." Semantic labeling is Pillar 4/5's job.
- **No cognate matching.** No external language data is used.
- **No phonetic value assignment.** We operate on sign IDs and morphological labels from Pillars 1-2.
- **No translation.** The grammar sketch describes structure, not meaning.

---

## 3. Inputs

### 3.1 From Pillar 2 (primary)

**File:** `results/pillar2_output.json`

| Field | What Pillar 3 uses it for |
|-------|---------------------------|
| `segmented_lexicon[].segmentation.stem` | Stems (not inflected forms) are the units for distributional analysis — reduces vocabulary sparsity |
| `segmented_lexicon[].segmentation.suffixes` | Suffix identity constrains word class (words with the same suffix pattern behave grammatically alike) |
| `paradigm_table.paradigms[]` | Paradigm class membership is a strong word-class signal (all members of a paradigm class are likely the same part of speech) |
| `morphological_word_classes[]` | Declining/uninflected hints seed the word-class induction |
| `affix_inventory.suffixes[].classification` | Inflectional suffixes mark grammatically active words |

Pillar 2 results (as measured):
- 787 segmented words (717 with suffixes, 70 unsegmented)
- 69 unique suffixes (28 inflectional)
- 39 paradigm classes
- 364 declining stems, 63 uninflected, 114 unknown

### 3.2 From Pillar 1 (supplementary)

**File:** `results/pillar1_output.json`

| Field | Use |
|-------|-----|
| `grid.assignments[]` | Signs in the same grid row share a consonant — distributional similarity between grid-row-mates informs word class boundaries |
| `phonotactics.favored_bigrams[]` | Fixed collocations (like ku-ro) should be treated as single distributional units |

### 3.3 Raw corpus

**File:** `data/sigla_full_corpus.json` (SigLA v2.0.0)

Relevant statistics for grammar induction:
- 193 inscriptions with ≥ 3 words (the word-order-eligible set)
- 131 with ≥ 4 words, 99 with ≥ 5 words
- 927 unique word-level bigrams
- Top last-position word: ku-ro (16 occurrences — "total" marker)
- Top functional word candidates: si (11), a (10), ku (10), i (8), ro (8), ta (7)
- Inscription types: 166 multi-word Tablets, 19 multi-word libation tables

### 3.4 Inscription context (same as Pillar 2)

Each inscription has type, site, and co-occurring ideograms/numerals. These provide context for word class induction (e.g., words always adjacent to numerals are likely quantity modifiers or commodity names).

---

## 4. Outputs (Interface Contract)

### 4.1 Output schema

```json
{
  "metadata": {
    "pillar": 3,
    "version": "1.0.0",
    "corpus_version": "<SHA-256>",
    "pillar1_version": "<SHA-256>",
    "pillar2_version": "<SHA-256>",
    "config_hash": "<SHA-256>",
    "timestamp": "ISO-8601",
    "seed": 1234
  },

  "word_classes": {
    "n_classes": 5,
    "method": "distributional_clustering_with_morphological_constraints",
    "classes": [
      {
        "class_id": 0,
        "suggested_label": "content_word_A",
        "n_members": 120,
        "morphological_profile": "declining",
        "positional_profile": {
          "mean_position": 0.35,
          "initial_rate": 0.40,
          "final_rate": 0.10,
          "pre_numeral_rate": 0.60
        },
        "top_members": [
          {"stem": ["AB59", "AB06"], "frequency": 8},
          {"stem": ["AB77", "AB03"], "frequency": 6}
        ],
        "distributional_signature": {
          "common_predecessors": ["class_3", "class_4"],
          "common_successors": ["class_1", "class_2"]
        }
      }
    ]
  },

  "word_order": {
    "dominant_pattern": "unknown",
    "evidence_strength": "weak",
    "pairwise_class_order": [
      {
        "class_a": 0,
        "class_b": 1,
        "a_before_b_count": 45,
        "b_before_a_count": 12,
        "direction_ratio": 3.75,
        "p_value": 0.001
      }
    ],
    "position_in_inscription": [
      {
        "class_id": 0,
        "mean_relative_position": 0.35,
        "std_relative_position": 0.20
      }
    ]
  },

  "agreement_patterns": [
    {
      "word_pair_classes": [0, 2],
      "shared_suffix_rate": 0.65,
      "expected_by_chance": 0.15,
      "p_value": 1.2e-8,
      "interpretation": "Words of class 0 and class 2 tend to share suffixes when adjacent — possible noun-adjective agreement"
    }
  ],

  "functional_words": [
    {
      "word_sign_ids": ["AB81", "AB02"],
      "reading": "ku-ro",
      "frequency": 34,
      "n_inscriptions": 31,
      "positional_profile": {
        "initial_rate": 0.06,
        "final_rate": 0.47,
        "pre_numeral_rate": 0.0
      },
      "classification": "structural_marker",
      "evidence": "Overwhelmingly final-position; known to mean 'total' from context"
    }
  ],

  "grammar_sketch": {
    "is_inflected": true,
    "estimated_word_classes": 5,
    "word_order_type": "unknown",
    "has_agreement": true,
    "n_functional_words": 8,
    "summary": "Linear A shows distributional evidence for N word classes with morphological inflection. Word order is [X]. Agreement patterns suggest [Y]. Functional words include ku-ro (total-marker, final position) and [others]."
  },

  "diagnostics": {
    "inscriptions_used_for_word_order": 193,
    "word_bigrams_analyzed": 927,
    "stems_with_distributional_profile": 541,
    "clustering_silhouette_score": 0.35,
    "agreement_pairs_tested": 10,
    "agreement_pairs_significant": 3
  }
}
```

### 4.2 What downstream pillars consume

**Pillar 5 (Vocab Resolution) uses:**
- `word_classes` — word class constrains which candidate language lexical entries are plausible matches (a "content_word_A" stem should match a noun/adjective in the candidate language, not a conjunction)
- `functional_words` — functional words are typically NOT borrowed, so they should match the core language stratum rather than a contact language
- `grammar_sketch` — typological features (word order type, agreement, inflection) constrain which language families are compatible

---

## 5. Approach

### 5.1 Step 1: Build Distributional Profiles

**Goal:** For each stem (from Pillar 2's segmented lexicon), compute a distributional profile: what contexts does it appear in?

**Algorithm:**

1. **Context features for each stem s:**

   a. **Left context (word-level):** For each occurrence of s in an inscription, record the stem of the immediately preceding word (or `<BOS>` if s is first). Build a left-context frequency vector.

   b. **Right context (word-level):** Same but for the following word (or `<EOS>` if s is last).

   c. **Positional features:**
      - `relative_position` = index of word in inscription / total words in inscription (0.0 = first, 1.0 = last)
      - `is_initial` = 1 if first word
      - `is_final` = 1 if last word
      - `is_pre_numeral` = 1 if followed by a numeral or ideogram+numeral

   d. **Morphological features (from Pillar 2):**
      - `n_attested_suffixes` = how many different suffixes this stem takes
      - `paradigm_class` = which paradigm class this stem belongs to (or -1 if uninflected)
      - `word_class_hint` = declining/uninflected/unknown from Pillar 2

   e. **Inscription-type features:**
      - `tablet_rate` = fraction of occurrences on Tablets
      - `libation_rate` = fraction of occurrences on libation tables/vessels
      - `other_rate` = fraction on other types

2. **Aggregate into a feature vector per stem:**
   The distributional profile of stem s is a vector combining:
   - Left-context PMI scores (top 20 context stems by PMI)
   - Right-context PMI scores (top 20)
   - Positional features (3-4 scalar values)
   - Morphological features (2-3 scalar values)
   - Inscription-type features (3 scalar values)

   Total vector dimension: ~50 features per stem (variable — depends on context vocabulary size)

**Mathematical basis:**

Pointwise Mutual Information for context:

PMI(stem_s, context_c) = log2(P(s, c) / (P(s) × P(c)))

where:
- P(s, c) = count(s in context c) / total_context_pairs
- P(s) = count(s) / total_stems
- P(c) = count(c) / total_contexts

High PMI = the stem and context co-occur more than expected.

We use Positive PMI (PPMI): max(0, PMI) — negative PMI values are noisy and uninformative.

### 5.2 Step 2: Word Class Induction via Clustering

**Goal:** Cluster stems into grammatical classes based on distributional similarity.

**Algorithm:**

1. **Build the stem × feature matrix X:**
   Rows = stems (N ≈ 541 stems with enough data), Columns = distributional features

2. **Dimensionality reduction:**
   Apply Truncated SVD (Latent Semantic Analysis) to reduce X to d dimensions (d = 10-20, selected by explained variance threshold of 80%).

   This denoises the sparse PMI matrix and captures the main axes of distributional variation.

3. **Clustering:**
   Apply agglomerative clustering with Ward linkage on the reduced representation.

   **Model selection for k (number of word classes):**
   - Silhouette score for k = 2, 3, ..., 15
   - Gap statistic (compare within-cluster variance to null model)
   - Morphological coherence: for each k, measure what fraction of each cluster shares the same Pillar 2 word-class hint (declining/uninflected). Higher coherence = better k.

   Select k that maximizes a weighted combination:
   score(k) = 0.4 × silhouette(k) + 0.3 × gap(k) + 0.3 × morphological_coherence(k)

4. **Label clusters:**
   Each cluster gets a descriptive label based on its dominant morphological profile:
   - If > 60% of members are "declining" → `content_word_A` (likely nouns/adjectives)
   - If > 60% of members are "uninflected" → `functional` or `particle`
   - Otherwise → `content_word_B`, `content_word_C`, etc.

**Constraint from Pillar 2:**
Stems in the same paradigm class should be in the same word class (or a very closely related one). If clustering places paradigm-mates in different word classes, penalize that split — it suggests the clustering granularity is too fine.

### 5.3 Step 3: Word Order Discovery

**Goal:** Determine the dominant word order pattern from multi-word inscriptions.

**Algorithm:**

1. **Assign word classes to every word in every multi-word inscription** (using the clustering from Step 2).

2. **Build a class × class precedence matrix P:**
   P[i, j] = count of word-class-i immediately preceding word-class-j across all inscriptions.

3. **For each class pair (i, j), compute directionality:**
   direction_ratio(i, j) = P[i, j] / P[j, i]

   If direction_ratio >> 1: class i consistently precedes class j.
   If direction_ratio ≈ 1: no consistent order.

   **Binomial test for significance:**
   Under the null hypothesis of no order preference: P(i precedes j) = 0.5
   n = P[i, j] + P[j, i], k = P[i, j]
   p_value = binomial_test(k, n, 0.5)

4. **Aggregate into a word order hypothesis:**
   - If content words consistently precede functional words → head-initial features
   - If functional words consistently precede content words → head-final features
   - Check if the pattern is consistent with known typologies (SOV, SVO, VSO)

5. **Position-in-inscription analysis:**
   For each word class, compute the mean relative position (0 = first, 1 = last).
   - Classes with low mean position tend to be sentence-initial (possible subjects or topic markers)
   - Classes with high mean position tend to be sentence-final (possible verbs in SOV, or totals/summaries)

**Caveats:**
- Administrative tablets may not reflect natural sentence order (they may have list structure: name + commodity + quantity)
- Libation tables are more likely to have natural clause structure
- Analyze tablet and libation inscriptions separately and compare

### 5.4 Step 4: Agreement Pattern Detection

**Goal:** Discover if adjacent words share morphological features (case/number/gender agreement).

**Algorithm:**

1. **For each pair of adjacent words in the corpus:**
   If both have suffixes (from Pillar 2), check whether their suffixes match.

2. **Build a word-class-pair agreement matrix:**
   For each pair of word classes (i, j), compute:
   - n_adjacent = number of times class-i and class-j are adjacent
   - n_same_suffix = number of times they share the same suffix when adjacent
   - same_suffix_rate = n_same_suffix / n_adjacent
   - expected_rate = probability of suffix match by chance (based on corpus suffix frequencies)

3. **Statistical test:**
   Binomial test: P(match) > expected_rate
   Bonferroni correction across all class pairs.

4. **Interpretation:**
   If class-pair (A, B) shows significantly elevated suffix agreement:
   - If A is a content word class and B is a different content word class → possible noun-adjective agreement
   - If within the same class → possible coordination or apposition
   - Agreement patterns constrain the grammar sketch (e.g., "class A and class B agree in suffix" suggests they share a grammatical category like case)

### 5.5 Step 5: Functional Word Identification

**Goal:** Identify high-frequency, low-semantic-content words that serve grammatical functions (articles, prepositions, conjunctions, discourse markers).

**Algorithm:**

1. **Candidate selection criteria (all must hold):**
   - Length ≤ 2 signs (functional words tend to be short)
   - Frequency ≥ 5 (must be common enough to be functional)
   - Appears in ≥ 5 different inscriptions (not a repetition artifact of one tablet)
   - Classified as "uninflected" or "unknown" by Pillar 2 (functional words typically don't decline)

2. **Positional profiling:**
   For each candidate:
   - initial_rate: fraction of occurrences in first position
   - final_rate: fraction in last position
   - pre_numeral_rate: fraction immediately before a numeral/ideogram

3. **Classification heuristics:**
   - `structural_marker`: high final_rate (> 0.3) → probably a totaling/summary word (like ku-ro)
   - `relator`: appears between two content words with high consistency → possibly a preposition or conjunction
   - `determiner`: consistently precedes the same word class → possibly an article or demonstrative
   - `particle`: no strong positional pattern, appears sporadically → discourse particle or conjunction

4. **Known functional words (from previous scholarship):**
   - ku-ro (AB81-AB02): "total" — final position, before sum lines
   - ki-ro (AB67-AB02): possibly "deficit" or "owed" — also final position
   - These serve as validation anchors: if the algorithm identifies them independently, it's working

---

## 6. Components

| Module | Responsibility | Input | Output |
|--------|---------------|-------|--------|
| `profile_builder.py` | Build distributional profiles (PPMI, positional, morphological features) | Corpus + P1/P2 outputs | Stem × feature matrix |
| `word_class_inducer.py` | SVD + agglomerative clustering, model selection for k | Feature matrix + P2 hints | Word class assignments |
| `word_order_analyzer.py` | Class precedence matrix, directionality tests, position analysis | Word classes + corpus | Word order hypothesis |
| `agreement_detector.py` | Adjacent suffix matching, agreement rate tests | Word classes + P2 lexicon | Agreement patterns |
| `functional_word_finder.py` | Candidate selection, positional profiling, classification | Corpus + word classes | Functional word inventory |
| `grammar_sketch_builder.py` | Synthesize all outputs into a coherent grammar sketch | All above | Grammar sketch JSON |
| `output_formatter.py` | Assemble interface contract JSON | All above | Final JSON |
| `pipeline.py` | Orchestrator | Config | Runs all steps |

---

## 7. Go/No-Go Gates

### Gate 1: Known-Answer Test on Latin (CRITICAL)

**Test:** Run the full Pillar 3 pipeline on a Latin corpus (with Pillar 1+2 outputs from the Latin test fixtures).

**Expected results:**
- Word class induction separates nouns from uninflected words (particles, prepositions) with Adjusted Rand Index > 0.3 against known Latin POS tags.
- Word order analysis: Latin has relatively free word order but SOV tendency. The pipeline should NOT find strong VSO or SVO signal. Direction ratios should be moderate (< 3) for most class pairs.
- Agreement detection: Latin noun-adjective pairs should show elevated suffix agreement rate (same case ending).
- Functional word identification: Latin conjunctions (et, -que, sed) and prepositions (in, ad, cum) should be identified as functional if present in the corpus.

### Gate 2: Null Test on Random Data (CRITICAL)

**Test:** Run on a corpus where words are randomly shuffled across inscriptions (destroying word-order and adjacency structure but preserving word frequencies).

**Expected results:**
- Word class induction still works (it uses morphological features which aren't affected by shuffling), but:
- Word order analysis should find NO significant directional patterns (all direction ratios ≈ 1, no p-values below threshold)
- Agreement detection should find NO significant agreement patterns (shuffling destroys real adjacency)

### Gate 3: ku-ro Rediscovery (HIGH)

**Test:** Run on the real Linear A corpus. The functional word identifier should independently identify ku-ro (AB81-AB02) as a structural marker based on:
- High frequency (34 occurrences)
- Final-position dominance (47% final)
- Short (2 signs)
- Uninflected

**On failure:** If ku-ro is not identified, the functional word criteria are too strict. Relax thresholds.

### Gate 4: Morphological Coherence (HIGH)

**Test:** In the induced word classes, ≥ 70% of each cluster's members should share the same Pillar 2 word-class hint (declining/uninflected). If word classes cut across morphological boundaries randomly, the distributional clustering is not capturing grammatical structure.

### Gate 5: Stability (MEDIUM)

**Test:** Run with k ∈ {3, 5, 7, 9} word classes. Core findings should be stable:
- ku-ro identified as functional word in all runs
- The largest word class is always "declining" content words
- Word order direction ratios for the top 3 class pairs are qualitatively consistent

---

## 8. Risks and Mitigations

| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| **Too few multi-word inscriptions** (193 with ≥3 words) for reliable word order analysis | HIGH | HIGH | Analyze tablets and libation tables separately. Libation tables (19 multi-word) may be too few alone. Report confidence intervals on direction ratios. Accept "inconclusive" if the data doesn't support a strong word-order claim. |
| **Administrative text structure ≠ natural syntax** (tablets are lists, not sentences) | HIGH | HIGH | Tablet "word order" may reflect list structure (name, commodity, quantity) rather than grammatical order. Distinguish list-structured tablets from free-text inscriptions. Weight libation tables and non-administrative inscriptions more heavily. |
| **Distributional profiles are too sparse** (most stems appear < 5 times) | HIGH | HIGH | Use SVD to denoise. Group rare stems by paradigm class (from Pillar 2) to pool their distributional evidence. Accept that rare stems get coarse word-class assignments. |
| **Agreement is invisible in a CV syllabary** (if agreement is by vowel and we can't distinguish vowels well) | MEDIUM | MEDIUM | Pillar 1's V=1 limitation means we can only detect agreement via exact suffix match, not vowel-class match. This catches full-suffix agreement but misses partial (vowel-only) agreement. Design to work with exact match; enhance if Pillar 1 is rerun with V>1. |
| **Over-clustering word classes** (too many classes = no generalization) | MEDIUM | MEDIUM | Use silhouette score + morphological coherence for model selection. Cap k at 10. Report the full silhouette curve for manual inspection. |
| **Functional words misidentified** (high-frequency content words classified as functional) | MEDIUM | LOW | Cross-check with Pillar 2: functional words should be uninflected. If a "functional word" takes inflectional suffixes, it's probably a common content word (like "grain" in administrative texts). |

---

## 9. Corpus Budget

| Data subset | Used for | Size | Notes |
|-------------|----------|------|-------|
| All inscriptions with ≥2 words | Distributional profiles (context features) | 520 inscriptions | Left/right context pairs |
| Inscriptions with ≥3 words | Word order analysis | 193 inscriptions | Need at least 3 words for a word-order triple |
| All adjacent word pairs | Agreement detection | ~927 unique bigrams | Testing suffix co-variation |
| All words with frequency ≥5 | Functional word candidates | ~30-40 words | Short, frequent, widespread |
| Pillar 2 segmented lexicon | Stem-based analysis | 787 entries | Primary vocabulary |
| Held-out: Knossos ivory scepter | Validation only | ~119 signs | Reserved |

---

## 10. Relationship to PhaiPhon (Legacy)

### What can be reused

- **Corpus loading infrastructure:** Same SigLA corpus, same loader code (via Pillar 1).
- **No direct PhaiPhon3-5 code applies.** PhaiPhon had no grammar induction component.

### What must be discarded

- **All cognate-based analysis.** Pillar 3 is purely internal — no external language comparison.
- **PhaiPhon's language-ranking framework.** Word order and morphological type are not used to rank candidate languages (that's Pillar 5's job).

### What changed and why

PhaiPhon never attempted grammar induction. This is entirely new work. The closest analog is PhaiPhon5's morphological analysis, but that aimed to produce a typological fingerprint for language comparison. Pillar 3 aims to produce a grammar sketch for understanding the language itself.

---

## 11. Kill Criteria

This approach should be ABANDONED (not iterated) if any of:

1. **Known-answer test on Latin: word class induction ARI < 0.15** against known POS tags after 3 attempts with different clustering methods (the distributional signal is too weak to recover grammatical categories).
2. **Null test: random-shuffled data produces significant word order patterns** (≥ 3 class pairs with p < 0.01) — the method is detecting spurious structure.
3. **ku-ro is not in the top 10 functional word candidates** — the functional word criteria are fundamentally misaligned with what functional words look like in this corpus.
4. **More than 50 person-hours spent** on Pillar 3 without passing Gate 1.

---

## 12. Appendix: Distributional Hypothesis in Low-Resource Settings

### A.1 Why distributional clustering works with small corpora

The distributional hypothesis (Harris 1954, Firth 1957) states that words occurring in similar contexts belong to similar categories. In modern NLP, this underpins word embeddings (word2vec, GloVe) trained on billions of tokens. Can it work with 3,518 syllabogram tokens?

**Yes, with important caveats:**

1. **Feature sparsity requires dimensionality reduction.** The raw PPMI matrix will be extremely sparse. SVD (Turney & Pantel 2010) is the standard remedy — it discovers latent dimensions that capture the main axes of distributional variation even from sparse data.

2. **Morphological constraints dramatically reduce the effective problem size.** We're not clustering arbitrary words — we're clustering stems that already have morphological labels from Pillar 2. A stem's paradigm class (declining vs. uninflected) is a strong prior on its word class. The distributional signal needs to refine this prior, not discover it from scratch.

3. **Administrative texts have repetitive structure.** The same commodity names appear with the same functional words in the same positions across many tablets. This repetition creates stronger distributional signal per token than natural language text would.

4. **We're looking for 3-7 classes, not 50.** Inducing fine-grained POS tags (noun vs. proper noun vs. gerund) requires massive data. Inducing coarse classes (content word vs. functional word vs. uninflected particle) is feasible with hundreds of distinct stems.

### A.2 Relation to tablet structure

Linear A tablets have a semi-formulaic structure (Schoep 2002):
- Transaction records: [agent] [commodity] [quantity]
- Totaling lines: [items...] ku-ro [total]
- Libation formulas: [deity?] [verb?] [offering?]

This structure means that word order in tablets reflects list conventions more than natural syntax. However:
- The RELATIVE order of elements within each template is still informative
- Deviations from the template may reveal grammatical flexibility
- Libation tables have more natural clause structure

The word order analysis (Step 3) should distinguish between template-consistent and template-deviating patterns, giving more weight to the latter for grammatical claims.

### A.3 Agreement detection in a syllabary

In an alphabetic script, agreement (e.g., Latin "bonus dominus" — adjective and noun share the -us ending) is visible as shared letter sequences. In a CV syllabary, the equivalent is shared sign sequences in the suffix position.

Linear A's syllabary makes suffix agreement detectable as EXACT suffix match (both words end in the same sign). This is a coarser signal than alphabetic analysis (which could detect shared vowels or consonants independently), but it's sufficient to detect full-paradigm agreement.

Example: if words X-ti and Y-ti consistently appear adjacent, but X-ta and Y-ta also appear adjacent (and X-ti never appears with Y-ta), this is strong evidence for case agreement between X and Y.
