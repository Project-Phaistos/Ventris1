# Adversarial Verification: Compound Suffix Constraint Extraction

**Date:** 2026-04-06
**Auditor:** Claude (adversarial critic agent)
**Subject:** Compound suffix analysis from `docs/logs/2026-04-06-suffix-slot-redesign-plan.md` (commit `8d60a25`)
**Scope:** Statistical validity, circularity, sample size, unknown signs, constraint direction, data quality

---

## 1. Statistical Validity

### 1.1 Reported vs. Verified Numbers

The redesign plan reports:
- Shared-head tails same-consonant: 31.6% (19 pairs), p = 0.013
- Shared-tail heads same-vowel: 57.9% (19 pairs), p = 0.003

**Recomputation from P2 output yields slightly different numbers.** The pair counts depend on which compound suffix types are included. The redesign plan uses the full set including types with only 1 attestation (conf=0.2), while the P2 paradigm table may group differently from the raw segmented lexicon.

Recomputation from the raw segmented lexicon (all 2-sign compound suffixes, no confidence filter):
- Shared-head same-C: **6/16 = 37.5%**, binomial p = **0.0049**
- Shared-tail same-V: **14/26 = 53.8%**, binomial p = **0.0020**

The pair counts differ (16 vs 19 for shared-head; 26 vs 19 for shared-tail) because the redesign plan appears to have used a subset of groups. The rates and significance are comparable or stronger in the recomputation.

### 1.2 Bonferroni Correction

With 2 tests (shared-head + shared-tail), Bonferroni-corrected p-values:
- Shared-head: 0.0049 x 2 = **0.0097** (significant at 0.01)
- Shared-tail: 0.0020 x 2 = **0.0039** (significant at 0.01)

The user's concern that Bonferroni makes p=0.013 marginal (0.026 after correction) applies to the redesign plan's numbers but NOT to the recomputed numbers. The recomputed values survive Bonferroni at alpha=0.01.

**However**, this ignores the broader multiple testing context. The redesign plan tested 6 hypotheses (H1-H4 + 2 compound analyses). With 6 tests, Bonferroni gives:
- Shared-head: 0.0049 x 6 = **0.029** (marginal at 0.05)
- Shared-tail: 0.0020 x 6 = **0.012** (significant at 0.05)

**VERDICT: The shared-tail same-vowel signal survives aggressive correction. The shared-head same-consonant signal is marginal under full correction.**

### 1.3 Group Concentration

**CRITICAL FINDING: The signal is driven by very few groups.**

Shared-head same-consonant (6 same-C pairs from 4 groups):
- **AB01(da)**: 3 of 6 same-C pairs (50%). All r-series: ro, re, ra.
- AB07(di): 1 pair (na+ni, n-series)
- AB59(ta): 1 pair (na+ne, n-series)
- AB73(mi): 1 pair (na+nu, n-series)

**3 of the 4 contributing groups share the same consonant (n-series) in their same-C pair.** This means the n-series consonant drives 3/6 = 50% of the signal, and the r-series drives the other 50%. The signal is concentrated in exactly 2 consonant series out of ~10. If either the AB01 group (r-series) or the n-series pairs are segmentation artifacts, half the evidence disappears.

Shared-tail same-vowel (14 same-V pairs from 5 groups):
- **AB27(re)**: 6 of 14 same-V pairs (43%). All a-vowel: da, ta, ra, ma.
- **AB24(ne)**: 3 pairs. All a-vowel: sa, ta, ra.
- AB06(na): 3 pairs. All i-vowel: di, ri, mi.
- AB59(ta): 1 pair (ni+pi, i-vowel)
- AB60(ra): 1 pair (di+ki, i-vowel)

**The signal is dominated by 2 vowels: a (9 pairs, 64%) and i (5 pairs, 36%).** This is consistent with the known skew in suffix vowel distribution: a=31%, i=31% of the 29 inflectional suffixes. Groups of a-vowel heads and i-vowel heads are more likely to form by chance because those vowels are more common.

The adjusted baseline (25.6%) accounts for this skew, and the signal still exceeds it. But the practical concern remains: the evidence for same-vowel constraints on e-vowel, o-vowel, and u-vowel signs is zero.

