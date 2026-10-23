from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import time

from apps.api.app.agents.student_workspace import StudentAgentWorkspace
from apps.api.app.projects.html_service import HtmlWorkspaceService
from packages.agent_runtime.src.dispatch_policy import AgentDispatchRequest
from packages.agent_runtime.src.dispatcher import AgentExecutionResult


def test_reopening_an_agent_selects_the_most_recently_used_conversation(tmp_path):
    path = str(tmp_path / "history.db")
    store = StudentAgentWorkspace(path)
    first = store.create("school", "student", "agent", "最初对话")
    store.create("school", "student", "agent", "较新对话")
    store.append(first["sessionId"], "school", "student", "继续原来的任务", {"text": "继续完成了", "capability": "text"})
    reopened = StudentAgentWorkspace(path).list_sessions("school", "student", "agent")
    assert reopened[0]["sessionId"] == first["sessionId"]
    assert reopened[0]["messages"][1]["text"] == "继续完成了"


def test_simultaneous_edits_on_one_page_keep_sequential_revision_context():
    class Dispatcher:
        def __init__(self):
            self.previous = []

        def dispatch(self, policy, prompt, *, organization_id, previous_html=""):
            self.previous.append(previous_html)
            time.sleep(.03)
            return AgentExecutionResult("html", f"<html><body>{prompt}</body></html>", [])
    dispatcher = Dispatcher()
    service = HtmlWorkspaceService(dispatcher)
    barrier = Barrier(2)
    def generate(prompt):
        barrier.wait()
        return service.generate(project_id="page", owner_user_id="student", organization_id="school", prompt=prompt, policy=AgentDispatchRequest("html", "text", True, True, True, True, False, "domestic", True))
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(generate, ["森林", "城堡"]))
    assert sum(bool(previous) for previous in dispatcher.previous) == 1
    assert len(service.get("page", "student").versions) == 2
