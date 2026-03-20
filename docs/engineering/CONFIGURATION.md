# 环境变量配置

> TrumanWorld 环境变量完整说明

- 类型：`reference`
- 状态：`active`
- 最后更新：`2026-03-20`

---

## 快速配置

### 1. 基础配置（无需 LLM）

使用 heuristic provider 可以在不调用外部 LLM 的情况下跑通仿真闭环：

```bash
cp .env.example .env
# 编辑 .env
TRUMANWORLD_AGENT_BACKEND=heuristic
```

### 2. Claude SDK 配置

```bash
TRUMANWORLD_LLM_PROVIDER=anthropic
TRUMANWORLD_ANTHROPIC_API_KEY=sk-ant-xxx
TRUMANWORLD_ANTHROPIC_BASE_URL=    # 可选，用于兼容代理
```

### 3. OpenAI 兼容接口配置

支持任何兼容 OpenAI API 的服务（如 Groq、Ollama Local、Cohere 等）：

```bash
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_API_KEY=your-api-key
TRUMANWORLD_LLM_BASE_URL=          # API 端点
TRUMANWORLD_LLM_MODEL=gpt-4o       # 模型名
```

---

## 统一 LLM 配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRUMANWORLD_LLM_PROVIDER` | LLM 提供者：`anthropic` 或 `openai` | `anthropic` |
| `TRUMANWORLD_LLM_MODEL` | 模型名称 | - |
| `TRUMANWORLD_LLM_API_KEY` | API 密钥 | - |
| `TRUMANWORLD_LLM_BASE_URL` | API 端点 URL | - |

### Anthropic Provider

```bash
TRUMANWORLD_LLM_PROVIDER=anthropic
TRUMANWORLD_LLM_MODEL=claude-sonnet-4-20250514
TRUMANWORLD_LLM_API_KEY=sk-ant-xxx
TRUMANWORLD_LLM_BASE_URL=          # 可选，默认 https://api.anthropic.com
```

### OpenAI 兼容 Provider

支持所有兼容 OpenAI Chat Completions API 的服务：

```bash
# 标准 OpenAI
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=gpt-4o
TRUMANWORLD_LLM_API_KEY=sk-xxx
TRUMANWORLD_LLM_BASE_URL=          # 默认 https://api.openai.com/v1

# Groq
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=llama-3.3-70b-versatile
TRUMANWORLD_LLM_API_KEY=gsk_xxx
TRUMANWORLD_LLM_BASE_URL=https://api.groq.com/openai/v1

# Ollama Local
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=llama3.3
TRUMANWORLD_LLM_API_KEY=ollama    # 任意值
TRUMANWORLD_LLM_BASE_URL=http://localhost:11434/v1

# Cohere
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=command-a
TRUMANWORLD_LLM_API_KEY=xxx
TRUMANWORLD_LLM_BASE_URL=https://api.cohere.ai/v1
```

---

## Agent 后端配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRUMANWORLD_AGENT_BACKEND` | Agent 运行时：`heuristic`、`claude_sdk`、`langgraph` | `claude_sdk` |
| `TRUMANWORLD_AGENT_BUDGET_USD` | 单次 Agent 调用的最大预算（USD） | `1.0` |

### 可选后端

- `heuristic`：基于规则的启发式决策，不调用 LLM
- `claude_sdk`：使用 Claude Agent SDK
- `langgraph`：使用 LangGraph 图状态机

---

## 导演智能体配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRUMANWORLD_DIRECTOR_AUTO_INTERVENTION_ENABLED` | 是否启用自动干预 | `false` |
| `TRUMANWORLD_DIRECTOR_BACKEND` | 导演后端：`claude_sdk`、`langgraph`、`heuristic` | `claude_sdk` |
| `TRUMANWORLD_DIRECTOR_AGENT_MODEL` | 导演模型，留空则使用 `LLM_MODEL` | - |
| `TRUMANWORLD_DIRECTOR_DECISION_INTERVAL` | 导演决策频率（每 N tick） | `5` |

---

## 调度器配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRUMANWORLD_SCHEDULER_INTERVAL_SECONDS` | 自动 tick 间隔（秒） | `1.0` |
| `TRUMANWORLD_SCHEDULER_MAX_CONSECUTIVE_ERRORS` | 连续失败多少次后自动暂停，0 表示不限制 | `5` |

---

## 数据库与缓存

