FROM node:20-alpine

WORKDIR /app/frontend

# 复制 package 文件
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# 安装依赖（以 root 用户安装，然后调整权限）
RUN corepack enable && pnpm install --frozen-lockfile && \
    chown -R node:node /app/frontend

# 切换到非 root 用户
USER node

CMD ["sh", "-c", "pnpm dev -- --hostname 0.0.0.0 --port 3000"]
