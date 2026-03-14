"""Application configuration."""

import json
import os
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "KeenPoint"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR: str = "uploads"
    DOWNLOAD_DIR: str = "downloads"
    OUTPUT_DIR: str = "outputs"
    LOG_DIR: str = "logs"
    PROMPT_LOG_DIR: str = "logs/prompts"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"

    # Dify API
    DIFY_API_KEY: Optional[str] = "app-VWzZqV55lOhVZoQm91SGaSLO"
    DIFY_API_URL: str = "https://api.dify.ai/v1"
    DIFY_USER: str = "keenpoint"

    # Gemini / AiHubMix image generation
    AIHUBMIX_API_KEY: Optional[str] = "sk-ixOhQ7cBdb4CIZzK9cFd56333aB14d46B1C9E9A4286aB293"
    AIHUBMIX_BASE_URL: str = "https://aihubmix.com/gemini"
    GEMINI_IMAGE_MODEL: str = "gemini-3.1-flash-image-preview-free"

    # Slide generation
    SLIDE_IMAGE_SRC_PREFIX: str = ""
    SLIDE_GENERATED_IMAGES_DIR: str = "outputs/generated_images"

    # LLM workflow IDs (Dify)
    LLM_ID_BASIC_INFO: int = 0
    LLM_ID_VISUAL_ANALYSIS: int = 2
    LLM_ID_OUTLINE: int = 3
    LLM_ID_SLIDE_GEN: int = 4
    LLM_ID_IMAGE_GEN: int = 5
    LLM_ID_TEXT_REWRITE: int = 6

    # MinerU API
    MINERU_TOKEN: Optional[str] = None
    MINERU_MODEL: str = "vlm"
    MINERU_UPLOAD_URL: str = "https://mineru.net/api/v4/file-urls/batch"
    MINERU_RESULT_URL: str = "https://mineru.net/api/v4/extract-results/batch"
    MINERU_POLL_INTERVAL: int = 10

    # Limits
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024
    MAX_SEGMENT_LENGTH: int = 10000

    @property
    def MINERU_HEADERS(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.MINERU_TOKEN}",
        }

    class Config:
        env_file = ".env"
        case_sensitive = True


# Pipeline output file names (numbered for clarity)
OUTPUT_FILES = {
    "parsed_document":   "01_parsed_document.json",
    "visual_analysis":   "02_visual_analysis.json",
    "section_outlines":  "03_section_outlines.json",
    "slide_pool":        "04_slide_pool.json",
    "compressed_slides": "05_compressed_slides.json",
    "enhanced_slides":   "06_enhanced_slides.json",
}

settings = Settings()


def ensure_dirs():
    """Create required directories."""
    for d in [settings.UPLOAD_DIR, settings.DOWNLOAD_DIR,
              settings.OUTPUT_DIR, settings.LOG_DIR, settings.PROMPT_LOG_DIR]:
        os.makedirs(d, exist_ok=True)


def save_output(data, filename: str) -> Path:
    """Save data as JSON to the outputs directory."""
    output_dir = Path(settings.BASE_DIR) / settings.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def get_output_path(filename: str) -> Path:
    """Get full path for an output file."""
    return Path(settings.BASE_DIR) / settings.OUTPUT_DIR / filename
