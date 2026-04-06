# Adversarial Audit: PRD_SUFFIX_CONSTRAINTS.md

**Date:** 2026-04-03
**Auditor:** Claude (adversarial review agent)
**Subject:** Suffix-Derived Phonological Constraints approach
**Verdict:** CRITICAL flaws found. The core mechanism (Kober's principle applied to suffix alternation sets) is empirically falsified by the data. The approach as specified will produce noise, not signal.

---

## Issue 1: Kober's Principle Fails on the Actual Suffix Data (10% Agreement)

**SEVERITY:** CRITICAL / BLOCKING

**DESCRIPTION:**
The PRD's central claim is that signs appearing as suffixes on the same stem share a consonant (Kober's principle). This was tested against ground truth by checking whether high-overlap suffix pairs actually share consonants according to their known Linear B readings. The result: **10.2% agreement** -- indistinguishable from the ~10% expected by random chance.

**EVIDENCE:**
All 29 inflectional suffixes have known LB readings (0 unknown signs among them). Using those readings as ground truth:

- Of the top 20 pairs by stem overlap, only 2 share a consonant (AB27/re + AB60/ra; AB04/te + AB69/tu). The other 18 pairs have completely different consonants.
- The highest-overlap pair, AB59(ta) + AB60(ra), overlap=6, has different consonants (t vs r).
- Over all 127 pairs with overlap >= 2: same consonant = 13 (10.2%), same vowel = 37 (29.1%), neither = 77 (60.6%).
- The same-consonant rate of 10.2% is exactly what random chance would produce given ~10 consonant series.
- The same-vowel rate of 29.1% is slightly above the 20% expected by chance, but not dramatically so.

This means the suffix alternation sets do NOT contain Kober-principle signal. The suffixes that attach to the same stems do so because they serve different grammatical functions (e.g., case endings), not because they share consonant structure.

**ROOT CAUSE:**
Kober's principle states that signs **alternating in the same morphological slot** share a consonant. But P2's stem overlap does NOT identify same-slot alternation. Two suffixes sharing a stem means the stem appears with both endings (e.g., stem-ta and stem-ra), which is evidence they fill DIFFERENT slots in the paradigm (e.g., nominative vs. genitive). Same-consonant sharing would only apply if two signs competed for the SAME slot, which is not what stem overlap measures.

The PRD conflates "suffix co-occurrence on the same stem" with "suffix alternation in the same slot." These are opposite phenomena. Co-occurring suffixes fill different paradigm cells; alternating suffixes fill the same cell.

**RECOMMENDATION:**
The entire approach must be redesigned. To properly test Kober's principle, you would need to identify which suffix signs fill the SAME paradigm cell (e.g., two signs that never co-occur on the same stem but appear in the same distributional context). This is much harder and may be infeasible with the available data.

---

## Issue 2: P1 Grid Is Degenerate -- 91% of Signs in Consonant Class 0

**SEVERITY:** CRITICAL

**DESCRIPTION:**
The P1 v5 grid assigns 63 of 69 signs (91.3%) to consonant_class 0. The remaining 6 signs in classes 1-3 are all rare R_-prefix signs with evidence_count=1 and confidence=0.167. This means the grid has effectively ONE consonant class, making it useless for cross-validation or constraint propagation.

All 29 inflectional suffix signs are in consonant_class 0 with confidence=1.0. This means:
- Step 2 of the PRD ("Cross-reference with P1's grid") will show 100% agreement for every pair, because all pairs are trivially in the same consonant class.
- Gate 2 ("Constraint-P1 Agreement >= 70%") will always pass, but this is meaningless -- it passes because P1 has no discriminatory power.
- Step 5 ("Propagate Constraints to Unknown Signs") cannot narrow candidates because P1 provides no consonant discrimination. Every sign's "prior" is consonant_class 0.

**EVIDENCE:**
```
Consonant class distribution: {0: 63, 3: 2, 1: 2, 2: 2}
All 29 suffix signs: consonant_class=0, confidence=1.0
```

**RECOMMENDATION:**
P1 must be fixed BEFORE this module can add value. The degenerate grid means any suffix constraint that agrees with P1 is vacuous, and any that disagrees is automatically suspect. Wait for the Jaccard sign classification PRD (PRD_JACCARD_SIGN_CLASSIFICATION.md) to produce a non-degenerate grid, then revisit.

---

## Issue 3: ALL 29 Suffix Signs Have Known LB Readings -- Zero Constraint Value

