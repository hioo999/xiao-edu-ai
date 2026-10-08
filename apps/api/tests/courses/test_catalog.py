from apps.api.app.courses.catalog import CourseCatalog, CourseRecord


def test_publish_and_unpublish_updates_course_visibility(tmp_path) -> None:
    catalog = CourseCatalog(tmp_path / "platform.db")
    catalog.save(CourseRecord("course-001", "org-001", "teacher-001", "网页入门", "基础课"))

    catalog.publish_to_class("course-001", "class-a", "org-001")

    assert catalog.get("course-001", "org-001").published is True
    assert [course.course_id for course in catalog.list_for_class("class-a", "org-001")] == ["course-001"]

    catalog.unpublish_from_class("course-001", "class-a", "org-001")

    assert catalog.get("course-001", "org-001").published is False
    assert catalog.list_for_class("class-a", "org-001") == []


def test_publishing_to_two_classes_keeps_course_published_until_last_withdrawal(tmp_path) -> None:
    catalog = CourseCatalog(tmp_path / "platform.db")
    catalog.save(CourseRecord("course-001", "org-001", "teacher-001", "网页入门", "基础课"))

    catalog.publish_to_class("course-001", "class-a", "org-001")
    catalog.publish_to_class("course-001", "class-b", "org-001")
    catalog.unpublish_from_class("course-001", "class-a", "org-001")

    assert catalog.get("course-001", "org-001").published is True
    assert [course.course_id for course in catalog.list_for_class("class-b", "org-001")] == ["course-001"]
