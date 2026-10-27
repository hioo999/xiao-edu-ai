from __future__ import annotations

from html import escape
import re

from apps.api.app.models.gateway import ModelGateway
from packages.agent_runtime.src.dispatcher import AgentExecutionResult
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest, evaluate_dispatch
from .design_protocol import DESIGN_AGENT_PROTOCOL


_HTML_FENCE = re.compile(r"```(?:html)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_DOCUMENT_END = re.compile(r"</html\s*>", re.IGNORECASE)

class HtmlModelDispatcher:
    """Turns an organization-scoped text model response into a safe HTML artifact."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    def dispatch(self, policy: AgentDispatchRequest, prompt: str, *, organization_id: str, previous_html: str = "") -> AgentExecutionResult:
        evaluate_dispatch(policy)
        generated = self._gateway.generate_text(organization_id, self._instruction(prompt, previous_html=previous_html))
        document = self._extract_html(generated.content)
        return AgentExecutionResult(
            agent_kind=policy.agent_kind,
            html=document,
            teaching_steps=self._teaching_steps(prompt, document),
        )

    @staticmethod
    def _instruction(prompt: str, *, previous_html: str = "") -> str:
        return (
            DESIGN_AGENT_PROTOCOL
            + "你是一名面向小学 3-6 年级学生的网页创作老师。"
            "根据学生的需求生成一个完整、单文件、中文网页。"
            "只输出 HTML 文档，不要解释，不要 Markdown 代码围栏。"
            "可以使用内联 JavaScript、CSS、SVG、Canvas 实现按钮、动画和小游戏。"
            "不能使用网络请求、外部依赖、iframe、表单、跳转、浏览器存储或访问父页面。"
            "所有互动必须在本网页内完成。\n\n"
            f"学生需求：{prompt.strip()}"
            + (f"\n请基于下面的已有网页修改，保留未要求修改的内容、风格与互动，返回修改后的完整文档：\n{previous_html}" if previous_html else "")
        )

    @staticmethod
    def _extract_html(content: str) -> str:
        fenced = _HTML_FENCE.search(content)
        candidate = fenced.group(1).strip() if fenced else content.strip()
        start = candidate.lower().find("<!doctype")
        if start < 0:
            start = candidate.lower().find("<html")
        if start >= 0:
            candidate = candidate[start:]
            match = _DOCUMENT_END.search(candidate)
            if match:
                return candidate[: match.end()]
            return candidate
        return (
            "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>我的 AI 创作网页</title></head><body><main><p>"
            f"{escape(candidate)}"
            "</p></main></body></html>"
        )

    @staticmethod
    def _teaching_steps(prompt: str, document: str = "") -> list[str]:
        title = re.search(r"<(?:h1|title)\b[^>]*>(.*?)</(?:h1|title)>", document, re.I | re.S)
        buttons = re.findall(r"<button\b[^>]*>(.*?)</button>", document, re.I | re.S)
        clean = lambda value: re.sub(r"<[^>]*>", "", value).strip()[:40]
        heading = clean(title.group(1)) if title else prompt.strip()[:24] or "我的创作主题"
        actions = "、".join(clean(button) for button in buttons[:3] if clean(button))
        return [
            f"打开预览，检查《{heading}》的标题和内容是否表达了你的主题。",
            f"依次点击“{actions}”，检查每个按钮是否有正确的变化。" if actions else "观察内容卡片和配色，再试试页面中的可点击内容。",
            "需要修改时，直接描述具体位置和想要的变化；完成后下载网页和指导步骤，历史版本仍可找回。",
        ]
