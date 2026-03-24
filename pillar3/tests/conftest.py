"""Session-scoped fixtures for Pillar 3 tests.

Loads real corpus + P1 + P2 outputs via data_loader.load_all, then
runs each analysis step as session-scoped fixtures so they are
computed once and shared across all test modules.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from pillar3.data_loader import load_all, GrammarInputData
from pillar3.profile_builder import build_profiles, ProfileMatrix
from pillar3.word_class_inducer import induce_word_classes, WordClassResult
from pillar3.word_order_analyzer import analyze_word_order, WordOrderResult
from pillar3.agreement_detector import detect_agreement, AgreementResult
from pillar3.functional_word_finder import find_functional_words, FunctionalWordResult


# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PILLAR1_PATH = _REPO_ROOT / "results" / "pillar1_output.json"
_PILLAR2_PATH = _REPO_ROOT / "results" / "pillar2_output.json"
_CORPUS_PATH = _REPO_ROOT / "data" / "sigla_full_corpus.json"


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def grammar_input() -> GrammarInputData:
    """Load real corpus + P1 + P2 outputs via data_loader.load_all."""
    return load_all(
        pillar1_path=_PILLAR1_PATH,
        pillar2_path=_PILLAR2_PATH,
        corpus_path=_CORPUS_PATH,
    )


@pytest.fixture(scope="session")
def profiles(grammar_input: GrammarInputData) -> ProfileMatrix:
    """Build distributional profiles from grammar_input."""
    return build_profiles(grammar_input)


@pytest.fixture(scope="session")
def word_classes(
    profiles: ProfileMatrix,
    grammar_input: GrammarInputData,
) -> WordClassResult:
    """Induce word classes from profiles."""
    return induce_word_classes(
        profiles,
        grammar_input.pillar2,
        config={"random_state": 1234},
    )


@pytest.fixture(scope="session")
def word_order(
    grammar_input: GrammarInputData,
    word_classes: WordClassResult,
) -> WordOrderResult:
    """Analyze word order from grammar_input and word classes."""
    return analyze_word_order(grammar_input, word_classes)


@pytest.fixture(scope="session")
def agreement(
    grammar_input: GrammarInputData,
    word_classes: WordClassResult,
) -> AgreementResult:
    """Detect agreement patterns from grammar_input and word classes."""
    return detect_agreement(grammar_input, word_classes)


@pytest.fixture(scope="session")
def functional_words(
    grammar_input: GrammarInputData,
    word_classes: WordClassResult,
) -> FunctionalWordResult:
    """Find functional words from grammar_input and word classes."""
    return find_functional_words(grammar_input, word_classes=word_classes)
