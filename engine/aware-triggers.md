# Aware 触发器系统设计文档

> OPC v2.0 核心新增 — 声明式事件驱动，让项目"自己动起来"

## 概述

Aware 触发器系统让 OPC 项目具备**事件驱动能力**：定义好规则后，CEO 在 heartbeat 时调用 `evaluate()`，满足条件的触发器自动产生动作（spawn agent / 发通知 / 跑脚本）。

配合 Focus 系统，实现项目焦点的自适应管理——agent 全部完成时焦点自动关闭，关联的触发器自动停用。

## 触发器类型

### 1. cron — 定时触发

通过 `openclaw cron create` 注册系统级 cron 任务，按 cron 表达式定时执行。

```yaml
- id: daily-report
  type: cron
  schedule: "30 9 * * *"
  timezone: "Asia/Shanghai"
  action:
    type: spawn_agent
    agent_label: "report-writer"
    task: "生成并发送日报"
```

**注意**: cron 类型触发器在 `register_cron()` 时注册到 OpenClaw 系统，不由 `evaluate()` 检查（因为 cron 是系统级调度）。

### 2. once — 一次性触发

到达指定时间后触发一次，然后自动标记 `fired: true`。

```yaml
- id: deadline-reminder
  type: once
  at: "2026-03-15T10:00:00+08:00"
  action:
    type: notify
    target: "daxiang"
    message: "KangaBase v0.2.0 deadline 到了"
  fired: false
```

### 3. interval — 周期检查

每隔指定分钟数检查一次。适用于需要定期巡逻的场景。

```yaml
- id: status-check
  type: interval
  every_minutes: 30
  action:
    type: run_script
    command: "python3 scripts/project_state.py show opc-20260311-001"
```

### 4. on_message — 消息触发

当某个 agent 的输出包含特定关键词时触发。支持 contains / regex / exact 三种匹配模式。

```yaml
- id: phase-transition
  type: on_message
  from_agent: "core-engineer"
  contains: "Phase 1 完成"
  match_mode: "contains"
  action:
    type: spawn_agent
    agent_label: "doc-writer"
    task: "开始 Phase 2 文档编写"
  max_fires: 1
```

**实现机制**: 通过 `subagents list` 获取最近完成的 agent 输出，逐行匹配。

### 5. poll — 外部状态轮询

HTTP 轮询外部 API，检查特定字段的值。适用于监控 CI/CD、外部服务状态等。

```yaml
- id: ci-check
  type: poll
  url: "https://api.github.com/repos/owner/repo/actions/runs?per_page=1"
  check_path: "workflow_runs[0].conclusion"
  expected: "success"
  interval_minutes: 5
  timeout_minutes: 60
  action:
    type: notify
    target: "daxiang"
    message: "CI 构建成功"
```

## triggers.yaml 完整 Schema

```yaml
version: "1.0"
triggers:
  - id: string           # 唯一标识（必填）
    type: string          # cron / once / interval / on_message / poll（必填）
    enabled: boolean      # 是否启用（默认 true）
    focus_ref: string     # 关联的 focus id（可选）

    # cron 专属
    schedule: string      # cron 表达式
    timezone: string      # 时区（默认 Asia/Shanghai）

    # once 专属
    at: string            # ISO 8601 时间
    fired: boolean        # 是否已触发（默认 false）

    # interval 专属
    every_minutes: number # 间隔分钟数
    last_fired: string    # 上次触发时间（自动维护）

    # on_message 专属
    from_agent: string    # 来源 agent label（可选，不填则匹配所有）
    contains: string      # 匹配关键词
    match_mode: string    # contains / regex / exact（默认 contains）
    max_fires: number     # 最大触发次数（0=无限）

    # poll 专属
    url: string           # HTTP URL
    check_path: string    # JSON 路径（如 "data.status"）
    expected: string      # 期望值
    interval_minutes: number  # 轮询间隔
    timeout_minutes: number   # 超时（0=不超时）

    # 动作定义（必填）
    action:
      type: string        # spawn_agent / notify / run_script
      # spawn_agent:
      agent_label: string
      task: string
      # notify:
      target: string
      message: string
      # run_script:
      command: string
```

