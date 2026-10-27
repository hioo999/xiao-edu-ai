# 登录入口与学生积分

## 登录入口

- 学生、教师、家长使用 `/login`，管理员账号在这里统一返回账号或密码错误。
- 平台和机构管理员使用 `/admin/sign-in`，页面不在普通导航中展示，搜索引擎标记为不索引。后台 API `/auth/admin/login` 只接受管理员角色；管理员页面仍逐项校验权限。两个入口都受到生产环境登录限流保护。

## 学生积分

- 批量创建学生账号时可设置每人初始积分，默认 100，允许设为 0。既有学生首次启动时补齐默认 100 积分账户；已配置的积分不覆盖。
- 管理员可在学生列表查看余额并追加积分。学生个人入口显示余额；余额 = 累计发放 − 已消费 − 已预留。
- 文本生成前预留足额积分，成功后按服务商返回的输入、输出 token 数结算并释放差额；失败时释放全部预留。服务商未返回 usage 时，按输入和输出的 UTF-8 字节数估算。
- 当前产品费率：每 1000 输入 token 记 1 积分，每 500 输出 token 记 1 积分；单次文本请求至少 1 积分，向上取整。图片、音乐、视频、语音每个成功任务分别收取 8、12、30、2 积分；失败任务退回预留积分。这些数值是产品配置策略，不是服务商公开价格。
- 原有按能力的使用上限继续作为独立保护；积分为学生跨能力共用的余额。SQLite 事务保证同一余额在并发请求中不会被重复消费，数据库记录也供 API 和媒体 worker 共享。

参考：[OpenAI 的 usage 字段](https://platform.openai.com/docs/api-reference/chat/object)、[AWS Bedrock TokenUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html)、[Stripe 预付额度与用量扣减](https://docs.stripe.com/billing/subscriptions/metered-billing/thresholds)。
