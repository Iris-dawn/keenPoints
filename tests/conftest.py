"""Shared fixtures for pipeline step tests.

All tests use real data from downloads/acl20_104/ (HiAGM paper).
"""

import json
from pathlib import Path

import pytest

from app.core.config import settings, ensure_dirs, get_output_path, OUTPUT_FILES

# ── Real data paths ──────────────────────────────────────────────────────────

BASE = Path(settings.BASE_DIR)
PAPER_DIR = BASE / "downloads" / "acl20_104"
MD_PATH = PAPER_DIR / "full.md"
JSON_PATH = PAPER_DIR / "9eafd4f2-7e84-4bf8-b8ae-7fd19e07a68b_content_list.json"


@pytest.fixture(scope="session", autouse=True)
def setup_dirs():
    """Ensure output directories exist before any test runs."""
    ensure_dirs()


@pytest.fixture(scope="session")
def md_path() -> str:
    assert MD_PATH.exists(), f"Test data not found: {MD_PATH}"
    return str(MD_PATH)


@pytest.fixture(scope="session")
def json_path() -> str:
    assert JSON_PATH.exists(), f"Test data not found: {JSON_PATH}"
    return str(JSON_PATH)


@pytest.fixture(scope="session")
def paper_dir() -> Path:
    return PAPER_DIR


def load_output(key: str) -> dict | list:
    """Load a pipeline output JSON by key name."""
    path = get_output_path(OUTPUT_FILES[key])
    assert path.exists(), f"Output not found: {path}. Run the previous step first."
    with path.open(encoding="utf-8") as f:
        return json.load(f)
