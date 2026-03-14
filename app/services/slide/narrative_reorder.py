"""Narrative reorder: three-pass compression from slide pool to presentation order.

Pass 1 — Role assignment + narrative group mapping
Pass 2 — Within-group compression (Merge / Delete)
Pass 3 — Cross-group reordering (academic → presentation narrative)
"""

import json
import copy
from pathlib import Path

from app.core.config import save_output, OUTPUT_FILES
from app.core.logger import logger

TAG = "[REORDER]"

# ── 1. Role taxonomy (14 roles, each with a narrative load weight) ────────────

ROLE_BASE: dict[str, float] = {
    "hook_context":       0.65,
    "related_work":       0.75,
    "problem_definition": 1.00,
    "gap_limitations":    0.95,
    "insight_thesis":     0.85,
    "overview_figure":    0.90,
    "method_overview":    1.20,
    "method_component":   1.45,
    "theoretical":        1.60,
    "experiment_setup":   0.95,
    "results":            1.20,
    "analysis_ablation":  1.10,
    "takeaways":          0.75,
    "limitation_future":  0.60,
}

# ── 2. Presentation narrative template ────────────────────────────────────────

NARRATIVE_GROUPS = [
    ("opening",  ["hook_context"],                                      0.07, 1, 1),
    ("problem",  ["problem_definition", "gap_limitations"],             0.14, 1, 2),
    ("related",  ["related_work"],                                      0.08, 1, 2),
    ("thesis",   ["insight_thesis", "overview_figure"],                 0.10, 1, 2),
    ("method",   ["method_overview", "method_component", "theoretical"],0.35, 3, 6),
    ("evidence", ["experiment_setup", "results", "analysis_ablation"],  0.26, 3, 5),
    ("closing",  ["takeaways", "limitation_future"],                    0.07, 1, 2),
]

GROUP_FLOOR: dict[str, int] = {
    "opening": 1, "problem": 1, "related": 1, "thesis": 1,
    "method": 3, "evidence": 3, "closing": 1,
}

GROUP_PRIORITY_ROLE: dict[str, str] = {
    "opening": "hook_context", "problem": "problem_definition",
    "related": "related_work", "thesis": "insight_thesis",
    "method": "method_overview", "evidence": "results", "closing": "takeaways",
}


# ── 3. Merge logic ───────────────────────────────────────────────────────────

def _jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def _should_merge(s1: dict, s2: dict) -> bool:
    if s1["section_name"] == s2["section_name"]:
        if _jaccard(s1.get("content_points", []), s2.get("content_points", [])) > 0.25:
            return True
        if len(s1.get("content_points", [])) <= 3 and len(s2.get("content_points", [])) <= 3:
            return True
    return False


def _merge(s1: dict, s2: dict) -> dict:
    merged = copy.deepcopy(s1)
    existing = set(s1.get("content_points", []))
    for pt in s2.get("content_points", []):
        if pt not in existing:
            merged["content_points"].append(pt)
    for key in ("images", "tables", "equations"):
        if not merged.get("visual_refs", {}).get(key):
            merged.setdefault("visual_refs", {})[key] = s2.get("visual_refs", {}).get(key, [])
    merged["_merged_from"] = merged.get("_merged_from", []) + [s2.get("slide_title", "")]
    return merged


# ── 4. Scoring ────────────────────────────────────────────────────────────────

def _has_visuals(slide: dict) -> bool:
    vr = slide.get("visual_refs", {})
    return bool(vr.get("images") or vr.get("tables") or vr.get("equations"))


def keep_score(slide: dict) -> float:
    load = slide.get("_load", ROLE_BASE.get(slide.get("_role", "method_component"), 1.0))
    vr = slide.get("visual_refs", {})
    visual = min(
        len(vr.get("images", [])) * 0.5 +
        len(vr.get("tables", [])) * 0.8 +
        len(vr.get("equations", [])) * 0.3, 1.0
    )
    content = min(len(slide.get("content_points", [])), 5) / 5.0
    return load * (1.0 + 0.3 * content + 0.2 * visual)


# ── 5. Within-group compression ──────────────────────────────────────────────

def _compress_group(slides: list[dict], budget: int) -> list[dict]:
    pinned = [s for s in slides if _has_visuals(s)]
    compressible = [s for s in slides if not _has_visuals(s)]

    if len(pinned) >= budget:
        return pinned

    text_budget = budget - len(pinned)
    if len(compressible) <= text_budget:
        return pinned + compressible

    # Deduplicate
    seen: set[str] = {s.get("slide_title", "") for s in pinned}
    deduped = []
    for s in sorted(compressible, key=keep_score, reverse=True):
        t = s.get("slide_title", "")
        if t not in seen:
            seen.add(t)
            deduped.append(s)
    compressible = deduped

    if len(compressible) <= text_budget:
        return pinned + compressible

    # Merge pass
    changed = True
    while changed and len(compressible) > text_budget:
        changed = False
        for i in range(len(compressible)):
            for j in range(i + 1, len(compressible)):
                if _should_merge(compressible[i], compressible[j]):
                    a, b = compressible[i], compressible[j]
                    primary, secondary = (a, b) if keep_score(a) >= keep_score(b) else (b, a)
                    merged = _merge(primary, secondary)
                    compressible = [merged] + [s for k, s in enumerate(compressible) if k != i and k != j]
                    changed = True
                    break
            if changed:
                break

    # Delete pass
    if len(compressible) > text_budget:
        compressible = sorted(compressible, key=keep_score, reverse=True)[:text_budget]

    return pinned + compressible


# ── 6. Main algorithm ────────────────────────────────────────────────────────

