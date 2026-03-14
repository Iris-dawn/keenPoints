"""Step 2: Visual element analysis — calls LLM (llm_id=2).

Input:  outputs/01_parsed_document.json
Output: outputs/02_visual_analysis.json

Requires: Step 1 completed.
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.document import visual_analyzer
from tests.conftest import load_output


@pytest.mark.e2e
class TestStep2Visual:

    def test_run(self, paper_dir):
        """Extract and analyze visual elements from parsed document."""
        parse_result = load_output("parsed_document")

        result = visual_analyzer.run(parse_result, paper_dir)

        assert isinstance(result, list)
        assert len(result) >= 1, "Should find at least 1 visual element"

        # Verify output file
        out = get_output_path(OUTPUT_FILES["visual_analysis"])
        assert out.exists()

    def test_output_structure(self):
        """Verify each analyzed element has required fields."""
        result = load_output("visual_analysis")

        for elem in result:
            assert "element" in elem
            assert "section_name" in elem
            el = elem["element"]
            assert "type" in el
            assert "id" in el

            # LLM analysis should be present
            if "analysis" in elem:
                assert "analysis_text" in elem["analysis"]
