# AI Truman World

AI Truman World 是一个基于 `Claude Agent SDK` 的 AI 社会模拟系统。

当前仓库处于 MVP 骨架阶段，目标是先搭建：

- `backend/`：Python + FastAPI 仿真与 API 层
- `frontend/`：Next.js + TypeScript 导演控制台
- `agents/`：配置驱动的 agent 注册表
- `docs/`：PRD、架构和规模估算

## 目录结构

```text
backend/     后端服务与仿真核心
frontend/    前端控制台
agents/      agent 配置与提示词
docs/        产品与架构文档
```

## 本地开发

### 环境要求

- Python `3.12+`
- Node.js `20+`
- PostgreSQL `16+`
- Redis `7+`
- `uv`
- 可选：`pre-commit`

### 初始化

```bash
cp .env.example .env
make install
```

### 启动后端

```bash
make backend-dev
```

默认地址：

- API: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/api/health`

### 启动前端

```bash
make frontend-dev
```

默认地址：

- UI: `http://127.0.0.1:3000`

### 数据库迁移

```bash
make migrate
```

### 代码检查

```bash
make lint
make pre-commit
```

## 常用命令

```bash
make install         # 安装后端和前端依赖
make backend-dev     # 启动 FastAPI 开发服务
make frontend-dev    # 启动 Next.js 开发服务
make migrate         # 执行 Alembic 升级
make lint            # 运行后端 ruff 检查
make format          # 运行后端 ruff format
make test            # 运行后端 pytest
make pre-commit      # 运行 pre-commit hooks
```

## 当前阶段

已完成：

- MVP 文档
- 仓库初始化
- 基础项目骨架
- 数据层基础结构
- Alembic 初始化

下一步：

- SimulationRunner
- Claude Agent SDK runtime
- Timeline API
- AgentRegistry / ConfigLoader / PromptLoader
