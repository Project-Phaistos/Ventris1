# Restructuring the Approach to Linear A Decipherment

**Date:** 2026-03-22
**Authors:** Alvin / Claude (ideation session)
**Status:** High-level ideation — not a PRD

---

## The Core Problem With Cognate-First Approaches

Every PhaiPhon iteration (and the Luo et al. phonetic prior) asks the same question: **"Which known language is Linear A most related to?"** — and then tries to answer it with increasingly sophisticated statistical machinery (edit distance DP, Bayes factors, transition matrices, JSD).

But this question has a buried assumption: that Linear A has **one primary genetic affiliation** that, once identified, unlocks the language. Ventris could make this assumption for Linear B because Mycenaean Greek turned out to be a straightforward member of a well-understood language family. For Linear A, there are three reasons this assumption probably fails:

1. **Minoan was likely a trade lingua franca** of a maritime civilization sitting at the crossroads of Greek, Anatolian, Levantine, and Egyptian cultural spheres. Its vocabulary may be a patchwork — core grammar from one source, trade terminology from another, religious vocabulary from a third, place names from a substrate.

2. **No single language "wins" convincingly.** PhaiPhon3-5 and the Luo et al. reproduction both show that ranking candidate languages produces noisy, inventory-size-biased results with no clear winner. This might not be a methodological failure — it might be telling us the truth: there IS no single winner.

3. **Even if we found the right cognate language, we still wouldn't have deciphered Linear A.** Knowing that *ku-ro* might relate to Semitic *kl* doesn't tell us the case system, verb morphology, or sentence structure. Cognacy is a proxy for vocabulary, which is itself only one component of a language.

What Ventris actually did was the opposite: he figured out the **internal structure** of Linear B first (the grid, the inflectional paradigms, the word classes), and only THEN asked what language it was. The language identification was the *last* step, not the first.

### What "decipherment" actually means

Decipherment is definitionally figuring out a critical mass of vocabulary and understanding the core grammar (inflections, conjugations, declensions), syntax and structure (phonotactics, etc.) of the language — not just finding cognates. Finding cognates is only a proxy.

---

## Pillar Dependency Chain

The five pillars are NOT independent — they have a clear dependency ordering:

```
Pillar 1 (Phonology)  ──→  Pillar 2 (Morphology)  ──→  Pillar 3 (Grammar)
                                                              │
Pillar 4 (Semantic Anchoring)  ←── can run in parallel ──────┘
                                                              │
                                        Pillar 5 (Multi-Source Vocab) ←── requires ALL above
```

**Pillar 1 must come first** because morphological segmentation (Pillar 2) needs to know the phonotactic constraints and syllable structure to segment at valid boundaries. You can't identify affixes if you don't know what constitutes a legal syllable.

**Pillar 2 feeds Pillar 3** because distributional grammar induction needs word classes, and word classes are partially determined by morphological behavior (nouns decline, verbs conjugate).

**Pillar 4 can run in parallel** with Pillars 2-3 because it operates on ideograms, numerals, and formula structure — largely independent of morphological analysis. Its outputs (anchor vocabulary, semantic field constraints) feed into Pillar 5.

**Pillar 5 comes last** because it requires the phonological fingerprint (Pillar 1), the morphological skeleton (Pillar 2), the grammar sketch (Pillar 3), and the anchor vocabulary (Pillar 4) to do its job properly. Without these, cognate searching is just what PhaiPhon1-5 already did — unconstrained and uninformative.

---

## Proposed Restructuring: Five Pillars

### Pillar 1: Phonological Engine (the computational grid)

Ventris built his consonant-vowel grid by hand from 159 inflected words. We should build it computationally.

**The idea:** The phonological engine should **discover the sound system independently from first principles**, using Linear B values only as a soft check after the fact — not as an input.

**Why independent discovery matters:** If we hard-assign Linear B phonetic values, we import Greek phonological assumptions (5 vowels, specific consonant inventory) that may not hold for Minoan. If Minoan had, say, 3 core vowels (as PhaiPhon4 suggested: a, i, u + 1 marginal), hard LB values would force a 5-vowel analysis and corrupt all downstream work. The engine needs to be able to disagree with Linear B.

