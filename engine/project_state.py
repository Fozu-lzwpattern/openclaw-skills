#!/usr/bin/env python3
"""
OPC Project State Manager v2.0 — 在 v1.4 基础上扩展 Trigger + Focus + ToolScan 命令

新增命令:
  python3 project_state_v2.py trigger-evaluate <project_id>          # 评估所有触发器
  python3 project_state_v2.py trigger-status <project_id>            # 查看触发器状态
  python3 project_state_v2.py focus-update <project_id> <id> <status>  # 更新焦点状态
  python3 project_state_v2.py focus-list <project_id>                # 列出活跃焦点
  python3 project_state_v2.py tool-scan <task_description>           # 扫描推荐工具

保持所有 v1.4 原有命令不变（init/show/list/agent-start/agent-complete/...）。

使用方式：将此文件替换或合并到原 project_state.py 中。
"""
import json, sys, os, glob
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.expanduser("~/.openclaw/workspace/opc-projects")
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def _now():
    return datetime.now(TZ).isoformat(timespec="seconds")

def _today():
    return datetime.now(TZ).strftime("%Y%m%d")

def _project_dir(pid):
    return os.path.join(BASE_DIR, pid)

def _state_path(pid):
    return os.path.join(_project_dir(pid), "state.json")

def _load(pid):
    p = _state_path(pid)
    if not os.path.exists(p):
        print(f"❌ 项目 {pid} 不存在")
        sys.exit(1)
    with open(p) as f:
        return json.load(f)

