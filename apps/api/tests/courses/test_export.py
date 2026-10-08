from apps.api.app.courses.exporter import Course, LessonBlock, export_offline_html


def test_course_export_keeps_teacher_content_and_marks_online_ai_features() -> None:
    course = Course(
        course_id="course-001",
        title="我的第一个网页",
        blocks=(
            LessonBlock(kind="text", content="先观察网页结构", authored_by="teacher"),
            LessonBlock(kind="code", content="<button>开始</button>", authored_by="teacher"),
            LessonBlock(kind="interaction", content="让 AI 帮你修改颜色", authored_by="ai"),
        ),
    )

    html = export_offline_html(course)

    assert "先观察网页结构" in html
    assert "<button>开始</button>" in html
    assert "AI 功能需要联网" in html
