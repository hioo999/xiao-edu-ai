import os
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from apps.api.app.auth.access import TeachingAccess
from apps.api.app.auth.dependencies import require_session
from apps.api.app.auth.service import SessionContext


MEDIA_TYPES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".mp4": "video/mp4",
    ".webm": "video/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav",
    ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".bin": "application/octet-stream",
}


class GeneratedFileAccess:
    def __init__(self, auth, ledger, assets, classrooms=None):
        self.auth = auth
        self.ledger = ledger
        self.assets = assets
        self.access = TeachingAccess(auth, classrooms)
        self.root = Path(os.getenv("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets")).resolve()
        self.url_prefix = os.getenv("PUBLIC_API_BASE_URL", "http://localhost:8000").rstrip("/") + "/generated-assets/"

    def is_generated_url(self, url: str) -> bool:
        return url.startswith(self.url_prefix) or url.startswith("/generated-assets/")

    def resolve(self, relative_path: str) -> Path:
        parts = PurePosixPath(relative_path).parts
        if not parts or relative_path.startswith("/") or any(part in {".", ".."} for part in parts) or any(character in relative_path for character in "\\%?#\x00"):
            raise KeyError(relative_path)
        candidate = self.root
        for part in parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise KeyError(relative_path)
        if not candidate.resolve().is_relative_to(self.root) or not candidate.is_file() or candidate.suffix.lower() not in MEDIA_TYPES:
            raise KeyError(relative_path)
        return candidate

    def asset_file(self, asset, url: str) -> Path:
        if not self.is_generated_url(url):
            raise KeyError(asset.asset_id)
        relative_path = url[len(self.url_prefix):] if url.startswith(self.url_prefix) else url[len("/generated-assets/"):]
        if "/" in relative_path:
            raise KeyError(asset.asset_id)
        path = self.resolve(relative_path)
        job = self.ledger.get(path.stem)
        if job.asset_id != asset.asset_id or job.owner_user_id != asset.owner_user_id or job.organization_id != asset.organization_id:
            raise KeyError(asset.asset_id)
        return path

    def authorized_file(self, relative_path: str, session: SessionContext) -> Path:
        path = self.resolve(relative_path)
        parts = PurePosixPath(relative_path).parts
        if len(parts) == 4 and parts[0] == "references":
            organization_id, owner_id = parts[1:3]
            if organization_id != session.organization_id:
                raise KeyError(relative_path)
            if owner_id != session.user_id and session.role not in {"organization_admin", "platform_admin"}:
                raise HTTPException(status_code=403, detail="reference image access denied")
            return path
        if len(parts) != 1:
            raise KeyError(relative_path)
        job = self.ledger.get(path.stem)
        if job.organization_id != session.organization_id:
            raise KeyError(relative_path)
        if job.owner_user_id == session.user_id or session.role in {"organization_admin", "platform_admin"} or self.access.can_manage_student(session, job.owner_user_id):
            return path
        if job.asset_id:
            asset = self.assets.get(job.asset_id, session.organization_id)
            if asset.review_state == "approved" and asset.visibility == "organization" and self.asset_file(asset, asset.preview_url) == path:
                return path
        raise HTTPException(status_code=403, detail="generated file access denied")

    @staticmethod
    def response(path: Path, *, public: bool = False) -> FileResponse:
        return FileResponse(path, media_type=MEDIA_TYPES[path.suffix.lower()], headers={
            "Cache-Control": "no-store" if public else "private, no-store",
            "Vary": "Authorization",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        })


def create_generated_file_router(auth, files: GeneratedFileAccess) -> APIRouter:
    router = APIRouter(prefix="/generated-assets", tags=["generated-files"])

    @router.api_route("/{relative_path:path}", methods=["GET", "HEAD"])
    def read_file(relative_path: str, session=Depends(require_session(auth))):
        try:
            return files.response(files.authorized_file(relative_path, session))
        except (KeyError, OSError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="generated file not found") from exc

    return router
