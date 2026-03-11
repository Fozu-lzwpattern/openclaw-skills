# OPC 故障排查与问题归因（v1.1 — 自动归因增强）

## 问题归因原则

OPC 编排中遇到问题时，**先用自动归因工具，再人工确认**。

### 自动归因工具

```bash
python3 scripts/diagnose_agent.py '{"spawn":"ok|error|timeout","announce":"received|missing","subagent_status":"active|done|error|timeout","output_quality":"good|low_quality|off_topic|wrong_format|error","error_msg":"具体错误信息","dependency_error":false}'
```

### 归因层级

| 层 | 来源 | 典型问题 | 自动归因关键词 |
|----|------|---------|-------------|
| L1 | **OpenClaw 平台** | spawn 失败、announce 丢失、session 超时 | spawn=error, announce=missing, subagent_status=timeout |
| L2 | **OPC 编排 Skill** | 角色定义不清、产出偏离、依赖管理错误 | output_quality=off_topic/low_quality/wrong_format |
| L3 | **业务 Skill** | API 认证过期、浏览器交互、组件版本 | error_msg 含 auth/cdp/browser/component 等 |
| L4 | **外部依赖** | 网络不通、服务不可用 | error_msg 含 network/502/503/connection |

### 归因决策树（人工版）

```
sub-agent 没有结果？
├── spawn 返回 error → L1：OpenClaw 平台问题
├── spawn accepted 但无 announce
│   ├── subagents list 显示 active → 还在运行，等待
│   ├── subagents list 显示 done → L1：announce 机制问题
│   │   → 缓解：主动 sessions_history 拉取结果
│   └── subagents list 显示 error → 检查错误
│       ├── task 内容有语法错误 → L2：prompt 问题
│       └── 工具调用失败 → L3：业务 Skill 问题
│
sub-agent 有结果但不符合预期？
├── 完全跑偏 → L2：角色卡定义不清
├── 方向对但质量差 → L2：task 描述不够具体
├── 方向对但操作报错 → L3：业务 Skill 问题
└── 方向对质量好但格式不对 → L2：产出要求不明确
```

## CEO 标准故障处理流程（v1.1 新增）

### Step 1: 发现问题

触发条件：
- announce 超时未到达
- subagents list 显示 error/done 但无产出
- 产出质量不达标

### Step 2: 自动归因

```python
# CEO 自动收集症状
symptoms = {
    "spawn": "ok",           # spawn 返回状态
    "announce": "missing",   # 是否收到 announce
    "subagent_status": "",   # subagents list 的状态
    "output_quality": "",    # 产出质量评估
    "error_msg": ""          # 如果有错误信息
}
# 运行归因
# python3 scripts/diagnose_agent.py '<symptoms_json>'
```

### Step 3: 执行修复

| Level | 自动修复 | 人工介入 |
|-------|---------|---------|
| L1 announce丢失 | ✅ 自动 sessions_history 拉取 | 无需 |
| L1 spawn失败 | 自动重试1次 | 重试仍失败→告警用户 |
| L1 session超时 | 检查 checkpoint → 断点续传 | 无 checkpoint→重新 spawn |
| L2 产出跑偏 | sessions_send 发送修正指令 | 3次修正仍不达标→告警用户 |
| L3 认证过期 | 触发重新认证流程 | 需要用户扫码 |
| L3 浏览器问题 | 串行化重试 | 持续失败→告警用户 |
| L4 网络问题 | 等待5min后重试 | 持续不可用→告警用户 |

### Step 4: 记录

```bash
# 归因结果记录到项目状态
python3 scripts/project_state.py agent-fail <pid> <label> '{"error":"<diagnosis>"}'
python3 scripts/project_state.py checkpoint <pid> <label> '{"completedSteps":[...],"context":{...}}'
```

### Step 5: 恢复

如果需要断点续传：
```bash
# 获取断点
python3 scripts/project_state.py checkpoint-get <pid> <label>
# 重新 spawn，注入断点
sessions_spawn(task="""
[断点续传]
上一个 agent 因以下原因失败：{error}
已完成步骤：{completedSteps}
当前上下文：{context}
请从以下步骤继续：{nextStep}

[原始任务]
{original_task}
""")
```

## 已知问题与缓解方案

### P1: Sub-agent 不 announce（高频）

**现象**：sub-agent 完成任务（subagents list 显示 done），但 Main Session 收不到 announce。

**自动归因**：`{"spawn":"ok","announce":"missing","subagent_status":"done"}` → L1

**缓解策略**：

```
CEO 编排流程中必须加入「主动检查」步骤：

1. spawn sub-agent
2. 等待合理时间（简单 2min，中等 5min，复杂 10min）
3. 收到 announce → 正常流程
4. 未收到 → 执行主动检查：
   a. subagents(action=list) 查看状态
   b. done → sessions_history 拉取结果
   c. active → 继续等待
   d. error → diagnose_agent.py 自动归因
```

### P2: Sub-agent 使用了错误的 model

**缓解**：sessions_spawn 时指定 model 参数。

### P3: Sub-agent 超时

**缓解**：设置 runTimeoutSeconds；超时后自动保存 checkpoint。

### P4: Compaction 丢失项目状态（v1.1 新增）

**现象**：CEO session 发生 compaction，丢失所有 Phase 进度和 agent 状态。

**缓解**：
1. 每个 Phase/Agent 状态变更后写入 project_state.py
2. Compaction 后执行 `project_state.py restore <pid>` 恢复
3. CEO 启动时自动检查 `workspace/opc-projects/` 是否有未完成项目

### P5: 并行 agent 浏览器 Tab 竞争（v1.1 新增）

**现象**：多个搭建员 agent 同时操作浏览器，互相干扰。

**缓解**：
1. 短期：CEO 编排层串行化浏览器操作（一个完成保存后启动下一个）
2. 中期：每个 agent 开独立 tab
3. 长期：多浏览器实例隔离

## CEO 编排最佳实践

### 1. 每次 spawn 后设置检查点

```
spawn → project_state.py agent-start
     → 等待 announce OR 超时检查
     → 收到结果 → 验证质量
     → project_state.py agent-complete/agent-fail
     → 触发下游
```

### 2. 故障自动处理优先

遇到问题先跑 diagnose_agent.py，自动修复优先，3次自动修复失败才告警用户。

### 3. 断点续传优于完全重试

agent 失败后：
1. 先保存 checkpoint（已完成步骤 + 上下文）
2. kill 失败 agent
3. spawn 新 agent，注入 checkpoint，从断点继续
4. 完全重试只作为最后手段
