# Overall Integrity Check — 2026-04-03

## 1. Test Suite Results

**461 passed, 0 failed, 0 errors** (8 warnings, ~7.5 min runtime)

Three independent runs confirmed identical results.

All warnings are sklearn ConvergenceWarning for k-means clustering with more
requested clusters than distinct points — benign and expected for grid eigengap
search.

### Test Counts by Pillar

| Pillar   | Tests | Status     |
|----------|------:|------------|
| Pillar 1 |   166 | ALL PASS   |
| Pillar 2 |    93 | ALL PASS   |
| Pillar 3 |    45 | ALL PASS   |
| Pillar 4 |    35 | ALL PASS   |
| Pillar 5 |   122 | ALL PASS   |
| **Total**| **461** | **ALL PASS** |

Baseline was 311 original tests. The increase to 461 reflects added adversarial
audit tests, regression tests, and new feature tests (Jaccard classification,
suffix constraints, ANS FDR fixes). No tests were removed.

## 2. Data File Integrity

| File | Check | Result |
|------|-------|--------|
| `data/sign_to_ipa.json` | 51 entries | PASS |
| `data/sign_to_ipa.json` | No *301 or *56 keys | PASS |
| `data/sigla_full_corpus.json` | 879 inscriptions | PASS |
| `data/sigla_full_corpus.json` | Loads without errors | PASS |
| `results/pillar1_v5_output.json` | 69 grid assignments | PASS |
| `results/pillar2_output.json` | 787 segmented lexicon entries | PASS |

## 3. Tier 0 Fix Persistence

### DOLGOPOLSKY dict in `constrained_sca_search.py`
- **PASS**: Contains U+0261 (ɡ), ʕ, ħ, χ in correct sound classes
- Line 105: `"g": "K", "ɡ": "K"` — both ASCII g and IPA ɡ mapped to K
- Line 106: `"χ": "K"` — mapped to K (velar class)
- Line 113: `"ʕ": "H", "ħ": "H"` — mapped to H (laryngeal class)

### AB08 reading resolution
- **PASS**: AB08 maps to "a" (tier1) throughout:
  - `kober_vowel_analysis.py` line 448: `"AB08": ("", "a")`
  - `kober_triangulation.py` line 97: `"AB08": ("", "a")`
  - `sign_to_ipa.json` keys are by syllabogram reading (e.g., "a", "da"), not AB-codes
  - No "AB08" key in `sign_to_ipa.json` (as expected — uses readings, not codes)

### AB-code fixes in `kober_vowel_analysis.py`
- **PASS**: Line 452: `"AB07": ("d", "i")` (was previously wrong)
- **PASS**: Line 463: `"AB06": ("n", "a")` (correct)
- **PASS**: Line 465: `"AB54": ("w", "a")` (correct)

### load_lexicon() seeded random sampling
- **PASS**: `constrained_sca_search.py` line 184: `rng = random.Random(42)` —
  uses seeded Random instance, not first-N truncation.

## 4. Alternation Detector Fix

### min_shared_prefix_length default
- **PASS**: Default is 2 (line 53: `min_shared_prefix_length: int = 2`)

### diff_len=2 final-position-only extraction
- **PASS**: Lines 158-161: `elif diff_len == 2:` followed by comment
  "only the FINAL position pair is a genuine suffix alternation"

### Production output
- **PASS**: `detect_alternations()` with defaults produces exactly **7 significant pairs**
  (65 candidate pairs, 65 prefix groups, 7 significant after Poisson filtering)

Pairs found:
1. AB57-AB69 (2 stems, p=0.001)
2. AB10-AB61 (2 stems, p=6.8e-7)
3. AB09-AB41 (3 stems, p=5.9e-6)
4. AB09-AB59 (2 stems, p=0.001)
5. R_e-R_ja (2 stems, p=1.7e-7) — Linear B validation
6. R_ma-R_me (2 stems, p=5.5e-7) — Linear B validation
7. R_si-R_ti (2 stems, p=7.5e-7) — Linear B validation

## 5. Git History and Conflict Check

### Branch status
- Current branch: `main` (up to date with `origin/main`)
- Working tree: **clean** (untracked files only — `.claude/`, scripts, data dirs)
- No merge conflicts detected

### Recent commit history (clean, linear)
```
d38ed78 Jaccard paradigmatic sign classification: 19 consonant clusters, all gates PASS
e667fe8 ANS production results: 243/378 FDR survivors, u-wi-ri->awari exact match
71917c2 Add Jaccard paradigmatic sign classification for consonant/vowel grid
5a7e3a6 Add Phase 2 adversarial audit reports (Jaccard + Suffix Constraints)
fd83975 Fix ANS FDR architecture: aggregate by (stem, language) before BH-FDR
bac5bc2 Fix null calibration: replace analytical formula with Monte Carlo null tables
dddf5cd Fix alternation detector: min_prefix=2, final-position-only diff_len=2
65bc291 Fix alternation detector: eliminate frequency artifacts, validate with permutation null
efc54f8 Tier 0 foundation fixes from adversarial audit
```

### Worktree branches
10 worktree branches exist (all prefixed `worktree-agent-*`). These are isolated
and do not affect `main`. No cross-contamination detected.

### File overwrite check
No evidence of different agents overwriting each other's files on `main`. The
commit history is linear with no merge commits, indicating clean sequential
integration.

## 6. Summary

| Category | Verdict |
|----------|---------|
| Test suite | **461/461 PASS** — 0 failures, 0 errors |
| Data files | **ALL INTACT** — correct counts, no corruption |
| Tier 0 fixes | **ALL PERSISTENT** — Dolgopolsky, AB08, AB-codes, seeded sampling |
| Alternation detector | **CORRECT** — 7 pairs (not ~610), min_prefix=2, final-only |
| Git history | **CLEAN** — linear, no conflicts, no overwrites |

**Overall verdict: PASS — no regressions detected.**

New test baseline: **461 tests** (up from 311 original).
