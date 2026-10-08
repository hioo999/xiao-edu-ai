# AI 创造力学习工作台

面向小学 3–6 年级学生的多模态 AI 智能体学习与创作平台。

## 当前状态

项目进入单服务器生产阶段：学生、教师、管理端和模型 Worker 均可部署；部署时只需配置模型 Key、固定加密密钥与域名。

## 核心底座

- GitHub AgentScope：智能体运行与协作底座
- Next.js + React + TypeScript：前端
- React Three Fiber + Three.js：3D 创作大厅
- FastAPI + Python：后端
- SQLite：单服务器生产部署的业务数据、任务元数据和哈希化登录会话
- 平台本地文件目录：课件和生成作品存储
- 独立媒体 Worker：图片生成与视频轮询

## 产品能力

- AI 文字
- AI 图片
- AI 音乐
- AI 视频
- AI 网页 Vibe Coding
- 智能体与专家团
- 灵感案例馆
- 统一跨模态项目
- 课程、知识库和成长报告

## 文档

- 产品需求文档：`docs/specs/2026-09-22-ai-creative-learning-workbench-prd.md`
- 开发计划：`docs/plans/2026-09-22-ai-creative-learning-workbench.md`

## 本地启动

```bash
# 终端 1：API
uvicorn apps.api.app.main:app --reload

# 终端 2：Web
npm --prefix apps/web run dev
```

浏览器打开 `http://localhost:3000`，登录页会请求 `http://localhost:8000/auth/login`。
如 API 地址不同，在 Web 环境中设置 `NEXT_PUBLIC_API_BASE_URL`。模型密钥只能配置在服务端，不能写入浏览器环境变量。

## 腾讯云单服务器部署

1. 复制 `.env.example` 为 `.env`，设置不可变的 `PROVIDER_ENCRYPTION_KEY`、`PUBLIC_APP_BASE_URL` 和后台模型 Key。
2. 在服务器项目目录执行 `docker compose up -d --build`。
3. 将域名解析到服务器，再为反向代理配置 HTTPS 证书。

`api`、`worker` 和课程/作品目录共享名为 `platform-data` 的 Docker 卷；备份时必须同时备份其中的 `platform.db`、`course-materials` 与 `generated-assets`。当前采用单机 SQLite：只能运行一套 API 与 Worker，不能横向扩容为多个 SQLite 写入实例。

发布前先运行 `python scripts/preflight_platform.py`。生产环境应把 `.env` 中的 `PUBLIC_APP_BASE_URL` 设为 HTTPS 地址，并把 `CADDY_SITE_ADDRESS` 设为域名（例如 `ai.example.com`）；Caddy 会自动申请和续期证书。

## 目录约定

后续代码将按以下方向组织：

```text
apps/
  web/
  api/
packages/
  contracts/
  agent-runtime/
  model-gateway/
  sandbox/
infra/
docs/
```
# AI 创造力学习工作台

## 本地模型配置

复制 `.env.example` 为本机 `.env`，再由管理员把重新生成的 DeepSeek 与火山方舟密钥填入其中。`.env` 不可提交至 Git，学生端和浏览器端也不会读取这些变量。火山方舟文字模型还需要填入已开通的模型 ID。
