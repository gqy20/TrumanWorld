# Agents

本目录用于存放 TrumanWorld 的 agent 配置。

## 结构

```text
agents/
  _template/
    agent.yml
    prompt.md
  alice/
    agent.yml
    prompt.md
  bob/
    agent.yml
    prompt.md
```

后续每个 agent 建议使用独立目录：

```text
agents/
  alice/
    agent.yml
    prompt.md
```

运行时 agent 可以通过持久化字段映射到配置目录。目前 demo world 会在 agent `profile.agent_config_id`
中写入 `alice` / `bob`，从而让运行中的 `run-id-alice`、`run-id-bob` 正确加载对应配置。
