"""Visual element extraction and LLM-based analysis (images, tables, equations)."""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import settings, save_output, OUTPUT_FILES
from app.core.logger import logger
from app.services.client.llm_client import get_client, extract_json_output

TAG = "[VISUAL]"


# ── Public API ────────────────────────────────────────────────────────────────

def extract_elements(parse_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract visual elements from all sections in the parsed document."""
    sections = parse_result.get("sections", [])

    abstract = ""
    for sec in sections:
        if sec.get("name", "").lower() in ("abstract", "摘要"):
            abstract = sec.get("content", "")
            break

    results = []
    for sec in sections:
        name = sec.get("name", "")
        content = sec.get("content", "")
        path = sec.get("path", "")

        for fig in sec.get("fig_refs", []):
            results.append(_make_entry(
                abstract, "image", fig, content, name, path,
                img_path=fig.get("img_path", ""), caption=fig.get("caption", ""),
            ))
        for tbl in sec.get("table_refs", []):
            results.append(_make_entry(
                abstract, "table", tbl, content, name, path,
                img_path=tbl.get("img_path", ""), caption=tbl.get("caption", ""),
                body=tbl.get("body", ""),
            ))
        for eq in sec.get("formula_refs", []):
            results.append(_make_entry(
                abstract, "equation", eq, content, name, path,
                img_path=eq.get("img_path", ""), text=eq.get("text", ""),
                text_format=eq.get("text_format", "latex"),
            ))

    logger.info(f"{TAG} extracted {len(results)} elements")
    return results


def analyze_elements(elements: List[Dict], base_path: Optional[Path] = None) -> List[Dict]:
    """Analyze each visual element via LLM (llm_id=2)."""
    if not elements:
        return []

    client = get_client()
    logger.info(f"{TAG} analyzing {len(elements)} elements")

    # Batch upload images
    file_ids = _upload_images(client, elements, base_path)

    results = []
    for idx, elem in enumerate(elements, 1):
        info = elem.get("element", {})
        etype, eid = info.get("type"), info.get("id")
        img_path = info.get("img_path", "")
        logger.info(f"{TAG} [{idx}/{len(elements)}] {etype}-{eid}")

        file_id = None
        if img_path:
            full = str((base_path / img_path) if base_path else Path(img_path))
            file_id = file_ids.get(full)

        # Build prompt
        info_copy = info.copy()
        info_copy["img_path"] = file_id or ""
        prompt = json.dumps({
            "abstract": elem.get("abstract", ""),
            "element": info_copy,
            "local_context": elem.get("local_context", ""),
            "section_content": elem.get("section_content", ""),
        }, ensure_ascii=False)

        try:
            extra = None
            if file_id:
                extra = {"images": [
                    {"transfer_method": "local_file", "upload_file_id": file_id, "type": "image"}
                ]}
            raw = client.run(
                settings.LLM_ID_VISUAL_ANALYSIS, prompt,
                extra=extra, tag=f"visual_{etype}_{eid}",
                metadata={
                    "step": 2,
                    "element_type": etype,
                    "element_id": eid,
                    "section_name": elem.get("section_name", ""),
                }
            )
            answer = extract_json_output(raw)
            if answer:
                results.append({
                    **elem,
                    "analysis": {
                        "element_id": answer.get("element_id", eid),
                        "element_type": answer.get("element_type", etype),
                        "analysis_text": answer.get("analysis_text", ""),
                    },
                })
            else:
                results.append({**elem, "analysis": None, "error": "Empty response"})
        except Exception as e:
            logger.error(f"{TAG} {etype}-{eid}: {e}")
            results.append({**elem, "analysis": None, "error": str(e)})

        if idx < len(elements):
            time.sleep(1)

    success = sum(1 for r in results if r.get("analysis"))
    logger.info(f"{TAG} done: success={success}, failed={len(results) - success}")
    return results


def run(parse_result: Dict, base_path: Optional[Path] = None) -> List[Dict]:
    """Full pipeline: extract + analyze + save."""
    elements = extract_elements(parse_result)
    analysis = analyze_elements(elements, base_path)
    save_output(analysis, OUTPUT_FILES["visual_analysis"])
    logger.info(f"{TAG} saved to {OUTPUT_FILES['visual_analysis']}")
    return analysis


# ── Internal helpers ──────────────────────────────────────────────────────────

def _make_entry(abstract, etype, ref, content, section_name, section_path, **extra):
    elem = {"type": etype, "id": ref.get("id")}
    elem.update(extra)
    return {
        "abstract": abstract,
        "element": elem,
        "local_context": _get_context(content, ref.get("id"), etype),
        "section_content": content,
        "section_name": section_name,
        "section_path": section_path,
    }


def _get_context(content: str, elem_id: int, elem_type: str, window: int = 200) -> str:
    patterns = {
        "image": rf"(?:Figure|Fig\.|图)\s*{elem_id}\b",
        "table": rf"(?:Table|Tab\.|表)\s*{elem_id}\b",
    }
    pattern = patterns.get(elem_type)
    if not pattern:
        return ""
    m = re.search(pattern, content, re.IGNORECASE)
    if not m:
        return ""
    start = max(0, m.start() - window)
    end = min(len(content), m.start() + window)
    ctx = content[start:end].strip()
    return ("..." if start > 0 else "") + ctx + ("..." if end < len(content) else "")


def _upload_images(client, elements, base_path):
    to_upload = []
    for elem in elements:
        img_path = elem.get("element", {}).get("img_path", "")
        if not img_path:
            continue
        full = (base_path / img_path) if base_path else Path(img_path)
        if full.exists():
            to_upload.append(str(full))

    file_ids = {}
    if to_upload:
        logger.info(f"{TAG} uploading {len(to_upload)} files")
        for r in client.upload_batch(to_upload):
            if r.get("success"):
                file_ids[r["file_path"]] = r["file_id"]
    return file_ids
