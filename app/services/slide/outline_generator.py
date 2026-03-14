"""LLM-based outline generation: one PPT outline per document section."""

import json
import time
from typing import Dict, List

from app.core.config import settings, save_output, OUTPUT_FILES
from app.core.logger import logger
from app.services.client.llm_client import get_client, extract_json_output

TAG = "[OUTLINE]"


# ── Public API ────────────────────────────────────────────────────────────────

def generate(parse_result: Dict, visual_analysis: List[Dict]) -> Dict:
    """Generate PPT outline for each section via LLM (llm_id=3). Saves output."""
    element_map = _build_element_map(visual_analysis)
    sections_data = _prepare_sections(parse_result, element_map)

    if not sections_data:
        result = {"sections": [], "statistics": {"total": 0, "success": 0, "failed": 0}}
        save_output(result, OUTPUT_FILES["section_outlines"])
        return result

    client = get_client()
    results = []
    total = len(sections_data)

    for idx, data in enumerate(sections_data, 1):
        name = data["section_name"]
        logger.info(f"{TAG} [{idx}/{total}] {name[:40]}")
        try:
            query = json.dumps(data, ensure_ascii=False)
            raw = client.run(settings.LLM_ID_OUTLINE, query, tag=f"outline_{idx}")
            raw_result = extract_json_output(raw)
            results.append({"section_name": name, "raw_result": raw_result})
        except Exception as e:
            logger.error(f"{TAG} [{idx}/{total}] failed: {e}")
            results.append({"section_name": name, "raw_result": None, "error": str(e)})

        if idx < total:
            time.sleep(1)

    success = sum(1 for r in results if not r.get("error"))
    outline = {
        "sections": results,
        "statistics": {"total": total, "success": success, "failed": total - success},
    }
    save_output(outline, OUTPUT_FILES["section_outlines"])
    logger.info(f"{TAG} saved to {OUTPUT_FILES['section_outlines']}: {success}/{total}")
    return outline


# ── Internal helpers ──────────────────────────────────────────────────────────

def _build_element_map(visual_analysis: List[Dict]) -> Dict[str, Dict[int, str]]:
    """Map element type+id -> analysis_text."""
    result = {"images": {}, "tables": {}, "equations": {}}
    if not isinstance(visual_analysis, list):
        return result
    type_map = {"image": "images", "table": "tables", "equation": "equations"}
    for item in visual_analysis:
        elem = item.get("element", {})
        analysis = item.get("analysis", {})
        etype, eid = elem.get("type"), elem.get("id")
        if analysis and eid is not None and etype in type_map:
            result[type_map[etype]][eid] = analysis.get("analysis_text", "")
    return result


def _extract_refs(section: Dict, element_map: Dict) -> Dict[str, List[Dict]]:
    refs = {"images": [], "tables": [], "equations": []}
    for src_key, dst_key in [("fig_refs", "images"), ("table_refs", "tables"), ("formula_refs", "equations")]:
        for ref in section.get(src_key, []):
            rid = ref.get("id")
            if rid is not None and rid in element_map[dst_key]:
                refs[dst_key].append({"id": rid, "analyze_text": element_map[dst_key][rid]})
    return refs


def _prepare_sections(parse_result: Dict, element_map: Dict) -> List[Dict]:
    """Prepare per-section input data for the outline LLM."""
    sections = parse_result.get("sections", [])
    abstract = ""
    for sec in sections:
        if "abstract" in sec.get("name", "").lower():
            abstract = sec.get("content", "")
            break

    results = []
    for idx, sec in enumerate(sections):
        name = sec.get("name", "")
        if idx == 0 or "abstract" in name.lower():
            continue
        refs = _extract_refs(sec, element_map)
        results.append({
            "abstract": abstract, "section_name": name,
            "content": sec.get("content", ""), "refs": refs,
        })
    logger.info(f"{TAG} prepared {len(results)} sections for outline")
    return results
