# 运行时工具自发现机制设计文档

> OPC v2.0 核心新增 — 任务启动前自动发现可用工具，弥补能力缺口

## 概述

工具自发现系统在 CEO 规划任务时自动扫描可用 Skill，将任务需求与工具能力匹配，生成推荐报告。目标：**永远不要因为"不知道有这个工具"而手动操作**。

## 工具发现流程

```
CEO 收到任务
    ↓
Phase 0: 工具扫描
    ├── 1. 扫描本地已安装 Skill
    ├── 2. 任务描述 ↔ Skill 描述 关键词匹配
    ├── 3. 生成匹配报告
    └── 4. 如有能力缺口 → 推荐搜索外部源
    ↓
Phase 1: 正常项目规划（带工具建议）
```

## 搜索源优先级

| 优先级 | 源 | 说明 |
|--------|------|------|
| 1 | 本地已安装 | `~/.openclaw/skills/` + `/app/skills/` |
| 2 | Friday Skill 广场 | 美团内部官方 Skill（需 SSO） |
| 3 | ClawHub | 社区公开 Skill（需安全审计） |

**规则**: 优先使用本地已安装的 Skill。外部 Skill 仅作为建议，安装需 CEO 确认。

## 安全策略

### 原则：安全优先，仅推荐官方源

1. **本地 Skill**: 已安装即已信任，直接推荐
2. **Friday 官方 Skill**: 经公司审核，推荐安装
3. **ClawHub 社区 Skill**: 推荐前需经过安全初筛（`check_skill_safety()`）
4. **安装确认**: 任何新 Skill 安装必须经 CEO（即用户）明确确认
5. **不自动安装**: 系统只推荐，不自动执行安装

### 安全初筛（快速检查）

`tool_discovery.py check <skill_path>` 执行以下检查：

- SKILL.md 是否存在
- 文件中是否包含可疑命令模式（curl+token、rm -rf /、nc -e 等）
- 是否引用敏感路径（openclaw.json、device-auth.json 等）

**注意**: 这只是初筛。完整安全审计应使用 `skill-vetter` Skill。

## CEO 集成规范

### 何时调用

1. **项目 Phase 0**（规划前）: 自动执行工具扫描
2. **用户显式请求**: "帮我找个能做 X 的工具"
3. **任务分配时**: 为 Sub-agent 推荐可用工具

### CEO 工作流

```python
# Phase 0: 工具扫描
report = tool_discovery.generate_tool_report(task_description)
# 在项目规划中包含工具建议

# 分配任务时
matches = tool_discovery.match_task_to_tools(sub_task, local_skills)
if matches:
    # 在角色卡中注入工具建议
    tool_hint = f"推荐工具: {matches[0]['name']}"
```

### 推荐在角色卡中注入

```
[OPC 角色卡]
- 角色：搭建工程师
- 可用工具：gundam-ops（高达搭建执行 Skill）
- 工具来源：本地已安装
```

## 使用示例

### 场景 1：营销活动搭建

```bash
$ python3 tool_discovery.py report "创建高达营销活动并配置组件"

# 🔧 OPC 工具建议报告
# **任务**: 创建高达营销活动并配置组件
# 
# ## ✅ 已安装可用
# | Skill | 相关度 | 匹配原因 |
# |-------|--------|----------|
# | gundam-ops-202603091158-lzw | ⭐⭐⭐⭐ | 关键词匹配: 活动, 配置, 组件, 营销 |
```

### 场景 2：搜索新工具

```bash
$ python3 tool_discovery.py search "PDF 文档处理"

# 本地匹配:
#   pdf ⭐⭐⭐ — 关键词匹配: pdf, 文档
# 
# 搜索 ClawHub...
# 找到 2 个外部 Skill:
#   pdf-merge — https://clawhub.com/skills/pdf-merge
```

### 场景 3：安全检查

```bash
$ python3 tool_discovery.py check ~/.openclaw/skills/some-skill

# ✅ 安全初筛通过: /root/.openclaw/skills/some-skill
# 注意: 这只是快速初筛，不替代完整安全审计 (skill-vetter)
```

## 命令行参考

```bash
# 扫描本地 Skill
python3 tool_discovery.py scan

# 搜索外部
python3 tool_discovery.py search "关键词"

# 生成完整报告
python3 tool_discovery.py report "任务描述"

# 安全初筛
python3 tool_discovery.py check <skill_path>

# 通过 project_state_v2 集成调用
python3 project_state_v2.py tool-scan "任务描述"
```

## 缓存机制

- 本地扫描结果缓存到 `opc-projects/.tool-cache.json`
- TTL: 1 小时（3600 秒）
- 过期后自动重新扫描
- `scan` 命令强制刷新缓存

## 限制

1. 关键词匹配是简单的词级交集，不做语义理解
2. ClawHub 搜索依赖网络可用性和 openclaw CLI
3. Friday Skill 广场需要 SSO 认证，sandbox 中可能不可用
4. 安全初筛只检查文本模式，不做代码执行分析