---

## 2. Circularity with P2

### 2.1 P2's Segmentation Feeds the Data

P2's `suffix_strip` segmenter determines which sign sequences are labeled as compound suffixes. The segmenter uses:
- A hardcoded suffix inventory built from frequency/productivity thresholds
- P1's phonotactic constraints at the stem-suffix boundary (forbidden/favored bigrams)

If P1's bigrams are wrong, P2 may misidentify stem-internal sequences as compound suffixes. The redesign plan correctly notes this risk but does not quantify it.

### 2.2 Segmentation Confidence is Alarmingly Low

**This is the most damaging finding in the audit.**

The segmentation confidence for compound suffix instances:
- conf = 0.6: 6 instances (6%) -- all AB73-AB06 (a single suffix type)
- conf = 0.4: 11 instances (11%)
- conf = 0.3: 43 instances (43%)
- conf = 0.2: 40 instances (40%)

**94% of compound suffix instances have confidence < 0.5.** The confidence formula is `min(1.0, n_stems / 10.0)`, where n_stems is the number of distinct stems attesting the suffix. A confidence of 0.3 means only 3 distinct stems; 0.2 means only 2 distinct stems.

**When filtering to confidence >= 0.5:**
- Only 1 compound suffix type survives: AB73-AB06 (mi-na)
- Zero shared-head groups with >= 2 tails
- Zero shared-tail groups with >= 2 heads
- **The entire compound suffix signal vanishes**

**When filtering to confidence >= 0.4:**
- 4 compound suffix types survive
- Not enough for any shared-head or shared-tail analysis

**When filtering to confidence >= 0.3:**
- 20 compound suffix types survive (of 43 total)
- Some shared-head/tail groups re-emerge, but smaller

This means the statistically significant results reported in the redesign plan depend entirely on compound suffixes attested by only 2-3 stems each. These are the weakest, most uncertain segmentations in P2's output. The suffix boundaries are unreliable, which means the head/tail decomposition is unreliable, which means the same-consonant/same-vowel analysis is built on sand.

### 2.3 Verdict on Circularity

The circularity risk is REAL and SEVERE, not because of P1-P2 feedback loops (though those exist), but because P2's suffix_strip heuristic assigns low confidence to compound suffixes, indicating the segmenter itself does not trust these boundaries. Building phonological constraints on segmentations the segmenter rates at 0.2-0.3 confidence is methodologically unsound.

---

## 3. Sample Size

### 3.1 Number of Compound Suffix Groups with 3+ Members

Shared-head groups with >= 3 tails: **4 groups**
- AB53(ri): 4 tails (te, na, ja, AB66[unknown])
- AB07(di): 3 tails (na, ni, ra)
- AB59(ta): 3 tails (na, ne, re)
- AB01(da): 3 tails (ro, re, ra)

Shared-tail groups with >= 3 heads: **6 groups**
- AB27(re): 4 heads (da, ta, ra, ma)
- AB06(na): 4 heads (di, ri, ta, mi)
- AB60(ra): 3 heads (da, di, ki)
- AB59(ta): 3 heads (ni, pi, ma)
- AB57(ja): 3 heads (pa, se, ri)
- AB24(ne): 3 heads (sa, ta, ra)

The 3+ member groups provide the most reliable evidence. However, each group contributes only C(n,2) pairs (3 pairs for a 3-member group, 6 for a 4-member group). The total pair counts are dominated by the largest groups (AB27 and AB06 with 4 members each produce 6 pairs each = 12 of the 26 total shared-tail pairs).

### 3.2 Is This Enough?

4 shared-head groups and 6 shared-tail groups is marginal but not negligible. The concern is fragility: removing any single group can substantially shift the statistics. Specifically:

- Without the AB01 head group (the strongest, 3/3 r-series same-C): the remaining 3 groups have 3/13 = 23% same-C, which is still above baseline (10.8%) but no longer statistically significant at any reasonable threshold.
- Without the AB27 tail group (the strongest, 6/6 a-vowel same-V): the remaining 5 groups have 8/20 = 40% same-V, still above baseline (25.6%), marginal significance.

