from __future__ import annotations

from html import escape
import re

from apps.api.app.models.gateway import ModelGateway
from packages.agent_runtime.src.dispatcher import AgentExecutionResult
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest, evaluate_dispatch


_HTML_FENCE = re.compile(r"```(?:html)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_DOCUMENT_END = re.compile(r"</html\s*>", re.IGNORECASE)


class HtmlModelDispatcher:
    """Turns an organization-scoped text model response into a safe HTML artifact."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    def dispatch(self, policy: AgentDispatchRequest, prompt: str, *, organization_id: str) -> AgentExecutionResult:
        evaluate_dispatch(policy)
        generated = self._gateway.generate_text(organization_id, self._instruction(prompt))
        return AgentExecutionResult(
            agent_kind=policy.agent_kind,
            html=self._extract_html(generated.content),
            teaching_steps=self._teaching_steps(prompt),
        )

    @staticmethod
    def _instruction(prompt: str) -> str:
        return (
            "你是一名面向小学 3-6 年级学生的网页创作老师。"
            "根据学生的需求生成一个完整、单文件、中文网页。"
            "只输出 HTML 文档，不要解释，不要 Markdown 代码围栏。"
            "禁止使用 script、外部链接、外部图片、iframe 或表单。\n\n"
            f"学生需求：{prompt.strip()}"
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
    def _teaching_steps(prompt: str) -> list[str]:
        return [
            f"先从“{prompt.strip()[:24] or '我的创作主题'}”提取页面主题和主要内容。",
            "观察标题、内容卡片和配色如何帮助读者理解主题。",
            "预览后，用自然语言告诉 AI 你想调整的内容或风格。",
        ]
