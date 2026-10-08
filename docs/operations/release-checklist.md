# Release Checklist

- [ ] Tenant and class boundary tests pass.
- [ ] Provider keys are absent from tracked files and logs.
- [ ] HTML preview sandbox and moderation tests pass.
- [ ] Upload virus scanning rejects executable payloads; ClamAV is configured in production.
- [ ] Student, teacher, and admin permissions are verified.
- [ ] Backup restore and queue recovery are tested.
- [ ] `python scripts/cleanup_platform.py --retention-days 90` is scheduled and tested.
- [ ] `python scripts/loadtest/load_smoke.py --concurrency 10 --requests 100` passes in staging.
- [ ] License inventory and minor-data review are approved.
- [ ] 100-user classroom load test passes in staging.
