"""BIT (Beijing Institute of Technology) slide template."""

from typing import Dict
from app.services.template import TemplateContent, register_template


class BITContent(TemplateContent):

    @property
    def name(self) -> str:
        return "BIT"

    @property
    def asset_filenames(self) -> Dict[str, str]:
        return {"logo": "logo.png", "xiaoxun": "校训.svg"}

    @property
    def colors(self) -> Dict[str, str]:
        return {
            "dk1": "#000000", "lt1": "#FFFFFF", "dk2": "#E8EEF2", "lt2": "#F9FAFB",
            "accent1": "#2B4663", "accent2": "#5C7885", "accent3": "#94ACBC",
            "accent4": "#B9CAE1", "accent5": "#97ABBD", "accent6": "#3B606F",
            "hlink": "#5FCBFB",
        }

    @property
    def role_to_layout(self) -> Dict[str, str]:
        return {"takeaways": "conclusion", "overview_figure": "figure_focus"}

    @property
    def layout_css_skeletons(self) -> Dict[str, str]:
        return {

"text_only": """
.slide-content {
    position: absolute; top: 72px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 12px;
}
.bullet-item {
    padding: 10px 12px 10px 18px;
    border-left: 3px solid #2B4663;
    background: rgba(43,70,99,0.04);
    border-radius: 0 4px 4px 0;
    font-size: 14px; line-height: 1.55; color: #3B606F;
}
""",

"text_image": """
.content-col {
    position: absolute; left: 35px; top: 72px;
    width: 410px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 12px;
}
.bullet-item {
    padding: 10px 10px 10px 16px;
    border-left: 3px solid #2B4663;
    background: rgba(43,70,99,0.04);
    border-radius: 0 4px 4px 0;
    font-size: 13px; line-height: 1.5; color: #000;
}
.col-divider {
    position: absolute; left: 455px; top: 75px;
    bottom: 55px; width: 1px; background: #B9CAE1; z-index: 4;
}
.image-col {
    position: absolute; left: 465px; top: 72px;
    right: 30px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.image-frame {
    width: 100%; flex: 1;
    border: 1px solid #B9CAE1; border-radius: 4px;
    overflow: hidden; background: #fff;
    display: flex; align-items: center; justify-content: center;
}
.image-frame img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.image-caption { margin-top: 6px; font-size: 10px; color: #3B606F; text-align: center; }
""",

"figure_focus": """
.image-area {
    position: absolute; left: 35px; top: 72px;
    width: 520px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.image-frame {
    width: 100%; flex: 1;
    border: 1px solid #B9CAE1; border-radius: 4px;
    overflow: hidden; background: #fff;
    display: flex; align-items: center; justify-content: center;
}
.image-frame img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.image-caption { margin-top: 6px; font-size: 10px; color: #3B606F; text-align: center; }
.notes-col {
    position: absolute; left: 575px; top: 72px;
    right: 25px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 10px;
}
.note-item {
    padding: 8px 10px 8px 14px;
    border-left: 2px solid #5C7885;
    font-size: 12px; line-height: 1.5; color: #3B606F;
}
""",

"equation": """
.content-col {
    position: absolute; left: 35px; top: 72px;
    width: 340px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 10px;
}
.bullet-item {
    padding: 8px 10px 8px 14px;
    border-left: 3px solid #2B4663;
    background: rgba(43,70,99,0.04);
    border-radius: 0 4px 4px 0;
    font-size: 12.5px; line-height: 1.5; color: #3B606F;
}
.col-divider {
    position: absolute; left: 385px; top: 75px;
    bottom: 55px; width: 1px; background: #B9CAE1; z-index: 4;
}
.eq-panel {
    position: absolute; left: 395px; top: 72px;
    right: 25px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 16px; padding: 12px 10px;
}
.eq-box {
    background: rgba(185,202,225,0.12);
    border: 1px solid #B9CAE1; border-radius: 6px;
    padding: 10px 14px; text-align: center;
}
.eq-label { font-size: 10px; font-weight: bold; color: #2B4663; margin-bottom: 6px; }
.eq-desc { font-size: 10.5px; color: #5C7885; margin-top: 6px; line-height: 1.4; text-align: left; }
""",

"table_result": """
.table-wrapper {
    position: absolute; top: 80px; bottom: 55px;
    left: 35px; right: 35px; z-index: 5;
    overflow: auto; display: flex; align-items: center; justify-content: center;
}
table { border-collapse: collapse; width: 100%; font-size: 12px; }
thead th {
    background: #2B4663; color: #fff;
    padding: 7px 10px; text-align: center; font-weight: 600;
}
tbody td {
    padding: 5px 10px; text-align: center;
    border-bottom: 1px solid #B9CAE1; color: #000;
}
tbody tr:nth-child(even) { background: rgba(185,202,225,0.18); }
tbody tr.highlight td { font-weight: bold; color: #2B4663; background: rgba(43,70,99,0.08); }
""",

"conclusion": """
.conclusion-grid {
    position: absolute; top: 78px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 14px;
}
.takeaway-card {
    display: flex; align-items: flex-start; gap: 14px;
    padding: 12px 16px;
    background: rgba(43,70,99,0.04);
    border: 1px solid #B9CAE1; border-radius: 6px;
}
.takeaway-num {
    min-width: 28px; height: 28px;
    background: #2B4663; color: #fff;
    border-radius: 50%; display: flex;
    align-items: center; justify-content: center;
    font-size: 13px; font-weight: bold;
}
.takeaway-text { font-size: 13px; line-height: 1.55; color: #000; }
.takeaway-text strong { color: #2B4663; }
""",

"text_image_generated": """
.content-col {
    position: absolute; left: 35px; top: 72px;
    width: 400px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 10px;
}
.bullet-item {
    padding: 10px 10px 10px 16px;
    border-left: 3px solid #2B4663;
    background: rgba(43,70,99,0.04);
    border-radius: 0 4px 4px 0;
    font-size: 13px; line-height: 1.5; color: #000;
}
.col-divider {
    position: absolute; left: 445px; top: 75px;
    bottom: 55px; width: 1px; background: #B9CAE1; z-index: 4;
}
.image-col {
    position: absolute; left: 455px; top: 72px;
    right: 28px; bottom: 50px; z-index: 5;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
}
.image-frame {
    width: 100%; flex: 1; border-radius: 6px;
    border: 1px solid #B9CAE1;
    overflow: hidden; background: #fff;
    display: flex; align-items: center; justify-content: center;
}
.image-frame img { max-width: 100%; max-height: 100%; object-fit: contain; display: block; }
.image-caption { margin-top: 6px; font-size: 10px; color: #3B606F; text-align: center; }
""",

"method_cards": """
.cards-area {
    position: absolute; top: 78px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: flex; flex-wrap: wrap; gap: 12px;
    align-items: stretch; align-content: center;
}
.method-card {
    flex: 1 1 200px;
    border: 1px solid #B9CAE1; border-radius: 6px;
    background: #fff; overflow: hidden;
    display: flex; flex-direction: column;
}
.method-card-header {
    background: #2B4663; color: #fff;
    padding: 7px 12px; font-size: 12px; font-weight: bold;
}
.method-card-header.alt { background: #5C7885; }
.method-card-body {
    flex: 1; padding: 10px 12px;
    font-size: 12px; line-height: 1.5; color: #3B606F;
}
.method-card-body ul { margin: 0; padding-left: 14px; }
.method-card-body li { margin-bottom: 5px; }
""",

"setup_timeline": """
.timeline-area {
    position: absolute; top: 78px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 16px;
}
.timeline-track { display: flex; align-items: stretch; gap: 0; }
.phase-block {
    flex: 1; position: relative;
    background: rgba(43,70,99,0.06);
    border: 1px solid #B9CAE1; border-radius: 4px;
    padding: 10px 12px; margin-right: 26px;
}
.phase-block:last-child { margin-right: 0; }
.phase-block::after {
    content: "→"; position: absolute; right: -19px; top: 50%;
    transform: translateY(-50%); color: #5C7885; font-size: 16px; font-weight: bold;
}
.phase-block:last-child::after { display: none; }
.phase-label { font-size: 11px; font-weight: bold; color: #2B4663; margin-bottom: 5px; }
.phase-items { font-size: 12px; color: #3B606F; line-height: 1.5; }
.detail-row { display: flex; gap: 12px; flex-wrap: wrap; }
.detail-chip {
    padding: 5px 11px; background: #fff;
    border: 1px solid #B9CAE1; border-radius: 4px;
    font-size: 12px; color: #2B4663;
}
""",

"highlight_grid": """
.highlight-grid {
    position: absolute; top: 78px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 12px; align-content: center;
}
.highlight-panel {
    padding: 14px 16px; border-radius: 6px;
    border-left: 4px solid #2B4663;
    background: rgba(43,70,99,0.05);
    display: flex; align-items: flex-start; gap: 12px;
}
.highlight-panel:nth-child(even) {
    border-left-color: #5C7885; background: rgba(92,120,133,0.05);
}
.panel-number {
    min-width: 28px; height: 28px;
    background: #2B4663; color: #fff;
    border-radius: 50%; display: flex;
    align-items: center; justify-content: center;
    font-size: 13px; font-weight: bold;
}
.highlight-panel:nth-child(even) .panel-number { background: #5C7885; }
.panel-text { font-size: 13px; line-height: 1.55; color: #000; }
""",

"structured_bullets": """
.bullets-area {
    position: absolute; top: 78px; bottom: 50px;
    left: 35px; right: 35px; z-index: 5;
    display: flex; flex-direction: column;
    justify-content: center; gap: 9px;
}
.bullet-row {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 9px 14px;
    border-left: 3px solid #2B4663;
    background: rgba(43,70,99,0.04);
    border-radius: 0 5px 5px 0;
}
.bullet-row.alt { border-left-color: #5C7885; background: rgba(92,120,133,0.04); }
.bullet-icon {
    min-width: 22px; height: 22px;
    background: #2B4663; color: #fff;
    border-radius: 50%; display: flex;
    align-items: center; justify-content: center;
    font-size: 11px; font-weight: bold;
}
.bullet-row.alt .bullet-icon { background: #5C7885; }
.bullet-text { font-size: 13px; line-height: 1.55; color: #000; }
.bullet-text strong { color: #2B4663; }
""",

        }

    @property
    def system_prompt(self) -> str:
        return (
            "You are an expert HTML/CSS developer creating academic presentation slides. "
            "Generate complete standalone HTML files following the BIT template.\n\n"
            "Rules:\n"
            "1. Canvas is exactly 960×540 px.\n"
            "2. Use only the BIT colour palette via CSS variables.\n"
            "3. Copy the decorative shell verbatim.\n"
            "4. Add ONLY content-area CSS and HTML after the shell.\n"
            "5. For equations, use MathJax v3.\n"
            "6. Keep text concise — no overflow.\n"
            "7. Return ONLY the HTML document."
        )

    def shell_snippet(self, section_num, title, page_label, assets):
        logo = assets.get("logo", "logo.png")
        xiaoxun = assets.get("xiaoxun", "校训.svg")
        return f"""
        <svg xmlns="http://www.w3.org/2000/svg"
            style="position:absolute;left:-0.7px;top:9.6px;width:44.1px;height:55.1px;overflow:visible;">
            <path d="M 0.000,0.000 L 44.100,0.000 L 25.355,55.100 L 0.000,55.100 Z"
                  fill="#2B4663" stroke="none" fill-rule="nonzero"/>
        </svg>
        <svg xmlns="http://www.w3.org/2000/svg"
            style="position:absolute;left:32.9px;top:29.9px;width:7.6px;height:17.5px;overflow:visible;">
            <path d="M 5.940,0.000 L 7.600,0.000 L 1.660,17.500 L 0.000,17.500 Z"
                  fill="#B9CAE1" stroke="#B9CAE1" stroke-width="3" fill-rule="nonzero"/>
        </svg>
        <div class="divider-line" style="top:64.7px;"></div>
        <div class="divider-line" style="top:493.2px;"></div>
        <div class="shape" style="left:956.4px;top:26.5px;width:3.6px;height:20.9px;background-color:#B9CAE1;"></div>
        <div class="shape" style="left:770.9px;top:19.8px;width:155.1px;height:34.1px;">
            <img src="{logo}" alt="BIT Logo" class="img-fit">
        </div>
        <div class="shape" style="left:45px;top:502px;width:200px;height:25px;">
            <img src="{xiaoxun}" alt="校训" class="img-fit" style="object-position:left bottom;">
        </div>
        <div class="slide-section">{section_num}</div>
        <div class="slide-title"><h1>{title}</h1></div>
        <div class="slide-footer-info">{page_label}</div>""".strip()


register_template(BITContent())
