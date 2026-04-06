# Adversarial Verification: freq_norm Bias Correction Implementation

**Date:** 2026-04-03
**Verifier:** Adversarial critic (Claude Opus 4.6, independent code audit)
**File under audit:** `pillar5/scripts/analytical_null_search.py`
**Scope:** `freq_norm_adjust_pvalue()` and its integration into the pipeline

---

## 0. Executive Summary

| Question | Verdict |
|----------|---------|
| Simple division or class-conditional null? | **Simple division** (multiplicative adjustment on raw p-value) |
| Does it double-count the null? | **YES** -- confirmed. See Section 2. |
| Edge cases handled? | **PARTIALLY** -- zero mean rate handled, but per-class zero rate NOT handled |
| Does it change u-wi-ri? | **NO** -- u-wi-ri is safe (fully phonetic, empty reading_map) |
| LB holdout: help, hurt, or neutral? | **INCONCLUSIVE** -- no holdout results on disk; structural analysis predicts neutral-to-harmful |

**Bottom line:** The implementation is simple ratio-based multiplication (`p * rate(C) / mean_rate`), not the class-conditional null tables recommended by the prior audit (`da_bias_fix_verification.md`, Section 5.3). The adjustment double-counts information already present in the Monte Carlo null. It should either be replaced with class-conditional null tables or removed entirely.

---

## 1. What freq_norm Actually Does (Lines 755-784)

### 1.1 The Function

```python
def freq_norm_adjust_pvalue(
    raw_pvalue: float,
    reading_map: dict[str, str],      # {sign_id: candidate_reading}
    class_rates: dict[str, float],    # {SCA_class: background_rate}
) -> float:
```

For each unknown sign in `reading_map`:
1. Map the candidate reading to its SCA consonant class via `_reading_to_sca_class()` (line 664-676).
2. Look up `class_rates[cls]` -- a background match rate for that class.
3. Compute `relative_rate = class_rates[cls] / mean_rate` where `mean_rate` is the mean of all non-vowel class rates.
4. Multiply into a running `adjustment` product.
5. Return `min(1.0, raw_pvalue * adjustment)`.

### 1.2 The Background Rates (Lines 679-733)

`compute_class_background_rates()` works as follows:

For each consonant class C:
1. Generate `samples_per_class` random SCA strings where the first character is C (rest uniform random).
2. Find the best NED against the lexicon pool for each.
3. Compute `class_mean_ned[C] = mean(best_NEDs)`.
4. Convert to rate: `rates[C] = 1.0 / max(class_mean_ned[C], 0.01)`.

**This is an inverse-NED metric, not a match rate.** Lower mean NED (easier matching) produces higher rate. The 0.01 floor prevents division by zero on the NED side.

### 1.3 Summary of What Happens

The adjustment is:

```
adjusted_p = raw_p * product_over_unknowns( (1/mean_ned_C) / mean(1/mean_ned_all) )
```

For classes with lower-than-average mean NED (easier matching, like T-class), the ratio > 1, so p-values are inflated (penalized). For classes with higher-than-average mean NED (harder matching, like W-class), the ratio < 1, so p-values are deflated (rewarded).

**This IS simple division, not class-conditional null tables.**

---

## 2. Double-Counting the Null -- CONFIRMED

### 2.1 The Problem

The raw p-value (`raw_pvalue`) already comes from `pvalue_from_null_table()` (line 646-658), which computes:

```
p = (count of null samples with NED <= observed NED + 1) / (M + 1)
```

The null table is built by `build_null_table()` (line 417-452), which generates random SCA strings **uniformly from the 12-class alphabet**. This means the null distribution already implicitly averages over all consonant classes: approximately 1/12 of null samples start with each class. The p-value therefore already reflects the aggregate difficulty of matching at each SCA class composition.

### 2.2 How This Creates Double-Counting

When `freq_norm_adjust_pvalue` multiplies the p-value by `rate(C) / mean_rate`:

- The **numerator** (`rate(C)`) measures how easily class C matches the lexicon -- which is the same information the null table captured when ~1/12 of its random strings started with C.
- The **denominator** (`mean_rate`) is the average ease of matching across all classes -- which is what the unconditional null table represents.

The raw p-value already incorporates the fact that some SCA compositions match more easily than others, because the null table samples from the same alphabet. Multiplying by the class-specific rate re-applies this correction.

### 2.3 Concrete Example

Consider an unknown sign assigned reading "da" (SCA class T) vs "wa" (SCA class W):

1. **Null table:** ~8.3% of null samples start with T, ~8.3% start with W. If T-initial strings tend to have lower NED against Semitic lexicons, the null distribution already includes more low-NED entries from T-class strings.

2. **raw p-value:** For "da" matching a Semitic word at NED=0.2, the p-value already accounts for the fact that T-class strings match Semitic lexicons well (many null samples also achieved NED <= 0.2 because 1/12 of them started with T).

3. **freq_norm adjustment:** `rate(T) / mean_rate > 1` further inflates the p-value. This double-penalizes "da" for the same statistical fact: T-class matches are easy against Semitic lexicons.

