"""Shared fixtures for Pillar 2 tests.

Session-scoped fixtures load the real SigLA corpus and Pillar 1 output,
then run the Pillar 2 pipeline stages once. Tests that need production
data share the (expensive) computation.

Also loads the Latin CV test corpus and the isolating language test corpus.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pillar1.corpus_loader import load_corpus, CorpusData
from pillar2.pillar1_loader import load_pillar1, Pillar1Output
from pillar2.segmenter import segment_corpus, SegmentedLexicon
from pillar2.affix_extractor import extract_affixes, AffixInventory
from pillar2.paradigm_inducer import induce_paradigms, ParadigmTable
from pillar2.inflection_classifier import classify_affixes
from pillar2.word_class_hinter import hint_word_classes, WordClassResult


# -- Paths -----------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORPUS_PATH = _PROJECT_ROOT / "data" / "sigla_full_corpus.json"
PILLAR1_PATH = _PROJECT_ROOT / "results" / "pillar1_output.json"

_FIXTURES = Path(__file__).resolve().parent / "fixtures"
LATIN_CORPUS_PATH = _FIXTURES / "latin_cv_corpus.json"
LATIN_P1_PATH = _FIXTURES / "latin_pillar1_output.json"
ISOLATING_CORPUS_PATH = _FIXTURES / "isolating_corpus.json"
ISOLATING_P1_PATH = _FIXTURES / "isolating_pillar1_output.json"


# ---------------------------------------------------------------------------
# Real Linear A corpus fixtures (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def real_corpus() -> CorpusData:
    """Load the real SigLA corpus once for the entire test session."""
    assert CORPUS_PATH.exists(), f"Corpus not found at {CORPUS_PATH}"
    return load_corpus(
        CORPUS_PATH,
        sign_types_included=["syllabogram"],
        exclude_damaged=True,
        min_word_length=2,
    )


@pytest.fixture(scope="session")
def real_pillar1() -> Pillar1Output:
    """Load the real Pillar 1 output once for the entire test session."""
    assert PILLAR1_PATH.exists(), f"Pillar 1 output not found at {PILLAR1_PATH}"
    return load_pillar1(PILLAR1_PATH)


@pytest.fixture(scope="session")
def real_lexicon(real_corpus: CorpusData, real_pillar1: Pillar1Output) -> SegmentedLexicon:
    """Run segmentation on the real corpus."""
    return segment_corpus(
        corpus=real_corpus,
        pillar1=real_pillar1,
        method="suffix_strip",
        min_word_length=2,
        min_suffix_frequency=3,
        min_suffix_stems=2,
        max_suffix_length=3,
    )


@pytest.fixture(scope="session")
def real_affix_inv(real_lexicon: SegmentedLexicon) -> AffixInventory:
    """Extract affixes from the real corpus."""
    return extract_affixes(real_lexicon, min_affix_stems=2)


@pytest.fixture(scope="session")
def real_paradigm_table(
    real_lexicon: SegmentedLexicon,
    real_affix_inv: AffixInventory,
    real_pillar1: Pillar1Output,
) -> ParadigmTable:
    """Induce paradigms from the real corpus."""
    return induce_paradigms(
        lexicon=real_lexicon,
        affix_inv=real_affix_inv,
        pillar1=real_pillar1,
    )


@pytest.fixture(scope="session")
def real_classified_inv(
    real_affix_inv: AffixInventory,
    real_paradigm_table: ParadigmTable,
) -> AffixInventory:
    """Classify affixes from the real corpus."""
    return classify_affixes(
        affix_inv=real_affix_inv,
        paradigm_table=real_paradigm_table,
    )


@pytest.fixture(scope="session")
def real_word_classes(
    real_lexicon: SegmentedLexicon,
    real_classified_inv: AffixInventory,
    real_paradigm_table: ParadigmTable,
) -> WordClassResult:
    """Hint word classes from the real corpus."""
    return hint_word_classes(
        lexicon=real_lexicon,
        affix_inv=real_classified_inv,
        paradigm_table=real_paradigm_table,
    )


# ---------------------------------------------------------------------------
# Latin CV test corpus fixtures (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def latin_corpus() -> CorpusData:
    """Load the Latin CV test corpus."""
    assert LATIN_CORPUS_PATH.exists(), f"Latin corpus not found at {LATIN_CORPUS_PATH}"
    return load_corpus(
        LATIN_CORPUS_PATH,
        sign_types_included=["syllabogram"],
        exclude_damaged=True,
        min_word_length=2,
    )


@pytest.fixture(scope="session")
def latin_pillar1() -> Pillar1Output:
    """Load the Latin Pillar 1 output."""
    assert LATIN_P1_PATH.exists(), f"Latin P1 not found at {LATIN_P1_PATH}"
    return load_pillar1(LATIN_P1_PATH)


@pytest.fixture(scope="session")
def latin_lexicon(
    latin_corpus: CorpusData, latin_pillar1: Pillar1Output
) -> SegmentedLexicon:
    """Segment the Latin corpus."""
    return segment_corpus(
        corpus=latin_corpus,
        pillar1=latin_pillar1,
        method="suffix_strip",
        min_word_length=2,
        min_suffix_frequency=3,
        min_suffix_stems=2,
        max_suffix_length=3,
    )


@pytest.fixture(scope="session")
def latin_affix_inv(latin_lexicon: SegmentedLexicon) -> AffixInventory:
    """Extract affixes from the Latin corpus."""
    return extract_affixes(latin_lexicon, min_affix_stems=2)


@pytest.fixture(scope="session")
def latin_paradigm_table(
    latin_lexicon: SegmentedLexicon,
    latin_affix_inv: AffixInventory,
    latin_pillar1: Pillar1Output,
) -> ParadigmTable:
    """Induce paradigms from the Latin corpus."""
    return induce_paradigms(
        lexicon=latin_lexicon,
        affix_inv=latin_affix_inv,
        pillar1=latin_pillar1,
    )


@pytest.fixture(scope="session")
def latin_classified_inv(
    latin_affix_inv: AffixInventory,
    latin_paradigm_table: ParadigmTable,
) -> AffixInventory:
    """Classify Latin affixes."""
    return classify_affixes(
        affix_inv=latin_affix_inv,
        paradigm_table=latin_paradigm_table,
    )


@pytest.fixture(scope="session")
def latin_word_classes(
    latin_lexicon: SegmentedLexicon,
    latin_classified_inv: AffixInventory,
    latin_paradigm_table: ParadigmTable,
) -> WordClassResult:
    """Hint word classes for the Latin corpus."""
    return hint_word_classes(
        lexicon=latin_lexicon,
        affix_inv=latin_classified_inv,
        paradigm_table=latin_paradigm_table,
    )


# ---------------------------------------------------------------------------
# Isolating language test corpus fixtures (session-scoped)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def isolating_corpus() -> CorpusData:
    """Load the isolating language test corpus."""
    assert ISOLATING_CORPUS_PATH.exists(), (
        f"Isolating corpus not found at {ISOLATING_CORPUS_PATH}"
    )
    return load_corpus(
        ISOLATING_CORPUS_PATH,
        sign_types_included=["syllabogram"],
        exclude_damaged=True,
        min_word_length=2,
    )


@pytest.fixture(scope="session")
def isolating_pillar1() -> Pillar1Output:
    """Load the isolating language Pillar 1 output."""
    assert ISOLATING_P1_PATH.exists(), (
        f"Isolating P1 not found at {ISOLATING_P1_PATH}"
    )
    return load_pillar1(ISOLATING_P1_PATH)


@pytest.fixture(scope="session")
def isolating_lexicon(
    isolating_corpus: CorpusData, isolating_pillar1: Pillar1Output
) -> SegmentedLexicon:
    """Segment the isolating corpus."""
    return segment_corpus(
        corpus=isolating_corpus,
        pillar1=isolating_pillar1,
        method="suffix_strip",
        min_word_length=2,
        min_suffix_frequency=3,
        min_suffix_stems=2,
        max_suffix_length=3,
    )


@pytest.fixture(scope="session")
def isolating_affix_inv(isolating_lexicon: SegmentedLexicon) -> AffixInventory:
    """Extract affixes from the isolating corpus."""
    return extract_affixes(isolating_lexicon, min_affix_stems=2)


@pytest.fixture(scope="session")
def isolating_paradigm_table(
    isolating_lexicon: SegmentedLexicon,
    isolating_affix_inv: AffixInventory,
    isolating_pillar1: Pillar1Output,
) -> ParadigmTable:
    """Induce paradigms from the isolating corpus."""
    return induce_paradigms(
        lexicon=isolating_lexicon,
        affix_inv=isolating_affix_inv,
        pillar1=isolating_pillar1,
    )


@pytest.fixture(scope="session")
def isolating_classified_inv(
    isolating_affix_inv: AffixInventory,
    isolating_paradigm_table: ParadigmTable,
) -> AffixInventory:
    """Classify affixes from the isolating corpus."""
    return classify_affixes(
        affix_inv=isolating_affix_inv,
        paradigm_table=isolating_paradigm_table,
    )


@pytest.fixture(scope="session")
def isolating_word_classes(
    isolating_lexicon: SegmentedLexicon,
    isolating_classified_inv: AffixInventory,
    isolating_paradigm_table: ParadigmTable,
) -> WordClassResult:
    """Hint word classes for the isolating corpus."""
    return hint_word_classes(
        lexicon=isolating_lexicon,
        affix_inv=isolating_classified_inv,
        paradigm_table=isolating_paradigm_table,
    )
