# 多媒体供应商适配约定

`apps/api/app/media/gateway.py` 只在服务端发送 API Key。学生端只能创建任务和读取任务状态，不能接触供应商凭据。

## 已支持能力

- `image`：`POST /images/generations`，返回 `data[0].url`。
- `video`：`POST /contents/generations/tasks` 创建任务，再通过 `GET /contents/generations/tasks?filter.task_ids={id}` 轮询。
- `voice`：`POST /audio/speech`，返回 `audio_url`、`audioUrl`、`url` 或 `data[0].url`。
- `music`：`POST /audio/music/generations`，返回 `audio_url`、`audioUrl`、`url` 或 `data[0].url`。
- 音频也可以返回 `base64`、`audio` 或字符串形式的 `data`；服务端会写入生成资源目录并转换为平台 URL。

## provider 配置

- `providerKind=doubao`：自动补齐 `/api/v3`。
- `providerKind=custom`、`openai_compatible`、`qwen`：`baseUrl` 必须直接指向供应商 API 根地址，系统不会自动拼接版本路径。
- Base64 音频当前限制为 50 MB，服务端会校验 MIME、编码和空内容。

所有返回结果都会进入媒体任务、作品资源、额度结算和调用日志链路；供应商返回无效结构时任务失败并释放预留额度。
