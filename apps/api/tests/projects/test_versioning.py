import zipfile
from io import BytesIO

from apps.api.app.projects.versioning import HtmlProject, create_version, download_html, download_zip, restore_version


def test_html_project_keeps_history_and_restores_without_deleting_newer_versions() -> None:
    project = HtmlProject(project_id="project-001", owner_user_id="student-001")
    first = create_version(project, title="太空主页", html="<main>第一版</main>", teaching_steps=["先确定主题"])
    second = create_version(project, title="太空主页", html="<main>第二版</main>", teaching_steps=["再加入按钮"])

    restore_version(project, first.version_id)

    assert project.current_version_id == first.version_id
    assert [version.version_id for version in project.versions] == [first.version_id, second.version_id]
    assert project.versions[-1].html == "<main>第二版</main>"


def test_html_and_zip_downloads_contain_current_sanitized_artifact() -> None:
    project = HtmlProject(project_id="project-001", owner_user_id="student-001")
    create_version(project, title="我的网页", html="<main>Hello</main>", teaching_steps=["观察布局"])

    html = download_html(project)
    archive = BytesIO(download_zip(project))

    with zipfile.ZipFile(archive) as zip_file:
        assert zip_file.read("index.html").decode() == html
        assert "teaching-steps.txt" in zip_file.namelist()
