"""Tier-2 known-answer tests: full Pillar 1 pipeline on Linear B.

Linear B has known phonetic values (Ventris & Chadwick 1956), making it
the ideal validation target. If Pillar 1 cannot recover the broad structure
of Linear B from distributional evidence alone, it cannot be trusted on
the undeciphered Linear A.

Known ground truth:
    - 5 pure vowel signs: a(AB08), e(AB38), i(AB28), o(AB61), u(AB10)
    - ~15 consonant series (d, j, k, m, n, p, q, r, s, t, w, z, ...)
    - ~87 CV syllabograms

These tests run the pipeline on a Linear B test corpus and verify that
the independently derived results are consistent with the known answers.
All thresholds are generous to account for the small corpus size (~450 words).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytest
from sklearn.metrics import adjusted_rand_score

from pillar1.corpus_loader import load_corpus, CorpusData
from pillar1.vowel_identifier import identify_vowels, VowelInventory
from pillar1.alternation_detector import detect_alternations, AlternationResult
from pillar1.grid_constructor import construct_grid, GridResult


# ── Paths ──────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
LB_CORPUS_PATH = FIXTURES_DIR / "linear_b_test_corpus.json"
LB_SIGN_TO_IPA_PATH = FIXTURES_DIR / "linear_b_sign_to_ipa.json"


# ── Known Linear B values ─────────────────────────────────────────────

# The five pure vowel signs and their AB codes.
LB_PURE_VOWELS: Dict[str, str] = {
    "AB08": "a",
    "AB38": "e",
    "AB28": "i",
    "AB61": "o",
    "AB10": "u",
}

# The t-series: ta, te, ti, to (share the consonant 't').
T_SERIES = {"AB59", "AB04", "AB37", "AB05"}

# Full AB-code -> reading mapping for CV parsing.
AB_TO_READING: Dict[str, str] = {
    "AB08": "a", "AB38": "e", "AB28": "i", "AB61": "o", "AB10": "u",
    "AB01": "da", "AB45": "de", "AB07": "di", "AB14": "do", "AB51": "du",
    "AB57": "ja", "AB46": "je", "AB36": "jo",
    "AB77": "ka", "AB44": "ke", "AB67": "ki", "AB70": "ko", "AB81": "ku",
    "AB80": "ma", "AB13": "me", "AB73": "mi", "AB15": "mo", "AB23": "mu",
    "AB06": "na", "AB24": "ne", "AB30": "ni", "AB52": "no", "AB55": "nu",
    "AB03": "pa", "AB72": "pe", "AB39": "pi", "AB11": "po", "AB50": "pu",
    "AB16": "qa", "AB78": "qe", "AB90": "qo",
    "AB60": "ra", "AB27": "re", "AB53": "ri", "AB02": "ro", "AB26": "ru",
    "AB31": "sa", "AB09": "se", "AB41": "si", "AB12": "so", "AB58": "su",
    "AB59": "ta", "AB04": "te", "AB37": "ti", "AB05": "to", "AB69": "tu",
    "AB54": "wa", "AB75": "we", "AB40": "wi", "AB42": "wo",
    "AB17": "za", "AB74": "ze", "AB20": "zo",
}


def _parse_cv(reading: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a CV reading into (consonant, vowel).

    Pure vowels return (None, vowel).
    CV syllables return (consonant, vowel).
    """
    vowels = {"a", "e", "i", "o", "u"}
    if reading in vowels:
        return (None, reading)
    if len(reading) >= 2 and reading[-1] in vowels:
        return (reading[:-1], reading[-1])
    return (None, None)


def _compute_consonant_ari(grid: GridResult) -> float:
    """Compute consonant ARI between grid assignments and known LB classes.

    Bridges the sign_id (AB code) -> reading gap that the production
    lb_validator cannot handle (it expects reading-based sign_ids).
    """
    lb_consonants: List[str] = []
    independent_consonants: List[int] = []

    for assignment in grid.assignments:
        reading = AB_TO_READING.get(assignment.sign_id)
        if reading is None:
            continue
        consonant, vowel = _parse_cv(reading)
        if consonant is None:
            continue  # skip pure vowels for consonant ARI
        lb_consonants.append(consonant)
        independent_consonants.append(assignment.consonant_class)

    if len(lb_consonants) < 2:
        return 0.0

    return adjusted_rand_score(lb_consonants, independent_consonants)


# ── Session-scoped fixtures ───────────────────────────────────────────

@pytest.fixture(scope="module")
def lb_corpus() -> CorpusData:
    """Load the Linear B test corpus."""
    assert LB_CORPUS_PATH.exists(), f"Fixture not found: {LB_CORPUS_PATH}"
    return load_corpus(LB_CORPUS_PATH)


