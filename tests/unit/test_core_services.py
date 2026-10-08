from datetime import datetime, timedelta, timezone

import pytest

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.usage.service import QuotaExceeded, UsageLedger
from packages.agent_runtime.src.agentscope_executor import AgentScopeExecutor
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest, DispatchDenied, evaluate_dispatch


pytestmark = pytest.mark.unit


def test_auth_rejects_wrong_password_disabled_and_expired_users() -> None:
    now = datetime.now(timezone.utc)
    service = AuthService(
        users={
            "valid": UserRecord("valid", "org-001", "student", hash_password("correct")),
            "disabled": UserRecord("disabled", "org-001", "student", hash_password("correct"), enabled=False),
            "expired": UserRecord("expired", "org-001", "student", hash_password("correct"), expires_at=now - timedelta(minutes=1)),
        }
    )

    assert service.login("valid", "correct").user_id == "valid"
    for username, password in [("valid", "wrong"), ("disabled", "correct"), ("expired", "correct")]:
        with pytest.raises(PermissionError):
            service.login(username, password)


def test_usage_reservation_is_idempotent_and_quota_is_enforced() -> None:
    ledger = UsageLedger({("student", "student-001", "text"): 1})

    ledger.reserve("student", "student-001", "text", 1, reservation_id="request-1")
    ledger.reserve("student", "student-001", "text", 1, reservation_id="request-1")

    with pytest.raises(QuotaExceeded):
        ledger.reserve("student", "student-001", "text", 1, reservation_id="request-2")

    ledger.finalize("request-1")
    assert ledger.committed("student", "student-001", "text") == 1
    ledger.release("request-1")
    assert ledger.committed("student", "student-001", "text") == 1


def test_usage_reservation_survives_restart(tmp_path) -> None:
    path = tmp_path / "usage.db"
    ledger = UsageLedger({}, storage_path=path)
    ledger.set_limit("organization", "org-001", "image", 2)
    ledger.reserve("organization", "org-001", "image", 1, reservation_id="job-1")

    restarted = UsageLedger({}, storage_path=path)

    assert restarted.summary("organization", "org-001") == [{"metric": "image", "limit": 2, "used": 0, "reserved": 1}]


def test_dispatch_policy_reports_first_failed_guard() -> None:
    request = AgentDispatchRequest("web-coach", "html", True, False, True, True, False, "domestic", True)

    with pytest.raises(DispatchDenied) as error:
        evaluate_dispatch(request)

    assert error.value.code == "FEATURE_DISABLED"


class FakeAgent:
    def run(self, prompt: str) -> dict[str, object]:
        return {"html": f"<main>{prompt}</main>", "teachingSteps": ["拆解需求", "预览结果"]}


def test_agentscope_adapter_normalizes_valid_result() -> None:
    result = AgentScopeExecutor(lambda kind: FakeAgent()).execute("html", "做网页")

    assert result.html == "<main>做网页</main>"
    assert result.teaching_steps == ["拆解需求", "预览结果"]


@pytest.mark.parametrize(
    "payload, message",
    [({"teachingSteps": []}, "must contain html"), ({"html": "<p>ok</p>", "teachingSteps": "bad"}, "string list")],
)
def test_agentscope_adapter_rejects_malformed_result(payload: dict[str, object], message: str) -> None:
    class MalformedAgent:
        def run(self, prompt: str) -> dict[str, object]:
            return payload

    with pytest.raises(ValueError, match=message):
        AgentScopeExecutor(lambda kind: MalformedAgent()).execute("html", "做网页")


def test_agentscope_adapter_rejects_agent_without_run() -> None:
    with pytest.raises(LookupError, match="does not expose run"):
        AgentScopeExecutor(lambda kind: object()).execute("html", "做网页")


def test_agentscope_adapter_accepts_reply_style_agent_content() -> None:
    class ReplyMessage:
        content = "这是一个适合小学生的创作建议。"

    class ReplyAgent:
        def reply(self, prompt: str) -> ReplyMessage:
            return ReplyMessage()

    result = AgentScopeExecutor(lambda kind: ReplyAgent()).execute("writing-coach", "写故事")

    assert "适合小学生" in result.html
    assert result.teaching_steps == []
