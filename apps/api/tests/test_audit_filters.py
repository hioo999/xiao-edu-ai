from apps.api.app.audit.service import AuditLog


def test_audit_log_filters_and_paginates() -> None:
    audit = AuditLog()
    audit.record(organization_id="org-001", actor_id="admin", action="course.saved", target_type="course", target_id="course-1")
    audit.record(organization_id="org-001", actor_id="teacher", action="course.published", target_type="classroom", target_id="class-1")
    audit.record(organization_id="org-001", actor_id="admin", action="provider.saved", target_type="model_provider", target_id="deepseek")

    records = audit.list_for_organization("org-001", limit=1, offset=0, actor_id="admin")

    assert len(records) == 1
    assert records[0].action == "provider.saved"
