from __future__ import annotations

import os
import time

from cryptography.fernet import Fernet
from dotenv import load_dotenv
import httpx

from apps.api.app.core.deployment import deployment_storage_from_env
from apps.api.app.models.registry import ModelCapability, PostgresProviderRegistry, ProviderRegistry, SecretVault
from apps.api.app.models.calls import ModelCallLog, PostgresModelCallLog
from apps.api.app.projects.catalog import CreativeAssetCatalog, PostgresCreativeAssetCatalog
from apps.api.app.usage.service import PostgresUsageLedger, UsageLedger

from .gateway import MediaProviderGateway
from .jobs import JobState, MediaJob, MediaJobLedger, PostgresMediaJobLedger
from .queue import MediaJobQueue, build_media_job_queue
from .storage import AssetStore, build_asset_store


class MediaGenerationWorker:
    def __init__(self, ledger: MediaJobLedger, providers: ProviderRegistry, assets: CreativeAssetCatalog, gateway: MediaProviderGateway, usage: UsageLedger | None = None, asset_store: AssetStore | None = None, call_log: ModelCallLog | None = None, queue: MediaJobQueue | None = None) -> None:
        self._ledger = ledger
        self._providers = providers
        self._assets = assets
        self._gateway = gateway
        self._usage = usage
        self._asset_store = asset_store
        self._call_log = call_log
        self._queue = queue
        self._max_attempts = max(1, int(os.getenv("MEDIA_WORKER_MAX_ATTEMPTS", "3")))
        self._task_timeout_seconds = max(1, int(os.getenv("MEDIA_WORKER_TASK_TIMEOUT_SECONDS", "900")))
        self._max_concurrency = max(1, int(os.getenv("MEDIA_WORKER_MAX_CONCURRENCY", "1")))

    def process_once(self) -> int:
        heartbeat = getattr(self._queue, "heartbeat", None)
        if callable(heartbeat):
            heartbeat()
        processed = 0
        recover_stale = getattr(self._ledger, "recover_stale_running", None)
        if callable(recover_stale):
            for job_id in recover_stale(self._task_timeout_seconds):
                try:
                    self._fail(self._ledger.get(job_id), "worker heartbeat timeout")
                except KeyError:
                    continue
        jobs = self._ledger.list_pending()
        if self._queue:
            queued_job_id = self._queue.dequeue()
            if queued_job_id:
                try:
                    queued_job = self._ledger.get(queued_job_id)
                except KeyError:
                    queued_job = None
                if queued_job and all(job.job_id != queued_job.job_id for job in jobs):
                    jobs.insert(0, queued_job)
        for job in jobs[: self._max_concurrency]:
            try:
                if job.state is JobState.QUEUED:
                    self._submit(job)
                elif job.external_task_id:
                    self._poll(job)
                processed += 1
            except (LookupError, ValueError, OSError, httpx.HTTPError) as exc:
                if str(exc) == "only queued jobs can start":
                    continue
                self._fail(job, str(exc))
        return processed

    def _submit(self, job: MediaJob) -> None:
        capability = {"image": ModelCapability.IMAGE, "video": ModelCapability.VIDEO, "music": ModelCapability.MUSIC, "voice": ModelCapability.TEXT_TO_SPEECH}[job.kind]
        candidates = self._providers.resolve_candidates(job.organization_id, capability)
        if not candidates:
            raise LookupError("no eligible media model provider")
        self._ledger.start(job.job_id)
        last_error: Exception | None = None
        for provider in candidates:
            self._ledger.assign_provider(job.job_id, provider.provider_id)
            try:
                result = self._gateway.submit(provider, self._ledger.get(job.job_id))
                if self._call_log:
                    self._call_log.record(job.organization_id, provider.provider_id, job.kind, "succeeded")
                self._apply_result(job.job_id, result.preview_url, result.external_task_id)
                return
            except (ValueError, OSError, httpx.HTTPError) as exc:
                if self._call_log:
                    self._call_log.record(job.organization_id, provider.provider_id, job.kind, "failed")
                last_error = exc
        raise ValueError("all media model providers are unavailable") from last_error

    def _poll(self, job: MediaJob) -> None:
        if not job.provider_id:
            raise ValueError("media job has no selected provider")
        result = self._gateway.poll(self._providers.provider(job.provider_id), job.external_task_id or "")
        self._apply_result(job.job_id, result.preview_url, result.external_task_id)

    def _apply_result(self, job_id: str, preview_url: str, external_task_id: str | None) -> None:
        if external_task_id:
            self._ledger.set_external_task(job_id, external_task_id)
            self._ledger.update_progress(job_id, 30)
            return
        if not preview_url:
            return
        job = self._ledger.get(job_id)
        if self._asset_store is not None:
            preview_url = self._asset_store.persist(job_id, preview_url)
        asset_kind = "text" if job.kind == "voice" else job.kind
        asset = self._assets.create(
            project_id=job.project_id or f"{job.kind}-{job.owner_user_id}",
            organization_id=job.organization_id,
            owner_user_id=job.owner_user_id,
            kind=asset_kind,
            title=f"{job.kind} 创作作品",
            preview_url=preview_url,
            prompt=job.prompt,
        )
        self._ledger.succeed(job_id, asset_id=asset.asset_id)
        if self._usage:
            self._usage.finalize(job_id)

    def _fail(self, job: MediaJob, error: str) -> None:
        current = self._ledger.get(job.job_id)
        was_running = current.state is JobState.RUNNING
        if current.state is JobState.QUEUED:
            self._ledger.fail_after_queue(job.job_id, error)
        elif current.state is JobState.RUNNING:
            self._ledger.fail(job.job_id, error)
        elif current.state is not JobState.FAILED:
            return
        failed = self._ledger.get(job.job_id)
        if (was_running or failed.error == "worker heartbeat timeout") and failed.attempts < self._max_attempts:
            delay_seconds = min(300, 2 ** max(0, failed.attempts - 1))
            self._ledger.retry(job.job_id, delay_seconds=delay_seconds)
            if self._queue:
                self._queue.enqueue(job.job_id)
            return
        if self._queue:
            self._queue.dead_letter(job.job_id, error)
        if self._usage:
            self._usage.release(job.job_id)


def build_worker() -> MediaGenerationWorker:
    load_dotenv()
    storage_path = os.getenv("PLATFORM_DB_PATH", "var/platform.db")
    deployment_storage = deployment_storage_from_env()
    encryption_key = os.getenv("PROVIDER_ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("PROVIDER_ENCRYPTION_KEY is required to run the media worker")
    postgres_url = deployment_storage.database_url if deployment_storage.mode == "postgres" else None
    providers = PostgresProviderRegistry(SecretVault(encryption_key.encode()), postgres_url) if postgres_url else ProviderRegistry(SecretVault(encryption_key.encode()), storage_path=storage_path)
    ledger = PostgresMediaJobLedger(postgres_url) if postgres_url else MediaJobLedger(storage_path)
    return MediaGenerationWorker(
        ledger,
        providers,
        PostgresCreativeAssetCatalog(postgres_url) if postgres_url else CreativeAssetCatalog(storage_path),
        MediaProviderGateway(providers),
        PostgresUsageLedger(postgres_url) if postgres_url else UsageLedger({}, storage_path),
        asset_store=build_asset_store(),
        call_log=PostgresModelCallLog(postgres_url) if postgres_url else ModelCallLog(storage_path),
        queue=build_media_job_queue(ledger),
    )


def main() -> None:
    worker = build_worker()
    interval_seconds = float(os.getenv("MEDIA_WORKER_INTERVAL_SECONDS", "3"))
    while True:
        worker.process_once()
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