### 2.4 Why It Still Reduces "da" Bias in Practice

Despite the double-counting, freq_norm does partially suppress "da" bias because:

- The null table's class-averaging is weak: each class contributes only ~8.3% of samples, so the null is dominated by the aggregate distribution, not any single class.
- The freq_norm adjustment is a direct multiplicative correction, which has a stronger per-hypothesis effect than the diluted signal in the unconditional null.

However, the magnitude of correction is **statistically unprincipled** -- it over-corrects for some classes and under-corrects for others, with no guarantee of calibration.

### 2.5 The Correct Alternative

As identified in `da_bias_fix_verification.md` (Section 5.3), the correct approach is **class-conditional null tables**:

- For each unknown position with class C, generate null strings where that position is constrained to class C.
- The resulting p-value is `P(NED <= d | null, consonant = C)` -- the null already conditions on the consonant class.
- No post-hoc multiplicative adjustment is needed.

This avoids double-counting entirely. Computational cost: 12x more null tables (one per class), estimated 6 minutes vs 30 seconds. Acceptable.

---

## 3. Edge Case Analysis

### 3.1 Zero Mean Rate (HANDLED)

Line 772-773:
```python
if mean_rate == 0:
    return raw_pvalue
```

If all consonant classes have zero rate (impossible in practice -- would require all random strings to have mean NED >= 100), the function returns the unadjusted p-value. **Safe.**

### 3.2 Zero Per-Class Rate (NOT HANDLED)

The rate computation (line 730) has a floor:
```python
rates[cls] = 1.0 / max(mn, 0.01)
```

This prevents `rates[cls]` from being infinite (when mean NED = 0), capping it at 100.0. But the floor of 0.01 on mean NED is arbitrary. A class with mean NED = 0.01 (near-perfect matching) gets rate = 100.0, while a class with mean NED = 0.5 (mediocre matching) gets rate = 2.0. The 50:1 ratio may create extreme adjustments.

**Risk:** For small lexicons (e.g., Phrygian with 79 entries), a rare consonant class might have very few lexicon entries in the comparison window, producing a mean NED near 1.0 (no matches) and rate near 1.0. Meanwhile a common class could have mean NED near 0.1 and rate 10.0. The adjustment factor `10.0 / mean_all` could be large.

### 3.3 Rare Consonant Classes in Small Lexicons (NOT HANDLED)

No minimum lexicon size gate exists. `compute_class_background_rates()` runs on all lexicons regardless of size. For a lexicon where a given length bucket has 0-2 entries, the mean NED for any class is noisy (variance ~ 1/sqrt(samples_per_class) on an already-noisy estimator).

**Recommendation:** Apply a minimum pool size check (e.g., skip freq_norm for pools with < 20 entries).

### 3.4 Multiple Unknowns (MULTIPLICATIVE INTERACTION)

Line 775-780:
```python
adjustment = 1.0
for _sign_id, reading in reading_map.items():
    cls = _reading_to_sca_class(reading)
    if cls in class_rates:
        relative_rate = class_rates[cls] / mean_rate
        adjustment *= relative_rate
```

For stems with 2+ unknowns, the adjustment is the product of per-unknown ratios. If both unknowns are assigned T-class readings (e.g., "da" + "ta"), the adjustment squares the T-class penalty. This is statistically incorrect: the background rates are computed for first-character class, but the second unknown may be at a different position in the SCA string.

**The class rates are position-insensitive but the adjustment is applied position-independently.** The first-character bias measured by `compute_class_background_rates()` does not apply to an unknown at position 3 of a 5-character SCA string.

### 3.5 Vowel Class (HANDLED INCORRECTLY)

Line 732:
```python
rates["V"] = 1.0
```

Vowels are hardcoded to rate 1.0 regardless of actual vowel matching statistics. Line 768 excludes vowels from the mean calculation. But `_reading_to_sca_class()` (line 664-676) returns "V" for pure vowel readings (e.g., reading "a" for an unknown sign). This means:

- `relative_rate = 1.0 / mean_rate` (since rates["V"] = 1.0)
- If `mean_rate > 1` (likely -- inverse NED rates are typically > 1), then `relative_rate < 1`, giving vowel readings a **discount** (lower p-value) regardless of actual vowel frequency in the lexicon.

This is a systematic bias toward vowel readings for unknowns.

---

## 4. u-wi-ri Impact -- CONFIRMED SAFE

u-wi-ri (AB10-AB07-AB53) is fully phonetic. All three signs have known IPA readings in `sign_to_ipa.json`:

- AB10 = "u"
- AB07 = "wi"
- AB53 = "ri"

In `enumerate_reading_hypotheses()` (line 1174-1183), when `unknowns` is empty:
```python
if not unknowns:
    return [{"reading_map": {}, ...}]
```

The `reading_map` is `{}` (empty dict).

In `freq_norm_adjust_pvalue()` (line 765-766):
```python
if not reading_map or not class_rates:
    return raw_pvalue
```

