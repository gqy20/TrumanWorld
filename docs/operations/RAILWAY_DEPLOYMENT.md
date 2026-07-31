# Railway 部署说明

- 类型：`runbook`
- 状态：`active`
- 负责人：`infra`
- 最后更新：`2026-07-31`

本项目在 Railway 上拆为 `backend`、`frontend` 和 PostgreSQL 三个服务。后端运行时会读取
仓库根目录的 `agents/`、`scenarios/` 和 `scripts/`，因此两个应用服务都从仓库根目录构建，
再通过独立的 config-as-code 文件选择各自命令。

Railway 官方说明：Root Directory 会改变构建和启动命令的工作目录；自定义配置文件路径不跟随
Root Directory，必须使用仓库绝对路径。参见 [Deploying a Monorepo](https://docs.railway.com/deployments/monorepo)
和 [Using Config as Code](https://docs.railway.com/config-as-code)。

## 服务配置

### Backend

在服务设置中配置：

- Root Directory：`/`（仓库根目录）
- Config File：`/backend/railway.toml`
- Healthcheck Path：由配置文件设为 `/api/ready`

[backend/railway.toml](../../backend/railway.toml) 已声明：

- Railpack 构建和 `uv sync --frozen`
- pre-deploy 阶段执行 `alembic upgrade head`
- 启动 Uvicorn 并监听 Railway 注入的 `PORT`
- readiness 只有在数据库执行 `SELECT 1` 成功后才返回 200

必要变量：

```env
TRUMANWORLD_APP_ENV=production
TRUMANWORLD_LOG_LEVEL=INFO
TRUMANWORLD_LOG_FORMAT=json
TRUMANWORLD_DATABASE_URL=${{Postgres.DATABASE_URL}}
TRUMANWORLD_DEMO_ADMIN_PASSWORD=替换为强密码
TRUMANWORLD_CORS_ALLOWED_ORIGINS=["https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}"]
```

非开发环境缺少 `TRUMANWORLD_DATABASE_URL` 或 `TRUMANWORLD_DEMO_ADMIN_PASSWORD` 时，后端会拒绝
启动。管理员密码保护创建、启动、暂停、删除和导演注入等写操作。

不使用 LLM 的链路验证配置：

```env
TRUMANWORLD_AGENT_BACKEND=heuristic
TRUMANWORLD_DIRECTOR_BACKEND=heuristic
TRUMANWORLD_DIRECTOR_AUTO_INTERVENTION_ENABLED=false
```

Anthropic / Claude SDK 配置：

```env
TRUMANWORLD_AGENT_BACKEND=claude_sdk
TRUMANWORLD_LLM_PROVIDER=anthropic
TRUMANWORLD_LLM_API_KEY=替换为真实密钥
TRUMANWORLD_LLM_MODEL=替换为模型名
TRUMANWORLD_DIRECTOR_BACKEND=claude_sdk
TRUMANWORLD_DIRECTOR_AGENT_MODEL=替换为导演模型名
```

### Frontend

在服务设置中配置：

- Root Directory：`/`（仓库根目录）
- Config File：`/frontend/railway.toml`
- 生成公网域名

必要变量：

```env
INTERNAL_API_BASE_URL=http://backend.railway.internal/api
NEXT_PUBLIC_API_BASE_URL=/api
```

[frontend/railway.toml](../../frontend/railway.toml) 使用 pnpm 安装、构建和启动 Next.js。
浏览器访问相对 `/api`，Next.js rewrite 再通过 Railway 私网访问后端。

### PostgreSQL

在同一 Railway Project 添加 PostgreSQL 服务，并把它的 `DATABASE_URL` 引用给 backend。
当前主链路不要求 Redis，也没有必须启用的 pgvector 扩展。

## 自动引导脚本

仓库提供 [railway-bootstrap.sh](../../scripts/railway-bootstrap.sh)。运行前至少提供前端域名和生产
管理员密码：

```bash
FRONTEND_DOMAIN=your-frontend.up.railway.app \
TRUMANWORLD_DEMO_ADMIN_PASSWORD='replace-with-a-strong-password' \
bash scripts/railway-bootstrap.sh
```

启用 Claude SDK 时额外提供：

```bash
FRONTEND_DOMAIN=your-frontend.up.railway.app \
TRUMANWORLD_DEMO_ADMIN_PASSWORD='replace-with-a-strong-password' \
ENABLE_CLAUDE=true \
TRUMANWORLD_AGENT_BACKEND=claude_sdk \
TRUMANWORLD_LLM_API_KEY='your-key' \
TRUMANWORLD_LLM_MODEL='your-model' \
TRUMANWORLD_DIRECTOR_AGENT_MODEL='your-director-model' \
bash scripts/railway-bootstrap.sh
```

脚本会创建服务、设置核心变量，并输出控制台中仍需确认的 Root Directory 和 Config File。
密钥通过标准输入写入 Railway，不会出现在命令参数中。

## 部署与验收

```bash
railway link
railway up --service backend
railway up --service frontend
railway logs --service backend
railway logs --service frontend
```

首次上线检查：

1. 后端日志显示 Alembic pre-deploy 成功。
2. `GET /api/health` 返回 `{"status":"ok"}`。
3. `GET /api/ready` 返回 `{"status":"ready"}`。
4. 前端首页能读取 run 列表，world、timeline 和 agent 页面没有 SSR 请求错误。
5. 未解锁时写操作不可见；直接调用写接口返回 401。
6. Railway deployment details 中的构建、pre-deploy、启动和 healthcheck 均显示来自配置文件。

Railway healthcheck 只用于新部署切流前的就绪验证，不是持续监控。生产环境仍应另配 uptime 和告警。
参见 [Railway Healthchecks](https://docs.railway.com/deployments/healthchecks)。

## 常见问题

- 构建命令找不到 `backend/` 或 `frontend/`：确认 Root Directory 是仓库根目录 `/`。
- 配置没有生效：确认 Config File 分别是 `/backend/railway.toml` 和 `/frontend/railway.toml`。
- `/api/ready` 返回 503：检查数据库引用变量、私网连通性和 Alembic 日志。
- 前端 SSR 访问 `127.0.0.1:18080`：检查 `INTERNAL_API_BASE_URL`。
- 浏览器写操作返回 401：使用页面右上角管理员入口输入
  `TRUMANWORLD_DEMO_ADMIN_PASSWORD`。

本地开发使用 [docker-compose.yml](../../docker-compose.yml) 及开发 Dockerfile；Railway 使用 Railpack 配置，
不要把本地 `--reload` / `pnpm dev` 命令当作生产启动方式。
