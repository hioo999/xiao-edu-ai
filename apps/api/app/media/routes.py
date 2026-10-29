from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pathlib import Path
import os
import secrets
import uuid
from typing import Literal
from pydantic import BaseModel, Field

from apps.api.app.auth.dependencies import require_role, require_session
from apps.api.app.auth.access import TeachingAccess
from apps.api.app.auth.service import AuthService, SessionContext
from apps.api.app.settings.dependencies import require_student_creative_access
from apps.api.app.settings.service import SettingsStore

from .jobs import JobState, MediaJobLedger
from .queue import MediaJobQueue
from .reference_images import reference_folder, reference_path, valid_reference_payload
from apps.api.app.models.registry import ModelCapability, ProviderRegistry
from apps.api.app.projects.catalog import CreativeAssetCatalog
from apps.api.app.usage.service import QuotaExceeded, UsageLedger
from apps.api.app.usage.credits import MEDIA_CREDITS, reserve_media_credits
from apps.api.app.models.calls import ModelCallLog
from apps.api.app.classrooms.assistance import AssistanceManager
from apps.api.app.audit.service import AuditLog


class MediaJobRequest(BaseModel):
    kind: str = Field(pattern="^(image|video|music|voice)$")
    prompt: str = Field(min_length=1, max_length=4000)
    projectId: str | None = None
    referenceImageUrl: str | None = Field(default=None, max_length=500)
    title: str = Field(default="", max_length=120)
    lyrics: str = Field(default="", max_length=10000)
    aspectRatio: Literal["1:1", "16:9", "9:16", "3:4", "4:3"] | None = None
    videoDurationSeconds: Literal[5, 10] | None = None


class MediaBatchRequest(MediaJobRequest):
    count: int = Field(default=4, ge=2, le=4)


class MediaWorkerUpdate(BaseModel):
    state: JobState = JobState.RUNNING
    progress: int = Field(default=0, ge=0, le=100)
    assetId: str | None = None
    previewUrl: str = Field(default="", max_length=2000)
    title: str | None = Field(default=None, min_length=1, max_length=120)
    error: str | None = None


