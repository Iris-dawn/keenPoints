"""Step 1: Document parsing — offline, no LLM calls.

Input:  downloads/acl20_104/full.md + content_list.json
Output: outputs/01_parsed_document.json
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.document import document_parser


class TestStep1Parse:

    def test_parse_and_save(self, md_path, json_path):
        """Parse real paper and save structured result."""
        result = document_parser.parse_and_save(md_path, json_path)

        assert "sections" in result
        sections = result["sections"]
        assert len(sections) >= 5, f"Expected ≥5 sections, got {len(sections)}"

        # Verify output file was written
        out = get_output_path(OUTPUT_FILES["parsed_document"])
        assert out.exists(), f"Output not saved: {out}"

    def test_output_structure(self, md_path, json_path):
        """Verify each section has required fields."""
        result = document_parser.parse(md_path, json_path)

        for sec in result["sections"]:
            assert "name" in sec, f"Section missing 'name': {sec}"
            assert "content" in sec, f"Section missing 'content': {sec.get('name')}"
            assert "level" in sec

        # At least one section should have visual refs
        has_figs = any(sec.get("fig_refs") for sec in result["sections"])
        assert has_figs, "Expected at least one section with figure references"
