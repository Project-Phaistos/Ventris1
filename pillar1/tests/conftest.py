"""Shared fixtures for Pillar 1 tests.

Session-scoped fixtures load the real SigLA corpus and run each
pipeline stage once, so tests that depend on production output
share the (expensive) computation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pillar1.corpus_loader import load_corpus, CorpusData
from pillar1.vowel_identifier import identify_vowels, VowelInventory
from pillar1.alternation_detector import detect_alternations, AlternationResult
from pillar1.grid_constructor import construct_grid, GridResult

# ── Paths ──────────────────────────────────────────────────────────────

CORPUS_PATH = Path(__file__).resolve().parents[2] / "data" / "sigla_full_corpus.json"


# ── Session-scoped fixtures ────────────────────────────────────────────

@pytest.fixture(scope="session")
def corpus_data() -> CorpusData:
    """Load the real SigLA corpus once for the entire test session."""
    assert CORPUS_PATH.exists(), f"Corpus not found at {CORPUS_PATH}"
    return load_corpus(CORPUS_PATH)


@pytest.fixture(scope="session")
def vowel_result(corpus_data: CorpusData) -> VowelInventory:
    """Run vowel identification on the real corpus."""
    return identify_vowels(corpus_data)


@pytest.fixture(scope="session")
def alternation_result(corpus_data: CorpusData) -> AlternationResult:
    """Run alternation detection on the real corpus."""
    return detect_alternations(corpus_data)


@pytest.fixture(scope="session")
def grid_result(
    alternation_result: AlternationResult,
    vowel_result: VowelInventory,
    corpus_data: CorpusData,
) -> GridResult:
    """Run grid construction on the real corpus."""
    return construct_grid(alternation_result, vowel_result, corpus_data)