def create_media_router(
    auth_service: AuthService,
    ledger: MediaJobLedger,
    providers: ProviderRegistry | None = None,
    usage: UsageLedger | None = None,
    asset_catalog: CreativeAssetCatalog | None = None,
    settings_store: SettingsStore | None = None,
    call_log: ModelCallLog | None = None,
    classrooms: AssistanceManager | None = None,
    queue: MediaJobQueue | None = None,
    audit_log: AuditLog | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/media/jobs", tags=["media"])
    session_dependency = require_session(auth_service)
    creative_dependency = require_student_creative_access(session_dependency, settings_store, auth_service, classrooms) if settings_store else session_dependency
    access = TeachingAccess(auth_service, classrooms)

    def require_job_access(job, session: SessionContext) -> None:
        if job.organization_id != session.organization_id:
            raise HTTPException(status_code=404, detail="media job not found")
        if session.role == "teacher" and job.owner_user_id != session.user_id:
            access.require_student(session, job.owner_user_id)

    def belongs_to_organization(job_id: str, session: SessionContext) -> bool:
        try:
            return ledger.get(job_id).organization_id == session.organization_id
        except KeyError:
            return False

    @router.post("", status_code=status.HTTP_202_ACCEPTED)
    def submit_job(request: MediaJobRequest, session: SessionContext = Depends(creative_dependency)) -> dict[str, str]:
        capability = {"image": ModelCapability.IMAGE, "video": ModelCapability.VIDEO, "music": ModelCapability.MUSIC, "voice": ModelCapability.TEXT_TO_SPEECH}[request.kind]
        provider_id = None
        if providers is not None:
            candidates = providers.resolve_candidates(session.organization_id, capability)
            provider_id = candidates[0].provider_id if candidates else None
        if request.referenceImageUrl and request.kind not in {"image", "video"}:
            raise HTTPException(status_code=422, detail="reference image is only supported for image and video creation")
        if request.aspectRatio and request.kind not in {"image", "video"}:
            raise HTTPException(status_code=422, detail="aspect ratio is only supported for image and video creation")
        if request.referenceImageUrl:
            try:
                reference_path(request.referenceImageUrl, session.organization_id, session.user_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        video_duration_seconds = None
        if request.kind == "video":
            video_duration_seconds = request.videoDurationSeconds or (settings_store.get(session.organization_id).video_duration_seconds if settings_store else 5)
        job = ledger.create(request.kind, session.user_id, organization_id=session.organization_id, prompt=request.prompt, project_id=request.projectId, reference_image_url=request.referenceImageUrl, provider_id=provider_id, title=request.title, lyrics=request.lyrics, aspect_ratio=request.aspectRatio, video_duration_seconds=video_duration_seconds)
        quota_scope = None
        if usage:
            user = auth_service.user_for_id(session.user_id)
            scopes = [("student", session.user_id)]
            if user and user.class_id:
                scopes.append(("class", user.class_id))
            scopes.append(("organization", session.organization_id))
            quota_scope = usage.configured_scope(scopes, request.kind)
        if quota_scope is not None:
            try:
                usage.reserve(quota_scope[0], quota_scope[1], request.kind, 1, reservation_id=job.job_id)
            except QuotaExceeded as exc:
                ledger.fail_after_queue(job.job_id, "quota exceeded")
                raise HTTPException(status_code=429, detail="generation quota exceeded") from exc
        try:
            reserve_media_credits(usage, session.user_id, request.kind, job.job_id, video_duration_seconds)
            if queue:
                queue.enqueue(job.job_id)
        except QuotaExceeded as exc:
            if usage:
                usage.release(job.job_id)
            ledger.fail_after_queue(job.job_id, "credits exceeded")
            raise HTTPException(status_code=429, detail="创作积分不足，请联系老师。") from exc
        except Exception:
            if usage:
                usage.release(job.job_id)
                usage.release(f"{job.job_id}-credits")
            ledger.fail_after_queue(job.job_id, "queue unavailable")
            raise
        return {"jobId": job.job_id, "state": job.state, "statusUrl": f"/media/jobs/{job.job_id}"}

    @router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
    def submit_batch(request: MediaBatchRequest, session: SessionContext = Depends(creative_dependency)) -> dict[str, object]:
        """Create independent image candidates through the normal accounting path."""
        if request.kind != "image":
            raise HTTPException(status_code=422, detail="batch creation currently supports image candidates only")
        batch_id = f"batch-{uuid.uuid4().hex[:12]}"
        single = request.model_dump(exclude={"count"})
        jobs = []
        for index in range(request.count):
            candidate = MediaJobRequest(**single)
            candidate.title = f"{candidate.title or '图片作品'} · 候选 {index + 1}"
            jobs.append(submit_job(candidate, session))
        return {"batchId": batch_id, "jobs": jobs}

    @router.post("/reference-images")
    async def upload_reference_image(file: UploadFile = File(...), session: SessionContext = Depends(creative_dependency)) -> dict[str, str]:
        filename = file.filename or "reference-image"
        extension = Path(filename).suffix.lower()
        content = await file.read(5 * 1024 * 1024 + 1)
        if not valid_reference_payload(extension, content):
            raise HTTPException(status_code=422, detail="reference image must be a valid PNG, JPG, or WEBP under 5 MB")
        try:
            storage_root = reference_folder(session.organization_id, session.user_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="reference image storage is unavailable") from exc
        storage_root.mkdir(parents=True, exist_ok=True)
        stored_name = f"{secrets.token_urlsafe(10)}{extension}"
        (storage_root / stored_name).write_bytes(content)
        public_base = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000").rstrip("/")
        return {"referenceImageUrl": f"{public_base}/generated-assets/references/{session.organization_id}/{session.user_id}/{stored_name}"}

    @router.get("")
    def list_jobs(session: SessionContext = Depends(session_dependency)) -> dict[str, list[dict[str, str | int | None]]]:
        jobs = ledger.list_for_owner(session.user_id, session.organization_id)
        return {"jobs": [{"jobId": job.job_id, "kind": job.kind, "state": job.state, "providerId": job.provider_id, "progress": job.progress, "assetId": job.asset_id, "error": job.error} for job in jobs]}

    @router.get("/operations")
    def list_operations(state: JobState | None = None, kind: str | None = None, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, object]:
        jobs = ledger.list_for_organization(session.organization_id, state=state, kind=kind)
        if session.role == "teacher":
            jobs = [job for job in jobs if job.owner_user_id == session.user_id or access.can_manage_student(session, job.owner_user_id)]
        return {"jobs": [{"jobId": job.job_id, "kind": job.kind, "ownerUserId": job.owner_user_id, "state": job.state, "providerId": job.provider_id, "progress": job.progress, "assetId": job.asset_id, "error": job.error, "attempts": job.attempts, "creditCost": MEDIA_CREDITS.get(job.kind, 0) * (2 if job.kind == "video" and job.video_duration_seconds == 10 else 1)} for job in jobs]}

    @router.get("/operations/dead-letters")
    def list_dead_letters(limit: int = 100, session: SessionContext = Depends(require_role(session_dependency, "organization_admin", "platform_admin"))) -> dict[str, object]:
        if queue is None:
            raise HTTPException(status_code=503, detail="distributed media queue is not configured")
        return {"jobs": [job for job in queue.list_dead_letters(min(max(limit, 1), 200)) if session.role == "platform_admin" or belongs_to_organization(job["jobId"], session)]}

    @router.post("/operations/dead-letters/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_dead_letter(job_id: str, session: SessionContext = Depends(require_role(session_dependency, "organization_admin", "platform_admin"))) -> dict[str, str]:
        if queue is None:
            raise HTTPException(status_code=503, detail="distributed media queue is not configured")
        if session.role != "platform_admin" and not belongs_to_organization(job_id, session):
            raise HTTPException(status_code=404, detail="media job not found")
        if not queue.retry_dead_letter(job_id):
            raise HTTPException(status_code=404, detail="dead-letter task not found")
        if audit_log:
            audit_log.record(organization_id=session.organization_id, actor_id=session.user_id, action="media.dead_letter_retried", target_type="media_job", target_id=job_id)
        return {"jobId": job_id, "status": "requeued"}

    @router.post("/{job_id}/operations/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_operation(job_id: str, session: SessionContext = Depends(require_role(session_dependency, "teacher", "organization_admin", "platform_admin"))) -> dict[str, str]:
        try:
            job = ledger.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc
        require_job_access(job, session)
        if job.state is not JobState.FAILED:
            raise HTTPException(status_code=409, detail="only failed jobs can retry")
        quota_scope = None
        if usage:
            owner = auth_service.user_for_id(job.owner_user_id)
            scopes = [("student", job.owner_user_id)]
            if owner and owner.class_id:
                scopes.append(("class", owner.class_id))
            scopes.append(("organization", job.organization_id))
            quota_scope = usage.configured_scope(scopes, job.kind)
        if quota_scope is not None:
            try:
                usage.reserve(quota_scope[0], quota_scope[1], job.kind, 1, reservation_id=job.job_id)
            except QuotaExceeded as exc:
                raise HTTPException(status_code=429, detail="generation quota exceeded") from exc
        try:
            reserve_media_credits(usage, job.owner_user_id, job.kind, job_id, job.video_duration_seconds)
            ledger.retry(job_id)
            if queue:
                queue.enqueue(job_id)
        except QuotaExceeded as exc:
            if usage:
                usage.release(job_id)
            raise HTTPException(status_code=429, detail="创作积分不足，请联系老师。") from exc
        except Exception:
            if usage:
                usage.release(job_id)
                usage.release(f"{job_id}-credits")
            raise
        return {"jobId": job_id, "state": JobState.QUEUED}

    @router.get("/{job_id}")
    def get_job(job_id: str, session: SessionContext = Depends(session_dependency)) -> dict[str, str | int | None]:
        try:
            job = ledger.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc
        require_job_access(job, session)
        if job.owner_user_id != session.user_id and session.role not in {"teacher", "organization_admin", "platform_admin"}:
            raise HTTPException(status_code=404, detail="media job not found")
        return {"jobId": job.job_id, "kind": job.kind, "state": job.state, "providerId": job.provider_id, "assetId": job.asset_id, "externalTaskId": job.external_task_id, "error": job.error, "attempts": job.attempts, "progress": job.progress, "lyrics": job.lyrics, "durationSeconds": job.duration_seconds, "aspectRatio": job.aspect_ratio, "videoDurationSeconds": job.video_duration_seconds}

    @router.post("/{job_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_job(job_id: str, session: SessionContext = Depends(creative_dependency)) -> dict[str, str]:
        try:
            job = ledger.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc
        if job.owner_user_id != session.user_id:
            raise HTTPException(status_code=404, detail="media job not found")
        if job.state is not JobState.FAILED:
            raise HTTPException(status_code=409, detail="only failed jobs can retry")
        quota_scope = None
        if usage:
            user = auth_service.user_for_id(session.user_id)
            scopes = [("student", session.user_id)]
            if user and user.class_id:
                scopes.append(("class", user.class_id))
            scopes.append(("organization", session.organization_id))
            quota_scope = usage.configured_scope(scopes, job.kind)
        if quota_scope is not None:
            try:
                usage.reserve(quota_scope[0], quota_scope[1], job.kind, 1, reservation_id=job.job_id)
            except QuotaExceeded as exc:
                raise HTTPException(status_code=429, detail="generation quota exceeded") from exc
        try:
            reserve_media_credits(usage, job.owner_user_id, job.kind, job_id, job.video_duration_seconds)
            ledger.retry(job_id)
            if queue:
                queue.enqueue(job_id)
        except QuotaExceeded as exc:
            if usage:
                usage.release(job_id)
            raise HTTPException(status_code=429, detail="创作积分不足，请联系老师。") from exc
        except Exception:
            if usage:
                usage.release(job_id)
                usage.release(f"{job_id}-credits")
            raise
        return {"jobId": job_id, "state": JobState.QUEUED}

    @router.post("/{job_id}/worker-update")
    def worker_update(job_id: str, request: MediaWorkerUpdate, session: SessionContext = Depends(require_role(session_dependency, "platform_admin"))) -> dict[str, str | int | None]:
        try:
            job = ledger.get(job_id)
            if request.state is JobState.RUNNING:
                if job.state is JobState.QUEUED:
                    ledger.start(job_id)
                ledger.update_progress(job_id, request.progress)
            elif request.state is JobState.SUCCEEDED:
                if not request.assetId and not request.previewUrl.strip():
                    raise HTTPException(status_code=422, detail="successful media job requires a preview URL or existing asset ID")
                if job.state is JobState.QUEUED:
                    ledger.start(job_id)
                asset_id = request.assetId
                if asset_catalog is not None and not asset_id:
                    asset_kind = "text" if job.kind == "voice" else job.kind
                    asset = asset_catalog.create(
                        project_id=job.project_id or f"{job.kind}-{job.owner_user_id}",
                        organization_id=job.organization_id,
                        owner_user_id=job.owner_user_id,
                        kind=asset_kind,
                        title=request.title or f"{job.kind} 创作作品",
                        preview_url=request.previewUrl,
                        prompt=job.prompt,
                        lyrics=job.lyrics,
                        duration_seconds=job.duration_seconds,
                    )
                    asset_id = asset.asset_id
                ledger.succeed(job_id, asset_id=asset_id or f"asset-{job_id}")
                if call_log and job.provider_id:
                    call_log.record(job.organization_id, job.provider_id, job.kind, "succeeded")
                if usage:
                    usage.finalize(job_id)
                    usage.finalize(f"{job_id}-credits")
            elif request.state is JobState.FAILED:
                if job.state is JobState.QUEUED:
                    ledger.start(job_id)
                ledger.fail(job_id, request.error or "media worker failed")
                if call_log and job.provider_id:
                    call_log.record(job.organization_id, job.provider_id, job.kind, "failed")
                if usage:
                    usage.release(job_id)
                    usage.release(f"{job_id}-credits")
            else:
                raise HTTPException(status_code=422, detail="unsupported worker state")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="media job not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        updated = ledger.get(job_id)
        return {"jobId": updated.job_id, "state": updated.state, "progress": updated.progress, "assetId": updated.asset_id, "error": updated.error}

    return router
