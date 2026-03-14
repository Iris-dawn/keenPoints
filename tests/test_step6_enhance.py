"""Step 7: Visual enhancement — calls Gemini (image) + Dify (text rewrite).

Input:  outputs/06_compressed_slides.json
Output: outputs/07_enhanced_slides.json

Requires: Step 6 completed.
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.slide import visual_enhancer
from tests.conftest import load_output


class TestStep7EnhanceClassify:
    """Classify slides into enhancement strategies (offline, no LLM)."""

    def test_classify_all(self):
        """Every slide gets a strategy: image, css, or none."""
        data = load_output("compressed_slides")

        for slide in data["slides"]:
            result = visual_enhancer.classify(slide)
            assert "strategy" in result
            assert result["strategy"] in ("image", "css", "skip")
            if result["strategy"] == "css":
                assert "css_strategy" in result
            if result["strategy"] == "image":
                assert "image_type" in result


@pytest.mark.e2e
class TestStep7EnhanceDryRun:
    """Dry-run enhancement (no API calls, validates logic)."""

    def test_dry_run(self):
        """Dry run should return all slides without API calls."""
        result = visual_enhancer.run(dry_run=True)

        assert "slides" in result
        slides = result["slides"]
        assert len(slides) >= 10

        for slide in slides:
            ve = slide.get("visual_enhance", {})
            assert "strategy" in ve


@pytest.mark.live
class TestStep7EnhanceLive:
    """Full enhancement with real Gemini + Dify calls."""

    def test_run(self):
        """Run visual enhancement with real API calls."""
        result = visual_enhancer.run()

        assert "slides" in result
        out = get_output_path(OUTPUT_FILES["enhanced_slides"])
        assert out.exists()

        # At least one slide should have been enhanced
        enhanced = [s for s in result["slides"]
                    if s.get("visual_enhance", {}).get("strategy") != "none"]
        assert len(enhanced) >= 1
