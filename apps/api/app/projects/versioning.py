from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from packages.sandbox.src.html_sanitizer import prepare_interactive_html, sanitize_html


@dataclass(frozen=True)
class HtmlVersion:
    version_id: str
    title: str
    html: str
    teaching_steps: list[str]


@dataclass
class HtmlProject:
    project_id: str
    owner_user_id: str
    versions: list[HtmlVersion] = field(default_factory=list)
    current_version_id: str | None = None


def create_version(project: HtmlProject, *, title: str, html: str, teaching_steps: list[str], interactive: bool = False) -> HtmlVersion:
    version = HtmlVersion(
        version_id=f"{project.project_id}-v{len(project.versions) + 1}",
        title=title,
        html=prepare_interactive_html(html) if interactive else sanitize_html(html),
        teaching_steps=list(teaching_steps),
    )
    project.versions.append(version)
    project.current_version_id = version.version_id
    return version


def restore_version(project: HtmlProject, version_id: str) -> None:
    if not any(version.version_id == version_id for version in project.versions):
        raise LookupError("HTML version not found")
    project.current_version_id = version_id


def current_version(project: HtmlProject) -> HtmlVersion:
    if project.current_version_id is None:
        raise LookupError("HTML project has no version")
    return next(version for version in project.versions if version.version_id == project.current_version_id)


def download_html(project: HtmlProject) -> str:
    return current_version(project).html


def download_zip(project: HtmlProject) -> bytes:
    version = current_version(project)
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("index.html", version.html)
        archive.writestr("teaching-steps.txt", "\n".join(version.teaching_steps))
    return buffer.getvalue()
