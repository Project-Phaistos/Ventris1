# Hypothesis Test Results — Pillar 5 Scoring Fixes

**Date:** 2026-03-27
**Status:** H1/H5 and H3 completed. Both FALSIFIED their hypotheses but revealed critical insights.

## H1/H5: Raw PP Score Thresholding — FALSIFIED

**Hypothesis:** Raw per-character PP scores with an empirically determined threshold from known cognate pairs can separate real cognates from noise.

**Result:** Raw PP scores do NOT correlate with linguistic distance.

| Category | Known Distance | Median Per-Char Score |
|----------|---------------|----------------------|
| CLOSEST (Oscan-Umbrian) | Same branch | -3.267 |
| CLOSE (Latin-Oscan) | Same family | -3.006 |
| MEDIUM (Greek-Latin) | Different branch | **-2.663 (BEST!)** |
| DISTANT (Latin-Sanskrit) | Very distant IE | -2.951 |
| UNRELATED (any-Anglo-Saxon) | Different branch | -3.031 |

**Root cause:** PP scores measure phoneme inventory overlap and IPA representational similarity, not cognate relationships. Greek-Latin scores best because Greek has a larger, richer IPA representation — not because it's more closely related than Oscan.

**Implication:** Any scoring method based on raw PP scores needs to CORRECT for source/target language properties before comparing across language pairs. The scores are confounded.

**Script:** `pillar5/scripts/test_h1_raw_threshold.py`

---

## H3: Cross-Extension Rank Stability — PARTIALLY FALSIFIED

**Hypothesis:** Real cognate matches should be stable across progressive scan extensions (if "a-sa-sa" matches Lydian, "a-sa-sa-ra" should too).

**Result:** Language-level stability cannot discriminate signal from noise (Cohen's d = -0.108, not significant). BUT word-level stability reveals a critical finding:

| Metric | Lydian | Messapic | Eteocretan |
|--------|--------|----------|------------|
| Language-level stability | **0.766 (HIGHEST)** | 0.61 | 0.65 |
| Word-level stability | **0.407 (LOWEST)** | 0.743 | 0.720 |

**Smoking gun:** Lydian always "wins" the language competition — but the specific Lydian word it matches CHANGES every extension. A real cognate would match the SAME word consistently. This is the signature of broad phonological inventory compatibility (systematic bias), not genuine word-level cognate relationships.

**Implication:** Lydian's 40% dominance in the Pillar 5 strata is very likely driven by phonological inventory bias, not real cognate signal. The scoring system's Lydian finding is UNRELIABLE.

**What DOES work:** Word-level stability might be a useful metric. Languages with HIGH word stability (Messapic 0.743, Eteocretan 0.720) are matching the SAME word consistently — which is more consistent with real cognate behavior.

**Script:** `pillar5/scripts/test_h3_rank_stability.py`

---

## Synthesis: What We Now Know

1. **Raw PP scores are confounded by inventory properties.** Cannot be used as absolute quality measures.
2. **Min-max normalization makes confound worse** by always giving the inventory-biased winner a score of 1.0.
3. **Language-level dominance (Lydian 40%) is unreliable** — driven by inventory compatibility, not cognates.
4. **Word-level match consistency IS a differentiating signal** — the one metric that separates potentially real matches from inventory noise.

## Next Steps

The fundamental approach needs to change. Instead of "which language wins most substrings?", we need:

1. **Permutation null correction:** For each language, shuffle the lost text IPA and re-score. The DIFFERENCE between real and shuffled scores isolates signal above inventory noise.
2. **Word-level stability as primary metric:** Only report matches where the SAME known word matches consistently across extensions.
3. **Inventory-size regression correction:** Regress out the correlation between inventory properties and PP scores before comparing languages.
4. **Synthetic chimaera validation:** Construct a test with known proportions and verify the corrected method recovers them.
