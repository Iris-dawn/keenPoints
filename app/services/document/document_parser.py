"""Markdown document parser: parse MinerU output into structured sections."""

import re
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

from app.core.config import settings, save_output, OUTPUT_FILES
from app.core.logger import logger

TAG = "[PARSE]"

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^\s\)]+)(?:\s+\"([^\"]*)\")?\)")
_NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
_FORMULA_RE = re.compile(r"\$\$([^\$]+?)\$\$", re.DOTALL)
_TABLE_RE = re.compile(r"<table[^>]*>(.*?)</table>", re.DOTALL | re.IGNORECASE)


# ── Public API ────────────────────────────────────────────────────────────────

def parse(file_path: str, json_path: Optional[str] = None) -> Dict[str, Any]:
    """Parse a Markdown file (+ optional content_list.json) into sections."""
    md_path = Path(file_path)
    if not md_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    content = md_path.read_text(encoding="utf-8")

    # Try to locate JSON element data
    json_data, json_file = None, None
    if json_path:
        json_file = Path(json_path)
        json_data = _load_json(json_file)
    else:
        candidates = list(md_path.parent.glob("*content_list.json"))
        if candidates:
            json_file = candidates[0]
            json_data = _load_json(json_file)

    return _parse_content(content, md_path.parent, json_data)


def parse_and_save(file_path: str, json_path: Optional[str] = None) -> Dict[str, Any]:
    """Parse and save result to outputs directory."""
    result = parse(file_path, json_path)
    path = save_output(result, OUTPUT_FILES["parsed_document"])
    logger.info(f"{TAG} saved to {path}")
    result["output_path"] = str(path)
    return result


# ── JSON element extraction ───────────────────────────────────────────────────

