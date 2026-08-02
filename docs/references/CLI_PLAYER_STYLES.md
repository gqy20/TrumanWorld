# CLI 五种玩家风格

- 文档类型：测试参考
- 最近实测：2026-08-02
- 实测模型：MiniMax-M3
- 实测世界：`5c09aaa9`（`CLI 五风格体验 2026-08-02`）

这五种风格不是五套功能清单，而是五种不同的使用动机。每次 CLI 体验测试至少选择其中三种；发布前应完整走完五种，才能同时覆盖可读性、控制力、叙事反馈、可解释性和自动化契约。

人工体验时推荐先进入统一会话，避免在多个子命令间反复复制世界引用：

```bash
truman play 5c09aaa9
```

## 1. 漫游观察者

心态：我不干预，只想快速理解小镇此刻发生了什么。

```bash
truman doctor
truman run list
truman world show 5c09aaa9
truman world pulse 5c09aaa9
truman agent list 5c09aaa9
truman timeline list 5c09aaa9 --limit 20 --newest-first
```

体验标准：60 秒内能说清世界是否运行、当前时间、居民在哪里、最近发生了什么；只读流程不得产生 LLM 成本。默认表格应优先展示可继续输入的短引用，而不是截断的数据库 ID。

本轮感受：`world show` 的表格摘要适合人读，`world show --output json` 包含完整导航图，信息量过大，只适合程序消费。观察者通常应从 `pulse` 和时间线开始。

## 2. 小镇运营官

心态：我要安全地启动、观察并暂停世界，同时控制时间和预算。

```bash
truman run create --name ops-smoke --scenario narrative_world --paused
truman run step <run-ref> --count 1

# 需要体验连续运行时：
truman run start <run-ref>
truman run wait <run-ref> --until-tick 1 --max-tokens 50000 --max-seconds 180
truman world cost <run-ref>
truman run pause <run-ref>
truman run show <run-ref>
```

体验标准：状态转换明确；`wait` 达到 Token 或费用上限时自动暂停；暂停后 `elapsed_seconds` 累计而不是归零；测试结束不留下意外运行的世界。

本轮结果：世界从 tick 0 推进到 tick 1，约 60 秒后暂停，累计运行时间正确保留。MiniMax-M3 使用 22,772 tokens，其中 input 21,899、output 873。

注意：当前上游没有返回 MiniMax-M3 的美元价格，因此 CLI 将费用明确显示为
`unavailable`，而不是容易被误解为免费的 `$0.00`。使用该模型时必须把 `--max-tokens`
当作强限制；若只设置 `--max-cost`，`run wait` 会暂停世界并报错。

## 3. 剧情导演

心态：我要施加一个外部条件，然后观察居民是否自然地吸收和回应它。

```bash
truman director observe <run-ref>
truman director inject <run-ref> \
  --type broadcast \
  --message "广场将在七点举办晨间音乐会" \
  --location plaza \
  --importance 0.7 \
  --payload '{"source":"player-style-test","mood":"inviting"}'
truman run step <run-ref>
truman timeline list <run-ref> --tick-from 1 --newest-first
truman director memories <run-ref>
```

支持的事件类型是 `activity`、`shutdown`、`broadcast`、`weather_change` 和 `power_outage`，命令帮助会直接列出这些选择。

体验标准：注入立即出现在时间线；下一 tick 的行为能体现事件影响，但导演不能直接改写居民思想；事件位置和 payload 可追溯。

本轮结果：广播在 tick 0 入队。tick 1 时 Meryl 主动向 Truman 提到晨间音乐会，随后形成 `conversation_started`、`speech` 和 `listen` 事件；Truman 也生成了相应情景记忆。这种“条件进入世界，再由居民自行反应”的感觉是目前 CLI 最有说服力的部分。

## 4. 取证调查员

心态：某个行为看起来奇怪，我要沿居民、记忆、关系、规则和时间线查清原因。

```bash
truman agent show <run-ref> truman --event-limit 20 --memory-limit 20
truman timeline list <run-ref> --agent truman --tick-from 1
truman agent economy <run-ref> truman
truman agent governance <run-ref> truman
truman director cases <run-ref>
truman director restrictions <run-ref>
truman evaluate <run-ref>
```

体验标准：不用复制完整复合 ID；居民最近事件、记忆和关系分区显示；能够从导演事件追踪到对话、记忆和关系变化；只读 `evaluate` 不推进世界。

本轮结果：可以确认广播如何进入 Meryl 的发言以及 Truman 的记忆，夫妻熟悉度、信任和亲密度也随互动上升。质量报告显示 6 次行动全部接受，包含移动、聆听和对话开始三类行为。

## 5. 自动化测试者

心态：我要在脚本和 CI 中稳定消费输出，并在失败时获得可靠退出码。

```bash
truman --output json doctor
truman --output json run list
truman --output ndjson timeline list <run-ref> --tick-from 1 --limit 5
truman --output json run wait <run-ref> --until-status paused --max-seconds 10
```

体验标准：JSON 可直接解析；NDJSON 严格保持一条记录一行，不受终端宽度影响；错误写入 stderr；参数错误、连接失败、资源不存在和超时使用稳定的非零退出码。

本轮结果：5 个事件输出为 5 个物理行；短 run ID、居民 Ref 和地点后缀都能解析；无效导演事件类型在请求发出前即被 CLI 拒绝。

## 发布前验收矩阵

| 风格 | 必测能力 | 成功信号 | 主要风险 |
|------|----------|----------|----------|
| 漫游观察者 | doctor、pulse、居民、时间线 | 一分钟形成世界概况 | 信息过载、ID 不可复制 |
| 小镇运营官 | create、start、wait、pause | tick 与累计时间正确 | 忘记暂停、预算失控 |
| 剧情导演 | observe、inject、后续 tick | 居民自然回应条件 | 事件类型/地点不清楚 |
| 取证调查员 | agent、governance、evaluate | 行为到记忆可追溯 | 嵌套数据难读 |
| 自动化测试者 | JSON、NDJSON、退出码 | 可解析且一行一事件 | 输出被样式或换行污染 |

## 已知边界与后续检查

- `--output`、`--profile` 等全局参数必须写在子命令前，这是 Typer 当前命令层级的明确约定。
- `run create` 和生命周期动作的即时响应中，`agent_count`、`location_count`、`event_count` 可能仍为默认值；需要准确计数时重新执行 `run list`。
- 默认表格模式的 `system status` 会单独显示数据库连通性；使用 Neon 时，本机 PostgreSQL
  进程显示 `remote / no local process` 是正常状态。JSON 模式继续保留 API 原始数据，供程序消费。
- 开发服务器带 `--reload` 且存在长连接时，热重载可能停在 `Waiting for connections to close`；发布前需单独覆盖 SSE 连接下的优雅重启测试。
- 完整 world JSON 包含导航图，适合保存或交给 `jq`，不适合作为人类的第一入口。
