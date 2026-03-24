# Run Log

Reverse chronological. Newest first.

## 2026-03-23 — Pillar 3 Initial Production Run

**Type:** Production Run
**Pillar:** 3
**Module:** Full pipeline (all 9 steps)
**Commit:** (this commit)
**Corpus version:** sigla_full_corpus.json v2.0.0
**Pillar 1 version:** results/pillar1_output.json (commit e7a9c02)
**Pillar 2 version:** results/pillar2_output.json (commit a195932)
**Duration:** 0.1s
**Platform:** Windows 11 local, Python 3.13

### Objective

First end-to-end run of the Pillar 3 distributional grammar pipeline on the full SigLA Linear A corpus.

### Results

| Metric | Value | Notes |
|--------|-------|-------|
| Stems profiled | 147 | With min_frequency ≥ 2 |
| Feature dimensions | 50 | PPMI context + positional + morphological + inscription-type |
| Word classes | 7 | 1 large (141 members) + 6 singletons — weak distributional signal |
| Silhouette score | 0.712 | High but misleading — dominated by one large cluster |
| Significant word orderings | 0 | Inconclusive — expected for list-structured tablets |
| Significant agreement patterns | 0 | Expected with V=1 from Pillar 1 |
| Functional words | 24 | 17 structural markers, 6 determiners, 1 particle |
| Top functional word | ku-ro (AB81-AB02) | final_rate=55.9%, freq=34, 31 inscriptions |
| Grammar sketch: inflected | Yes | 67.3% declining stems |
| Tests passing | 45 Pillar 3, 206 total | All pass |

### Top Functional Words

| Word | Classification | Freq | Inscriptions | Final Rate |
|------|---------------|------|-------------|------------|
| ku-ro | structural_marker | 34 | 31 | 55.9% |
| sa-ra2 | structural_marker | 17 | 17 | 41.2% |
| ki-ro | structural_marker | 16 | 12 | 37.5% |
| ku | determiner | 10 | 10 | 30.0% |
| si | structural_marker | 10 | 9 | 80.0% |

### Interpretation

1. **Functional word identification is the strongest result.** ku-ro (total), ki-ro (deficit/owed), and sa-ra2 are all independently identified as structural markers from positional statistics alone. si (80% final rate, high frequency) is a new finding worth investigating — it may be a sentence-final particle or a variant totaling marker.

2. **Word class induction is underperforming.** With 147 stems and 50 features, the distributional signal is too diffuse for fine-grained clustering. The SVD correctly captures the main variation but most stems land in one large undifferentiated class. This is a known risk from the PRD (Section 8, Risk 3: "distributional profiles are too sparse").

3. **Word order is genuinely inconclusive.** This is not a failure — it's an accurate finding. Administrative tablets have list structure (name-commodity-quantity), not natural sentence order. The 19 multi-word libation inscriptions alone are too few for statistical power. We cannot claim SOV, SVO, or VSO from this data.

4. **Agreement detection requires V>1 from Pillar 1.** With V=1, all endings are trivially in the same vowel class, so the suffix-match test has no resolving power for vowel-based agreement. This will improve if Pillar 1 is rerun with V=4.

### Next Steps

1. **Improve word class induction**: Try fewer SVD dimensions (5 instead of 15), or use paradigm class as the primary clustering feature rather than distributional context. The morphological signal from Pillar 2 (39 paradigm classes, 28 inflectional suffixes) is much stronger than the distributional signal.
2. **Separate tablet vs. libation analysis**: Word order analysis on libation tables only, where clause structure is more natural.
3. **Investigate si**: Is si (AB41) a sentence-final particle? Cross-reference with inscription types and co-occurring ideograms.
4. **Re-run after Pillar 1 V=4 override**: Agreement detection and word class induction will both benefit from richer phonological information.

---

## 2026-03-23 — Pillar 2 Initial Production Run

**Type:** Production Run
**Pillar:** 2
**Module:** Full pipeline (all 8 steps)
**Commit:** (this commit)
**Corpus version:** sigla_full_corpus.json v2.0.0
**Pillar 1 version:** results/pillar1_output.json (commit e7a9c02)
**Duration:** 0.6s
**Platform:** Windows 11 local, Python 3.13

### Objective

First end-to-end run of the Pillar 2 morphological decomposition pipeline on the full SigLA Linear A corpus.

### Configuration

```yaml
# configs/pillar2_default.yaml — all defaults
segmentation_method: suffix_strip
min_suffix_frequency: 3
min_suffix_stems: 2
max_suffix_length: 3
jaccard_threshold: 0.3
min_paradigm_members: 2
min_paradigm_slots: 2
```

### Results

