"""Visual enhancement: enrich text-only slides with AI images or CSS strategies.

For each text_only slide:
  IMAGE → generate concept diagram via Gemini, rewrite bullets via Dify
  CSS   → assign a richer layout strategy (method_cards, highlight_grid, etc.)
"""

import json
import re
import time
from pathlib import Path
from typing import Optional

from app.core.config import settings, save_output, OUTPUT_FILES, get_output_path
from app.core.logger import logger
from app.services.client.llm_client import get_client, generate_image, extract_json_output

TAG = "[ENHANCE]"

# ── Role → image type mapping ────────────────────────────────────────────────

_IMAGE_ROLES: dict[str, str] = {
    "hook_context":       "concept_diagram",
    "gap_limitations":    "comparison_chart",
    "problem_definition": "directed_graph",
    "insight_thesis":     "framework_diagram",
    "method_overview":    "flowchart",
    "related_work":       "timeline_diagram",
    "takeaways":          "infographic",
}

# ── Role → CSS strategy mapping ──────────────────────────────────────────────

_CSS_STRATEGY: dict[str, str] = {
    "related_work":      "method_cards",
    "experiment_setup":  "setup_timeline",
    "theoretical":       "structured_bullets",
    "takeaways":         "highlight_grid",
    "analysis_ablation": "structured_bullets",
}
_DEFAULT_CSS = "structured_bullets"

_MATH_RE = re.compile(r"[=∈→←∀∃∑∏\\\$_{}^]")


# ── Classification ───────────────────────────────────────────────────────────

def classify(slide: dict) -> dict:
    """Decide enhancement strategy for one slide."""
    role = slide.get("role", "")
    points = slide.get("content_points", [])
    visual = slide.get("visual_refs", {})

    if visual.get("images") or visual.get("tables"):
        return {"strategy": "skip", "reason": "already has visuals"}
    if visual.get("equations"):
        return {"strategy": "skip", "reason": "equation slide"}
    if len(points) <= 2:
        return {"strategy": "css", "css_strategy": _CSS_STRATEGY.get(role, _DEFAULT_CSS),
                "reason": "too few bullets"}
    if _is_math_heavy(points):
        return {"strategy": "css", "css_strategy": _CSS_STRATEGY.get(role, _DEFAULT_CSS),
                "reason": "math-heavy"}
    if role in ("experiment_setup", "analysis_ablation", "theoretical"):
        return {"strategy": "css", "css_strategy": _CSS_STRATEGY.get(role, _DEFAULT_CSS),
                "reason": "analytical role"}
    if role in _IMAGE_ROLES:
        image_type = _IMAGE_ROLES[role]
        return {"strategy": "image", "image_type": image_type,
                "image_prompt": _build_image_prompt(slide, image_type)}
    return {"strategy": "css", "css_strategy": _DEFAULT_CSS, "reason": "default"}


def _is_math_heavy(points: list[str]) -> bool:
    if not points:
        return False
    return sum(1 for p in points if _MATH_RE.search(p)) / len(points) >= 0.5


# ── Main service ─────────────────────────────────────────────────────────────