def _save(pid, data):
    data["project"]["updatedAt"] = _now()
    d = _project_dir(pid)
    os.makedirs(d, exist_ok=True)
    os.makedirs(os.path.join(d, "outputs"), exist_ok=True)
    os.makedirs(os.path.join(d, "logs"), exist_ok=True)
    with open(_state_path(pid), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════
# v1.4 原有命令（保持不变）
# ═══════════════════════════════════════════════════════════════

def cmd_init(name, date=None):
    date_str = date or _today()
    seq = 1
    while True:
        pid = f"opc-{date_str}-{seq:03d}"
        if not os.path.exists(_project_dir(pid)):
            break
        seq += 1
    data = {
        "project": {
            "id": pid, "name": name,
            "createdAt": _now(), "updatedAt": _now(),
            "currentPhase": "phase_0_init", "status": "created"
        },
        "plan": {}, "agents": {}, "checkpoints": {},
        "cost": {"totalTokens": 0, "byRole": {}, "budgetLimit": 0, "budgetUsedPercent": 0}
    }
    _save(pid, data)
    print(f"✅ 项目初始化: {pid} — {name}")
    print(f"   路径: {_project_dir(pid)}")
    return pid

def cmd_update_phase(pid, phase):
    data = _load(pid)
    old = data["project"]["currentPhase"]
    data["project"]["currentPhase"] = phase
    if phase in ("completed", "cancelled"):
        data["project"]["status"] = phase
    elif phase.startswith("phase_"):
        data["project"]["status"] = "in_progress"
    _save(pid, data)
    print(f"✅ Phase: {old} → {phase}")

def cmd_agent_start(pid, label, meta_json):
    data = _load(pid)
    meta = json.loads(meta_json) if meta_json else {}
    data["agents"][label] = {
        "role": meta.get("role", label), "status": "active",
        "startedAt": _now(), "sessionKey": meta.get("sessionKey", ""),
        "tokens": 0, "output": None, "error": None
    }
    _save(pid, data)
    print(f"✅ Agent started: {label} ({meta.get('role', label)})")

def cmd_agent_complete(pid, label, output_json, tokens=0):
    data = _load(pid)
    if label not in data["agents"]:
        data["agents"][label] = {"role": label, "status": "active", "startedAt": _now(), "tokens": 0}
    agent = data["agents"][label]
    agent["status"] = "completed"
    agent["finishedAt"] = _now()
    agent["output"] = json.loads(output_json) if output_json else {}
    tokens = int(tokens)
    if tokens:
        agent["tokens"] = tokens
        role = agent.get("role", label)
        data["cost"]["byRole"].setdefault(role, 0)
        data["cost"]["byRole"][role] += tokens
        data["cost"]["totalTokens"] += tokens
        if data["cost"]["budgetLimit"] > 0:
            data["cost"]["budgetUsedPercent"] = round(
                data["cost"]["totalTokens"] / data["cost"]["budgetLimit"] * 100, 1)
    data["checkpoints"].pop(label, None)
    _save(pid, data)
    # v2.0: 自动检查 Focus 是否可以 auto-complete
    _check_focus_auto_complete(pid, data)
    print(f"✅ Agent completed: {label} (tokens: {tokens})")

def cmd_agent_fail(pid, label, error_json):
    data = _load(pid)
    if label not in data["agents"]:
        data["agents"][label] = {"role": label, "status": "active", "startedAt": _now(), "tokens": 0}
    agent = data["agents"][label]
    err = json.loads(error_json) if error_json else {}
    agent["status"] = "failed"
    agent["failedAt"] = _now()
    agent["error"] = err.get("error", str(err))
    agent["retryCount"] = agent.get("retryCount", 0) + 1
    _save(pid, data)
    print(f"❌ Agent failed: {label} — {agent['error']}")

def cmd_checkpoint(pid, label, cp_json):
    data = _load(pid)
    cp = json.loads(cp_json) if cp_json else {}
    cp["savedAt"] = _now()
    data["checkpoints"][label] = cp
    _save(pid, data)
    print(f"💾 Checkpoint saved: {label}")

def cmd_checkpoint_get(pid, label):
    data = _load(pid)
    cp = data.get("checkpoints", {}).get(label)
    if not cp:
        print(f"⚠️ 无断点: {label}")
        return
    print(json.dumps(cp, indent=2, ensure_ascii=False))

def cmd_restore(pid):
    data = _load(pid)
    p = data["project"]
    print(f"═══ 项目恢复: {p['id']} ═══")
    print(f"名称: {p['name']}")
    print(f"状态: {p['status']} | 阶段: {p['currentPhase']}")
    print(f"更新: {p['updatedAt']}")
    print("\n── Agent ──")
    for label, ag in data.get("agents", {}).items():
        icon = {"completed":"✅","active":"🔄","failed":"❌"}.get(ag["status"],"❓")
        print(f"  {icon} {label} ({ag.get('role','')}) — {ag['status']}")
    cps = data.get("checkpoints", {})
    if cps:
        print("\n── 断点 ──")
        for label, cp in cps.items():
            print(f"  💾 {label}: steps={cp.get('completedSteps',[])} next={cp.get('nextStep','?')}")
    c = data.get("cost", {})
    if c.get("totalTokens", 0):
        print(f"\n── 成本 ── total: {c['totalTokens']//1000}K tokens")
    return data

def cmd_show(pid=None):
    if pid:
        data = _load(pid)
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        cmd_list()

def cmd_list():
    if not os.path.exists(BASE_DIR):
        print("无项目")
        return
    dirs = sorted(glob.glob(os.path.join(BASE_DIR, "opc-*")))
    if not dirs:
        print("无项目")
        return
    print(f"{'ID':<22} {'Name':<30} {'Phase':<25} {'Status':<12}")
    print("─" * 90)
    for d in dirs:
        sp = os.path.join(d, "state.json")
        if not os.path.exists(sp):
            continue
        with open(sp) as f:
            data = json.load(f)
        p = data["project"]
        print(f"{p['id']:<22} {p['name']:<30} {p['currentPhase']:<25} {p['status']:<12}")

def cmd_cost(pid, add_tokens=None, agent_label=None):
    data = _load(pid)
    if add_tokens:
        tokens = int(add_tokens)
        label = agent_label or "ceo"
        data["cost"]["totalTokens"] += tokens
        data["cost"]["byRole"].setdefault(label, 0)
        data["cost"]["byRole"][label] += tokens
        if data["cost"]["budgetLimit"] > 0:
            data["cost"]["budgetUsedPercent"] = round(
                data["cost"]["totalTokens"] / data["cost"]["budgetLimit"] * 100, 1)
        _save(pid, data)
        print(f"✅ 成本更新: +{tokens} ({label})")
    c = data["cost"]
    total = c["totalTokens"]
    print(f"\n📊 {data['project']['name']} 成本报告")
    print(f"{'Role':<20} {'Tokens':<12} {'Cost':<10}")
    print("─" * 42)
    for role, t in c.get("byRole", {}).items():
        cost = t * 2.5 / 1_000_000
        print(f"{role:<20} {t//1000}K{'':<8} ${cost:.3f}")
    total_cost = total * 2.5 / 1_000_000
    print("─" * 42)
    print(f"{'Total':<20} {total//1000}K{'':<8} ${total_cost:.3f}")

def cmd_close(pid):
    data = _load(pid)
    data["project"]["status"] = "completed"
    data["project"]["currentPhase"] = "completed"
    data["project"]["closedAt"] = _now()
    _save(pid, data)
    print(f"✅ 项目已关闭: {pid}")

def cmd_diagnose(pid):
    data = _load(pid)
    failed = {k:v for k,v in data.get("agents",{}).items() if v["status"] == "failed"}
    if not failed:
        print("✅ 无失败 agent")
        return
    import importlib.util
    diag_path = os.path.join(os.path.dirname(__file__), "diagnose_agent.py")
    if not os.path.exists(diag_path):
        print("⚠️ diagnose_agent.py 未找到，跳过自动归因")
        return
    spec = importlib.util.spec_from_file_location("diagnose_agent", diag_path)
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)
    for label, ag in failed.items():
        print(f"\n{'═'*50}")
        print(f"🔍 归因: {label} ({ag.get('role','')})")
        error = ag.get("error", "")
        symptoms = {"spawn":"ok","announce":"received","output_quality":"error","error_msg":str(error)}
        results = diag.diagnose_multi(symptoms)
        print(diag.format_report(results, symptoms))


