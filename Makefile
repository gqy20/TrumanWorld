PYTHON ?= python3.13
BACKEND_DIR := backend
FRONTEND_DIR := frontend
LOGS_DIR := logs
BACKEND_MYPY_TARGETS := app/api/errors.py app/api/auth.py app/infra/settings.py
BACKEND_TEST_ENV := TRUMANWORLD_ANTHROPIC_API_KEY=test-key
PRE_COMMIT := uv run --project $(BACKEND_DIR) pre-commit

# 生成带时间戳的日志文件名
LOG_TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

.PHONY: install hooks-install backend-install frontend-install backend-dev frontend-dev frontend-clean-port backend-lock-check backend-lint backend-format-check backend-typecheck backend-test backend-test-ci backend-integration-test backend-migration-check frontend-lint frontend-eslint frontend-typecheck frontend-build frontend-test lint format quality test ci pre-commit pre-push migrate dev docker-dev docker-down docker-clean db-start db-stop db-status db-wait db-migrate db-clean check-ports kill-ports sync-agent-logos benchmark-reactor-pool evaluate-run

# 同步 agent logo 到前端 public 目录
sync-agent-logos:
	@echo "🔄 同步 agent logos..."
	@mkdir -p $(FRONTEND_DIR)/public/agents
	@for dir in agents/*/; do \
		agent_id=$$(basename "$$dir"); \
		if [ -f "$$dir/logo.svg" ]; then \
			cp "$$dir/logo.svg" "$(FRONTEND_DIR)/public/agents/$$agent_id.svg"; \
			echo "  ✓ $$agent_id"; \
		fi; \
	done
	@echo "✅ Agent logos 同步完成"

install: backend-install frontend-install sync-agent-logos

hooks-install:
	git config --unset-all core.hooksPath 2>/dev/null || true
	$(PRE_COMMIT) install --hook-type pre-commit --hook-type pre-push

backend-install:
	cd $(BACKEND_DIR) && uv sync --group dev --frozen

frontend-install:
	cd $(FRONTEND_DIR) && pnpm install --frozen-lockfile

backend-dev:
	@mkdir -p $(LOGS_DIR)
	@LOG_TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	LOG_FILE_BACKEND="$(CURDIR)/$(LOGS_DIR)/dev_$${LOG_TIMESTAMP}_backend.log"; \
	echo "📝 后端日志: $${LOG_FILE_BACKEND}"; \
	cd $(BACKEND_DIR) && TRUMANWORLD_DATABASE_URL=$(DATABASE_URL) env -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_BASE_URL uv run uvicorn app.main:app --reload --host 127.0.0.1 --port $(BACKEND_PORT) 2>&1 | tee "$${LOG_FILE_BACKEND}"

frontend-dev: frontend-clean-port sync-agent-logos
	@mkdir -p $(LOGS_DIR)
	@LOG_TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	LOG_FILE_FRONTEND="$(CURDIR)/$(LOGS_DIR)/dev_$${LOG_TIMESTAMP}_frontend.log"; \
	echo "📝 前端日志: $${LOG_FILE_FRONTEND}"; \
	cd $(FRONTEND_DIR) && INTERNAL_API_BASE_URL=http://127.0.0.1:$(BACKEND_PORT)/api NEXT_PUBLIC_API_BASE_URL=/api pnpm dev --port $(FRONTEND_PORT) --hostname 0.0.0.0 2>&1 | tee "$${LOG_FILE_FRONTEND}"

frontend-clean-port:
	@echo "🧹 清理前端端口和锁文件..."
	@FRONTEND_PIDS=$$(ss -tlnp 2>/dev/null | grep -E ":$(FRONTEND_PORT)" | grep -oP 'pid=\K[0-9]+' | sort -u); \
	if [ -n "$$FRONTEND_PIDS" ]; then \
		for PID in $$FRONTEND_PIDS; do \
			echo "终止前端端口占用 (PID: $$PID)"; \
			kill -9 $$PID 2>/dev/null || true; \
		done; \
		sleep 1; \
	fi
	@rm -f $(FRONTEND_DIR)/.next/dev/lock
	@echo "✅ 前端端口和锁文件已清理"

backend-lint:
	cd $(BACKEND_DIR) && uv run ruff check app tests

backend-lock-check:
	cd $(BACKEND_DIR) && uv lock --check

backend-format-check:
	cd $(BACKEND_DIR) && uv run ruff format --check app tests

backend-typecheck:
	cd $(BACKEND_DIR) && uv run mypy $(BACKEND_MYPY_TARGETS)

frontend-lint:
	cd $(FRONTEND_DIR) && pnpm lint

frontend-eslint:
	cd $(FRONTEND_DIR) && pnpm lint:eslint

frontend-typecheck:
	cd $(FRONTEND_DIR) && pnpm lint:types

frontend-build:
	cd $(FRONTEND_DIR) && pnpm build

backend-test:
	cd $(BACKEND_DIR) && $(BACKEND_TEST_ENV) uv run pytest -m "not integration"

backend-test-ci:
	cd $(BACKEND_DIR) && $(BACKEND_TEST_ENV) uv run pytest -m "not integration" -v --cov=app --cov-report=xml

backend-integration-test:
	cd $(BACKEND_DIR) && TRUMANWORLD_TEST_POSTGRES_URL="$(DATABASE_URL)" uv run pytest -m integration

backend-migration-check:
	cd $(BACKEND_DIR) && TRUMANWORLD_DATABASE_URL="$${TRUMANWORLD_DATABASE_URL:-$(DATABASE_URL)}" uv run alembic upgrade head

frontend-test:
	cd $(FRONTEND_DIR) && pnpm test --runInBand --passWithNoTests

lint:
	$(MAKE) backend-lint
	$(MAKE) backend-typecheck
	$(MAKE) frontend-lint

quality:
	$(MAKE) backend-lock-check
	$(MAKE) backend-lint
	$(MAKE) backend-format-check
	$(MAKE) backend-typecheck
	$(MAKE) frontend-eslint
	$(MAKE) frontend-typecheck

format:
	cd $(BACKEND_DIR) && uv run ruff format app tests

test:
	$(MAKE) backend-test
	$(MAKE) frontend-test

ci: quality backend-test-ci backend-migration-check backend-integration-test frontend-test frontend-build

benchmark-reactor-pool:
	cd $(BACKEND_DIR) && uv run python scripts/benchmark_reactor_pooling.py --base-url http://127.0.0.1:$(BACKEND_PORT)/api --ticks 10 --seed-demo

RUN_QUALITY_BASE_URL ?= http://127.0.0.1:$(BACKEND_PORT)/api
RUN_QUALITY_TICKS ?= 0
RUN_QUALITY_OUTPUT ?=

evaluate-run:
	@test -n "$(RUN_ID)" || (echo "RUN_ID is required" && exit 1)
	cd $(BACKEND_DIR) && uv run python scripts/evaluate_run_quality.py \
		--base-url "$(RUN_QUALITY_BASE_URL)" \
		--run-id "$(RUN_ID)" \
		--ticks "$(RUN_QUALITY_TICKS)" $(if $(RUN_QUALITY_OUTPUT),--output "$(RUN_QUALITY_OUTPUT)",)

migrate:
	cd $(BACKEND_DIR) && TRUMANWORLD_DATABASE_URL=$(DATABASE_URL) uv run alembic upgrade head

pre-commit:
	$(PRE_COMMIT) run --all-files

pre-push:
	$(PRE_COMMIT) run --hook-stage pre-push --all-files

# 数据库配置（本地开发环境，从环境变量或使用默认值）
# 生产环境请务必设置环境变量 TRUMANWORLD_DB_PASSWORD
DB_CONTAINER_NAME := trumanworld-db-test
DB_PORT := 5432
DB_USER := $(or $(TRUMANWORLD_DB_USER),truman)
DB_PASSWORD := $(or $(TRUMANWORLD_DB_PASSWORD),truman)
DB_NAME := $(or $(TRUMANWORLD_DB_NAME),trumanworld)
DATABASE_URL := postgresql+psycopg://$(DB_USER):$(DB_PASSWORD)@127.0.0.1:$(DB_PORT)/$(DB_NAME)

# 应用端口配置
BACKEND_PORT := 18080
FRONTEND_PORT := 13000

# 检查端口是否被占用（支持 IPv4 和 IPv6）
check-ports:
	@echo "🔍 检查端口占用情况..."
	@BACKEND_PIDS=$$(ss -tlnp 2>/dev/null | grep -E ":$(BACKEND_PORT)" | grep -oP 'pid=\K[0-9]+' | sort -u); \
	FRONTEND_PIDS=$$(ss -tlnp 2>/dev/null | grep -E ":$(FRONTEND_PORT)" | grep -oP 'pid=\K[0-9]+' | sort -u); \
	if [ -n "$$BACKEND_PIDS" ] || [ -n "$$FRONTEND_PIDS" ]; then \
		echo "⚠️  检测到端口被占用:"; \
		if [ -n "$$BACKEND_PIDS" ]; then \
			echo "  - 端口 $(BACKEND_PORT) (后端) 被 PID $$BACKEND_PIDS 占用"; \
		fi; \
		if [ -n "$$FRONTEND_PIDS" ]; then \
			echo "  - 端口 $(FRONTEND_PORT) (前端) 被 PID $$FRONTEND_PIDS 占用"; \
		fi; \
		echo ""; \
		echo "运行 'make kill-ports' 终止占用进程，或手动关闭后重试"; \
		exit 1; \
	else \
		echo "✅ 端口 $(BACKEND_PORT) 和 $(FRONTEND_PORT) 可用"; \
	fi

# 终止占用端口的进程（支持 IPv4 和 IPv6）
kill-ports:
	@echo "🛑 终止占用端口的进程..."
	@BACKEND_PIDS=$$(ss -tlnp 2>/dev/null | grep -E ":$(BACKEND_PORT)" | grep -oP 'pid=\K[0-9]+' | sort -u); \
	if [ -n "$$BACKEND_PIDS" ]; then \
		for PID in $$BACKEND_PIDS; do \
			echo "终止后端端口占用 (PID: $$PID)"; \
			kill -9 $$PID 2>/dev/null || true; \
		done; \
	fi; \
	FRONTEND_PIDS=$$(ss -tlnp 2>/dev/null | grep -E ":$(FRONTEND_PORT)" | grep -oP 'pid=\K[0-9]+' | sort -u); \
	if [ -n "$$FRONTEND_PIDS" ]; then \
		for PID in $$FRONTEND_PIDS; do \
			echo "终止前端端口占用 (PID: $$PID)"; \
			kill -9 $$PID 2>/dev/null || true; \
		done; \
	fi; \
	sleep 2; \
	echo "✅ 端口已释放"
	@echo "🧹 清理前端锁文件..."
	@rm -f $(FRONTEND_DIR)/.next/dev/lock
	@echo "✅ 锁文件已清理"

# 启动测试数据库（如果不存在则创建）
db-start:
	@echo "🐘 启动 PostgreSQL 测试数据库..."
	@if [ "$$(docker ps -q -f name=$(DB_CONTAINER_NAME))" ]; then \
		echo "数据库容器已在运行"; \
	elif [ "$$(docker ps -aq -f status=exited -f name=$(DB_CONTAINER_NAME))" ]; then \
		echo "启动已存在的数据库容器..."; \
		docker start $(DB_CONTAINER_NAME); \
	else \
		echo "创建新的数据库容器..."; \
		docker run -d \
			--name $(DB_CONTAINER_NAME) \
			-e POSTGRES_USER=$(DB_USER) \
			-e POSTGRES_PASSWORD=$(DB_PASSWORD) \
			-e POSTGRES_DB=$(DB_NAME) \
			-p $(DB_PORT):5432 \
				postgres:17.3; \
		echo "等待数据库启动..."; \
		sleep 3; \
	fi
	@echo "数据库连接信息: postgresql://$(DB_USER):$(DB_PASSWORD)@127.0.0.1:$(DB_PORT)/$(DB_NAME)"

# 停止测试数据库
db-stop:
	@echo "🛑 停止 PostgreSQL 测试数据库..."
	@docker stop $(DB_CONTAINER_NAME) 2>/dev/null || echo "数据库容器未运行"

# 查看数据库状态
db-status:
	@if [ "$$(docker ps -q -f name=$(DB_CONTAINER_NAME))" ]; then \
		echo "✅ 数据库容器正在运行"; \
		docker ps -f name=$(DB_CONTAINER_NAME); \
	elif [ "$$(docker ps -aq -f status=exited -f name=$(DB_CONTAINER_NAME))" ]; then \
		echo "⏸️ 数据库容器已停止"; \
	else \
		echo "❌ 数据库容器不存在，运行 'make db-start' 创建"; \
	fi

# 删除测试数据库（清理）
db-clean:
	@echo "🗑️ 删除 PostgreSQL 测试数据库..."
	@docker rm -f $(DB_CONTAINER_NAME) 2>/dev/null || echo "数据库容器不存在"

# 等待数据库就绪
db-wait:
	@echo "⏳ 等待数据库就绪..."
	@for i in $$(seq 1 30); do \
		if [ -z "$$(docker ps -q -f name=$(DB_CONTAINER_NAME))" ]; then \
			echo "❌ 数据库容器未运行"; \
			docker ps -a -f name=$(DB_CONTAINER_NAME); \
			exit 1; \
		fi; \
		if docker exec $(DB_CONTAINER_NAME) pg_isready -U $(DB_USER) -d $(DB_NAME) >/dev/null 2>&1; then \
			echo "✅ 数据库已就绪"; \
			exit 0; \
		fi; \
		echo "  等待中... ($$i/30)"; \
		sleep 2; \
	done; \
	echo "❌ 数据库启动超时"; \
	docker ps -a -f name=$(DB_CONTAINER_NAME); \
	echo "最近数据库日志:"; \
	docker logs --tail 50 $(DB_CONTAINER_NAME) 2>/dev/null || true; \
	exit 1

# 执行数据库迁移
db-migrate: db-wait
	@echo "🔄 执行数据库迁移..."
	@cd $(BACKEND_DIR) && TRUMANWORLD_DATABASE_URL=$(DATABASE_URL) uv run alembic upgrade head

# 一行命令同时启动前后端（测试环境，非 Docker）
# 使用非常用端口避免冲突：后端 18080，前端 13000
# 日志会自动保存到 logs/ 目录，文件名包含时间戳
dev: check-ports db-start db-migrate sync-agent-logos
	@mkdir -p $(LOGS_DIR)
	@LOG_TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	LOG_FILE_BACKEND="$(CURDIR)/$(LOGS_DIR)/dev_$${LOG_TIMESTAMP}_backend.log"; \
	LOG_FILE_FRONTEND="$(CURDIR)/$(LOGS_DIR)/dev_$${LOG_TIMESTAMP}_frontend.log"; \
	echo ""; \
	echo "🚀 启动 Truman World 开发环境..."; \
	echo "================================"; \
	echo "数据库: postgresql://$(DB_USER):$(DB_PASSWORD)@127.0.0.1:$(DB_PORT)/$(DB_NAME)"; \
	echo "后端:   http://127.0.0.1:$(BACKEND_PORT)"; \
	echo "前端:   http://127.0.0.1:$(FRONTEND_PORT)"; \
	echo "日志:   $(LOGS_DIR)/dev_$${LOG_TIMESTAMP}_*.log"; \
	echo "================================"; \
	echo "按 Ctrl+C 停止前后端（数据库会继续运行）"; \
	echo ""; \
	(cd $(BACKEND_DIR) && TRUMANWORLD_DATABASE_URL=$(DATABASE_URL) env -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_BASE_URL uv run uvicorn app.main:app --host 127.0.0.1 --port $(BACKEND_PORT) 2>&1 | tee "$${LOG_FILE_BACKEND}") & \
	BACKEND_PID=$$!; \
	(cd $(FRONTEND_DIR) && INTERNAL_API_BASE_URL=http://127.0.0.1:$(BACKEND_PORT)/api NEXT_PUBLIC_API_BASE_URL=/api pnpm dev --port $(FRONTEND_PORT) --hostname 0.0.0.0 2>&1 | tee "$${LOG_FILE_FRONTEND}") & \
	FRONTEND_PID=$$!; \
	trap 'echo ""; echo "🛑 停止服务..."; kill $$BACKEND_PID $$FRONTEND_PID 2>/dev/null; wait $$BACKEND_PID $$FRONTEND_PID 2>/dev/null; echo "✅ 已停止"' INT TERM; \
	wait $$BACKEND_PID $$FRONTEND_PID

# Docker 开发环境启动（带日志输出）
docker-dev:
	@mkdir -p $(LOGS_DIR)
	@LOG_TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	LOG_FILE_BACKEND="$(CURDIR)/$(LOGS_DIR)/docker_$${LOG_TIMESTAMP}_backend.log"; \
	LOG_FILE_FRONTEND="$(CURDIR)/$(LOGS_DIR)/docker_$${LOG_TIMESTAMP}_frontend.log"; \
	echo ""; \
	echo "🐳 启动 Truman World Docker 开发环境..."; \
	echo "================================"; \
	echo "日志目录: $(LOGS_DIR)/"; \
	echo "后端日志: docker_$${LOG_TIMESTAMP}_backend.log"; \
	echo "前端日志: docker_$${LOG_TIMESTAMP}_frontend.log"; \
	echo "================================"; \
	docker compose up --build 2>&1 | tee >(grep -E "(backend|trumanworld-backend|INFO:|ERROR:|WARNING:|DEBUG:)" > "$${LOG_FILE_BACKEND}") >(grep -E "(frontend|trumanworld-front|Next.js|GET|POST|PUT|DELETE|PATCH)" > "$${LOG_FILE_FRONTEND}")

# 停止并移除 Docker 容器（保留数据卷）
docker-down:
	@echo "🛑 停止 Docker 容器..."
	@docker compose down
	@echo "✅ 容器已停止"

# 完全清理 Docker 环境（容器 + 数据卷）
docker-clean:
	@echo "🗑️  清理 Docker 环境（容器 + 数据卷）..."
	@docker compose down -v --remove-orphans
	@echo "✅ Docker 环境已清理"

# 清理日志文件（保留最近 7 天）
clean-logs:
	@echo "🧹 清理日志文件..."
	@find $(LOGS_DIR) -name "*.log" -type f -mtime +7 -delete 2>/dev/null || true
	@find $(LOGS_DIR) -name "*.sql" -type f -mtime +7 -delete 2>/dev/null || true
	@echo "✅ 已清理 7 天前的日志文件"

# 清理所有日志文件（谨慎使用）
clean-logs-all:
	@echo "🗑️  清理所有日志文件..."
	@rm -f $(LOGS_DIR)/*.log $(LOGS_DIR)/*.sql 2>/dev/null || true
	@echo "✅ 已清理所有日志文件"
