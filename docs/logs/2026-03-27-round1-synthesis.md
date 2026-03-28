# Round 1 Synthesis: All Hypotheses Converge on Inventory Bias

**Date:** 2026-03-27
**Status:** Round 1 complete. Designing Round 2.

## What Round 1 Established

Four parallel teams (H1 raw thresholding, H3 rank stability, adversarial synthetic chimaera critique, Akkadian/Hittite research) all converge on the same root cause:

**PP fleet scores are dominated by phoneme inventory compatibility, not genuine cognate signal.**

### Evidence

| Finding | Source | Implication |
|---------|--------|-------------|
| Greek-Latin scores BETTER than Oscan-Umbrian (known closer cognates) | H1 | Raw scores measure IPA representation, not linguistic distance |
| Lydian has highest language stability but LOWEST word stability (0.407) | H3 | Lydian "wins" via broad inventory compatibility, not specific word matches |
| Simply mixing IPA from different languages is trivially separable by inventory | Adversarial | The same artifact corrupting LA results would corrupt naive tests |
| Messapic (0.743) and Eteocretan (0.720) show high word stability | H3 | Word-level consistency IS a differentiating signal |

### What Does NOT Work

1. Raw PP per-char score thresholding (H1 — FALSIFIED)
2. Min-max normalization across languages (original P5 — already known broken)
3. Language-level rank stability (H3 — cannot discriminate signal from noise)
4. Naive synthetic chimaera mixing (Adversarial — trivially solvable by inventory matching)

### What MIGHT Work (Round 2 Hypotheses)

1. **Word-level match stability** — the one metric that showed differentiation
2. **Permutation null correction** — shuffle lost text, re-score, subtract inventory component
3. **Inventory-regressed scores** — regress out inventory-size correlation before comparing
4. **Nativized synthetic chimaera** — apply phonological adaptation rules before mixing

### Natural Chimaera Test Language

**Hittite is the best candidate** (5 source families: IE core, Hattic substrate, Hurrian, Akkadian, Luwian). But only 281 lexicon entries — needs supplementation.

**Akkadian has the quantified benchmark** (Sumerian at ~7%, Lieberman 1977) but is less multi-sourced.

Neither has pre-computed PP fleet results — would need new PP runs.

## Round 2 Design Priorities

1. **Permutation null for existing fleet data** — can test immediately, no new PP runs needed. For each LA-vs-language pair, shuffle the LA IPA and check if scores change. If they don't, the score is pure inventory artifact.

2. **Word-stability-weighted scoring** — re-rank languages by word stability instead of raw score. Does Messapic/Eteocretan dominance hold up?

3. **Inventory regression** — compute phoneme inventory overlap for each LA-vs-language pair, regress it out of the PP scores, check residuals.

4. **Nativized synthetic chimaera** — Latin core (60%) + Greek contact (25%, with Latin-phonotactic adaptation) + Finnish substrate (15%, adapted). Per adversarial critique: replace Oscan with Latin (data quality), add nativization layer, include controls.
