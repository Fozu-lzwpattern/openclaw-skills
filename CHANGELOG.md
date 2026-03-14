# Changelog - agent-orchestration-20260309-lzw

## 版本信息
- **分支名**: agent-orchestration-20260309-lzw
- **作者**: 大仙 (lzw)
- **创建时间**: 2026-03-09 14:05
- **方向**: One-Person Company (OPC) 编排技能

## 设计目标
- 让 OpenClaw 成为"一人公司"CEO
- 能指挥调度多个专业 Sub-agent 协作完成企业复杂任务
- 借鉴 PaperClip 组织管理方法论
- 与 gundam-ops 等业务 Skill 配合使用

## v1.0 (2026-03-09)

### Added
- SKILL.md 主入口 (~215行)
- references/ 方法论文档
  - role-design.md - 角色设计方法论
  - task-decomposition.md - 任务分解（OKR → Epic → Task）
  - heartbeat-protocol.md - Agent 执行协议
  - cost-tracking.md - 成本追踪方法
  - collaboration-patterns.md - 协作模式
- templates/ 可复用模板
  - agent-prompt.md - Sub-agent task prompt 模板
  - project-plan.md - 项目计划模板
  - cost-report.md - 成本报告模板
- scenarios/ 场景案例
  - marketing-campaign.md - 营销活动全链路案例（含详细 spawn 示例）
- scripts/ 自动化脚本
  - project_tracker.py - 项目状态追踪
  - cost_summary.sh - 成本汇总

### 文件统计
- 总计 12 个文件
- 约 1100 行

## 待迭代
- [ ] 实际营销场景联调验证
- [ ] 与 gundam-ops skill 联动测试
- [ ] 多 Agent 并行协作稳定性
- [ ] 更多场景案例（研究项目、内容创作...）

## 联调测试 (2026-03-09 14:22 - 15:37)

### 场景
315营销活动（精简3角色：策划→搭建→发布）

### 结果
- 3个 sub-agent 全部完成，产出质量良好
- 总消耗 67K tokens ($0.17)
- 发现 announce 不可靠问题并修复

### 迭代
- 新增 references/troubleshooting.md（故障归因）
- SKILL.md 新增超时检查规则 + 三步归因法

## v1.1 (2026-03-09 15:48)

### Added
- references/design-philosophy.md (315行) — 完整设计理念文档
  - OPC 核心理念和5大设计原则
  - 全生命周期运行逻辑
  - 多轮对话 OPC 组织设定流程（3轮确认）
  - 独立 Session 模式说明
  - OPC 与业务 Skill 关系（分层架构 + 通俗比喻）
  - 独立 Session 决策指南
  - 设计哲学总结

### Changed
- SKILL.md 新增多轮对话组织设定说明 + 设计理念引用

## v1.2 (2026-03-09 16:23)

### Added
- 附录A：OPC vs OpenClaw 原生 Multi-Agent 对比分析（追加到 design-philosophy.md）
  - 原生7种模式梳理（spawn/heartbeat/cron/send/lobster/A2A...）
  - 逐一对比（OPC vs spawn / heartbeat / cron / lobster）
  - 适用 vs 不适用场景明确
  - 组合使用最佳实践
  - 优劣势总结

## v1.3 (2026-03-09 21:49)

### Added
- references/persona-priming.md — 角色 Persona 增强方法论
  - 顶级人才 persona 库（营销/技术/研究/创意 4大类）
  - 使用原则：借鉴方法论，而非模仿人格
  - 升级版角色卡模板
- references/proactive-reporting.md — CEO 主动监控与汇报机制
  - 检查间隔标准（简单3min/中等5min/复杂10min）
  - 4条汇报规则（确认/检查点/阶段转换/异常）
  - 汇报模板（进度更新/异常告警/阶段完成）
  - 与 Sub-agent Heartbeat 的双保险机制

### Changed
- SKILL.md 新增 Persona Priming 和 CEO 主动监控章节
- templates/agent-prompt.md 角色卡新增 Persona 字段

## v1.4 (2026-03-11) — 实战驱动的四项优化

> 基于 2026-03-10 三会场搭建实战中暴露的问题，推动四项关键优化。

