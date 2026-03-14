"""Logging with LLM prompt recording."""

import json
import os
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

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


def log_llm_call(llm_id: int, prompt: str, response: dict = None, tag: str = ""):
    """Save LLM prompt and response to logs/prompts/ for auditing.

    Each call produces:
      - {timestamp}_llm{id}_{tag}_prompt.txt
      - {timestamp}_llm{id}_{tag}_response.json  (if response provided)
    """
    from app.core.config import settings

    prompt_dir = Path(settings.BASE_DIR) / settings.PROMPT_LOG_DIR
    prompt_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
    tag_str = f"_{tag}" if tag else ""
    base = f"{ts}_llm{llm_id}{tag_str}"

    (prompt_dir / f"{base}_prompt.txt").write_text(prompt, encoding="utf-8")

    if response is not None:
        (prompt_dir / f"{base}_response.json").write_text(
            json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    logger.debug(f"[LOG] LLM call logged: {base}")
