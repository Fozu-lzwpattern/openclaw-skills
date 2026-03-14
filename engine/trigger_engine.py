#!/usr/bin/env python3
"""
OPC Aware 触发器引擎 — 声明式事件驱动系统 + Focus 焦点管理

用法:
  python3 trigger_engine.py evaluate <project_dir>   # 评估所有触发器，返回应执行的动作
  python3 trigger_engine.py status <project_dir>     # 查看所有触发器状态
  python3 trigger_engine.py fire <project_dir> <id>  # 手动触发指定触发器
  python3 trigger_engine.py focus-list <project_dir>         # 列出活跃焦点
  python3 trigger_engine.py focus-update <project_dir> <id> <status>  # 更新焦点状态
  python3 trigger_engine.py --help                   # 显示帮助

trigger 状态持久化到 <project_dir>/trigger_state.json
focus 定义在 <project_dir>/focus.yaml
triggers 定义在 <project_dir>/triggers.yaml

Python 3.9+, 仅标准库 (yaml 可选, 内置 fallback)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

TZ = timezone(timedelta(hours=8))

# ──────────────────────────── YAML helper ────────────────────────────
# Try pyyaml first; fall back to a minimal safe loader for simple structures.

try:
    import yaml as _yaml

    def _load_yaml(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return _yaml.safe_load(f) or {}

    def _dump_yaml(data: dict, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            _yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

except ImportError:
    # Minimal fallback: parse flat YAML via json round-trip won't work for
    # nested structures, so we shell out to python -c … or accept JSON.
    def _load_yaml(path: str) -> dict:
        """Very thin YAML subset loader (handles the trigger/focus schemas)."""
        import ast
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # Strip comments
        lines = []
        for line in text.splitlines():
            stripped = line.split("#")[0].rstrip() if "#" in line else line.rstrip()
            lines.append(stripped)
        # Try JSON first (triggers.yaml written by us may be JSON-compat)
        clean = "\n".join(lines)
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass
        # Last resort: try ast.literal_eval on a dict-like structure
        raise RuntimeError(
            f"无法解析 {path}: 请安装 PyYAML (pip install pyyaml) 或使用 JSON 格式"
        )

    def _dump_yaml(data: dict, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def _now() -> datetime:
    return datetime.now(TZ)


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _parse_dt(s: str) -> Optional[datetime]:
    """Parse ISO 8601 datetime string, tolerating missing tz."""
    if not s:
        return None
    try:
        # Python 3.11+ has datetime.fromisoformat for full ISO; older needs fixup
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


# ──────────────────────────── Data classes ────────────────────────────

@dataclass
class TriggerAction:
    """evaluate() 返回的待执行动作"""
    trigger_id: str
    action_type: str        # spawn_agent / notify / run_script
    action_params: dict     # agent_label+task / target+message / command
    focus_ref: Optional[str] = None


# ──────────────────────────── Trigger Engine ────────────────────────────

class TriggerEngine:
    """OPC Aware 触发器引擎 — 声明式事件驱动系统"""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.triggers: list[dict] = []
        self.state: dict[str, dict] = {}  # trigger_id -> {last_fired, fire_count, ...}
        self._state_path = self.project_dir / "trigger_state.json"
        self._triggers_path = self.project_dir / "triggers.yaml"

        self._load_state()
        if self._triggers_path.exists():
            self.load(str(self._triggers_path))

    # ─── load / save ───

    def load(self, triggers_path: str) -> None:
        """解析 triggers.yaml"""
        try:
            data = _load_yaml(triggers_path)
        except Exception as e:
            print(f"⚠️ 触发器配置加载失败: {e}")
            return
        self.triggers = data.get("triggers", [])
        # Ensure each trigger has an id
        for i, t in enumerate(self.triggers):
            if "id" not in t:
                t["id"] = f"trigger-{i}"

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.state = {}

    def _save_state(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)

    # ─── evaluate ───

    def evaluate(self) -> list[TriggerAction]:
        """评估所有触发器，返回应执行的动作列表。
        在 heartbeat 或 CEO 检查时调用。
        """
        actions: list[TriggerAction] = []
        for t in self.triggers:
            if not t.get("enabled", True):
                continue
            tid = t["id"]
            ttype = t.get("type", "")

            should_fire = False
            try:
                if ttype == "cron":
                    # cron triggers are registered externally; evaluate just reports status
                    should_fire = False
                elif ttype == "once":
                    should_fire = self.check_once(t)
                elif ttype == "interval":
                    should_fire = self.check_interval(t)
                elif ttype == "on_message":
                    should_fire = self.check_on_message(t)
                elif ttype == "poll":
                    should_fire = self.check_poll(t)
                else:
                    print(f"⚠️ 未知触发器类型: {ttype} (id={tid})")
            except Exception as e:
                print(f"⚠️ 触发器 {tid} 评估异常: {e}")
                continue

            if should_fire:
                action = self._build_action(t)
                if action:
                    actions.append(action)
                    self.mark_fired(tid)

        self._save_state()
        return actions

    def _build_action(self, t: dict) -> Optional[TriggerAction]:
        act = t.get("action", {})
        return TriggerAction(
            trigger_id=t["id"],
            action_type=act.get("type", "unknown"),
            action_params={k: v for k, v in act.items() if k != "type"},
            focus_ref=t.get("focus_ref"),
        )

    # ─── type checkers ───

    def check_once(self, trigger: dict) -> bool:
        """once 类型：检查是否到达指定时间且未触发过"""
        tid = trigger["id"]
        # Already fired?
        if trigger.get("fired", False):
            return False
        ts = self.state.get(tid, {})
        if ts.get("fired", False):
            return False

        at_str = trigger.get("at", "")
        target_dt = _parse_dt(at_str)
        if not target_dt:
            return False
        return _now() >= target_dt

    def check_interval(self, trigger: dict) -> bool:
        """interval 类型：检查距上次执行是否超过指定间隔"""
        tid = trigger["id"]
        every_min = trigger.get("every_minutes", 0)
        if every_min <= 0:
            return False

        ts = self.state.get(tid, {})
        last_str = ts.get("last_fired") or trigger.get("last_fired")
        if not last_str:
            # Never fired → fire now
            return True

        last_dt = _parse_dt(last_str)
        if not last_dt:
            return True
        elapsed = (_now() - last_dt).total_seconds() / 60.0
        return elapsed >= every_min

    def check_on_message(self, trigger: dict) -> bool:
        """on_message 类型：检查是否有匹配的 agent 消息。
        实际调用 `subagents list` 获取最近完成的 agent，匹配关键词。
        """
        tid = trigger["id"]
        # Respect max_fires
        max_fires = trigger.get("max_fires", 0)
        if max_fires > 0:
            fire_count = self.state.get(tid, {}).get("fire_count", 0)
            if fire_count >= max_fires:
                return False

        contains = trigger.get("contains", "")
        match_mode = trigger.get("match_mode", "contains")
        from_agent = trigger.get("from_agent", "")

        # Call subagents list (CLI)
        try:
            result = subprocess.run(
                ["openclaw", "subagents", "list", "--recent", "30"],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Fallback: cannot check, skip
            return False

        if not output:
            return False

        # Simple line-by-line check
        for line in output.splitlines():
            # Filter by from_agent label if specified
            if from_agent and from_agent not in line:
                continue
            if _match_text(line, contains, match_mode):
                return True
        return False

    def check_poll(self, trigger: dict) -> bool:
        """poll 类型：HTTP 轮询外部状态"""
        tid = trigger["id"]

        # Check interval
        interval_min = trigger.get("interval_minutes", 5)
        ts = self.state.get(tid, {})
        last_str = ts.get("last_fired") or ts.get("last_polled")
        if last_str:
            last_dt = _parse_dt(last_str)
            if last_dt and (_now() - last_dt).total_seconds() / 60.0 < interval_min:
                return False  # Not time yet

        # Check timeout
        timeout_min = trigger.get("timeout_minutes", 0)
        if timeout_min > 0:
            started_str = ts.get("started_at", _now_iso())
            if "started_at" not in ts:
                ts["started_at"] = started_str
                self.state[tid] = ts
            started_dt = _parse_dt(started_str)
            if started_dt and (_now() - started_dt).total_seconds() / 60.0 > timeout_min:
                print(f"⏱️ poll 触发器 {tid} 已超时 ({timeout_min}min)")
                return False

        url = trigger.get("url", "")
        check_path = trigger.get("check_path", "")
        expected = trigger.get("expected", "")

        if not url:
            return False

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "OPC-TriggerEngine/2.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
            print(f"⚠️ poll {tid} 请求失败: {e}")
            # Record poll time even on failure
            self.state.setdefault(tid, {})["last_polled"] = _now_iso()
            self._save_state()
            return False

        # Record poll time
        self.state.setdefault(tid, {})["last_polled"] = _now_iso()

        # Navigate check_path (e.g. "workflow_runs[0].conclusion")
        value = _navigate_json(data, check_path)
        return str(value) == str(expected)

    def register_cron(self, trigger: dict) -> None:
        """注册 cron 类型触发器 → 调用 openclaw cron create"""
        tid = trigger.get("id", "unknown")
        schedule = trigger.get("schedule", "")
        tz = trigger.get("timezone", "Asia/Shanghai")
        action = trigger.get("action", {})

        if not schedule:
            print(f"⚠️ cron 触发器 {tid} 缺少 schedule")
            return

        # Build the cron command based on action type
        act_type = action.get("type", "")
        if act_type == "spawn_agent":
            label = action.get("agent_label", tid)
            task = action.get("task", "")
            cmd = f'openclaw sessions spawn --label "{label}" --task "{task}"'
        elif act_type == "notify":
            target = action.get("target", "")
            message = action.get("message", "")
            cmd = f'openclaw message send --target "{target}" --message "{message}"'
        elif act_type == "run_script":
            cmd = action.get("command", "echo 'no command'")
        else:
            print(f"⚠️ cron 触发器 {tid}: 不支持的 action type '{act_type}'")
            return

        # Call openclaw cron create
        cron_cmd = [
            "openclaw", "cron", "create",
            "--schedule", schedule,
            "--tz", tz,
            "--command", cmd,
            "--label", f"opc-trigger-{tid}",
        ]
        try:
            result = subprocess.run(cron_cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"✅ cron 触发器已注册: {tid} ({schedule})")
                self.state.setdefault(tid, {})["cron_registered"] = True
                self._save_state()
            else:
                print(f"❌ cron 注册失败: {tid}\n{result.stderr}")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            print(f"❌ cron 注册异常: {tid} — {e}")

    # ─── mark / status ───

    def mark_fired(self, trigger_id: str) -> None:
        """标记触发器已执行（记录时间戳，防止重复触发）"""
        ts = self.state.setdefault(trigger_id, {})
        ts["last_fired"] = _now_iso()
        ts["fire_count"] = ts.get("fire_count", 0) + 1
        ts["fired"] = True
        self._save_state()

    def status(self) -> dict:
        """返回所有触发器的状态"""
        result = {}
        for t in self.triggers:
            tid = t["id"]
            ts = self.state.get(tid, {})
            result[tid] = {
                "type": t.get("type", "?"),
                "enabled": t.get("enabled", True),
                "focus_ref": t.get("focus_ref"),
                "last_fired": ts.get("last_fired"),
                "fire_count": ts.get("fire_count", 0),
                "fired": ts.get("fired", False),
            }
        return result


# ──────────────────────────── Focus Manager ────────────────────────────

class FocusManager:
    """Focus 系统 — 项目焦点自适应管理"""

    VALID_STATUS = {"[ ]", "[/]", "[x]", "[!]"}

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.focus_items: list[dict] = []
        self._focus_path = self.project_dir / "focus.yaml"
        if self._focus_path.exists():
            self._load()

    def _load(self) -> None:
        try:
            data = _load_yaml(str(self._focus_path))
            self.focus_items = data.get("focus_items", [])
        except Exception as e:
            print(f"⚠️ focus.yaml 加载失败: {e}")

    def _save(self) -> None:
        data = {"version": "1.0", "focus_items": self.focus_items}
        _dump_yaml(data, str(self._focus_path))

    def update_status(self, focus_id: str, status: str) -> None:
        """更新 focus 状态: [ ] / [/] / [x] / [!]"""
        if status not in self.VALID_STATUS:
            print(f"⚠️ 无效状态 '{status}'，有效值: {self.VALID_STATUS}")
            return
        for item in self.focus_items:
            if item.get("id") == focus_id:
                old = item.get("status", "?")
                item["status"] = status
                if status == "[x]":
                    item["completed"] = _now_iso()
                self._save()
                print(f"✅ Focus '{focus_id}': {old} → {status}")
                return
        print(f"⚠️ Focus '{focus_id}' 不存在")

    def check_auto_complete(self, agent_statuses: dict[str, str] | None = None) -> list[str]:
        """检查是否所有关联 agent 完成 → 自动标记 focus [x]
        agent_statuses: {label: status} 从 project_state 获取
        返回自动完成的 focus id 列表
        """
        if not agent_statuses:
            return []

        completed_focuses: list[str] = []
        for item in self.focus_items:
            if item.get("status") in ("[x]", "[!]"):
                continue
            if not item.get("auto_complete", False):
                continue
            agents = item.get("agents", [])
            if not agents:
                continue
            # All agents completed?
            all_done = all(
                agent_statuses.get(a) == "completed" for a in agents
            )
            if all_done:
                item["status"] = "[x]"
                item["completed"] = _now_iso()
                completed_focuses.append(item["id"])
                print(f"🎯 Focus '{item['id']}' 自动完成 — 所有 agent 已交付")
                # Handle recurring reset
                if item.get("recurring", False):
                    item["status"] = "[ ]"
                    item["completed"] = None
                    print(f"🔄 循环焦点 '{item['id']}' 已重置为 [ ]")

        if completed_focuses:
            self._save()
        return completed_focuses

    def get_active_focuses(self) -> list[dict]:
        """获取活跃焦点列表（非 [x] 状态）"""
        return [f for f in self.focus_items if f.get("status") != "[x]"]

    def get_triggers_for_focus(self, focus_id: str) -> list[str]:
        """获取某 focus 关联的 trigger id 列表"""
        for item in self.focus_items:
            if item.get("id") == focus_id:
                return item.get("triggers", [])
        return []


# ──────────────────────────── Utilities ────────────────────────────

def _match_text(text: str, pattern: str, mode: str) -> bool:
    """匹配文本：contains / regex / exact"""
    if not pattern:
        return False
    if mode == "exact":
        return text.strip() == pattern.strip()
    elif mode == "regex":
        try:
            return bool(re.search(pattern, text))
        except re.error:
            return False
    else:  # contains
        return pattern in text


def _navigate_json(data: Any, path: str) -> Any:
    """Navigate a dot/bracket path in JSON data.
    e.g. "workflow_runs[0].conclusion"
    """
    if not path:
        return data
    # Split by dots, then handle [N]
    parts: list[str] = []
    for segment in path.split("."):
        # Handle array index: segment[0] → segment, 0
        m = re.match(r"^(\w+)\[(\d+)\]$", segment)
        if m:
            parts.append(m.group(1))
            parts.append(f"[{m.group(2)}]")
        else:
            parts.append(segment)

    current = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if isinstance(current, list) and 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


# ──────────────────────────── CLI ────────────────────────────

def _print_status(engine: TriggerEngine) -> None:
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


def _print_actions(actions: list[TriggerAction]) -> None:
    if not actions:
        print("✅ 无待执行动作")
        return
    print(f"🔔 {len(actions)} 个触发器就绪:\n")
    for a in actions:
        print(f"  ▶ {a.trigger_id}")
        print(f"    类型: {a.action_type}")
        print(f"    参数: {json.dumps(a.action_params, ensure_ascii=False)}")
        if a.focus_ref:
            print(f"    焦点: {a.focus_ref}")
        print()


def _print_focuses(fm: FocusManager) -> None:
    active = fm.get_active_focuses()
    if not active:
        print("无活跃焦点")
        return
    print(f"{'ID':<24} {'Title':<30} {'Status':<8} {'Priority':<8}")
    print("─" * 72)
    for f in active:
        print(f"{f.get('id','?'):<24} {f.get('title',''):<30} {f.get('status','?'):<8} {f.get('priority',''):<8}")


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in ("--help", "-h"):
        print(__doc__)
        sys.exit(0)

    cmd = args[0]

    if cmd == "evaluate":
        if len(args) < 2:
            print("用法: trigger_engine.py evaluate <project_dir>")
            sys.exit(1)
        engine = TriggerEngine(args[1])
        actions = engine.evaluate()
        _print_actions(actions)
        # Also output JSON for programmatic use
        if actions:
            print("\n--- JSON ---")
            print(json.dumps([asdict(a) for a in actions], ensure_ascii=False, indent=2))

    elif cmd == "status":
        if len(args) < 2:
            print("用法: trigger_engine.py status <project_dir>")
            sys.exit(1)
        engine = TriggerEngine(args[1])
        _print_status(engine)

    elif cmd == "fire":
        if len(args) < 3:
            print("用法: trigger_engine.py fire <project_dir> <trigger_id>")
            sys.exit(1)
        engine = TriggerEngine(args[1])
        tid = args[2]
        # Find and build action
        found = False
        for t in engine.triggers:
            if t["id"] == tid:
                action = engine._build_action(t)
                engine.mark_fired(tid)
                print(f"🔥 手动触发: {tid}")
                if action:
                    print(f"   动作: {action.action_type}")
                    print(f"   参数: {json.dumps(action.action_params, ensure_ascii=False)}")
                found = True
                break
        if not found:
            print(f"❌ 触发器 '{tid}' 不存在")
            sys.exit(1)

    elif cmd == "focus-list":
        if len(args) < 2:
            print("用法: trigger_engine.py focus-list <project_dir>")
            sys.exit(1)
        fm = FocusManager(args[1])
        _print_focuses(fm)

    elif cmd == "focus-update":
        if len(args) < 4:
            print("用法: trigger_engine.py focus-update <project_dir> <focus_id> <status>")
            print("  status: [ ] / [/] / [x] / [!]")
            sys.exit(1)
        fm = FocusManager(args[1])
        fm.update_status(args[2], args[3])

    else:
        print(f"未知命令: {cmd}")
        print("可用命令: evaluate | status | fire | focus-list | focus-update")
        print("使用 --help 查看完整帮助")
        sys.exit(1)


# ──────────────────────────── Self-test ────────────────────────────

def _self_test() -> None:
    """基本自测：创建临时项目目录，写入测试 triggers/focus，验证引擎"""
    import tempfile
    import shutil

    print("🧪 运行自测...\n")
    tmpdir = tempfile.mkdtemp(prefix="opc-trigger-test-")
    try:
        # Write test triggers.yaml as JSON (works with fallback loader)
        triggers_data = {
            "version": "1.0",
            "triggers": [
                {
                    "id": "test-once",
                    "type": "once",
                    "at": "2020-01-01T00:00:00+08:00",  # Past → should fire
                    "action": {"type": "notify", "target": "test", "message": "测试消息"},
                    "enabled": True,
                    "fired": False,
                },
                {
                    "id": "test-interval",
                    "type": "interval",
                    "every_minutes": 1,
                    "action": {"type": "run_script", "command": "echo hello"},
                    "enabled": True,
                },
                {
                    "id": "test-disabled",
                    "type": "once",
                    "at": "2020-01-01T00:00:00+08:00",
                    "action": {"type": "notify", "target": "x", "message": "x"},
                    "enabled": False,
                },
            ],
        }

        # Write as JSON (compatible with both loaders)
        triggers_path = os.path.join(tmpdir, "triggers.yaml")
        with open(triggers_path, "w") as f:
            json.dump(triggers_data, f, indent=2)

        # Write test focus.yaml
        focus_data = {
            "version": "1.0",
            "focus_items": [
                {
                    "id": "test-focus",
                    "title": "测试焦点",
                    "status": "[/]",
                    "priority": "P0",
                    "agents": ["agent-a", "agent-b"],
                    "auto_complete": True,
                },
            ],
        }
        focus_path = os.path.join(tmpdir, "focus.yaml")
        with open(focus_path, "w") as f:
            json.dump(focus_data, f, indent=2)

        # Test TriggerEngine
        engine = TriggerEngine(tmpdir)
        assert len(engine.triggers) == 3, f"Expected 3 triggers, got {len(engine.triggers)}"
        print("  ✅ 触发器加载: 3 条")

        actions = engine.evaluate()
        # test-once (past, should fire) + test-interval (never fired, should fire)
        # test-disabled should NOT fire
        action_ids = {a.trigger_id for a in actions}
        assert "test-once" in action_ids, "test-once should fire"
        assert "test-interval" in action_ids, "test-interval should fire"
        assert "test-disabled" not in action_ids, "disabled trigger should not fire"
        print(f"  ✅ evaluate: {len(actions)} 个动作触发 (once + interval)")

        # Status check
        st = engine.status()
        assert st["test-once"]["fired"] is True
        assert st["test-disabled"]["fire_count"] == 0
        print("  ✅ 状态持久化正常")

        # Re-evaluate: once should not fire again
        actions2 = engine.evaluate()
        once_fired_again = any(a.trigger_id == "test-once" for a in actions2)
        assert not once_fired_again, "once trigger should not fire again"
        print("  ✅ once 触发器不重复触发")

        # Test FocusManager
        fm = FocusManager(tmpdir)
        assert len(fm.focus_items) == 1
        active = fm.get_active_focuses()
        assert len(active) == 1
        print("  ✅ Focus 加载: 1 条活跃焦点")

        # Auto-complete: only agent-a done
        completed = fm.check_auto_complete({"agent-a": "completed", "agent-b": "active"})
        assert len(completed) == 0
        print("  ✅ 部分完成 → 不自动关闭")

        # Auto-complete: both done
        completed = fm.check_auto_complete({"agent-a": "completed", "agent-b": "completed"})
        assert "test-focus" in completed
        print("  ✅ 全部完成 → 自动标记 [x]")

        # Status update
        fm2 = FocusManager(tmpdir)
        fm2.update_status("test-focus", "[!]")

        print("\n✅ 所有自测通过!")

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-test":
        _self_test()
    else:
        main()
