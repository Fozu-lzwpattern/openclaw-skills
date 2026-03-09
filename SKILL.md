---
name: agent-orchestration-20260309-lzw
description: >
  One-Person Company (OPC) 编排技能 — 让 OpenClaw 成为指挥调度一群专业 Agent 
  协作完成企业复杂任务的"一人公司"CEO。借鉴 PaperClip 的组织管理方法论，
  通过 OpenClaw 原生的 sessions_spawn/sessions_send 机制实现多 Agent 协作。
  触发场景：(1)需要多角色协作的复杂项目 (2)营销活动全链路执行 (3)内容生产流水线
  (4)研究项目多人分工 (5)任何需要"拆任务-分角色-追进度-汇成果"的场景。
  核心能力：角色定义、任务分解、Heartbeat协议、成本追踪、协作编排。
---

# Agent Orchestration — One-Person Company (OPC)

> 让 OpenClaw 成为能指挥调度专业 Agent 团队的"一人公司"CEO。

## 核心理念

**OPC (One-Person Company)** = 一个人（用户）+ 一个 AI CEO（OpenClaw Main Session）+ 一群专业 Agent（Sub-agents）

用户只需说"我要做 X"，OpenClaw 自动完成：
1. 拆解任务为可执行的子任务
2. 定义所需角色并 spawn 对应 Agent
3. 分配任务、监控进度
4. 汇总成果、追踪成本
5. 向用户交付最终产出

## 目录结构

```
agent-orchestration-20260309-lzw/
├── SKILL.md                           # 本文件 — 入口
├── references/                        # 方法论（how-to）
│   ├── role-design.md                # 角色定义方法论
│   ├── task-decomposition.md         # 任务分解（OKR → Epic → Task）
│   ├── heartbeat-protocol.md         # Agent 执行协议
│   ├── cost-tracking.md              # 成本追踪方法
│   └── collaboration-patterns.md     # 协作模式
├── templates/                         # 可复用模板
│   ├── agent-prompt.md               # Sub-agent task prompt 模板
│   ├── project-plan.md               # 项目计划模板
│   └── cost-report.md                # 成本报告模板
├── scenarios/                         # 场景案例
│   └── marketing-campaign.md         # 营销活动全链路案例
└── scripts/
    ├── cost_summary.sh               # 汇总 token 消耗
    └── project_tracker.py            # 项目状态追踪
```

## 核心流程：OPC 工作循环

```
用户意图 → Phase 1: 项目规划 → Phase 2: 团队组建 → Phase 3: 执行监控 → Phase 4: 交付汇总
```

### Phase 1: 项目规划（CEO 执行）

1. 理解用户目标
2. 拆解为 OKR → Epic → Task（见 [references/task-decomposition.md](references/task-decomposition.md)）
3. 为每个 Task 确定角色、依赖、预算
4. 输出项目计划，**请用户确认后再执行**

### Phase 2: 团队组建

按角色定义 `sessions_spawn` Sub-agents，注入角色卡 + Heartbeat 协议。

```python
# 示例：spawn 一个"活动策划员"
sessions_spawn(
  task="""
  [OPC 角色卡]
  - 角色：活动策划员
  - 隶属：营销团队
  - 汇报给：OpenClaw CEO
  - 职责：根据活动目标制定策划方案，包括主题、目标人群、预算分配、时间节点
  - 预算：本次任务 token 上限 30K

  [Heartbeat 协议]
  1. 确认身份和任务
  2. 执行工作
  3. 产出必须包含：方案文档 + token 消耗估算
  4. 如遇障碍，明确说明需要什么帮助

  [任务]
  为 315 消费者权益日制定一个到店餐饮促销活动策划方案。
  目标：提升到店餐饮 GMV 15%，活动周期 3.10-3.16。

  [产出要求]
  Markdown 格式，包含：活动主题、目标人群、促销机制、预算分配、时间节点、预期效果。
  """,
  label="planner-315"
)
```

详细角色定义 → [references/role-design.md](references/role-design.md)
Prompt 模板 → [templates/agent-prompt.md](templates/agent-prompt.md)

### Phase 3: 执行监控（循环）

```
Sub-agent announce 产出
    │
    ├── CEO 检查质量
    │   ├── OK → 更新状态 → 触发下游依赖任务
    │   └── 不OK → sessions_send 要求修改
    │
    ├── 异常处理
    │   ├── 超时 → 检查 subagents list，必要时 kill + 重新 spawn
    │   ├── 失败 → 分析原因，决定重试或调整方案
    │   └── 预算超限 → 告警用户，等待指示
    │
    └── 追踪 token 消耗
```

### Phase 4: 交付汇总

1. 汇总所有 Sub-agent 产出
2. 生成项目成果文档
3. 生成成本报告（模板 → [templates/cost-report.md](templates/cost-report.md)）
4. 向用户交付

## 角色卡规范

每个 Sub-agent 通过 task prompt 注入角色卡：

```
[OPC 角色卡]
- 角色：{role_name}
- 隶属：{team_name}
- 汇报给：OpenClaw CEO
- 职责：{responsibilities}
- 预算：{budget}K tokens
- 可用工具：{tools}（如需业务 Skill 则说明）

[Heartbeat 协议]
1. 确认身份和任务
2. 执行工作
3. 产出格式：{output_format}
4. 汇报：产出摘要 + token 消耗
5. 遇障碍：说明障碍 + 建议方案 + 是否需要 CEO 介入

[任务]
{task_description}

[产出要求]
{output_requirements}

[约束]
{constraints}
```

