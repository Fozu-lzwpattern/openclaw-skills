# 成本追踪方法（v1.1 — 自动化增强）

## 设计原则

1. **CEO 主动采集，不依赖 Sub-agent 自觉汇报**
2. **结合 session_status + project_state.py 双路径**
3. **预算是硬约束，超限自动暂停**

## 追踪维度

| 维度 | 方式 |
|------|------|
| 按角色 | project_state.py 的 `byRole` 字段 |
| 按任务 | 每个 agent-complete 时记录 tokens |
| 按阶段 | Phase 切换时汇总当前成本 |
| 总计 | project_state.py cost 命令 |

## CEO 主动采集机制（v1.1 新增）

### 不再依赖 Sub-agent 汇报

旧方案（v1.0）：要求 Sub-agent 在 announce 中包含 `### Token 消耗\n约 {N}K tokens`

**问题**：实测中 Sub-agent 基本不汇报 token，即使汇报也不准确。

新方案（v1.1）：**CEO 主动通过 session_status 获取**

```
每个 Sub-agent 完成（announce 或超时主动检查）后：
1. 调用 session_status(sessionKey=<agent_session_key>)
2. 从返回中提取 Tokens 使用量
3. 写入 project_state.py：agent-complete <pid> <label> <output> <tokens>
```

### 获取 sessionKey 的方法

spawn 返回值中包含 sessionKey。如果 spawn 后没记录：
```
subagents(action=list) → 找到目标 agent → 获取 sessionKey
```

### 汇报流程

```
Phase 完成时：
1. python3 project_state.py cost <project_id>
2. 输出成本报告给用户
3. 检查是否超预算
```

## 预算告警（增强）

| 阈值 | 动作 |
|------|------|
| 50% | 汇报进度 + 当前成本 |
| 80% | ⚠️ 告警用户，评估剩余任务是否在预算内 |
| 100% | 🛑 暂停所有 agent，等待用户授权追加预算或削减范围 |
| 120% | 🚨 强制终止，生成成本超支报告 |

### 预算设置

初始化项目后设置预算：
```bash
python3 project_state.py show <pid> 
# 手动编辑 state.json 的 cost.budgetLimit 字段
# 或在 CEO 规划阶段根据任务复杂度自动估算
```

### 自动估算公式

```
简单任务（单角色）：50K tokens
中等任务（2-3角色）：150K tokens
复杂任务（4+角色/并行）：300K tokens
每增加一个 Sub-agent：+50K 基础开销
```

## CEO 汇总模板

```markdown
📊 项目成本报告 — {project_name}
周期：{start} → {end}

| 角色 | 任务数 | Token消耗 | 成本估算 |
|------|--------|----------|---------|
| {role1} | {n} | {tokens}K | ${cost} |
| {role2} | {n} | {tokens}K | ${cost} |
| CEO协调 | - | {tokens}K | ${cost} |
| **总计** | **{total_tasks}** | **{total_tokens}K** | **${total_cost}** |

预算使用: {used}% ({total}/{budget})
```

## 成本优化建议（v1.1 更新）

1. **先小后大**：先用简单方案验证，再投入大预算
2. **复用产出**：Sub-agent 产出保存为文件（project outputs/），后续可直接读取不用重新生成
3. **裁剪角色**：简单项目合并角色，减少协调开销
4. **选对 model**：简单任务用基础模型，复杂任务才用高端模型
5. **断点续传**：agent 失败后从断点恢复，而非完全重试（利用 checkpoint）
6. **确认流程分级**：简单任务压缩确认轮次（见下方）

## 确认流程分级（v1.1 新增）

### 复杂度评估

在 Phase 1（项目规划）完成后，CEO 自动评估复杂度：

```
agent数量 ≤ 2 且无串行依赖 → 简单
agent数量 3-5 或有串行依赖 → 中等
agent数量 > 5 或有复杂依赖图 → 复杂
```

### 确认轮次

| 复杂度 | 确认轮次 | 说明 |
|--------|---------|------|
| 简单 | **1轮** | 合并：目标确认 + 角色方案 + 开始执行 |
| 中等 | **2轮** | 第1轮：目标+方案；第2轮：执行模式确认 |
| 复杂 | **3轮** | 标准流程不变（任务理解→组织方案→执行模式） |

### 简单任务的1轮确认模板

```markdown
📋 任务确认

**目标**: {goal}
**方案**: spawn {n} 个 agent（{role1}、{role2}）
**执行模式**: 当前Session / 独立Session
**预估成本**: ~{budget}K tokens

确认执行？(Y/N)
```
