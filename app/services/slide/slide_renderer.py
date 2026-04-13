"""HTML slide renderer: convert enhanced slides to standalone HTML pages via LLM.

Reads from 07_enhanced_slides.json, renders each slide to HTML using Dify (llm_id=4),
and writes output to outputs/slides/<TemplateName>/.
"""

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings, get_output_path, OUTPUT_FILES
from app.core.logger import logger
from app.services.client.llm_client import get_client, extract_html_output
from app.services.template import TemplateContent, get_template, list_templates

TAG = "[RENDER]"

_DEFAULT_OUTPUT_BASE = Path(settings.BASE_DIR) / settings.OUTPUT_DIR / "slides"
_ASSETS_BASE = Path(__file__).parent.parent / "template" / "assets"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_layout(slide: dict, role_to_layout: Dict[str, str]) -> str:
    enhance = slide.get("visual_enhance", {})
    if enhance.get("strategy") == "image":
        return "text_image_generated"
    if enhance.get("strategy") == "css" and enhance.get("css_strategy"):
        return enhance["css_strategy"]

    role = slide.get("role", "")
    images = slide["visual_refs"].get("images", [])
    tables = slide["visual_refs"].get("tables", [])
    equations = slide["visual_refs"].get("equations", [])

    if role in role_to_layout:
        return role_to_layout[role]
    if tables:
        return "table_result"
    if equations:
        return "equation"
    if images:
        return "text_image"
    return "text_only"


def _section_num(section_name: str) -> str:
    m = re.match(r"^(\d[\d.]*)", section_name.strip())
    return m.group(1).rstrip(".") if m else "?"


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "_", text.strip())[:40]


