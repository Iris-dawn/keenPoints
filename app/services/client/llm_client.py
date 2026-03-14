"""Unified LLM client: Dify Workflow API + Gemini image generation.

All external LLM interactions go through this module. Every call is
automatically logged to logs/prompts/ for auditing and debugging.
"""

import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

from app.core.config import settings
from app.core.logger import logger, log_llm_call

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    genai = None
    genai_types = None

MIME_TYPES = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "webp": "image/webp", "gif": "image/gif", "pdf": "application/pdf",
}


# ── Dify Workflow Client ──────────────────────────────────────────────────────

class DifyClient:
    """Dify Workflow API client with integrated prompt logging."""

    def __init__(self, api_key: str = None, base_url: str = None, user: str = None):
        self.api_key = api_key or settings.DIFY_API_KEY
        if not self.api_key:
            raise ValueError("DIFY_API_KEY not configured")
        self.base_url = (base_url or settings.DIFY_API_URL).rstrip("/")
        self.user = user or settings.DIFY_USER
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def upload(self, file_path: Union[str, Path]) -> Dict:
        """Upload a single file to Dify."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        ext = path.suffix.lower().lstrip(".")
        mime = MIME_TYPES.get(ext)
        if not mime:
            raise ValueError(f"Unsupported file type: {ext}")
        with open(path, "rb") as f:
            resp = requests.post(
                f"{self.base_url}/files/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (path.name, f, mime)},
                data={"user": self.user},
                timeout=300,
            )
            resp.raise_for_status()
            return resp.json()

    def upload_batch(self, paths: List[Union[str, Path]]) -> List[Dict]:
        """Upload multiple files, returning per-file results."""
        results = []
        for idx, p in enumerate(paths, 1):
            try:
                r = self.upload(p)
                results.append({"success": True, "file_path": str(p), "file_id": r.get("id")})
                logger.info(f"[LLM] upload [{idx}/{len(paths)}] ok: {Path(p).name}")
            except Exception as e:
                results.append({"success": False, "file_path": str(p), "error": str(e)})
                logger.error(f"[LLM] upload [{idx}/{len(paths)}] fail: {e}")
        return results

    def run(self, llm_id: int, prompt: str, extra: Dict = None,
            timeout: int = 600, tag: str = "") -> Dict:
        """Execute a Dify workflow (streaming). Every call is logged."""
        inputs = {"llm_id": llm_id, "user_prompt": prompt}
        if extra:
            inputs.update(extra)
        payload = {"inputs": inputs, "response_mode": "streaming", "user": self.user}
        logger.info(f"[LLM] run llm_id={llm_id} prompt_len={len(prompt)}")

        result = self._stream(payload, timeout)
        log_llm_call(llm_id, prompt, result, tag=tag)
        return result

    def _stream(self, payload: Dict, timeout: int) -> Dict:
        """Execute SSE streaming request and collect the response."""
        with requests.post(
            f"{self.base_url}/workflows/run",
            headers=self.headers, json=payload, timeout=timeout, stream=True,
        ) as resp:
            resp.raise_for_status()
            result_data: Dict = {}
            text_chunks: list = []

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                etype = event.get("event")
                data = event.get("data", {})
                if etype == "workflow_started":
                    logger.info(f"[LLM] stream started run_id={event.get('workflow_run_id')}")
                elif etype == "text_chunk":
                    text_chunks.append(data.get("text", ""))
                elif etype == "node_finished" and data.get("status") == "failed":
                    logger.warning(f"[LLM] node failed: {data.get('error')}")
                elif etype == "workflow_finished":
                    result_data = data
                    logger.info(
                        f"[LLM] finished status={data.get('status')} "
                        f"elapsed={data.get('elapsed_time', 0):.1f}s "
                        f"tokens={data.get('total_tokens')}"
                    )

            outputs = result_data.get("outputs") or {}
            if not outputs and text_chunks:
                outputs = {"text": "".join(text_chunks)}

            return {"data": {
                "id":           result_data.get("id", ""),
                "workflow_id":  result_data.get("workflow_id", ""),
                "status":       result_data.get("status", "succeeded"),
                "outputs":      outputs,
                "error":        result_data.get("error"),
                "elapsed_time": result_data.get("elapsed_time"),
                "total_tokens": result_data.get("total_tokens"),
                "total_steps":  result_data.get("total_steps", 0),
            }}


# ── Output parsing ────────────────────────────────────────────────────────────

def extract_json_output(result: Dict) -> Any:
    """Extract and parse JSON from a Dify workflow response."""
    outputs = result.get("data", {}).get("outputs", {})
    if not outputs:
        return {"error": "No output"}

    if len(outputs) == 1:
        val = list(outputs.values())[0]
        if isinstance(val, str):
            parsed = _try_parse_json(val)
            if parsed is not None:
                return parsed
        elif isinstance(val, dict):
            text_val = val.get("text")
            if isinstance(text_val, str):
                parsed = _try_parse_json(text_val)
                if isinstance(parsed, dict):
                    return parsed
        return val if isinstance(val, dict) else outputs

    text_val = outputs.get("text")
    if isinstance(text_val, str):
        parsed = _try_parse_json(text_val)
        if isinstance(parsed, dict):
            return parsed
    return outputs


def extract_html_output(result: Dict) -> str:
    """Extract raw HTML string from a Dify workflow response."""
    outputs = result.get("data", {}).get("outputs", {})
    if not outputs:
        raise ValueError("No outputs in response")
    for key in ("text", "output", "result", "html"):
        val = outputs.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    for val in outputs.values():
        if isinstance(val, str) and val.strip():
            return val.strip()
    raise ValueError(f"No HTML text in outputs. Keys: {list(outputs.keys())}")


def _try_parse_json(text: str) -> Optional[Any]:
    """Parse text that may contain JSON, possibly markdown-fenced."""
    if not isinstance(text, str) or not text.strip():
        return None
    s = text.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    fenced = re.match(r"^```(?:json)?\s*([\s\S]*?)\s*```$", s, re.IGNORECASE)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except Exception:
            pass
    for start_ch, end_ch in [("{", "}"), ("[", "]")]:
        i, j = s.find(start_ch), s.rfind(end_ch)
        if i != -1 and j > i:
            try:
                return json.loads(s[i:j + 1])
            except Exception:
                pass
    return None


# ── Gemini image generation ───────────────────────────────────────────────────

def generate_image(prompt: str, aspect_ratio: str = "4:3") -> tuple:
    """Generate an image via Gemini/AiHubMix. Returns (bytes, extension)."""
    if genai is None or genai_types is None:
        raise ImportError("google-genai required for image generation")
    if not settings.AIHUBMIX_API_KEY:
        raise ValueError("AIHUBMIX_API_KEY not configured")

    log_llm_call(settings.LLM_ID_IMAGE_GEN, prompt, tag="gemini_image")

    client = genai.Client(
        api_key=settings.AIHUBMIX_API_KEY,
        http_options={"base_url": settings.AIHUBMIX_BASE_URL},
    )
    contents = [genai_types.Content(
        role="user", parts=[genai_types.Part.from_text(text=prompt)]
    )]
    config = genai_types.GenerateContentConfig(
        response_modalities=["IMAGE", "TEXT"],
        image_config=genai_types.ImageConfig(aspect_ratio=aspect_ratio),
    )

    for chunk in client.models.generate_content_stream(
        model=settings.GEMINI_IMAGE_MODEL, contents=contents, config=config,
    ):
        if (not chunk.candidates or not chunk.candidates[0].content
                or not chunk.candidates[0].content.parts):
            continue
        part = chunk.candidates[0].content.parts[0]
        if part.inline_data and part.inline_data.data:
            mime = part.inline_data.mime_type
            ext = (mimetypes.guess_extension(mime) or ".png").lstrip(".")
            return part.inline_data.data, ext

    raise RuntimeError("Gemini returned no image data")


# ── Module-level singleton ────────────────────────────────────────────────────

_client: Optional[DifyClient] = None


def get_client() -> DifyClient:
    """Get or create the default Dify client."""
    global _client
    if _client is None:
        _client = DifyClient()
    return _client