| Metric | Value | Notes |
|--------|-------|-------|
| Words segmented | 787 unique | 717 with suffixes, 70 unsegmented |
| Unique suffixes | 69 | Filtered from raw candidates |
| Inflectional suffixes | 28 | Productivity > 0.3 + paradigm regular |
| Derivational suffixes | 18 | Productivity < 0.1 or not paradigm regular |
| Ambiguous suffixes | 23 | Between thresholds |
| Paradigm classes | 39 | Above Gate 3 target range (2-10) — needs tuning |
| Mean paradigm completeness | 0.49 | ~49% of stem×slot cells attested |
| Declining stems | 364 | 67% of all stems |
| Uninflected stems | 63 | 12% |
| Unknown stems | 114 | 21% |
| Tests passing | 78/78 Pillar 2, 138/138 total | All pass |

### Top 10 Suffixes (by frequency)

| Suffix (AB code) | LB reading | Frequency | Stems | Productivity | Classification |
|-------------------|-----------|-----------|-------|-------------|---------------|
| AB27 | re | 42 | 32 | 1.00 | inflectional |
| AB60 | ra | 38 | 30 | 0.94 | inflectional |
| AB37 | ti | 35 | 29 | 0.91 | inflectional |
| AB57 | ja | 34 | 31 | 0.97 | inflectional |
| AB06 | na | 33 | 29 | 0.91 | inflectional |
| AB59 | ta | 32 | 29 | 0.91 | inflectional |
| AB76 | ra2 | 32 | 8 | 0.25 | ambiguous |
| AB26 | ru | 30 | 18 | 0.56 | inflectional |
| AB04 | te | 27 | 24 | 0.75 | inflectional |
| AB09 | se | 27 | 20 | 0.62 | inflectional |

### Interpretation

1. **Top suffixes match expected Linear A case endings.** The identified suffixes (re, ra, ti, ja, na, ta, te, se, ru) correspond exactly to the signs that scholars have long suspected are grammatical endings in Linear A. This is strong independent confirmation.

2. **High productivity of top suffixes confirms inflectional morphology.** The top 6 suffixes each attach to 29-32 different stems (productivity > 0.9), which is characteristic of case endings in an inflected language. This is evidence that Linear A is inflected, not isolating.

3. **39 paradigm classes is too many.** The Jaccard threshold (0.3) is producing over-fragmentation — many small paradigm classes that should be merged. This is expected with a sparse corpus (most stems appear with only 1-2 of their possible endings). Raising the Jaccard threshold or lowering min_paradigm_slots would consolidate paradigms.

4. **The Latin known-answer test passes.** The pipeline recovers Latin case suffixes and 3 paradigm classes (within the 2-7 range), with 71% of stems classified as declining. This validates the core methodology.

5. **Null/negative tests all pass.** Random permutation, uniform random, and isolating language corpora produce significantly less morphological structure, confirming the pipeline is detecting real signal.

### Next Steps

1. **Tune paradigm count**: Raise Jaccard threshold from 0.3 to 0.5 to consolidate paradigms. Target: 5-15 paradigm classes.
2. **Grid-informed paradigm alignment**: Currently Pillar 1's V=1 limits this. Re-run with V=4 override to enable vowel-column alignment of endings.
3. **Investigate verb morphology**: Check if libation table stems show a different paradigm family than tablet stems (potential verb vs. noun distinction).
4. **Cross-reference with known Linear A morphological analyses**: Compare suffix inventory against Duhoux (1989) and Davis (2014) suffix lists.

---

## 2026-03-23 — Pillar 1 Initial Production Run

**Type:** Production Run
**Pillar:** 1
**Module:** Full pipeline (all 8 steps)
**Commit:** e7a9c02
**Corpus version:** sigla_full_corpus.json v2.0.0
**Duration:** 11.1s
**Platform:** Windows 11 local, Python 3.13

### Objective

First end-to-end run of the Pillar 1 phonological engine on the full SigLA Linear A corpus.

### Configuration

```yaml
alpha: 0.05
min_sign_frequency: 15
bootstrap_n: 1000
seed: 1234
min_independent_stems: 2
clustering_method: spectral
```

### Results

| Metric | Value | Notes |
|--------|-------|-------|
| Vowel count | 1 (CI: [1, 4]) | Only AB08 passes Bonferroni-corrected double test |
| Consonant count | 4 (CI: [3, 6]) | Eigengap heuristic |
| Grid assignments | 63 assigned, 85 unassigned | Many signs lack alternation evidence |
| Alternation pairs | 137 significant / 1,323 candidates | 10.4% acceptance rate |
| Consonant ARI vs LB | 0.615 | Strong agreement |
| Vowel ARI vs LB | 0.000 | Degenerate (V=1) |
| Favored bigrams | 6 | Top: AB81-AB02 (ku-ro) at 37 obs vs 4.6 exp |
| Tests passing | 60/60 | All pass |

### Interpretation

Consonant ARI = 0.615 validates the alternation-based grid construction method. AB08 ("a") is the only sign with enough power to survive Bonferroni correction. Bootstrap CI [1,4] suggests 3-4 vowels. Top favored bigram rediscovers ku-ro ("total").

### Next Steps

Relax vowel identification (BH-FDR or enrichment-only). Re-run grid with V=4 from convergent evidence.
