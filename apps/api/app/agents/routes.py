from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
import uuid

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.audit.service import AuditLog
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore
from apps.api.app.usage.service import QuotaExceeded, UsageLedger
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest, DispatchDenied, evaluate_dispatch

from .catalog import AgentCatalog, ManagedAgent, ManagedTool
from .expert_teams import ExpertTeam, run_expert_team
from .runtime import AgentRuntime


DEFAULT_AGENTS = (
    ManagedAgent("writing-coach", "写作小老师", "text", "3-6", True),
    ManagedAgent("painting-coach", "绘画灵感师", "image", "3-6", True),
    ManagedAgent("web-coach", "网页创作伙伴", "html", "4-6", True),
    ManagedAgent("video-coach", "视频故事导演", "video", "4-6", True),
)


class AgentDispatchPayload(BaseModel):
    agentId: str
    prompt: str = Field(min_length=1, max_length=4000)
    classroomOpen: bool = True
    featureEnabled: bool = True
    quotaAvailable: bool = True
    modelAvailable: bool = True
    allowForeign: bool = False
    modelRegion: str = "domestic"
    mcpApproved: bool = True


class ExpertTeamPayload(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    roles: list[str] = Field(min_length=1, max_length=6)
    prompt: str = Field(min_length=1, max_length=4000)


class ManagedToolRequest(BaseModel):
    toolId: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=80)
    capabilities: str = Field(default="", max_length=1000)
    enabled: bool = True
    instruction: str = Field(default="", max_length=8000)


class ManagedAgentRequest(BaseModel):
    agentId: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=80)
    capability: str = Field(pattern="^(text|image|video|music|html)$")
    gradeRange: str = Field(default="3-6", max_length=20)
    published: bool = False


def agent_payload(agent: ManagedAgent) -> dict[str, object]:
    return {
        "agentId": agent.agent_id,
        "name": agent.name,
        "capability": agent.capability,
        "gradeRange": agent.grade_range,
        "published": agent.published,
    }


