from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
import httpx

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.usage.charging import generation_charge
from apps.api.app.usage.service import QuotaExceeded, UsageLedger
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest

from .catalog import CreativeAssetCatalog
from .artifact_storage import WorkArtifactStore
from .html_service import HtmlWorkspaceService
from .versioning import current_version, download_html, download_zip


class HtmlGenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)


def create_project_router(
    auth_service: AuthService,
    html_service: HtmlWorkspaceService,
    asset_catalog: CreativeAssetCatalog | None = None,
    settings_store: SettingsStore | None = None,
    classrooms: AssistanceManager | None = None,
    artifact_store: WorkArtifactStore | None = None,
    usage: UsageLedger | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/projects", tags=["projects"])
    student_dependency = require_role(require_session(auth_service), "student")
    creative_dependency = require_student_creative_access(student_dependency, settings_store, auth_service, classrooms) if settings_store else student_dependency

    def owned_project(project_id: str, session: SessionContext):
        try:
            return html_service.get(project_id, session.user_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="project access denied") from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="HTML project not found") from exc

    @router.get("/html")
    def list_html_projects(session: SessionContext = Depends(creative_dependency)) -> dict[str, list[dict[str, object]]]:
        projects = []
        for project in html_service.list_for_owner(session.user_id):
            version = current_version(project) if project.current_version_id else None
            projects.append({"projectId": project.project_id, "title": version.title if version else "未命名网页", "currentVersionId": project.current_version_id})
        return {"projects": projects}

    @router.get("/{project_id}/html")
    def get_html_project(project_id: str, session: SessionContext = Depends(creative_dependency)) -> dict[str, object]:
        project = owned_project(project_id, session)
        version = current_version(project)
        return {
            "projectId": project.project_id,
            "currentVersionId": project.current_version_id,
            "currentVersion": {"versionId": version.version_id, "title": version.title, "html": version.html, "teachingSteps": version.teaching_steps},
            "versions": [{"versionId": item.version_id, "title": item.title, "teachingSteps": item.teaching_steps} for item in project.versions],
        }

    @router.post("/{project_id}/html/versions/{version_id}/restore")
    def restore_html_project(project_id: str, version_id: str, session: SessionContext = Depends(creative_dependency)) -> dict[str, str]:
        try:
            html_service.restore(project_id, session.user_id, version_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail="project access denied") from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="HTML version not found") from exc
        return {"projectId": project_id, "currentVersionId": version_id}

    @router.get("/{project_id}/html/versions/{version_id}")
    def get_html_version(project_id: str, version_id: str, session: SessionContext = Depends(creative_dependency)) -> dict[str, object]:
        project = owned_project(project_id, session)
        version = next((item for item in project.versions if item.version_id == version_id), None)
        if version is None:
            raise HTTPException(status_code=404, detail="HTML version not found")
        return {"projectId": project.project_id, "currentVersion": {"versionId": version.version_id, "title": version.title, "html": version.html, "teachingSteps": version.teaching_steps}}

    @router.get("/{project_id}/html/download")
    def download_current_html(project_id: str, session: SessionContext = Depends(creative_dependency)) -> Response:
        return Response(download_html(owned_project(project_id, session)), media_type="text/html", headers={"Content-Disposition": 'attachment; filename="my-webpage.html"'})

    @router.get("/{project_id}/html/download.zip")
    def download_current_html_zip(project_id: str, session: SessionContext = Depends(creative_dependency)) -> Response:
        return Response(download_zip(owned_project(project_id, session)), media_type="application/zip", headers={"Content-Disposition": 'attachment; filename="my-webpage.zip"'})

    @router.post("/{project_id}/html/generate")
    def generate_html(
        project_id: str,
        request: HtmlGenerateRequest,
        session: SessionContext = Depends(creative_dependency),
    ) -> dict[str, object]:
        if not request.prompt.strip():
            raise HTTPException(status_code=422, detail="prompt is required")
        try:
            with generation_charge(auth_service, usage, session):
                project = html_service.generate(
                    project_id=project_id,
                    owner_user_id=session.user_id,
                    organization_id=session.organization_id,
                    prompt=request.prompt,
                    policy=AgentDispatchRequest(
                        agent_kind="html",
                        capability="text",
                        classroom_open=True,
                        feature_enabled=True,
                        quota_available=True,
                        model_available=True,
                        allow_foreign=False,
                        model_region="domestic",
                        mcp_approved=True,
                    ),
                )
        except QuotaExceeded as exc:
            raise HTTPException(status_code=429, detail="本次创作积分不足，请联系老师。") from exc
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(status_code=502, detail="网页生成没有完成，请稍后重试。") from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=503, detail="老师还没有开启可用的网页创作模型。") from exc
        version = current_version(project)
        asset_id = None
        if asset_catalog is not None:
            asset = asset_catalog.create(
                project_id=project.project_id,
                organization_id=session.organization_id,
                owner_user_id=session.user_id,
                kind="webpage",
                title=version.title,
                preview_url="",
                prompt=request.prompt,
            )
            asset_id = asset.asset_id
            if artifact_store is not None:
                artifact_store.save(asset.asset_id, session.organization_id, "my-webpage.html", "text/html", version.html.encode("utf-8"))
        return {
            "projectId": project.project_id,
            "assetId": asset_id,
            "currentVersion": {
                "versionId": version.version_id,
                "title": version.title,
                "html": version.html,
                "teachingSteps": version.teaching_steps,
            },
        }

    return router
