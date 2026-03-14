"""Step 6: Narrative reorder + compression — offline, no LLM calls.

Input:  outputs/05_slide_pool.json
Output: outputs/06_compressed_slides.json

Requires: Step 5 completed.
"""

import json

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.slide import narrative_reorder
from tests.conftest import load_output


class TestStep6Reorder:

    def test_run(self):
        """Run narrative compression on slide pool."""
        compressed = narrative_reorder.run(target_n=21)

        assert isinstance(compressed, list)
        assert 15 <= len(compressed) <= 25, \
            f"Expected 15-25 slides after compression, got {len(compressed)}"

        # Verify output file
        out = get_output_path(OUTPUT_FILES["compressed_slides"])
        assert out.exists()

    def test_output_structure(self):
        """Verify compressed slides have required fields and roles."""
        with get_output_path(OUTPUT_FILES["compressed_slides"]).open(encoding="utf-8") as f:
            data = json.load(f)

        slides = data["slides"]
        roles = {s.get("role") for s in slides}
        assert len(roles) >= 3, f"Expected ≥3 distinct roles, got {roles}"

        for slide in slides:
            assert "slide_id" in slide
            assert "slide_title" in slide
            assert "role" in slide
            assert "content_points" in slide
            assert "visual_refs" in slide

    def test_custom_target(self):
        """Compression with different target."""
        compressed = narrative_reorder.run(target_n=15)
        assert len(compressed) <= 20, f"With target=15, got {len(compressed)} slides"