详细 → [references/role-design.md](references/role-design.md)

## 任务分解

OKR → Epic → Task 三层结构：

```
Objective: {目标}
├── KR1: {关键结果1}
│   ├── Epic 1.1: {大功能块}
│   │   ├── Task: {具体任务} → {角色} [依赖: 无] [预算: XK]
│   │   └── Task: {具体任务} → {角色} [依赖: Task上] [预算: XK]
│   └── Epic 1.2: ...
└── KR2: ...
```

Task 状态机：`pending → assigned → in_progress → review → completed / failed`

详细 → [references/task-decomposition.md](references/task-decomposition.md)

## 协作模式

| 模式 | 适用场景 | 示例 |
|------|---------|------|
| 串行流水线 | 严格依赖顺序 | 策划 → 搭建 → 发布 |
| 并行分工 | 独立子任务 | 文案 ∥ 设计 ∥ 数据 → 组装 |
| 迭代反馈 | 需要审核 | 搭建 ↔ 审核 → 发布 |
| 分治汇总 | 大任务拆分 | 研究1 ∥ 研究2 ∥ 研究3 → 汇总 |

详细 → [references/collaboration-patterns.md](references/collaboration-patterns.md)

## 成本追踪

脚本 → `bash scripts/cost_summary.sh`
模板 → [templates/cost-report.md](templates/cost-report.md)
详细 → [references/cost-tracking.md](references/cost-tracking.md)

## 场景案例

| 案例 | 文件 |
|------|------|
| 营销活动全链路 | [scenarios/marketing-campaign.md](scenarios/marketing-campaign.md) |

## 与业务 Skill 的关系

本 Skill 是**编排层**（谁做什么、怎么协作），业务 Skill 是**执行层**（具体怎么操作）：

```
agent-orchestration（编排层 — 本 Skill）
    │ spawn + 角色注入
    ├── gundam-ops（高达搭建执行）
    ├── calendar-api（日程管理）
    ├── catclaw-search（信息搜索）
    ├── catclaw-image（图片生成）
    └── ... 更多业务 Skill
```

编排层 Sub-agent 的 task prompt 中可以提示"你可以使用 gundam-ops skill 来操作高达平台"，让 Sub-agent 在执行时自动加载对应业务 Skill。

## 使用限制

1. **Sub-agent 不能 spawn Sub-agent** — 所有 spawn 由 Main Session 执行
2. **Sub-agent 默认无 session 工具** — 协作通过 Main Session 中转
3. **预算是软约束** — 依赖 Sub-agent 自觉汇报
4. **项目状态在 context 中** — /reset 会丢失，重要项目应写文件持久化

## 故障排查与问题归因

遇到问题时先归因（L1平台/L2编排/L3业务），再修复：
详细 → [references/troubleshooting.md](references/troubleshooting.md)

### 关键防坑规则

**规则1：不信任 announce，主动检查**
每次 spawn 后必须有超时检查机制。如果合理时间内没收到 announce，主动执行：
```
subagents(action=list)  → 看状态
sessions_history(key)   → 拉结果
```

**规则2：三步归因**
1. spawn 成功吗？→ 不成功 = L1 平台问题
2. 产出有吗？→ done 但无 announce = L1，主动拉取
3. 产出对吗？→ 跑偏 = L2 编排问题，操作报错 = L3 业务 Skill 问题

## 设计理念与运行逻辑

完整的设计理念、运行逻辑、与业务 Skill 关系说明：
→ [references/design-philosophy.md](references/design-philosophy.md)

核心要点：
- OPC = 用户(老板) + OpenClaw(CEO) + Sub-agents(员工)
- CEO 不干活，只管人（规划、分配、监控、汇总）
- 编排与执行分离：OPC 管协作，gundam-ops 等管操作
- 新增执行能力不需要改编排逻辑

## 多轮对话：OPC 组织设定

**发起企业级复杂任务时，必须先经过多轮对话确认：**

1. **第1轮 — 任务理解**：确认目标、交付物、约束
2. **第2轮 — 组织方案**：提出角色配置、协作模式、预算
3. **第3轮 — 执行模式**：
   - A. 当前 Session（小中型，实时可见）
   - B. 独立 Session（大型/长任务，后台执行）

**用户确认后才开始执行。不可跳过确认步骤。**

## Persona Priming（角色增强）

给每个角色注入顶级人才的方法论，激活 LLM 的深层专业知识：

```
[OPC 角色卡]
- 角色：活动策划员
- Persona：以 Philip Kotler（营销之父）的方法论和思维框架工作
```

原则：**借鉴方法论，而非模仿人格。**
详细 → [references/persona-priming.md](references/persona-priming.md)

## CEO 主动监控机制

**不信任 announce，CEO 必须主动轮询：**

| 任务复杂度 | 首次检查 | 后续间隔 |
|-----------|---------|---------|
| 简单 | 3min | 每2min |
| 中等 | 5min | 每3min |
| 复杂 | 10min | 每5min |

**四条汇报规则：**
1. spawn 后给用户确认
2. 到达检查点必须汇报状态
3. 阶段转换必须通知
4. 异常立即告警

详细 → [references/proactive-reporting.md](references/proactive-reporting.md)
