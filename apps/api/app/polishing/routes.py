from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.agents.catalog import AgentCatalog, ManagedTool
from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.models.gateway import ModelGateway


DEFAULT_POLICIES = {
    "text": ("文字表达润色", "把小学 3-6 年级学生写的想法润色成清楚、自然、有画面感的中文表达。保留原意，不虚构事实，使用短句。只输出润色后的内容，不解释。\n学生原文：{input}"),
    "html": ("网页创作润色", "把学生的网页想法改写成适合 AI 网页创作的任务说明。补全主题、页面内容、互动方式和儿童友好视觉风格；不写代码。只输出一段可直接生成网页的中文需求。\n学生原文：{input}"),
    "image": ("图片创作润色", "把学生的绘画想法整理成儿童友好的绘图提示词。包含主体、场景、动作、画风和画面氛围；保留原意，不过度复杂。只输出润色后的提示词。\n学生原文：{input}"),
    "music": ("音乐创作润色", "把学生的音乐想法整理成歌曲创作提示词。包含主题、情绪、节奏、演唱氛围和适合小学生的歌词方向。只输出润色后的提示词。\n学生原文：{input}"),
    "video": ("视频创作润色", "把学生的视频想法整理成安全、清楚的短视频提示词。包含主角、场景、动作、镜头感和节奏；不加入危险内容。只输出润色后的提示词。\n学生原文：{input}"),
}


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

    @router.post("")
    def polish(request: PolishRequest, session: SessionContext = Depends(session_dependency)) -> dict[str, str]:
        instruction, enabled = _policy(catalog, session.organization_id, request.capability)
        if not enabled:
            raise HTTPException(status_code=403, detail="prompt polishing is disabled for this workspace")
        try:
            generated = gateway.generate_text(session.organization_id, instruction.replace("{input}", request.content.strip()))
        except LookupError as exc:
            raise HTTPException(status_code=503, detail="no text model is configured") from exc
        except ValueError as exc:
            raise HTTPException(status_code=502, detail="prompt polishing failed") from exc
        return {"content": generated.content.strip(), "providerId": generated.provider_id, "modelId": generated.model_id}

    return router