class VisualEnhancer:

    def __init__(self, outline_path: Optional[str | Path] = None,
                 images_output_dir: Optional[str | Path] = None,
                 images_src_prefix: Optional[str] = None):
        self.outline_path = Path(outline_path) if outline_path else \
            get_output_path(OUTPUT_FILES["compressed_slides"])
        self.images_dir = Path(images_output_dir) if images_output_dir else \
            Path(settings.BASE_DIR) / settings.SLIDE_GENERATED_IMAGES_DIR
        self.images_src_prefix = images_src_prefix or settings.SLIDE_IMAGE_SRC_PREFIX or \
            str(self.images_dir).replace("\\", "/")
        self.client = get_client()

    def run(self, slide_ids: Optional[list[int]] = None, dry_run: bool = False,
            delay: float = 2.0) -> dict:
        """Process all or selected slides."""
        data = json.loads(self.outline_path.read_text(encoding="utf-8"))
        slides = data["slides"]
        candidates = [s for s in slides if slide_ids is None or s.get("slide_id") in slide_ids]

        report = {}
        modified = False

        for slide in candidates:
            sid = slide.get("slide_id", "?")
            decision = classify(slide)
            report[sid] = decision

            logger.info(f"{TAG} [{sid:02}] role={slide.get('role', '?'):<22} "
                        f"strategy={decision['strategy']}")

            if dry_run or decision["strategy"] == "skip":
                continue

            if decision["strategy"] == "image":
                try:
                    img_entry, rewritten = self._enhance_image(slide, decision, delay)
                    slide.setdefault("visual_refs", {})["images"] = [img_entry]
                    slide["content_points"] = rewritten
                    slide.setdefault("visual_enhance", {}).update({
                        "strategy": "image", "image_type": decision["image_type"],
                    })
                    modified = True
                except Exception as e:
                    logger.error(f"{TAG} slide {sid} image failed: {e}")

            elif decision["strategy"] == "css":
                css = decision.get("css_strategy", _DEFAULT_CSS)
                slide.setdefault("visual_enhance", {}).update({
                    "strategy": "css", "css_strategy": css,
                    "reason": decision.get("reason", ""),
                })
                modified = True

        if not dry_run and modified:
            self._save(data)

        return report

    def _enhance_image(self, slide, decision, delay):
        image_type = decision["image_type"]
        image_prompt = decision["image_prompt"]

        logger.info(f"{TAG} generating image: {image_type}")
        img_bytes, ext = generate_image(image_prompt, aspect_ratio="4:3")

        self.images_dir.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[\W]+", "_", slide.get("slide_title", "slide"))[:32].lower()
        fname = f"{slug}.{ext}"
        (self.images_dir / fname).write_bytes(img_bytes)

        img_entry = {
            "type": "image", "id": 1, "img_path": fname,
            "img_src_prefix": self.images_src_prefix,
            "caption": "",
            "analysis_text": f"AI-generated {image_type} diagram.",
            "generated": True,
        }

        time.sleep(delay)

        # Rewrite bullets
        desc = f"AI-generated {image_type} covering: " + \
               "; ".join(slide.get("content_points", [])[:3])
        rw_prompt = _build_rewrite_prompt(slide, image_type, desc)
        logger.info(f"{TAG} rewriting bullets")
        rw_result = self.client.run(settings.LLM_ID_TEXT_REWRITE, rw_prompt, tag="text_rewrite")
        rewritten = _parse_rewrite_output(rw_result)
        if not rewritten:
            rewritten = slide.get("content_points", [])[:3]
            logger.warning(f"{TAG} rewrite returned no valid JSON, using truncated originals")

        return img_entry, rewritten

    def run_strategy(self) -> dict:
        """Pass 1 (offline): Classify all slides and write visual_enhance strategy fields.

        No image generation, no LLM calls. Reads from compressed_slides and saves
        06_enhanced_slides.json with each slide's ``visual_enhance`` field filled.
        For image-strategy slides the field also carries ``generated: False`` as a
        reminder that the actual image has not yet been produced.
        """
        data = json.loads(self.outline_path.read_text(encoding="utf-8"))
        slides = data["slides"]
        report = {}

        for slide in slides:
            sid = slide.get("slide_id", "?")
            decision = classify(slide)
            report[sid] = decision

            logger.info(f"{TAG} [strategy] [{sid:02}] role={slide.get('role', '?'):<22} "
                        f"strategy={decision['strategy']}")

            if decision["strategy"] == "skip":
                slide.setdefault("visual_enhance", {})["strategy"] = "skip"
                continue

            if decision["strategy"] == "image":
                slide.setdefault("visual_enhance", {}).update({
                    "strategy": "image",
                    "image_type": decision["image_type"],
                    "image_prompt": decision.get("image_prompt", ""),
                    "generated": False,
                })
            elif decision["strategy"] == "css":
                css = decision.get("css_strategy", _DEFAULT_CSS)
                slide.setdefault("visual_enhance", {}).update({
                    "strategy": "css",
                    "css_strategy": css,
                    "reason": decision.get("reason", ""),
                })

        self._save(data)
        return {"slides": slides, "report": report}

    def run_images(self, slide_ids: Optional[list[int]] = None, delay: float = 2.0) -> dict:
        """Pass 2 (online): Generate AI images for slides with strategy=='image'.

        Reads from the already-saved 06_enhanced_slides.json (produced by
        run_strategy), generates an image for each un-generated image-strategy
        slide, and overwrites the file with the update.
        """
        enhanced_path = get_output_path(OUTPUT_FILES["enhanced_slides"])
        if not enhanced_path.exists():
            raise FileNotFoundError("Run run_strategy() first to produce enhanced_slides.")

        data = json.loads(enhanced_path.read_text(encoding="utf-8"))
        slides = data["slides"]

        candidates = [
            s for s in slides
            if (slide_ids is None or s.get("slide_id") in slide_ids)
            and s.get("visual_enhance", {}).get("strategy") == "image"
            and not s.get("visual_enhance", {}).get("generated", False)
        ]

        logger.info(f"{TAG} [images] {len(candidates)} slide(s) to generate")
        report = {}

        for slide in candidates:
            sid = slide.get("slide_id", "?")
            enhance = slide.get("visual_enhance", {})
            decision = {
                "strategy": "image",
                "image_type": enhance.get("image_type", "concept_diagram"),
                "image_prompt": enhance.get("image_prompt") or _build_image_prompt(
                    slide, enhance.get("image_type", "concept_diagram")
                ),
            }
            try:
                img_entry, rewritten = self._enhance_image(slide, decision, delay)
                slide.setdefault("visual_refs", {})["images"] = [img_entry]
                slide["content_points"] = rewritten
                slide["visual_enhance"]["generated"] = True
                report[sid] = {"ok": True, "img_path": img_entry["img_path"]}
                logger.info(f"{TAG} [images] [{sid:02}] generated: {img_entry['img_path']}")
            except Exception as e:
                report[sid] = {"ok": False, "error": str(e)}
                logger.error(f"{TAG} [images] [{sid:02}] failed: {e}")

        self._save_enhanced(data)
        return {"generated": len([v for v in report.values() if v.get("ok")]), "report": report}

    def _save(self, data):
        output_path = get_output_path(OUTPUT_FILES["enhanced_slides"])
        output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"{TAG} saved to {output_path}")

    def _save_enhanced(self, data):
        """Save back to enhanced_slides (used after run_images)."""
        self._save(data)