def reconstruct(input_path: str, target_n: int = 16) -> list[dict]:
    """Full three-pass narrative reconstruction."""
    raw = json.loads(Path(input_path).read_text(encoding="utf-8"))
    slides = raw["slides"]

    # Pass 1: Role assignment
    for s in slides:
        s["_role"] = s.get("role", "method_component")
        s["_load"] = ROLE_BASE.get(s["_role"], 1.0)

    total_raw_load = sum(s["_load"] for s in slides)
    logger.info(f"{TAG} Pass 1: {len(slides)} candidates, raw_load={total_raw_load:.2f}")

    role_to_group: dict[str, str] = {}
    group_config: dict[str, dict] = {}
    for gname, roles, frac, mn, mx in NARRATIVE_GROUPS:
        for r in roles:
            role_to_group[r] = gname
        group_config[gname] = {"roles": roles, "frac": frac, "min": mn, "max": mx}

    groups: dict[str, list[dict]] = {g[0]: [] for g in NARRATIVE_GROUPS}
    for s in slides:
        g = role_to_group.get(s["_role"])
        if g:
            groups[g].append(s)
        else:
            groups["method"].append(s)

    for gname, gslides in groups.items():
        logger.info(f"{TAG}   {gname}: {len(gslides)} slides")

    # Pass 2: Budget allocation + compression
    group_load = {gn: sum(s["_load"] for s in gs) for gn, gs in groups.items()}
    total_load = sum(group_load.values()) or 1.0

    mandatory_floor = sum(
        min(GROUP_FLOOR.get(gn, 1), len(gs)) for gn, gs in groups.items() if gs
    )
    effective_target = max(target_n, mandatory_floor)
    extra_budget = effective_target - mandatory_floor

    if effective_target > target_n:
        logger.info(f"{TAG} Pass 2: target raised {target_n}→{effective_target} (floor={mandatory_floor})")

    compressed: dict[str, list[dict]] = {}
    for gname, roles, _frac, _mn, mx in NARRATIVE_GROUPS:
        raw_slides = groups[gname]
        if not raw_slides:
            compressed[gname] = []
            continue

        floor = min(GROUP_FLOOR.get(gname, 1), len(raw_slides))
        frac_dynamic = group_load[gname] / total_load
        extra = round(extra_budget * frac_dynamic)
        budget = min(floor + extra, mx, len(raw_slides))
        budget = max(budget, floor)

        result = _compress_group(raw_slides, budget)

        # Priority-role guarantee
        priority_role = GROUP_PRIORITY_ROLE.get(gname)
        if priority_role:
            has_priority = any(s.get("_role") == priority_role for s in result)
            if not has_priority:
                candidates = [s for s in raw_slides if s.get("_role") == priority_role]
                if candidates:
                    best = max(candidates, key=keep_score)
                    swappable = [s for s in result if s.get("_role") != priority_role and not _has_visuals(s)]
                    if swappable:
                        worst = min(swappable, key=keep_score)
                        result = [s for s in result if s is not worst] + [best]
                    else:
                        result.append(best)

        compressed[gname] = result
        logger.info(f"{TAG}   {gname}: {len(raw_slides)}→{len(result)}")

    # Pass 3: Cross-group reordering
    _section_order = {}
    for s in slides:
        sec = s.get("section_name", "")
        if sec not in _section_order:
            _section_order[sec] = len(_section_order)

    _ROLE_ORDER = [
        "hook_context", "gap_limitations", "problem_definition", "related_work",
        "insight_thesis", "overview_figure", "method_overview", "method_component",
        "theoretical", "experiment_setup", "results", "analysis_ablation",
        "takeaways", "limitation_future",
    ]

    def intra_order(slide):
        role = slide.get("_role", "method_component")
        try:
            ri = _ROLE_ORDER.index(role)
        except ValueError:
            ri = 99
        si = _section_order.get(slide.get("section_name", ""), 999)
        return (ri, si, -keep_score(slide))

    presentation_order = ["opening", "problem", "related", "thesis", "method", "evidence", "closing"]
    final_slides = []
    for gname in presentation_order:
        final_slides.extend(sorted(compressed.get(gname, []), key=intra_order))

    logger.info(f"{TAG} Pass 3: {len(final_slides)} final slides in presentation order")
    for i, s in enumerate(final_slides, 1):
        logger.info(f"{TAG}   [{i:02d}] [{s.get('_role', ''):20s}] {s.get('slide_title', '')}")

    return final_slides


# ── 7. Output writer ─────────────────────────────────────────────────────────

def _write_output(slides: list[dict], output_path: str) -> None:
    clean = []
    for new_id, s in enumerate(slides):
        cs = {k: v for k, v in s.items() if not k.startswith("_")}
        cs["slide_id"] = new_id
        clean.append(cs)
    Path(output_path).write_text(
        json.dumps({"slides": clean, "statistics": {"total_slides": len(clean)}},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"{TAG} saved to {output_path}")


# ── 8. Public entry ──────────────────────────────────────────────────────────

def run(input_path: str = None, target_n: int = 21) -> list[dict]:
    """Run narrative reconstruction and save output."""
    from app.core.config import get_output_path
    if input_path is None:
        input_path = str(get_output_path(OUTPUT_FILES["slide_pool"]))
    final = reconstruct(input_path, target_n=target_n)
    output_path = str(get_output_path(OUTPUT_FILES["compressed_slides"]))
    _write_output(final, output_path)
    return final


# ── 9. CLI entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from app.core.config import settings, get_output_path

    input_file = sys.argv[1] if len(sys.argv) > 1 else str(get_output_path(OUTPUT_FILES["slide_pool"]))
    target = int(sys.argv[2]) if len(sys.argv) > 2 else 21
    run(input_file, target_n=target)
