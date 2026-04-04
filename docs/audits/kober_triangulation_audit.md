# Adversarial Audit: Kober Alternation Identification / Triangulation

**Auditor:** Claude (adversarial critic role)
**Date:** 2026-04-03
**Scope:** PRD_KOBER_ALTERNATION_IDENTIFICATION.md, alternation_detector.py, grid_constructor.py, kober_vowel_analysis.py, data files, validation protocol
**Verdict:** BLOCKING ISSUES FOUND -- method cannot proceed without fundamental rework

---

## Executive Summary

The Kober Triangulation method as designed has a **fatal flaw**: the 610 "alternation pairs" are not primarily driven by inflectional alternation. Empirical testing shows that shuffling sign sequences within words -- which should destroy all alternation structure -- produces an EQUAL or GREATER number of "significant" pairs (588-637 across 5 seeds vs 610 original). This means the alternation detector is measuring frequency co-occurrence artifacts, not morphological alternation.

Additionally, the consonant row purity of alternation partners is only 10.1% (vs expected ~100% for true Kober alternations), three AB-code assignments in the LB reference grid are wrong, and the anchor set contains 2 undeciphered signs misrepresented as known readings.

The triangulation algorithm as described in the PRD would operate on a graph that contains ~90% noise edges and ~64% of edges from single-sign prefixes (which are not inflectional paradigms). Any consonant row inference from this graph would be indistinguishable from random assignment.

---

## Issue 1: Alternation Signal is Indistinguishable from Noise

**SEVERITY:** CRITICAL (project-blocking)

**DESCRIPTION:**
The alternation detector finds 610 "significant" pairs using a Poisson test against a frequency-based null model. However, shuffling sign order within words -- which destroys all positional structure including inflectional alternations -- produces essentially the same number of significant pairs:

| Corpus | Significant Pairs | Branching Prefixes |
|--------|------------------|--------------------|
| Original | 610 | 153 |
| Shuffled (seed 42) | 637 | 132 |
| Shuffled (seed 123) | 588 | 131 |
| Shuffled (seed 456) | 616 | 131 |
| Shuffled (seed 789) | 599 | 150 |
| Shuffled (seed 1234) | 605 | 141 |

The shuffled corpora produce a mean of 609 pairs -- statistically identical to the original 610. This demonstrates that the "alternation" signal is entirely driven by frequency artifacts: common signs co-occur as word-final signs after common prefixes regardless of morphological relationship.

**EVIDENCE:**
- `pillar1/alternation_detector.py` lines 51-269 (the full detection algorithm)
- Reproduced via: load corpus, `copy.deepcopy`, shuffle signs within each word, re-run `detect_alternations`

**ROOT CAUSE:**
The Poisson null model (`expected = p_a * p_b * n_branching_prefixes`) treats each branching prefix as an independent trial. But the final-position frequencies `p_a` and `p_b` are computed from the same corpus that generates the prefix groups. When you shuffle sign order, the same signs still appear with similar frequencies, creating similar prefix groups with similar final-sign distributions. The test has essentially zero power to distinguish real alternation from frequency co-occurrence.

**RECOMMENDATION:**
1. The alternation detector must be redesigned with a permutation-based null model (shuffle word-final signs across prefix groups while preserving prefix structure) rather than the Poisson parametric test.
2. Require `min_shared_prefix_length >= 2` to exclude single-sign prefixes (see Issue 2).
3. The PRD's null test (Section 7.5) should be run BEFORE building the triangulation algorithm, as a prerequisite sanity check on the input data. If the null test fails (as it does), the entire downstream method is invalidated.

---

## Issue 2: 64% of Alternation Pairs Come from Single-Sign Prefixes

**SEVERITY:** CRITICAL

**DESCRIPTION:**
Of the 610 significant pairs, 393 (64.4%) are supported ONLY by single-sign prefix evidence. These are NOT inflectional alternations.

In a 2-sign word like `AB08-AB59` ("a-ta"), the "prefix" is just `AB08` ("a") -- the first syllable of the word. All 2-sign words starting with the same initial sign form a "branching prefix group," but these are entirely different words that happen to share an initial syllable, not inflectional variants of the same stem.

