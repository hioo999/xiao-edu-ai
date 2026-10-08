# 火山方舟媒体生成接口调研

## 已确认的接口

- Seedream 图片生成使用 `POST /api/v3/images/generations`，使用 API Key 鉴权，输入包含模型 ID 与 `prompt`，结果返回生成图片信息。[官方图片生成 API](https://docs.volcengine.com/docs/ark/image-generation-api?lang=en)
- Seedance 视频生成先使用 `POST /api/v3/contents/generations/tasks` 创建异步任务；生成完成后再查询任务并获取视频地址。[官方创建视频任务 API](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)
- Seedance 支持文生视频；模型、时长、比例均受已开通模型限制，生产部署必须在后台选择已开通的模型 ID。[官方模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh)

## 平台接入决定

- 图片由独立 Worker 调用后直接写入作品记录。
- 视频由 Worker 创建上游任务并轮询；成功后写入作品记录及预览地址。
- API Key 仅在服务端加密保存；学生浏览器永远不会拿到第三方 Key。
- 运行 Worker 前必须配置固定的 `PROVIDER_ENCRYPTION_KEY`，并以独立进程运行 `python -m apps.api.app.media.worker`。
