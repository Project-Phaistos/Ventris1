"""Session-scoped fixtures for Pillar 4 tests.

Loads the real SigLA corpus and runs all pipeline stages as session-scoped
fixtures so they are computed once and shared across all test modules.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from pillar4.corpus_context_loader import load_context_corpus, ContextCorpus
from pillar4.ideogram_analyzer import analyze_ideograms, IdeogramAnalysisResult
from pillar4.transaction_analyzer import (
    analyze_transactions,
    TransactionAnalysisResult,
)
from pillar4.formula_mapper import map_formulas, FormulaMapResult
from pillar4.place_name_finder import find_place_names, PlaceNameResult
from pillar4.anchor_assembler import assemble_anchors, AnchorVocabulary
from pillar4.output_formatter import format_output


# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_CORPUS_PATH = _REPO_ROOT / "data" / "sigla_full_corpus.json"


# ---------------------------------------------------------------------------
# Default config values matching pillar4_default.yaml
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG = {
    "corpus_path": str(_CORPUS_PATH),
    "ideogram_adjacency_window": 3,
    "min_co_occurrence": 2,
    "min_exclusivity": 0.3,
    "co_occurrence_alpha": 0.05,
    "kuro_sign_ids": ["AB81", "AB02"],
    "fixed_element_threshold": 0.20,
    "variable_element_threshold": 0.05,
    "libation_inscription_types": [
        "libation_table",
        "libation table",
        "Libation table",
        "libation_table_corpus",
    ],
    "confirmed_place_names": [
        {
            "sign_ids": ["AB03", "AB28", "AB05"],
            "name": "Phaistos",
            "source": "Evans 1909; confirmed by site provenance and Linear B PA-I-TO",
            "confidence": 0.90,
        },
        {
            "sign_ids": ["AB28", "AB01"],
            "name": "Mount Ida",
            "source": "Widely accepted; geographic context + Linear B I-DA",
            "confidence": 0.80,
        },
        {
            "sign_ids": ["AB08", "AB07", "AB67", "AB04"],
            "name": "Dikte",
            "source": (
                "Widely accepted; attested at Psychro cave near Dikte "
                "+ Linear B DI-KI-TE"
            ),
            "confidence": 0.80,
        },
    ],
    "min_anchor_confidence": 0.3,
    "seed": 1234,
    "output_path": "results/pillar4_output.json",
}


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pillar4_config() -> dict:
    """Return the default Pillar 4 configuration."""
    return dict(_DEFAULT_CONFIG)


@pytest.fixture(scope="session")
def context_corpus() -> ContextCorpus:
    """Load the real SigLA corpus with full sign sequences."""
    return load_context_corpus(_CORPUS_PATH)


@pytest.fixture(scope="session")
def ideogram_result(context_corpus: ContextCorpus) -> IdeogramAnalysisResult:
    """Run ideogram co-occurrence analysis on the real corpus."""
    return analyze_ideograms(
        context_corpus,
        adjacency_window=_DEFAULT_CONFIG["ideogram_adjacency_window"],
        min_co_occurrence=_DEFAULT_CONFIG["min_co_occurrence"],
        min_exclusivity=_DEFAULT_CONFIG["min_exclusivity"],
        co_occurrence_alpha=_DEFAULT_CONFIG["co_occurrence_alpha"],
    )


@pytest.fixture(scope="session")
def transaction_result(
    context_corpus: ContextCorpus,
) -> TransactionAnalysisResult:
    """Run transaction analysis on the real corpus."""
    return analyze_transactions(
        context_corpus,
        kuro_sign_ids=_DEFAULT_CONFIG["kuro_sign_ids"],
    )


@pytest.fixture(scope="session")
def formula_result(context_corpus: ContextCorpus) -> FormulaMapResult:
    """Run formula mapping on the real corpus."""
    return map_formulas(
        context_corpus,
        libation_inscription_types=_DEFAULT_CONFIG[
            "libation_inscription_types"
        ],
        fixed_element_threshold=_DEFAULT_CONFIG["fixed_element_threshold"],
        variable_element_threshold=_DEFAULT_CONFIG[
            "variable_element_threshold"
        ],
    )


@pytest.fixture(scope="session")
def place_name_result(context_corpus: ContextCorpus) -> PlaceNameResult:
    """Run place name search on the real corpus."""
    return find_place_names(
        context_corpus,
        confirmed_place_names=_DEFAULT_CONFIG["confirmed_place_names"],
    )


@pytest.fixture(scope="session")
def anchor_vocab(
    ideogram_result: IdeogramAnalysisResult,
    transaction_result: TransactionAnalysisResult,
    formula_result: FormulaMapResult,
    place_name_result: PlaceNameResult,
) -> AnchorVocabulary:
    """Assemble the anchor vocabulary from all analysis results."""
    return assemble_anchors(
        ideogram_result=ideogram_result,
        transaction_result=transaction_result,
        formula_result=formula_result,
        place_name_result=place_name_result,
        min_anchor_confidence=_DEFAULT_CONFIG["min_anchor_confidence"],
    )
