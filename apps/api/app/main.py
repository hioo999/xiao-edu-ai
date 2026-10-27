from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from cryptography.fernet import Fernet

from .auth.routes import create_auth_router
from .auth.provisioning_routes import create_provisioning_router
from .auth.staff_lifecycle import StaffLifecycle
from .auth.staff_routes import create_staff_router
from .auth.service import AuthService, PostgresAuthService
from .models.registry import PostgresProviderRegistry, ProviderRegistry, SecretVault
from .models.environment import register_environment_providers
from .models.gateway import ModelGateway
from .models.calls import ModelCallLog, PostgresModelCallLog
from .models.routes import create_model_router
from .agents.routes import create_agent_router
from .agents.catalog import AgentCatalog, PostgresAgentCatalog
from .agents.runtime import AgentRuntime, agentscope_readiness, build_agent_runtime
from .media.jobs import MediaJobLedger, PostgresMediaJobLedger
from .media.routes import create_media_router
from .media.queue import build_media_job_queue
from .media.files import GeneratedFileAccess, create_generated_file_router
from .classrooms.assistance import AssistanceManager, PostgresAssistanceManager
from .classrooms.routes import create_classroom_router
from .projects.html_service import HtmlWorkspaceService, PostgresHtmlWorkspaceService
from .projects.html_dispatcher import HtmlModelDispatcher
from .agents.student_workspace import StudentAgentWorkspace
from .agents.student_runner import StudentAgentRunner
from .agents.student_routes import create_student_workspace_router
from .projects.routes import create_project_router
from .projects.catalog import CreativeAssetCatalog, PostgresCreativeAssetCatalog
from .projects.asset_routes import create_asset_router
from .sharing.links import PostgresShareLinkService, ShareLinkService
from .sharing.routes import create_share_router
from .projects.artifact_storage import WorkArtifactStore
from .projects.interactions import WorkInteractionStore
from .projects.deployments import DeploymentService
from .tenants.routes import create_tenant_router
from .courses.routes import create_course_router
from .courses.storage import CourseMaterialStore, PostgresCourseMaterialStore, build_course_blob_store
from .courses.catalog import CourseCatalog, PostgresCourseCatalog
from .courses.learning import LearningStore, PostgresLearningStore
from .courses.learning_routes import create_learning_router
from .parents.service import ParentPortalStore
from .parents.routes import create_parent_router
from .usage.service import PostgresUsageLedger, UsageLedger
from .usage.routes import create_usage_router
from .reports.service import PostgresReportService, ReportService
from .reports.routes import create_report_router
from .moderation.service import ModerationPolicyStore, ModerationService
from .moderation.routes import create_moderation_router
from .audit.service import AuditLog, PostgresAuditLog
from .audit.routes import create_audit_router
from .knowledge.catalog import KnowledgeCatalog, PostgresKnowledgeCatalog
from .knowledge.routes import create_knowledge_router
from .settings.routes import create_settings_router
from .settings.service import PostgresSettingsStore, SettingsStore
from .inspiration.catalog import InspirationCatalog, PostgresInspirationCatalog
from .inspiration.routes import create_inspiration_router
from .polishing.routes import create_polishing_router
from .core.security import build_login_rate_limiter, cors_allowed_origins
from .core.deployment import deployment_storage_from_env, storage_is_ready
from .core.metrics import MetricsRegistry, QueueBacklogMonitor
from .core.observability import configure_structured_logging
from packages.agent_runtime.src.tool_policy import McpServer
import os
import logging
import time