| Pair Source | Count | Percentage |
|-------------|-------|------------|
| Only single-sign prefix evidence | 393 | 64.4% |
| Only multi-sign prefix evidence | 29 | 4.8% |
| Both types | 23 | 3.8% |
| From diff_len=2 or other | 165 | 27.0% |

Only 52 pairs (8.6%) have any multi-sign prefix support. The remaining 558 pairs (91.4%) are either from single-sign prefixes or from the diff_len=2 mechanism (which has its own problems, see Issue 3).

**EVIDENCE:**
- `pillar1/alternation_detector.py` line 69: `min_shared_prefix_length: int = 1` -- the default allows single-sign prefixes
- 44.6% of corpus words are exactly 2 signs long, making single-sign prefixes the dominant pattern
- The algorithm at lines 104-173 treats all prefix lengths identically

**RECOMMENDATION:**
- Set `min_shared_prefix_length = 2` as the minimum. This would reduce the pair count dramatically but would select for actual stem-sharing pairs.
- Even better: require `min_shared_prefix_length = 2` AND `len(word) >= 3` to ensure the prefix is a plausible stem.

---

## Issue 3: diff_len=2 Generates Spurious Pairs from Penultimate Position

**SEVERITY:** HIGH

**DESCRIPTION:**
When `max_suffix_diff_length=2`, the detector compares words differing in their last 2 signs. For words `[p, a1, a2]` vs `[p, b1, b2]`, it generates pairs `(a1, b1)` and `(a2, b2)` each at weight 0.5.

The penultimate pair `(a1, b1)` is NOT a suffix alternation -- it is a difference in the second-to-last sign, which in a 3-sign word is a STEM position, not a suffix position. The Kober principle (same consonant, different vowel) only applies to suffix-position alternations where grammatical endings change the vowel.

With `min_shared_prefix_length=1` and `diff_len=2`, even 3-sign words generate pairs from what is effectively word-internal position variation. 165 of 610 pairs (27%) come from the diff_len=2 mechanism, and approximately half of those (the penultimate pairs) violate the Kober principle entirely.

**EVIDENCE:**
- `pillar1/alternation_detector.py` lines 147-173 (diff_len=2 handling)
- The code does not distinguish which of the two extracted pairs is from the final position vs the penultimate position

**RECOMMENDATION:**
- For diff_len=2, only extract the pair from the FINAL position `(a2, b2)`, not the penultimate pair `(a1, b1)`.
- Or: remove diff_len=2 entirely and rely solely on diff_len=1 with multi-sign prefixes.

---

## Issue 4: Consonant Row Purity is 10% (Expected ~100%)

**SEVERITY:** CRITICAL

**DESCRIPTION:**
In a true Kober alternation graph, all alternation partners of a sign should share its consonant row (same consonant, different vowel). The observed mean consonant row purity -- measured against the known Linear B ground truth -- is 10.1%.

This means for a given sign, only ~10% of its alternation partners actually share its consonant. The remaining ~90% are from different consonant rows, constituting noise edges.

For the triangulation algorithm's consonant row voting (Step 2), this means the correct consonant row would receive ~10% of votes while 11 incorrect rows share the remaining ~90%. The voting is essentially random -- no consonant row will have a statistically distinguishable advantage.

**EVIDENCE:**
- Mean consonant row purity: 0.101 (median: 0.091, min: 0.000, max: 1.000)
- Example: AB80/ma has 37 alternation partners, but only 2 (AB73/mi, AB13/me) share the /m/ row. The other 29 known partners span 8 different consonant rows.
- Measured against `pillar1/tests/fixtures/linear_b_sign_to_ipa.json`

**RECOMMENDATION:**
- This result is a direct consequence of Issues 1-3. Fixing the alternation detector to use only multi-sign prefix, diff_len=1 alternations would dramatically improve purity, but the pair count would drop from 610 to approximately 29-52.
- With only ~50 pairs, the alternation graph would be too sparse for triangulation of 16 unknown signs.

---

## Issue 5: Three Wrong AB-Code Assignments in LB Reference Grid

**SEVERITY:** HIGH

**DESCRIPTION:**
The `LB_PHONETIC_VALUES` dictionary in `kober_vowel_analysis.py` (lines 447-468) contains three incorrect AB-code-to-reading assignments. The same errors appear in the PRD's Section 4.3 grid table (lines 131-143).

