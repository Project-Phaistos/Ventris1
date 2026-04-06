# Independent CV Syllabary Corpus Search for Jaccard Validation

**Date:** 2026-04-06
**Purpose:** Find an independent CV syllabary with restrictive phonotactics to validate the Jaccard sign classification method (Gate 1b of PRD_JACCARD_SIGN_CLASSIFICATION.md)
**Status:** CYPRIOT CORPUS EXTRACTED AND VALIDATED

---

## Background

The Jaccard paradigmatic substitutability method classifies CV syllabary signs into consonant series and vowel classes using distributional context similarity. Results so far:

| Script | Consonant ARI | Vowel ARI | Phonotactics | Notes |
|--------|:---:|:---:|:---:|---|
| Linear B | 0.342 | 0.422 | Restrictive (Greek) | Primary validation |
| Japanese | 0.047 | -0.013 | Permissive | Negative control |

The method works on restrictive phonotactics (where consonant identity constrains followers) but fails on permissive phonotactics. An independent CV syllabary with restrictive phonotactics is needed to confirm this is a general property, not an artifact of Linear B specifically.

---

## Candidate Scripts Evaluated

### 1. Cypriot Greek Syllabary -- SELECTED

**What it is:** A CV syllabary used to write Arcadocypriot Greek on Cyprus (~800-200 BCE). 55 signs in the Unicode standard, each representing one CV pair. Independently deciphered.

**Phonotactic assessment:** RESTRICTIVE. Same Greek phonotactic constraints as Linear B. Consonant clusters must be spelled out with silent vowels (e.g., "stasis" = sa-ta-si-se), creating strong distributional signatures. Consonant identity constrains following syllables.

**Corpus found:** The Idalion Tablet (ICS 217), the longest surviving Cypriot inscription (~1000 signs, 31 lines), plus 3 shorter inscriptions from Palaeolexicon.

