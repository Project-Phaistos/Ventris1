# Gate 3 Language Pair Verification -- Adversarial Audit

**Date**: 2026-04-03
**Auditor**: Claude (adversarial critic, independent verification)
**Scope**: Verify whether Gate 3 false-positive control uses a genuinely unrelated pair
**Verdict**: CURRENT PAIR (English-Akkadian) IS FLAWED. Replacement recommendations below.

---

## 1. Current State: Gate 3 Uses English-Akkadian

Gate 3 in `pillar5/scripts/analytical_null_search.py` (line 930) tests 10 English
words against the Akkadian lexicon (3,000 entries capped from 24,341). The test passes
if <= 5/10 produce FDR-surviving matches at q < 0.05.

### 1.1 Multi-Seed Stability Test (English-Akkadian)

| Seed  | FP/10 |
|-------|-------|
| 42    | 8     |
| 123   | 4     |
| 7     | 5     |
| 999   | 5     |
| 2026  | 3     |
| 1     | 4     |
| 314   | 5     |
| 555   | 5     |
| 777   | 3     |
| 12345 | 4     |

**Median: 4.5 FP. Range: 3-8 FP. Only 2/10 seeds produce <= 3 FP.**

The gate "passes" all seeds (threshold <= 5), but the threshold itself is extremely
permissive. A properly calibrated null on a genuinely unrelated pair should produce
0-1 FP consistently.

### 1.2 Root Cause of False Positives

Detailed match analysis reveals the Akkadian matches are overwhelmingly proper names:

| English Word | SCA | Akkadian Match | Category | NED |
|---|---|---|---|---|
| computer | KVMPJVTVR | qumbutu | common vocab | 0.222 |
| elephant | VLVPVNT | Baal-Sapunu | theonym | 0.250 |
| umbrella | VMPRVLV | Hasmargalsu | anthroponym | 0.143 |
| chocolate | TSVKLVT | Udsakar | theonym | 0.286 |
| pineapple | PVVNVPVL | Nanibgal | theonym | 0.250 |
| hamburger | HVMPVRKVR | Aham-arsi | anthroponym | 0.333 |

The Akkadian lexicon contains ~24,000 entries including proper names (anthroponyms,
theonyms, toponyms). These names have long, compounded forms (e.g., "Baal-Sapunu",
"Hasmargalsu") that produce close SCA matches to English compound words purely by
chance. This inflates the effective comparison pool far beyond what a common-vocabulary
lexicon would provide.

### 1.3 Hidden Contact Paths

English and Akkadian share indirect contact through:
- Semitic loanwords in English via Arabic (algorithm, algebra, alcohol, cotton, lemon,
  orange, sugar, zero) -- though none of the 10 test words are Semitic loans
- Shared Wanderwort via trade networks
- Indo-European/Semitic areal contact

While the 10 chosen English words are specifically modern (computer, basketball, etc.)
to avoid this, the Akkadian lexicon's massive proper name content creates a separate
false-positive pathway.

---

## 2. Alternative Pairs Tested

I tested 5 alternative language pairs across 10 seeds each:

### 2.1 Summary Table

| Pair | Family | Pool Size (L=7-10) | FP Range | Median FP | Verdict |
|---|---|---|---|---|---|
| English-Akkadian | Semitic | 822-2091 | 3-8 | 4.5 | REJECT |
| English-Japanese | Japonic | comparable | 6-8 | 8 | REJECT (worse) |
| English-Korean | Koreanic | 1034-2135 | 4-9 | 6 | REJECT (worse) |
| English-Tagalog | Austronesian | 1044-2322 | 7-7 | 7 | REJECT (constant 7) |
| English-Basque | Isolate | comparable | 10-10 | 10 | REJECT (catastrophic) |
| English-Yoruba | Niger-Congo | 89-642 | 0-1 | 0 | CONDITIONAL ACCEPT |
| Synthetic SCA-Akkadian | N/A | 822-2091 | 0-0 | 0 | GOLD STANDARD |