| AB Code | Code/PRD Says | Standard Value | Effect |
|---------|--------------|----------------|--------|
| AB06 | di (d-row) | na (n-row) | na wrongly placed in d-row |
| AB54 | na (n-row) | wa (w-row) | wa wrongly placed in n-row |
| AB07 | wi (w-row) | di (d-row) | di wrongly placed in w-row |

This is a circular permutation of three signs across three consonant rows. The errors contaminate:
- Cross-reference ARI scores (consonant and vowel)
- Consonant row ground truth for LB validation
- Any anchor-based vowel assignment that uses these signs

Additionally, the code has a duplicate key bug: AB80, AB13, AB73 appear twice in the dict (lines 453-454 and 463). In Python, the second occurrence overwrites the first, so no data is lost, but it indicates careless construction.

**EVIDENCE:**
- `C:/Users/alvin/Ventris1/pillar1/scripts/kober_vowel_analysis.py` lines 447-468
- Cross-referenced against `pillar1/tests/fixtures/linear_b_sign_to_ipa.json` which has the CORRECT assignments
- Verified against standard Bennett numbering (Documents in Mycenaean Greek, Ventris & Chadwick 1973)

**RECOMMENDATION:**
Fix the three AB-code assignments and remove the duplicate entries. The fixture file `linear_b_sign_to_ipa.json` has the correct values and should be used as the authoritative source.

---

## Issue 6: Anchor Set Contains 2 Undeciphered Signs

**SEVERITY:** MEDIUM

**DESCRIPTION:**
`data/sign_to_ipa.json` contains 53 entries, but 2 are undeciphered signs with Greek-letter placeholders:
- `"*301": "\u0398"` (Theta) -- an undeciphered sign
- `"*56": "\u03a6"` (Phi) -- an undeciphered sign

These are NOT known phonetic values. They are placeholder symbols for signs whose readings have not been established. Including them as "anchors" in the triangulation would provide zero useful information (their "IPA" values are single Greek letters, not CV syllables) and could inject errors into the vowel extraction (`_get_vowel()` would fail to extract a vowel from a single Greek letter).

The PRD claims "53 known signs" but the effective anchor count is 48 standard CV syllabograms + 3 complex signs (nwa, ra2, pu2) = 51 usable anchors.

**EVIDENCE:**
- `data/sign_to_ipa.json` lines 4 and 27
- The `_get_vowel()` function in `grid_constructor.py` (line 349-361) would return "" for these entries, effectively making them unassigned

**RECOMMENDATION:**
Remove `*301` and `*56` from the anchor set. Update the PRD to state 51 usable anchors.

---

## Issue 7: data/sign_to_ipa.json Has No AB Codes

**SEVERITY:** MEDIUM

**DESCRIPTION:**
The anchor file `data/sign_to_ipa.json` uses reading names as keys (e.g., "ta", "ma") while the corpus and alternation detector use AB codes (e.g., "AB59", "AB80"). There is no direct mapping between them in the anchor file.

The mapping must go through the corpus `sign_inventory`, which maps reading names to AB codes. But this introduces an indirection that:
1. Is error-prone (requires the sign_inventory to be complete and correct)
2. Fails silently for signs not in the inventory
3. Creates a dependency on corpus loading just to interpret the anchor file

The fixture file `linear_b_sign_to_ipa.json` correctly uses AB codes as keys.

**EVIDENCE:**
- `data/sign_to_ipa.json` keys: "a", "ta", "i", "*301", "wa", ...
- `pillar1/tests/fixtures/linear_b_sign_to_ipa.json` keys: "AB08", "AB59", "AB28", ...

**RECOMMENDATION:**
Add an AB-code-keyed version of the anchor file, or modify the existing file to include AB codes alongside reading names.

---

## Issue 8: LB Test Corpus is Too Small for Validation

**SEVERITY:** HIGH

**DESCRIPTION:**
The LB test corpus (`linear_b_test_corpus.json`) contains only 142 inscriptions with 448 words and 56 unique signs. Running the alternation detector on this corpus produces only 26 significant pairs and 20 signs in the alternation graph. This is far too sparse for meaningful validation.