def _load_json(path: Path) -> Optional[Dict]:
    """Load content_list.json, extracting images/tables/equations."""
    if not path.exists():
        logger.warning(f"{TAG} json not found: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        images, tables, equations = [], [], []
        img_id = tbl_id = eq_id = 1
        for item in data:
            t = item.get("type")
            if t == "image":
                images.append({
                    "type": "image", "id": img_id,
                    "img_path": item.get("img_path", ""),
                    "caption": " ".join(item.get("image_caption", [])),
                })
                img_id += 1
            elif t == "table":
                tables.append({
                    "type": "table", "id": tbl_id,
                    "img_path": item.get("img_path", ""),
                    "caption": " ".join(item.get("table_caption", [])),
                    "body": item.get("table_body", ""),
                })
                tbl_id += 1
            elif t == "equation":
                equations.append({
                    "type": "equation", "id": eq_id,
                    "img_path": item.get("img_path", ""),
                    "text": item.get("text", ""),
                    "text_format": item.get("text_format", "latex"),
                })
                eq_id += 1
        logger.info(f"{TAG} json: img={len(images)}, tbl={len(tables)}, eq={len(equations)}")
        return {"images": images, "tables": tables, "equations": equations, "raw": data}
    except Exception as e:
        logger.error(f"{TAG} json load error: {e}")
        return None


# ── Content parsing ───────────────────────────────────────────────────────────

def _parse_content(content: str, base_path: Path, json_data: Optional[Dict]) -> Dict:
    headings = _extract_headings(content)
    if json_data:
        figures = json_data.get("images", [])
        tables = json_data.get("tables", [])
        formulas = json_data.get("equations", [])
        sections = _build_sections_from_json(json_data.get("raw", []), figures, tables, formulas)
    else:
        figures = _extract_figures(content, base_path)
        tables = _extract_tables(content)
        formulas = _extract_formulas(content)
        sections = _build_sections(content, headings, figures, tables, formulas)

    metadata = {
        "total_sections": len(sections),
        "total_figures": len(figures),
        "total_tables": len(tables),
        "total_formulas": len(formulas),
    }
    logger.info(f"{TAG} done: {metadata}")
    return {"sections": sections, "metadata": metadata}


def _extract_headings(content: str) -> List[Dict]:
    headings = []
    for m in _HEADING_RE.finditer(content):
        level = len(m.group(1))
        title = m.group(2).strip()
        num_match = _NUMBER_RE.match(title)
        if num_match:
            level = len(num_match.group(1).split("."))
        headings.append({"level": level, "title": title, "start": m.start(), "end": None})
    for i in range(len(headings)):
        headings[i]["end"] = headings[i + 1]["start"] if i < len(headings) - 1 else len(content)
    return headings


def _extract_figures(content: str, base_path: Path) -> List[Dict]:
    figures = []
    for idx, m in enumerate(_IMAGE_RE.finditer(content), 1):
        img_path = m.group(2)
        if base_path and not img_path.startswith(("http://", "https://")):
            full = base_path / img_path
            if full.exists():
                img_path = str(full)
        figures.append({
            "id": idx, "img_path": img_path,
            "caption": m.group(3) or m.group(1) or "", "alt": m.group(1) or "",
        })
    return figures


def _extract_tables(content: str) -> List[Dict]:
    tables = []
    for idx, m in enumerate(_TABLE_RE.finditer(content), 1):
        caption = ""
        before = content[:m.start()].split("\n")
        for line in reversed(before[-3:]):
            if re.search(r"(?:Table|Tab\.|表)\s*\d+", line, re.IGNORECASE):
                caption = line.strip()
                break
        tables.append({"id": idx, "caption": caption, "body": m.group(0), "img_path": None})
    return tables


def _extract_formulas(content: str) -> List[Dict]:
    return [
        {"id": idx, "type": "block", "text": f"$$\n{m.group(1).strip()}\n$$"}
        for idx, m in enumerate(_FORMULA_RE.finditer(content), 1)
    ]


# ── Section building ──────────────────────────────────────────────────────────

def _build_sections(content, headings, figures, tables, formulas):
    if not headings:
        return [{
            "name": "Document", "level": 0, "path": "Document",
            "content": content.strip(),
            "fig_refs": figures, "table_refs": tables, "formula_refs": formulas,
        }]

    sections = []
    path_stack = []
    for h in headings:
        text = content[h["start"]:h["end"]]
        pure = "\n".join(text.split("\n")[1:]).strip()
        while path_stack and path_stack[-1]["level"] >= h["level"]:
            path_stack.pop()
        path_stack.append({"name": h["title"], "level": h["level"]})
        sections.append({
            "name": h["title"], "level": h["level"],
            "path": " > ".join(p["name"] for p in path_stack),
            "content": pure,
            "fig_refs": _find_refs(figures, pure, "image"),
            "table_refs": _find_refs(tables, pure, "table"),
            "formula_refs": _find_refs(formulas, pure, "equation"),
        })
    return sections


def _build_sections_from_json(raw_data, figures, tables, formulas):
    if not raw_data:
        return []

    # Build element position index
    elem_pos = {}
    img_id = tbl_id = eq_id = 1
    for idx, item in enumerate(raw_data):
        t = item.get("type")
        if t == "image":
            elem_pos[f"image_{img_id}"] = idx
            img_id += 1
        elif t == "table":
            elem_pos[f"table_{tbl_id}"] = idx
            tbl_id += 1
        elif t == "equation":
            elem_pos[f"equation_{eq_id}"] = idx
            eq_id += 1

    sections = []
    current = None
    path_stack = []

    for idx, item in enumerate(raw_data):
        t = item.get("type")
        text = item.get("text", "").strip()
        if t == "text" and text:
            level = item.get("text_level", 0)
            if level > 0:
                if current:
                    sections.append(current)
                while path_stack and path_stack[-1]["level"] >= level:
                    path_stack.pop()
                path_stack.append({"name": text, "level": level})
                current = {
                    "name": text, "level": level,
                    "path": " > ".join(p["name"] for p in path_stack),
                    "content": "", "start_idx": idx,
                    "fig_refs": [], "table_refs": [], "formula_refs": [],
                }
            else:
                if current is None:
                    current = {
                        "name": "Document", "level": 0, "path": "Document",
                        "content": "", "start_idx": 0,
                        "fig_refs": [], "table_refs": [], "formula_refs": [],
                    }
                current["content"] += ("\n\n" if current["content"] else "") + text

    if current:
        sections.append(current)

    # Assign visual elements to sections by position
    for sec in sections:
        start = sec.get("start_idx", 0)
        end = min(
            [s.get("start_idx", len(raw_data))
             for s in sections if s.get("start_idx", 0) > start]
            or [len(raw_data)]
        )
        for fig in figures:
            pos = elem_pos.get(f"image_{fig['id']}")
            if pos is not None and start <= pos < end:
                sec["fig_refs"].append(fig)
        for tbl in tables:
            pos = elem_pos.get(f"table_{tbl['id']}")
            if pos is not None and start <= pos < end:
                sec["table_refs"].append(tbl)
        for eq in formulas:
            pos = elem_pos.get(f"equation_{eq['id']}")
            if pos is not None and start <= pos < end:
                sec["formula_refs"].append(eq)
        sec.pop("start_idx", None)

    return sections


def _find_refs(items, content, item_type):
    """Find elements referenced in content text."""
    found = []
    patterns = {
        "image": r"(?:Figure|Fig\.|图)\s*{}\b",
        "table": r"(?:Table|Tab\.|表)\s*{}\b",
    }
    for item in items:
        item_id = item.get("id")
        if item_type in patterns:
            if re.search(patterns[item_type].format(item_id), content, re.IGNORECASE):
                found.append(item)
        elif item_type == "equation":
            text = item.get("text", "").replace("$$", "").strip()[:30]
            if text and text in content:
                found.append(item)
    return found