### 实战问题

| 问题 | 影响 | 根因 |
|------|------|------|
| Compaction 丢失执行状态 | Phase 2 启动延迟 | 项目状态完全在 context 中 |
| 并行 agent 状态不清晰 | CEO 难判断谁完了谁卡了 | 缺乏结构化状态看板 |
| 失败后完整重试 | 到餐搭建员浪费 17min | 无断点续传机制 |
| 成本追踪形同虚设 | Sub-agent 不汇报 token | 依赖"自觉"这种不可靠的机制 |

### Added — 项目状态持久化（P0）
- **scripts/project_state.py** (368行) — 全新项目状态管理器
  - `init` / `update-phase` / `agent-start` / `agent-complete` / `agent-fail`
  - `checkpoint` / `checkpoint-get` / `restore`
  - `show` / `list` / `report` / `diagnose`
  - 自动计算成本占比和预算告警
- **references/project-state.md** — 状态持久化设计文档
  - 状态文件结构（JSON Schema）
  - 目录结构规范
  - CEO 集成规范（4条必须遵守的规则）
  - Compaction 恢复流程

### Added — 断点续传（P0）
- SKILL.md 新增「断点续传」章节
  - 完整流程：失败→提取步骤→保存断点→kill→恢复→注入
  - 断点续传 prompt 模板
  - 断点内容规范（completedSteps/nextStep/context）

### Added — 自动归因（P1）
- `project_state.py diagnose` 命令
  - 根据错误关键词自动分类：L1-Platform / L2-Orchestration / L3-BusinessSkill
  - 输出建议操作
  - 标注是否有可用断点

### Changed — 成本追踪自动化（P1）
- 不再依赖 Sub-agent 自觉汇报
- CEO 通过 session_status 获取 token 消耗后写入 project_state
- `project_state.py report` 自动生成成本报告
- 预算告警自动计算（80%/100% 阈值）

### Changed — 确认流程分级简化（P1）
- 原来：所有任务都3轮确认
- 现在：简单1轮 / 中等2轮 / 复杂3轮
- 判断标准：Sub-agent 数量 + 并行度 + 跨业务线

### Changed — 使用限制更新
- 第3条：「预算是软约束」→「预算通过 project_state.py 自动追踪」
- 第4条：「项目状态在 context 中」→「项目状态持久化到文件」

### File Statistics
- 新增文件：2（project_state.py + project-state.md）
- 修改文件：2（SKILL.md + CHANGELOG.md）
- 新增行数：~550行
- SKILL.md 总行数：~486行
# v2.0 (2026-03-12) — Aware 触发器 + 运行时工具自发现

> OPC 从"被动执行"进化为"事件驱动"——项目定义好规则后能自己动起来。

## 核心新增

### Aware 触发器系统（P0）

声明式事件驱动，CEO 在 heartbeat 时调用 `evaluate()` 自动检查触发条件。

- **scripts/trigger_engine.py** (~380行) — 触发器引擎 + Focus 管理器
  - `TriggerEngine`: 5种触发类型（cron/once/interval/on_message/poll）
  - `FocusManager`: 项目焦点自适应管理，agent 全部完成时自动关闭
  - 命令行: `evaluate` / `status` / `fire` / `focus-list` / `focus-update`
  - 状态持久化: `trigger_state.json`
  - 内置自测: `--self-test`

- **references/aware-triggers.md** (~200行) — 完整设计文档
  - 触发器类型说明和 YAML Schema
  - Focus 系统和联动机制
  - CEO 集成规范和最佳实践

- **templates/triggers.yaml** — 触发器配置模板（5种类型示例）
- **templates/focus.yaml** — Focus 焦点模板

### 运行时工具自发现（P0）

任务启动前自动发现可用工具，弥补能力缺口。

- **scripts/tool_discovery.py** (~300行) — 工具自发现引擎
  - `scan`: 扫描本地已安装 Skill
  - `search`: 搜索 ClawHub 公开 Skill
  - `report`: 生成工具建议报告（任务↔工具匹配）
  - `check`: 基础安全初筛
  - 缓存: `.tool-cache.json`（TTL 1小时）
  - 内置自测: `--self-test`

