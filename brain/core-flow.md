# OPC 核心执行流程

> CEO 决策层 — 完整的 OPC 工作循环

---

## Phase 0：Context Intake（上下文摄入）⭐ 最重要

**OPC 被触发后，第一步必须是理解背景、任务和目标，给出推进方案，征询确认。**

不允许跳过此步骤直接开始规划。

### 0.1 主动追问框架

CEO 必须围绕以下维度明确信息（不确定的主动问，信息充分则简化）：

```
【背景】
- 这个任务在什么业务场景下？有什么前置条件？
- 是新建还是继续已有工作？

【目标】
- 最终交付物是什么？（文档/页面/代码/分析报告...）
- 成功的标准是什么？怎么判断"完成了"？

【约束】
- 截止时间？预算（token 上限）？
- 有哪些平台限制（需要 SSO/浏览器/特定工具）？
- 需要人工介入的节点？

【范围】
- 从哪里开始、到哪里结束？
- 哪些不在本次范围内？
```

### 0.2 推进方案输出格式

理解完成后，CEO 输出以下结构化方案，**等用户确认后才进入 Phase 1**：

```markdown
## 📋 OPC 项目方案

**背景理解**：{一句话概括}
**目标**：{交付物 + 成功标准}
**约束**：{时间/预算/限制}

**推进方案**：
- 角色配置：{N 个角色，名称 + 主要职责}
- 协作模式：{串行/并行/混合，简述顺序}
- 预估总预算：~{N}K tokens
- 预计耗时：~{N} 分钟

**确认后开始执行，是否有需要调整的地方？**
```

### 0.3 复杂度自动判断

| 条件 | 复杂度 | 确认轮次 |
|------|--------|---------|
| ≤2 角色，单一流水线 | 简单 | 1轮（合并 0+1） |
| 3-5 角色，有并行 | 中等 | 1轮（0+1合并）|
| >5 角色，跨业务线，>200K预算 | 复杂 | 2轮（0理解→1方案）|

---

## Phase 1：项目规划

1. 用 `project_state.py init` 创建项目
2. 拆解 OKR → Epic → Task（见 task-decomposition.md）
3. 定义角色、依赖关系、token 预算
4. 工具扫描（可选，见 engine/README.md）
5. **用户确认方案后才执行**

```bash
python3 engine/project_state.py init "项目名称"
python3 engine/project_state.py update-phase <pid> phase_1_planning
```

---

## Phase 2：团队组建

按角色定义 spawn Sub-agents，注入角色卡 + Heartbeat 协议。

```bash
python3 engine/project_state.py agent-start <pid> <label> '{"role":"角色名"}'
```

每个 spawn 后必须给用户一条确认消息：
> ✅ {角色} 已启动（预计 N 分钟），持续监控中。

---

## Phase 3：执行监控循环

```
Sub-agent 完成 / 超时检查
    │
    ├── 收到结果 → 质量验收
    │   ├── OK → agent-complete → 触发下游
    │   └── 不OK → sessions_send 修改 → 最多 3 次
    │
    ├── 超时未收到 → 主动检查
    │   subagents(action=list) → sessions_history → 拉取结果
    │
    ├── 触发器评估（每轮循环必须执行）
    │   python3 engine/project_state.py trigger-evaluate <pid>
    │
    └── 阶段进度汇报给用户
```

### 主动监控间隔

| 任务复杂度 | 首次检查 | 后续间隔 |
|-----------|---------|---------|
| 简单 | 3 min | 2 min |
| 中等 | 5 min | 3 min |
| 复杂 | 10 min | 5 min |

---

## Phase 4：交付汇总

1. 汇总所有 Sub-agent 产出
2. 生成成本报告：`python3 engine/project_state.py cost <pid>`
3. 关闭项目：`python3 engine/project_state.py close <pid>`
4. 向用户交付最终成果 + 成本报告

---

## 关键规则（CEO 必须遵守）

1. **Context Intake 不可跳过** — Phase 0 是所有 OPC 项目的入口，必须执行
2. **确认后才执行** — 任何 spawn 必须在用户确认方案后才触发
3. **不信任 announce** — 超时必须主动检查
4. **每步持久化** — Phase 切换、agent 状态变更立即写入 project_state
5. **断点优于重试** — agent 失败先保存 checkpoint，再考虑重新 spawn
6. **Phase 3 必须 trigger-evaluate** — 每轮监控循环必须调用触发器评估
