#!/usr/bin/env python3
"""
OPC Agent Failure Diagnosis — 自动归因工具

根据 agent 的 session history / 状态信息自动判断故障层级：
  L1 = OpenClaw 平台问题（spawn失败/announce丢失/session超时）
  L2 = OPC 编排问题（角色定义不清/prompt歧义/依赖管理错误）
  L3 = 业务 Skill 问题（API报错/认证过期/组件版本/浏览器交互）
  L4 = 外部依赖问题（网络/内部平台不可用）

用法:
  python3 diagnose_agent.py <symptoms_json>
  
示例:
  python3 diagnose_agent.py '{"spawn":"ok","announce":"missing","subagent_status":"done"}'
  python3 diagnose_agent.py '{"spawn":"ok","announce":"received","output_quality":"off_topic"}'
  python3 diagnose_agent.py '{"spawn":"ok","announce":"received","output_quality":"error","error_msg":"CDP connection refused"}'
"""

import json, sys, re

# ─── 归因规则引擎 ───

RULES = [
    # L1: Platform
    {
        "level": "L1",
        "name": "Spawn 失败",
        "condition": lambda s: s.get("spawn") == "error",
        "diagnosis": "OpenClaw 平台无法 spawn sub-agent",
        "action": "检查 OpenClaw 状态(openclaw status)，确认 session 配额未满，尝试重新 spawn"
    },
    {
        "level": "L1",
        "name": "Announce 丢失",
        "condition": lambda s: s.get("spawn") == "ok" and s.get("announce") == "missing" and s.get("subagent_status") == "done",
        "diagnosis": "Sub-agent 已完成(done)但 announce 未到达 Main Session",
        "action": "已知平台问题。用 sessions_history 主动拉取结果；后续所有 spawn 都要加超时检查"
    },
    {
        "level": "L1",
        "name": "Session 超时",
        "condition": lambda s: s.get("subagent_status") == "timeout" or s.get("spawn") == "timeout",
        "diagnosis": "Sub-agent session 超时退出",
        "action": "增加 runTimeoutSeconds；检查任务是否过于复杂需要拆分"
    },
    {
        "level": "L1",
        "name": "Session 异常终止",
        "condition": lambda s: s.get("subagent_status") == "error" and not s.get("error_msg"),
        "diagnosis": "Sub-agent 异常终止，无错误信息",
        "action": "检查 sessions_history 获取最后几条消息；可能是 context 溢出或 model 问题"
    },
    # L2: Orchestration
    {
        "level": "L2",
        "name": "产出完全跑偏",
        "condition": lambda s: s.get("output_quality") == "off_topic",
        "diagnosis": "Sub-agent 完成了任务但产出与预期完全不符",
        "action": "角色卡定义不清或 task prompt 歧义。优化：1)明确角色职责边界 2)给出具体产出示例 3)增加约束条件"
    },
    {
        "level": "L2",
        "name": "产出方向对但质量差",
        "condition": lambda s: s.get("output_quality") == "low_quality",
        "diagnosis": "产出方向正确但深度/格式/完整性不够",
        "action": "1)task描述增加详细要求 2)考虑使用更强model 3)Persona Priming注入专家方法论"
    },
    {
        "level": "L2",
        "name": "产出格式不符",
        "condition": lambda s: s.get("output_quality") == "wrong_format",
        "diagnosis": "产出内容OK但格式不符合 OPC 规范",
        "action": "在 task prompt 中增加明确的产出格式示例和 JSON Schema"
    },
    {
        "level": "L2",
        "name": "依赖任务未完成就启动",
        "condition": lambda s: s.get("dependency_error") == True,
        "diagnosis": "上游任务未完成就 spawn 了下游 agent",
        "action": "检查编排流程中的依赖检查逻辑，确保串行依赖严格等待"
    },
    # L3: Business Skill
    {
        "level": "L3",
        "name": "API/认证错误",
        "condition": lambda s: s.get("error_msg") and any(kw in s["error_msg"].lower() for kw in 
            ["auth", "401", "403", "token", "cookie", "sso", "login", "credential", "认证", "登录", "过期", "授权"]),
        "diagnosis": "业务 API 认证失败或过期",
        "action": "1)检查 SSO cookie/token 是否过期 2)重新执行认证流程 3)确认 MOA 登录状态"
    },
    {
        "level": "L3",
        "name": "浏览器交互失败",
        "condition": lambda s: s.get("error_msg") and any(kw in s["error_msg"].lower() for kw in
            ["cdp", "browser", "click", "selector", "element", "timeout", "date", "picker", "mouse", "tab", "日期", "选择器", "超时", "浏览器", "点击", "交互"]),
        "diagnosis": "浏览器自动化交互失败（CDP/选择器/元素定位）",
        "action": "1)检查浏览器是否正常运行(curl localhost:9222) 2)Tab竞争？串行化操作 3)元素定位变化？更新选择器"
    },
    {
        "level": "L3",
        "name": "组件版本/配置错误",
        "condition": lambda s: s.get("error_msg") and any(kw in s["error_msg"].lower() for kw in
            ["component", "version", "snapshot", "props", "schema", "validate", "组件", "版本", "配置"]),
        "diagnosis": "高达组件版本不匹配或配置参数错误",
        "action": "1)检查 components-index.json 版本 2)用 query_components.py 验证最新版本 3)检查 props 格式"
    },
    {
        "level": "L3",
        "name": "脚本执行错误",
        "condition": lambda s: s.get("error_msg") and any(kw in s["error_msg"].lower() for kw in
            ["script", "node", "python", "syntax", "import", "module", "traceback"]),
        "diagnosis": "业务脚本执行报错",
        "action": "检查脚本输出日志，定位具体报错行；可能是环境依赖缺失或参数传递错误"
    },
    # L4: External
    {
        "level": "L4",
        "name": "网络/外部服务不可用",
        "condition": lambda s: s.get("error_msg") and any(kw in s["error_msg"].lower() for kw in
            ["network", "dns", "connection refused", "unreachable", "502", "503", "504", "econnreset", "网络", "连接"]),
        "diagnosis": "外部网络或服务不可用",
        "action": "1)检查网络连通性 2)确认目标服务状态 3)等待恢复后重试"
    },
    # Catch-all
    {
        "level": "L?",
        "name": "未知错误",
        "condition": lambda s: True,
        "diagnosis": "无法自动归因",
        "action": "手动检查 sessions_history 获取详细日志，人工归因"
    }
]

