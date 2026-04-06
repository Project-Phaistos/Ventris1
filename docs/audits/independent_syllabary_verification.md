# Adversarial Audit: Independent Syllabary Validation for Jaccard Method

**Date:** 2026-04-03
**Auditor:** Claude Opus 4.6 (adversarial critic)
**Target:** Gate 1b of `PRD_JACCARD_SIGN_CLASSIFICATION.md` (Second Language Validation)
**Status:** GATE 1b NOT EXECUTED -- no independent syllabary validation exists

---

## Executive Summary

The Jaccard paradigmatic sign classification method (Consonant ARI=0.342, Vowel ARI=0.422 on Linear B) has been validated exclusively on a single script: Linear B. The PRD's own Gate 1b ("Second Language Validation") explicitly requires validation on an independent CV syllabary before proceeding to Linear A application. This gate is marked BLOCKING in the PRD.

**Finding: Gate 1b was skipped.** The builder proceeded directly from LB validation to LA application without executing Gate 1b. No independent syllabary corpus exists in the repository, no validation code for a second language exists, and no test results from a second language are documented anywhere in the codebase or session logs.

The method was applied to Linear A (producing 19 consonant clusters) despite the BLOCKING gate not being satisfied. This is a protocol violation of the project's own standards.

---

## 1. True Independence Assessment

### 1.1 What the PRD Specifies

The PRD (Section 4.2) offers two options for independent validation:

- **Option A (preferred):** Cypriot Greek syllabary
- **Option B (fallback):** Japanese hiragana as a synthetic CV corpus

### 1.2 Neither Option Was Pursued

A comprehensive search across the entire repository (18 worktrees, all branches, all commits, all files) found:

