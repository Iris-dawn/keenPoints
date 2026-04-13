"""Logging with LLM prompt recording."""

import json
import os
import logging
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, List

_LOG_FMT = "%(asctime)s [%(levelname)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logger(name: str = "keenpoint", level: str = "INFO",
                 log_file: str = None) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(getattr(logging, level.upper(), logging.INFO))
    if log.handlers:
        return log

    fmt = logging.Formatter(_LOG_FMT, _DATE_FMT)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    log.addHandler(ch)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        log.addHandler(fh)

    return log


logger = setup_logger("keenpoint", "INFO", "logs/app.log")


# ── Prompt Tracking System ─────────────────────────────────────────────────────

def log_llm_call(llm_id: int, 
                 prompt: str, 
                 response: dict = None, 
                 tag: str = "",
                 metadata: Optional[Dict[str, Any]] = None):
    """Save LLM prompt and response to logs/prompts/ with enhanced metadata.

    Each call produces a JSON manifest file containing:
      - Prompt and response content
      - Metadata (paper, step, slide_id, etc.)
      - Timestamp and llm_id
      - File paths to raw content (if large)

    Args:
        llm_id: Dify workflow ID
        prompt: User prompt string
        response: Dify API response dict
        tag: Custom tag for identification (e.g., "outline_1", "slide_02_text_only")
        metadata: Additional context dict with keys:
            - paper: str (paper name)
            - step: int (pipeline step 1-7)
            - slide_id: Optional[int]
            - section_name: Optional[str]
            - element_type: Optional[str] (image/table/equation)
            - element_id: Optional[int]
    """
    from app.core.config import settings, get_current_paper

    prompt_dir = Path(settings.BASE_DIR) / settings.PROMPT_LOG_DIR
    prompt_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
    tag_str = f"_{tag}" if tag else ""
    
    # Build metadata
    meta = {
        "timestamp": ts,
        "llm_id": llm_id,
        "tag": tag,
        "paper": get_current_paper() or "unknown",
        "created_at": datetime.now().isoformat(),
    }
    
    if metadata:
        meta.update(metadata)
    
    # Determine if content should be inlined or saved separately
    PROMPT_INLINE_THRESHOLD = 5000  # chars
    RESPONSE_INLINE_THRESHOLD = 10000  # chars
    
    manifest = {
        "metadata": meta,
        "prompt": None,
        "prompt_file": None,
        "response": None,
        "response_file": None,
    }
    
    # Handle prompt
    if len(prompt) > PROMPT_INLINE_THRESHOLD:
        prompt_file = f"{ts}_llm{llm_id}{tag_str}_prompt.txt"
        (prompt_dir / prompt_file).write_text(prompt, encoding="utf-8")
        manifest["prompt_file"] = prompt_file
    else:
        manifest["prompt"] = prompt
    
    # Handle response
    if response is not None:
        response_json = json.dumps(response, ensure_ascii=False, indent=2)
        if len(response_json) > RESPONSE_INLINE_THRESHOLD:
            response_file = f"{ts}_llm{llm_id}{tag_str}_response.json"
            (prompt_dir / response_file).write_text(response_json, encoding="utf-8")
            manifest["response_file"] = response_file
        else:
            manifest["response"] = response
    
    # Save manifest
    manifest_file = f"{ts}_llm{llm_id}{tag_str}_manifest.json"
    (prompt_dir / manifest_file).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), 
        encoding="utf-8"
    )
    
    # Update index
    _update_prompt_index(manifest_file, manifest)
    
    logger.debug(f"[LOG] LLM call logged: {manifest_file}")