## Focus 系统

Focus 代表项目中的"焦点"——当前需要关注的工作块。

### 状态标记

| 标记 | 含义 |
|------|------|
| `[ ]` | 待办 |
| `[/]` | 进行中 |
| `[x]` | 完成 |
| `[!]` | 阻塞 |

### focus.yaml Schema

```yaml
version: "1.0"
focus_items:
  - id: string            # 唯一标识
    title: string          # 标题
    status: string         # [ ] / [/] / [x] / [!]
    priority: string       # P0 / P1 / P2
    agents: [string]       # 关联的 agent label 列表
    triggers: [string]     # 关联的 trigger id 列表
    auto_complete: boolean # 所有 agent 完成时自动标记 [x]
    recurring: boolean     # 循环焦点（完成后重置为 [ ]）
    created: string        # 创建时间
    completed: string      # 完成时间
```

## Focus 与 Trigger 联动机制

```
Agent 完成 → agent-complete 写入 state.json
    ↓
自动检查: 该 agent 关联的 focus → 所有 agent 都完成？
    ↓ 是
Focus 标记 [x] → 关联的 trigger 可按需停用
    ↓ 如果是 recurring
重置为 [ ]，继续下一轮循环
```

**实现位置**: `project_state_v2.py` 的 `cmd_agent_complete()` 末尾自动调用 `FocusManager.check_auto_complete()`。

## CEO 集成规范

### 何时调用 evaluate()

1. **每次 heartbeat** 时调用一次
2. **收到 agent announce** 后调用（可能触发 on_message 类型）
3. **用户手动请求** "检查触发器" 时

### CEO 工作流

```python
# heartbeat 中
actions = trigger_engine.evaluate()
for action in actions:
    if action.action_type == "spawn_agent":
        # spawn sub-agent
        sessions_spawn(label=action.action_params["agent_label"], 
                       task=action.action_params["task"])
    elif action.action_type == "notify":
        # 发送通知
        message_send(target=action.action_params["target"],
                     message=action.action_params["message"])
    elif action.action_type == "run_script":
        # 执行脚本
        exec(command=action.action_params["command"])
```

### 项目初始化时

```bash
# 1. 初始化项目
python3 project_state_v2.py init "项目名"

# 2. 复制模板到项目目录
cp templates/triggers.yaml opc-projects/<pid>/triggers.yaml
cp templates/focus.yaml opc-projects/<pid>/focus.yaml

# 3. 编辑触发器和焦点配置

# 4. 注册 cron 类型触发器
python3 trigger_engine.py register-crons <project_dir>
```

## 最佳实践

1. **触发器数量控制**: 单项目建议不超过 10 个触发器，避免评估开销过大
2. **interval 合理设置**: 最小间隔建议 5 分钟，避免频繁操作
3. **on_message 防重复**: 始终设置 `max_fires`，避免反复触发
4. **poll 设超时**: HTTP 轮询必须设 `timeout_minutes`，避免无限轮询
5. **Focus auto_complete**: 只有明确的交付型焦点才开启，探索型焦点手动管理
6. **cron vs interval**: 需要精确时间用 cron，需要相对间隔用 interval
7. **触发器状态持久化**: 通过 `trigger_state.json` 自动持久化，compaction 不影响

## 命令行参考

```bash
# 评估触发器（在 heartbeat 中使用）
python3 trigger_engine.py evaluate <project_dir>

# 查看状态
python3 trigger_engine.py status <project_dir>

# 手动触发
python3 trigger_engine.py fire <project_dir> <trigger_id>

# 通过 project_state_v2 集成调用
python3 project_state_v2.py trigger-evaluate <project_id>
python3 project_state_v2.py trigger-status <project_id>
python3 project_state_v2.py focus-list <project_id>
python3 project_state_v2.py focus-update <project_id> <focus_id> "[/]"
```
