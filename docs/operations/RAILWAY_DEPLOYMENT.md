# Railway 部署说明

- 类型：`runbook`
- 状态：`active`
- 负责人：`infra`
- 最后更新：`2026-03-11`

本项目适合在 Railway 上拆成 3 个服务：

- `backend`：FastAPI + Alembic
- `frontend`：Next.js
- `postgres`：Railway PostgreSQL

当前代码里虽然有 `docker-compose.yml` 和前后端 `Dockerfile`，但它们是本地开发用途，不建议直接拿去做 Railway 生产部署：

- 后端 Dockerfile 会启动 `uvicorn --reload`
- 前端 Dockerfile 会启动 `npm run dev`
- `docker-compose.yml` 里的 `db` 主机名只适用于 Compose 网络，不适用于 Railway

另外，仓库里已经补了 Railway config-as-code 文件：

- [backend/railway.toml](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/backend/railway.toml)
- [frontend/railway.toml](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/frontend/railway.toml)

它们显式指定了 `builder = "RAILPACK"`，避免 Railway 因为检测到现有 `Dockerfile` 而误用开发态镜像构建流程。

## 推荐拓扑

### 1. Backend

- Root Directory: `/backend`
- Build Command: `uv sync --frozen`
- Start Command: `sh scripts/start-railway.sh`

必要变量：

```env
TRUMANWORLD_APP_ENV=production
TRUMANWORLD_LOG_LEVEL=INFO
TRUMANWORLD_DATABASE_URL=${{Postgres.DATABASE_URL}}
TRUMANWORLD_CORS_ALLOWED_ORIGINS=["https://${{Frontend.RAILWAY_PUBLIC_DOMAIN}}"]
```

按需补充：

```env
TRUMANWORLD_AGENT_BACKEND=claude_sdk
TRUMANWORLD_ANTHROPIC_API_KEY=你的_key
TRUMANWORLD_AGENT_MODEL=你的模型名
TRUMANWORLD_DIRECTOR_BACKEND=claude_sdk
TRUMANWORLD_DIRECTOR_AGENT_MODEL=你的导演模型名
```

如果你暂时只想验证链路，不想消耗 LLM 额度，可以先这样：

```env
TRUMANWORLD_AGENT_BACKEND=heuristic
TRUMANWORLD_DIRECTOR_BACKEND=heuristic
```

说明：

- 启动脚本会在进程启动前执行 `alembic upgrade head`
- Railway 私网只在运行时可用，所以迁移应放在 Start Command 阶段，不要放到 Build Command。Railway 官方文档也明确说明了这一点

### 2. Frontend

- Root Directory: `/frontend`
- Build Command: `npm ci && npm run build`
- Start Command: `sh scripts/start-railway.sh`

变量：

```env
INTERNAL_API_BASE_URL=http://backend.railway.internal/api
NEXT_PUBLIC_API_BASE_URL=
```

说明：

- 当前前端已经支持服务端走 `INTERNAL_API_BASE_URL`，浏览器端走 `/api`
- `frontend/next.config.ts` 已配置 rewrite，`/api/*` 会转发到后端
- Railway 私网文档说明同项目内服务可直接通过 `SERVICE_NAME.railway.internal` 通信，不需要额外暴露后端公网域名
- 因此前端公开，后端可只保留私网访问；如果你需要直接打开 `/api/docs`，再给后端单独生成公网域名

### 3. Postgres

直接在 Railway 项目里添加 PostgreSQL 服务即可。

本项目当前迁移和模型没有发现对 `pgvector` 扩展的实际硬依赖，所以先用标准 PostgreSQL 即可。

## CLI 操作建议

Railway 官方 CLI 文档里 `railway up` 支持按服务部署，但对于 monorepo，官方也说明更稳的方式是先在服务设置里把 Root Directory 配好。

建议顺序：

1. `railway login`
2. 在 Railway 控制台新建一个 Project
3. 在项目里创建 `backend`、`frontend`、`Postgres` 三个服务
4. 把仓库连接到 `backend` 和 `frontend`
5. 分别设置 Root Directory、Build Command、Start Command、变量
6. 先部署 `backend`
7. 再部署 `frontend`

如果你已经把当前目录 link 到项目里，也可以用 CLI 触发重部署：

```bash
railway up --service backend
railway up --service frontend
```

注意：Railway 官方文档提到，如果你在 monorepo 子目录里直接运行 `railway up`，默认仍可能从项目根目录上传；要长期稳定按子目录部署，应以服务配置里的 Root Directory 为准。

## 一套可直接执行的 CLI 流程

下面假设：

- Railway 项目名叫 `TrumanWorld`
- 服务名固定为 `backend`、`frontend`、`postgres`
- 你在仓库根目录执行命令

### 1. 登录并初始化项目

```bash
railway login
railway init -n TrumanWorld
```

检查当前绑定状态：

```bash
railway status
```

### 2. 创建 3 个服务

```bash
railway add --service backend
railway add --service frontend
railway add --database postgres
```

创建完后再看一次：

```bash
railway service status
```

### 3. 给前端生成公网域名

```bash
railway domain --service frontend
```

这一步会返回一个 Railway 域名，后面把它填进后端 CORS。

### 4. 配 backend 变量

先设置基础变量：

```bash
railway variable set --service backend \
  TRUMANWORLD_APP_ENV=production \
  TRUMANWORLD_LOG_LEVEL=INFO \
  TRUMANWORLD_DATABASE_URL='${{Postgres.DATABASE_URL}}'
```

然后设置 CORS。把下面的 `YOUR_FRONTEND_DOMAIN` 替换成上一步生成的域名，例如 `your-app.up.railway.app`：

```bash
railway variable set --service backend \
  'TRUMANWORLD_CORS_ALLOWED_ORIGINS=["https://YOUR_FRONTEND_DOMAIN"]'
```

