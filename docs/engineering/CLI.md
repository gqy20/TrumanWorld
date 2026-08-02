# Truman World CLI

`truman` 是 FastAPI 的正式命令行客户端，用于调试、自动化、长跑观察和导演操作。浏览器负责
3D 与交互体验；CLI 和浏览器共享同一 API、认证、生命周期和持久化语义。

## 安装与入口

```bash
make backend-install
cd backend && uv run truman --help

# 或从仓库根目录转发参数
make cli CLI_ARGS="doctor"
make cli CLI_ARGS="--output json run list"
```

全局参数必须写在子命令之前，例如 `truman --output json run list`。
运行可使用完整 UUID、`run list` 展示的唯一短 ID，或精确名称；居民可使用 `agent list`
展示的 `Ref`（例如 `truman`），导演地点也可使用 `plaza`、`cafe` 等唯一后缀。

## 配置

默认连接 `http://127.0.0.1:18080/api`。配置优先级为命令参数、环境变量、profile、默认值。

```toml
# ~/.config/trumanworld/config.toml
[profiles.default]
base_url = "http://127.0.0.1:18080/api"
timeout = 120
output = "table"

[profiles.production]
base_url = "https://example.com/api"
timeout = 180
output = "json"
```

```bash
truman --profile production health
TRUMANWORLD_CLI_BASE_URL=http://127.0.0.1:18080/api truman doctor
```

写操作密码只从 `TRUMANWORLD_DEMO_ADMIN_PASSWORD` 读取，不提供密码命令参数，避免进入 shell
history。可用 `TRUMANWORLD_CLI_CONFIG` 覆盖配置文件路径。

## 常用操作

```bash
truman health
truman ready
truman doctor
truman system status
truman system access
truman system scenarios

truman run list
truman run create --name smoke --scenario narrative_world --paused
truman run show <run-id>
truman run start <run-id>
truman run pause <run-id>
truman run resume <run-id>
truman run step <run-id> --count 3       # 暂停状态下精确推进
truman run tick <run-id> --count 3       # step 的兼容别名
truman run restore-all
truman run delete <run-id> --yes
```

`--paused` 会完成场景 seed，但不启动 scheduler，适合无费用的结构检查和手动 tick 调试。

## 世界会话

```bash
truman play <run-ref>
truman play <run-ref> --execute look --execute people --execute cost
```

`play` 会记住当前世界，支持 `look`、`people`、`inspect truman`、`step 1`、
`broadcast <message>`、`start`、`pause` 和 `cost`。交互模式适合持续体验；重复的
`--execute` 适合五风格冒烟测试。

## 观察与自动化

```bash
truman world show <run-id>
truman world pulse <run-id>
truman world cost <run-id>

truman agent list <run-id>
truman agent show <run-id> <agent-id> --event-limit 20 --memory-limit 20
truman agent economy <run-id> <agent-id>
truman agent governance <run-id> <agent-id>

truman timeline list <run-id> --tick-from 10 --event-type talk
truman --output ndjson timeline follow <run-id> --since-tick 10
```

所有查询支持 `--output table|json|ndjson`。JSON 适合单次响应，NDJSON 适合事件流与 Unix 管道。

## 条件等待与成本保护

```bash
truman run wait <run-id> --until-tick 20
truman run wait <run-id> --until-status paused
truman run wait <run-id> --until-tick 100 --max-cost 1.00
truman run wait <run-id> --until-tick 100 --max-tokens 500000
```

达到 `--max-cost` 或 `--max-tokens` 时，CLI 会通过 API 暂停仍在运行的世界。
`--max-seconds` 控制等待总时限，`--poll-interval` 控制采样频率。成本来自持久化的
`LlmCall.total_cost_usd` 汇总；MiniMax 等上游没有返回价格时，CLI 会显示 `unavailable`。
这类 provider 应以 `--max-tokens` 作为强制保护；如果只提供 `--max-cost`，`run wait`
会暂停正在运行的世界并返回错误，避免把“价格未知”误判为零成本。

## 导演与质量评估

```bash
truman director observe <run-id>
truman director memories <run-id>
truman director cases <run-id>
truman director restrictions <run-id>
truman director inject <run-id> --type broadcast --message "广场将在下午举办活动"
truman director inject <run-id> --type activity --location cafe --payload '{"duration_hours":2}'

truman evaluate <run-id>
truman evaluate <run-id> --ticks 20 --output-file artifacts/run-quality.json
```

带 `--ticks` 的评估会产生真实模型调用，且要求 run 先暂停。只读评估不推进世界。

## 退出码

| 退出码 | 含义 |
| ---: | --- |
| `0` | 成功 |
| `1` | 诊断或一般失败 |
| `2` | 命令参数错误 |
| `4` | API 不可达 |
| `5` | 未授权 |
| `6` | 资源不存在 |
| `7` | 状态冲突，例如 tick 正在执行 |
| `8` | 其他 API/响应错误 |
| `9` | 超时或等待期限到期 |
| `130` | 用户中断 |

CLI 默认不会隐式启动服务。先运行 `make backend-dev`，或把 profile 指向已经部署的 API。
面向不同测试意图的完整体验路径见
[五种 CLI 玩家风格](../references/CLI_PLAYER_STYLES.md)。
