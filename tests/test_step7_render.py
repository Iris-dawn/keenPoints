"""Step 8: HTML slide rendering — calls LLM (llm_id=4).

Input:  outputs/07_enhanced_slides.json
Output: outputs/slides/BIT/*.html

Requires: Step 7 completed.
"""

import pytest

from app.core.config import get_output_path, OUTPUT_FILES
from app.services.slide.slide_renderer import SlideRenderer


@pytest.mark.live
class TestStep8Render:

    def test_render_single(self):
        """Render a single slide by index."""
        renderer = SlideRenderer(template_name="BIT")
        files = renderer.generate_all(index=0)

        assert len(files) == 1
        html = files[0].read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_render_all(self):
        """Render all slides (full generation)."""
        renderer = SlideRenderer(template_name="BIT")
        files = renderer.generate_all(delay=1.0)

        assert len(files) >= 10, f"Expected ≥10 slides, got {len(files)}"

        # Viewer file should be created
        viewer = renderer.output_dir / "_viewer.html"
        assert viewer.exists()

        # Each file should be valid HTML
        for f in files[:3]:  # spot check first 3
            content = f.read_text(encoding="utf-8")
            assert len(content) > 200, f"Slide {f.name} too short: {len(content)} chars"