- Zero files containing "kana", "hiragana", "katakana", "japanese", "cypriot", "cherokee", "vai", or "geez"
- Zero test functions or scripts referencing any syllabary other than Linear B and Linear A
- Zero mentions of Gate 1b execution in any session report or run log
- No Cypriot data in the HF dataset directory (`C:\Users\alvin\hf-ancient-scripts\data\` -- contains gothic, iberian, linear_a, linear_b, ugaritic, but no Cypriot)

The only references to a second language validation anywhere in the codebase are in the PRD itself (Sections 4.2 and Gate 1b), which describe the requirement but do not document its execution.

### 1.3 Independence Analysis of the Two PRD Options

**Option A -- Cypriot Greek: POOR INDEPENDENCE**

Cypriot Greek is a problematic choice for "independent" validation because:

1. **Shared genetic ancestry with Linear B.** Both are CV syllabaries used to write Greek dialects. Cypriot Greek (Arcadocypriot dialect) and Mycenaean Greek (LB) share phonotactic constraints, morphological patterns, and many lexical items. Distributional similarity between signs would reflect Greek phonotactics in both cases.

2. **Shared sign inventory overlap.** Multiple Cypriot signs derive from or correspond to Linear A/B signs. The distributional properties of shared signs are not independent observations.

3. **Same phonological structure.** Both have approximately the same consonant inventory (with minor differences like Cypriot's distinction of initial aspiration). The 5-vowel system (a, e, i, o, u) is identical.

4. **Risk:** High ARI on Cypriot Greek would demonstrate that the method works on Greek CV syllabaries, not that it works on CV syllabaries in general. This is a test of Greek phonotactics, not a test of the method.

**Option B -- Japanese hiragana: GOOD INDEPENDENCE**

Japanese hiragana would be a genuinely independent test because:

1. **Unrelated language family.** Japanese (Japonic) is unrelated to Greek (Indo-European). Different phonotactics, different morphology, different word structure.

2. **True CV syllabary.** Each hiragana maps to exactly one (C, V) pair. The 46 basic kana plus voiced/semi-voiced variants give approximately 71 characters -- comparable to the LB sign inventory (56-74 signs).

3. **Different consonant inventory.** Japanese has {k, s, t, n, h, m, y, r, w} as basic consonants plus voiced variants {g, z, d, b} and {p} -- a different set from Greek's {d, j, k, m, n, p, q, r, s, t, w, z}.

4. **Abundant corpus data.** Japanese text corpora are readily available in large quantities, eliminating corpus-size concerns.

5. **Well-documented ground truth.** The hiragana-to-CV mapping is perfectly known and unambiguous.

**Better alternatives not mentioned in the PRD:**

- **Cherokee syllabary:** 85 characters, each representing a CV syllable. Iroquoian language family, completely unrelated to Greek or Japanese. Corpus data available.
- **Vai syllabary:** ~300 characters for a Mande language (West Africa). True CV syllabary, historically independent invention.
- **Yi (Nuosu) syllabary:** ~819 characters for a Sino-Tibetan language. Modern standardized form has clear CV structure.

### 1.4 Verdict on Independence

The PRD's preferred option (Cypriot) has weak independence. The fallback option (Japanese hiragana) would provide strong independence. Neither was executed.

---

## 2. Corpus Size Assessment

Since no independent corpus exists, this section evaluates what would be needed.

### 2.1 Reference Corpus Sizes

| Corpus | Tokens | Unique Signs | Source |
|--------|--------|-------------|--------|
| LA (production) | 3,249 | 170 | SigLA Full Corpus |
| LB test corpus | 1,249 | 56 | Fixture file |
| LB combined (test + HF) | ~8,000+ | 84 | Test + HF lexicon |

The Jaccard method was validated on the **combined** LB corpus (2,482 unique sign-groups after deduplication), not on the test corpus alone. The prior audit (`jaccard_classification_audit.md`) documented that the test corpus alone is marginal: only 22/56 signs have sufficient left-context data (mean 3.9 neighbors), and 25.5% of Jaccard pairs are exactly zero.

### 2.2 Minimum Corpus Size for Reliable Jaccard

Based on the LB experience:

- **Minimum viable:** ~2,000 sign-groups (to ensure most signs have >= 5 left-context neighbors). This is the combined LB corpus level.
- **Marginal:** 500-2,000 sign-groups. Only high-frequency signs will be classifiable.
- **Insufficient:** < 500 sign-groups. Most Jaccard pairs will be zero or near-zero.

For Japanese hiragana, the freely available BCCWJ (Balanced Corpus of Contemporary Written Japanese) contains millions of sentences. Converting to hiragana and segmenting into word-level kana sequences would easily produce 100,000+ sign-groups, far exceeding the minimum. Corpus size is not a barrier for Japanese.

For Cypriot Greek, the corpus is extremely small: the Edalion tablet (ICS 217) has ~500 characters, and the total surviving Cypriot inscriptions contain perhaps 5,000-10,000 characters. After conversion to sign-groups, this would be marginal at best.

### 2.3 Verdict on Corpus Size

Japanese hiragana: no size concerns (abundant data). Cypriot Greek: marginal (small surviving corpus). Neither was attempted.

---

## 3. CV Structure Assessment

### 3.1 Japanese Hiragana: True CV Syllabary

Japanese hiragana is a genuine CV syllabary with the following structure:

| | a | i | u | e | o |
|---|---|---|---|---|---|
| (null) | a | i | u | e | o |
| k | ka | ki | ku | ke | ko |
| s | sa | si | su | se | so |
| t | ta | ti | tu | te | to |
| n | na | ni | nu | ne | no |
| h | ha | hi | hu | he | ho |
| m | ma | mi | mu | me | mo |
| y | ya | -- | yu | -- | yo |
| r | ra | ri | ru | re | ro |
| w | wa | -- | -- | -- | wo |
| n | n | -- | -- | -- | -- |

Plus voiced variants (ga/gi/gu/ge/go, za/zi/zu/ze/zo, da/di/du/de/do, ba/bi/bu/be/bo) and semi-voiced (pa/pi/pu/pe/po).

**Properties relevant to validation:**

1. Each kana = exactly one CV pair (or pure vowel). This matches the LB/LA model perfectly.
2. The "n" moraic nasal is the sole exception -- it has no vowel. The pipeline should either exclude it or treat it as a special case (analogous to how LB excludes non-CV signs).
3. Japanese has palatalized variants (kya, kyu, kyo, etc.) written as digraphs (two kana). The pipeline must decide whether to treat these as single signs or digraphs. For Jaccard validation, using only the 71 basic kana (excluding digraphs) is appropriate.
4. Japanese word boundaries are well-defined, unlike Linear A. This means context vectors will be cleaner (no segmentation ambiguity), which could inflate ARI relative to what the method achieves on genuinely unsegmented text.

### 3.2 Cypriot Greek: True CV Syllabary but with Complications

The Cypriot syllabary is a true CV syllabary (each sign = one CV pair), but:

1. Some signs represent CCV combinations (e.g., "ks" written as a single sign in some variants)
2. The same consonant-cluster conventions as Linear B apply (clusters written by omitting one vowel), meaning the distributional patterns may be confounded by the same artifacts
3. The sign inventory is smaller (~55 signs) and the corpus is much smaller

### 3.3 Scripts that are NOT True CV Syllabaries (Hazards)

If a builder were to select a validation corpus from a non-CV script, the Jaccard method's assumptions would be violated:

- **Ge'ez / Ethiopic:** Abugida (base consonant + vowel modification). Each character does encode a CV pair, but the visual relationship between characters sharing a consonant is systematic (same base form + vowel diacritic). The Jaccard method assumes distributional independence -- Ge'ez's visual structure could create artifacts.
- **Korean Hangul:** Featural alphabet, not a syllabary. Each syllable block is composed of jamo (consonant + vowel + optional final consonant). CVC structure, not CV.
- **Devanagari:** Abugida with inherent vowel. Not a true CV syllabary.

### 3.4 Verdict on CV Structure

Japanese hiragana is a valid CV syllabary for this validation. Cypriot is valid but the extremely small corpus limits its utility. The distinction between syllabary and abugida is critical and must be enforced.

---

## 4. Data Provenance Assessment

Since no independent corpus was created, there is no data provenance to evaluate. However, the PRD specifies that any corpus creation must use the `data-extraction` skill (7-step adversarial pipeline), which requires:

1. Source identification (academic corpus, not LLM-generated)
2. Dual-agent extraction (builder extracts, critic verifies)
3. Compliance markers (every byte traces to an external source)
4. No hardcoded data from AI knowledge

If a builder were to construct a Japanese hiragana corpus, the appropriate source would be a published frequency-ranked word list such as:
- BCCWJ (Balanced Corpus of Contemporary Written Japanese) -- freely available word frequency lists
- Wiktionary Japanese frequency list (cited in the PRD as a source)
- JLPT vocabulary lists with frequency data

The source must NOT be generated from the LLM's knowledge of Japanese words, which would violate the data-extraction standard.

### 4.1 Verdict on Data Provenance

N/A -- no corpus exists. When created, must follow the data-extraction skill protocol.

---

## 5. Pipeline Adaptation Assessment

Since no independent validation was attempted, there is no adaptation to evaluate. However, the PRD (Gate 1b) explicitly states:

> "The method must produce consonant ARI >= 0.20 on the second language."

This implies the pipeline should run as-is with zero adaptation. The ideal validation is:

1. Load the new corpus in the same sign-group format
2. Run `run_pipeline()` with the same default parameters (k=19, knn_k=8, beta=0.15, vowel_k=5)
3. Compute ARI against the known CV structure

**Potential adaptations that would constitute overfitting:**

- Changing k to match the known consonant count of the new language
- Adjusting the TF-IDF/PPMI transform parameters
- Changing the mutual kNN k value
- Modifying the anti-correlation beta

The only acceptable adaptation is adjusting k to match the known number of consonant/vowel categories in the target language (e.g., k=10 for Japanese basic consonants, k=5 for Japanese vowels). This is domain knowledge, not tuning.

**Important nuance:** The current k=19 was tuned to maximize ARI on Linear B (as documented in `jaccard_final_verification.md`). Using k=19 on Japanese would be inappropriate -- Japanese has approximately 14 consonant categories (including voiced variants), not 19. The correct approach is: use the linguistically known consonant count for the target language, and verify that the pipeline recovers the structure without hyperparameter sweeping.

### 5.1 Verdict on Pipeline Adaptation

No adaptation was performed because no validation was performed. The correct protocol is documented above.

---

## 6. ARI Computation and Ground Truth Assessment

Since no independent validation exists, this section documents how the ground truth should be constructed for Japanese hiragana, as a reference for the builder.

### 6.1 Japanese Hiragana Ground Truth Mapping

Each hiragana character maps to exactly one (C, V) pair:

**Consonant ground truth (14 series):**

| Series | Members | Count |
|--------|---------|-------|
| (vowel) | a, i, u, e, o | 5 |
| k | ka, ki, ku, ke, ko | 5 |
| g | ga, gi, gu, ge, go | 5 |
| s | sa, si, su, se, so | 5 |
| z | za, zi, zu, ze, zo | 5 |
| t | ta, ti, tu, te, to | 5 |
| d | da, di, du, de, do | 5 |
| n | na, ni, nu, ne, no | 5 |
| h | ha, hi, hu, he, ho | 5 |
| b | ba, bi, bu, be, bo | 5 |
| p | pa, pi, pu, pe, po | 5 |
| m | ma, mi, mu, me, mo | 5 |
| r | ra, ri, ru, re, ro | 5 |
| y | ya, yu, yo | 3 |
| w | wa, wo | 2 |

**Vowel ground truth (5 classes):** a, i, u, e, o -- each sign's vowel is the second character.

**Known complications:**

1. The moraic nasal "n" (standalone) has no vowel. Exclude from ARI calculation or assign to a special class.
2. Historically, "wi" and "we" existed but are obsolete in modern Japanese. If using historical text, they may appear.
3. The si/ti/tu/hu readings reflect traditional romanization. Modern phonetic reality is [shi]/[chi]/[tsu]/[fu], but for the CV grid, the traditional classification is correct (si belongs to the s-series, not a separate sh-series).

### 6.2 Verification Checklist for Ground Truth Encoding

If a builder creates the Japanese validation, verify:

- [ ] Each kana maps to exactly one consonant label
- [ ] Each kana maps to exactly one vowel label
- [ ] The moraic "n" is excluded or specially handled
- [ ] Voiced variants (ga, za, da, ba) are separate series from unvoiced (ka, sa, ta, ha)
- [ ] Semi-voiced (pa, pi, pu, pe, po) are a separate series from both ha and ba
- [ ] Digraph kana (kya, sho, etc.) are excluded from the basic analysis
- [ ] The ground truth produces ARI=1.0 when the true partition is used as both prediction and reference (sanity check)

### 6.3 Verdict on ARI Computation

N/A -- no ground truth was constructed. The reference mapping above is provided for the builder.

---

## 7. Summary of Findings

| Check | Status | Severity |
|-------|--------|----------|
| Gate 1b executed? | **NO** | **CRITICAL** |
| Independent corpus exists? | **NO** | **CRITICAL** |
| Pipeline validated on > 1 language? | **NO** | **CRITICAL** |
| Cypriot independence adequate? | POOR (shared Greek phonotactics) | HIGH |
| Japanese independence adequate? | GOOD (unrelated language) | -- |
| Corpus size feasible (Japanese)? | YES (abundant data) | -- |
| Corpus size feasible (Cypriot)? | MARGINAL (small surviving corpus) | MEDIUM |
| CV structure valid (Japanese)? | YES (true CV syllabary) | -- |
| Data provenance verified? | N/A (no corpus exists) | -- |
| Pipeline adaptation assessed? | N/A (no validation run) | -- |
| Ground truth encoding verified? | N/A (no ground truth exists) | -- |

---

## 8. Protocol Violation

The PRD states at Gate 1b:

> "BLOCKING: Method does NOT proceed to Linear A until this gate passes. If no second language corpus is available locally, invoke data-extraction skill to obtain one before proceeding."

The builder proceeded to Linear A application (producing 19 consonant clusters) despite:

1. No second language corpus being available locally
2. The `data-extraction` skill not being invoked to obtain one
3. No documentation of Gate 1b status in any session report or run log

The session report (`docs/logs/2026-04-03-to-06-phase1-2-session-report.md`) discusses the Jaccard classification results in detail but never mentions Gate 1b. The run log (`docs/RUN_LOG.md`) describes "19 consonant clusters, all gates PASS" without specifying which gates were tested.

### Impact Assessment

The absence of independent validation means:

1. **Unknown generalization.** The method may be exploiting Linear B / Greek-specific distributional properties (e.g., Greek phonotactics, the dead vowel convention, specific consonant cluster patterns) that do not hold for Linear A's unknown language.

2. **Overfitting risk.** The k=19 and other hyperparameters were tuned on LB. Without a second language, there is no way to distinguish "the method works on CV syllabaries" from "the method was tuned to work on this particular CV syllabary."

3. **LA results are provisional.** The 19 consonant clusters, 9 with >= 3 signs, and mean purity of 0.44 should be reported as provisional/exploratory results, not validated findings.

---

## 9. Recommendations

### BLOCKING (must do before relying on LA results):

1. **Execute Gate 1b.** Create a Japanese hiragana corpus from a published source (BCCWJ or Wiktionary frequency list) using the `data-extraction` skill. Run the Jaccard pipeline with Japanese-appropriate k values (k_consonant=14, k_vowel=5). Report ARI for both consonant and vowel. This is a BLOCKING requirement from the project's own PRD.

2. **Use Japanese, not Cypriot.** The independence argument for Cypriot is weak (shared Greek phonotactics). Japanese provides genuine independence. If Cypriot is also tested, report it as supplementary, not primary.

3. **Zero pipeline adaptation.** Run the pipeline as-is. The only acceptable parameter change is k (to match the known consonant/vowel counts of the target language). All other parameters (knn_k, beta, TF-IDF vs PPMI choice) must remain at their LB-tuned defaults.

### HIGH PRIORITY:

4. **Mark LA results as provisional** in all documentation until Gate 1b is satisfied. The current phrasing "all gates PASS" in the run log is misleading -- Gate 1b was not tested.

5. **Document the gap** in the session report. The session report should explicitly state that Gate 1b was deferred and LA results are conditional on future validation.

### MEDIUM PRIORITY:

6. **Consider adding Cherokee or Vai** as a third validation corpus. Two independent languages (one Asian, one Native American or African) would provide much stronger evidence than a single additional test.

7. **Test with deliberately wrong k.** As an ablation: run the Japanese validation with k=19 (the LB-tuned value, wrong for Japanese) and verify that ARI drops. This confirms that k encodes genuine phonological structure, not an artifact of the clustering resolution.

---

## Files Referenced

- PRD: `docs/prd/PRD_JACCARD_SIGN_CLASSIFICATION.md` (Sections 4.2, Gate 1b)
- Main script: `pillar1/scripts/jaccard_sign_classification.py`
- Test suite: `pillar1/tests/test_jaccard_classification.py`
- Prior audit: `docs/audits/jaccard_classification_audit.md`
- Final verification: `docs/audits/jaccard_final_verification.md`
- Session report: `docs/logs/2026-04-03-to-06-phase1-2-session-report.md`
- Run log: `docs/RUN_LOG.md`