**How independent discovery works:**

The key insight is that the ~7,400 sign tokens, even without phonetic interpretation, contain distributional information that constrains the sound system:

1. **Positional frequency analysis (Ventris's method, computationalized):**
   - Count each sign's frequency in word-initial, word-medial, and word-final positions across the entire corpus.
   - Signs with high initial frequency but low medial frequency are pure vowel signs (in a CV syllabary, vowel-initial words need a bare vowel sign, but mid-word vowels are written as part of CV compounds). This is how Ventris identified signs 08, 61, 38 as pure vowels — purely from frequency, with zero phonetic knowledge.
   - This analysis determines the **number of vowels** independently: however many signs show the "high-initial, low-medial" pattern = the vowel count.

2. **Inflectional alternation clustering (Kober's method, computationalized):**
   - Find pairs/triples of sign-groups that share a common prefix but differ in their final 1-2 signs (Kober's triplets).
   - Signs that alternate in the same word-final position across inflectional variants share a consonant (different vowels) → place in same grid ROW.
   - Signs that appear as corresponding endings across parallel paradigms share a vowel (different consonants) → place in same grid COLUMN.
   - This is an unsupervised clustering problem: given a set of pairwise "same-consonant" and "same-vowel" constraints, recover the 2D grid.

3. **Bigram/trigram transition analysis:**
   - Certain sign sequences will be common (legal clusters) and others will never appear (phonotactic gaps).
   - These gaps reveal syllable structure: if certain pairs of pure-vowel signs never appear adjacent, that constrains hiatus rules. If certain CV combinations never appear word-initially, that constrains onset rules.

4. **Linear B as soft validation (NOT input):**
   - After the grid is independently constructed, compare it against Linear B values. Where they agree, confidence is high. Where they disagree, flag for investigation — the disagreement itself is informative (it reveals where Minoan phonology differs from Greek).
   - Quantify an "agreement score" — e.g., if the independently-discovered grid places 85% of signs in the same C-V cell as LB values predict, that validates both the grid and the LB transfer. If it's only 60%, something is structurally different.

**Output:** "Linear A has N vowels, M consonants, permits these syllable types, and forbids these sequences." A phonological fingerprint of the language itself — with a measured agreement/disagreement score against the Linear B assumption.

---

### Pillar 2: Morphological Decomposition (automated Kober)

**Depends on:** Pillar 1 (phonotactic constraints, syllable structure, C-V grid)

Kober found her "triplets" by hand — sets of words sharing a stem but varying in endings. This is a segmentation and paradigm-discovery problem.

**The idea:** Given the corpus with Pillar 1's phonological model applied:

- **Automatic stem-affix segmentation** — find recurring prefixes and suffixes. Morfessor or BPE-style algorithms can do this, but they MUST be constrained by Pillar 1's syllable structure (affixes should respect syllable boundaries, and segmentation should not split within a CV unit). This is why Pillar 1 must come first — without knowing what constitutes a legal syllable boundary, morphological segmentation is underconstrained.
- **Paradigm induction** — group words that share a stem into inflectional paradigms. Identify how many distinct paradigm types exist (like Latin has 5 declensions). Each paradigm type tells you something about noun/verb classes. Pillar 1's C-V grid is essential here: if two endings share a consonant row, they are likely different case forms of the same declension; if they share a vowel column, they may represent the same case across different declension classes.
- **Distinguish inflection from derivation** — inflectional endings are high-frequency and productive (apply to many stems); derivational affixes are less frequent. This separation reveals the grammatical skeleton.
- **Case system mapping** — from the paradigms, determine how many grammatical cases exist and what their endings are. The libation formula and administrative lists provide context (e.g., words before offerings are probably in a dative/allative case; words after *ku-ro* are probably nominative or absolutive).

**Output:** "Linear A has N declension classes, M cases, these are the endings, and verbs inflect like this." Decipherment-grade morphological knowledge.

---

### Pillar 3: Distributional Grammar (word classes and syntax)

**Depends on:** Pillar 2 (morphological decomposition — word classes are partially determined by inflectional behavior)

**The idea:** Use distributional semantics — words that appear in the same contexts belong to the same class — to induce grammatical categories without any external language knowledge.

- **Word class induction** — cluster sign-groups by their distributional profiles (what precedes them, what follows them, what ideograms they co-occur with). This should separate nouns, verbs, adjectives, prepositions/postpositions, and particles.
- **Word order discovery** — from the ~1,500 texts, especially the longer ones (libation formula, the new Knossos ivory scepter), determine whether the language is VSO, SOV, SVO, etc. Davis (2013) argued VSO from the libation formula; this should be tested computationally across all available texts.
- **Agreement pattern detection** — if nouns and adjectives agree in case/number/gender, their endings should co-vary. Find these co-variation patterns automatically.
- **Functional word identification** — high-frequency, low-semantic-content words (articles, prepositions, conjunctions) are identifiable from frequency and positional distributions. We already know *ku-ro* = "total" and sign 78 in Linear B = "and"; find the Linear A equivalents.

**Output:** A grammar sketch — word classes, word order, agreement rules — derived entirely from internal evidence.

---

### Pillar 4: Semantic Anchoring (the known knowns)

**Depends on:** Nothing — can run in parallel with Pillars 2-3. Feeds into Pillar 5.

Before touching any external language, maximize what we can learn from context alone.

**The idea:** The Linear A tablets aren't just text — they contain ideograms (pictures of grain, oil, wine, animals, people), numerals, and transaction structures. This is supervised signal that most computational approaches underuse.

- **Ideogram-constrained semantics** — every sign-group that appears next to a wine ideogram + numeral is probably a word for wine, a type of wine, a place wine comes from, or a person who produces wine. This dramatically narrows the semantic space.
- **Numerical reasoning** — when lines sum to a total (*ku-ro*), the individual entries are quantities of the same category. Discrepancies between stated and computed totals reveal whether the discrepancy-words are modifiers (half, double) or different units.
- **Formula structure** — the libation formula appears on ~50+ vessels with systematic variation. Map every variant, identify the fixed elements (likely deity names, ritual verbs) vs. variable elements (place names, dedicant names, epithets).
- **Place name anchoring** — PA-I-TO (Phaistos), DI-KI-TE (Dikte), I-DA (Ida) are known. These anchor phonetic values AND provide geographic context for site-specific vocabulary.
- **The Knossos ivory scepter** — 119 signs, the longest single inscription. Hold this out as a validation set (exactly as Blegen's P641 validated Linear B). Never train on it; only use it to test.

**Output:** A vocabulary of ~50-100 words with known or strongly constrained meanings, derived without any cross-language comparison.

---

### Pillar 5: Multi-Source Vocabulary Resolution (cognates as tools, not goals)

**Depends on:** ALL of Pillars 1-4. This is the final integrative step.

Only NOW, with the phonological system, morphological structure, grammar sketch, and anchor vocabulary in hand, do we bring in external languages — but with a fundamentally different framing.

**The idea:** Instead of asking "is Linear A related to Luwian?", ask: **"For each unknown word in our partially-decoded vocabulary, which language(s) provide plausible source etymologies?"**

- **Simultaneous multi-language search** — for each word with known phonological form and constrained semantic field (from Pillar 4), search across ALL candidate languages at once: Greek, Luwian, Hurrian, Akkadian, Egyptian, Hattic, Phoenician, Proto-Anatolian, etc.
- **Allow mixed provenance** — the model should naturally produce results like: "trade terms cluster with Semitic; religious vocabulary clusters with Anatolian; place names are substrate (no match); kinship terms cluster with pre-Greek." This IS the answer, not a failure to find one answer.
- **Stratum detection** — group vocabulary by source language. Each stratum represents a historical layer of contact or inheritance. The relative sizes and domains of strata tell you the sociolinguistic history of Minoan civilization.
- **Borrowing vs. inheritance detection** — borrowed words typically don't undergo regular sound change; inherited words do. If the Anatolian stratum shows regular correspondences but the Semitic stratum doesn't, that suggests Anatolian inheritance and Semitic borrowing.

**Output:** Not "Linear A is Language X" but "Linear A's vocabulary is N% substrate (unknown), M% Anatolian-origin, P% Semitic-borrowing, Q% Greek-contact" — a compositional linguistic portrait.

---

## Comparison: Current vs. Proposed

| Current PhaiPhon approach | Proposed restructuring |
|---|---|
| Starts with cognate search | Starts with internal structure |
| Assumes one primary affiliation | Assumes mixed provenance |
| Cognacy is the goal | Cognacy is a tool for vocabulary |
| Language identification first | Language identification last (or never — it might be an isolate with borrowings) |
| Phonology from Linear B values (hard) | Phonology from distributional evidence (soft) |
| No morphological analysis | Morphology is central |
| No grammar induction | Grammar sketch from distributional patterns |
| Underuses ideograms and numerals | Ideograms and numerals are primary semantic signal |
| Single-language ranking output | Multi-stratum compositional output |

---

## Resolved Design Decisions

1. **Linear B values: soft check only.** The phonological engine (Pillar 1) discovers the sound system independently from distributional evidence. Linear B values are used ONLY as post-hoc validation — a measured agreement/disagreement score. Where the independent grid disagrees with LB, the disagreement is itself informative (reveals where Minoan phonology differs from Greek). This is architecturally possible via the positional frequency + inflectional alternation clustering approach described in Pillar 1.

2. **Corpus size is a constraint, not a question.** ~7,400 tokens is what we have. Chadwick's n-squared rule (60^2 = 3,600) says we're above the minimum threshold. Morphological analysis is the most data-efficient approach because it leverages the redundancy of inflectional patterns (many stems x few endings = many observations of the same affixes) rather than needing unique word forms. No alternative exists, so this is not a design decision — it's a boundary condition.

3. **Pillar execution order: 1 → 2 → 3 (+ 4 in parallel) → 5.** Pillar 2 depends on Pillar 1's phonotactic constraints and syllable structure to segment at valid boundaries. Pillar 3 depends on Pillar 2's morphological classes. Pillar 4 can run in parallel since it operates on ideograms and numerals. Pillar 5 requires all four predecessors.

4. **Chimaera hypothesis: informal, let strata emerge.** Do NOT formalize a mixture model over source languages upfront. Instead, let vocabulary strata emerge naturally in Pillar 5 from the data — if trade terms cluster with Semitic and religious terms cluster with Anatolian, that should be visible without an explicit mixture architecture. Formalizing too early risks encoding the very bias we're trying to avoid (pre-specifying which languages should appear as sources).

5. **Fundamental axiom (non-negotiable):** Linear A is NOT to be treated as a language with one dominant cognate ancestor. It is a chimaera language with multiple major influences from a maritime trading civilization. All architecture, analysis, and interpretation must allow for mixed provenance. Cognate matching is ONLY a tool for vocabulary resolution — never the goal and never framed as proving a genetic relationship.

---

## Methodological Inspiration

This restructuring draws directly from Ventris's decipherment methodology for Linear B (Chadwick 1958):

- **Structure before values**: Ventris built his consonant-vowel grid from internal distributional evidence before assigning any phonetic values. The grid captured structural relationships without phonetic labels.
- **Kober's triplets**: Systematic inflectional variants proved the language was inflected and revealed which signs shared consonants/vowels — pure internal analysis.
- **Place names as beachheads**: Only 3-4 initial phonetic guesses, tested against expected place names, were enough to seed the grid. The grid's structural relationships then propagated values automatically.
- **Confirmation on virgin material**: The decisive proof came from applying values derived from one corpus to freshly excavated tablets the decipherer had never seen (the Knossos ivory scepter could serve this role for Linear A).

The key lesson: Ventris's method was structure-first, content-second. He figured out the internal system before asking what language it was. Any computational approach to Linear A should replicate this discipline.
