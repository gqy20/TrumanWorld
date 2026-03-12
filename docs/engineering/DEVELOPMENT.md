# 开发指南

> 快速上手 TrumanWorld 开发环境

- 类型：`guide`
- 状态：`active`
- 负责人：`repo`
- 最后更新：`2026-03-11`

---

## 📋 环境要求

### 必需

| 工具 | 版本 | 说明 |
|------|------|------|
| Python | 3.13 | 后端运行时 |
| Node.js | 20.9+ 且 <21 | 前端运行时 |
| PostgreSQL | 17.3 | 主数据库 |
| Redis | 7+ | 缓存层 |
| uv | 0.9.18 | Python 包管理 |

### 可选

| 工具 | 说明 |
|------|------|
| Docker | 数据库容器化运行 |
| pre-commit | Git hooks 管理 |

---

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/gqy20/TrumanWorld.git
cd TrumanWorld
```

### 2. 配置环境变量

```bash
# 后端配置
cp .env.example .env

# 前端配置
cp frontend/.env.local.example frontend/.env.local
```

编辑 `.env` 配置至少以下变量：

```bash
# 可选：使用 heuristic provider 跑通仿真闭环
TRUMANWORLD_AGENT_BACKEND=heuristic

# 如需 Claude 决策层，再配置：
# TRUMANWORLD_ANTHROPIC_API_KEY=sk-ant-xxx
```

### 3. 安装依赖

```bash
# 一次性安装前后端
make install

# 或分别安装
make backend-install
make frontend-install
```

### 4. 启动数据库

```bash
# 使用 Docker（推荐）
make db-start

# 或手动启动 PostgreSQL 后，执行迁移
make db-migrate
```

如果你不保留本地数据库数据，先执行一次清理再重建：

```bash
make db-clean
make db-start
make db-migrate
```

### 5. 启动开发服务器

```bash
# 一键启动前后端 + 数据库
make dev

# 或分别启动
make backend-dev    # http://127.0.0.1:18080
make frontend-dev   # http://127.0.0.1:13000
```

默认开发端口：

- 前端：`13000`
- 后端：`18080`
- 数据库：`5432`

---

## 🔧 常用命令

### 开发

```bash
make dev            # 一键启动前后端 + 数据库
make backend-dev    # 后端开发模式（热重载）
make frontend-dev   # 前端开发模式（热重载）
```

### 数据库

```bash
make db-start       # 启动 PostgreSQL 容器
make db-stop        # 停止容器
make db-migrate     # 执行数据库迁移
make db-clean       # 删除容器（数据会丢失）
make db-status      # 查看容器状态
```

### 代码质量

```bash
make lint           # Ruff 检查
make format         # Ruff 格式化
make pre-commit     # 运行 pre-commit hooks
cd frontend && npm run lint   # ESLint + TypeScript
```

### 测试

```bash
make test           # 运行所有测试
cd frontend && npm run build  # 前端生产构建检查
```

### 端口管理

```bash
make check-ports    # 检查端口占用
make kill-ports     # 终止占用端口的进程
```

---

## 📁 项目结构

```
TrumanWorld/
├── backend/              # Python FastAPI 后端
│   ├── app/
│   │   ├── api/         # HTTP 路由
│   │   ├── sim/         # 仿真核心
│   │   ├── agent/       # Agent 运行时
│   │   ├── scenario/    # 题材/世界规则层
│   │   ├── store/       # 数据持久化
│   │   └── infra/       # 基础设施
│   ├── tests/           # 测试文件
│   └── pyproject.toml
├── frontend/             # Next.js 前端
│   ├── app/             # App Router 路由
│   ├── components/      # React 组件
│   └── package.json
├── agents/               # Agent 配置
│   └── <agent_id>/
│       ├── agent.yml    # 配置
│       └── prompt.md    # 角色提示词
├── backend/
│   └── app/
│       └── agent/
│           └── prompts/
│               └── system.md  # 全局 system prompt
├── docs/                 # 文档
└── AGENTS.md             # 仓库协作说明
```

### Scenario 结构

后端现在支持通过 `Scenario` 抽象切换题材规则：

```text
backend/app/scenario/
  base.py
  truman_world/
    scenario.py
    coordinator.py
    context.py
    heuristics.py
    seed.py
    state.py
  open_world/
    scenario.py
```

含义是：

- `sim` 不再直接绑定 Truman world 具体实现
- `SimulationService` 依赖 `Scenario` 接口
- 题材特定的 heuristic、seed、state update 放在各自 scenario 下

当前 run 已持久化 `scenario_type`，所以创建、手动 tick、自动调度、恢复运行都会基于同一世界类型执行。

新增 scenario 时，最小需要实现的是：

- `with_session`
- `configure_runtime`
- `configure_agent_context`
- `observe_run`
- `build_director_plan`
- `merge_agent_profile`
- `fallback_intent`
- `seed_demo_run`
- `update_state_from_events`

---

## 🐛 调试技巧

### 后端调试

#### 1. 查看日志

```bash
# 设置日志级别
TRUMANWORLD_LOG_LEVEL=DEBUG make backend-dev
```

#### 2. 数据库调试

```bash
# 连接数据库
docker exec -it trumanworld-db-test psql -U truman -d trumanworld

# 查看当前 run 状态
SELECT id, status, current_tick FROM simulation_runs;

