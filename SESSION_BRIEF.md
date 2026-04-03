# Ventris1 Session Brief — Start Here

**Repo:** https://github.com/Project-Phaistos/Ventris1
**Local:** `C:\Users\alvin\Ventris1\`

---

## What This Project Is

Ventris1 is a computational decipherment system for Linear A, the undeciphered Bronze Age writing system from Minoan Crete (~1800-1450 BCE). It uses 5 structural pillars to analyze the script from the inside out — phonology, morphology, grammar, semantics, then external vocabulary matching. The fundamental axiom: Linear A is a chimaera language (multiple linguistic influences), not a single-language descendant.

## What Has Been Built (Pillars 1-5)

All 5 pillars are implemented with 311 tests passing. Read `docs/RUN_LOG.md` for production run results.

- **Pillar 1:** Phonological grid (4C×5V, Kober-anchored vowels at 95% accuracy, consonant ARI=0.615 vs Linear B). Vowel identification triple-validated (LB transfer + Kober alternations + novel Jaccard method F1=89%).
- **Pillar 2:** Morphological decomposition (787 segmented words, 29 inflectional suffixes, 39 paradigm classes).
- **Pillar 3:** Distributional grammar (7 word classes, 24 functional words, ku-ro confirmed as structural marker).
- **Pillar 4:** Semantic anchoring (205 anchored sign-groups, zero bias terms, bias-free design).
- **Pillar 5:** Multi-source vocabulary resolution (18 candidate ancient languages, SCA matching infrastructure, 1,393 extracted academic glosses from eDiAna/IDS/eCUT).

## What Was Tried and Failed (11 Approaches)

Read `docs/logs/2026-03-29-to-04-01-full-session-report.md` for full details. Summary:

Every phonetic matching approach failed because **only 53 of 142 syllabograms have known phonetic values**, producing stems of 1-2 syllables — too short for cross-linguistic comparison by ANY method. PP fleet scores measure inventory compatibility, not cognacy. SCA at 2-sign stem length has 84% collision rate. The bottleneck is DATA SPARSITY, not algorithm choice.

## The Path Forward — The Iterative Decipherment Loop

**Core insight:** Sign identification and cognate matching are a feedback loop. More known sign readings → longer matchable stems → viable cognate matching → confirms sign readings → unlocks more stems.

**The approach:** Use structural analysis (Kober alternations, Jaccard distributional similarity, suffix morphology) to constrain unknown signs to 2-5 possible readings. Then SCA-match the constrained readings against candidate lexicons with proper statistical testing. Where evidence converges across multiple stems, accept new sign readings and iterate.

## Documents to Read (in order)

1. **Ground truth:** `README.md`
2. **Standards:** `STANDARDS_AND_PROCEDURES.md` (3-tier testing, data provenance, consensus dependency layer)
3. **Session history:** `docs/logs/2026-03-29-to-04-01-full-session-report.md`
4. **Weakness audit:** `docs/logs/2026-03-27-pillar-weakness-audit.md`

## The 6 Forward PRDs (execute in phases)

All at `docs/prd/`. Each is self-contained with full background context.

### Phase 1 (parallel — do first):

- **`PRD_ANALYTICAL_NULL_SEARCH.md`** (581 lines) — Quick win. Search 21 longest P2 stems (3+ signs) against 18 languages with analytical null + BH-FDR. Expected yield: 1-3 sign identifications. This is the minimum viable cognate search.

- **`PRD_KOBER_ALTERNATION_IDENTIFICATION.md`** (603 lines) — Use 610 alternation pairs + 53 known anchors to triangulate unknown sign readings via Kober's method. Expected yield: 5-10 new readings. BLOCKING validation: full leave-one-out on all 53 known signs, precision@3 >= 70%.

### Phase 2 (parallel — after Phase 1):

- **`PRD_JACCARD_SIGN_CLASSIFICATION.md`** (585 lines) — Extend the novel Jaccard paradigmatic substitutability method (F1=89% on LB vowels) to consonant series classification. LEFT-context Jaccard for consonants, RIGHT-context for vowels. Potentially publishable. BLOCKING: full LB corpus, ARI >= 0.30 for consonants.

- **`PRD_SUFFIX_CONSTRAINTS.md`** (472 lines) — Extract phonological constraints from P2's 29 inflectional suffixes. Kober's principle applied to morphological positions. Independent evidence source. BLOCKING: full LB suffix test, >= 80% accuracy.

### Phase 3:

- **`PRD_P1_CONSONANT_FIX.md`** (424 lines) — Fix the mega-class problem (91% of signs in one consonant class). 5 proposed approaches, all tested on LB, winner must achieve ARI >= 0.50.

### Phase 4 (orchestrator):

- **`PRD_ITERATIVE_DECIPHERMENT.md`** (850 lines) — The master feedback loop tying everything together. Constrain → match → accept → feed back → repeat.

## Critical Rules

1. **Every untested method has a BLOCKING full-corpus validation gate on Linear B.** No smoke tests. No 5-word samples. Full corpus, proper metrics, confidence intervals.
2. **Follow `STANDARDS_AND_PROCEDURES.md`** — 3-tier testing (formula correctness, known-answer, null/negative), data provenance tags, consensus dependency layer.
3. **Data extraction uses the `data-extraction` skill** — dual-agent adversarial pipeline, no hardcoded data, every byte traces to an external source.
4. **53 known sign readings are in `data/sign_to_ipa.json`** — these are the LB-transferred values. 19 were added this session (were missing despite being tier-1 consensus).
5. **The P1 V=5 grid is at `results/pillar1_v5_output.json`** — Kober-anchored vowels (95% accuracy), but consonant classes are still 1 mega-class (the fix is PRD_P1_CONSONANT_FIX).

## Key Data Locations

| What | Where |
|------|-------|
| LA corpus (879 inscriptions) | `data/sigla_full_corpus.json` |
| Sign-to-IPA (53 signs) | `data/sign_to_ipa.json` |
| P1 grid (V=5 Kober) | `results/pillar1_v5_output.json` |
| P2 lexicon (787 stems) | `results/pillar2_output.json` |
| P3 grammar | `results/pillar3_output.json` |
| P4 anchors (205) | `results/pillar4_output.json` |
| Candidate lexicons (18 langs) | `../ancient-scripts-datasets/data/training/lexicons/` |
| LB test corpus | `pillar1/tests/fixtures/linear_b_test_corpus.json` |
| LB HF data | `C:\Users\alvin\hf-ancient-scripts\data\linear_b\` |
| Extracted glosses | `pillar5/data/ediana_lydian_glosses.tsv` etc. |
| PP fleet results | `../ancient-scripts-datasets/data/linear_a_cognates_clean/` |
| All hypothesis test scripts | `pillar5/scripts/test_*.py` |