# ── Public entry ─────────────────────────────────────────────────────────────

def run(outline_path: str = None, slide_ids: list[int] = None,
        dry_run: bool = False) -> dict:
    """Run full visual enhancement pass (strategy + image generation)."""
    enhancer = VisualEnhancer(outline_path=outline_path)
    return enhancer.run(slide_ids=slide_ids, dry_run=dry_run)


def run_strategy(outline_path: str = None) -> dict:
    """Classify slides and write strategy fields only (no image generation)."""
    enhancer = VisualEnhancer(outline_path=outline_path)
    return enhancer.run_strategy()


def run_images(slide_ids: list[int] = None, delay: float = 2.0) -> dict:
    """Generate AI images for slides that have strategy=='image' but not yet generated."""
    enhancer = VisualEnhancer()
    return enhancer.run_images(slide_ids=slide_ids, delay=delay)


# ── Prompt builders ──────────────────────────────────────────────────────────

def _build_image_prompt(slide: dict, image_type: str) -> str:
    title = slide.get("slide_title", "")
    purpose = slide.get("slide_purpose", "")
    role = slide.get("role", "")
    concepts = "; ".join(slide.get("content_points", []))

    return f"""TASK: Generate a schematic diagram for an academic presentation slide.

SLIDE TITLE   : {title}
SLIDE PURPOSE : {purpose}
SLIDE ROLE    : {role}
KEY CONCEPTS  : {concepts}

REQUIREMENTS:
- Clean academic style; white or light grey background (#F9FAFB)
- Flat vector design; BIT palette: Primary #2B4663, Secondary #5C7885, Accent #B9CAE1
- No photographs — use geometric shapes, arrows, labels, nodes
- Canvas: 480×420 px (embedded in 960×540 slide)
- English labels only, ≤5 words per node
- Visual type: {image_type}

{_image_type_guide(image_type)}

OUTPUT: Return ONLY the image."""


def _image_type_guide(t: str) -> str:
    guides = {
        "comparison_chart": "Side-by-side two-column layout comparing old vs. new approaches.",
        "directed_graph": "Nodes as rounded rectangles connected by directed arrows with labels.",
        "concept_diagram": "Central concept connected to 3–5 surrounding attribute bubbles.",
        "framework_diagram": "Modular block diagram with input→process→output flow.",
        "flowchart": "Top-to-bottom or left-to-right flow with process boxes and arrows.",
        "timeline_diagram": "Horizontal timeline with labelled milestone nodes.",
        "infographic": "2–4 highlight panels in a grid with bold key phrases.",
    }
    return guides.get(t, "An appropriate schematic diagram for the topic.")


def _build_rewrite_prompt(slide, image_type, image_desc):
    points = slide.get("content_points", [])
    n = len(points)
    target = 2 if n <= 4 else 3
    original = "\n".join(f"{i+1}. {p}" for i, p in enumerate(points))
    return f"""A slide displays both a generated diagram AND text bullets.
The diagram covers the structural aspects.

Rewrite bullets to COMPLEMENT (not repeat) the diagram.

SLIDE PURPOSE  : {slide.get('slide_purpose', '')}
DIAGRAM TYPE   : {image_type}
DIAGRAM COVERS : {image_desc}

ORIGINAL BULLETS ({n}):
{original}

Output exactly {target} concise English bullet strings as a JSON array.
Example: ["First insight.", "Second insight."]"""


def _parse_rewrite_output(result: dict) -> list[str]:
    outputs = result.get("data", {}).get("outputs", {})
    for key in ("text", "output", "result"):
        val = outputs.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        try:
            arr = json.loads(val.strip())
            if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
                return arr
        except json.JSONDecodeError:
            pass
        m = re.search(r"\[.*?\]", val, re.DOTALL)
        if m:
            try:
                arr = json.loads(m.group())
                if isinstance(arr, list):
                    return [str(x) for x in arr]
            except json.JSONDecodeError:
                pass
    return []


# ── CLI entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Visual enhancement pass")
    parser.add_argument("--outline", default=None)
    parser.add_argument("--slide-ids", nargs="*", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(outline_path=args.outline, slide_ids=args.slide_ids, dry_run=args.dry_run)
