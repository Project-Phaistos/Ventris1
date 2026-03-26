"""Shared fixtures for Pillar 5 tests."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def results_dir(project_root: Path) -> Path:
    """Return the results directory."""
    return project_root / "results"


@pytest.fixture
def data_dir(project_root: Path) -> Path:
    """Return the data directory."""
    return project_root / "data"


@pytest.fixture
def configs_dir(project_root: Path) -> Path:
    """Return the configs directory."""
    return project_root / "configs"


@pytest.fixture
def p1_output(results_dir: Path) -> dict:
    """Load pillar 1 output."""
    with open(results_dir / "pillar1_output.json", "r") as f:
        return json.load(f)


@pytest.fixture
def p2_output(results_dir: Path) -> dict:
    """Load pillar 2 output."""
    with open(results_dir / "pillar2_output.json", "r") as f:
        return json.load(f)


@pytest.fixture
def p3_output(results_dir: Path) -> dict:
    """Load pillar 3 output."""
    with open(results_dir / "pillar3_output.json", "r") as f:
        return json.load(f)


@pytest.fixture
def p4_output(results_dir: Path) -> dict:
    """Load pillar 4 output."""
    with open(results_dir / "pillar4_output.json", "r") as f:
        return json.load(f)


@pytest.fixture
def sign_to_ipa(data_dir: Path) -> dict:
    """Load sign-to-IPA mapping."""
    with open(data_dir / "sign_to_ipa.json", "r") as f:
        return json.load(f)


@pytest.fixture
def lexicon_dir() -> Path:
    """Return the lexicon directory."""
    p = Path(__file__).parent.parent.parent.parent / "ancient-scripts-datasets" / "data" / "training" / "lexicons"
    if not p.exists():
        pytest.skip("Lexicon directory not found")
    return p
