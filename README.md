# AI Truman World

AI Truman World 是一个基于 `Claude Agent SDK` 的 AI 社会模拟系统。

当前仓库处于 MVP 骨架阶段，目标是先搭建：

- `backend/`：Python + FastAPI 仿真与 API 层
- `frontend/`：Next.js + TypeScript 导演控制台
- `agents/`：配置驱动的 agent 注册表
- `docs/`：PRD、架构和规模估算

当前默认使用 `heuristic` agent provider 跑通仿真闭环；当配置 `Claude Agent SDK` 所需环境后，可以切换到真实的 `claude` provider。

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
cp frontend/.env.local.example frontend/.env.local
make install
```

说明：

- 后端会读取仓库根目录的 `.env`
- 前端 `Next.js` 会读取 `frontend/.env.local`

如果要启用真实 Claude 决策层，在 `.env` 中至少配置：

```bash
TRUMANWORLD_AGENT_PROVIDER=claude
TRUMANWORLD_ANTHROPIC_API_KEY=your_key
TRUMANWORLD_ANTHROPIC_BASE_URL=
TRUMANWORLD_AGENT_MODEL=claude-sonnet-4-20250514
TRUMANWORLD_CORS_ALLOWED_ORIGINS=["http://127.0.0.1:33100","http://localhost:33100"]
```

如果前端不走默认后端地址，在 `frontend/.env.local` 中配置：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
INTERNAL_API_BASE_URL=http://127.0.0.1:8000/api
```

- `NEXT_PUBLIC_API_BASE_URL` 给浏览器端请求使用
- `INTERNAL_API_BASE_URL` 给 Next.js 服务端渲染时请求后端使用

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

### 一次性启动前后端和数据库

```bash
docker compose up --build
```

默认暴露：

- PostgreSQL: `localhost:55432`
- Backend API: `http://127.0.0.1:38000`
- Frontend UI: `http://127.0.0.1:33100`

说明：

- `backend` 容器启动时会自动执行 `alembic upgrade head`
- `backend` 镜像会安装 `Claude Code` CLI，供 `claude_agent_sdk` 在容器内调用
- `frontend` 会同时注入：
  - `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:38000/api`
  - `INTERNAL_API_BASE_URL=http://backend:8000/api`
- Compose 当前是开发向配置，使用挂载卷与热重载

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
- Agent registry / runtime
- Simulation service 与 director console 闭环
- run 生命周期控制与单步 tick 推进

下一步：

- Claude provider 的真实 prompt/输出约束细化
- 记忆写入与检索
- relationship 更新
- timeline 自动刷新与更完整导演操作
