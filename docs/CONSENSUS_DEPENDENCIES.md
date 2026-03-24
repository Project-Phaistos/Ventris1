# Consensus Dependency Registry

Every external scholarly claim the Ventris1 system relies on. Each entry documents the source, acceptance level, testability, and blast radius if wrong.

---

### CD-001: Sign type classification (syllabogram vs logogram)
**Source:** GORILA catalogue (Godart & Olivier 1976-1985), SigLA database (Salgarella & Castellan)
**Acceptance:** Universal — the GORILA sign list is the standard reference for Linear A, used by all researchers
**Independently testable:** ~~Partially via sign count heuristic~~ **RETESTED 2026-03-24: The sign count heuristic V(1+C)=N is NOT discriminative.** For any N in [50,150], V(1+C) fits within +/-1 for some V in [3,6]. The equation accepts N=62, N=75, N=100, and N=142 equally well. It only rules out extreme values (N<18 or N>300), which nobody claims. **The heuristic cannot verify the GORILA classification.**

**Stronger independent tests exist:**
1. **Grid rectangularity test (moderate):** If the tier1 signs form a CV syllabary, the grid should be approximately rectangular. Tested: row sizes range 2-6 (most are 3-5), column sizes range 6-16 (most are 9-13). The grid IS approximately rectangular. But this test uses LB values to assign signs to cells, so it's not fully independent of CD-008.
2. **Distributional clustering test (strong):** Pillar 1's alternation-based spectral clustering recovers consonant groups from distributional evidence alone, achieving ARI=0.615 vs LB. This is the strongest independent evidence that the tier1 signs behave as a CV syllabary — the clustering discovers CV structure from the data without knowing which signs are syllabograms.

**Used by:** Pillar 1 (filters corpus to syllabograms only), propagates to Pillars 2, 3, 4
**What breaks if wrong:** All of Pillar 1 operates on the wrong sign set. A misclassified logogram treated as a syllabogram would corrupt the C-V grid. A misclassified syllabogram excluded from analysis would create a gap.
**Mitigation:** Run Pillar 1 on ALL signs (including unknowns) as a sensitivity analysis. Compare results to the filtered run. If qualitatively similar, the classification is not load-bearing for the main findings.
**Remaining vulnerability:** The 80 tier3 "undeciphered syllabograms" are classified as syllabograms by GORILA but their phonetic values are unknown. Some may actually be logograms. The top 9 by frequency (count >= 10) are the most likely to be genuine syllabograms; the 38 with count = 1 (hapax) are uncertain.

---

### CD-002: CV syllabary assumption
**Source:** Sign count analysis (Evans 1909, Bennett 1951, Packard 1974). ~60 phonetic signs matches the CV syllabary parameter space (V=3-6, C=9-19).
**Acceptance:** Universal — no serious alternative has been proposed. The sign count excludes both an alphabet (~26 signs) and a logosyllabic system (hundreds of signs).
**Independently testable:** ~~Yes via V(1+C)=N~~ **RETESTED 2026-03-24: V(1+C)=N is not discriminative (see CD-001).** However, the grid rectangularity test and the distributional clustering test (ARI=0.615) provide stronger independent support. The CV assumption is also supported by the positional frequency analysis: the existence of signs with significantly elevated initial-position rates (AB08 at E=2.72) is predicted by the CV model (pure vowel signs appear initially) and would not occur in an alphabetic or logographic system.
**Used by:** Pillar 1 (grid construction assumes CV structure), Pillar 2 (segmentation respects syllable = 1 sign)
**What breaks if wrong:** If some signs are CVC or CVCV, the grid has wrong dimensions. Morphological segmentation could split within multi-phone signs.
**Mitigation:** Check for signs that appear in positions inconsistent with CV (e.g., signs that only appear in clusters, never alone — might be CVC). Flag anomalies.

---

### CD-003: AB code assignments
**Source:** GORILA catalogue. Each sign gets a standardized AB code (e.g., AB08, AB59).
**Acceptance:** Universal — GORILA is the standard.
**Independently testable:** No — these are conventional labels, not empirical claims. The assignment is definitional.
**Used by:** All pillars (as sign identifiers)
**What breaks if wrong:** Nothing — AB codes are arbitrary labels. The analysis doesn't depend on which code maps to which sign, only on consistency.
**Mitigation:** None needed. If GORILA updates its numbering, we update ours.

---

### CD-004: Commodity ideogram identifications (FIG, GRAIN, WINE, OLIVE, etc.)
**Source:** Pictographic identification (Evans 1909, Bennett 1950). The signs visually resemble their referents.
**Acceptance:** Universal for the major commodities (FIG, GRAIN, WINE, OLIVE). Less certain for minor ones (TEXTILE, OIL).
**Independently testable:** Partially — archaeological context provides independent evidence (tablets found in grain storerooms tend to contain the GRAIN ideogram). But the pictographic interpretation itself is subjective.
**Used by:** Pillar 4 (semantic field assignment: sign-groups near FIG ideogram get COMMODITY:FIG)
**What breaks if wrong:** Semantic field labels are wrong. The CO-OCCURRENCE PATTERN is still real (sign-group X really does appear near ideogram Y), but our label for what Y represents would be wrong.
**Mitigation:** In Pillar 5, use the co-occurrence pattern directly (sign-group X co-occurs with ideogram Y) rather than the label (X is related to figs). The label is convenient but not essential.

