from packages.sandbox.src.html_sanitizer import sanitize_html
from packages.sandbox.src.preview_policy import preview_policy


def test_sanitizer_removes_scripts_event_handlers_and_javascript_links() -> None:
    unsafe = '<button onclick="alert(1)">点我</button><script>alert(1)</script><a href="javascript:alert(1)">x</a>'

    safe = sanitize_html(unsafe)

    assert "script" not in safe.lower()
    assert "onclick" not in safe.lower()
    assert "javascript:" not in safe.lower()


def test_preview_policy_isolated_from_platform_storage_and_network() -> None:
    policy = preview_policy()

    assert policy["sandbox"] == "allow-scripts"
    assert "allow-same-origin" not in policy["sandbox"]
    assert "default-src 'none'" in policy["contentSecurityPolicy"]