**SEVERITY:** HIGH

**DESCRIPTION:**
The PRD's practical justification is constraining unknown signs to unlock the 184 one-sign-missing stems. However, ALL 29 inflectional suffix signs already have known Linear B readings:

AB37=ti, AB57=ja, AB60=ra, AB04=te, AB59=ta, AB27=re, AB73=mi, AB06=na, AB77=ka, AB67=ki, AB26=ru, AB80=ma, AB53=ri, AB41=si, AB07=di, AB24=ne, AB09=se, AB69=tu, AB51=du, AB30=ni, AB65=ju, AB17=za, AB01=da, AB28=i, AB81=ku, AB56=pa, AB39=pi, AB58=su, AB02=ro.

Since the module only analyzes signs IN suffix positions, and all suffix-position signs are already known, the module cannot produce NEW constraints on unknown signs. It can only cross-validate already-known readings.

**EVIDENCE:**
The corpus marks all AB-prefix signs as `tier3_undeciphered`, but the project maintains a separate `sign_to_ipa.json` with 51 signs (47 with AB-code mappings via the LB corpus). All 29 inflectional suffix signs are in this known set.

The PRD's Risk table (Section 8) mentions this possibility ("Too few unknown signs in suffix positions") and rates it LOW severity, MEDIUM likelihood. The actual data shows it is 100% certain: zero unknown signs in suffix positions.

**RECOMMENDATION:**
The module's value proposition must be reframed. It cannot unlock new sign readings from suffix positions. Its only possible value is cross-validating existing LB-to-LA reading assumptions, which is useful but far less impactful than the PRD claims.

---

## Issue 4: The 184 One-Sign-Missing Count Is Inflated

**SEVERITY:** MEDIUM

**DESCRIPTION:**
The PRD and session report claim 184 stems are "missing JUST ONE syllable" from having full phonetic readings. Recomputation from the actual data yields 149-151 depending on definition (using LB corpus AB mappings: 149; using sign_to_ipa.json: 151). The discrepancy is ~20%.

More importantly, the session report's own tally says "426 fully phonetic, 219 partially phonetic, 142 no phonetics" which sums to 787 but does not match the 184 figure. The 184 appears to use a different counting methodology that was not preserved.

**EVIDENCE:**
Using the LB corpus's 58 AB-code mappings as "known":
```
0 unknown: 578 stems
1 unknown: 149 stems
2 unknown: 26 stems
3+ unknown: 34 stems
```

Using sign_to_ipa.json's 47 AB-code mappings:
```
0 unknown: 576 stems
1 unknown: 151 stems
```

**RECOMMENDATION:**
Pin down the exact definition and reproduce the count. The 184 figure appears to use a broader set of "known" signs than either current data source supports. The practical target set may be smaller than claimed.

---

## Issue 5: P2 Paradigm Table Is a Single Mega-Class (Not 2 Useful Classes)

**SEVERITY:** HIGH

**DESCRIPTION:**
The PRD states P2 has "2 paradigm classes." In practice:
- Paradigm class 0: 384 members, 91 slots, mean completeness 1.9%
- Paradigm class 1: 15 members, 6 slots, all R_-prefix (romanized) signs

Class 0 is a single amorphous bucket containing essentially ALL AB-prefix words. With 91 slots and 1.9% completeness (most stems attested with only 1-2 suffixes), the paradigm structure is too sparse to be meaningful. Class 1 is an entirely different sign system (romanized signs with R_ prefix) and cannot be compared to Class 0 for cross-paradigm vowel constraints.

The RUN_LOG records that P2 originally produced 39 paradigm classes (which the log calls "over-fragmented"), and the current 2-class output is the result of raising the Jaccard threshold to consolidate them. Both extremes (39 and 2) are problematic. At 39, the classes are too small to detect patterns. At 2, the classes are too large to represent real paradigm distinctions.

**EVIDENCE:**
```
Paradigm 0: 384 members, 91 slots, completeness=0.019
Paradigm 1: 15 members, 6 slots (R_ signs only)
```

Step 3 (cross-paradigm same-vowel constraints) is entirely infeasible because the two classes use different sign systems (AB vs R_). There is no way to find "corresponding slots" between them.

**RECOMMENDATION:**
Step 3 should be removed from the PRD entirely. It will produce zero constraints. If cross-paradigm analysis is desired, P2 must first be re-run with a threshold that produces 5-15 paradigm classes within the AB sign system.

---

