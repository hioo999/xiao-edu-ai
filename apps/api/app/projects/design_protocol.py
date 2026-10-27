"""Runtime quality contract for AI generated HTML pages."""

DESIGN_AGENT_PROTOCOL = """你是网页设计 Agent。交付前必须反复迭代和自我评审，不能草草输出第一版。
以 Awwwards、Webby Awards、FWA 获奖网站作为视觉完成度参考，但要原创，不复制具体作品。
每一轮都检查并修正这 8 个维度：字体排版、留白节奏、视觉层级、色彩系统、动效、微交互、响应式布局、原创性。
先生成完整页面，再逐项审查；发现任何明显短板就修改并重新审查，最多进行 3 轮修订。
只有当 8 个维度都没有明显短板时才交付。最终只输出完整 HTML，不输出评审过程、评分或解释。
"""


def design_quality_issues(html: str) -> list[str]:
    """Apply deterministic minimum gates before a complete HTML page is saved."""
    lowered = html.lower()
    if "<html" not in lowered and "<!doctype" not in lowered:
        return []
    issues: list[str] = []
    if "<meta" not in lowered or "viewport" not in lowered:
        issues.append("missing responsive viewport")
    if "<style" not in lowered:
        issues.append("missing inline style system")
    if "@media" not in lowered:
        issues.append("missing responsive breakpoint")
    if "<script" not in lowered and "<button" not in lowered and "href=" not in lowered:
        issues.append("missing visible interaction")
    return issues
