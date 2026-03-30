# Constrained Search Approach — PhaiPhon6 via P1 Grid + P2 Partial Phonetics

**Date:** 2026-03-29
**Status:** Blocked on P1 V=4 re-run. Approach stored for execution after fix.
**Depends on:** P1 re-run with V=4 (or BH-FDR relaxation)

## The Idea

Instead of giving up because only 53/142 syllabograms have known phonetic values, use the P1 phonological grid to CONSTRAIN the possible readings of unknown signs. Then enumerate the constrained possibilities for partially-phonetic P2 stems and search for cognate matches.

## Why This Could Work

184 P2 stems are missing JUST ONE syllable. If P1's grid can narrow each unknown sign from "any of 50+ possible readings" down to "one of 3-5 possible readings", then:
- For each partially-phonetic stem, we try 3-5 possible complete readings
- We SCA-match each reading against candidate lexicons
- If ONE reading produces a significantly better match than others, that simultaneously:
  1. Constrains the unknown sign's identity (decipherment!)
  2. Identifies a cognate relationship (vocabulary resolution!)

## Why P1 Must Be Fixed First

Current P1 grid (V=1, Bonferroni):
- 4 consonant classes, but class 0 has 91% of all signs
- Class 0 contains every consonant type (d,e,j,m,n,p,q,r,s,t,u,w) — no discrimination
- Classes 1-3 have 2 signs each, all unknown, zero known members
- USELESS for constraining unknowns

Required P1 grid (V=4, BH-FDR or override):
- ~4-5 consonant classes with actual phonetic coherence
- ~4 vowel classes discriminating a/e/i/o/u
- Each unknown sign constrained to "consonant class X, vowel class Y" = 2-5 possible readings
- This is the prerequisite

## The Algorithm (execute after P1 fix)

```
Step 1: Re-run P1 with V=4
  → Finer grid with C×V cells, each containing 3-8 signs
  → Each unknown sign constrained to possible readings from its cell

Step 2: For each partially-phonetic P2 stem (184 stems, 1 syllable missing):
  a. Identify the unknown sign and its P1 grid cell
  b. Enumerate all possible readings for that sign (constrained by grid)
  c. For each candidate reading, construct the complete IPA string
  d. SCA-encode and search against all candidate language lexicons

Step 3: Score with permutation null
  For each (stem, candidate_reading, language) triple:
  - Compute SCA distance to best lexicon match
  - Compare against shuffled lexicon (permutation null)
  - Record p-value

Step 4: Identify significant matches
  If a specific reading of the unknown sign produces p < 0.01 against
  a specific language while other readings don't → convergent evidence:
  - The sign probably has that reading (decipherment hypothesis)
  - The stem probably matches that language word (cognate hypothesis)

Step 5: Cross-validate
  If the same sign appears in multiple stems, its constrained reading
  must be CONSISTENT across all stems. Inconsistency = false positive.
```

## What Makes This Different from Previous Approaches

1. **No learnable parameters** — SCA distance is fixed by phonetic theory
2. **Constrained search** — P1 grid limits combinatorial explosion
3. **Self-consistency check** — same sign must get same reading everywhere
4. **Dual output** — produces both decipherment hypotheses AND cognate hypotheses
5. **Permutation null** — controls for chance matches

## Data Requirements

- P1 output with V=4 grid (TO BE PRODUCED)
- P2 segmented lexicon (AVAILABLE: 787 entries, 184 with 1 missing syllable)
- Candidate language lexicons with SCA column (AVAILABLE: 15+ languages)
- Supplementary glosses (AVAILABLE: 1,393 entries from eDiAna/IDS/eCUT)

## Expected Yield

With V=4 grid constraining unknowns to ~4 readings each:
- 184 stems × 4 readings × 15 languages = ~11,000 comparisons
- At p=0.01, expect ~110 false positives
- Any sign with consistent reading across 3+ stems is a strong candidate
- Could potentially identify 5-20 new sign readings (conservative estimate)

## Risks

1. P1 V=4 grid may still be too coarse (CI was [1,4] — might get V=3 or V=2)
2. SCA distance may not discriminate at 3-syllable level (our earlier test showed stems need 4+ SCA chars for significance)
3. The self-consistency check may be too strict (signs might have context-dependent readings, though this is unlikely for a CV syllabary)
4. Combinatorial explosion if grid cells are too large (>8 possible readings per cell)

## Relationship to Previous PhaiPhon Work

This approach supersedes:
- PhaiPhon 3-5 (corpus-level language ranking — shown to be inventory-biased)
- PP fleet progressive scans (substring scores don't track linguistic distance)
- PhaiPhon6 prototype (SCA on fully-phonetic stems — too short for discrimination)

It builds on validated results:
- P1 consonant ARI = 0.615 vs LB (grid structure is real)
- P2 suffix patterns validated on Latin (segmentation is sound)
- SCA distance is validated in computational historical linguistics (List 2012, 2014)
- Permutation null controls for chance (validated in R2 hypothesis testing)