def create_agent_router(
    auth_service: AuthService,
    catalog: AgentCatalog | None = None,
    audit_log: AuditLog | None = None,
    runtime: AgentRuntime | None = None,
    settings_store: SettingsStore | None = None,
    classrooms: AssistanceManager | None = None,
    usage: UsageLedger | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/agents", tags=["agents"])
    session_dependency = require_session(auth_service)
    creative_dependency = require_student_creative_access(session_dependency, settings_store, auth_service, classrooms) if settings_store else session_dependency
    admin_dependency = require_role(session_dependency, "platform_admin", "organization_admin")
    tools = catalog or AgentCatalog()

    def all_agents(organization_id: str | None) -> list[ManagedAgent]:
        overrides = {agent.agent_id: agent for agent in tools.list_agents(organization_id)}
        return [overrides.pop(agent.agent_id, agent) for agent in DEFAULT_AGENTS] + list(overrides.values())

    @router.get("/skills")
    def list_skills(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return {"skills": [tool.__dict__ for tool in tools.list("skill", session.organization_id)]}

    @router.post("/skills")
    def save_skill(request: ManagedToolRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        tool = tools.save(ManagedTool(request.toolId, "skill", request.name, request.capabilities, request.enabled, session.organization_id, request.instruction.strip()))
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="skill.saved", target_type="skill", target_id=tool.tool_id)
        return tool.__dict__

    @router.delete("/skills/{tool_id}")
    def delete_skill(tool_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, str]:
        try:
            tool = next((item for item in tools.list("skill", session.organization_id) if item.tool_id == tool_id), None)
            if tool is None or (session.role != "platform_admin" and tool.organization_id != session.organization_id):
                raise KeyError(tool_id)
            tools.delete("skill", tool_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="skill not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="skill.deleted", target_type="skill", target_id=tool_id)
        return {"toolId": tool_id, "status": "deleted"}

    @router.get("/mcp")
    def list_mcp(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return {"servers": [tool.__dict__ for tool in tools.list("mcp", session.organization_id)]}

    @router.post("/mcp")
    def save_mcp(request: ManagedToolRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        tool = tools.save(ManagedTool(request.toolId, "mcp", request.name, request.capabilities, request.enabled, session.organization_id, request.instruction.strip()))
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="mcp.saved", target_type="mcp", target_id=tool.tool_id)
        return tool.__dict__

    @router.delete("/mcp/{tool_id}")
    def delete_mcp(tool_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, str]:
        try:
            tool = next((item for item in tools.list("mcp", session.organization_id) if item.tool_id == tool_id), None)
            if tool is None or (session.role != "platform_admin" and tool.organization_id != session.organization_id):
                raise KeyError(tool_id)
            tools.delete("mcp", tool_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="MCP server not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="mcp.deleted", target_type="mcp", target_id=tool_id)
        return {"toolId": tool_id, "status": "deleted"}

    @router.get("")
    def list_agents(session: SessionContext = Depends(session_dependency)) -> dict[str, object]:
        agents = all_agents(session.organization_id)
        if session.role not in {"platform_admin", "organization_admin"}:
            agents = [agent for agent in agents if agent.published]
        return {"agents": [agent_payload(agent) for agent in agents]}

    @router.post("")
    def save_agent(request: ManagedAgentRequest, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        agent = tools.save_agent(ManagedAgent(request.agentId, request.name, request.capability, request.gradeRange, request.published, None if session.role == "platform_admin" else session.organization_id))
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="agent.saved", target_type="agent", target_id=agent.agent_id)
        return agent_payload(agent)

    @router.delete("/{agent_id}")
    def delete_agent(agent_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, str]:
        if any(agent.agent_id == agent_id for agent in DEFAULT_AGENTS):
            raise HTTPException(status_code=422, detail="default agent cannot be deleted")
        try:
            agent = next((item for item in tools.list_agents(None if session.role == "platform_admin" else session.organization_id) if item.agent_id == agent_id), None)
            if agent is None or (session.role != "platform_admin" and agent.organization_id != session.organization_id):
                raise KeyError(agent_id)
            tools.delete_agent(agent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="agent not found") from exc
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="agent.deleted", target_type="agent", target_id=agent_id)
        return {"agentId": agent_id, "status": "deleted"}

    @router.post("/dispatch")
    def dispatch_agent(payload: AgentDispatchPayload, session: SessionContext = Depends(creative_dependency)) -> dict[str, object]:
        agent = next((candidate for candidate in all_agents(session.organization_id) if candidate.agent_id == payload.agentId and candidate.published), None)
        if agent is None:
            raise HTTPException(status_code=404, detail="agent not found")
        try:
            evaluate_dispatch(AgentDispatchRequest(agent_kind=payload.agentId, capability=agent.capability, classroom_open=True, feature_enabled=True, quota_available=True, model_available=True, allow_foreign=False, model_region="domestic", mcp_approved=True))
        except DispatchDenied as exc:
            raise HTTPException(status_code=403, detail={"code": exc.code, "message": str(exc)}) from exc
        if runtime is None:
            raise HTTPException(status_code=503, detail="agent runtime is not configured")
        reservation_id = f"agent-{uuid.uuid4().hex}"
        quota_scope = None
        if usage is not None:
            user = auth_service.user_for_id(session.user_id)
            scopes = [("student", session.user_id)]
            if user and user.class_id:
                scopes.append(("class", user.class_id))
            scopes.append(("organization", session.organization_id))
            quota_scope = usage.configured_scope(scopes, "text")
        if quota_scope is not None:
            try:
                usage.reserve(quota_scope[0], quota_scope[1], "text", 1, reservation_id=reservation_id)
            except QuotaExceeded as exc:
                raise HTTPException(status_code=429, detail="generation quota exceeded") from exc
        try:
            result = runtime.execute(agent_id=agent.agent_id, capability=agent.capability, organization_id=session.organization_id, prompt=payload.prompt)
        except LookupError as exc:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise HTTPException(status_code=503, detail="agent runtime is unavailable") from exc
        except ValueError as exc:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise HTTPException(status_code=502, detail="agent returned an invalid result") from exc
        except Exception:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise
        if quota_scope is not None:
            usage.finalize(reservation_id)
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="agent.executed", target_type="agent", target_id=agent.agent_id)
        return {"agentId": agent.agent_id, "status": "completed", "message": "智能体已完成本次创作。", "ownerUserId": session.user_id, "content": result.html, "teachingSteps": result.teaching_steps}

    @router.post("/expert-teams/run")
    def execute_expert_team(payload: ExpertTeamPayload, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return run_expert_team(ExpertTeam(payload.name, tuple(payload.roles)), payload.prompt)

    return router