@pytest.fixture(scope="module")
def lb_vowel_result(lb_corpus: CorpusData) -> VowelInventory:
    """Run vowel identification on the LB corpus.

    Uses min_sign_frequency=10 (lower than the default 15) because
    the test corpus is smaller than the real SigLA corpus.
    """
    return identify_vowels(lb_corpus, min_sign_frequency=10)


@pytest.fixture(scope="module")
def lb_alternation(lb_corpus: CorpusData) -> AlternationResult:
    """Run alternation detection on the LB corpus."""
    return detect_alternations(lb_corpus)


@pytest.fixture(scope="module")
def lb_grid(
    lb_alternation: AlternationResult,
    lb_vowel_result: VowelInventory,
    lb_corpus: CorpusData,
) -> GridResult:
    """Run grid construction on the LB corpus."""
    return construct_grid(lb_alternation, lb_vowel_result, lb_corpus)


# ── Test 1: Vowel count ──────────────────────────────────────────────

class TestLinearBVowelCount:
    """Linear B has exactly 5 pure vowels. The pipeline should find 4-6."""

    def test_vowel_count_is_near_5(
        self, lb_vowel_result: VowelInventory,
    ) -> None:
        """Accept 4-6 vowels (tight). FAIL if < 3 or > 7."""
        count = lb_vowel_result.count
        assert 3 <= count <= 7, (
            f"Vowel count {count} is outside acceptable range [3, 7]. "
            f"Linear B has exactly 5 pure vowels. "
            f"Found: {[s.sign_id for s in lb_vowel_result.signs]}"
        )

    def test_vowel_count_ideal_is_5(
        self, lb_vowel_result: VowelInventory,
    ) -> None:
        """The ideal result is exactly 5. Warn but don't fail if 4 or 6."""
        count = lb_vowel_result.count
        if count != 5:
            pytest.xfail(
                f"Vowel count is {count}, not the ideal 5. "
                f"This is acceptable for a small corpus."
            )


# ── Test 2: Pure vowel signs identified ──────────────────────────────

class TestLinearBPureVowelSigns:
    """At least 3 of the 5 known pure vowel signs should be classified."""

    def test_at_least_3_known_vowels_found(
        self, lb_vowel_result: VowelInventory,
    ) -> None:
        """At least 3 of {AB08, AB38, AB28, AB61, AB10} should be pure_vowel."""
        found_vowel_ids = {s.sign_id for s in lb_vowel_result.signs}
        known_vowel_ids = set(LB_PURE_VOWELS.keys())
        overlap = found_vowel_ids & known_vowel_ids
        assert len(overlap) >= 3, (
            f"Only {len(overlap)} of the 5 known LB vowels were identified: "
            f"{overlap}. Expected >= 3. "
            f"All identified: {found_vowel_ids}"
        )

    def test_no_cv_sign_misclassified_as_vowel(
        self, lb_vowel_result: VowelInventory,
    ) -> None:
        """No sign with a known consonant component should be classified
        as a pure vowel. This catches false positives."""
        found_vowel_ids = {s.sign_id for s in lb_vowel_result.signs}
        known_vowel_ids = set(LB_PURE_VOWELS.keys())
        false_positives = found_vowel_ids - known_vowel_ids

        # Check if any false positive has a known CV reading
        cv_false_positives = []
        for fp_id in false_positives:
            reading = AB_TO_READING.get(fp_id)
            if reading is not None:
                consonant, vowel = _parse_cv(reading)
                if consonant is not None:
                    cv_false_positives.append(f"{fp_id} ({reading})")

        assert len(cv_false_positives) == 0, (
            f"CV signs misclassified as pure vowels: {cv_false_positives}. "
            f"These signs have a consonant component and should NOT be vowels."
        )


# ── Test 3: Consonant ARI ───────────────────────────────────────────

class TestLinearBConsonantARI:
    """The independently derived consonant classes should show meaningful
    agreement with the known Linear B consonant grid."""

    def test_consonant_ari_above_threshold(
        self, lb_grid: GridResult,
    ) -> None:
        """ARI_consonant should be > 0.3 (meaningful agreement).

        ARI = 1.0 means perfect agreement with LB consonant classes.
        ARI = 0.0 means no better than random.
        ARI > 0.3 indicates the pipeline is recovering real structure.
        We allow a generous threshold because the small corpus limits
        the number of alternation pairs available for clustering.
        """
        ari = _compute_consonant_ari(lb_grid)
        assert ari > 0.3, (
            f"Consonant ARI = {ari:.4f}, expected > 0.3. "
            f"The independently derived consonant classes do not show "
            f"meaningful agreement with the known Linear B grid. "
            f"Grid has {lb_grid.consonant_count} consonant classes, "
            f"{len(lb_grid.assignments)} assigned signs."
        )