# ═══════════════════════════════════════════════════════════════
# v2.0 新增命令
# ═══════════════════════════════════════════════════════════════

def _get_trigger_engine(pid):
    """延迟导入 trigger_engine 模块"""
    trigger_path = os.path.join(SCRIPTS_DIR, "trigger_engine.py")
    if not os.path.exists(trigger_path):
        print(f"❌ trigger_engine.py 未找到: {trigger_path}")
        sys.exit(1)
    import importlib.util
    spec = importlib.util.spec_from_file_location("trigger_engine", trigger_path)
    mod = importlib.util.module_from_spec(spec)
    import sys as _sys
    _sys.modules["trigger_engine"] = mod
    spec.loader.exec_module(mod)
    return mod.TriggerEngine(_project_dir(pid)), mod.FocusManager(_project_dir(pid))

def _get_tool_discovery():
    """延迟导入 tool_discovery 模块"""
    td_path = os.path.join(SCRIPTS_DIR, "tool_discovery.py")
    if not os.path.exists(td_path):
        print(f"❌ tool_discovery.py 未找到: {td_path}")
        sys.exit(1)
    import importlib.util
    spec = importlib.util.spec_from_file_location("tool_discovery", td_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ToolDiscovery()

def _check_focus_auto_complete(pid, data):
    """agent 完成时自动检查 Focus 是否可以 auto-complete"""
    try:
        _, fm = _get_trigger_engine(pid)
        agent_statuses = {
            label: ag["status"]
            for label, ag in data.get("agents", {}).items()
        }
        completed = fm.check_auto_complete(agent_statuses)
        if completed:
            print(f"🎯 Focus 自动完成: {completed}")
    except Exception:
        pass  # 静默失败，不影响核心流程

def cmd_trigger_evaluate(pid):
    """评估项目下所有触发器"""
    engine, _ = _get_trigger_engine(pid)
    actions = engine.evaluate()
    if not actions:
        print("✅ 无待执行动作")
        return
    print(f"🔔 {len(actions)} 个触发器就绪:\n")
    for a in actions:
        print(f"  ▶ {a.trigger_id} — {a.action_type}")
        print(f"    参数: {json.dumps(a.action_params, ensure_ascii=False)}")
        if a.focus_ref:
            print(f"    焦点: {a.focus_ref}")
        print()
    # Also JSON output
    from dataclasses import asdict
    print("--- JSON ---")
    print(json.dumps([asdict(a) for a in actions], ensure_ascii=False, indent=2))

def cmd_trigger_status(pid):
    """查看项目下所有触发器状态"""
    engine, _ = _get_trigger_engine(pid)
    st = engine.status()
    if not st:
        print("无触发器定义")
        return
    print(f"{'ID':<22} {'Type':<12} {'Enabled':<8} {'Fired':<6} {'Count':<6} {'Last Fired':<22}")
    print("─" * 78)
    for tid, info in st.items():
        enabled = "✅" if info["enabled"] else "❌"
        fired = "✓" if info["fired"] else "✗"
        last = info.get("last_fired", "-") or "-"
        print(f"{tid:<22} {info['type']:<12} {enabled:<8} {fired:<6} {info['fire_count']:<6} {last:<22}")

def cmd_focus_update(pid, focus_id, status):
    """更新焦点状态"""
    _, fm = _get_trigger_engine(pid)
    fm.update_status(focus_id, status)

def cmd_focus_list(pid):
    """列出活跃焦点"""
    _, fm = _get_trigger_engine(pid)
    active = fm.get_active_focuses()
    if not active:
        print("无活跃焦点")
        return
    print(f"{'ID':<24} {'Title':<30} {'Status':<8} {'Priority':<8}")
    print("─" * 72)
    for f in active:
        print(f"{f.get('id','?'):<24} {f.get('title',''):<30} {f.get('status','?'):<8} {f.get('priority',''):<8}")

def cmd_tool_scan(task_description):
    """扫描推荐工具"""
    td = _get_tool_discovery()
    report = td.generate_tool_report(task_description)
    print(report)


# ═══════════════════════════════════════════════════════════════
# Main dispatcher
# ═══════════════════════════════════════════════════════════════

USAGE = """
OPC Project State Manager v2.0

v1.4 命令:
  init <name> [date]                    — 初始化项目
  update-phase <pid> <phase>            — 更新阶段
  agent-start <pid> <label> [meta_json] — 注册 agent
  agent-complete <pid> <label> [json] [tokens] — agent 完成
  agent-fail <pid> <label> [error_json] — agent 失败
  checkpoint <pid> <label> [json]       — 保存断点
  checkpoint-get <pid> <label>          — 获取断点
  restore <pid>                         — 恢复项目上下文
  show [pid]                            — 查看项目 / 项目列表
  list                                  — 列出所有项目
  cost <pid> [tokens] [label]           — 成本报告 / 追加成本
  diagnose <pid>                        — 自动归因
  close <pid>                           — 关闭项目

v2.0 新增命令:
  trigger-evaluate <pid>                — 评估所有触发器
  trigger-status <pid>                  — 查看触发器状态
  focus-update <pid> <id> <status>      — 更新焦点状态 ([ ] [/] [x] [!])
  focus-list <pid>                      — 列出活跃焦点
  tool-scan <task_description>          — 扫描推荐工具
"""

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print(USAGE)
        sys.exit(0)

    cmd = args[0]

    # ── v1.4 commands ──
    if cmd == "init":
        cmd_init(args[1] if len(args) > 1 else "unnamed", args[2] if len(args) > 2 else None)
    elif cmd == "update-phase":
        cmd_update_phase(args[1], args[2])
    elif cmd == "agent-start":
        cmd_agent_start(args[1], args[2], args[3] if len(args) > 3 else "{}")
    elif cmd == "agent-complete":
        cmd_agent_complete(args[1], args[2], args[3] if len(args) > 3 else "{}", args[4] if len(args) > 4 else 0)
    elif cmd == "agent-fail":
        cmd_agent_fail(args[1], args[2], args[3] if len(args) > 3 else "{}")
    elif cmd == "checkpoint":
        cmd_checkpoint(args[1], args[2], args[3] if len(args) > 3 else "{}")
    elif cmd == "checkpoint-get":
        cmd_checkpoint_get(args[1], args[2])
    elif cmd == "restore":
        cmd_restore(args[1])
    elif cmd == "show":
        cmd_show(args[1] if len(args) > 1 else None)
    elif cmd == "list":
        cmd_list()
    elif cmd in ("cost", "report"):
        cmd_cost(args[1], args[2] if len(args) > 2 else None, args[3] if len(args) > 3 else None)
    elif cmd == "diagnose":
        cmd_diagnose(args[1])
    elif cmd == "close":
        cmd_close(args[1])

    # ── v2.0 new commands ──
    elif cmd == "trigger-evaluate":
        if len(args) < 2:
            print("用法: trigger-evaluate <project_id>")
            sys.exit(1)
        cmd_trigger_evaluate(args[1])
    elif cmd == "trigger-status":
        if len(args) < 2:
            print("用法: trigger-status <project_id>")
            sys.exit(1)
        cmd_trigger_status(args[1])
    elif cmd == "focus-update":
        if len(args) < 4:
            print("用法: focus-update <project_id> <focus_id> <status>")
            print("  status: [ ] / [/] / [x] / [!]")
            sys.exit(1)
        cmd_focus_update(args[1], args[2], args[3])
    elif cmd == "focus-list":
        if len(args) < 2:
            print("用法: focus-list <project_id>")
            sys.exit(1)
        cmd_focus_list(args[1])
    elif cmd == "tool-scan":
        if len(args) < 2:
            print("用法: tool-scan <task_description>")
            sys.exit(1)
        cmd_tool_scan(" ".join(args[1:]))

    else:
        print(f"未知命令: {cmd}")
        print(USAGE)
        sys.exit(1)
