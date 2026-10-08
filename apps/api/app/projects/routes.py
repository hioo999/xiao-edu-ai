from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore
from apps.api.app.classrooms.assistance import AssistanceManager
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest

from .catalog import CreativeAssetCatalog
from .html_service import HtmlWorkspaceService
from .versioning import current_version, download_html, download_zip


class HtmlGenerateRequest(BaseModel):
    prompt: str


def create_project_router(
    auth_service: AuthService,
    html_service: HtmlWorkspaceService,
    asset_catalog: CreativeAssetCatalog | None = None,
    settings_store: SettingsStore | None = None,
    classrooms: AssistanceManager | None = None,
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
        return {"projectId": project.project_id, "currentVersionId": project.current_version_id, "versions": [{"versionId": version.version_id, "title": version.title, "teachingSteps": version.teaching_steps} for version in project.versions]}

    @router.post("/{project_id}/html/versions/{version_id}/restore")
    def restore_html_project(project_id: str, version_id: str, session: SessionContext = Depends(creative_dependency)) -> dict[str, str]:
        try:
            html_service.restore(project_id, session.user_id, version_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="HTML version not found") from exc
        return {"projectId": project_id, "currentVersionId": version_id}

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
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
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
