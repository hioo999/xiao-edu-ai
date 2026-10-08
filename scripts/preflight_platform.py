from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
from apps.api.app.core.deployment import deployment_storage_from_env


def writable_directory(path: Path) -> bool:
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".platform-write-probe"
    try:
        probe.write_text("ok", encoding="utf-8")
        return True
    finally:
        probe.unlink(missing_ok=True)


def check_environment(environment: dict[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    previous = {name: os.environ.get(name) for name in ("PLATFORM_STORAGE_MODE", "DATABASE_URL", "REDIS_URL")}
    os.environ.update({name: value for name, value in environment.items() if name in previous})
    try:
        storage = deployment_storage_from_env()
        if storage.mode == "postgres":
            warnings.append("PostgreSQL mode is configured; complete repository migration before routing production traffic")
    except RuntimeError as exc:
        errors.append(str(exc))
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    encryption_key = environment.get("PROVIDER_ENCRYPTION_KEY", "")
    if not encryption_key:
        errors.append("PROVIDER_ENCRYPTION_KEY is required")
    else:
        try:
            Fernet(encryption_key.encode())
        except ValueError:
            errors.append("PROVIDER_ENCRYPTION_KEY is not a valid Fernet key")

    public_url = environment.get("PUBLIC_APP_BASE_URL", "")
    if not public_url.startswith(("http://", "https://")):
        errors.append("PUBLIC_APP_BASE_URL must start with http:// or https://")
    if public_url.startswith("http://") and public_url != "http://localhost":
        warnings.append("production traffic should use HTTPS")

    for variable, fallback in (
        ("PLATFORM_DB_PATH", "var/platform.db"),
        ("COURSE_STORAGE_PATH", "var/course-materials"),
        ("GENERATED_ASSET_STORAGE_PATH", "var/generated-assets"),
    ):
        path = Path(environment.get(variable, fallback))
        directory = path.parent if path.suffix else path
        try:
            if not writable_directory(directory):
                errors.append(f"{variable} is not writable")
        except OSError:
            errors.append(f"{variable} is not writable")

    caddy_site = environment.get("CADDY_SITE_ADDRESS", "http://localhost")
    if caddy_site.startswith("http://") and caddy_site != "http://localhost":
        warnings.append("CADDY_SITE_ADDRESS should be a domain name to enable automatic HTTPS")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate platform deployment prerequisites without printing secrets.")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    arguments = parser.parse_args()
    errors, warnings = check_environment(dict(os.environ))
    print(json.dumps({"errors": errors, "warnings": warnings, "ready": not errors and (not arguments.strict or not warnings)}, ensure_ascii=False))
    if errors or (arguments.strict and warnings):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
