import httpx
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore

from .registry import ModelCapability, ModelProvider, ProviderRegistry
from .gateway import ModelGateway
from apps.api.app.audit.service import AuditLog
from .calls import ModelCallLog
from apps.api.app.usage.service import QuotaExceeded, UsageLedger
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.retrieval import build_grounded_prompt
from apps.api.app.knowledge.scopes import KnowledgeScope
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.courses.catalog import CourseCatalog


class ProviderRequest(BaseModel):
    providerId: str
    capability: ModelCapability
    region: str
    apiKey: str | None = None
    providerKind: str = "custom"
    modelId: str = ""
    baseUrl: str = "https://api.deepseek.com"
    priority: int = 100
    enabled: bool = True
    modelCatalog: list[str] | None = None


class TextGenerationRequest(BaseModel):
    prompt: str
    courseId: str | None = None
    providerId: str | None = None


def create_model_router(auth_service: AuthService, registry: ProviderRegistry, gateway: ModelGateway, audit_log: AuditLog | None = None, call_log: ModelCallLog | None = None, settings_store: SettingsStore | None = None, usage: UsageLedger | None = None, classrooms: AssistanceManager | None = None, knowledge_catalog: KnowledgeCatalog | None = None, course_catalog: CourseCatalog | None = None) -> APIRouter:
    router = APIRouter(prefix="/models", tags=["models"])
    session_dependency = require_session(auth_service)
    admin_dependency = require_role(
        session_dependency,
        "platform_admin",
        "organization_admin",
    )
    creative_dependency = require_student_creative_access(session_dependency, settings_store, auth_service, classrooms) if settings_store else session_dependency
    access = TeachingAccess(auth_service, classrooms)

    @router.post("/text/generate")
    def generate_text(
        request: TextGenerationRequest,
        session: SessionContext = Depends(creative_dependency),
    ) -> dict[str, str]:
        if not request.prompt.strip():
            raise HTTPException(status_code=422, detail="prompt is required")
        if request.courseId:
            authorized = False
            if course_catalog is not None:
                try:
                    course = course_catalog.get(request.courseId, session.organization_id)
                    if session.role == "student":
                        user = auth_service.user_for_id(session.user_id)
                        authorized = bool(user and user.class_id and any(item.course_id == course.course_id for item in course_catalog.list_for_class(user.class_id, session.organization_id)))
                    elif session.role == "teacher":
                        authorized = course.author_user_id == session.user_id or any(item.course_id == course.course_id for class_id in access.teacher_class_ids(session) for item in course_catalog.list_for_class(class_id, session.organization_id))
                    else:
                        authorized = True
                except (KeyError, PermissionError):
                    pass
            if not authorized:
                raise HTTPException(status_code=403, detail="course context access denied")

        def allowed_document(document) -> bool:
            if document.scope is KnowledgeScope.PLATFORM:
                return True
            if document.organization_id not in (None, session.organization_id):
                return False
            if document.scope is KnowledgeScope.ORGANIZATION:
                return document.scope_id == session.organization_id
            if document.scope is KnowledgeScope.COURSE:
                return bool(request.courseId and document.scope_id == request.courseId)
            return document.scope_id == session.user_id and document.scope.value == session.role

        reservation_id = f"text-{uuid.uuid4().hex}"
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
            grounded_prompt = build_grounded_prompt(knowledge_catalog, organization_id=session.organization_id, course_id=request.courseId, prompt=request.prompt, document_filter=allowed_document)
            if request.providerId:
                generated = gateway.generate_text(session.organization_id, grounded_prompt, provider_id=request.providerId)
            else:
                generated = gateway.generate_text(session.organization_id, grounded_prompt)
        except LookupError as exc:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise HTTPException(status_code=503, detail="no text model is configured") from exc
        except ValueError as exc:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise HTTPException(status_code=502, detail="text model is unavailable") from exc
        except Exception:
            if quota_scope is not None:
                usage.release(reservation_id)
            raise
        if quota_scope is not None:
            usage.finalize(reservation_id)
        return {"content": generated.content, "providerId": generated.provider_id, "modelId": generated.model_id}

    @router.get("/text/available")
    def available_text_models(session: SessionContext = Depends(creative_dependency)) -> dict[str, object]:
        models = []
        for provider in registry.resolve_candidates(session.organization_id, ModelCapability.TEXT):
            models.append({
                "providerId": provider.provider_id,
                "modelId": provider.model_id,
                "name": provider.model_id or provider.provider_id,
                "providerKind": provider.provider_kind,
            })
        return {"models": models}

    @router.get("/providers")
    def list_providers(
        session: SessionContext = Depends(admin_dependency),
    ) -> dict[str, list[dict[str, object]]]:
        return {
            "providers": [provider.__dict__ for provider in registry.public_providers(session.organization_id)]
        }

    @router.get("/calls/summary")
    def call_summary(session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return {"calls": call_log.summary(session.organization_id) if call_log else []}

    @router.get("/calls")
    def recent_calls(limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0), provider_id: str | None = Query(default=None, alias="providerId"), capability: str | None = None, outcome: str | None = None, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        return {"calls": [call.__dict__ for call in call_log.recent(session.organization_id, limit=limit, offset=offset, provider_id=provider_id, capability=capability, outcome=outcome)] if call_log else [], "offset": offset, "limit": limit}

    @router.post("/providers/{provider_id}/test")
    def test_provider(provider_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        try:
            provider = registry.provider(provider_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="provider not found") from exc
        if session.role != "platform_admin" and provider.organization_id != session.organization_id:
            raise HTTPException(status_code=403, detail="provider access denied")
        if not provider.model_id or not provider.base_url:
            raise HTTPException(status_code=422, detail="请先填写模型名称和 Base URL。")
        try:
            check = gateway.test_connection(provider_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=502, detail=f"服务商拒绝连接（HTTP {exc.response.status_code}）。请确认 API Key、模型和项目空间是否一致。") from exc
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail="无法连接服务商，请检查 Base URL 或网络连通性。") from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="服务商返回了无法识别的响应。请检查模型名称和接口类型。") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="连接服务商时出现未知错误，请稍后重试。") from exc
        return {"providerId": provider.provider_id, "status": check.status, "modelId": provider.model_id, "message": check.message}

    @router.get("/providers/{provider_id}/available-models")
    def available_models(provider_id: str, session: SessionContext = Depends(admin_dependency)) -> dict[str, object]:
        try:
            provider = registry.provider(provider_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="provider not found") from exc
        if session.role != "platform_admin" and provider.organization_id != session.organization_id:
            raise HTTPException(status_code=403, detail="provider access denied")
        try:
            models = gateway.discover_models(provider_id)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=502, detail="provider returned an invalid model list") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail="unable to refresh provider model list") from exc
        return {"providerId": provider_id, "models": [{"id": model.model_id, "name": model.display_name} for model in models]}

    @router.post("/providers")
    def register_provider(
        request: ProviderRequest,
        session: SessionContext = Depends(admin_dependency),
    ) -> dict[str, str]:
        if request.region not in {"domestic", "foreign"}:
            raise HTTPException(status_code=422, detail="unsupported provider region")
        if session.role != "platform_admin":
            try:
                existing = registry.provider(request.providerId)
            except KeyError:
                existing = None
            if existing is not None and existing.organization_id != session.organization_id:
                raise HTTPException(status_code=403, detail="provider access denied")
        if request.apiKey is None:
            try:
                if session.role != "platform_admin" and registry.provider(request.providerId).organization_id != session.organization_id:
                    raise PermissionError("provider access denied")
                api_key = registry.secret_key(request.providerId)
            except KeyError as exc:
                raise HTTPException(status_code=422, detail="apiKey is required for a new provider") from exc
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail="provider access denied") from exc
        elif not request.apiKey.strip():
            raise HTTPException(status_code=422, detail="apiKey cannot be empty")
        else:
            api_key = request.apiKey
        try:
            existing_catalog = registry.provider(request.providerId).model_catalog
        except KeyError:
            existing_catalog = ()
        registry.register(
            ModelProvider(
                provider_id=request.providerId,
                organization_id=None if session.role == "platform_admin" else session.organization_id,
                capability=request.capability,
                region=request.region,
                priority=request.priority,
                api_key=api_key,
                provider_kind=request.providerKind,
                model_id=request.modelId,
                base_url=request.baseUrl,
                enabled=request.enabled,
                model_catalog=tuple(dict.fromkeys(item.strip() for item in (request.modelCatalog if request.modelCatalog is not None else existing_catalog) if item.strip())),
            )
        )
        if audit_log is not None:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="provider.saved", target_type="model_provider", target_id=request.providerId)
        return {"providerId": request.providerId, "status": "registered"}

    @router.delete("/providers/{provider_id}")
    def delete_provider(
        provider_id: str,
        session: SessionContext = Depends(admin_dependency),
    ) -> dict[str, str]:
        try:
            registry.delete(provider_id, None if session.role == "platform_admin" else session.organization_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="provider not found") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="provider access denied") from exc
        if audit_log is not None:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="provider.deleted", target_type="model_provider", target_id=provider_id)
        return {"providerId": provider_id, "status": "deleted"}

    return router