## Issue 6: Segmentation Method Is Purely Heuristic (suffix_strip, Not MDL)

**SEVERITY:** MEDIUM

**DESCRIPTION:**
The PRD's Section 3.3 says P2 uses "MDL/BPE segmentation." The actual P2 output shows all 787 words were segmented using `suffix_strip`, not MDL or BPE. Suffix-stripping is a simpler heuristic: for each word, check if its last 1-3 signs match a known suffix pattern, and if so, split there.

The suffix-strip method has a well-known failure mode: it will happily strip a suffix that is actually part of the stem. For example, if the word is stem+AB60 and AB60(ra) happens to be a frequent suffix, the method strips it even if AB60 is part of the stem. This over-segmentation inflates suffix frequencies and creates spurious stem-suffix associations.

**EVIDENCE:**
```
Segmentation methods: {'suffix_strip': 787}
Confidence distribution: 1.0 = 443, <0.5 = 215, 0.5-0.79 = 76, 0.8-0.99 = 53
```

215 of 787 segmentations (27%) have confidence < 0.5, indicating the method itself flags substantial uncertainty. These low-confidence segmentations will introduce noise into the suffix alternation sets.

**RECOMMENDATION:**
Filter out segmentations with confidence < 0.5 before computing stem overlaps. This removes ~27% of the data but substantially reduces spurious suffix assignments. Also: correct the PRD's claim that P2 uses "MDL/BPE" -- it uses suffix_strip.

---

## Issue 7: Circularity Between P1 and Suffix Constraints

**SEVERITY:** MEDIUM

**DESCRIPTION:**
P2's segmenter directly consults P1's phonotactic constraints at segmentation boundaries:
- Forbidden bigrams at the stem-suffix boundary cause segmentation rejection
- Favored bigrams at the boundary also cause rejection (to avoid splitting within collocations)

This means P2's suffix inventory is shaped by P1's bigram statistics. If P1's bigrams are wrong (which is likely given the degenerate grid), P2's suffixes are systematically biased. Suffix constraints derived from P2 would then be feeding P1-derived errors back as "independent evidence."

The PRD (Section 3.3) claims "independence of provenance" between P1 and this module. This is only partially true. While this module's constraint EXTRACTION logic is independent of P1, the input DATA (P2's suffixes) is P1-dependent. The constraints are not fully independent.

**EVIDENCE:**
From `pillar2/segmenter.py`:
```python
# Forbidden bigram at boundary: reject
if boundary_pair in pillar1.forbidden_bigram_set:
    return False
# favored pair -- reject
if boundary_pair in pillar1.favored_bigram_set:
    return False
```

**RECOMMENDATION:**
The PRD should explicitly acknowledge that suffix constraints are NOT independent of P1 -- they share a common data ancestor. The circularity risk (Section 8) rates this MEDIUM severity, LOW likelihood. Given the degenerate P1 grid, LOW likelihood should be upgraded to HIGH. The 30% conflict threshold for halting is appropriate but should be accompanied by a direct test: run P2 with P1 constraints disabled and compare suffix inventories.

---

## Issue 8: Gate 1 (LB Validation) Tests the Wrong Thing

**SEVERITY:** HIGH

**DESCRIPTION:**
Gate 1 asks: "Does the suffix constraint algorithm correctly identify same-consonant pairs when applied to Linear B?" This is a necessary validation, but it tests the algorithm in isolation, not the algorithm applied to P2's actual output.

The LB corpus has clean, well-attested paradigms with dozens of stems per suffix. The LA corpus has sparse, noisy paradigms with 1-2 stems per suffix for most entries. Even if the algorithm works perfectly on LB data, it may produce garbage on LA data because the input quality is fundamentally different.

More critically, Gate 1 tests whether Kober's principle holds for LB suffixes -- but we already know it does (that is how LB was deciphered). The real question is whether P2's segmentation correctly identifies suffix positions in LA, and Gate 1 does not test this.

**EVIDENCE:**
- LB corpus: 142 inscriptions, 448 words, well-studied paradigms
- LA corpus: 879 inscriptions, 787 segmented words, 12.6% paradigm completeness
- The issue is not algorithmic (Gate 1) but data quality (sparse paradigms, heuristic segmentation)

**RECOMMENDATION:**
Add a Gate 1.5: "Degrade the LB corpus to match LA sparsity (randomly remove 87% of attestations) and re-run. Does the algorithm still achieve >= 50% accuracy?" This tests whether the method is robust to the actual data conditions.

