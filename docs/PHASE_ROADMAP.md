# Ventris1 — Phase Roadmap & Quick Reference

**Last updated:** 2026-04-03

---

## High-Level Objective

Ventris1 deciphers Linear A through 5 structural pillars (phonology, morphology, grammar, semantics, vocabulary resolution). All 5 pillars are implemented (311+ tests). The fundamental bottleneck is that only 53/142 syllabograms have known phonetic values, producing stems too short for cross-linguistic matching. The 6 forward PRDs form an iterative loop to break this bottleneck: identify more signs, unlock longer stems, match cognates, confirm signs.

**Core axiom:** Linear A is a chimaera language (multiple linguistic influences). Cognates are tools for vocabulary, never the goal.

---

## The 6 PRDs — Execution Phases

### Phase 1 (parallel — execute first)

| PRD | File | Goal | BLOCKING Gate | Expected Yield |
|-----|------|------|---------------|----------------|
| Analytical Null Search | `docs/prd/PRD_ANALYTICAL_NULL_SEARCH.md` | Search 21 longest P2 stems (3+ signs) against 18 languages with Monte Carlo analytical null + BH-FDR | Gates 1-3: Ugaritic-Hebrew cognate recovery (5/10), Greek-Latin (3/10), English-Akkadian false positive (0/10) | 1-3 sign identifications |
| Kober Alternation ID | `docs/prd/PRD_KOBER_ALTERNATION_IDENTIFICATION.md` | Triangulate unknown sign readings via 610 alternation pairs + 53 known anchors | FULL leave-one-out ALL 53 signs (precision@3 >= 70%), FULL LB corpus validation (precision@3 >= 65%), null test on shuffled corpus (precision@3 < 10%) | 5-10 new readings |

### Phase 2 (parallel — after Phase 1)

| PRD | File | Goal | BLOCKING Gate | Expected Yield |
|-----|------|------|---------------|----------------|
| Jaccard Sign Classification | `docs/prd/PRD_JACCARD_SIGN_CLASSIFICATION.md` | Extend Jaccard paradigmatic substitutability to consonant series (LEFT-context) and vowel classes (RIGHT-context) | Full LB corpus: consonant ARI >= 0.50, vowel ARI >= 0.40 | Refined C-V grid with 6+ consonant series |
| Suffix Constraints | `docs/prd/PRD_SUFFIX_CONSTRAINTS.md` | Extract phonological constraints from P2's 29 inflectional suffixes using Kober's principle on morphological positions | Full LB suffix test: >= 80% accuracy | Constraints on unknown signs in suffix positions |

### Phase 3

| PRD | File | Goal | BLOCKING Gate | Expected Yield |
|-----|------|------|---------------|----------------|
| P1 Consonant Fix | `docs/prd/PRD_P1_CONSONANT_FIX.md` | Fix mega-class problem (91% of signs in C0). 5 proposed approaches, all tested on LB | Winner must achieve ARI >= 0.50 on LB | 6-8 meaningful consonant classes |

### Phase 4 (orchestrator)

| PRD | File | Goal | BLOCKING Gate | Expected Yield |
|-----|------|------|---------------|----------------|
| Iterative Decipherment | `docs/prd/PRD_ITERATIVE_DECIPHERMENT.md` | Master feedback loop: constrain -> match -> accept -> feed back -> repeat | Convergence criterion: iteration produces zero new STRONG identifications | Progressive sign identification until alternation graph is exhausted |

---

## Key Data Locations

| What | Where |
|------|-------|
| LA corpus (879 inscriptions) | `data/sigla_full_corpus.json` |
| Sign-to-IPA (53 signs) | `data/sign_to_ipa.json` |
| P1 grid (V=5 Kober) | `results/pillar1_v5_output.json` |
| P1 alternation stats (610 pairs) | `results/kober_vowel_analysis.json` |
| P1 alternation detector | `pillar1/alternation_detector.py` |
| P2 lexicon (787 stems) | `results/pillar2_output.json` |
| P3 grammar | `results/pillar3_output.json` |
| P4 anchors (205) | `results/pillar4_output.json` |
| P5 output | `results/pillar5_output.json` |
| Candidate lexicons (18 langs) | `../ancient-scripts-datasets/data/training/lexicons/` |
| LB test corpus | `pillar1/tests/fixtures/linear_b_test_corpus.json` |
| LB HF data | `C:\Users\alvin\hf-ancient-scripts\data\linear_b\` |
| HF SDK repo | `C:\Users\alvin\ancient-scripts-datasets-NEW\` |
| Existing SCA search | `pillar5/scripts/constrained_sca_search.py` |
| Kober vowel analysis | `pillar1/scripts/kober_vowel_analysis.py` |
| Entropy/Jaccard analysis | `pillar1/scripts/entropy_vowel_analysis.py` |

## Critical Rules

1. Every untested method has a BLOCKING full-corpus LB validation gate. No smoke tests.
2. Follow `STANDARDS_AND_PROCEDURES.md` — 3-tier testing, data provenance, consensus dependency.
3. Data extraction uses `data-extraction` skill — dual-agent adversarial pipeline.
4. Linear A sign-groups are NOT "words" — word boundaries are unknown. P2 segments are hypotheses.
5. 53 known sign readings in `data/sign_to_ipa.json` are LB-transferred values.
6. No single-cognate assumption. Architecture allows mixed provenance at every level.

## Current State

- 311+ tests passing, 7 errors in old hypothesis test scripts (not in core modules)
- Git branch: `master`, remote: `main`
- Python 3.13, Windows 11, no MSVC build tools (avoid C-extension deps)
