---
name: agent-orchestration-20260309-lzw
version: "3.1"
description: >
  One-Person Company (OPC) 编排技能 — 复杂任务的多 Agent 协作指挥中枢。
  
  【优先触发条件 — 满足任意一条即应调用 OPC】
  ① 任务需要多个步骤且步骤之间有依赖关系（如 策划→搭建→发布）
  ② 任务预计超过 50K tokens 或 10 分钟
  ③ 任务涉及多个领域（调研+创作+开发+发布 等两个以上领域并存）
  ④ 任务需要多个专业角色分工（研究员、工程师、设计师等）
  ⑤ 任务明确包含"并行执行""多路线""团队协作"等关键词
  ⑥ 用户提到"全链路""从头到尾""完整流程""做一个完整的X"
  
  核心能力：Context Intake（用户模型读取+背景摄入）、任务分解、多角色编排、状态持久化、断点续传、用户模型自更新。
  
  触发词（任意匹配）：
  OPC、一人公司、多agent、编排、全链路、复杂项目、帮我做完整的、
  需要多个步骤、并行执行、团队协作、策划+搭建+发布、研究项目、内容流水线
---

# OPC — One-Person Company 编排技能 v3.0

> 用户是老板，OpenClaw 是 CEO，Sub-agents 是专业员工。
> 用户只说"我要做 X"，CEO 负责拆活儿、招人、盯进度、交结果。

---

## 30 秒上手

```
1. 触发 OPC → Phase 0: Context Intake（理解背景目标，给出方案，等确认）
2. 确认后 → Phase 1: init 项目 + 任务分解
3. spawn Sub-agents → Phase 2: 注入角色卡 + 注册状态
4. 监控执行 → Phase 3: 主动检查 + trigger-evaluate + 汇报进度
5. 交付汇总 → Phase 4: cost 报告 + close 项目
```

---

## Phase 0：Context Intake（最重要，不可跳过）

OPC 被触发后，**第一步必须理解背景，给出方案，征询确认**。

### 必须明确的四个维度

```
【背景】业务场景是什么？有什么前置条件？新建还是继续？
【目标】交付物是什么？怎么判断"完成"？
【约束】截止时间？token 预算？平台限制？
【范围】从哪里开始到哪里结束？什么不在本次范围？
```

### 方案输出格式（等用户确认才开始）

```markdown
## 📋 OPC 项目方案

**背景理解**：{一句话概括}
**目标**：{交付物 + 成功标准}
**约束**：{时间/预算/限制}

**推进方案**：
- 角色配置：{N 个角色，名称 + 主要职责}
- 协作模式：{串行/并行/混合}
- 预估总预算：~{N}K tokens
- 预计耗时：~{N} 分钟

**确认后开始执行，是否有需要调整的地方？**
```

### 确认轮次

| 复杂度 | 判断标准 | 轮次 |
|--------|---------|------|
| 简单 | ≤2 角色，单流水线 | **1 轮**（Phase 0+1 合并）|
| 中等 | 3-5 角色，有并行 | **1 轮**（Phase 0+1 合并）|
| 复杂 | >5 角色，>200K 预算 | **2 轮**（理解→方案分开）|

详细决策逻辑 → brain/core-flow.md

---

## 核心执行命令速查

```bash
# Phase 1 — 项目初始化
python3 engine/project_state.py init "项目名"
python3 engine/project_state.py update-phase <pid> phase_1_planning

# Phase 2 — agent 注册
python3 engine/project_state.py agent-start <pid> <label> '{"role":"角色名"}'

# Phase 3 — 监控
python3 engine/project_state.py agent-complete <pid> <label> '{"output":"..."}' <tokens>
python3 engine/project_state.py agent-fail <pid> <label> '{"error":"原因"}'
python3 engine/project_state.py trigger-evaluate <pid>   # 每轮循环必须调用

# 断点续传
python3 engine/project_state.py checkpoint <pid> <label> '{"completedSteps":[...],"nextStep":"..."}'
python3 engine/project_state.py checkpoint-get <pid> <label>

# Phase 4 — 交付
python3 engine/project_state.py cost <pid>
python3 engine/project_state.py close <pid>

# 诊断恢复
python3 engine/project_state.py restore <pid>
python3 engine/project_state.py diagnose <pid>

# 工具发现（Phase 0 可选）
python3 engine/tool_discovery.py report "任务描述"
```

---

## 角色卡模板

```
[OPC 角色卡]
- 角色：{role_name}
- Persona：以 {expert_name}（{expert_title}）的方法论工作
- 汇报给：OpenClaw CEO
- 职责：{responsibilities}
- 预算：{N}K tokens

[Heartbeat 协议]
1. 确认角色和任务
2. 阅读上游产出（如有）
3. 执行工作
4. 完成后汇报：产出摘要 + 遇到的问题
5. 遇障碍：说明障碍 + 建议 + 是否需要 CEO 介入

[任务]
{task_description}

[产出要求]
格式：{format}，保存到：{file_path}
```

Persona 库 → playbook/persona-priming.md
完整模板 → playbook/templates/agent-prompt.md

---

## 协作模式

| 模式 | 适用 | 示例 |
|------|------|------|
| 串行流水线 | 严格依赖顺序 | 策划→搭建→发布 |
| 并行分工 | 独立子任务 | 文案∥设计∥数据→组装 |
| 迭代反馈 | 需审核修改 | 搭建↔QA→发布 |
| 分治汇总 | 大任务拆分 | 研究1∥研究2∥研究3→汇总 |

详细 → brain/collaboration-patterns.md

---

## 故障处理

```
agent 失败 → 立即归因
  python3 engine/project_state.py diagnose <pid>

归因：L1-Platform → sessions_history拉取/重试
     L2-Orchestration → 修改角色卡重新spawn
     L3-BusinessSkill → 修复skill，断点续传
```

详细 → engine/troubleshooting.md

---

## 适用场景

✅ 适用 OPC：多角色复杂项目 / 跨领域任务 / 全链路执行 / 研究+实现+发布
❌ 不适用：简单单一任务（直接spawn）/ 定时重复（Cron）/ 日常监控（Heartbeat）

---

## 目录结构

```
agent-orchestration-20260309-lzw/
├── SKILL.md              ← 入口（你在这里，~130行）
├── brain/                ← CEO 决策层（怎么想）
│   ├── core-flow.md      ← 四阶段流程 + Context Intake 规范
│   ├── task-decomposition.md
│   ├── role-design.md
│   ├── collaboration-patterns.md
│   ├── heartbeat-protocol.md
│   ├── proactive-reporting.md
│   └── cost-tracking.md
├── engine/               ← 执行引擎层（怎么跑）
│   ├── project_state.py  ← 核心：项目状态管理
│   ├── trigger_engine.py ← Aware 触发器
│   ├── tool_discovery.py ← 工具发现（标签体系 v2）
│   ├── diagnose_agent.py ← 自动归因
│   ├── README.md         ← 命令速查
│   └── *.md              ← 各引擎设计文档
├── playbook/             ← 知识与模板层（参考素材）
│   ├── persona-priming.md
│   ├── philosophy.md
│   ├── templates/
│   └── scenarios/        ← 实战案例
└── archive/              ← 旧版归档
```