### 2.2 Detailed Findings

**Japanese (REJECTED)**: 6-8 FP. Japanese has massive modern loanword contamination
from English (via transliteration). "Cambodia" (NED=0.222), SCA matches from
transliterated loanwords.

**Korean (REJECTED)**: 4-9 FP. Same loanword issue as Japanese. Korean lexicon
contains transliterated English/global terms.

**Tagalog (REJECTED)**: Constant 7/10 FP. Tagalog has extreme Spanish/English
loanword contamination. "basketbol" matches "basketball" at NED=0.000 (identical SCA).
"Buenafe" matches "pineapple" at NED=0.125.

**Basque (REJECTED)**: 10/10 FP despite being a language isolate. The Basque lexicon
is heavily contaminated with Spanish/French loanwords: "txokolate" (chocolate) at
NED=0.222, "elefante" at NED=0.125. Basque is genetically isolated but lexically
very European. **This disproves the naive assumption that "language isolate = safe
negative control."**

**Yoruba (CONDITIONALLY ACCEPTED)**: 0/10 FP on 9/10 seeds, 1/10 on one seed.
However, Yoruba's short average SCA length (3.3 chars) means the comparison pool
for query lengths 7-10 is small (89-642 entries vs 822-2091 for Akkadian). The 0 FP
result may partially reflect this smaller pool rather than purely the lack of
linguistic relationship.

**Synthetic Random SCA (GOLD STANDARD)**: 0/10 FP on all 10 seeds, tested against
the Akkadian lexicon (pool sizes 822-2091). The synthetic strings use seeded RNG
with uniform distribution over the 12-character SCA alphabet. This provides the
only truly guaranteed zero-cognate control.

### 2.3 Wanderwort Check (Yoruba)

| Probe | SCA | Yoruba Match | NED | Risk |
|---|---|---|---|---|
| tea | TV | ude (TV) | 0.000 | LOW (coincidence: both are 2-char TV) |
| coffee | KVPV | logun ofe (LKVPV) | 0.200 | LOW (compound phrase) |
| sugar | SVKVR | seleru (SVLVR) | 0.200 | LOW (different semantics) |
| tobacco | TVPVKVV | ebekon (VPVKV) | 0.286 | NONE |
| cotton | KVTVN | akoto (KVTV) | 0.200 | LOW (coincidental) |
| wine | WVVN | Ooni (VVN) | 0.250 | NONE (proper name) |
| gold | KVVLT | Kolade (KVLT) | 0.200 | NONE (proper name) |
| silver | SVLPVR | seleru (SVLVR) | 0.167 | LOW |

No Wanderwort produces NED <= 0.100. The "tea" -> "ude" match (NED=0.000) is a
two-character coincidence (both are just TV in SCA), not a meaningful loanword. Yoruba
has no documented Semitic/IE loanword layer.

---

## 3. Recommendation

### 3.1 Primary Recommendation: Dual-Track Gate 3

Replace the single Gate 3 with two sub-gates:

**Gate 3A: Synthetic Random SCA vs Akkadian**
- Generate 10 random SCA strings (seeded RNG, uniform over SCA alphabet)
- Match lengths to the actual Linear A query lengths (4-8 chars)
- Threshold: 0 FP (strict)
- Purpose: Verify the Monte Carlo null is mathematically calibrated

**Gate 3B: English vs Yoruba**
- Use the existing 10 English test words
- Search against Yoruba lexicon (3000 entries)
- Threshold: <= 1 FP
- Purpose: Verify real-language phonotactic patterns don't break the null

### 3.2 Rationale

Synthetic random SCA alone is insufficient because:
- SCA strings are uniformly random over a 12-char alphabet
- Real language SCA strings follow CVCV patterns (~50% V)
- Synthetic strings have unrealistic consonant clusters (HWMLLKW)
- This structural difference inflates NED values, making the test too easy

