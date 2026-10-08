# Tencent Cloud Operations

## Recommended First Deployment

- One CVM for the web, API, reverse-proxy and worker containers.
- One shared Docker volume for SQLite, course files and generated assets.
- A domain, HTTPS and regular backups for the web shell and approved public assets.
- COS 可选用于生成作品；设置 `TENCENT_COS_*` 后，媒体 Worker 会把供应商的临时文件复制到 COS，再只保存平台自己的访问地址。
- 上传安全：生产环境建议在同一 VPC 部署 ClamAV 并设置 `CLAMAV_HOST`/`CLAMAV_PORT`；未配置时平台使用本地启发式扫描兜底，不替代真实杀毒引擎。
- CLS and monitoring for audit, provider failures, queue latency, and storage growth.

## Operational Requirements

- Keep provider keys and database credentials in deployment secrets, not images.
- Back up `platform.db`, `course-materials` and `generated-assets` together.
- Rotate provider credentials and encryption keys on a documented schedule.
- Test queue recovery, provider outage fallback, backup restore, and rollback in staging.
- 用 `python scripts/cleanup_platform.py --retention-days 90` 定期清理过期会话、历史媒体任务、审计记录与旧生成文件，避免 SQLite 文件无界增长。

## Scale-Up Trigger

如需要多个 API 或 Worker 实例、频繁并发写入或跨服务器共享存储，再迁移 TencentDB for PostgreSQL、Tencent Cloud Redis 和 COS。不要在不同服务器运行多个 SQLite 写入实例。

## COS 配置

- 为每个环境创建独立 COS 桶和最小权限子账号，仅授予指定前缀的读写权限。
- 将 `TENCENT_COS_BUCKET`、`TENCENT_COS_REGION`、`TENCENT_COS_SECRET_ID`、`TENCENT_COS_SECRET_KEY`、`TENCENT_COS_PUBLIC_BASE_URL` 保存在腾讯云密钥管理或部署密钥中。
- 生产环境使用 HTTPS 自定义域名作为 `TENCENT_COS_PUBLIC_BASE_URL`；不要把密钥、桶策略或临时下载地址发送给浏览器。