---

## Issue 9: Compound Suffix Analysis (Step 4) Is More Promising Than Step 1, But Under-Specified

**SEVERITY:** LOW (this is a missed opportunity, not a flaw)

**DESCRIPTION:**
Step 4 (compound suffix analysis) groups multi-sign suffixes by shared head or tail. For example, AB06+AB41 and AB06+AB69 share head AB06(na); the tails AB41(si) and AB69(tu) would form an alternation set. This is actually a more defensible application of Kober's principle because:

1. The second sign of a compound suffix is more likely to be a true morphological alternant (same slot, different value) than two independent single-sign suffixes.
2. The shared head provides structural evidence that the words are in the same paradigm.

However, Step 4 is under-specified: it does not say how many compound suffix groups exist in the data, what their overlap counts are, or whether the alternation sets are non-trivial.

**EVIDENCE:**
P2 has 41 multi-sign suffixes. Potential shared-head groups include:
- AB06+AB41, AB06+AB69 (head=AB06/na; tails=si,tu)
- AB59+AB06, AB59+AB27 (head=AB59/ta; tails=na,re)
- AB53+AB06, AB53+AB57 (head=AB53/ri; tails=na,ja)

The tail signs in these groups do have different consonants (s/t, n/r, n/j), so Kober's principle still fails. But the sample is small and worth investigating further.

**RECOMMENDATION:**
Elevate Step 4 to the primary analysis path, with its own dedicated validation gate. Also test: does the shared-head grouping correlate with same-vowel (rather than same-consonant) sharing?

---

## Issue 10: The 51/53 Sign Count Discrepancy

**SEVERITY:** LOW

**DESCRIPTION:**
The PRD (Section 5.5) says sign_to_ipa.json has "53 known signs as of the session report." The actual file has 51 entries. A previous PRD reference says "51 signs after Tier 0 fixes." The discrepancy is minor but indicates the PRD was not checked against the live data.

**EVIDENCE:**
`sign_to_ipa.json`: 51 entries.
PRD text: "53 known signs."

**RECOMMENDATION:**
Update the PRD to say 51.

---

## Summary Table

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Kober's principle empirically falsified (10% agreement vs 10% chance) | CRITICAL | BLOCKING |
| 2 | P1 grid degenerate (91% in consonant class 0) | CRITICAL | BLOCKING |
| 3 | All 29 suffix signs already have known LB readings | HIGH | Undermines value proposition |
| 4 | 184 one-sign-missing count inflated (actual: ~150) | MEDIUM | Data error |
| 5 | Paradigm table is one mega-class + one irrelevant class | HIGH | Step 3 infeasible |
| 6 | Segmentation is heuristic suffix_strip, not MDL | MEDIUM | Noise risk |
| 7 | P1-P2 circularity not fully independent | MEDIUM | Design flaw |
| 8 | Gate 1 tests wrong conditions (clean LB vs sparse LA) | HIGH | Validation gap |
| 9 | Compound suffix analysis under-explored | LOW | Missed opportunity |
| 10 | Sign count discrepancy (51 vs 53) | LOW | Cosmetic |

---

## Overall Assessment

The Suffix Constraints approach rests on a fundamental misapplication of Kober's principle. The PRD conflates suffix co-occurrence (two different suffixes on the same stem) with suffix alternation (two signs competing for the same paradigm slot). These are opposite phenomena:

- **Co-occurring suffixes** mark DIFFERENT grammatical functions (e.g., nominative -ta, genitive -ra on the same stem). They should have DIFFERENT consonants. The data confirms this: 90% of high-overlap pairs have different consonants.

- **Alternating suffixes** would mark the SAME grammatical function with different phonetic realizations (e.g., first declension -ta vs second declension -te). These would share a consonant. But P2's paradigm table does not distinguish paradigm cells at this level of granularity.

Until this conceptual error is corrected, the module will produce constraints that are worse than random. The approach should not proceed to implementation.

**Potential salvage paths:**
1. Invert the logic: treat high-overlap suffix pairs as DIFFERENT-consonant constraints (exclusion constraints rather than inclusion constraints). This matches the data.
2. Focus on compound suffix analysis (Step 4), which has a stronger structural basis.
3. Wait for non-degenerate P1 grid (Jaccard classification) before attempting consonant/vowel constraint extraction.
4. Redefine "alternation" to mean paradigm-cell competition (two signs that NEVER co-occur on the same stem but appear in the same distributional context), not stem overlap.