The PRD's validation protocol (Section 7.3) requires holding out 20 of ~87 LB syllabograms and triangulating their readings. But:
1. The test corpus only covers 56 of the ~87 known signs
2. The alternation graph from this corpus only includes 20 signs
3. Consonant row purity on this corpus is 53.2% -- better than LA but still noisy

The PRD suggests combining with HF data (`linear_b_words.tsv`), but this file is a VOCABULARY LIST with 2,478 word entries, not an inscription corpus. It contains individual words with IPA transcriptions but no inscription context (words in sequences). The alternation detector requires inscription context to find prefix-sharing pairs. The two data sources cannot be "combined" for alternation detection.

**EVIDENCE:**
- `pillar1/tests/fixtures/linear_b_test_corpus.json`: 142 inscriptions, 448 words, 56 signs
- `C:/Users/alvin/hf-ancient-scripts/data/linear_b/linear_b_words.tsv`: 2,478 vocabulary entries, no inscription structure
- LB alternation detection: 26 pairs, 20 signs in graph

**RECOMMENDATION:**
A proper LB inscription corpus is needed. The 448 words in the fixture are insufficient. Either:
1. Obtain the DAMOS or another published LB inscription database with full tablet transcriptions
2. Construct a larger synthetic LB corpus from the vocabulary list by generating plausible inscription-like sequences (but this has its own validity issues)
3. Acknowledge that LB corpus validation is not currently possible with available data

---

## Issue 9: Leave-One-Out Protocol Has No Data Leakage, But is Misleading

**SEVERITY:** MEDIUM

**DESCRIPTION:**
The PRD's leave-one-out protocol (Section 7.1) removes a sign from the anchor set but does NOT re-run the alternation detector. The alternation pairs are corpus-derived and sign-independent, so the held-out sign's alternation edges remain in the graph. This is technically correct -- the alternation pairs are objective observations that don't depend on knowing the sign's reading.

However, the protocol is misleading in practice because:
1. The 610 pairs include ~90% noise edges (Issue 4), so the "alternation evidence" used for triangulation is mostly uninformative
2. With 52 remaining anchors and mean degree 17.7, a held-out sign will typically have 10-15 anchor alternation partners -- but ~90% of those are from the WRONG consonant row
3. The leave-one-out test would effectively measure whether the triangulation algorithm can find a signal in a 90% noise graph, which it cannot

The PRD's threshold of 70% top-3 accuracy is almost certainly unachievable given the noise level. A more honest assessment would acknowledge that the method's expected accuracy is near-random (~20% for consonant row x ~20% for vowel column = ~4% joint accuracy).

**EVIDENCE:**
- 10.1% consonant row purity means ~90% of anchor alternation edges provide wrong-row evidence
- With 12 consonant rows and noisy voting, random baseline for consonant identification is ~8%
- With 5 vowel columns, random baseline for vowel identification is ~20%
- Joint random baseline: ~1.6% (any specific CV reading)

**RECOMMENDATION:**
Before running the full leave-one-out, compute the EXPECTED accuracy from the graph's noise level. If the expected accuracy is below the threshold, the test will fail by design and should not be attempted until the alternation detector is fixed.

---

## Issue 10: Confidence Formula is Poorly Calibrated

**SEVERITY:** MEDIUM

**DESCRIPTION:**
The PRD's confidence formula (Section 6.7):
```
confidence = (n_supporting / n_total_anchor) * grid_consistency * cell_occupancy
```

Has four problems:
1. **Denominator includes noise:** `n_total_anchor` counts ALL anchor alternations including ~90% cross-row noise. Even for correctly identified signs, `n_supporting/n_total` will rarely exceed 0.2.
2. **No minimum evidence:** A sign with 3 edges all from one row gets confidence 1.0, but 3 edges from a 12-row graph could easily be coincidence (p=0.1^3 per row, but 12 rows tested).
3. **Binary grid consistency:** The P1 grid has ARI=0.615 (wrong 38.5% of the time). A binary 1.0/0.5 factor gives too much weight to an unreliable signal.
4. **Cell occupancy penalty is backwards:** The 0.7 penalty for occupied cells assumes single-valued cells, but Linear A may have variant signs for the same CV value (common in syllabaries).

**EVIDENCE:**
- PRD Section 6.7 (Step 7, lines 297-301)
- Grid ARI=0.615 from `results/kober_vowel_analysis.json`
- Mean consonant row purity 10.1%

