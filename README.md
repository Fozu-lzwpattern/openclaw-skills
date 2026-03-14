# 🏢 OPC — One-Person Company

> **Multi-Agent 编排技能** — 让 OpenClaw 成为一人公司的 CEO

基于 OpenClaw 原生 `sessions_spawn` / `sessions_send` 机制，OPC 把复杂任务拆解为多 Agent 并行协作，CEO（OpenClaw）负责规划、招募、监控和交付。

## v3.1 新特性

- **用户模型自学习**：Phase 0 读取用户模型，Phase 4 写回，越用越懂你
- **三层架构**：`brain/`（决策）+ `engine/`（执行）+ `playbook/`（知识）
- **Phase 0 Context Intake**：强制入口，理解背景→给出方案→等确认后才执行
- **工具发现 v2**：domain × capability 标签体系，精准推荐，OPC 自排除
- **触发器融入生命周期**：Phase 3 每轮循环必须 trigger-evaluate

## 快速上手

```bash
# 在 OpenClaw 中安装
# 将整个目录放入 ~/.openclaw/skills/agent-orchestration-20260309-lzw/
```

## 架构

```
agent-orchestration-20260309-lzw/
├── SKILL.md              ← 入口（~200行）
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
    ├── scenarios/        ← 实战案例（营销活动/研究项目）
    └── templates/        ← Prompt 模板
```

## 实战案例

- [营销活动搭建](playbook/scenarios/marketing-campaign.md)：策划员 → 3 搭建员并行 → QA
- [研究项目](playbook/scenarios/research-project.md)：4 研究员并行分治 → 汇总员（Kangas2 嵌入式认知研究实战）

## 版本历史

见 [CHANGELOG.md](CHANGELOG.md)

---

MIT License · Built for [OpenClaw](https://github.com/openclaw/openclaw)
