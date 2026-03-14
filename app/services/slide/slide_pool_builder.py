"""Build complete slide pool from outline + parse result + visual analysis."""

import json
import re
from typing import Any, Dict, List

from app.core.config import save_output, OUTPUT_FILES
from app.core.logger import logger

TAG = "[POOL]"


# ── Public API ────────────────────────────────────────────────────────────────

def build(outline_result: Dict, parse_result: Dict, visual_analysis: List[Dict]) -> Dict:
    """Build the full slide pool from all sections. Saves output."""
    all_slides = []
    for section in outline_result.get("sections", []):
        if section.get("error"):
            continue
        all_slides.extend(_build_section(section, parse_result, visual_analysis))

    # Assign global sequential IDs
    for gid, slide in enumerate(all_slides):
        slide["slide_id"] = gid

    result = {
        "slides": all_slides,
        "statistics": {
            "total_slides": len(all_slides),
            "total_sections": len(outline_result.get("sections", [])),
        },
    }
    save_output(result, OUTPUT_FILES["slide_pool"])
    logger.info(f"{TAG} total: {len(all_slides)} slides → {OUTPUT_FILES['slide_pool']}")
    return result


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_section(outline_section: Dict, parse_result: Dict,
                   visual_analysis: List[Dict]) -> List[Dict]:
    section_name = outline_section.get("section_name", "")
    raw_result = _normalize(outline_section.get("raw_result", {}))
    if not raw_result or outline_section.get("error"):
        return []

    ppt_outline = raw_result.get("ppt_outline", [])
    if not ppt_outline:
        return []

    slides = []
    for si, sd in enumerate(ppt_outline):
        vrefs = _build_visual_refs(sd.get("visual_refs", {}), parse_result, visual_analysis)
        slides.append({
            "slide_id": si,
            "slide_title": sd.get("slide_title", ""),
            "section_name": section_name,
            "role": sd.get("role", ""),
            "slide_purpose": sd.get("slide_purpose", ""),
            "content_points": sd.get("content_points", []),
            "visual_refs": vrefs,
        })
    logger.info(f"{TAG} section '{section_name}': {len(slides)} slides")
    return slides


def _build_visual_refs(visual_ids: Dict, parse_result: Dict,
                       visual_analysis: List[Dict]) -> Dict:
    refs = {"images": [], "tables": [], "equations": []}

    for img_id in visual_ids.get("images", []):
        elem = _find_element(img_id, "image", parse_result)
        if elem:
            refs["images"].append({
                "type": "image", "id": img_id,
                "img_path": elem.get("img_path", ""),
                "caption": elem.get("caption", ""),
                "analysis_text": _find_analysis(img_id, "image", visual_analysis),
            })
    for tbl_id in visual_ids.get("tables", []):
        elem = _find_element(tbl_id, "table", parse_result)
        if elem:
            refs["tables"].append({
                "type": "table", "id": tbl_id,
                "img_path": elem.get("img_path", ""),
                "caption": elem.get("caption", ""),
                "body": elem.get("body", ""),
                "analysis_text": _find_analysis(tbl_id, "table", visual_analysis),
            })
    for eq_id in visual_ids.get("equations", []):
        elem = _find_element(eq_id, "equation", parse_result)
        if elem:
            refs["equations"].append({
                "type": "equation", "id": eq_id,
                "img_path": elem.get("img_path", ""),
                "text": elem.get("text", ""),
                "text_format": elem.get("text_format", "latex"),
                "analysis_text": _find_analysis(eq_id, "equation", visual_analysis),
            })
    return refs


def _find_element(element_id: int, element_type: str, parse_result: Dict) -> Dict:
    ref_map = {"image": "fig_refs", "table": "table_refs", "equation": "formula_refs"}
    ref_key = ref_map.get(element_type)
    if not ref_key:
        return {}
    for sec in parse_result.get("sections", []):
        for ref in sec.get(ref_key, []):
            if ref.get("id") == element_id:
                return ref
    return {}


def _find_analysis(element_id: int, element_type: str, visual_analysis: List[Dict]) -> str:
    for item in visual_analysis:
        elem = item.get("element", {})
        if elem.get("id") == element_id and elem.get("type") == element_type:
            return (item.get("analysis") or {}).get("analysis_text", "")
    return ""


def _normalize(raw_result: Any) -> Dict:
    """Normalize raw_result into a dict, handling JSON-in-text and markdown fences."""
    if isinstance(raw_result, dict):
        if isinstance(raw_result.get("ppt_outline"), list):
            return raw_result
        text_val = raw_result.get("text")
        if not isinstance(text_val, str):
            return raw_result
        candidate = text_val
    elif isinstance(raw_result, str):
        candidate = raw_result
    else:
        return {}

    s = candidate.strip()
    fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", s, re.IGNORECASE)
    if fenced:
        s = fenced.group(1).strip()
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        i, j = s.find("{"), s.rfind("}")
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except Exception:
                pass
    return raw_result if isinstance(raw_result, dict) else {}