---

### CD-005: Numeral values (A701=1, A704=10, A705=100)
**Source:** Bennett 1950, based on analysis of totaling lines and Linear B comparison.
**Acceptance:** Broadly accepted for units and tens. Hundreds less certain. Fractions are debated.
**Independently testable:** Partially — if ku-ro totals consistently sum correctly with these values, the values are confirmed. Our current verification (0 matching, 1 discrepant, 9 unparsable) is inconclusive.
**Used by:** Pillar 4 (transaction analysis, total verification)
**What breaks if wrong:** Total verification fails (or gives false positives). Numeral-based quantity analysis is wrong.
**Mitigation:** Flag all parsed numerals with their confidence. Use total verification as a TEST of the values, not an assumption. If verification fails, the values may need revision.

---

### CD-006: ku-ro = "total"
**Source:** Bennett 1950. ku-ro consistently appears before summation lines on accounting tablets.
**Acceptance:** Universal — no serious challenge.
**Independently testable:** YES — Pillar 3 independently confirms ku-ro is a final-position structural marker (55.9% final rate, p < 0.001) from positional statistics alone, without knowing what it "means."
**Used by:** Pillar 3 (functional word identification), Pillar 4 (transaction analysis)
**What breaks if wrong:** The semantic label "total" is wrong, but the structural role (final-position marker associated with summation context) is independently confirmed.
**Status:** CONSENSUS_CONFIRMED — independent evidence agrees with consensus.

---

### CD-007: Place name identifications (PA-I-TO = Phaistos, I-DA = Ida, A-DI-KI-TE = Dikte)
**Source:** Linear B cognates (Ventris & Chadwick 1956) + geographic context (tablets found at or near the named sites).
**Acceptance:** Widely accepted but not absolutely certain. Depends on LB phonetic values being transferable to Linear A.
**Independently testable:** Partially — finding PA-I-TO at/near Phaistos provides geographic confirmation. But the phonetic reading depends on LB transfer (CD-008).
**Used by:** Pillar 4 (phonetic anchors, place name semantic field)
**What breaks if wrong:** Phonetic anchors extracted from place names are wrong. Semantic field PLACE:PHAISTOS is misassigned.
**Mitigation:** Place name anchors get confidence < 1.0 (currently 0.90 for Phaistos, 0.80 for Ida). Pillar 5 should not depend critically on any single place name identification.

---

### CD-008: Linear B phonetic values are approximately transferable to Linear A
**Source:** Packard (1974) — statistical validation showing real LB values produce significantly more doublets than 9 false decipherments. About 80-90% of LA phonetic signs resemble LB signs.
**Acceptance:** Broadly accepted as a working hypothesis. Not universally certain.
**Independently testable:** YES — Pillar 1's independent grid construction, measured against LB values, gives ARI=0.615. This is the test. High ARI = transfer is valid; low ARI = transfer is problematic.
**Used by:** Pillar 1 (LB soft validation only — NOT as input), Pillar 4 (place name readings)
**What breaks if wrong:** LB validation scores are meaningless. Place name identifications (CD-007) lose their phonetic basis. But Pillar 1's independent findings (vowel identification, consonant clustering) are unaffected.
**Status:** INDEPENDENT_VALIDATED — ARI=0.615 provides independent confirmation.

---

### CD-009: Sign-group segmentation (physical dividers on tablets)
**Source:** Archaeological observation. Linear A tablets have physical marks (vertical strokes, dots, spaces) that separate sign-groups. SigLA transcribes these as word boundaries.
**Acceptance:** Universal for inscriptions WITH dividers. Many inscriptions have NO dividers.
**Independently testable:** Yes for divided inscriptions (the marks are physically present). No for undivided inscriptions (segmentation is editorial).
**Used by:** Pillar 2 (morphological segmentation operates on sign-groups), Pillar 3 (distributional analysis), Pillar 4 (co-occurrence analysis)
**What breaks if wrong:** If dividers don't correspond to linguistic word boundaries, our "sign-groups" are wrong units. Suffix analysis could identify intra-word boundaries as morpheme boundaries.
**Mitigation:** For divided inscriptions, the physical marks are strong evidence. For undivided inscriptions, we should NOT assume segmentation. Currently, the SigLA corpus has 473 multi-word inscriptions (with dividers) and 359 with no segmentation. Our analysis primarily uses the divided inscriptions.

---

### CD-010: Inscription type labels (Tablet, libation_table, Nodule, etc.)
**Source:** Archaeological classification by excavators and SigLA database.
**Acceptance:** Universal — inscription types are based on physical properties (shape, material, context).
**Independently testable:** No — these are physical classifications, not linguistic ones.
**Used by:** Pillar 3 (word class hints: tablet vs. libation), Pillar 4 (formula analysis filters to libation inscriptions)
**What breaks if wrong:** If a "libation table" is actually something else, our formula analysis includes wrong inscriptions. But the physical classification (stone vessel with pour spout) is objective.
**Mitigation:** Low risk — physical classification is well-established.