def diagnose(symptoms: dict) -> dict:
    """对 symptoms 运行规则引擎，返回第一个匹配的诊断"""
    for rule in RULES:
        try:
            if rule["condition"](symptoms):
                return {
                    "level": rule["level"],
                    "name": rule["name"],
                    "diagnosis": rule["diagnosis"],
                    "action": rule["action"],
                    "symptoms": symptoms
                }
        except Exception:
            continue
    return {"level": "L?", "name": "未知", "diagnosis": "无法诊断", "action": "人工检查", "symptoms": symptoms}

def diagnose_multi(symptoms: dict) -> list:
    """返回所有匹配的诊断（不含 catch-all）"""
    results = []
    for rule in RULES:
        if rule["name"] == "未知错误":
            continue
        try:
            if rule["condition"](symptoms):
                results.append({
                    "level": rule["level"],
                    "name": rule["name"],
                    "diagnosis": rule["diagnosis"],
                    "action": rule["action"]
                })
        except Exception:
            continue
    if not results:
        results.append(diagnose(symptoms))
    return results

def format_report(results: list, symptoms: dict) -> str:
    lines = ["═══ OPC 故障诊断报告 ═══", ""]
    lines.append(f"症状: {json.dumps(symptoms, ensure_ascii=False)}")
    lines.append("")
    for i, r in enumerate(results, 1):
        icon = {"L1":"🔴","L2":"🟡","L3":"🟠","L4":"⚪"}.get(r["level"],"❓")
        lines.append(f"诊断 {i}: {icon} [{r['level']}] {r['name']}")
        lines.append(f"  原因: {r['diagnosis']}")
        lines.append(f"  建议: {r['action']}")
        lines.append("")
    return "\n".join(lines)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    symptoms = json.loads(sys.argv[1])
    results = diagnose_multi(symptoms)
    print(format_report(results, symptoms))