**VERDICT: The result is fragile. It depends on 1-2 showcase groups. Removing the best group destroys statistical significance for same-consonant and weakens it for same-vowel.**

---

## 4. All Known Signs Problem

### 4.1 The 29 Inflectional Suffix Signs

27 of 29 inflectional suffix signs have known LB readings via the LB corpus ab_code mapping. The 2 without direct LB ab_code mappings are:
- AB65 (listed as "ju" in the audit's text, but not in the LB corpus sign_inventory ab_codes)
- AB56 (listed as "pa" in the audit's text, but not in the LB corpus sign_inventory ab_codes)

However, both AB65 and AB56 have readings in the project's broader sign knowledge (AB65=ju, AB56=pa from the audit text). So effectively all 29 are known.

### 4.2 Non-Inflectional Signs in Compound Suffixes

9 AB-code signs appear in compound suffixes but are NOT among the 29 inflectional suffixes:
- AB03 = pa (KNOWN in LB)
- AB10 = u (KNOWN in LB)
- AB31 = sa (KNOWN in LB)
- AB55 = nu (KNOWN in LB)
- **AB66 = UNKNOWN in LB**
- **AB76 = UNKNOWN in LB**
- **AB79 = UNKNOWN in LB**
- **AB118 = UNKNOWN in LB**
- **A310 = UNKNOWN in LB**

There are 5 genuinely unknown signs in compound suffix positions. However:

- AB66 appears in one compound suffix group: Head=AB53(ri), as a tail. Its sole groupmate tails (te, na, ja, ni) do not share a consonant uniformly, so the constraint on AB66 from this group is weak.
- AB76 appears in AB76-AB10 (2 instances). AB10 = u (pure vowel). No shared-head or shared-tail group possible with only this one type.
- AB79 appears in AB79-AB30 (2 instances). AB30 = ni. Only one compound suffix type -- no grouping possible.
- AB118 appears in AB41-AB118 (2 instances). Only one compound suffix type.
- A310 appears in A310-AB28 (2 instances). Only one compound suffix type.

**VERDICT: Of the 5 unknown signs, only AB66 participates in a compound suffix group with >= 2 members, and that group does not produce a clean same-consonant constraint. The module produces ZERO actionable constraints on unknown signs.**

---

## 5. Direction of the Constraint

### 5.1 The Claim

The redesign plan claims:
- Shared-head tails share consonant (e.g., da-ro, da-re, da-ra: tails ro/re/ra share consonant r)
- Shared-tail heads share vowel (e.g., X-re where X = da/ta/ra/ma: heads share vowel a)

### 5.2 Verification: Is This Paradigmatic or Coincidental?

The constraint only holds if the compound suffixes are genuine paradigmatic variants -- i.e., the same morphological slot filled by different signs. The alternative is that these are unrelated compound suffixes that happen to share a sign.

**Evidence FOR paradigmatic interpretation:**
- The AB01 head group (da-ro, da-re, da-ra) is textbook: all 3 tails are r-series with different vowels. This is exactly what vowel alternation in an inflectional paradigm looks like.
- The AB27 tail group (da-re, ta-re, ra-re, ma-re) shows 4 heads all with vowel a. This is consistent with consonant alternation holding vowel constant.

**Evidence AGAINST paradigmatic interpretation:**
- The compound suffixes are EACH attested on only 2-3 stems. With such sparse data, we cannot verify that da-ro and da-re appear on the SAME stems (true paradigmatic alternation). If da-ro appears on stem X and da-re appears on unrelated stem Y, they are not paradigmatic variants -- they are independent suffix sequences that happen to share a head.
- The redesign plan does not report stem overlap between compound suffixes within shared-head groups. This is a critical missing piece of evidence.
- The n-series concentration (3 of 4 shared-head contributing groups have n-series same-C pairs involving na, ne, ni, or nu) could reflect that n-series signs (na, ne, ni) are simply the most common in compound suffix tails, making random same-C matches more likely.

### 5.3 The User's Counterexample

The user correctly identifies: da-ro, da-ti, da-me would be a shared-head group where tails ro/ti/me do NOT share a consonant. This pattern would be expected if the "shared head" is not a morphological head but a stem-final sign that happens to precede different suffixes.

From the data: Head=AB53(ri) has tails = te, na, ja, ni, AB66. The tails te/na/ja/ni have 4 different consonants (t, n, j, n). Only na/ni share consonant n. This is the exact counterexample pattern -- a shared head with heterogeneous tails. The 1/6 same-C rate for this group is consistent with random chance.

**The constraint holds strongly for AB01(da) and weakly or not at all for other groups.** The question is whether AB01's perfect 3/3 r-series result is a genuine morphological pattern or a lucky coincidence in a sample of 4 groups.

---

## 6. P2 Output: What Do Compound Suffixes Actually Look Like?

### 6.1 Inventory

100 compound suffix instances across 43 unique 2-sign suffix types.

Most frequent types:
- AB73-AB06 (mi-na): 6 instances, conf=0.6
- AB59-AB06 (ta-na): 4 instances, conf=0.4
- AB17-AB09 (za-se): 4 instances, conf=0.4
- AB06-AB41 (na-si): 3 instances, conf=0.4
- AB06-AB69 (na-tu): 3 instances, conf=0.3

### 6.2 Do They Look Like Morphological Units?

Some compound suffixes look linguistically plausible:
- **mi-na** (AB73-AB06): 6 instances, highest confidence. Could be a 2-morpheme suffix (e.g., ablative-locative in Anatolian languages).
- **ta-na** (AB59-AB06): 4 instances. A recognizable suffix in Minoan studies (cf. Ventris & Chadwick).

Others look like segmentation artifacts:
- **za-se** (AB17-AB09): Less linguistically motivated. "za" and "se" are rarely co-morphemic in known Aegean languages.
- Many 2-instance types (conf=0.2-0.3) appear to be stem-final sequences misidentified as suffixes.

### 6.3 The R_ Prefix Signs

Several compound suffixes involve R_-prefix (romanized) signs: R_ka-R_na-R_si, R_ti-R_nu, R_sa-R_ra-R_me, R_wa-R_ja. These come from Paradigm Class 1 (15 members) and represent a completely different notation system. They cannot be compared to AB-code compound suffixes for cross-paradigm analysis.

---

## 7. Summary Table

| Check | Finding | Severity |
|-------|---------|----------|
| Statistical validity (Bonferroni) | Shared-tail survives at 0.01; shared-head marginal at 0.05 under 6-test correction | MEDIUM |
| Group concentration | Same-C driven by 2 consonant series (r, n). Same-V driven by 2 vowels (a, i). Removing AB01 group destroys same-C significance. | HIGH |
| Segmentation confidence | **94% of compound suffix instances have confidence < 0.5. Signal vanishes entirely when filtering to conf >= 0.5.** | CRITICAL |
| Circularity with P2 | P2's suffix_strip depends on P1 bigrams. Low confidence means boundary identification is unreliable. | HIGH |
| Sample size (3+ groups) | 4 shared-head, 6 shared-tail groups with 3+ members. Marginal but non-trivial. | MEDIUM |
| Unknown signs | 5 unknown signs in compound suffixes, but only AB66 participates in a group, and that group produces no clean constraint. **Zero actionable constraints on unknowns.** | HIGH |
| Constraint direction | AB01 group is textbook paradigmatic. Other groups are mixed or weak. No stem-overlap verification exists. | MEDIUM |
| Paradigmatic vs. coincidental | Not verified. Missing evidence: do compound suffixes in the same shared-head group appear on the SAME stems? | HIGH |

---

## 8. Overall Assessment

The compound suffix analysis finds a real statistical signal (p < 0.01 after Bonferroni for same-vowel, marginal for same-consonant). The AB01(da) head group and the AB27(re) tail group are genuinely striking examples. **The signal is real but fragile, and its practical value is near zero.**

### Why Practical Value Is Near Zero

1. **Zero constraints on unknown signs.** All suffix signs that participate in informative groups already have known LB readings. The one unknown sign in a group (AB66) gets no useful constraint.

2. **The 184 one-sign-missing stems are not helped.** The missing signs are in stem positions, not suffix positions. Compound suffix constraints only constrain suffix-position signs, which are already known.

3. **The signal depends on the weakest segmentations.** Filtering to conf >= 0.5 leaves exactly 1 compound suffix type and zero analyzable groups. The entire result is built on segmentations that P2 itself rates at 0.2-0.3 confidence.

### What the Signal IS Good For

1. **Methodological validation.** The compound suffix pattern is consistent with Kober's principle applied to compound suffix internal structure. This confirms that the CV syllabary structure of Linear A is detectable in morphological data, which validates the broader decipherment framework.

2. **A template for growth.** As new inscriptions are published and the corpus grows, compound suffix groups will expand. The analysis framework is correct even if the current data is too sparse for practical constraints.

### Recommendations

1. **Do not invest implementation time** in a compound suffix constraint extraction module. The practical yield (zero unknown-sign constraints) does not justify the engineering cost.

2. **Preserve the analysis** as a methodological finding in the session report. The fact that Kober's principle works on compound suffix internal structure (but not single-sign suffix co-occurrence) is a genuine scientific result worth documenting.

3. **If proceeding despite this audit**, the minimum requirement is:
   - Verify stem overlap within shared-head groups (do compound suffixes in the same group appear on the same stems?).
   - Exclude segmentations with confidence < 0.3.
   - Report the leave-one-group-out sensitivity analysis.
   - Do NOT claim novel constraints on unknown signs unless new evidence emerges.

4. **The real next step for unlocking unknowns** is the Jaccard sign classification (19 consonant clusters, ARI=0.342), which constrains unknown signs directly via distributional similarity, not via suffix morphology. Prioritize integration of Jaccard constraints into the iterative decipherment loop over suffix constraint extraction.

---

## Appendix: Recomputed Statistics

### A. Shared-Head Same-Consonant (All Pairs, No Confidence Filter)

| Head | Tails (with reading) | Same-C pairs | Total pairs |
|------|---------------------|:---:|:---:|
| AB53(ri) | te, na, ja, AB66(?), ni | 1/6 (na+ni) | 6 |
| AB01(da) | ro, re, ra | 3/3 (all r-series) | 3 |
| AB07(di) | na, ni, ra | 1/3 (na+ni) | 3 |
| AB59(ta) | na, ne, re | 1/3 (na+ne) | 3 |
| AB73(mi) | na, nu | 1/1 (n-series) | 1 |
| **Total** | | **6/16 (37.5%)** | **16** |

Note: AB53's group includes AB66 (unknown), excluded from pair counting for known-answer validation.

Binomial test: p = 0.0049 (H0: p = 0.108). Bonferroni x 6: p = 0.029.

### B. Shared-Tail Same-Vowel (All Pairs, No Confidence Filter)

| Tail | Heads (with reading) | Same-V pairs | Total pairs |
|------|---------------------|:---:|:---:|
| AB27(re) | da, ta, ra, ma | 6/6 (all vowel-a) | 6 |
| AB06(na) | di, ri, ta, mi | 3/6 (i-vowel: di+ri+mi) | 6 |
| AB24(ne) | sa, ta, ra | 3/3 (all vowel-a) | 3 |
| AB60(ra) | da, di, ki | 1/3 (i-vowel: di+ki) | 3 |
| AB57(ja) | pa, se, ri | 0/3 | 3 |
| AB59(ta) | ni, pi, ma | 1/3 (i-vowel: ni+pi) | 3 |
| AB02(ro) | da, ku | 0/1 | 1 |
| AB09(se) | za, i | 0/1 | 1 |
| **Total** | | **14/26 (53.8%)** | **26** |

Binomial test: p = 0.0020 (H0: p = 0.256). Bonferroni x 6: p = 0.012.

### C. Confidence Distribution

| Confidence | Instances | Percentage |
|:---:|:---:|:---:|
| 0.6 | 6 | 6% |
| 0.4 | 11 | 11% |
| 0.3 | 43 | 43% |
| 0.2 | 40 | 40% |

Compound suffix types surviving at each threshold:
- conf >= 0.6: 1 type (AB73-AB06 only)
- conf >= 0.5: 1 type
- conf >= 0.4: 4 types
- conf >= 0.3: 20 types
- All: 43 types
