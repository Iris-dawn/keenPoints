"""API routes — maps each pipeline step to a REST endpoint."""

import json
import shutil
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, File, UploadFile, HTTPException, Form

from app.core.config import settings, get_output_path, OUTPUT_FILES, set_current_paper, get_current_paper
from app.core.logger import logger
from app.services.client import mineru_client
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


# ── MinerU: upload & parse document ─────────────────────────────────────────

@router.post("/mineru/upload")
async def mineru_upload(file: UploadFile = File(...)):
    """Upload a PDF/DOC/PPT file, parse it via MinerU, then run document parse.

    If a previous MinerU result for the same filename already exists in the
    downloads directory (full.md present), skip the MinerU API call entirely
    and re-use the cached result.
    """
    if not settings.MINERU_TOKEN:
        raise HTTPException(503, "MINERU_TOKEN not configured")
    if not file.filename:
        raise HTTPException(400, "Filename is required")

    stem = Path(file.filename).stem
    set_current_paper(stem)
    extract_dir = Path(settings.BASE_DIR) / settings.DOWNLOAD_DIR / stem
    md_file = next(extract_dir.rglob("full.md"), None) if extract_dir.exists() else None

    if md_file:
        logger.info(f"[ROUTE] cached MinerU result found for '{stem}', skipping API call")
        # Consume the uploaded bytes so the multipart form is fully read
        await file.read()
    else:
        upload_dir = Path(settings.BASE_DIR) / settings.UPLOAD_DIR
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / Path(file.filename).name
        file_path.write_bytes(await file.read())

        try:
            await mineru_client.process_files([str(file_path)])
        except Exception as e:
            raise HTTPException(500, f"MinerU processing failed: {e}")

        md_file = next(extract_dir.rglob("full.md"), None)
        if not md_file:
            raise HTTPException(500, "MinerU completed but full.md not found in output")

    json_file = next(extract_dir.rglob("*content_list.json"), None)

    result = document_parser.parse_and_save(
        str(md_file),
        str(json_file) if json_file else None,
    )
    return {
        "sections": len(result.get("sections", [])),
        "output": OUTPUT_FILES["parsed_document"],
    }


# ── Step 1: Parse document ────────────────────────────────────────────────────

@router.post("/parse")
async def parse_document(
    file: UploadFile = File(...),
    json_file: Optional[UploadFile] = File(None),
):
    """Upload a Markdown (+ optional JSON) file and parse into sections."""
    if not file.filename:
        raise HTTPException(400, "Filename is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".md", ".txt"):
        raise HTTPException(
            400,
            f"Unsupported file type '{suffix}'. "
            "Upload .md/.txt directly, or use /mineru/upload for PDF/DOC/PPT files.",
        )

    set_current_paper(Path(file.filename).stem)

    upload_dir = Path(settings.BASE_DIR) / settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)

    md_path = upload_dir / Path(file.filename).name
    md_path.write_bytes(await file.read())

    json_path = None
    if json_file and json_file.filename:
        json_path = upload_dir / Path(json_file.filename).name
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
    """Step 6a — Classify slides and write strategy fields (no image generation)."""
    comp_path = get_output_path(OUTPUT_FILES["compressed_slides"])
    if not comp_path.exists():
        raise HTTPException(400, "Run /narrative/reorder first")

    result = visual_enhancer.run_strategy()
    slides = result.get("slides", [])
    report = result.get("report", {})
    counts = {"image": 0, "css": 0, "skip": 0}
    for v in report.values():
        counts[v.get("strategy", "skip")] = counts.get(v.get("strategy", "skip"), 0) + 1
    return {
        "slides": len(slides),
        "strategy_counts": counts,
        "output": OUTPUT_FILES["enhanced_slides"],
    }


