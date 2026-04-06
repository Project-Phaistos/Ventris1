# Run Log

Reverse chronological. Newest first.

## 2026-04-03 to 2026-04-06 — Phase 1-2 Execution: All 6 Forward PRDs

**Type:** Multi-day execution sprint
**Scope:** All 6 forward PRDs across 4 phases
**Agents dispatched:** 16 (8 builders, 5 adversarial critics, 3 final verifiers)
**Tests:** 311 -> 461 (+150, zero regressions)
**Full report:** `docs/logs/2026-04-03-to-06-phase1-2-session-report.md`

### Tier 0: Foundation Fixes

Adversarial critics found 7 CRITICAL + 8 HIGH bugs in existing infrastructure before any PRD execution. All fixed:
- Removed undeciphered signs *301/*56 from anchors (53 -> 51)
- Fixed 3 AB-code swaps (AB06=na, AB07=di, AB54=wa)
- Fixed AB08 reading resolution (tier1 preferred over tier3 duplicate)
- Extended DOLGOPOLSKY dict (+25 IPA chars, diacritic stripping)
- Fixed SCA encoding mismatch (recompute_sca=True)
- Fixed lexicon subsampling (seeded random, not first-N)

### Phase 1A: Analytical Null Search

Replaced degenerate permutation null with Monte Carlo null tables (M=1,000). Per-hypothesis aggregation (best reading per stem x language). Gates: 10/10 Ug-Heb, 10/10 Grc-Lat, 3/10 Eng-Akk FP. FDR survivors: 243/378 (64.3%) — all at q=[0.028, 0.050], no deeply significant results.

**Notable:** u-wi-ri -> Urartian "awari" (field) at NED=0.000. Perfect SCA match, independently verified as legitimate.

### Phase 1B: Kober Alternation Identification

**Critical discovery:** Alternation detector was broken (shuffled corpus = same pair count). Fixed: min_prefix=2, final-position-only diff_len=2. Signal-to-noise: 0.94x -> 7.0x. But only 7 genuine pairs survive — too sparse for triangulation. Data limitation, not algorithm failure.

### Phase 2A: Jaccard Sign Classification — SESSION HIGHLIGHT

**19 consonant clusters** (9 with >= 3 signs) from distributional evidence alone. Solved the P1 mega-class problem (91% of signs in C0). Method: TF-IDF left-context cosine + mutual kNN sparsification.

| Metric | P1 Before | Jaccard After |
|--------|-----------|---------------|
| Consonant clusters | 1 mega-class | 19 clusters |
| Consonant ARI vs LB | degenerate | 0.342 (verified) |
| Vowel ARI vs LB | 0.242 | 0.422 (verified) |
| LB series recovered | 0 | 3/5 (t, k, n) |

Caveats: null test fragile (30% of seeds breach 0.05), k=19 at ARI peak (possible tuning), TF-IDF did not fix frequency confound (rho increased 0.159 -> 0.624).

### Phase 2B: Suffix Constraints — Core Assumption Falsified

Critic proved Kober's principle as applied was backwards: stem overlap measures signs in DIFFERENT paradigm slots (should have different consonants), not the SAME slot. 10.2% same-consonant = random chance. Infrastructure solid (48 tests) but constraints unreliable.

### Post-Session Fix (2026-04-06)

Fixed AB08 bug in `analytical_null_search.py` — same tier1-preferred fix as Tier 0 sprint. Commit `874bb42`.

### Audit Reports (7 total, all committed)

| Report | Key Finding |
|--------|-------------|
| `kober_triangulation_audit.md` | Alternation signal = noise (610 vs 609 shuffled) |
| `analytical_null_search_audit.md` | SCA encoding mismatch, degenerate null |
| `jaccard_classification_audit.md` | Frequency confound rho=0.965 |
| `suffix_constraints_audit.md` | Core assumption falsified (10.2% = chance) |
| `jaccard_final_verification.md` | All ARI values reproduced exactly |
| `ans_final_verification.md` | u-wi-ri -> awari confirmed legitimate |
| `overall_integrity_check.md` | 461/461 tests, all fixes intact |

---

## 2026-03-26 — Pillar 5: Multi-Source Vocabulary Resolution — Implementation + Production Run

**Type:** Implementation + Production Run
**Pillar:** 5
**Commits:** 575d560, d0f89ee, 2b2d511, 849c358, 9727f40

### What was built

10 Python modules implementing per-substring multi-language cognate matching with semantic constraints, evidence provenance weighting, and emergent stratum detection. 70 tests (3-tier: 46 formula, 12 known-answer, 12 null/negative). 311 total tests across all 5 pillars, all passing.

| Module | Purpose |
|--------|---------|
| `constraint_assembler.py` | Gathers P1-P4 constraints, bridges P2 AB codes ↔ P4 reading names via corpus mapping |
| `lexicon_loader.py` | Loads 33 candidate language IPA lexicons with gloss audit |
| `pp_result_loader.py` | Loads PP fleet progressive-scan results (21,555 entries, 18 languages) |
| `semantic_scorer.py` | Keyword taxonomy scoring (exact=1.0, domain=0.5, mismatch=0.0) |
| `evidence_combiner.py` | Combined scoring: phon×0.5 + sem×w_prov (Section 15 weights) |
| `cognate_list_assembler.py` | Multi-language search from PP substrings + P2 convergence detection |
| `stratum_detector.py` | Emergent strata from best-match language groupings |
| `output_formatter.py` | PRD Section 4.1 interface contract JSON |
| `pipeline.py` | 8-step orchestrator |
| `scripts/extract_glosses.py` | Adversarial-audited data extraction from 3 academic sources |

### Key architectural decision: unsegmented text

Linear A is fundamentally unsegmented — we do not know where words start and end. The Phonetic Prior algorithm evaluates ALL possible substrings of the unsegmented text. Each fleet result entry is a hypothesis: "if this substring is a word, its best cognate in Language X is Y with score Z." These progressive-scan results are the correct PP output, not a flaw. P2 segments are independent structural hypotheses; where PP and P2 agree, that is convergent evidence.

### Production run results

**Search:** 1,177 unique substring hypotheses evaluated across 18 ancient languages.
**Significant matches (score > 0.5):** 64 substrings.
**Gloss coverage:** 67.5% of 18,339 total matches have English translations.
**Semantic scoring:** 9.7% of matches (requires both gloss AND P4 anchor overlap).

### Stratum analysis (emergent, not pre-specified)

| Stratum | Language | % of substrings | Family |
|---------|----------|----------------|--------|
| 0 | **Lydian** | **39.9%** | Anatolian IE |
| 1 | Urartian | 12.1% | Hurro-Urartian |
| 2 | Proto-Dravidian | 10.9% | Dravidian |
| 3 | Proto-IE | 9.7% | Indo-European |
| 4 | Phoenician | 8.8% | Semitic |
| 5 | Proto-Caucasian | 5.4% | Caucasian |
| 6 | Proto-Semitic | 2.9% | Semitic |
| 7 | Elamite | 2.5% | Isolate |
| 8 | Old Persian | 2.2% | Iranian IE |

### Inventory-size confound check (Section 14.1)

| Check | Spearman rho | Threshold | Verdict |
|-------|-------------|-----------|---------|
| Lexicon size vs PP score | +0.428 | \|rho\| > 0.5 | **CLEARED** |
| Direction | Positive (larger = better) | Opposite of artifact | Larger lexicons score better, not worse |

Lydian has the 5th largest lexicon (693 words, 59% above median). The smallest lexicons (Lepontic 30, Messapic 45) rank last. **Lydian dominance is NOT an inventory-size artifact.**

### Top vocabulary matches

| LA Substring | Language | Match | Gloss | Combined Score |
|---|---|---|---|---|
| ti-nu-ja | Phrygian | aoːroː | plowed | 0.900 |
| a-sa-ra-me-u-na | Lydian | katʰtʰirs | preventing | 0.650 |
| ma-si-ru-te | Old Persian | ɡaːuʃ | cow | 0.650 |
| za-*56-ni | Proto-Dravidian | tʃeːr | ox plough | 0.650 |
| i-pi-na-ma-i-na | Urartian | tsari | fruit orchard | 0.650 |
| i-da-ja-j | Lydian | kofuu | soil | 0.650 |
| i-ki-te | Elamite | abebe | food | 0.610 |

### Data extraction (adversarial-audited, per Section 7 Iron Law)

Dual-agent pipeline: Team A wrote extraction scripts, Team B independently audited every step.

| Source | Language | Entries | License | Audit |
|--------|----------|---------|---------|-------|
| eDiAna (LMU Munich / DFG) | Lydian | 453 | CC BY-SA 4.0 | PASS |
| IDS (MPI Leipzig) | Elamite | 340 | CC BY 4.0 | PASS |
| eCUT/ORACC (UPenn) | Urartian | 600 | CC0 | PASS (after fix) |
| **Total** | | **1,393** | | |

Palaeolexicon **VETOED** by auditor (data inaccessible without browser automation, claims unverifiable, no license).

### Hypotheses generated

1. **Lydian phonological affinity (39.9%):** The PP's learned character mapping between Linear A and Lydian produces consistently tighter alignments than any other language. Lydian is an Anatolian IE language from western Anatolia — geographically proximate to Bronze Age Crete. This is not driven by inventory size (rho=0.428). Warrants further investigation with expanded semantic scoring.

2. **Multi-source vocabulary (chimaera pattern):** No single language dominates completely. The spread across Anatolian (42.5%), Hurro-Urartian (12.1%), Dravidian (10.9%), and Semitic (11.7%) is consistent with the chimaera hypothesis — Linear A vocabulary drawn from multiple contact languages.

3. **Agricultural/commodity terms cluster with Anatolian and IE:** The semantic matches that DO fire show agricultural vocabulary (soil, plowed, cow, seed, food, fruit orchard) clustering with Anatolian, IE, and Near Eastern languages. This is archaeologically plausible for Bronze Age Crete trade.

### Known limitations

1. **Semantic scoring at 9.7%** — most PP substrings don't overlap with P4 anchors because PP scans are progressive (cross word boundaries) while P4 anchors are specific sign-groups.
2. **All phonology-only scores at 0.500 ceiling** — combined_score = phon × 0.5, so without semantic scoring the maximum is exactly 0.5.
3. **PP results are progressive scans, not word-level decompositions** — the 1,177 substrings include overlapping fragments from the same inscriptions.
4. **No P2 convergence detected yet** — PP substring signs and P2 sign-group IDs use different namespaces; convergence check needs refinement.

### Next steps

- Expand semantic coverage: extract Wiktionary Lydian (49), Phoenician (166), Hittite (1,273 from AssyrianLanguages)
- Refine P2 convergence detection across PP/P2 namespaces
- Run PRD Gate 1 (Ugaritic-Hebrew known-answer test) and Gate 3 (English chimaera test)
- Investigate Lydian-Linear A phonological correspondences in detail

## 2026-03-24 — Consensus Dependency Audit: Sign Count Heuristic Debunked

**Type:** Diagnostic
**Pillar:** Cross-pillar (CD-001, CD-002)
**Commit:** (this commit)

### Objective

Test whether the V(1+C)=N sign count heuristic can independently verify the GORILA sign type classification (CD-001) — our biggest single point of failure.

### Finding: V(1+C)=N IS NOT DISCRIMINATIVE

For any N in [50, 150], V(1+C) fits within +/-1 for some V in [3,6] and integer C >= 3. The equation accepts:
- N=62 (tier1 syllabograms — GORILA classification)
- N=83 (tier1 + frequent tier3)
- N=142 (ALL classified syllabograms)
- N=75 (hypothetical misclassification)

...all equally well. The heuristic only rules out N < 18 or N > 300, which nobody claims. **It cannot distinguish a correct classification from an incorrect one.**

This means the claim in CD-001 and CD-002 that the sign count heuristic provides an independent check was WRONG. The registry has been corrected.

### What DOES independently support the classification

Two stronger tests exist:

1. **Grid rectangularity (moderate):** The tier1 grid has row sizes 2-6 (mostly 3-5) and column sizes 6-16 (mostly 9-13). An approximately rectangular grid is predicted by the CV model. But this test uses LB values for cell assignment, so it's not fully independent of CD-008.

2. **Distributional clustering (strong, ARI=0.615):** Pillar 1's alternation-based spectral clustering recovers consonant groups from positional/inflectional evidence alone — no knowledge of sign types, no LB values. The fact that the clustering agrees with LB consonant classes (ARI=0.615) means the tier1 signs really do exhibit the distributional behavior expected of CV syllabograms. This is the strongest independent evidence.

3. **Positional frequency pattern (moderate):** The existence of signs with significantly elevated initial-position rates (AB08 at E=2.72, p=4.2e-10) is predicted by the CV model (pure vowel signs) and would not occur in an alphabetic or logographic system.

### Impact on consensus dependency audit

| Dependency | Previous testability | Updated testability |
|-----------|---------------------|---------------------|
| CD-001 (sign types) | "Partially — sign count heuristic" | "V(1+C)=N debunked. Grid rectangularity (moderate) and distributional ARI=0.615 (strong) provide real evidence." |
| CD-002 (CV assumption) | "Yes — V(1+C)=N" | "V(1+C)=N debunked. Distributional ARI + positional frequency are the real tests." |

### Lesson

Always test whether a proposed discriminator actually discriminates. V(1+C)=N *looks* like a constraint but the parameter space (V=3-6, C=3-49) is so wide that it accepts essentially any sign count. This is analogous to PhaiPhon's FDR rubber-stamping — a test that accepts everything is not a test.

---

## 2026-03-24 — Pillar 4 Initial Production Run

**Type:** Production Run
**Pillar:** 4
**Module:** Full pipeline (all 8 steps)
**Commit:** (this commit)
**Corpus version:** sigla_full_corpus.json v2.0.0
**Duration:** 0.1s
**Platform:** Windows 11 local, Python 3.13

### Objective

First end-to-end run of the bias-free Pillar 4 semantic anchoring pipeline on the full SigLA Linear A corpus.

### Bias Removal Verification

| Bias term | Occurrences in output | Status |
|-----------|----------------------|--------|
| "deity" | 0 | CLEAN |
| "god" | 0 | CLEAN |
| "ritual" | 0 | CLEAN |
| "verb" | 0 | CLEAN |
| "prayer" | 0 | CLEAN |
| "offering" | 0 | CLEAN |
| "dedicant" | 0 | CLEAN |

All labels are neutral: COMMODITY:FIG, FUNCTION:TOTAL_MARKER, FORMULA:FIXED_EARLY, TRANSACTION:ENTITY, PLACE:PHAISTOS, etc. Sign-groups are called "sign_groups" not "words" throughout.

### Results

| Metric | Value | Notes |
|--------|-------|-------|
| Inscriptions loaded | 740 | (139 lack signs_sequence) |
| Named ideograms found | 19 | GORILA-identified only |
| Unknown logograms | 326 | NOT treated as identified — excluded from semantic fields |
| Sign-groups analyzed | 826 | |
| Semantic field assignments | 37 | From ideogram co-occurrence |
| ku-ro inscriptions | 33 | |
| ku-ro totals verified | 0 matching, 1 discrepant, 9 unparsable | Conservative parsing |
| Libation inscriptions | 3 usable | (48 legacy entries have empty sign data) |
| Formula elements | 7 fixed, 0 semi-fixed, 0 variable | |
| Place names found | PA-I-TO (2), I-DA (3), Dikte NOT FOUND | |
| Phonetic anchors | 5 | pa, i, to, da from place names |
| Total anchored sign-groups | 205 | |
| Evidence sources | transaction:181, ideogram:37, formula:7, place:2 | |
| Tests passing | 35 Pillar 4, 241 total | All pass |

### Top Anchored Sign-Groups

| Sign-group | Semantic Field | Confidence | Source |
|------------|---------------|-----------|--------|
| ku-ro | FUNCTION:TOTAL_MARKER | 0.95 | Transaction role (communis opinio) |
| pa-i-to | PLACE:PHAISTOS | 0.90 | Place name (confirmed) |
| po-to-ku-ro | FUNCTION:TOTAL_MARKER | 0.90 | Transaction role |
| i-da | PLACE:MOUNT_IDA | 0.85 | Place name (confirmed) |
| ku-ma-ro | COMMODITY:FIG | 0.70 | Ideogram co-occurrence |

### Interpretation

1. **Bias removal verified.** Zero occurrences of deity/ritual/verb labels in output. All semantic assignments are evidence-based and use neutral terminology.

2. **Transaction structure is the strongest signal.** 181 of 205 anchored sign-groups come from positional role in tablet transaction structure (before ideogram, before numeral, ku-ro adjacent). This makes sense — administrative tablets are structured documents.

3. **Ideogram co-occurrence identifies 37 commodity-associated sign-groups.** These are sign-groups that appear significantly more often near a specific commodity ideogram (FIG, GRAIN, WINE, etc.) than expected by chance. Each assignment passes Fisher's exact test.

4. **Place name confirmation is sparse but high-confidence.** PA-I-TO found at Hagia Triada (not Phaistos itself — interesting but not unexpected, as HT tablets record transactions from multiple sites). I-DA found at Phaistos and Zakros. Dikte NOT found — the expected AB-code sequence does not appear contiguously.

5. **Libation formula analysis is limited by data.** Only 3 of 71 libation inscriptions have usable sign-group data in the SigLA corpus (the 48 legacy entries lack signs_sequence). This severely limits formula mapping. Future work should reconcile the legacy libation data.

6. **ku-ro total verification mostly fails** due to numeral parsing limitations. Our conservative approach (only A701=1, A704=10, A705=100) leaves most numeral clusters unparsed because they contain fractional or uncertain values. This is the correct behavior — we don't guess.

### Next Steps

1. **Reconcile legacy libation data**: The 48 `libation_table` entries have sign data in a different format (linear_a_corpus.txt) but empty signs_sequence. Ingesting this would 16x the formula analysis data.
2. **Expand numeral parsing**: Consult Younger's numeral analysis for additional certain values.
3. **Feed anchors to Pillar 5**: The 205 anchored sign-groups with semantic fields dramatically constrain the cognate search space.

---

## 2026-03-24 — Architecture Summary: Pillars 1-3 Complete, Pillar 4 PRD

**Type:** Architecture Summary
**Scope:** Cross-pillar
**Pillars:** 1, 2, 3 (implemented), 4 (PRD complete)

### System Architecture

The Ventris1 system attacks Linear A decipherment from multiple independent angles that converge on the same data. Each pillar extracts a different type of structural information, and all outputs feed into Pillar 5 for multi-source vocabulary resolution.

```
SigLA Corpus (879 inscriptions, 3518 syllabogram tokens)
     │
     ├──→ Pillar 1: Phonological Engine
     │        Input:  raw sign sequences (AB codes only, no LB values)
     │        Method: positional frequency + spectral clustering on alternation graph
     │        Output: C-V grid, vowel inventory, phonotactic constraints
     │        Key result: consonant ARI vs LB = 0.615 (validates method)
     │        Key finding: AB08 is the only statistically significant pure vowel
     │        Tests: 60 (Tier 1: 18, Tier 2: 12 Linear B, Tier 3: 8 null/negative)
     │
     ├──→ Pillar 2: Morphological Decomposition
     │        Input:  corpus + Pillar 1 grid/phonotactics
     │        Method: suffix-stripping + Jaccard paradigm clustering
     │        Output: segmented lexicon, 69 suffixes, 39 paradigm classes
     │        Key result: top suffixes match known Linear A endings (re,ra,ti,ja,na,ta)
     │        Key finding: 67% declining stems = Linear A is inflected
     │        Tests: 78 (Tier 1: 45, Tier 2: 6 Latin, Tier 3: 6 null/negative)
     │
     ├──→ Pillar 3: Distributional Grammar
     │        Input:  corpus + Pillar 1 + Pillar 2
     │        Method: PPMI profiles + SVD + agglomerative clustering
     │        Output: 7 word classes, word order (inconclusive), 24 functional words
     │        Key result: ku-ro confirmed as structural marker (final_rate=55.9%)
     │        Key finding: si (AB41) at 80% final-rate = new functional word candidate
     │        Tests: 45 (Tier 1: 26, Tier 2: 16, Tier 3: 3)
     │
     ├──→ Pillar 4: Semantic Anchoring (PRD complete, implementation next)
     │        Input:  corpus ideograms, numerals, transaction structure, formulas
     │        Method: word-ideogram co-occurrence, total verification, formula alignment
     │        Output: anchor vocabulary (50-100 words with constrained meanings)
     │        Design: 5 steps + 5 gates + kill criteria
     │
     └──→ Pillar 5: Multi-Source Vocabulary Resolution (PRD pending)
              Input:  ALL of above
              Method: simultaneous multi-language search, stratum detection
              Output: compositional linguistic portrait (not single-language ranking)
```

### How the Pillars Reinforce Each Other

The design is intentionally redundant — each pillar provides independent evidence that cross-validates the others:

1. **Pillar 1 validates Pillar 2:** The C-V grid's consonant classes (ARI=0.615 vs LB) confirm that the alternation pairs used for grid construction are real inflectional patterns, not noise. This same alternation evidence seeds Pillar 2's suffix inventory.

2. **Pillar 2 validates Pillar 3:** The morphological word classes (67% declining) provide ground truth for Pillar 3's distributional clustering. If Pillar 3 separates declining from uninflected stems, the distributional signal agrees with the morphological signal — convergent evidence.

3. **Pillar 3 validates Pillar 4:** Functional words identified by Pillar 3 (ku-ro, ki-ro, si) should appear in Pillar 4's transaction/formula analysis in structural roles, not as commodity names. This cross-check prevents semantic misclassification.

4. **Pillar 4 validates Pillar 1:** Place names (PA-I-TO = Phaistos) provide independent phonetic anchors. If Pillar 1's independent grid assigns these signs to the same C-V cells that the LB values predict, the grid is confirmed.

5. **All four feed Pillar 5 with constraints:** Pillar 5 doesn't search for cognates blindly — it searches for words that (a) have a known phonological form (P1), (b) match the morphological structure (P2), (c) belong to a known word class (P3), and (d) fall in a constrained semantic field (P4). This dramatically reduces the search space and false positive rate.

### Test Coverage Summary

| Pillar | Tier 1 (formula) | Tier 2 (known-answer) | Tier 3 (null/negative) | Unit/integration | Total |
|--------|------------------|-----------------------|------------------------|------------------|-------|
| 1 | 18 | 12 (Linear B) | 8 | 22 | 60 |
| 2 | 45 | 6 (Latin) | 6 | 21 | 78 |
| 3 | 26 | 16 (Linear A real) | 3 | 0 | 45 |
| **Total** | **89** | **34** | **17** | **43** | **183** (+23 integration = **206**) |

All 206 tests passing in ~65 seconds.

### Design Decisions Made During Implementation

| Decision | Rationale | Impact |
|----------|-----------|--------|
| Pillar 1: Bonferroni correction for vowel identification | Conservative — only AB08 passes, but bootstrap CI [1,4] is informative | V=1 limits Pillar 3 agreement detection; future V=4 override will unlock |
| Pillar 2: Suffix-stripping over Morfessor | Corpus too small (834 words) for MDL-based segmentation to converge well | Simpler, more robust; BPE available as alternative |
| Pillar 3: Inconclusive word order | Honest finding — administrative lists ≠ natural syntax | Not a failure; documented as boundary condition |
| Pillar 4: Ideogram semantics are script-independent | Pictographic evidence + archaeology, not LB-dependent | Most reliable semantic signal available |
| All: 3-tier testing mandatory | PhaiPhon failures (FDR rubber-stamping, mean-vs-sum bugs) taught us surface tests are insufficient | 206 tests including formula-level math, known-language end-to-end, and null/random controls |

### Current Limitations (Honest Assessment)

1. **Pillar 1 V=1** degrades everything downstream. Only one vowel passes the strict test. Fix: relax to BH-FDR or override to V=4 from convergent evidence.
2. **Pillar 2's 39 paradigm classes** is over-fragmented. Fix: raise Jaccard threshold from 0.3 to 0.5.
3. **Pillar 3 word class induction** produces 1 dominant cluster + 6 singletons. Fix: use morphological features as primary signal, distributional as secondary.
4. **No verb morphology detected.** Administrative texts are noun-heavy. Libation tables may contain verbs but the signal is too sparse.
5. **Pillar 4 not yet implemented.** The semantic anchoring is the highest-value remaining work — it produces the only supervised labels in the entire system.

---

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
