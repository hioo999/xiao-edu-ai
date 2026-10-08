from datetime import datetime, timedelta, timezone

from apps.api.app.sharing.links import ShareLinkService


def test_share_link_expires_and_can_be_revoked() -> None:
    service = ShareLinkService()
    link = service.create("project-001", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5), allow_download=True)

    assert service.is_accessible(link.token) is True
    service.revoke(link.token)
    assert service.is_accessible(link.token) is False