Empty `reading_map` triggers an immediate return of the unadjusted p-value.

**Confirmed:** freq_norm has zero effect on u-wi-ri. The NED=0.000 match to Urartian "awari" (and the NED=0.167 matches to Hittite "awarna" and Lycian "uwedri") are completely unaffected.

This also holds for any other fully-phonetic stem where all sign readings are already known.

---

## 5. LB Holdout Impact Analysis

### 5.1 No Stored Results

No holdout comparison results were found on disk. The `compare_approaches()` function (line 2017-2133) exists but has not been run (or results were not persisted).

### 5.2 Structural Prediction

Based on code analysis, the holdout test (lines 917-1038) works as follows:

1. Each of 11 LB signs with known readings is treated as unknown.
2. Candidate readings are generated from the grid cell.
3. Each candidate is searched against all 18 lexicons.
4. The best raw p-value across languages is selected.
5. freq_norm adjusts this p-value based on the consonant class of the candidate reading.
6. The candidate with the lowest adjusted p-value is selected.

**Key structural observation:** The holdout test uses a fixed padding context ("pa" + candidate + "ru", line 959). The unknown is always at position 2 of a 3-position query. The freq_norm rates, however, are computed based on **first-character** class (line 713: `rand_sca = cls + rest`). This is a position mismatch: the adjustment penalizes based on first-character difficulty but the unknown occupies a middle position.

### 5.3 Predicted Outcomes

For the 11 holdout signs:

| Sign | Known | SCA class | Prediction |
|------|-------|-----------|------------|
| AB01 | da | T | freq_norm penalizes (T is common), may hurt if true answer is "da" |
| AB06 | na | N | freq_norm near-neutral (N is mid-frequency) |
| AB08 | a | V | freq_norm discounts (vowel gets relative_rate < 1), may help or hurt |
| AB27 | re | R | freq_norm near-neutral |
| AB37 | ti | T | freq_norm penalizes, may hurt |
| AB45 | de | T | freq_norm penalizes, may hurt |
| AB57 | ja | J | freq_norm may reward (J is rare), may help |
| AB59 | ta | T | freq_norm penalizes, may hurt |
| AB60 | ra | R | freq_norm near-neutral |
| AB67 | ki | K | freq_norm penalizes somewhat (K is common) |
| AB70 | ko | K | freq_norm penalizes somewhat |

**4 of 11** signs are T-class (da, ti, de, ta). If freq_norm penalizes T-class readings, it may cause these 4 signs to be assigned incorrect non-T readings, **reducing** holdout accuracy.

**Predicted verdict: freq_norm is likely neutral-to-harmful on the LB holdout**, because 36% of holdout ground truth labels are T-class, and freq_norm penalizes T-class readings.

---

## 6. Recommendations

### 6.1 Replace Simple Division with Class-Conditional Null Tables

The current implementation double-counts the null and uses position-insensitive first-character rates for position-independent unknowns. The correct fix is class-conditional null tables as specified in `da_bias_fix_verification.md` Section 5.3:

- For each (query_length, language, unknown_position, SCA_class) tuple, build a null table where the unknown position is fixed to the given SCA class.
- Use `p(reading) = P(NED <= d | null, consonant_at_position = C)` directly.
- No multiplicative post-hoc adjustment needed.

### 6.2 If Keeping Simple Division, Fix Edge Cases

If class-conditional null tables are not implemented:

1. **Position sensitivity:** Compute per-position class rates, not just first-character rates.
2. **Small lexicon gate:** Skip freq_norm for lexicons with < 50 pool entries.
3. **Vowel handling:** Compute actual vowel-position match rates instead of hardcoding `rates["V"] = 1.0`.
4. **Multiple unknowns:** Use additive log-adjustment instead of multiplicative product to avoid squared/cubed penalties.

### 6.3 Run the Holdout Comparison

Execute `python analytical_null_search.py --compare` and persist results. The structural prediction (Section 5.3) suggests freq_norm may hurt on the LB holdout due to T-class prevalence in ground truth. Empirical confirmation is needed before committing to freq_norm as the default.

---

## 7. Severity Assessment

| Issue | Severity | Impact |
|-------|----------|--------|
| Double-counting the null | **HIGH** | P-values are not calibrated; false positive rate unknown |
| Position mismatch | **MEDIUM** | Adjustment based on wrong position; noisy but not catastrophic |
| No small-lexicon gate | **LOW** | Affects 2-3 small lexicons; dominated by larger lexicons in practice |
| Vowel rate hardcoding | **LOW** | Few unknowns assigned vowel readings; minor systematic bias |
| u-wi-ri safety | **NONE** | Fully phonetic stems are completely unaffected |
| Multiplicative multi-unknown | **MEDIUM** | Squared penalties for stems with 2+ unknowns; over-correction |

**Overall: The freq_norm implementation is a well-intentioned but statistically unprincipled heuristic. It partially addresses the "da" bias through brute-force multiplication, but at the cost of calibration and with double-counting of the null model's information. Class-conditional null tables are the correct solution.**