def _update_prompt_index(manifest_file: str, manifest: dict):
    """Append entry to daily prompt index for fast querying."""
    from app.core.config import settings
    
    prompt_dir = Path(settings.BASE_DIR) / settings.PROMPT_LOG_DIR
    today = datetime.now().strftime("%Y%m%d")
    index_file = prompt_dir / f"index_{today}.json"
    
    # Load existing index
    if index_file.exists():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            index = {"date": today, "calls": []}
    else:
        index = {"date": today, "calls": []}
    
    # Append entry
    entry = {
        "manifest_file": manifest_file,
        "timestamp": manifest["metadata"]["timestamp"],
        "llm_id": manifest["metadata"]["llm_id"],
        "tag": manifest["metadata"]["tag"],
        "paper": manifest["metadata"]["paper"],
        "metadata": manifest["metadata"],
    }
    index["calls"].append(entry)
    
    # Save index
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def query_prompts(paper: str = None, 
                  llm_id: int = None, 
                  step: int = None,
                  date: str = None,
                  tag: str = None,
                  limit: int = 100) -> List[dict]:
    """Query prompt logs by filters.
    
    Args:
        paper: Paper name filter
        llm_id: LLM workflow ID filter
        step: Pipeline step filter (1-7)
        date: Date filter (YYYYMMDD or YYYY-MM-DD)
        tag: Tag substring filter
        limit: Max number of results
    
    Returns:
        List of manifest dicts matching filters
    """
    from app.core.config import settings
    
    prompt_dir = Path(settings.BASE_DIR) / settings.PROMPT_LOG_DIR
    results = []
    
    # Normalize date
    if date:
        date = date.replace("-", "")
    
    # Find index files
    if date:
        index_files = [prompt_dir / f"index_{date}.json"]
    else:
        index_files = sorted(prompt_dir.glob("index_*.json"), reverse=True)
    
    for index_file in index_files:
        if not index_file.exists():
            continue
        
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        
        for entry in index.get("calls", []):
            # Apply filters
            if paper and entry.get("paper") != paper:
                continue
            if llm_id is not None and entry.get("llm_id") != llm_id:
                continue
            if step is not None and entry.get("metadata", {}).get("step") != step:
                continue
            if tag and tag not in (entry.get("tag") or ""):
                continue
            
            # Load full manifest
            manifest_path = prompt_dir / entry["manifest_file"]
            if manifest_path.exists():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    # Add manifest_file to metadata for frontend reference
                    manifest["metadata"]["manifest_file"] = entry["manifest_file"]
                    results.append(manifest)
                    
                    if len(results) >= limit:
                        return results
                except Exception:
                    continue
    
    return results


def get_prompt_detail(manifest_file: str) -> dict:
    """Load full prompt detail by manifest filename.
    
    Returns dict with:
        - metadata
        - prompt (loaded from file if needed)
        - response (loaded from file if needed)
    """
    from app.core.config import settings
    
    prompt_dir = Path(settings.BASE_DIR) / settings.PROMPT_LOG_DIR
    manifest_path = prompt_dir / manifest_file
    
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_file}")
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    
    # Load prompt from file if needed
    if manifest.get("prompt_file"):
        prompt_path = prompt_dir / manifest["prompt_file"]
        if prompt_path.exists():
            manifest["prompt"] = prompt_path.read_text(encoding="utf-8")
    
    # Load response from file if needed
    if manifest.get("response_file"):
        response_path = prompt_dir / manifest["response_file"]
        if response_path.exists():
            try:
                manifest["response"] = json.loads(response_path.read_text(encoding="utf-8"))
            except Exception:
                manifest["response"] = response_path.read_text(encoding="utf-8")
    
    return manifest


def get_prompt_stats(date: str = None) -> dict:
    """Get statistics of LLM calls.
    
    Returns counts by llm_id, paper, step.
    """
    results = query_prompts(date=date, limit=10000)
    
    stats = {
        "total_calls": len(results),
        "by_llm_id": {},
        "by_paper": {},
        "by_step": {},
    }
    
    for r in results:
        meta = r.get("metadata", {})
        
        llm = meta.get("llm_id")
        if llm is not None:
            stats["by_llm_id"][llm] = stats["by_llm_id"].get(llm, 0) + 1
        
        paper = meta.get("paper")
        if paper:
            stats["by_paper"][paper] = stats["by_paper"].get(paper, 0) + 1
        
        step = meta.get("step")
        if step is not None:
            stats["by_step"][step] = stats["by_step"].get(step, 0) + 1
    
    return {
        "date": date or "all time",
        "statistics": stats
    }
