"""Tests for Manual_Generator — unit tests and Property 33.

# Feature: anti-uav-dataset-workflow, Property 33: MANUAL.md contains all required sections
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from anti_uav.manual_generator import generate_manual

# ---------------------------------------------------------------------------
# Required section headings (all 8)
# ---------------------------------------------------------------------------

_REQUIRED_SECTIONS = [
    "## Project Overview",
    "## Folder Structure",
    "## Step-by-Step Procedure",
    "## Trained Weights Guide",
    "## Results Interpretation",
    "## Run Comparison Guide",
    "## Troubleshooting",
    "## Glossary",
]


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_generate_manual_creates_file():
    """MANUAL.md is created at the given root."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        result = generate_manual(root)
        assert result == root / "MANUAL.md"
        assert result.exists()


def test_generate_manual_has_all_sections():
    """All 8 required section headings are present in MANUAL.md."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = generate_manual(root)
        content = out.read_text(encoding="utf-8")
        for section in _REQUIRED_SECTIONS:
            assert section in content, f"Missing required section: {section!r}"


def test_generate_manual_has_colab_subsection():
    """Step-by-Step Procedure contains a Google Colab subsection."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = generate_manual(root)
        content = out.read_text(encoding="utf-8")
        assert "Colab" in content, "Expected 'Colab' subsection in MANUAL.md"


def test_generate_manual_has_kaggle_subsection():
    """Step-by-Step Procedure contains a Kaggle subsection."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = generate_manual(root)
        content = out.read_text(encoding="utf-8")
        assert "Kaggle" in content, "Expected 'Kaggle' subsection in MANUAL.md"


def test_generate_manual_non_empty():
    """MANUAL.md has non-zero file size."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out = generate_manual(root)
        assert out.stat().st_size > 0, "MANUAL.md should not be empty"


def test_generate_manual_idempotent():
    """Calling generate_manual twice overwrites with the same content without error."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        out1 = generate_manual(root)
        content1 = out1.read_text(encoding="utf-8")
        out2 = generate_manual(root)
        content2 = out2.read_text(encoding="utf-8")
        assert out1 == out2
        assert content1 == content2, "Second call should produce identical content"


# ---------------------------------------------------------------------------
# Property 33: MANUAL.md contains all required sections
# Validates: Requirements 14.2
# ---------------------------------------------------------------------------

@settings(max_examples=10, deadline=None)
@given(subdir=st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_-"),
    min_size=1,
    max_size=20,
))
def test_property33_manual_has_all_sections(subdir: str):
    """**Validates: Requirements 14.1-14.5**

    Property 33: For any root path, generate_manual writes MANUAL.md with all 8 required
    section headings.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / subdir
        root.mkdir(parents=True, exist_ok=True)
        out = generate_manual(root)
        assert out == root / "MANUAL.md"
        content = out.read_text(encoding="utf-8")
        for section in _REQUIRED_SECTIONS:
            assert section in content, (
                f"Missing section {section!r} for root={root}"
            )
