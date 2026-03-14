# OPC Project State Manager

OPC 项目状态持久化管理器，解决 compaction 导致执行状态丢失的问题。

## 设计原则

1. **每个 Phase 完成后自动持久化** - 写入 `workspace/opc-projects/{project-id}/state.json`
2. **Compaction 后自动恢复** - CEO 启动时检查 state.json，恢复项目上下文
3. **断点续传** - Sub-agent 失败后可从断点继续，而非完全重试

## 状态文件结构

```json
{
  "project": {
    "id": "opc-20260311-001",
    "name": "愚人节三会场搭建",
    "createdAt": "2026-03-10T18:33:00Z",
    "updatedAt": "2026-03-10T18:45:00Z",
    "currentPhase": "phase_2_execution",
    "status": "in_progress"
  },
  "plan": {
    "okr": "KR: 4.1愚人节活动上线",
    "epics": ["..."]
  },
  "agents": {
    "builder-main": {
      "role": "主会场搭建员",
      "status": "completed",
      "startedAt": "2026-03-10T18:40:00Z",
      "finishedAt": "2026-03-10T18:45:00Z",
      "output": { "activityId": "1014813", "url": "..." },
      "tokens": 45000
    },
    "builder-waimai": {
      "role": "外卖分会场搭建员",
      "status": "completed",
      "startedAt": "2026-03-10T18:40:00Z",
      "finishedAt": "2026-03-10T18:47:00Z",
      "output": { "activityId": "1014814", "url": "..." },
      "tokens": 52000
    },
    "builder-dcan": {
      "role": "到餐分会场搭建员",
      "status": "failed",
      "startedAt": "2026-03-10T18:40:00Z",
      "failedAt": "2026-03-10T18:57:00Z",
      "error": "日期选择器交互超时",
      "checkpoint": {
        "phase": "component_added",
        "completedSteps": ["create_activity", "add_header", "add_coupon"],
        "lastStep": "set_date_range"
      },
      "retryCount": 1
    }
  },
  "checkpoints": {
    "builder-dcan": {
      "phase": "component_added",
      "completedSteps": ["create_activity", "add_header", "add_coupon"],
      "context": { "activityId": "1014818", "components": ["..."] }
    }
  },
  "cost": {
    "totalTokens": 97000,
    "byRole": { "策划员": 35000, "搭建员": 62000 },
    "budgetLimit": 150000,
    "budgetUsedPercent": 65
  }
}
```

## 目录结构

```
workspace/opc-projects/
└── {project-id}/
    ├── state.json           # 项目状态（自动生成）
    ├── plan.md              # 项目计划
    ├── outputs/             # Sub-agent 产出
    │   ├── planner.md       # 策划员产出
    │   ├── builder-main.md  # 主会场搭建产出
    │   └── ...
    └── logs/                # 执行日志
```

## CEO 集成规范

### Phase 完成后必须调用

```
Phase 1（项目规划）完成 → project_state.py update-phase <id> phase_1_completed
Phase 2（团队组建）完成 → project_state.py update-phase <id> phase_2_started
Phase 3（执行监控）完成 → project_state.py update-phase <id> phase_3_completed
Phase 4（交付汇总）完成 → project_state.py update-phase <id> completed
```

### Agent 状态变更必须同步

```
spawn agent → agent-start
agent announce done → agent-complete
agent announce error → agent-fail（同时保存 checkpoint）
```

### Compaction 恢复流程

```
1. CEO 启动时检查 workspace/opc-projects/
2. 找到未完成项目（status != completed）
3. 调用 restore <id> 获取状态摘要
4. 继续执行剩余任务
```

## 断点续传规范

### 何时保存断点

- Agent 失败时
- Agent 被 kill 前
- 长时间无响应（>10min）被标记为可疑时

### 断点内容

断点必须包含：
1. **completedSteps**: 已完成的步骤列表（顺序）
2. **context**: 关键上下文（活动ID、组件树状态、配置参数）
3. **nextStep**: 下一步要做什么

### 断点续传 prompt

恢复 agent 时，注入断点信息：

```
[断点续传]
上一个 agent 因以下原因失败：{error}
已完成步骤：{completedSteps}
当前上下文：{context}
请从以下步骤继续：{nextStep}
```