def _strip_fences(text: str) -> str:
    text = re.sub(r"^```[\w]*\n?", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
    return text.strip()


def _build_prompt(slide, layout, sec_num, page_label, assets, img_base, template):
    title = slide["slide_title"]
    purpose = slide["slide_purpose"]
    points = slide["content_points"]
    images = slide["visual_refs"].get("images", [])
    tables = slide["visual_refs"].get("tables", [])
    equations = slide["visual_refs"].get("equations", [])

    shell = template.shell_snippet(sec_num, title, page_label, assets)
    css_skel = template.layout_css_skeletons.get(
        layout, template.layout_css_skeletons.get("text_only", "")
    )
    color_vars = "  ".join(f"--{k}:{v}" for k, v in template.colors.items())

    imgs_block = ""
    if images:
        lines = []
        for img in images:
            prefix = (img.get("img_src_prefix") or img_base).rstrip("/")
            rel = prefix + "/" + img.get("img_path", "")
            cap = img.get("caption", "")
            desc = img.get("analysis_text", "")[:200]
            lines.append(f'  - src: "{rel}"\n    caption: "{cap}"\n    description: "{desc}"')
        imgs_block = "IMAGES:\n" + "\n".join(lines)

    eq_block = ""
    if equations:
        lines = [f"  LaTeX: {eq.get('text', '')}\n  Description: {eq.get('analysis_text', '')[:180]}"
                 for eq in equations]
        eq_block = "EQUATIONS (render with MathJax):\n" + "\n\n".join(lines)

    tbl_block = ""
    if tables:
        tbl_block = "TABLE DATA (JSON):\n" + json.dumps(tables, ensure_ascii=False, indent=2)

    content_block = "\n\n".join(filter(None, [imgs_block, eq_block, tbl_block]))
    bullets = "\n".join(f"- {p}" for p in points)

    return f"""Generate a complete {template.name}-template HTML slide.

LAYOUT TYPE : {layout}
SECTION     : {sec_num}
PAGE        : {page_label}
TITLE       : {title}
PURPOSE     : {purpose}

CONTENT POINTS:
{bullets}

{content_block}

─── CSS COLOUR VARIABLES ───
{color_vars}

─── CSS SKELETON ───
{css_skel}

─── DECORATIVE SHELL ───
{shell}

─── TASK ───
Produce a complete <!DOCTYPE html> document (960×540, standalone).
• Paste the shell snippet verbatim inside <div class="slide">.
• Add content HTML for layout "{layout}" after the shell.
• For equations: add MathJax script tags.
• For images: use exactly the provided src paths.
• Return ONLY the HTML document — no markdown, no explanation.
"""


def _write_viewer(output_dir: Path, files: List[Path]):
    links = "\n".join(f'<li><a href="{f.name}" target="preview">{f.stem}</a></li>' for f in files)
    first = files[0].name if files else ""
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Slide Viewer</title>
<style>
  body{{margin:0;display:flex;font-family:sans-serif;font-size:13px;}}
  nav{{width:260px;min-height:100vh;background:#2B4663;padding:12px;overflow-y:auto;}}
  nav a{{display:block;color:#B9CAE1;padding:5px 4px;text-decoration:none;}}
  nav a:hover{{color:#fff;}}
  iframe{{flex:1;border:none;height:100vh;}}
</style></head>
<body>
  <nav><ul style="list-style:none;padding:0;margin:0">{links}</ul></nav>
  <iframe name="preview" src="{first}"></iframe>
</body></html>"""
    (output_dir / "_viewer.html").write_text(html, encoding="utf-8")


# ── Renderer class ────────────────────────────────────────────────────────────

class SlideRenderer:
    """Template-agnostic HTML slide renderer backed by Dify LLM (llm_id=4)."""

    def __init__(self, template_name: str = "BIT",
                 input_json: Optional[Path] = None,
                 output_dir: Optional[Path] = None,
                 images_dir: Optional[Path] = None,
                 assets_dir: Optional[Path] = None,
                 image_src_prefix: Optional[str] = None):
        self.template = get_template(template_name)
        self.client = get_client()
        self.input_json = input_json or get_output_path(OUTPUT_FILES["enhanced_slides"])
        self.output_dir = output_dir or (_DEFAULT_OUTPUT_BASE / template_name)
        self.images_dir = images_dir or get_output_path("images")
        self.assets_dir = assets_dir or (_ASSETS_BASE / template_name)
        self.image_src_prefix = image_src_prefix

    def render_slide(self, slide: dict, index: int) -> Path:
        """Render one slide to HTML. Retries up to 3 times."""
        layout = _detect_layout(slide, self.template.role_to_layout)
        sec_num = _section_num(slide.get("section_name", "?"))
        title = slide["slide_title"]
        slug = _slugify(title)
        filename = f"{index:02d}_{layout}_{slug}.html"
        out_path = self.output_dir / filename

        # Copy template assets (logo, etc.) to the slide output dir so they
        # resolve as simple filenames relative to the HTML file.
        self.output_dir.mkdir(parents=True, exist_ok=True)
        assets = {}
        for name, fname in self.template.asset_filenames.items():
            src = self.assets_dir / fname
            if src.exists():
                dst = self.output_dir / fname
                if not dst.exists():
                    shutil.copy2(src, dst)
                assets[name] = fname   # just the filename — same directory
            else:
                assets[name] = fname

        img_base = self._resolve_img_prefix()
        page_label = f"Page {index + 1}"
        prompt = _build_prompt(slide, layout, sec_num, page_label, assets, img_base, self.template)

        logger.info(f"{TAG} [{index:02d}] layout={layout}  title={title[:55]}")

        html_text = None
        for attempt in range(3):
            try:
                result = self.client.run(
                    settings.LLM_ID_SLIDE_GEN, prompt,
                    tag=f"slide_{index:02d}_{layout}_{slug}",
                    metadata={
                        "step": 7,
                        "slide_id": slide.get("slide_id"),
                        "slide_title": slide.get("slide_title"),
                        "layout": layout,
                        "section_name": slide.get("section_name", ""),
                    }
                )
                html_text = extract_html_output(result)
                break
            except Exception as e:
                wait = 5 * (attempt + 1)
                logger.warning(f"{TAG} attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(wait)

        if html_text is None:
            raise RuntimeError(f"Slide {index} failed after 3 attempts")

        html_text = _strip_fences(html_text)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_text, encoding="utf-8")
        logger.info(f"{TAG} saved: {out_path}")
        return out_path

    def generate_all(self, slide_id: Optional[int] = None,
                     index: Optional[int] = None,
                     delay: float = 1.0) -> List[Path]:
        """Render all (or filtered) slides from the input JSON."""
        with self.input_json.open(encoding="utf-8") as f:
            data = json.load(f)
        all_slides = data["slides"]

        if slide_id is not None:
            # Build a list of (original_seq, slide) so the filename uses the real position
            pairs = [(i, s) for i, s in enumerate(all_slides) if s.get("slide_id") == slide_id]
            if not pairs:
                raise ValueError(f"No slide with slide_id={slide_id}")
        elif index is not None:
            pairs = [(index, all_slides[index])]
        else:
            pairs = list(enumerate(all_slides))

        slides = [s for _, s in pairs]
        logger.info(f"{TAG} template={self.template.name} slides={len(pairs)} → {self.output_dir}")

        generated = []
        for i, (seq, slide) in enumerate(pairs):
            out = self.render_slide(slide, seq)
            generated.append(out)
            if i < len(pairs) - 1:
                time.sleep(delay)

        if generated:
            _write_viewer(self.output_dir, generated)

        logger.info(f"{TAG} done: {len(generated)} file(s)")
        return generated

    def _asset_rel(self, filename, from_dir):
        """Return relative or absolute path to a template asset file (legacy)."""
        asset = self.assets_dir / filename
        if asset.exists():
            try:
                return os.path.relpath(asset, from_dir).replace("\\", "/")
            except ValueError:
                return str(asset).replace("\\", "/")
        return filename

    def _resolve_img_prefix(self) -> str:
        """Return absolute HTTP root-relative URL prefix for paper images.

        Images are served at /outputs/<paper>/images/ by the FastAPI static mount.
        If image_src_prefix is configured in settings, use that.
        Otherwise, derive it from the images_dir relative to the backend root.
        """
        configured = (self.image_src_prefix or settings.SLIDE_IMAGE_SRC_PREFIX or "").strip()
        if configured:
            return configured.rstrip("/")
        # Compute URL-relative path: images_dir relative to BASE_DIR maps to the
        # /downloads/ static mount.
        try:
            rel = Path(self.images_dir).relative_to(settings.BASE_DIR)
            return "/" + str(rel).replace("\\", "/")
        except ValueError:
            return str(self.images_dir).replace("\\", "/")


# ── CLI entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate HTML slides from enhanced outline")
    parser.add_argument("--json", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--template", default="BIT")
    parser.add_argument("--slide-id", type=int, default=None)
    parser.add_argument("--index", type=int, default=None)
    parser.add_argument("--delay", type=float, default=1.0)
    args = parser.parse_args()

    renderer = SlideRenderer(
        template_name=args.template,
        input_json=Path(args.json) if args.json else None,
        output_dir=Path(args.output_dir) if args.output_dir else None,
    )
    renderer.generate_all(slide_id=args.slide_id, index=args.index, delay=args.delay)