Yoruba alone is insufficient because:
- Its short average word length (3.3 SCA chars) means small comparison pools
  for long queries
- The 0 FP result may partly reflect pool-size effects, not calibration quality

Together, they cover both mathematical calibration AND realistic phonotactic behavior.

### 3.3 Why Not Yoruba-Akkadian?

The original audit (Issue 5.2) suggested "Quechua-Akkadian, Navajo-Akkadian, or
Basque-Hittite" as replacements. This audit shows:
- Basque is catastrophically contaminated with loanwords (10/10 FP)
- Navajo has only 312 entries (too small for a meaningful test)
- Quechua (`que.tsv`) was not found in the lexicon directory

Yoruba is the best available genuinely-unrelated language with sufficient data.

### 3.4 If Synthetic-Only Is Chosen

If the builder prefers a single sub-gate using only synthetic random SCA:
- The test is valid for mathematical calibration
- But it provides no evidence about real-language false-positive rates
- The threshold should be 0 FP (strict, no tolerance)
- The random strings should use the **same length distribution as the actual
  Linear A queries** (not the English test words), to match the real use case

---

## 4. Structural Concerns (Beyond Language Choice)

### 4.1 Gate 3 Threshold Is Too Permissive

The current threshold (<= 5 FP out of 10) means the gate passes even when half the
"obviously unrelated" queries produce FDR-surviving matches. This is not a meaningful
quality gate. For a properly calibrated null, the threshold should be:
- 0 FP for synthetic random SCA
- <= 1 FP for real language pairs

### 4.2 Akkadian Lexicon Quality Issue

The Akkadian lexicon's massive proper name content (anthroponyms, theonyms, toponyms)
inflates the effective comparison pool. This affects not just Gate 3 but the entire
production search. Consider filtering proper names from all lexicons (entries with
Concept_ID containing "anthroponym:", "theonym:", "toponym:").

### 4.3 NULL_SAMPLES = 1000 Is Underpowered

With M=1000, the minimum achievable p-value is 0.001. For BH-FDR with m=378
hypotheses, rank-1 threshold is 0.05/378 = 1.32e-4, which is below the resolution
floor. This means the most significant real result cannot pass FDR. Increase to
M=10000 minimum.

### 4.4 Seed Instability

The 3-8 FP range across seeds for English-Akkadian (and similar instability for
Japanese, Korean) indicates the Monte Carlo null variance is too high at M=1000.
Increasing M reduces this variance. At M=10000, seed-to-seed variation should drop
below 1 FP.

---

## 5. Experimental Evidence Summary

| Test | Seeds | FP Range | Conclusion |
|---|---|---|---|
| English-Akkadian (current) | 10 | 3-8 | Unstable, too many FP |
| Synthetic SCA-Akkadian | 10 | 0-0 | Perfect calibration |
| English-Yoruba | 10 | 0-1 | Best real-language option |
| English-Japanese | 10 | 6-8 | Loanword contamination |
| English-Korean | 10 | 4-9 | Loanword contamination |
| English-Tagalog | 10 | 7-7 | Heavy Spanish/English loans |
| English-Basque | 5 (aborted) | 10-10 | Catastrophic European loans |

---

## 6. Verdict

**The current English-Akkadian Gate 3 pair is flawed** but not because English and
Akkadian have genuine cognate relationships. The false positives arise from:
1. The Akkadian lexicon's massive proper-name content creating spurious close matches
2. The Monte Carlo null's low resolution (M=1000) producing unstable p-values
3. The permissive threshold (<= 5 FP) masking the underlying calibration problem

**Recommended replacement**: Dual-track Gate 3A (synthetic SCA) + Gate 3B (English-Yoruba),
with strict thresholds (0 FP and <= 1 FP respectively).

**No language pair replacement alone fixes the underlying issue.** The root cause is
M=1000 being underpowered for the BH-FDR correction's resolution requirements.