**Sources searched:**
- [Kyprios Character Project](https://kyprioscharacter.eie.gr/) -- 1,397 inscriptions cataloged but not digitally available as syllabic text
- [PASP Database](https://dataverse.tdl.org/dataset.xhtml?persistentId=doi:10.18738/T8/GDUFXG) -- Downloaded (CC0). Contains 981 CS entries but only metadata (ICS numbers, locations, dates), not actual syllabic text.
- [PHI Greek Inscriptions](https://inscriptions.packhum.org/) -- Cyprus region exists but primarily alphabetic Greek; syllabic texts not easily accessible.
- [LinA/ancientscriptsstudy](https://ancientscriptsstudy.wordpress.com/home/syllabic-cypriot-idalion-tablet-ics-217/) -- Complete syllable-by-syllable transliteration of ICS 217 (Idalion Tablet). SOURCE USED.
- [Palaeolexicon](http://www.palaeolexicon.com/Cypriot) -- 3 Cypriot syllabary inscriptions with transliterations. SOURCE USED.
- [Mnamon](https://mnamon.sns.it/index.php?page=Scrittura&id=4&lang=en) -- Scholarly description but no downloadable corpus.
- [Unicode Cypriot Syllabary](https://en.wiktionary.org/wiki/Appendix:Unicode/Cypriot_Syllabary) -- Complete sign inventory (55 signs with CV values). SOURCE USED for sign-to-CV mapping.

**Independence from Linear B:**
- Different script (no shared sign forms)
- Different historical period (Iron Age vs Bronze Age)
- Same language family (both Greek dialects)
- Same phonotactics (both encode Greek with CV constraints)
- Weakness: NOT fully independent, because both encode Greek. A high Cypriot ARI confirms the method works on Greek phonotactics via a different script, but does not prove it generalizes to non-Greek restrictive phonotactics.

**Corpus statistics:**
- 269 sign-groups (words)
- 1,072 sign tokens
- 51 unique signs (out of 55 in the inventory)
- 43 signs with count >= 3 (analyzable)
- 13 consonant series, 5 vowel classes
- Mean word length: 3.99 signs

**Limitation:** The corpus is dominated by one inscription (Idalion Tablet = ~95% of data). This is a single legal/administrative text with formulaic language, so distributional patterns are narrower than a multi-genre corpus.

### 2. Cherokee Syllabary -- NOT PURSUED (phonotactic mismatch)

**What it is:** 85-character syllabary invented by Sequoyah (1820s) for Cherokee (Iroquoian). 6 vowels x 14 consonant series.

**Phonotactic assessment:** PROBLEMATIC. While the syllabary has a clean CV grid, Cherokee spoken language has complex consonant clusters (up to 4 consonants in a cluster) that the orthography obscures. The syllabary inserts epenthetic vowels to spell clusters, which means the distributional patterns in text reflect the orthographic conventions more than phonotactic constraints. This makes it a poor test case for the Jaccard method's phonotactic sensitivity.

**Corpus availability:** Cherokee Wikipedia (chr.wikipedia.org) has moderate content. No large downloadable corpus found.

### 3. Vai Syllabary (Liberia) -- NOT FOUND

**What it is:** ~300 signs, CV structure. Invented 1833 for Vai language (Mande family).

**Corpus availability:** No digital corpus found. The script is in Unicode (U+A500-U+A63F) but no searchable text datasets were located on HuggingFace, GitHub, or academic databases.

### 4. Ethiopic/Ge'ez Fidel -- NOT SUITABLE

**What it is:** An abugida (not a true syllabary). Each base character represents a consonant; vowel modification is systematic (diacritical variations of the base form). 33 consonants x 7 vowel orders = 231 characters.

**Why unsuitable:** The Jaccard method relies on distributional similarity between independent signs. In an abugida, vowel variants of the same consonant have visually related forms, meaning sign identity already encodes consonant information. This is structurally different from a true CV syllabary where each sign is an independent symbol.

**Local data:** Amharic lexicon (379 entries) exists at `ancient-scripts-datasets/data/training/lexicons/amh.tsv` but is IPA-based, not Ge'ez character-based.

### 5. Yi Syllabary (China) -- NOT PURSUED

**What it is:** ~1,164 signs for Nuosu Yi language. CV structure.

**Why not pursued:** Very large sign inventory (1,164 signs vs 55-85 for target scripts) would require fundamentally different hyperparameters. Not directly comparable. No corpus was searched.

---

## Cypriot Validation Results

### Method
Ran the same Jaccard pipeline (TF-IDF left-context for consonants, PPMI right-context + anti-correlation for vowels) on the Cypriot corpus. Adjusted hyperparameters for smaller corpus: min_count=3 (vs 5), consonant_knn=6 (vs 8).

### Results

| Metric | Cypriot | Linear B | Japanese |
|--------|:---:|:---:|:---:|
| **Consonant ARI** | **0.107** | 0.342 | 0.047 |
| **Vowel ARI** | **0.155** | 0.422 | -0.013 |
| **Combined ARI** | **0.131** | 0.382 | 0.017 |
| Null test (shuffled) | 0.011 / 0.075 | -- | -- |
| Recovered series | 6/13 | -- | -- |

### K-sweep (consonant k)

| k | Cons ARI | Recovered |
|---|:---:|:---:|
| 5 | 0.013 | 1 |
| 9 | 0.046 | 5 |
| 13 | 0.107 | 6 |
| **14** | **0.111** | **6** |
| 17 | 0.090 | 3 |

Best k=14, cons_ARI=0.111.

### Interpretation

1. **Signal is real.** The null test confirms ARI drops to ~0 on shuffled data (cons_ARI: 0.107 -> 0.011). The method detects genuine distributional structure.

2. **Cypriot > Japanese.** Consonant ARI 0.107 vs 0.047 and vowel ARI 0.155 vs -0.013. The method performs better on Cypriot's restrictive Greek phonotactics than on Japanese's permissive phonotactics. This supports the phonotactic sensitivity hypothesis.

3. **Cypriot < Linear B.** The gap (0.107 vs 0.342) is likely explained by corpus size:
   - Cypriot: 1,072 tokens from 1 inscription (formulaic text)
   - Linear B: ~8,000+ tokens from 142+ inscriptions (diverse administrative texts)
   - Fewer tokens = sparser context vectors = weaker signal

4. **6 consonant series recovered.** The method correctly clustered signs from the V, l, m, n, r, and s series -- the most frequent consonant groups. Less frequent series (j, x, z with 1-2 members each) cannot be recovered due to data sparsity.

5. **Ordering:** Restrictive > Permissive, as predicted. But the effect is confounded by corpus size.

---

## Files Produced

| File | Description |
|------|-------------|
| `pillar1/tests/fixtures/cypriot_cv_corpus.json` | Cypriot corpus (269 words, 1072 tokens) |
| `pillar1/tests/fixtures/cypriot_sign_to_cv.json` | Sign-to-CV mapping (55 signs) |
| `pillar1/scripts/extract_cypriot_corpus.py` | Extraction script |
| `pillar1/scripts/jaccard_cypriot_validation.py` | Validation script |
| `pillar1/scripts/data_extraction/cyprus-inscriptions.tab` | PASP database (CC0, metadata only) |
| `results/cypriot_jaccard_validation.json` | Full results |

---

## Recommendation

**The Cypriot corpus provides a useful but limited second validation point.** It confirms that the Jaccard method detects real distributional structure in a CV syllabary with restrictive phonotactics, and that it outperforms the Japanese (permissive) baseline. However:

1. The corpus is too small (1,072 tokens from 1 primary inscription) for high-confidence ARI measurement. Bootstrap CIs would be wide.

2. The independence from Linear B is partial -- both encode Greek. A truly independent test would use a non-Greek language with restrictive phonotactics.

3. For a stronger Gate 1b, consider supplementing with Cherokee data from chr.wikipedia.org (despite the phonotactic caveats) or finding more Cypriot inscriptions from the forthcoming IG XV digital edition.

**Bottom line:** Gate 1b is now partially satisfied. The method shows phonotactic-dependent performance across 3 scripts (LB > Cypriot > Japanese), with the null test confirming real signal. The small Cypriot corpus prevents a definitive quantitative benchmark, but the qualitative pattern is clear.

---

## Sources

- [LinA: Idalion Tablet ICS 217](https://ancientscriptsstudy.wordpress.com/home/syllabic-cypriot-idalion-tablet-ics-217/)
- [Palaeolexicon: Cypriot](http://www.palaeolexicon.com/Cypriot)
- [Unicode Cypriot Syllabary](https://en.wiktionary.org/wiki/Appendix:Unicode/Cypriot_Syllabary)
- [PASP Database (CC0)](https://dataverse.tdl.org/dataset.xhtml?persistentId=doi:10.18738/T8/GDUFXG)
- [Kyprios Character Project](https://kyprioscharacter.eie.gr/)
- [PHI Greek Inscriptions](https://inscriptions.packhum.org/)
- [Mnamon: Cypro-Syllabic](https://mnamon.sns.it/index.php?page=Scrittura&id=4&lang=en)
- Masson, O. (1983) *Les inscriptions chypriotes syllabiques* (ICS)
- Egetmeyer, M. (2010) *Le dialecte grec ancien de Chypre*