# 查看最新事件
SELECT * FROM events ORDER BY created_at DESC LIMIT 10;
```

#### 3. API 测试

```bash
# 健康检查
curl http://127.0.0.1:8000/api/health

# 创建 run
curl -X POST http://127.0.0.1:8000/api/runs \
  -H "Content-Type: application/json" \
  -d '{"name": "test-run"}'

# 启动 run
curl -X POST http://127.0.0.1:8000/api/runs/{id}/start
```

### 前端调试

#### 1. 开发模式日志

Next.js 开发服务器会在终端输出编译状态和错误。

#### 2. 浏览器控制台

前端错误和 API 调用日志在浏览器控制台查看。

#### 3. 网络请求调试

打开 DevTools Network 面板查看：
- API 请求/响应
- WebSocket 连接状态

---

## 🔄 CI/CD

### GitHub Actions

项目在每次 push 和 PR 时自动运行：

| Job | 说明 |
|-----|------|
| `lint` | Python ruff check + format |
| `frontend-check` | Frontend lint + build |
| `test` | pytest + 覆盖率上传 Codecov |

### Codecov 集成

测试覆盖率会自动上传至 Codecov：
https://codecov.io/gh/gqy20/TrumanWorld

覆盖率阈值配置见 `codecov.yml`。

### 本地运行 CI 检查

```bash
# 运行 pre-commit（包含 lint + format + actionlint）
make pre-commit
```

---

## 🧪 测试

### 运行测试

```bash
cd backend
uv run pytest                    # 运行所有测试
uv run pytest -v                 # 详细输出
uv run pytest -x                 # 遇到失败停止
uv run pytest tests/test_file.py # 运行单个文件
uv run pytest -k test_name       # 按名称过滤
```

### 测试覆盖

```bash
cd backend
uv run pytest --cov=app --cov-report=html
open htmlcov/index.html
```

覆盖率报告会自动上传至 [Codecov](https://codecov.io/gh/gqy20/TrumanWorld)。

### 测试分类

| 目录 | 说明 |
|------|------|
| `test_agents_api.py` | Agent API 测试 |
| `test_runs_api.py` | Run 生命周期 API 测试 |
| `test_simulation_core.py` | 仿真核心逻辑测试 |
| `test_repositories.py` | 数据访问层测试 |

---

## 🗃️ 数据库

### 表结构

| 表名 | 说明 |
|------|------|
| `simulation_runs` | Run 生命周期 |
| `agents` | Agent 状态 |
| `locations` | 地点信息 |
| `events` | 事件记录 |
| `relationships` | 关系状态 |
| `memories` | 记忆存储 |

### 执行迁移

```bash
# 查看当前版本
cd backend && uv run alembic current

# 升级到最新
uv run alembic upgrade head

# 回退一个版本
uv run alembic downgrade -1

# 生成新迁移
uv run alembic revision -m "add_new_column"
```

---

## 🔑 Agent 配置

### 创建新 Agent

1. 创建目录：

```bash
mkdir agents/new_agent
```

2. 创建配置文件 `agents/new_agent/agent.yml`：

```yaml
id: new_agent
name: New Agent
occupation: teacher
home: house_a
personality:
  openness: 0.8
  conscientiousness: 0.6
capabilities:
  reflection: true
  dialogue: true
  mcp: false
  subagents: false
model:
  max_turns: 8
  max_budget_usd: 1.0
```

3. 创建提示词 `agents/new_agent/prompt.md`：

```markdown
# 角色定义

你是 TrumanWorld 中的一名教师...

# 行为要求

- 遵守教师职业习惯
- ...
```

说明：

- `agents/<id>/prompt.md` 只写角色身份、行为风格和个体差异
- 全局规则（例如统一使用中文、世界约束、输出边界）统一放在 `backend/app/agent/prompts/system.md`

---

## ⚠️ 常见问题

### Q: 端口被占用

```bash
# 检查端口
make check-ports

# 终止占用进程
make kill-ports
```

### Q: 数据库无法连接

1. 检查容器状态：`make db-status`
2. 重启容器：`make db-stop && make db-start`
3. 重新迁移：`make db-migrate`

### Q: Claude API 调用失败

1. 检查 `.env` 中 `TRUMANWORLD_ANTHROPIC_API_KEY` 是否配置
2. 检查网络代理设置
3. 可临时切换到 `heuristic` provider 测试仿真逻辑

### Q: 前端无法连接后端

1. 检查 `frontend/.env.local` 中 `NEXT_PUBLIC_API_BASE_URL`
2. 确认后端服务已启动
3. 检查 CORS 配置

### Q: 测试失败

1. 确保数据库容器已启动
2. 检查测试依赖：`cd backend && uv sync --extra dev`
3. 清理缓存后重试：`rm -rf .pytest_cache`

---

## 📚 文档导航

| 文档 | 说明 |
|------|------|
| [PRD](../product/PRD.md) | 产品需求文档 |
| [当前架构](../engineering/CURRENT_ARCHITECTURE.md) | 当前技术架构说明 |
| [MVP 架构历史稿](../references/MVP_ARCHITECTURE.md) | 历史架构基线 |
| [任务拆解](../references/TASK_BREAKDOWN.md) | 开发任务分解 |
| [Build vs Buy](../references/BUILD_VS_BUY.md) | 复用/自研分析 |
| [代码估算](../references/ESTIMATE.md) | 代码量预估 |
