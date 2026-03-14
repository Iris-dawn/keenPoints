"""API routes — maps each pipeline step to a REST endpoint."""

import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Form

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
from app.services import pipeline
from app.services.template import list_templates

router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health():
    return {"status": "ok", "version": settings.VERSION}


# ── Step 1: Parse document ────────────────────────────────────────────────────

@router.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    json_file: Optional[UploadFile] = File(None),
):
    """Upload a Markdown (+ optional JSON) file and parse into sections."""
    upload_dir = Path(settings.BASE_DIR) / settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    md_path = upload_dir / file.filename
    md_path.write_bytes(await file.read())

    json_path = None
    if json_file:
        json_path = upload_dir / json_file.filename
        json_path.write_bytes(await json_file.read())

    result = document_parser.parse_and_save(
        str(md_path), str(json_path) if json_path else None
    )
    return {"sections": len(result.get("sections", [])), "output": OUTPUT_FILES["parsed_document"]}


# ── Step 2: Visual analysis ──────────────────────────────────────────────────

@router.post("/analyze/visual")
def analyze_visual(base_path: Optional[str] = Form(None)):
    """Analyze visual elements from the parsed document."""
    parse_path = get_output_path(OUTPUT_FILES["parsed_document"])
    if not parse_path.exists():
        raise HTTPException(400, "Run /parse first")
    with parse_path.open(encoding="utf-8") as f:
        parse_result = json.load(f)
    bp = Path(base_path) if base_path else None
    result = visual_analyzer.run(parse_result, bp)
    return {"elements": len(result), "output": OUTPUT_FILES["visual_analysis"]}


# ── Step 3: Outline generation ───────────────────────────────────────────────

@router.post("/outline/generate")
def generate_outline():
    """Generate PPT section outlines from parsed document + visual analysis."""
    parse_path = get_output_path(OUTPUT_FILES["parsed_document"])
    vis_path = get_output_path(OUTPUT_FILES["visual_analysis"])
    if not parse_path.exists():
        raise HTTPException(400, "Run /parse first")
    if not vis_path.exists():
        raise HTTPException(400, "Run /analyze/visual first")

    with parse_path.open(encoding="utf-8") as f:
        parse_result = json.load(f)
    with vis_path.open(encoding="utf-8") as f:
        vis_analysis = json.load(f)

    result = outline_generator.generate(parse_result, vis_analysis)
    return {
        "statistics": result.get("statistics", {}),
        "output": OUTPUT_FILES["section_outlines"],
    }


# ── Step 4: Slide pool ──────────────────────────────────────────────────────

@router.post("/slide-pool/build")
def build_slide_pool():
    """Build the complete slide pool from outlines + parse + visual data."""
    parse_path = get_output_path(OUTPUT_FILES["parsed_document"])
    vis_path = get_output_path(OUTPUT_FILES["visual_analysis"])
    outline_path = get_output_path(OUTPUT_FILES["section_outlines"])
    for name, path in [("parse", parse_path), ("visual", vis_path), ("outline", outline_path)]:
        if not path.exists():
            raise HTTPException(400, f"Missing prerequisite: {name}")

    with parse_path.open(encoding="utf-8") as f:
        parse_result = json.load(f)
    with vis_path.open(encoding="utf-8") as f:
        vis_analysis = json.load(f)
    with outline_path.open(encoding="utf-8") as f:
        outlines = json.load(f)

    result = slide_pool_builder.build(outlines, parse_result, vis_analysis)
    return {
        "statistics": result.get("statistics", {}),
        "output": OUTPUT_FILES["slide_pool"],
    }


# ── Step 5: Narrative reorder ───────────────────────────────────────────────

@router.post("/narrative/reorder")
def reorder(target_slides: int = 21):
    """Run narrative compression on the slide pool."""
    pool_path = get_output_path(OUTPUT_FILES["slide_pool"])
    if not pool_path.exists():
        raise HTTPException(400, "Run /slide-pool/build first")

    compressed = narrative_reorder.run(target_n=target_slides)
    return {
        "slides": len(compressed),
        "output": OUTPUT_FILES["compressed_slides"],
    }


# ── Step 6: Visual enhancement ──────────────────────────────────────────────

@router.post("/visual/enhance")
def enhance_visual():
    """Enhance text-only slides with images or CSS strategies."""
    comp_path = get_output_path(OUTPUT_FILES["compressed_slides"])
    if not comp_path.exists():
        raise HTTPException(400, "Run /narrative/reorder first")

    result = visual_enhancer.run()
    return {
        "slides": len(result.get("slides", [])),
        "output": OUTPUT_FILES["enhanced_slides"],
    }


# ── Step 7: Render HTML slides ──────────────────────────────────────────────

@router.post("/slide/render")
def render_slides(template: str = "BIT", delay: float = 1.0):
    """Render enhanced slides to HTML using the specified template."""
    enhanced_path = get_output_path(OUTPUT_FILES["enhanced_slides"])
    if not enhanced_path.exists():
        raise HTTPException(400, "Run /visual/enhance first")

    renderer = slide_renderer.SlideRenderer(template_name=template)
    files = renderer.generate_all(delay=delay)
    return {
        "slides": len(files),
        "files": [f.name for f in files],
        "template": template,
    }


# ── Full pipeline ────────────────────────────────────────────────────────────

@router.post("/pipeline/run")
async def run_pipeline(
    file: UploadFile = File(...),
    json_file: Optional[UploadFile] = File(None),
    template: str = Form("BIT"),
    target_slides: int = Form(21),
):
    """Run the complete document-to-slides pipeline."""
    upload_dir = Path(settings.BASE_DIR) / settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    md_path = upload_dir / file.filename
    md_path.write_bytes(await file.read())

    json_path = None
    if json_file:
        json_path = upload_dir / json_file.filename
        json_path.write_bytes(await json_file.read())

    result = pipeline.run(
        str(md_path),
        str(json_path) if json_path else None,
        template=template,
        target_slides=target_slides,
    )
    return result


# ── Templates ────────────────────────────────────────────────────────────────

@router.get("/templates")
def get_templates():
    """List available slide templates."""
    return {"templates": list_templates()}


# ── Utility ──────────────────────────────────────────────────────────────────

@router.get("/outputs/{filename}")
def get_output(filename: str):
    """Retrieve a saved pipeline output by filename."""
    path = get_output_path(filename)
    if not path.exists():
        raise HTTPException(404, f"Output not found: {filename}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)