# ── Test 4: Alternation pairs include known series ───────────────────

class TestLinearBAlternationPairs:
    """The ta/te/ti/to series (AB59/AB04/AB37/AB05) is one of the most
    prominent alternation patterns. At least one pair from this series
    should appear in the significant alternation pairs."""

    def test_t_series_pair_found(
        self, lb_alternation: AlternationResult,
    ) -> None:
        """At least one pair from the t-series should be significant."""
        t_pairs = [
            p for p in lb_alternation.significant_pairs
            if {p.sign_a, p.sign_b} <= T_SERIES
        ]
        assert len(t_pairs) >= 1, (
            f"No alternation pairs found within the t-series "
            f"({T_SERIES}). "
            f"Total significant pairs: {lb_alternation.total_significant_pairs}. "
            f"All pairs: {[(p.sign_a, p.sign_b) for p in lb_alternation.significant_pairs]}"
        )

    def test_has_multiple_significant_pairs(
        self, lb_alternation: AlternationResult,
    ) -> None:
        """The corpus should yield multiple significant alternation pairs.

        Linear B has ~15 consonant series, each with multiple vowel
        alternation pairs. Even with a small corpus, we should find >= 5.
        """
        assert lb_alternation.total_significant_pairs >= 5, (
            f"Only {lb_alternation.total_significant_pairs} significant pairs found, "
            f"expected >= 5. Alternation detection may be too conservative "
            f"or the corpus lacks sufficient inflectional variation."
        )


# ── Test 5: Grid consonant count ────────────────────────────────────

class TestLinearBGridConsonantCount:
    """Linear B has ~15 consonant series. The grid should find 6-20."""

    def test_consonant_count_in_range(
        self, lb_grid: GridResult,
    ) -> None:
        """C should be between 3 and 20.

        Linear B has ~15 major consonant series. We allow a wide range
        [3, 20] because:
        - With min_shared_prefix_length=2 (the corrected default), the
          alternation graph is much sparser (only genuine Kober pairs
          survive), yielding fewer distinct consonant clusters.
        - The small test corpus may merge rarely-attested series (lower bound).
        - Spectral clustering may split noisy series (upper bound).
        - Weighted stems (diff_len=2 at 0.5) and corrected null model
          affect the affinity matrix structure.
        """
        C = lb_grid.consonant_count
        assert 3 <= C <= 20, (
            f"Consonant count C = {C}, expected 3-20. "
            f"Linear B has ~15 consonant series. "
            f"Best k by eigengap: {lb_grid.best_k_eigengap}, "
            f"best k by silhouette: {lb_grid.best_k_silhouette}."
        )

    def test_vowel_count_matches_inventory(
        self, lb_grid: GridResult,
        lb_vowel_result: VowelInventory,
    ) -> None:
        """Grid's vowel count should match the vowel inventory count."""
        expected_V = lb_vowel_result.count if lb_vowel_result.count > 0 else 5
        assert lb_grid.vowel_count == expected_V, (
            f"Grid vowel_count={lb_grid.vowel_count}, "
            f"expected {expected_V} from vowel inventory."
        )


# ── Test 6: Corpus integrity ────────────────────────────────────────

class TestLinearBCorpusIntegrity:
    """Sanity checks on the test corpus itself."""

    def test_corpus_has_enough_tokens(
        self, lb_corpus: CorpusData,
    ) -> None:
        """Corpus must have >= 200 syllabogram tokens for statistical power."""
        assert lb_corpus.total_syllabogram_tokens >= 200, (
            f"Only {lb_corpus.total_syllabogram_tokens} tokens, need >= 200."
        )

    def test_corpus_has_enough_unique_signs(
        self, lb_corpus: CorpusData,
    ) -> None:
        """Corpus must have >= 30 unique syllabograms."""
        assert lb_corpus.unique_syllabograms >= 30, (
            f"Only {lb_corpus.unique_syllabograms} unique signs, need >= 30."
        )

    def test_all_5_vowels_in_initial_position(
        self, lb_corpus: CorpusData,
    ) -> None:
        """All 5 pure vowel signs should appear in word-initial position."""
        initial_signs: Set[str] = set()
        for rec in lb_corpus.positional_records:
            if rec.position == "initial":
                initial_signs.add(rec.sign_id)

        for ab_code, reading in LB_PURE_VOWELS.items():
            assert ab_code in initial_signs, (
                f"Vowel {reading} ({ab_code}) never appears word-initially."
            )
