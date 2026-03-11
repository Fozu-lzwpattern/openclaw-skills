#!/usr/bin/env python3
"""
OPC Project State Manager — 持久化项目状态，防 compaction 丢失

用法:
  python3 project_state.py init <name> [date]
  python3 project_state.py update-phase <project_id> <phase>
  python3 project_state.py agent-start <project_id> <agent_label> '{"role":"..."}'
  python3 project_state.py agent-complete <project_id> <agent_label> '{"output":...}' [tokens]
  python3 project_state.py agent-fail <project_id> <agent_label> '{"error":"..."}'
  python3 project_state.py checkpoint <project_id> <agent_label> '{"completedSteps":[...],"context":{...}}'
  python3 project_state.py checkpoint-get <project_id> <agent_label>
  python3 project_state.py restore <project_id>
  python3 project_state.py show [project_id]
  python3 project_state.py list
  python3 project_state.py cost <project_id> [add_tokens agent_label]
  python3 project_state.py close <project_id>
"""
import json, sys, os, glob
from datetime import datetime, timezone, timedelta

TZ = timezone(timedelta(hours=8))
BASE_DIR = os.path.expanduser("~/.openclaw/workspace/opc-projects")

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

# ─────────────────── commands ───────────────────

def cmd_init(name, date=None):
    date_str = date or _today()
    # Auto-increment: opc-20260311-001, -002, ...
    seq = 1
    while True:
        pid = f"opc-{date_str}-{seq:03d}"
        if not os.path.exists(_project_dir(pid)):
            break
        seq += 1

    data = {
        "project": {
            "id": pid,
            "name": name,
            "createdAt": _now(),
            "updatedAt": _now(),
            "currentPhase": "phase_0_init",
            "status": "created"
        },
        "plan": {},
        "agents": {},
        "checkpoints": {},
        "cost": {
            "totalTokens": 0,
            "byRole": {},
            "budgetLimit": 0,
            "budgetUsedPercent": 0
        }
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
        "role": meta.get("role", label),
        "status": "active",
        "startedAt": _now(),
        "sessionKey": meta.get("sessionKey", ""),
        "tokens": 0,
        "output": None,
        "error": None
    }
    _save(pid, data)
    print(f"✅ Agent started: {label} ({meta.get('role', label)})")

def cmd_agent_complete(pid, label, output_json, tokens=0):
    data = _load(pid)
    if label not in data["agents"]:
        print(f"⚠️ Agent {label} 不在项目中，自动注册")
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
    # 清除该 agent 的 checkpoint
    data["checkpoints"].pop(label, None)
    _save(pid, data)
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
    print(f"   completedSteps: {cp.get('completedSteps', [])}")

def cmd_checkpoint_get(pid, label):
    data = _load(pid)
    cp = data.get("checkpoints", {}).get(label)
    if not cp:
        print(f"⚠️ 无断点: {label}")
        return
    print(json.dumps(cp, indent=2, ensure_ascii=False))

def cmd_restore(pid):
    """输出项目状态摘要，供 CEO compaction 后恢复上下文"""
    data = _load(pid)
    p = data["project"]
    print(f"═══ 项目恢复: {p['id']} ═══")
    print(f"名称: {p['name']}")
    print(f"状态: {p['status']}")
    print(f"当前阶段: {p['currentPhase']}")
    print(f"更新时间: {p['updatedAt']}")
    print()
    print("── Agent 状态 ──")
    for label, ag in data.get("agents", {}).items():
        status_icon = {"completed":"✅","active":"🔄","failed":"❌"}.get(ag["status"],"❓")
        print(f"  {status_icon} {label} ({ag.get('role','')}) — {ag['status']}")
        if ag.get("output"):
            out_str = json.dumps(ag["output"], ensure_ascii=False)
            if len(out_str) > 120:
                out_str = out_str[:120] + "..."
            print(f"     产出: {out_str}")
        if ag.get("error"):
            print(f"     错误: {ag['error']}")
    print()
    # 断点
    cps = data.get("checkpoints", {})
    if cps:
        print("── 断点 ──")
        for label, cp in cps.items():
            print(f"  💾 {label}: steps={cp.get('completedSteps',[])} nextStep={cp.get('nextStep','?')}")
        print()
    # 成本
    c = data.get("cost", {})
    if c.get("totalTokens", 0) > 0:
        print(f"── 成本 ── (total: {c['totalTokens']//1000}K tokens)")
        for role, tokens in c.get("byRole", {}).items():
            print(f"  {role}: {tokens//1000}K")
    print()
    # 待执行
    pending = [l for l, a in data.get("agents", {}).items() if a["status"] in ("active", "failed")]
    if pending:
        print(f"⚠️ 未完成/失败的 agent: {pending}")
    completed_all = all(a["status"] == "completed" for a in data.get("agents", {}).values())
    if data.get("agents") and completed_all:
        print("✅ 所有 agent 已完成，可进入交付阶段")
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
    # 输出成本报告
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
    if c["budgetLimit"] > 0:
        print(f"预算: {c['budgetLimit']//1000}K ({c['budgetUsedPercent']}% used)")

def cmd_close(pid):
    data = _load(pid)
    data["project"]["status"] = "completed"
    data["project"]["currentPhase"] = "completed"
    data["project"]["closedAt"] = _now()
    _save(pid, data)
    print(f"✅ 项目已关闭: {pid}")

# ─────────────────── main ───────────────────

# ─────────────────── diagnose (集成自动归因) ───────────────────

def cmd_diagnose(pid):
    """自动归因：分析项目中失败的 agent"""
    data = _load(pid)
    failed = {k:v for k,v in data.get("agents",{}).items() if v["status"] == "failed"}
    if not failed:
        print("✅ 无失败 agent")
        return
    
    # 导入归因引擎
    import importlib.util, os
    diag_path = os.path.join(os.path.dirname(__file__), "diagnose_agent.py")
    spec = importlib.util.spec_from_file_location("diagnose_agent", diag_path)
    diag = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diag)
    
    for label, ag in failed.items():
        print(f"\n{'═'*50}")
        print(f"🔍 归因: {label} ({ag.get('role','')})")
        print(f"{'═'*50}")
        
        # 构建症状
        error = ag.get("error", "")
        symptoms = {
            "spawn": "ok",
            "announce": "received",
            "output_quality": "error",
            "error_msg": str(error)
        }
        
        results = diag.diagnose_multi(symptoms)
        print(diag.format_report(results, symptoms))
        
        # 检查是否有断点
        cp = data.get("checkpoints", {}).get(label)
        if cp:
            print(f"💾 有断点可用: steps={cp.get('completedSteps',[])} nextStep={cp.get('nextStep','?')}")
        else:
            print(f"⚠️ 无断点，需要完整重试")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    cmd = args[0]
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
    elif cmd == "cost":
        cmd_cost(args[1], args[2] if len(args) > 2 else None, args[3] if len(args) > 3 else None)
    elif cmd == "report":
        cmd_cost(args[1], args[2] if len(args) > 2 else None, args[3] if len(args) > 3 else None)
    elif cmd == "diagnose":
        cmd_diagnose(args[1])
    elif cmd == "close":
        cmd_close(args[1])
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)
