from apps.api.app.projects.html_dispatcher import HtmlModelDispatcher
from packages.sandbox.src.html_sanitizer import prepare_interactive_html


def test_interactive_document_keeps_click_logic_but_blocks_external_resources():
    page = prepare_interactive_html('<html><head><base href="https://outside.test"><script src="https://outside.test/x.js"></script></head><body><button onclick="this.textContent=\'完成\'">开始</button><script>const score = 0;</script><iframe src="https://outside.test"></iframe></body></html>')
    assert "this.textContent" in page
    assert "const score = 0" in page
    assert 'http-equiv="Content-Security-Policy"' in page
    assert "connect-src 'none'" in page
    assert "outside.test" not in page


def test_revision_instruction_includes_previous_document_and_new_request():
    instruction = HtmlModelDispatcher._instruction("把标题改成森林", previous_html="<html><body>海洋<button>探索</button></body></html>")
    assert "<button>探索</button>" in instruction
    assert "把标题改成森林" in instruction
    assert "保留" in instruction


def test_security_policy_is_applied_before_scripts_even_in_malformed_documents():
    page = prepare_interactive_html('<script>window.marker=1</script><html><body style="background:pink"><h1>童话</h1></body></html>')
    assert page.index("Content-Security-Policy") < page.index("<script>")
    assert '<body style="background:pink">' in page


def test_teaching_steps_refer_to_the_actual_created_page():
    steps = HtmlModelDispatcher._teaching_steps("做魔法书", "<html><h1>森林魔法书</h1><button>翻开书页</button></html>")
    assert "森林魔法书" in steps[0]
    assert "翻开书页" in steps[1]
