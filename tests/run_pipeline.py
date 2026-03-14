"""Pipeline step runner — execute tests step by step or run the full pipeline.

Usage:
    python -m tests.run_pipeline              # run all steps sequentially
    python -m tests.run_pipeline 1            # run step 1 only
    python -m tests.run_pipeline 1 5          # run steps 1 through 5
    python -m tests.run_pipeline 6 8          # run steps 6 through 8

Each step prints its result summary and saves output to outputs/.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import ensure_dirs, get_output_path, OUTPUT_FILES
from app.core.logger import logger

PAPER_DIR = Path("downloads/acl20_104")
MD_PATH = str(PAPER_DIR / "full.md")
JSON_PATH = str(PAPER_DIR / "9eafd4f2-7e84-4bf8-b8ae-7fd19e07a68b_content_list.json")


def _load(key):
    import json
    path = get_output_path(OUTPUT_FILES[key])
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def step1():
    """Parse document."""
    from app.services.document import document_parser
    result = document_parser.parse_and_save(MD_PATH, JSON_PATH)
    n = len(result.get("sections", []))
    print(f"  Step 1 ✓  {n} sections parsed → {OUTPUT_FILES['parsed_document']}")
    return result


def step2():
    """Visual analysis."""
    from app.services.document import visual_analyzer
    parse_result = _load("parsed_document")
    result = visual_analyzer.run(parse_result, PAPER_DIR)
    print(f"  Step 2 ✓  {len(result)} elements analyzed → {OUTPUT_FILES['visual_analysis']}")
    return result


def step3():
    """Outline generation."""
    from app.services.slide import outline_generator
    parse_result = _load("parsed_document")
    vis_analysis = _load("visual_analysis")
    result = outline_generator.generate(parse_result, vis_analysis)
    stats = result.get("statistics", {})
    print(f"  Step 3 ✓  {stats.get('success', 0)}/{stats.get('total', 0)} outlines → {OUTPUT_FILES['section_outlines']}")
    return result


def step4():
    """Slide pool building."""
    from app.services.slide import slide_pool_builder
    outlines = _load("section_outlines")
    parse_result = _load("parsed_document")
    vis_analysis = _load("visual_analysis")
    result = slide_pool_builder.build(outlines, parse_result, vis_analysis)
    n = result.get("statistics", {}).get("total_slides", 0)
    print(f"  Step 4 ✓  {n} slides in pool → {OUTPUT_FILES['slide_pool']}")
    return result


def step5():
    """Narrative reorder."""
    from app.services.slide import narrative_reorder
    compressed = narrative_reorder.run(target_n=21)
    print(f"  Step 5 ✓  {len(compressed)} slides after compression → {OUTPUT_FILES['compressed_slides']}")
    return compressed


def step6():
    """Visual enhancement."""
    from app.services.slide import visual_enhancer
    result = visual_enhancer.run()
    n = len(result.get("slides", []))
    print(f"  Step 6 ✓  {n} slides enhanced → {OUTPUT_FILES['enhanced_slides']}")
    return result


def step7():
    """Render HTML slides."""
    from app.services.slide.slide_renderer import SlideRenderer
    renderer = SlideRenderer(template_name="BIT")
    files = renderer.generate_all(delay=1.0)
    print(f"  Step 7 ✓  {len(files)} HTML slides → outputs/slides/BIT/")
    return files


STEPS = {1: step1, 2: step2, 3: step3, 4: step4,
         5: step5, 6: step6, 7: step7}


def main():
    ensure_dirs()
    args = sys.argv[1:]

    if len(args) == 0:
        start, end = 1, 7
    elif len(args) == 1:
        start = end = int(args[0])
    else:
        start, end = int(args[0]), int(args[1])

    print(f"\n{'═' * 50}")
    print(f"  Running steps {start}–{end}")
    print(f"{'═' * 50}\n")

    for i in range(start, end + 1):
        fn = STEPS.get(i)
        if fn is None:
            print(f"  Unknown step: {i}")
            continue
        try:
            fn()
        except Exception as e:
            print(f"  Step {i} ✗  {e}")
            raise

    print(f"\n{'═' * 50}")
    print(f"  Done.")
    print(f"{'═' * 50}\n")


if __name__ == "__main__":
    main()
