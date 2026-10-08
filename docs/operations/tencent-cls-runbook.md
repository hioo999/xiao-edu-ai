# 腾讯云 CLS、告警与演练

## 日志与告警

1. 在每个环境创建独立 CLS 日志集和主题，采集 API、Worker、Caddy 的标准输出；日志保留不少于 180 天。
2. 为 `5xx`、登录限流、模型降级耗尽、媒体任务失败、备份失败和磁盘使用率建立告警；告警发送到教师运营群和运维值班渠道。
3. 不发送 API Key、登录令牌、学生提示词全文或身份证明到 CLS；只记录请求 ID、机构 ID、任务类型、结果和耗时。

## 恢复演练

每月在隔离测试环境执行一次：停止 API/Worker，运行 `python scripts/restore_platform.py --archive <backup> --data-dir <empty-dir>`，启动副本并核验管理员登录、课程、作品和模型配置可读。演练记录恢复时间、数据校验结果和异常处理。

## 压测

仅在预发布环境执行健康检查压测：`python scripts/load_test.py --base-url https://staging.example.com --requests 1000 --concurrency 100`。生成型请求必须使用测试额度与模拟模型，不能对真实供应商进行无上限压测。