def create_app(
    auth_service: AuthService | None = None,
    provider_registry: ProviderRegistry | None = None,
    html_service: HtmlWorkspaceService | None = None,
    media_ledger: MediaJobLedger | None = None,
    model_gateway: ModelGateway | None = None,
    assistance_manager: AssistanceManager | None = None,
    course_material_store: CourseMaterialStore | None = None,
    course_catalog: CourseCatalog | None = None,
    usage_ledger: UsageLedger | None = None,
    report_service: ReportService | None = None,
    moderation_service: ModerationService | None = None,
    creative_asset_catalog: CreativeAssetCatalog | None = None,
    share_link_service: ShareLinkService | None = None,
    audit_log: AuditLog | None = None,
    model_call_log: ModelCallLog | None = None,
    knowledge_catalog: KnowledgeCatalog | None = None,
    agent_catalog: AgentCatalog | None = None,
    settings_store: SettingsStore | None = None,
    inspiration_catalog: InspirationCatalog | None = None,
    agent_runtime: AgentRuntime | None = None,
) -> FastAPI:
    configure_structured_logging()
    deployment_storage = deployment_storage_from_env()
    service = auth_service or (PostgresAuthService({}, deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else AuthService(users={}, storage_path=os.getenv("PLATFORM_DB_PATH")))
    provider_encryption_key = os.getenv("PROVIDER_ENCRYPTION_KEY")
    if provider_encryption_key:
        vault_key = provider_encryption_key.encode()
    elif os.getenv("PLATFORM_DB_PATH"):
        key_path = os.getenv("PROVIDER_ENCRYPTION_KEY_FILE") or f"{os.getenv('PLATFORM_DB_PATH')}.provider-key"
        if os.path.exists(key_path):
            vault_key = open(key_path, "rb").read().strip()
        else:
            vault_key = Fernet.generate_key()
            with open(key_path, "wb") as key_file:
                key_file.write(vault_key)
            os.chmod(key_path, 0o600)
    else:
        vault_key = Fernet.generate_key()
    models = provider_registry or (PostgresProviderRegistry(SecretVault(vault_key), deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else ProviderRegistry(SecretVault(vault_key), storage_path=os.getenv("PLATFORM_DB_PATH")))
    if provider_registry is None:
        register_environment_providers(models)
    media = media_ledger or (PostgresMediaJobLedger(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else MediaJobLedger(os.getenv("PLATFORM_DB_PATH")))
    calls = model_call_log or (PostgresModelCallLog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else ModelCallLog(os.getenv("PLATFORM_DB_PATH")))
    gateway = model_gateway or ModelGateway(models, call_log=calls)
    workspace = html_service or (PostgresHtmlWorkspaceService(HtmlModelDispatcher(gateway), deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else HtmlWorkspaceService(HtmlModelDispatcher(gateway), storage_path=os.getenv("PLATFORM_DB_PATH")))
    classrooms = assistance_manager or (PostgresAssistanceManager(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else AssistanceManager(os.getenv("PLATFORM_DB_PATH")))
    course_blob_store = None if course_material_store is not None else build_course_blob_store()
    course_materials = course_material_store or (PostgresCourseMaterialStore(os.getenv("COURSE_STORAGE_PATH", "var/course-materials"), deployment_storage.database_url, course_blob_store) if deployment_storage.mode == "postgres" and deployment_storage.database_url else CourseMaterialStore(os.getenv("COURSE_STORAGE_PATH", "var/course-materials"), course_blob_store))
    courses = course_catalog or (PostgresCourseCatalog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else CourseCatalog(os.getenv("PLATFORM_DB_PATH")))
    learning = PostgresLearningStore(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else LearningStore(os.getenv("LEARNING_STORAGE_PATH", "var/learning"))
    usage = usage_ledger or (PostgresUsageLedger(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else UsageLedger({}, os.getenv("PLATFORM_DB_PATH")))
    for student_id in service.student_user_ids():
        if not usage.is_configured("student", student_id, "credits"):
            usage.set_limit("student", student_id, "credits", 100)
    reports = report_service or (PostgresReportService(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else ReportService(storage_path=os.getenv("PLATFORM_DB_PATH")))
    moderation = moderation_service or ModerationService(store=ModerationPolicyStore(os.getenv("PLATFORM_DB_PATH")))
    creative_assets = creative_asset_catalog or (PostgresCreativeAssetCatalog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else CreativeAssetCatalog(os.getenv("PLATFORM_DB_PATH")))
    shares = share_link_service or (PostgresShareLinkService(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else ShareLinkService(os.getenv("PLATFORM_DB_PATH")))
    audit = audit_log or (PostgresAuditLog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else AuditLog(os.getenv("PLATFORM_DB_PATH")))
    knowledge = knowledge_catalog or (PostgresKnowledgeCatalog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else KnowledgeCatalog(os.getenv("PLATFORM_DB_PATH")))
    agent_tools = agent_catalog or (PostgresAgentCatalog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else AgentCatalog(os.getenv("PLATFORM_DB_PATH")))
    settings = settings_store or (PostgresSettingsStore(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else SettingsStore(os.getenv("PLATFORM_DB_PATH")))
    inspiration = inspiration_catalog or (PostgresInspirationCatalog(deployment_storage.database_url) if deployment_storage.mode == "postgres" and deployment_storage.database_url else InspirationCatalog(os.getenv("PLATFORM_DB_PATH")))
    login_rate_limiter = build_login_rate_limiter()
    generated_assets_path = os.getenv("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets")
    os.makedirs(generated_assets_path, exist_ok=True)
    application = FastAPI(title="星芽 AI 创作岛 API")
    generated_files = GeneratedFileAccess(service, media, creative_assets, classrooms)
    application.include_router(create_generated_file_router(service, generated_files))
    metrics = MetricsRegistry()
    media_queue = build_media_job_queue(media)
    queue_monitor = QueueBacklogMonitor(media_queue)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=cors_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Range"],
        expose_headers=["Content-Length", "Content-Range", "Accept-Ranges"],
    )

    @application.middleware("http")
    async def apply_security_controls(request: Request, call_next):
        started_at = time.perf_counter()
        if login_rate_limiter and request.url.path in {"/auth/login", "/auth/admin/login"}:
            client_host = request.client.host if request.client else "unknown"
            if not login_rate_limiter.allow(client_host):
                return JSONResponse(status_code=429, content={"detail": "too many login attempts"}, headers={"Retry-After": "300"})
        response = await call_next(request)
        metrics.increment("http.requests.total")
        metrics.increment(f"http.responses.{response.status_code // 100}xx")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        logging.getLogger("platform.request").info(
            "request completed",
            extra={"event": "http.request", "method": request.method, "path": request.url.path, "status_code": response.status_code, "duration_ms": round((time.perf_counter() - started_at) * 1000, 2)},
        )
        return response
    application.include_router(create_auth_router(service), prefix="/auth")
    staff_lifecycle = StaffLifecycle(service, classrooms, courses, audit)
    application.include_router(create_provisioning_router(service, audit, classrooms, staff_lifecycle, usage))
    application.include_router(create_staff_router(service, staff_lifecycle, audit))
    application.include_router(create_model_router(service, models, gateway, audit, calls, settings, usage, classrooms, knowledge, courses))
    def approved_mcp_servers(organization_id: str) -> list[McpServer]:
        servers: list[McpServer] = []
        for tool in agent_tools.list("mcp", organization_id):
            capabilities = {value.strip() for value in tool.capabilities.split(",") if value.strip()}
            servers.append(McpServer(tool.tool_id, tool.enabled, capabilities))
        return servers

    def enabled_skill_instructions(organization_id: str, capability: str) -> list[str]:
        instructions: list[str] = []
        for tool in agent_tools.list("skill", organization_id):
            capabilities = {value.strip() for value in tool.capabilities.split(",") if value.strip()}
            if tool.enabled and tool.instruction and (not capabilities or "*" in capabilities or capability in capabilities):
                instructions.append(tool.instruction)
        return instructions

    application.include_router(create_agent_router(service, agent_tools, audit, agent_runtime or build_agent_runtime(gateway, approved_mcp_servers, enabled_skill_instructions), settings, classrooms, usage))
    application.include_router(create_polishing_router(service, gateway, agent_tools, audit, usage))
    application.include_router(create_media_router(service, media, models, usage, creative_assets, settings, calls, classrooms, media_queue, audit))
    application.include_router(create_classroom_router(service, classrooms, audit, staff_lifecycle))
    work_artifacts = WorkArtifactStore(os.getenv("WORK_ARTIFACT_STORAGE_PATH", "var/work-artifacts"))
    application.include_router(create_student_workspace_router(service, agent_tools, StudentAgentWorkspace(os.getenv("PLATFORM_DB_PATH")), StudentAgentRunner(gateway, models, agent_tools, knowledge), models, creative_assets, work_artifacts, usage, settings, classrooms, media, media_queue, audit))
    application.include_router(create_project_router(service, workspace, creative_assets, settings, classrooms, work_artifacts, usage))
    work_interactions = WorkInteractionStore(os.getenv("WORK_INTERACTION_STORAGE_PATH", "var/work-interactions"))
    deployments = DeploymentService(os.getenv("DEPLOYMENT_STORAGE_PATH", "var/deployments"))
    application.include_router(create_asset_router(service, creative_assets, settings, audit, classrooms, work_artifacts, work_interactions, deployments, html_service=workspace))
    application.include_router(create_share_router(service, shares, creative_assets, artifact_store=work_artifacts, classrooms=classrooms, generated_files=generated_files))
    application.include_router(create_tenant_router(service))
    application.include_router(create_course_router(service, course_materials, courses, audit, classrooms, staff_lifecycle))
    application.include_router(create_learning_router(service, courses, learning, audit, reports, classrooms))
    parent_store = ParentPortalStore(os.getenv("PLATFORM_DB_PATH"))
    application.include_router(create_parent_router(service, parent_store, courses, audit, learning, creative_assets, classrooms))
    application.include_router(create_usage_router(service, usage, audit))
    application.include_router(create_report_router(service, reports, classrooms))
    application.include_router(create_moderation_router(service, moderation))
    application.include_router(create_audit_router(service, audit))
    application.include_router(create_knowledge_router(service, knowledge, classrooms, courses))
    application.include_router(create_settings_router(service, settings, audit))
    application.include_router(create_inspiration_router(service, inspiration, audit, work_artifacts))

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/health/ready")
    def readiness() -> dict[str, str]:
        if storage_is_ready(deployment_storage, os.getenv("PLATFORM_DB_PATH", "var/platform.db")):
            return {"status": "ready", "storage": "ok"}
        raise HTTPException(status_code=503, detail="platform storage is unavailable")

    @application.get("/health/metrics")
    def metrics_endpoint() -> dict[str, object]:
        return {"metrics": metrics.snapshot(), "queue": queue_monitor.status(), "alerts": queue_monitor.alerts()}

    @application.get("/health/alerts")
    def alerts_endpoint() -> dict[str, object]:
        return {"alerts": queue_monitor.alerts()}

    @application.get("/health/agents")
    def agent_readiness() -> dict[str, object]:
        return agentscope_readiness()

    @application.get("/health/media-worker")
    def media_worker_readiness() -> dict[str, object]:
        if media_queue is None:
            return {"workerReady": False, "reason": "media queue is not configured"}
        status = getattr(media_queue, "worker_status", None)
        if not callable(status):
            return {"workerReady": False, "reason": "media queue does not expose worker status"}
        return status()

    return application
app = create_app()
