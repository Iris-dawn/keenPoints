"""Full document-to-slides pipeline orchestrator.

Coordinates all processing steps in order, reading each step's output
from the previous step's saved JSON.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings, get_output_path, OUTPUT_FILES
from app.core.logger import logger
from app.services.document import document_parser, visual_analyzer
from app.services.slide import (
    outline_generator,
    slide_pool_builder,
    narrative_reorder,
    visual_enhancer,
    slide_renderer,
)

TAG = "[PIPELINE]"


def run(md_path: str,
        json_path: Optional[str] = None,
        template: str = "BIT",
        target_slides: int = 21,
        delay: float = 1.0) -> Dict:
    """Execute the full document-to-slides pipeline.

    Steps:
      1. Parse document           → 01_parsed_document.json
      2. Analyze visual elements  → 02_visual_analysis.json
      3. Generate section outlines→ 03_section_outlines.json
      4. Build slide pool         → 04_slide_pool.json
      5. Narrative reorder        → 05_compressed_slides.json
      6. Visual enhancement       → 06_enhanced_slides.json
      7. Render HTML slides       → outputs/slides/<Template>/

    Args:
        md_path: Path to the main Markdown file from MinerU.
        json_path: Optional path to MinerU JSON output.
        template: Template name (default "BIT").
        target_slides: Target number of slides after compression.
        delay: Delay between LLM calls in seconds.

    Returns:
        Summary dict with slide count and output paths.
    """
    base = Path(md_path).parent
    logger.info(f"{TAG} ═══ Starting pipeline: {md_path} ═══")

    # Step 1: Parse document
    logger.info(f"{TAG} [1/7] Parsing document")
    parse_result = document_parser.parse_and_save(md_path, json_path)
    logger.info(f"{TAG} [1/7] Done — {len(parse_result.get('sections', []))} sections")

    # Step 2: Visual element analysis
    logger.info(f"{TAG} [2/7] Analyzing visual elements")
    vis_analysis = visual_analyzer.run(parse_result, base)
    logger.info(f"{TAG} [2/7] Done — {len(vis_analysis)} elements analyzed")

    # Step 3: Generate section outlines
    logger.info(f"{TAG} [3/7] Generating section outlines")
    outlines = outline_generator.generate(parse_result, vis_analysis)
    stats = outlines.get("statistics", {})
    logger.info(f"{TAG} [3/7] Done — {stats.get('success', 0)}/{stats.get('total', 0)} sections")

    # Step 4: Build slide pool
    logger.info(f"{TAG} [4/7] Building slide pool")
    slide_pool = slide_pool_builder.build(outlines, parse_result, vis_analysis)
    total_slides = slide_pool.get("statistics", {}).get("total_slides", 0)
    logger.info(f"{TAG} [4/7] Done — {total_slides} slides in pool")

    # Step 5: Narrative reorder + compression
    logger.info(f"{TAG} [5/7] Narrative reorder (target={target_slides})")
    compressed = narrative_reorder.run(target_n=target_slides)
    logger.info(f"{TAG} [5/7] Done — {len(compressed)} slides after compression")

    # Step 6: Visual enhancement
    logger.info(f"{TAG} [6/7] Visual enhancement")
    enhanced = visual_enhancer.run()
    enhanced_count = len(enhanced.get("slides", []))
    logger.info(f"{TAG} [6/7] Done — {enhanced_count} slides enhanced")

    # Step 7: Render HTML slides
    logger.info(f"{TAG} [7/7] Rendering HTML slides (template={template})")
    renderer = slide_renderer.SlideRenderer(template_name=template)
    html_files = renderer.generate_all(delay=delay)

    logger.info(f"{TAG} ═══ Pipeline complete: {len(html_files)} slides ═══")
    return {
        "slides_count": len(html_files),
        "output_files": [str(p) for p in html_files],
        "template": template,
        "steps_output": {k: str(get_output_path(v)) for k, v in OUTPUT_FILES.items()},
    }


def run_from_step(step: int,
                  template: str = "BIT",
                  target_slides: int = 21,
                  delay: float = 1.0,
                  md_path: Optional[str] = None,
                  json_path: Optional[str] = None) -> Dict:
    """Resume pipeline from a specific step, using previously saved outputs.

    Useful for re-running later steps without re-processing earlier ones.
    """
    base = Path(md_path).parent if md_path else None

    # Load previously saved data as needed
    def _load(key):
        path = get_output_path(OUTPUT_FILES[key])
        with path.open(encoding="utf-8") as f:
            return json.load(f)

    parse_result = _load("parsed_document") if step <= 3 else None
    vis_analysis = _load("visual_analysis") if step <= 4 else None

    if step <= 1 and md_path:
        parse_result = document_parser.parse_and_save(md_path, json_path)

    if step <= 2 and parse_result:
        vis_analysis = visual_analyzer.run(parse_result, base)

    if step <= 3 and parse_result and vis_analysis:
        outlines = outline_generator.generate(parse_result, vis_analysis)
    else:
        outlines = _load("section_outlines") if step <= 4 else None

    if step <= 4 and outlines and parse_result and vis_analysis:
        slide_pool_builder.build(outlines, parse_result, vis_analysis)

    if step <= 5:
        narrative_reorder.run(target_n=target_slides)

    if step <= 6:
        visual_enhancer.run()

    if step <= 7:
        renderer = slide_renderer.SlideRenderer(template_name=template)
        html_files = renderer.generate_all(delay=delay)
        return {
            "slides_count": len(html_files),
            "output_files": [str(p) for p in html_files],
            "template": template,
        }

    return {"message": f"Steps up to {step} completed"}
