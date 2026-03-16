# 🏢 OPC — One-Person Company

> **Multi-Agent 编排技能** — 让 OpenClaw 成为一人公司的 CEO

基于 OpenClaw 原生 `sessions_spawn` / `sessions_send` 机制，OPC 把复杂任务拆解为多 Agent 并行协作，CEO（OpenClaw）负责规划、招募、监控和交付。

## v3.2 新特性

- **内置 LZW 顾问 Persona**：`playbook/personas/lzw.md` — OPC-Skill 原作者思维框架，可直接被任意 Agent 角色借鉴
- **personas/ 目录**：可扩展的 Advisor Persona 库，支持用户沉淀自己的方法论并注入 Agent 团队

## v3.1 特性

- **用户模型自学习**：Phase 0 读取用户模型，Phase 4 写回，越用越懂你
- **三层架构**：`brain/`（决策）+ `engine/`（执行）+ `playbook/`（知识）
- **Phase 0 Context Intake**：强制入口，理解背景→给出方案→等确认后才执行
- **工具发现 v2**：domain × capability 标签体系，精准推荐，OPC 自排除
- **触发器融入生命周期**：Phase 3 每轮循环必须 trigger-evaluate

## 快速上手

\`\`\`bash
# 在 OpenClaw 中安装
# 将整个目录放入 ~/.openclaw/skills/agent-orchestration-20260309-lzw/
\`\`\`

## 架构

\`\`\`
agent-orchestration-20260309-lzw/
├── SKILL.md              ← 入口（v3.2）
├── brain/                ← CEO 决策层
│   ├── core-flow.md      ← 四阶段流程 + Context Intake 规范
│   ├── task-decomposition.md
│   ├── role-design.md
│   └── collaboration-patterns.md
├── engine/               ← 执行引擎层
│   ├── project_state.py  ← 项目状态管理（核心）
│   ├── trigger_engine.py ← Aware 触发器
│   ├── tool_discovery.py ← 工具发现（标签体系 v2）
│   └── diagnose_agent.py ← 自动归因
└── playbook/             ← 知识与模板层
    ├── persona-priming.md      ← Persona 方法论 + 预置库索引
    ├── personas/
    │   └── lzw.md              ← 内置 LZW 顾问 Persona（v3.2 新增）
    ├── scenarios/              ← 实战案例
    └── templates/              ← Prompt 模板
\`\`\`

## Persona Priming

OPC 的核心创新之一：给每个 Agent 角色注入顶级人才的方法论，激活 LLM 预训练中的深层专业知识。

**预置 Persona 库**覆盖营销（Kotler / Ogilvy / Andrew Chen）、技术（Fowler / Jeff Dean）、研究（Drucker / Nate Silver / Mary Meeker）、创意（Gaiman）等方向。

**v3.2 内置 LZW 顾问 Persona**（\`playbook/personas/lzw.md\`）：

与预置公众人物不同，LZW Persona 是完整的方法论文档。这开创了一个新范式：**用户可以把自己的思维框架沉淀为 Persona，注入到自己的 Agent 团队中。**

\`\`\`
李增伟 · LZW · OPC-Skill Author
  - 体系化收敛：整合平台/工具/策略/用户多维视角
  - 范式驱动：3A范式 / Agentic Commerce 理论架构师
  - 因人施策：根据受众背景调整呈现方式，娓娓道来
\`\`\`

## 实战案例

- [营销活动搭建](playbook/scenarios/marketing-campaign.md)
- [研究项目](playbook/scenarios/research-project.md)

## 版本历史

| 版本 | 日期 | 核心变更 |
|------|------|---------|
| **v3.2** | **2026-03-16** | **内置 LZW 顾问 Persona + personas/ 目录** |
| v3.1 | 2026-03-14 | 用户模型自学习：Phase 0 读取 + Phase 4 写回 |
| v3.0 | 2026-03-14 | 三层架构重构 + Context Intake + 工具发现标签体系 v2 |
| v2.0 | 2026-03-12 | Aware 触发器 + 运行时工具自发现 + Focus 焦点管理 |
| v1.4 | 2026-03-11 | 状态持久化 + 断点续传 + 自动归因 + 成本自动化 |
| v1.0 | 2026-03-09 | 首版：角色卡 + 任务分解 + 协作模式 + 成本追踪 |

见完整 [CHANGELOG.md](CHANGELOG.md)

---

Apache License 2.0 · Built for [OpenClaw](https://github.com/openclaw/openclaw)