**RECOMMENDATION:**
Replace with a Bayesian posterior or likelihood-ratio score that accounts for the noise level of the graph. The confidence should reflect how much the observed evidence exceeds the noise baseline, not just the fraction of supporting edges.

---

## Issue 11: The PRD References a Non-Existent Script

**SEVERITY:** LOW

**DESCRIPTION:**
The PRD references `pillar1/scripts/kober_vowel_analysis.py` (lines 447-468) for the LB CV grid definition. This script exists in the main Ventris1 repo (`C:/Users/alvin/Ventris1/pillar1/scripts/kober_vowel_analysis.py`) but NOT in the git worktree where development is happening (`C:/Users/alvin/Ventris1/.claude/worktrees/agent-a3e6b674/`). The `pillar1/scripts/` directory does not exist in the worktree.

This means any developer working in the worktree cannot verify the PRD's claims about lines 447-468 without accessing the main repo.

**EVIDENCE:**
- `Glob("**/pillar1/scripts/*")` returns no results in the worktree
- The file exists at `C:/Users/alvin/Ventris1/pillar1/scripts/kober_vowel_analysis.py`

**RECOMMENDATION:**
Ensure the worktree is up to date with the main repo, or update the PRD to reference files that exist in all working copies.

---

## Issue 12: HF LB Data Has IPA Inconsistencies with Fixture

**SEVERITY:** LOW

**DESCRIPTION:**
The HF `sign_to_ipa.json` (74 entries) and the fixture `linear_b_sign_to_ipa.json` (58 entries) disagree on IPA values for 6 sign families:

| Sign | HF IPA | Fixture IPA |
|------|--------|-------------|
| qa | kwa | qa |
| qe | kwe | qe |
| qo | kwo | qo |
| za | tsa | za |
| ze | tse | ze |
| zo | tso | zo |

The HF values are phonetically accurate IPA (labiovelars, affricates), while the fixture uses simplified transliteration-style values. Both are defensible conventions, but they must be consistent for any cross-referencing.

**EVIDENCE:**
- `C:/Users/alvin/hf-ancient-scripts/data/linear_b/sign_to_ipa.json`
- `pillar1/tests/fixtures/linear_b_sign_to_ipa.json`

**RECOMMENDATION:**
Decide on one convention (IPA or transliteration) and enforce it across all data files. For vowel extraction purposes, the simplified convention is easier to parse.

---

## Summary of Findings by Severity

| Severity | Count | Issues |
|----------|-------|--------|
| CRITICAL | 3 | #1 (signal = noise), #2 (64% from bad prefixes), #4 (10% row purity) |
| HIGH | 3 | #3 (diff_len=2 penultimate), #5 (wrong AB codes), #8 (LB corpus too small) |
| MEDIUM | 4 | #6 (bad anchors), #7 (no AB codes), #9 (misleading LOO), #10 (bad confidence) |
| LOW | 2 | #11 (missing script), #12 (IPA inconsistency) |

---

## Overall Recommendation

**DO NOT proceed with the Kober Triangulation algorithm as specified.** The input data (610 alternation pairs) is fundamentally compromised -- it measures frequency artifacts, not inflectional alternation.

**Required before any triangulation work:**

1. **Fix the alternation detector** to use only multi-sign prefixes (`min_shared_prefix_length >= 2`), diff_len=1 only, and a permutation-based null model. This will reduce the pair count from 610 to approximately 30-50 genuine alternation pairs.

2. **Run the null test FIRST** (shuffled corpus) and confirm the redesigned detector passes it (shuffled pairs << original pairs, target: < 10% of original).

3. **Fix the 3 wrong AB-code assignments** in `kober_vowel_analysis.py` and the PRD.

4. **Remove undeciphered signs** from the anchor set.

5. **Re-evaluate feasibility** after steps 1-4. With ~40 genuine pairs and 48 anchors, the alternation graph may be too sparse for meaningful triangulation. If so, the Jaccard-based approach (PRD_JACCARD_SIGN_CLASSIFICATION.md) should be prioritized instead.

6. **Obtain a larger LB corpus** for validation, or acknowledge that LB corpus validation is infeasible with current data.

---

*This audit was conducted as an adversarial review. All findings are empirically verified against the codebase and corpus data.*
