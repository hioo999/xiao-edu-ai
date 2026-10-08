from dataclasses import dataclass, field
from typing import Literal


AssetKind = Literal["text", "image", "music", "video", "webpage", "lesson", "report"]

ALLOWED_TRANSITIONS: set[tuple[AssetKind, AssetKind]] = {
    ("text", "image"),
    ("text", "music"),
    ("text", "video"),
    ("text", "webpage"),
    ("image", "video"),
    ("image", "webpage"),
    ("music", "video"),
    ("music", "webpage"),
    ("video", "webpage"),
}


@dataclass(frozen=True)
class ProjectAsset:
    asset_id: str
    kind: AssetKind
    owner_user_id: str


@dataclass
class Project:
    project_id: str
    organization_id: str
    owner_user_id: str
    assets: list[ProjectAsset] = field(default_factory=list)


def add_asset(project: Project, asset: ProjectAsset) -> None:
    if asset.owner_user_id != project.owner_user_id:
        raise PermissionError("asset owner does not match project owner")
    project.assets.append(asset)


def allowed_transition(source: AssetKind, target: AssetKind) -> bool:
    return (source, target) in ALLOWED_TRANSITIONS