如果你要启用 Claude：

```bash
railway variable set --service backend \
  TRUMANWORLD_AGENT_BACKEND=claude_sdk \
  TRUMANWORLD_AGENT_MODEL='your-model' \
  TRUMANWORLD_DIRECTOR_BACKEND=claude_sdk \
  TRUMANWORLD_DIRECTOR_AGENT_MODEL='your-director-model'
```

再单独从标准输入写入 API Key，避免进 shell 历史：

```bash
printf '%s' 'YOUR_ANTHROPIC_API_KEY' | railway variable set --service backend TRUMANWORLD_ANTHROPIC_API_KEY --stdin
```

如果你只想先把站跑起来，不想接 LLM：

```bash
railway variable set --service backend \
  TRUMANWORLD_AGENT_BACKEND=heuristic \
  TRUMANWORLD_DIRECTOR_BACKEND=heuristic
```

### 5. 配 frontend 变量

```bash
railway variable set --service frontend \
  INTERNAL_API_BASE_URL=http://backend.railway.internal/api \
  NEXT_PUBLIC_API_BASE_URL=
```

### 6. 在 Railway 服务设置里补 Root Directory / Config File

CLI 目前不适合稳定管理这些构建设置，建议直接在 Railway 控制台里配：

`backend`

- Root Directory: `backend`
- Config File: `/backend/railway.toml`

`frontend`

- Root Directory: `frontend`
- Config File: `/frontend/railway.toml`

如果你不想用 Config File，才退回到手动填写：

`backend`

- Build Command: `uv sync --frozen`
- Start Command: `sh scripts/start-railway.sh`

`frontend`

- Build Command: `npm ci && npm run build`
- Start Command: `sh scripts/start-railway.sh`

### 7. 触发部署

```bash
railway up --service backend
railway up --service frontend
```

如果 `up` 因为当前目录未绑定到目标服务而报错，可以先切换绑定：

```bash
railway service link backend
railway up

railway service link frontend
railway up
```

### 8. 看日志和状态

```bash
railway logs --service backend
railway logs --service frontend
railway status
```

如果后端启动失败，优先看是否卡在迁移或数据库连通性。

## 脚本模板

仓库里还提供了一份可直接改变量后执行的模板：

- [scripts/railway-bootstrap.sh](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/scripts/railway-bootstrap.sh)

使用方式：

```bash
chmod +x scripts/railway-bootstrap.sh

FRONTEND_DOMAIN=your-frontend.up.railway.app \
ENABLE_CLAUDE=false \
bash scripts/railway-bootstrap.sh
```

默认会先读取仓库根目录 `.env`，再用你显式传入的 shell 变量覆盖。

例如你可以保留 `.env` 里的模型配置，只覆盖生产域名：

```bash
FRONTEND_DOMAIN=your-frontend.up.railway.app \
bash scripts/railway-bootstrap.sh
```

如果你要启用 Claude：

```bash
FRONTEND_DOMAIN=your-frontend.up.railway.app \
ENABLE_CLAUDE=true \
TRUMANWORLD_ANTHROPIC_API_KEY=your_key \
TRUMANWORLD_AGENT_MODEL=your-model \
TRUMANWORLD_DIRECTOR_AGENT_MODEL=your-director-model \
bash scripts/railway-bootstrap.sh
```

这个脚本会：

- 初始化 Railway 项目
- 创建 `backend`、`frontend`、`postgres`
- 写入核心环境变量
- 提示你去控制台补 Root Directory / Config File

注意：

- `.env` 里的本地值不会自动变成生产安全值
- 生产环境至少应覆盖 `FRONTEND_DOMAIN`
- 如果 `.env` 里仍是 `TRUMANWORLD_APP_ENV=development`、`TRUMANWORLD_LOG_LEVEL=DEBUG`、`localhost` 数据库地址，建议显式覆盖

## 首次上线后的检查项

### 后端

- 打开前端后确认首页可以拉到 run 列表
- 查看后端日志，确认 Alembic 成功执行到 `head`
- 检查 `/api/health`

### 前端

- 首页加载无 `network_error`
- 创建 run 成功
- 进入 world/timeline 页面没有 SSR 请求失败

## 当前仓库里的已知部署注意点

### 1. 不要直接复用现有 Dockerfile

现有文件偏开发环境：

- [backend/Dockerfile](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/backend/Dockerfile)
- [frontend/Dockerfile](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/frontend/Dockerfile)

它们目前分别用了 `--reload` 和 `npm run dev`。

### 2. 后端 CORS 必须带上前端域名

配置入口在：

- [backend/app/infra/settings.py](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/backend/app/infra/settings.py)

如果前端域名变了，记得同步更新 `TRUMANWORLD_CORS_ALLOWED_ORIGINS`。

### 3. 前端 SSR 依赖内部 API 地址

配置入口在：

- [frontend/lib/api.ts](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/frontend/lib/api.ts)
- [frontend/next.config.ts](/home/qy113/workspace/project/2603/TrumanWorld/TrumanWorld/frontend/next.config.ts)

不设置 `INTERNAL_API_BASE_URL` 时，SSR 默认会回退到本地地址 `http://127.0.0.1:18080/api`，上线一定会失败。

## 参考资料

- Railway Monorepo Guide: https://docs.railway.com/guides/deploying-a-monorepo
- Railway Private Networking: https://docs.railway.com/networking/private-networking
- Railway Private Networking Internals: https://docs.railway.com/networking/private-networking/how-it-works
- Railway Dockerfile Path: https://docs.railway.com/builds/dockerfiles
- Railway Variables Reference: https://docs.railway.com/variables/reference
- Railway Build and Start Commands: https://docs.railway.com/reference/build-and-start-commands
