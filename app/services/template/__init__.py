"""Template registry and base class for slide generation.

To add a new template:
  1. Create a module in this package (e.g. modern_template.py)
  2. Subclass TemplateContent, implement all abstract members
  3. Call register_template(MyContent()) at module level
  4. Import the module at the bottom of this file
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class TemplateContent(ABC):
    """Abstract base for template-specific content blocks."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def colors(self) -> Dict[str, str]: ...

    @property
    @abstractmethod
    def layout_css_skeletons(self) -> Dict[str, str]: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def shell_snippet(self, section_num: str, title: str,
                      page_label: str, assets: Dict[str, str]) -> str: ...

    @property
    def role_to_layout(self) -> Dict[str, str]:
        return {"takeaways": "conclusion", "overview_figure": "figure_focus"}

    @property
    def asset_filenames(self) -> Dict[str, str]:
        return {"logo": "logo.png"}


# ── Registry ─────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, TemplateContent] = {}


def register_template(template: TemplateContent) -> None:
    _REGISTRY[template.name] = template


def get_template(name: str) -> TemplateContent:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown template '{name}'. Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[name]


def list_templates() -> List[str]:
    return list(_REGISTRY.keys())


# ── Auto-import templates ────────────────────────────────────────────────────
from app.services.template import bit_template  # noqa: E402, F401
