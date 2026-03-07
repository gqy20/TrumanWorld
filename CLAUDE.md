# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Truman World is an AI social simulation system built with Claude Agent SDK. It's a small-scale,可持续运行、可观察、可回放的 AI 小镇仿真器。MVP 目标：10-20 个 agent 在一个小镇持续运行 3-7 天。

## Common Commands

```bash
# Install dependencies
make install

# Start backend (FastAPI on http://127.0.0.1:8000)
make backend-dev

# Start frontend (Next.js on http://127.0.0.1:3000)
make frontend-dev

# Database migrations
make migrate

# Code quality
make lint        # ruff check
make format      # ruff format

# Run tests
make test        # pytest (run from backend/)
make pre-commit  # pre-commit hooks

# Single test (from backend/)
python -m pytest tests/test_file.py::test_name
```

## Architecture

### Tech Stack
- **Backend**: Python + FastAPI
- **Frontend**: Next.js + TypeScript + Tailwind
- **AI Cognition**: Claude Agent SDK
- **Database**: PostgreSQL + pgvector
- **Cache**: Redis

### Backend Modules (4 core modules)

```
backend/app/
├── api/         # HTTP routes, run control, queries
├── sim/         # Simulation loop, world state, action resolver
├── agent/       # Claude SDK, registry, planner/reactor/reflector
└── store/       # SQLAlchemy models, persistence, memory retrieval
```

### Agent Configuration Pattern (参考 IssueLab)

Agents are configured declaratively in `agents/<id>/` directories:

```
agents/
├── _template/
│   ├── agent.yml   # id, name, occupation, home, personality, capabilities, model
│   └── prompt.md   # role definition and behavior instructions
└── <agent_id>/
    ├── agent.yml
    └── prompt.md
```

Key capability flags in `agent.yml`:
- `reflection`: 是否启用每日反思
- `dialogue`: 是否启用对话生成
- `mcp`: 是否启用 MCP 工具
- `subagents`: 是否启用子 agent

### Agent Runtime Flow

```
registry.py      → 扫描 agents/*/agent.yml
config_loader.py → 解析人格、职业、model config
prompt_loader.py → 加载 prompt.md 并拼装上下文
runtime.py       → 封装 Claude Agent SDK 调用
context_builder.py → 组装世界状态、地点、附近 agent、记忆
planner.py       → 早晨生成日计划
reactor.py       → 遇到社交/异常事件时反应
reflector.py     → 晚上做每日反思
```

### Tick Flow (每个 tick 执行)

1. 推进世界时间
2. 选择一个 agent
3. 判断是否需要 Claude cognition
4. 生成动作意图 (planner/reactor)
5. 校验动作 (action_resolver)
6. 应用动作
7. 写 event
8. 更新 relationship
9. 写 memory

### MVP Data Model (6 tables)

- `simulation_runs` - run 生命周期, 当前 tick
- `locations` - 地点信息, 坐标, 容量
- `agents` - agent 状态, 目标, 地点, profile
- `events` - 所有结构化事件 (talk, action, director injection)
- `relationships` - familiarity, trust, affinity
- `memories` - recent, episodic, reflection

### Director Layer

Only 4 capabilities in MVP:
- `start_run` / `pause_run` / `resume_run`
- `inspect` (查看 run/agent/timeline)
- `inject_event` (仅限简单世界事件: 活动、关闭、广播)

不允许直接修改 agent 属性或 relationships。

### Claude SDK 调用边界

Only in:
- 早晨生成粗粒度日计划 (planner)
- 社交/异常事件反应 (reactor)
- 晚上反思 (reflector)

NOT in:
- 每个 tick 基础移动
- 简单 work/rest 执行
- 直接改 world state

## Environment Variables

Create `.env` from `.env.example`:

```
TRUMANWORLD_APP_ENV=development
TRUMANWORLD_API_PREFIX=/api
TRUMANWORLD_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/trumanworld
TRUMANWORLD_REDIS_URL=redis://localhost:6379/0
TRUMANWORLD_ANTHROPIC_API_KEY=<your-key>
TRUMANWORLD_LOG_LEVEL=INFO
```

## API Endpoints (MVP)

- `POST /runs` - 创建新 run
- `POST /runs/{id}/start` - 启动
- `POST /runs/{id}/pause` - 暂停
- `POST /runs/{id}/resume` - 恢复
- `POST /runs/{id}/director/events` - 导演注入事件
- `GET /runs/{id}` - 获取 run 状态
- `GET /runs/{id}/timeline` - 获取时间线事件
- `GET /runs/{id}/agents/{agent_id}` - 获取 agent 详情
- `GET /api/health` - 健康检查

## Testing

Tests are in `backend/tests/`. Key fixtures in `conftest.py`:
- `db_session` - database session fixture
- `client` - FastAPI test client

Run single test:
```bash
cd backend && python -m pytest tests/test_agents_api.py::test_get_agents -v
```