- **references/tool-discovery.md** (~150行) — 设计文档
  - 搜索源优先级和安全策略
  - CEO 集成规范和使用示例

### project_state_v2.py — 集成扩展

在 v1.4 `project_state.py` 基础上新增 5 个命令:

| 命令 | 说明 |
|------|------|
| `trigger-evaluate <pid>` | 评估所有触发器 |
| `trigger-status <pid>` | 查看触发器状态 |
| `focus-update <pid> <id> <status>` | 更新焦点状态 |
| `focus-list <pid>` | 列出活跃焦点 |
| `tool-scan <task>` | 扫描推荐工具 |

另外，`agent-complete` 命令现在会自动调用 `FocusManager.check_auto_complete()`。

## Changed

- **SKILL.md** — 追加两个新章节（Aware 触发器 + 工具自发现），更新目录结构
- **目录结构** — 新增 4 个文件到 scripts/、2 个到 references/、2 个到 templates/

## 设计约束

- Python 3.9+ 兼容，仅标准库 + yaml（可选，有 fallback）
- 所有脚本支持 `--help` 和 `--self-test`
- YAML 解析容错（缺字段不崩溃）
- 触发器状态持久化到 `trigger_state.json`
- 工具缓存 TTL 1 小时

## 文件统计

| 文件 | 行数 | 说明 |
|------|------|------|
| scripts/trigger_engine.py | ~380 | 新增 |
| scripts/tool_discovery.py | ~300 | 新增 |
| scripts/project_state_v2.py | ~370 | 新增（v1.4扩展） |
| references/aware-triggers.md | ~200 | 新增 |
| references/tool-discovery.md | ~150 | 新增 |
| templates/triggers.yaml | ~60 | 新增 |
| templates/focus.yaml | ~25 | 新增 |
| SKILL_v2_additions.md | ~100 | SKILL.md 追加内容 |

**新增总行数**: ~1585
**新增文件数**: 8

## 迁移指南

1. 将 `scripts/trigger_engine.py` 和 `scripts/tool_discovery.py` 复制到正式路径
2. 用 `project_state_v2.py` 替换原 `project_state.py`（完全向后兼容）
3. 将 `references/` 和 `templates/` 下新文件复制到正式路径
4. 将 `SKILL_v2_additions.md` 内容追加到 SKILL.md 末尾
5. 将此 CHANGELOG 内容追加到 CHANGELOG.md

---

## v3.1 — 用户模型自学习（2026-03-14）

### 核心变更：OPC 越用越懂你

**问题**：v3.0 的 Phase 0 每次从零开始理解用户意图，不积累任何经验。

**方案**：双源用户模型 + 项目结束自动写回。

### 新增：Phase 0 用户模型读取

OPC 触发后，在追问用户之前，先依次读取：

| 优先级 | 文件 | 说明 |
|--------|------|------|
| ① | `workspace/opc-user-model.md` | OPC 专属模型，越用越精准 |
| ② | `~/.openclaw/workspace/MEMORY.md` | OpenClaw 官方长期记忆 |
| ③ | `~/.openclaw/workspace/USER.md` | 用户扩展文件（可能不存在）|
| ④ | `~/.openclaw/workspace/memory/YYYY-MM-DD.md` | 今日日志（可选）|

有预判 → 生成带预填的方案草稿，用户只需校正差异
无预判（首次）→ 正常追问，记录为第一次使用

### 新增：Phase 4 用户模型写回

项目关闭前，CEO 自动将以下信息写入 `opc-user-model.md`：
- 任务类型、角色配置、协作模式
- 实际 token 消耗与耗时
- Persona 效果观察
- 踩坑与经验

偏好区如有新发现，同步更新（覆盖旧条目）。

### 新增文件

| 文件 | 说明 |
|------|------|
| `playbook/templates/opc-user-model.md` | 用户模型文件模板 |
| `workspace/opc-user-model.md` | 用户实例（含历史5个项目数据）|

### 进化飞轮

```
项目越多 → 用户模型越丰富 → Phase 0 预判越准 → 用户越惊喜 → 做更多项目
```
