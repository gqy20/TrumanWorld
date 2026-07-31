# Changelog

> 所有重要变更将记录在此文件中

格式参考：[Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)

---

## [Unreleased]

### Added
- 可读取现有 run 或推进 tick 的运行质量评估 CLI，输出动作、导演、主体告警、记忆与性能指标
- 数据库 readiness 探针 `/api/ready`，供部署切流前检查关键依赖
- Voxel plot / parcel 布局模型、入口、角色锚点和标准场景无重叠测试
- PostgreSQL integration tests 进入 GitHub Actions

### Fixed
- 运行质量评估禁止与自动调度并发推进 tick，并将 agent 记忆快照合并为单次批量查询
- 删除 run 时同步清理治理案件、限制和经济状态/日志
- 世界 pulse 首次轮询、时间线筛选分页与迟到响应竞态
- Demo 权限状态请求失败时改为只读 fail-closed
- Docker 开发链路统一使用 `uv --group dev` 和 pnpm
- Git hooks 安装入口、CI path filters 与 Railway config-as-code 漂移

### Changed
- Director 单次预算提高到 `$0.20`，并禁用不需要的 Claude SDK 工具上下文以降低调用成本
- 非开发环境必须设置 `TRUMANWORLD_DEMO_ADMIN_PASSWORD`
- Railway 使用仓库根目录构建、pre-deploy 迁移和数据库 readiness healthcheck
- 世界页改进窄屏滚动与侧栏覆盖行为

---

## [v0.1.0] - 2026-03-07

### Added
- GitHub Actions CI 工作流 (Python lint + pytest)
- GitHub Actions 前端 CI 检查 (lint + build)
- pytest 覆盖率报告集成 Codecov
- OpenAPI 文档增强 (tags, summaries, descriptions, examples)
- README.md 添加 CI 和 Codecov 徽章
- GitHub 仓库配置 topics 和 description
- 初始项目骨架
- MVP 产品与技术文档
- `agents/` 配置驱动的 Agent 注册表
- FastAPI 后端基础架构
- Next.js 导演控制台骨架
- SQLAlchemy 数据模型
- Alembic 迁移配置
- Makefile 开发命令
- MIT License 文件
- 开发文档：DEVELOPMENT.md, INDEX.md, CONTRIBUTING.md

### Changed
- README 重构为产品宣传风格
