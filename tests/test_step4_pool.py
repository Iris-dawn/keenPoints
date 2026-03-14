"""Step 5: Slide pool building — offline, no LLM calls.

Input:  outputs/04_section_outlines.json + 01 + 02
Output: outputs/05_slide_pool.json

Requires: Steps 1, 2, 4 completed.
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.slide import slide_pool_builder
from tests.conftest import load_output


class TestStep5Pool:

    def test_build(self):
        """Build slide pool from outlines + parsed data + visual analysis."""
        outlines = load_output("section_outlines")
        parse_result = load_output("parsed_document")
        vis_analysis = load_output("visual_analysis")

        result = slide_pool_builder.build(outlines, parse_result, vis_analysis)

        assert "slides" in result
        assert "statistics" in result
        total = result["statistics"].get("total_slides", 0)
        assert total >= 10, f"Expected ≥10 slides in pool, got {total}"

        # Verify output file
        out = get_output_path(OUTPUT_FILES["slide_pool"])
        assert out.exists()

    def test_output_structure(self):
        """Verify slides have IDs, titles, content, and refs."""
        result = load_output("slide_pool")

        slides = result["slides"]
        ids = [s["slide_id"] for s in slides]
        assert ids == sorted(ids), "slide_id should be sequential"

        for slide in slides:
            assert "slide_id" in slide
            assert "slide_title" in slide
            assert "section_name" in slide
            assert "content_points" in slide
            assert "visual_refs" in slide
