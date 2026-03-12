# Reactor Pool Benchmark

用于比较 `TRUMANWORLD_CLAUDE_SDK_REACTOR_POOL_ENABLED=true/false` 两种模式下的
tick 性能和连接池行为。

## 前提

- 后端服务已启动
- Claude SDK 可正常调用
- 使用同一套模型、数据库和场景配置做对比

## 建议步骤

### 1. 启动后端（连接池开启）

设置：

- `TRUMANWORLD_CLAUDE_SDK_REACTOR_POOL_ENABLED=true`

运行：

```bash
cd backend
uv run python scripts/benchmark_reactor_pooling.py --base-url http://127.0.0.1:18080/api --ticks 10 --seed-demo
```

记录：

- `avg_tick_seconds_client`
- `p95_tick_seconds_client`
- `tick_histogram_sum_delta`
- `trumanworld_claude_reactor_pool_size`
- `trumanworld_claude_reactor_pool_active`

### 2. 启动后端（连接池关闭）

设置：

- `TRUMANWORLD_CLAUDE_SDK_REACTOR_POOL_ENABLED=false`

运行同一条 benchmark 命令。

## 重点比较

- tick 平均耗时是否显著上升
- p95 是否变差
- 连接池大小和活跃连接数是否稳定归零
- 运行期间是否更少出现 `cancel scope` 相关异常
- pause/delete run 后是否更少留下 Claude CLI 残留进程

## 指标说明

Prometheus `/api/metrics` 相关指标：

- `trumanworld_claude_reactor_pool_enabled`
- `trumanworld_claude_reactor_pool_size`
- `trumanworld_claude_reactor_pool_active`
- `trumanworld_tick_duration_seconds`

## 结论建议

- 如果关闭连接池后 tick 平均耗时增加不大，但错误率和残留进程明显下降，建议默认关闭
- 如果高频 reactor tick 明显依赖连接池且稳定性没有显著恶化，保留默认开启更合理
