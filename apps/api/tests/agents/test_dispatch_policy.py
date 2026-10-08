import pytest

from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest, DispatchDenied, evaluate_dispatch


def base_request(**changes: object) -> AgentDispatchRequest:
    values = {
        "agent_kind": "html",
        "capability": "text",
        "classroom_open": True,
        "feature_enabled": True,
        "quota_available": True,
        "model_available": True,
        "allow_foreign": False,
        "model_region": "domestic",
        "mcp_approved": True,
    }
    values.update(changes)
    return AgentDispatchRequest(**values)


def test_html_request_is_allowed_when_all_policies_pass() -> None:
    decision = evaluate_dispatch(base_request())

    assert decision.allowed is True
    assert decision.agent_kind == "html"


@pytest.mark.parametrize(
    ("change", "error_code"),
    [
        ({"classroom_open": False}, "CLASSROOM_CLOSED"),
        ({"feature_enabled": False}, "FEATURE_DISABLED"),
        ({"quota_available": False}, "QUOTA_EXCEEDED"),
        ({"model_available": False}, "MODEL_UNAVAILABLE"),
        ({"mcp_approved": False}, "MCP_NOT_APPROVED"),
        ({"model_region": "foreign"}, "FOREIGN_MODEL_DENIED"),
    ],
)
def test_dispatch_denies_each_failed_policy(change: dict[str, object], error_code: str) -> None:
    with pytest.raises(DispatchDenied) as error:
        evaluate_dispatch(base_request(**change))

    assert error.value.code == error_code
