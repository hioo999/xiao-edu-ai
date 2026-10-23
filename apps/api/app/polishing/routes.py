from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.agents.catalog import AgentCatalog, ManagedTool
from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.models.gateway import ModelGateway


DEFAULT_POLICIES = {
    "text": ("文字表达润色", "你是小学 3-6 年级 AI 课堂的提示词润色助手。把学生输入的一句话、关键词或主题，直接改写成清楚、自然、有画面感的中文表达。保留原意，不虚构具体事实，使用短句，适合小学生继续创作。\n学生原文：{input}"),
    "html": ("网页创作润色", "你是小学 3-6 年级 AI 网页创作课的提示词润色助手。把学生输入的主题，直接扩写成可用于生成网页的完整需求。必须包含：网页主题、主要版块、互动玩法、按钮或任务、儿童友好视觉风格。不要写代码。\n学生原文：{input}"),
    "image": ("图片创作润色", "你是小学 3-6 年级 AI 绘画课的提示词润色助手。把学生输入的主题，直接扩写成绘图提示词。必须包含：主体、场景、动作、画面细节、艺术风格、色彩和氛围，内容安全、童趣、不过度复杂。\n学生原文：{input}"),
    "music": ("音乐创作润色", "你是小学 3-6 年级 AI 音乐课的提示词润色助手。把学生输入的主题，直接扩写成歌曲生成提示词。必须包含：歌曲主题、情绪、节奏、乐器或风格、演唱氛围、适合小学生的歌词方向。\n学生原文：{input}"),
    "video": ("视频创作润色", "你是小学 3-6 年级 AI 视频课的提示词润色助手。把学生输入的主题，直接扩写成 5-10 秒短视频提示词。必须包含：主角、场景、动作变化、镜头运动、节奏、画面风格；避免危险、惊吓和成人化内容。\n学生原文：{input}"),
}

POLISH_OUTPUT_GUARDRAIL = """输出要求：
1. 只输出润色后的最终内容，不要解释、不要列步骤、不要加标题。
2. 禁止向学生提问，禁止输出“你想要”“是否需要”“可以告诉我”等追问句。
3. 如果学生只写了主题或关键词，也要主动补全为可直接生成的提示词。
4. 不要说自己是 AI，不要评价学生输入，不要输出多种方案。
5. 使用中文，控制在 80-180 字。"""


class PolishRequest(BaseModel):
    capability: str = Field(pattern="^(text|html|image|music|video)$")
    content: str = Field(min_length=1, max_length=2000)


class PolicyRequest(BaseModel):
    instruction: str = Field(min_length=20, max_length=8000)
    enabled: bool = True


def _tool_id(capability: str) -> str:
    return f"prompt-polish-{capability}"


def _policy(catalog: AgentCatalog, organization_id: str, capability: str) -> tuple[str, bool]:
    _, default_instruction = DEFAULT_POLICIES[capability]
    saved = next((item for item in catalog.list("skill", organization_id) if item.tool_id == _tool_id(capability)), None)
    return (saved.instruction if saved and saved.instruction else default_instruction, saved.enabled if saved else True)


def _compose_polish_prompt(instruction: str, content: str) -> str:
    if "{input}" in instruction:
        prompt = instruction.replace("{input}", content.strip())
    else:
        prompt = f"{instruction.strip()}\n学生原文：{content.strip()}"
    return f"{prompt.strip()}\n\n{POLISH_OUTPUT_GUARDRAIL}"


def create_polishing_router(auth: AuthService, gateway: ModelGateway, catalog: AgentCatalog, audit: AuditLog | None = None) -> APIRouter:
    router = APIRouter(prefix="/prompt-polish", tags=["prompt-polish"])
    session_dependency = require_session(auth)
    admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin")

    @router.get("/policies")
    def list_policies(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return {"policies": [{"capability": capability, "name": name, "instruction": _policy(catalog, session.organization_id, capability)[0], "enabled": _policy(catalog, session.organization_id, capability)[1]} for capability, (name, _) in DEFAULT_POLICIES.items()]}

    @router.put("/policies/{capability}")
    def save_policy(capability: str, request: PolicyRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        if capability not in DEFAULT_POLICIES:
            raise HTTPException(status_code=404, detail="unknown polishing capability")
        name, _ = DEFAULT_POLICIES[capability]
        catalog.save(ManagedTool(_tool_id(capability), "skill", name, capability, request.enabled, session.organization_id, request.instruction.strip()))
        if audit:
            audit.record(organization_id=session.organization_id, actor_id=session.user_id, action="prompt_polish.saved", target_type="prompt_polish", target_id=capability)
        return {"capability": capability, "name": name, "instruction": request.instruction.strip(), "enabled": request.enabled}

    @router.post("/policies/{capability}/reset")
    def reset_policy(capability: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        if capability not in DEFAULT_POLICIES:
            raise HTTPException(status_code=404, detail="unknown polishing capability")
        name, instruction = DEFAULT_POLICIES[capability]
        catalog.save(ManagedTool(_tool_id(capability), "skill", name, capability, True, session.organization_id, instruction))
        if audit:
            audit.record(organization_id=session.organization_id, actor_id=session.user_id, action="prompt_polish.reset", target_type="prompt_polish", target_id=capability)
        return {"capability": capability, "name": name, "instruction": instruction, "enabled": True}

    @router.post("")
    def polish(request: PolishRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, str]:
        instruction, enabled = _policy(catalog, session.organization_id, request.capability)
        if not enabled:
            raise HTTPException(status_code=403, detail="prompt polishing is disabled for this workspace")
        try:
            generated = gateway.generate_text(session.organization_id, _compose_polish_prompt(instruction, request.content))
        except LookupError as exc:
            raise HTTPException(status_code=503, detail="no text model is configured") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="prompt polishing failed") from exc
        return {"content": generated.content.strip(), "providerId": generated.provider_id, "modelId": generated.model_id}

    return router
