# Pillar 5 Scoring Fix — Master Plan

**Date:** 2026-03-27
**Status:** In progress — building test datasets before implementing fixes

## The Problem

Min-max normalization in Pillar 5 destroys absolute quality signal. The "best" language always scores 1.0 even if all matches are garbage. This produces 0% substrate (artifact) and false positives like Proto-Dravidian at 11%.

## What We Need to Build

A scoring system that:
1. Has an absolute quality threshold (not just relative ranking)
2. Produces a null baseline from known non-cognate languages
3. Handles small-corpus bias (small lexicons shouldn't get inflated scores)
4. Can detect chimaera languages (multiple cognate sources at different proportions)
5. Correctly identifies substrate (vocabulary with no external cognate)

## Test Strategy (Two-Track)

### Track 1: Natural chimaera — Hittite or Akkadian
Use a real ancient language with known multiple cognate layers. Test whether the scoring method recovers the known strata in correct proportions (or at least correct rank order).

Research needed: scholarly consensus on proportion of loanwords by source language.

### Track 2: Synthetic chimaera — constructed from known languages
Mix vocabulary from 3+ languages at known proportions (e.g., 57% Oscan, 29% Greek, 14% Basque). Ground truth is exact. Test:
- Does the system recover the proportions?
- Does shrinking one layer (e.g., Greek to 50 words) still detect it?
- Does it correctly identify non-cognate noise?

Adversarial critique needed: what makes a synthetic chimaera imperfect compared to a real one? IPA representation issues, phonological drift, morphological integration of loanwords, etc.

## Hypothesis Teams for Scoring Fixes

Each team proposes and tests ONE alternative to min-max normalization:

### H1: Z-score against null distribution
For each substring, compute its PP score's z-score against a null distribution (from synthetic random language or known isolate). Only matches with z > 2.0 count as significant.

### H2: Percentile rank against shuffled baseline
Permute the lost-language IPA and re-score. The percentile of the real score against shuffled scores gives an absolute quality measure.

### H3: Cross-language rank stability
A real cognate should rank high consistently across progressive scan extensions. If "a-sa-sa" matches Lydian well but "a-sa-sa-ra" doesn't, the match is fragile (noise). Require rank stability across 3+ extensions.

### H4: Bayesian model comparison with proper null
Instead of normalizing scores, compute P(cognate | score) using a prior calibrated from the validation dataset (Ugaritic-Hebrew known P@1=0.557).

### H5: Raw score thresholding with per-character correction
Skip normalization entirely. Use raw PP per-character scores with an empirically determined threshold from the validation pairs. The threshold is: "what per-char score does a known cognate pair achieve?"

## Adversarial Requirements

Each hypothesis team gets a paired adversarial agent that:
1. Critiques the theoretical basis (is this approach validated in published work?)
2. Checks for small-corpus bias (does it produce false positives for small lexicons?)
3. Verifies on known-answer test (does it correctly identify cognates AND reject non-cognates?)
4. Checks for the Proto-Dravidian problem (does it still produce implausible results?)

## User Instructions (preserved)

- Spin up parallel subagent teams for each hypothesis
- Each team MUST have adversarial agent critique
- Test against known language pairs from validation pipeline
- Use ancient languages when possible (closer to Linear A situation)
- Test small-corpus bias explicitly (shrink one language to ~300 entries)
- Establish null baseline for real vs fake positives
- Test chimaera detection capability (multiple cognate sources at different proportions)
