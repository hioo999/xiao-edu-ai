from typing import Literal
import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.models.registry import ModelCapability
from apps.api.app.projects.html_dispatcher import HtmlModelDispatcher
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.usage.charging import generation_charge
from apps.api.app.usage.service import QuotaExceeded
from packages.sandbox.src.html_sanitizer import prepare_interactive_html


class StudentSettings(BaseModel):
    capability: Literal["text", "html", "image", "music", "video"] = "text"
    skillIds: list[str] = Field(default_factory=list, max_length=20)
    mcpIds: list[str] = Field(default_factory=list, max_length=10)
    knowledgeIds: list[str] = Field(default_factory=list, max_length=10)
    runtime: Literal["gateway", "agentscope"] = "gateway"


class ChatMessage(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def create_student_workspace_router(auth, catalog, workspace, runner, providers, assets, artifacts, usage, settings, classrooms, media, queue, audit):
    router = APIRouter(prefix="/student-agents", tags=["student-agents"])
    student = require_role(require_session(auth), "student")
    creative = require_student_creative_access(student, settings, auth, classrooms)

    def owned_agent(agent_id, session):
        agent = next((item for item in catalog.list_student_agents(session.organization_id, session.user_id) if item.agent_id == agent_id), None)
        if agent is None:
            raise HTTPException(status_code=404, detail="智能体不存在或无权访问。")
        return agent

    def conversation(session_id, session):
        try:
            current = workspace.get(session_id, session.organization_id, session.user_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="对话不存在。") from exc
        owned_agent(current["agentId"], session)
        return current

    @router.get("/options")
    def options(session=Depends(student)):
        result = runner.options(session)
        result["models"] = [{"providerId": provider.provider_id, "modelId": provider.model_id, "name": provider.model_id or provider.provider_id, "providerKind": provider.provider_kind} for provider in providers.resolve_candidates(session.organization_id, ModelCapability.TEXT, allow_foreign=True)]
        return result

    @router.get("/{agent_id}/settings")
    def get_settings(agent_id: str, session=Depends(student)):
        owned_agent(agent_id, session)
        return workspace.settings(agent_id)

    @router.put("/{agent_id}/settings")
    def save_settings(agent_id: str, request: StudentSettings, session=Depends(student)):
        owned_agent(agent_id, session)
        try:
            runner.validate(session, request.model_dump())
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return workspace.save_settings(agent_id, request.model_dump())

    @router.get("/{agent_id}/sessions")
    def list_sessions(agent_id: str, session=Depends(student)):
        owned_agent(agent_id, session)
        return {"sessions": workspace.list_sessions(session.organization_id, session.user_id, agent_id)}

    @router.post("/{agent_id}/sessions")
    def create_session(agent_id: str, session=Depends(student)):
        agent = owned_agent(agent_id, session)
        if len(workspace.list_sessions(session.organization_id, session.user_id, agent_id)) >= 100:
            raise HTTPException(status_code=422, detail="这个智能体已有100个对话，请继续已有对话。")
        return workspace.create(session.organization_id, session.user_id, agent_id, agent.name)

    @router.get("/sessions/{session_id}")
    def get_session(session_id: str, session=Depends(student)):
        return conversation(session_id, session)

    @router.post("/sessions/{session_id}/messages")
    def send(session_id: str, request: ChatMessage, session=Depends(creative)):
        if not request.text.strip():
            raise HTTPException(status_code=422, detail="请先输入想完成的任务。")
        current = conversation(session_id, session)
        agent = owned_agent(current["agentId"], session)
        configuration = workspace.settings(agent.agent_id)
        try:
            with workspace.conversation_lock(session_id), generation_charge(auth, usage, session):
                current = conversation(session_id, session)
                if len(current["messages"]) >= 200:
                    raise HTTPException(status_code=422, detail="这个对话已满，请新建对话。")
                content = runner.run(session, agent, configuration, current["messages"], request.text.strip())
                capability = configuration["capability"]
                answer = {"text": content, "capability": capability, "assetId": None, "jobId": None, "html": ""}
                if capability in {"text", "html"}:
                    html = prepare_interactive_html(HtmlModelDispatcher._extract_html(content)) if capability == "html" else ""
                    asset = assets.create(project_id=session_id, organization_id=session.organization_id, owner_user_id=session.user_id, kind="webpage" if html else "text", title=f"{agent.name} · {request.text[:40]}", preview_url="", prompt=request.text, content="" if html else content)
                    if html:
                        artifacts.save(asset.asset_id, session.organization_id, "my-webpage.html", "text/html", html.encode("utf-8"))
                        answer.update(text="网页已生成并保存，可以在下方预览。", html=html)
                    answer["assetId"] = asset.asset_id
                else:
                    candidates = providers.resolve_candidates(session.organization_id, ModelCapability(capability), allow_foreign=True)
                    if not candidates:
                        raise HTTPException(status_code=503, detail="老师还没有开启这种创作能力。")
                    job = media.create(capability, session.user_id, organization_id=session.organization_id, prompt=content[:4000], project_id=session_id, provider_id=candidates[0].provider_id, title=agent.name, lyrics=content if capability == "music" else "", video_duration_seconds=settings.get(session.organization_id).video_duration_seconds if capability == "video" else None)
                    user = auth.user_for_id(session.user_id)
                    scopes = [("student", session.user_id), *([("class", user.class_id)] if user and user.class_id else []), ("organization", session.organization_id)]
                    reserved = None
                    try:
                        reserved = usage.reserve_with_fallback(scopes, capability, 1, reservation_id=job.job_id)
                        queue.enqueue(job.job_id)
                    except Exception:
                        if reserved:
                            usage.release(job.job_id)
                        media.fail_after_queue(job.job_id, "任务提交失败，请重新尝试。")
                        raise
                    answer.update(text="创作任务已提交，完成后会显示在这里并保存到作品夹。", jobId=job.job_id, creationPrompt=content)
                updated = workspace.append(session_id, session.organization_id, session.user_id, request.text.strip(), answer)
            audit.record(organization_id=session.organization_id, actor_id=session.user_id, action="student_agent.executed", target_type="student_agent", target_id=agent.agent_id)
            return {"conversation": updated, "message": answer}
        except QuotaExceeded as exc:
            raise HTTPException(status_code=429, detail="创作积分不足，请联系老师。") from exc
        except BlockingIOError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="所选工具或资料未获授权，请重新选择。") from exc
        except (LookupError, ValueError, RuntimeError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=502, detail="智能体未完成本次任务，请检查老师开启的模型和工具后重试。") from exc

    return router
