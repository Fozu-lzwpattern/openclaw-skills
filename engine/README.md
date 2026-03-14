# Engine 层命令速查

> OPC 执行引擎 — 所有脚本的完整命令参考

工作目录建议切换到 skill 根目录执行：
`cd ~/.openclaw/skills/agent-orchestration-20260309-lzw/`

---

## project_state.py — 项目状态管理

```bash
# 初始化
python3 engine/project_state.py init "项目名" [yyyymmdd]
python3 engine/project_state.py update-phase <pid> <phase>

# Agent 生命周期
python3 engine/project_state.py agent-start <pid> <label> '{"role":"名"}'
python3 engine/project_state.py agent-complete <pid> <label> '{"output":"..."}' <tokens>
python3 engine/project_state.py agent-fail <pid> <label> '{"error":"原因"}'

# 断点续传
python3 engine/project_state.py checkpoint <pid> <label> '{"completedSteps":[...],"nextStep":"..."}'
python3 engine/project_state.py checkpoint-get <pid> <label>

# 查询
python3 engine/project_state.py list
python3 engine/project_state.py show <pid>
python3 engine/project_state.py restore <pid>   # compaction 后恢复用
python3 engine/project_state.py cost <pid>
python3 engine/project_state.py diagnose <pid>
python3 engine/project_state.py close <pid>

# 触发器（Phase 3 每轮必调）
python3 engine/project_state.py trigger-evaluate <pid>
python3 engine/project_state.py trigger-status <pid>
python3 engine/project_state.py focus-list <pid>
python3 engine/project_state.py focus-update <pid> <id> "[x]"

# 工具发现
python3 engine/project_state.py tool-scan "任务描述"
```

---

## tool_discovery.py — 工具发现（标签体系 v2）

```bash
python3 engine/tool_discovery.py scan                  # 扫描本地 Skill
python3 engine/tool_discovery.py report "任务描述"      # 推荐报告（Phase 0 使用）
python3 engine/tool_discovery.py search "关键词"        # 搜索
python3 engine/tool_discovery.py check <skill_path>    # 安全初筛
python3 engine/tool_discovery.py enrich <skill_name>   # 查看某 Skill 的标签
python3 engine/tool_discovery.py --self-test
```

v2 标签体系：domain(12) × capability(8) 双路匹配，OPC 自排除。

---

## trigger_engine.py — Aware 触发器

```bash
python3 engine/trigger_engine.py evaluate <project_dir>
python3 engine/trigger_engine.py status <project_dir>
python3 engine/trigger_engine.py --self-test
```

**CEO 集成规则**：Phase 3 每轮循环调用 `trigger-evaluate`；agent-complete 时自动检查 on_message 触发器（内置）。

---

## diagnose_agent.py — 自动归因

```bash
python3 engine/diagnose_agent.py '{"spawn":"ok","announce":"missing","subagent_status":"done","error_msg":""}'
```

归因层级：`L1-Platform` / `L2-Orchestration` / `L3-BusinessSkill` / `L4-External`

---

## 触发器生命周期

```
项目创建 → 可选：复制 playbook/templates/triggers.yaml 到项目目录
Phase 3 每轮 → trigger-evaluate（检查 once/interval/on_message）
agent-complete → 自动检查 on_message + Focus auto-complete（内置）
项目关闭 → close（自动停用相关触发器）
```
