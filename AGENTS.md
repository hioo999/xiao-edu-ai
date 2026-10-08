# ai-creative-learning-workbench Knowledge Map

## About This Project

ai-creative-learning-workbench — A project using Harness Engineering practices (basic adoption level).

## Documentation

- Main docs: `docs/`
- Architecture decisions: `docs/architecture.md`

## Source Code

- Entry point: `src/index.ts`

## Architecture

See `docs/architecture.md` for architectural decisions.

## Agent skills

### Issue tracker

项目任务统一使用 GitHub Issues，仓库为 `hioo999/xiao-edu-ai`。详见 `docs/agents/issue-tracker.md`。

### Triage labels

使用默认标签：`needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`。详见 `docs/agents/triage-labels.md`。

### Domain docs

项目采用多上下文布局，通过 `CONTEXT-MAP.md` 管理前端、后端、Agent Runtime、数据与部署文档。详见 `docs/agents/domain.md`。
