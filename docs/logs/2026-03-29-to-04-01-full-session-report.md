# Full Session Report — 2026-03-29 to 2026-04-01

## Session Overview

Multi-day session building Pillar 5 (Multi-Source Vocabulary Resolution), discovering fundamental limitations in phonetic matching approaches, and developing novel solutions for vowel identification. Started from a crashed previous session's partial Pillar 5 work.

---

## 1. Pillar 5 Implementation (from scratch)

**Prompt:** Resume Pillar 5 build from the PRD, which was complete but all implementation code was lost in a crash.

**What was built:**
- 10 Python modules: constraint_assembler, lexicon_loader, semantic_scorer, evidence_combiner, stratum_detector, pp_result_loader, cognate_list_assembler, output_formatter, pipeline, __main__
- 70 tests (3-tier: 46 formula, 12 known-answer, 12 null/negative)
- 311 total tests across all 5 pillars, all passing
- Config file (pillar5_default.yaml)

**Key technical challenge solved:** P2 uses AB codes (AB81, AB02) while P4 uses reading names (ku, ro). Built corpus-based AB-to-reading mapping to bridge the namespaces.

**Result:** STRUCTURAL SUCCESS. Pipeline infrastructure works end-to-end.

---

## 2. PP Fleet Data Integration

**Prompt:** Can we use the existing Phonetic Prior fleet results?

**Initial assessment (wrong):** PP fleet data is "not usable" because it's progressive scans.

**User correction:** Linear A is fundamentally unsegmented — progressive scans ARE the correct output. Each entry is a word-boundary hypothesis.

**What was done:** Rewrote pp_result_loader to load fleet clean cognate TSVs (21,555 entries, 18 languages). Integrated into pipeline.

**Initial result:** Lydian dominated at 40.4% of substrings. But all scores at phonology-only ceiling (0.500) because semantic scoring wasn't wired in.

**Result:** DATA INTEGRATION SUCCESS, but scoring methodology needed work.

---

## 3. Academic Data Extraction (Adversarial-Audited)

**Prompt:** Scrape the internet for Lydian glosses following data-extraction skill.

**Process:** Full dual-agent adversarial pipeline:
- 3 Team A source discovery agents (Lydian dictionaries, databases, other PP fleet languages)
- 1 Team B adversarial auditor (verified all URLs, entry counts, licenses)
- 1 Team A extraction agent (wrote and ran download scripts)
- 1 Team B extraction auditor (traced all entries from output → raw → source URL)

**Sources found and extracted:**
- eDiAna (Munich/DFG, CC BY-SA 4.0): 453 Lydian glossed entries via JSON API
- IDS (MPI, CC BY 4.0): 340 Elamite entries via TSV download
- eCUT/ORACC (UPenn, CC0): 600 Urartian entries via JSON zip

**Palaeolexicon VETOED** by auditor (data inaccessible, claims unverifiable, no license).

**Auditor finding:** Urartian glossary selection bug (147-entry subset instead of full 600). Fixed and re-extracted.

**Result:** 1,393 new glossed entries from 3 verified academic sources. COMPLETE SUCCESS.

---

## 4. Inventory-Size Confound Analysis

**Prompt:** Is the Lydian 40% dominance an artifact of lexicon size?

**Method:** Computed Spearman correlation between lexicon size and mean per-char PP score across all 18 languages.

**Result:** rho = +0.428 (below |rho| > 0.5 threshold). Correlation runs OPPOSITE to artifact hypothesis — larger lexicons score better. Lydian has 5th largest lexicon (693 words). CONFOUND CLEARED.