| 变量 | 说明 |
|------|------|
| `TRUMANWORLD_DATABASE_URL` | PostgreSQL 连接 URL（必填） |
| `TRUMANWORLD_REDIS_URL` | Redis 连接 URL |

---

## 应用配置

| 变量 | 说明 |
|------|------|
| `TRUMANWORLD_APP_ENV` | 环境：`development`、`production` |
| `TRUMANWORLD_API_PREFIX` | API 路径前缀 |
| `TRUMANWORLD_LOG_LEVEL` | 日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR` |
| `TRUMANWORLD_CORS_ALLOWED_ORIGINS` | 允许的 CORS 源列表（JSON 数组） |
| `TRUMANWORLD_DEMO_ADMIN_PASSWORD` | 演示模式管理员密码（留空不启用） |

---

## 前端配置

| 变量 | 说明 |
|------|------|
| `NEXT_PUBLIC_API_BASE_URL` | 浏览器端 API 地址，留空由 Next.js rewrites 代理 |

---

## LangGraph 特定配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `TRUMANWORLD_LANGGRAPH_REACTOR_STRUCTURED_ENABLED` | 启用结构化输出 | `false` |
| `TRUMANWORLD_LANGGRAPH_REACTOR_PROMPT_CACHE_ENABLED` | 启用提示词缓存 | `true` |
| `TRUMANWORLD_LANGGRAPH_REACTOR_MAX_CONCURRENCY` | 最大并发数 | `4` |

---

## Claude SDK 特定配置

| 变量 | 说明 |
|------|------|
| `TRUMANWORLD_CLAUDE_SDK_ISOLATED_HOME_ENABLED` | 启用隔离 home 目录 |
| `TRUMANWORLD_CLAUDE_SDK_HOME_DIR` | Claude SDK home 目录路径 |
| `TRUMANWORLD_CLAUDE_SDK_REACTOR_POOL_ENABLED` | 启用 reactor 连接池 |

---

## 兼容性别名（已废弃）

以下变量已废弃，建议使用新的 `LLM_*` 配置：

| 旧变量 | 新变量 | 说明 |
|--------|--------|------|
| `TRUMANWORLD_ANTHROPIC_API_KEY` | `TRUMANWORLD_LLM_API_KEY` | Anthropic API 密钥 |
| `TRUMANWORLD_ANTHROPIC_BASE_URL` | `TRUMANWORLD_LLM_BASE_URL` | Anthropic API 端点 |
| `TRUMANWORLD_ANTHROPIC_MODEL` | `TRUMANWORLD_LLM_MODEL` | 兼容 Anthropic 接口的模型名 |

---

## 完整示例

### 开发环境（Anthropic）

```bash
TRUMANWORLD_APP_ENV=development
TRUMANWORLD_DATABASE_URL=postgresql+psycopg://truman:password@localhost:5432/trumanworld
TRUMANWORLD_REDIS_URL=redis://localhost:6379/0
TRUMANWORLD_LLM_PROVIDER=anthropic
TRUMANWORLD_LLM_MODEL=claude-sonnet-4-20250514
TRUMANWORLD_LLM_API_KEY=sk-ant-xxx
TRUMANWORLD_AGENT_BACKEND=claude_sdk
TRUMANWORLD_LOG_LEVEL=DEBUG
TRUMANWORLD_CORS_ALLOWED_ORIGINS=["http://127.0.0.1:13000","http://localhost:13000"]
```

### 生产环境（OpenAI）

```bash
TRUMANWORLD_APP_ENV=production
TRUMANWORLD_DATABASE_URL=postgresql+psycopg://truman:password@db:5432/trumanworld
TRUMANWORLD_REDIS_URL=redis://redis:6379/0
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=gpt-4o
TRUMANWORLD_LLM_API_KEY=sk-xxx
TRUMANWORLD_LLM_BASE_URL=https://api.openai.com/v1
TRUMANWORLD_AGENT_BACKEND=claude_sdk
TRUMANWORLD_LOG_LEVEL=INFO
TRUMANWORLD_CORS_ALLOWED_ORIGINS=["https://your-domain.com"]
```

### 本地 Ollama

```bash
TRUMANWORLD_LLM_PROVIDER=openai
TRUMANWORLD_LLM_MODEL=llama3.3
TRUMANWORLD_LLM_API_KEY=ollama
TRUMANWORLD_LLM_BASE_URL=http://localhost:11434/v1
TRUMANWORLD_AGENT_BACKEND=langgraph
```
