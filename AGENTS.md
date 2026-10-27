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

## 页面设计 Agent 强制规则

涉及首页、创作工作区、课程页面、管理后台或任何网页视觉设计时，Codex 必须执行设计自评循环，不得草率交付。

### 目标与参考

- 目标：达到获奖级网页的完整度和原创性。
- 参考：Awwwards、Webby Awards、FWA 获奖作品的完成度、叙事节奏和交互质量；只参考方法，不复制具体作品。

### 交付门槛

1. 先完成页面，再逐项检查 8 个维度：字体排版、留白节奏、视觉层级、色彩系统、动效、微交互、响应式布局、原创性。
2. 任一维度存在明显短板，必须修改后重新检查；至少保留一轮自我评审，最多连续修订 3 轮。
3. 必须在桌面端和窄屏端检查布局、溢出、可读性和交互可用性。
4. 必须运行与页面相关的测试或构建验证；发现问题要修复后再报告完成。
5. 没有明显可见改进空间后才算完成。最终交付说明应简要列出修改点和验证结果，不输出虚构的奖项或评分。

### 自评清单

```text
READ     当前页面与用户目标
CHECK    字体排版 / 留白节奏 / 视觉层级 / 色彩系统
CHECK    动效 / 微交互 / 响应式布局 / 原创性
COMPARE  获奖级网页的完成度与叙事节奏
PATCH    修复所有明显短板
RECHECK  直到 8 个维度都没有明显短板，或已完成 3 轮修订并记录剩余限制
VERIFY   测试、构建和关键页面回归
```