**But:** This was later invalidated by deeper analysis (see #5).

---

## 5. Hypothesis Testing Rounds 1-2 (Scoring Fix Attempts)

### Round 1

**H1 — Raw PP Score Thresholding: FALSIFIED.**
Raw PP per-char scores don't correlate with linguistic distance. Greek-Latin scores BETTER than Oscan-Umbrian (known closer cognates). PP scores measure IPA inventory compatibility, not cognacy.

**H3 — Cross-Extension Rank Stability: PARTIALLY FALSIFIED.**
Lydian has highest language stability (0.766) but LOWEST word stability (0.407). The specific Lydian word matched CHANGES every extension — signature of broad inventory compatibility, not real cognate signal. Messapic (0.743) and Eteocretan (0.720) showed higher word stability.

**Conclusion:** Lydian's 40% dominance is inventory bias, NOT real cognate signal.

### Round 2

**R2-H1 — Permutation Null Correction: FAILED.**
Cross-language z-score is a perfect linear transform of raw scores (r=0.9998) — adds nothing. Within-language z captures distribution skewness (r=0.944 with skewness), not cognacy. ACID test: 2/6 correct (worse than coin flip).

**R2-H2 — Word-Stability-Weighted Scoring: PARTIAL SUCCESS.**
Validated on known pairs (Oscan 44.9% vs Anglo-Saxon 23.2%). Eliminates Lydian false dominance (40% → 2.5%). But new bias: tiny lexicon words (2-3 chars) trivially match everything. After filtering: near-uniform distribution across 18 languages — no dominant signal.

**Overall conclusion:** PP fleet scores are exhausted. They don't contain usable cognate signal. The scoring function measures IPA representation compatibility, not linguistic relationships.

---

## 6. PP Production Re-Run Assessment

**Prompt:** Fix the PP production script bugs and test locally.

**Bugs fixed:**
1. `char_distr` parameter missing from `word_boundary_dp()` call
2. `edit_dist_dp` → `edit_distance_dp` method name mismatch (all quality scores were 0.0)
3. Memory fix: `--max-inscriptions` flag for CPU training (was OOMing at 9.3 GB)

**Smoke test:** Eteocretan, 200 steps, 30 inscriptions — completed in 16 hours. Quality scores now non-zero (range -4.81 to -188.52).

**But:** `spʰura` matches 17.5% of all inscriptions — the model defaults to a handful of phonologically convenient words. Same inventory bias in a different format.

**Adversarial critique (6 questions, all FAIL):** The DP uses the same confounded `char_distr` scoring function. Changing from "all substrings" to "DP-optimal segments" is changing the search strategy, not the objective. The character mapping has ~2,679 free parameters to explain ~50 short inscriptions — it can find some mapping for ANY language.

**Conclusion:** PP re-run won't fix the root problem.

---

## 7. PhaiPhon6: SCA-Based Cognate Search

**Prompt:** If PP scoring is confounded, use SCA (Sound Class Assignment) — zero learnable parameters, fixed phonetic distance.

**What was built:** `sca_cognate_search.py` — searches P2 stems against candidate lexicons using Dolgopolsky sound classes with permutation null.

**sign_to_ipa.json expansion:** Discovered 19 tier-1 LB signs were missing from the mapping file (ku, ro, pa, du, mi, etc.). Added them: 34 → 53 known signs. P2 full-IPA stems: 16 → 37 unique.

**Result:** 1/555 significant matches (p=0.04, Greek ἔπω vs LA pi). At or below false positive rate. Stems too short (1-2 syllables, 2-4 SCA chars) for SCA to discriminate between languages.

**Conclusion:** Method is sound (validated in literature) but data is insufficient. Need longer stems.

---

## 8. P2 Phonetic Tally Discovery

**Prompt:** How many P2 sign-groups have phonetic values at various levels?

**Key discovery:** 184 stems missing JUST ONE syllable. If we could constrain that one unknown sign to a few possible readings, we'd have 3+ syllable stems suitable for SCA matching.

**Full tally produced** and saved to Downloads: 426 fully phonetic (using corpus sign_inventory readings), 219 partially phonetic, 142 no phonetics.

---

## 9. P1 V=5 with Triple-Validated Vowel Identification

**Problem:** P1's V=1 (Bonferroni too conservative) collapses the grid into one mega-class. The V=4 override selects wrong signs (qa, sa, ku instead of real vowels).

**Solution D: Triple cross-reference of three independent methods.**

**Solution A — LB Transfer:** Use the 5 known LB vowels (a, e, i, o, u). Packard 1974 validated transfer at 2:1 to 5:1 odds. CONSENSUS_ASSUMED.

**Solution B — Kober Alternations:** Built `kober_vowel_analysis.py`. Used P1's 610 alternation pairs to identify initial-position vowel clique. AB08/a confirmed unambiguously (rank #1, 2.3x margin). AB28/i rank #9, AB10/u rank #11. AB38/e and AB61/o too rare to detect. Limitation: alternation graph too dense (mean degree 17.7) for clean consonant row separation.

**Solution C — Novel Entropy/Jaccard Method:** Built `entropy_vowel_analysis.py`. Original entropy hypothesis FAILED (F1=50%). But paradigmatic substitutability (Jaccard similarity of bigram context sets) WORKS: F1=89% on Linear B validation (4/5 vowels, zero false positives). Applied to Linear A: identifies a, u, i as vowel candidates. e and o too rare.

**Convergence:**
- AB08/a: all three methods agree → INDEPENDENT
- AB28/i, AB10/u: Solutions B+C weakly support, A confirms → INDEPENDENT_VALIDATED
- AB38/e, AB61/o: only Solution A (too rare for B/C) → CONSENSUS_ASSUMED

**Result:** V=5 vowel set established with documented provenance per sign. METHODOLOGICAL SUCCESS.

---

## 10. Kober-Style LB-Anchored Vowel Column Assignment

**Problem:** Grid constructor assigned vowel columns by frequency round-robin (meaningless). Vowel ARI = -0.364.

**Fix:** Implemented Kober's principle: signs in the same consonant row that DON'T alternate with LB anchor signs share that anchor's vowel. Signs that DO alternate have different vowels.

**Result:** Vowel ARI jumped from -0.364 to +0.242. 95% accuracy on 20 known signs (19/20 correct, only `di` wrong). Unknown signs now constrained to 2-5 possible readings per grid cell. SIGNIFICANT IMPROVEMENT.

---

## 11. Constrained SCA Search

**Prompt:** Use P1 grid constraints to narrow unknown signs to 2-5 readings, then SCA-match against lexicons.

**What was built:** `constrained_sca_search.py` — 99 partially-phonetic stems, each unknown constrained by grid cell, searched with permutation null.

**Adversarial critique (3 fatal flaws):**
1. SCA collision rate 84% at 4-char length — too short for discrimination
2. Permutation null minimum p=0.005, but Bonferroni threshold = 4.5×10⁻⁶ — incompatible
3. Consonant class still one mega-class (all 10+ consonants in C0)

**Empirical confirmation:** All p-values = 0.000. Every reading produces "significant" matches in every language. Critic was right.

**Conclusion:** Constrained search confirmed non-viable at 2-sign stem length. Restrict to 3+ sign stems (18 stems) with analytical null for any viable subset.

---

## Summary: What Was Accomplished

### Structural improvements (lasting value):
- Pillar 5 fully built (10 modules, 70 tests)
- 19 missing LB signs added to sign_to_ipa.json (34 → 53)
- 1,393 academic glosses extracted (eDiAna, IDS, eCUT)
- Kober-anchored vowel assignment (ARI -0.364 → +0.242, 95% accuracy)
- Novel Jaccard vowel identification method (F1=89% on Linear B)
- Triple-validated V=5 vowel set with provenance documentation
- PP production script bugs fixed (char_distr, method name, memory)
- All data pushed to Project-Phaistos shared repos

### Approaches attempted and their outcomes:
| Approach | Status | Why |
|----------|--------|-----|
| PP fleet raw scores | FAILED | Measures inventory compatibility, not cognacy |
| Min-max normalization | FAILED | Best language always scores 1.0 regardless of quality |
| Raw score thresholding | FAILED | Scores don't correlate with linguistic distance |
| Permutation null correction | FAILED | Perfect linear transform of raw scores (r=0.9998) |
| Word-stability scoring | PARTIAL | Discriminates known pairs but short-word bias |
| Rank stability | PARTIAL | Language stability ≠ word stability |
| PP re-run with DP | FAILED | Same confounded scoring function, different output format |
| SCA on fully-phonetic stems | FAILED | Stems too short (1-2 syllables) |
| Constrained SCA search | FAILED | Collision rate too high at 4 SCA chars |

### The fundamental bottleneck identified:
53 of 142 syllabograms have known phonetic values, producing mostly 1-2 syllable stems. This is insufficient for cross-linguistic comparison by ANY method. The bottleneck is data sparsity, not algorithm choice.

### Viable next steps:
1. Restrict constrained search to the 18 stems with 3+ signs (6+ SCA chars), use analytical null, apply BH-FDR
2. Improve P1 consonant discrimination (finer classes)
3. Use the Jaccard paradigmatic substitutability method to identify more unknown signs (it's novel and validated)
4. Any approach that increases the number of known sign readings will unlock exponentially more matchable stems (the 184 one-missing-syllable stems are the leverage point)
