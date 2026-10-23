import pytest
from fastapi.testclient import TestClient

from apps.api.app.auth.service import AuthService, UserRecord, hash_password
from apps.api.app.knowledge.catalog import KnowledgeCatalog
from apps.api.app.knowledge.scopes import KnowledgeScope
from apps.api.app.main import create_app
from apps.api.app.models.gateway import TextGeneration
from apps.api.app.courses.catalog import CourseCatalog, CourseRecord
from apps.api.app.classrooms.assistance import AssistanceManager


pytestmark = pytest.mark.integration


class CapturingGateway:
    def __init__(self) -> None:
        self.prompt = ""

    def generate_text(self, organization_id: str, prompt: str, *, allow_foreign: bool = False) -> TextGeneration:
        self.prompt = prompt
        return TextGeneration("fake", "fake", "完成")


def test_text_generation_includes_matching_organization_knowledge(tmp_path) -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    knowledge = KnowledgeCatalog(tmp_path / "knowledge.db")
    knowledge.add(KnowledgeScope.ORGANIZATION, "org-001", "网页提示", "org-001", "海洋页面使用蓝色。")
    gateway = CapturingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, knowledge_catalog=knowledge))
    token = client.post("/auth/login", json={"username": "student", "password": "password"}).json()["accessToken"]

    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {token}"}, json={"prompt": "做一个海洋网页"})

    assert response.status_code == 200
    assert "网页提示" in gateway.prompt
    assert "海洋页面使用蓝色" in gateway.prompt


def test_generation_does_not_retrieve_other_users_private_knowledge(tmp_path) -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"))})
    knowledge = KnowledgeCatalog(tmp_path / "knowledge.db")
    knowledge.add(KnowledgeScope.TEACHER, "teacher-001", "海洋教师私有", "org-001", "教师私密资料不可读取")
    knowledge.add(KnowledgeScope.STUDENT, "another-student", "海洋同学私有", "org-001", "同学私密资料不可读取")
    knowledge.add(KnowledgeScope.STUDENT, "student-001", "海洋自己的资料", "org-001", "自己的蓝色海洋")
    gateway = CapturingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, knowledge_catalog=knowledge))
    login = client.post("/auth/login", json={"username": "student", "password": "password"})
    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {login.json()['accessToken']}"}, json={"prompt": "海洋"})
    assert response.status_code == 200
    assert "自己的蓝色海洋" in gateway.prompt
    assert "私密资料不可读取" not in gateway.prompt


def test_generation_rejects_unpublished_course_context_before_model_call(tmp_path) -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-a")})
    gateway = CapturingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway))
    login = client.post("/auth/login", json={"username": "student", "password": "password"})
    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {login.json()['accessToken']}"}, json={"prompt": "海洋", "courseId": "not-published"})
    assert response.status_code == 403
    assert gateway.prompt == ""


def test_generation_can_use_knowledge_from_a_course_published_to_own_class(tmp_path) -> None:
    auth = AuthService(users={"student": UserRecord("student-001", "org-001", "student", hash_password("password"), class_id="class-a")})
    courses = CourseCatalog(tmp_path / "courses.db")
    courses.save(CourseRecord("own-course", "org-001", "teacher", "海洋课", ""))
    courses.publish_to_class("own-course", "class-a", "org-001")
    classrooms = AssistanceManager()
    classrooms.create("class-a", "org-001")
    classrooms.open("class-a")
    knowledge = KnowledgeCatalog()
    knowledge.add(KnowledgeScope.COURSE, "own-course", "海洋课程资料", "org-001", "可以参考的珊瑚颜色")
    knowledge.add(KnowledgeScope.COURSE, "other-course", "海洋其他课程资料", "org-001", "禁止读取的其他课程")
    gateway = CapturingGateway()
    client = TestClient(create_app(auth_service=auth, model_gateway=gateway, knowledge_catalog=knowledge, course_catalog=courses, assistance_manager=classrooms))
    login = client.post("/auth/login", json={"username": "student", "password": "password"})
    response = client.post("/models/text/generate", headers={"Authorization": f"Bearer {login.json()['accessToken']}"}, json={"prompt": "海洋", "courseId": "own-course"})
    assert response.status_code == 200
    assert "可以参考的珊瑚颜色" in gateway.prompt
    assert "禁止读取的其他课程" not in gateway.prompt
