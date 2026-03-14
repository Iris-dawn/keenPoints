"""Step 4: Outline generation — calls LLM (llm_id=3).

Input:  outputs/01_parsed_document.json + outputs/02_visual_analysis.json
Output: outputs/04_section_outlines.json

Requires: Steps 1, 2 completed.
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.slide import outline_generator
from tests.conftest import load_output


@pytest.mark.e2e
class TestStep4Outline:

    def test_generate(self):
        """Generate PPT outlines for each section."""
        parse_result = load_output("parsed_document")
        vis_analysis = load_output("visual_analysis")

        result = outline_generator.generate(parse_result, vis_analysis)

        assert "sections" in result
        assert "statistics" in result
        stats = result["statistics"]
        assert stats.get("total", 0) > 0
        assert stats.get("success", 0) > 0

        # Verify output file
        out = get_output_path(OUTPUT_FILES["section_outlines"])
        assert out.exists()

    def test_output_structure(self):
        """Verify outline sections contain slides with required fields."""
        result = load_output("section_outlines")

        for sec in result["sections"]:
            assert "section_name" in sec
            slides = sec.get("slides", [])
            for slide in slides:
                assert "slide_title" in slide
                assert "content_points" in slide
                assert "visual_refs" in slide