@router.post("/visual/enhance/images")
def enhance_images(slide_ids: Optional[str] = None, delay: float = 1.5):
    """Step 6b (optional) — Generate AI images for image-strategy slides.

    slide_ids: optional comma-separated list of slide_id integers to process.
               If omitted, all un-generated image-strategy slides are processed.
    """
    enhanced_path = get_output_path(OUTPUT_FILES["enhanced_slides"])
    if not enhanced_path.exists():
        raise HTTPException(400, "Run /visual/enhance (strategy) first")

    ids: Optional[List[int]] = None
    if slide_ids:
        try:
            ids = [int(x.strip()) for x in slide_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(422, "slide_ids must be comma-separated integers")

    result = visual_enhancer.run_images(slide_ids=ids, delay=delay)
    return {
        "generated": result.get("generated", 0),
        "report": result.get("report", {}),
        "output": OUTPUT_FILES["enhanced_slides"],
    }


# ── Step 7: Render HTML slides ──────────────────────────────────────────────

@router.post("/slide/render")
def render_slides(template: str = "BIT", delay: float = 1.0,
                  slide_id: Optional[int] = None):
    """Render enhanced slides to HTML.

    If slide_id is given, render only that slide; otherwise render all slides.
    """
    enhanced_path = get_output_path(OUTPUT_FILES["enhanced_slides"])
    if not enhanced_path.exists():
        raise HTTPException(400, "Run /visual/enhance first")

    renderer = slide_renderer.SlideRenderer(template_name=template)
    files = renderer.generate_all(delay=delay, slide_id=slide_id)
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

    if file.filename:
        set_current_paper(Path(file.filename).stem)

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


# ── Papers ───────────────────────────────────────────────────────────────────

@router.get("/papers")
def list_papers():
    """List all available paper output directories."""
    output_base = Path(settings.BASE_DIR) / settings.OUTPUT_DIR
    papers = []
    skip = {"slides", "generated_images"}
    if output_base.exists():
        for p in sorted(output_base.iterdir()):
            if not p.is_dir() or p.name.startswith(".") or p.name in skip:
                continue
            json_files = list(p.glob("*.json"))
            slides_dir = p / "slides"
            html_files = list(slides_dir.glob("*.html")) if slides_dir.exists() else []
            papers.append({
                "name": p.name,
                "json_count": len(json_files),
                "has_slides": len(html_files) > 0,
                "slide_count": len(html_files),
            })
    return {"papers": papers, "current": get_current_paper()}


@router.post("/papers/select")
def select_paper(payload: dict):
    """Switch the active paper context."""
    name = payload.get("name")
    if name:
        output_base = Path(settings.BASE_DIR) / settings.OUTPUT_DIR
        paper_dir = output_base / name
        if not paper_dir.exists() or not paper_dir.is_dir():
            raise HTTPException(404, f"Paper not found: {name}")
        # Basic safety check
        if ".." in Path(name).parts:
            raise HTTPException(400, "Invalid paper name")
    set_current_paper(name or None)
    return {"selected": name, "current": get_current_paper()}


# ── Utility ──────────────────────────────────────────────────────────────────

@router.get("/outputs")
def list_outputs():
    """List all output files for the current paper."""
    paper = get_current_paper()
    output_dir = Path(settings.BASE_DIR) / settings.OUTPUT_DIR
    if paper:
        output_dir = output_dir / paper
    if not output_dir.exists():
        return {"files": [], "paper": paper}
    files = sorted(
        f.name for f in output_dir.iterdir()
        if f.is_file() and f.suffix == ".json"
    )
    return {"files": files, "paper": paper}


@router.get("/outputs/{filename:path}")
def get_output(filename: str):
    """Retrieve a saved pipeline output by filename."""
    safe = Path(filename)
    if ".." in safe.parts:
        raise HTTPException(400, "Invalid path")
    # Resolve under the current paper's output directory
    path = get_output_path(str(safe))
    if not path.exists():
        raise HTTPException(404, f"Output not found: {filename}")
    if path.is_dir():
        items = sorted(f.name for f in path.iterdir() if f.is_file())
        return {"files": items}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@router.put("/outputs/{filename}")
def save_output_file(filename: str, data: dict):
    """Save/update an output file under the current paper directory."""
    safe = Path(filename)
    if ".." in safe.parts:
        raise HTTPException(400, "Invalid path")
    path = get_output_path(str(safe))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": str(safe)}


# ── Pipeline Status ──────────────────────────────────────────────────────────

@router.get("/pipeline/status")
def pipeline_status():
    """Check which pipeline steps have completed outputs."""
    status = {}
    for key, fname in OUTPUT_FILES.items():
        path = get_output_path(fname)
        status[key] = {
            "file": fname,
            "exists": path.exists(),
            "size": path.stat().st_size if path.exists() else 0,
        }
    status["current_paper"] = get_current_paper()
    # Check rendered slides
    slides_dir = Path(settings.BASE_DIR) / settings.OUTPUT_DIR / "slides"
    rendered = []
    if slides_dir.exists():
        for template_dir in slides_dir.iterdir():
            if template_dir.is_dir():
                html_files = sorted(f.name for f in template_dir.glob("*.html"))
                rendered.append({"template": template_dir.name, "files": html_files})
    status["rendered_slides"] = rendered
    return status


# ── Single Slide Render ──────────────────────────────────────────────────────

@router.post("/slide/render-single")
def render_single_slide(payload: dict):
    """Render a single slide to HTML."""
    slide_data = payload.get("slide")
    template = payload.get("template", "BIT")
    if not slide_data:
        raise HTTPException(400, "Missing slide data")

    renderer = slide_renderer.SlideRenderer(template_name=template)
    out_path = renderer.render_slide(slide_data, index=payload.get("index", 0))
    return {"html_file": out_path.name}
