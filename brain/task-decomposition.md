# 任务分解方法论

## 三层结构：OKR → Epic → Task

```
Objective: {一句话目标}
├── KR1: {可衡量的关键结果}
│   ├── Epic 1.1: {大功能块}
│   │   ├── Task: {具体任务} → 角色 [依赖] [预算]
│   │   └── Task: ...
│   └── Epic 1.2: ...
└── KR2: ...
```

## Task 定义规范

```yaml
task_id: T001
name: 确定活动主题
epic: E1.1-活动策划
role: 活动策划员
depends_on: []           # 依赖的 task_id 列表
estimated_tokens: 25000  # 预估 token
status: pending          # pending/assigned/in_progress/review/completed/failed
priority: high           # high/medium/low
output: markdown         # 产出格式
```

## 状态机

```
pending → assigned → in_progress → review → completed
                         ↓            ↓
                       failed       failed
```

## 依赖管理

1. **硬依赖**：必须等上游完成。如"搭建"依赖"策划方案"
2. **软依赖**：最好有但可以先开始。如"内容"软依赖"设计风格"
3. **无依赖**：可并行执行

## 拆分粒度原则

- 每个 Task 预估 token < 50K
- 每个 Task 产出明确可验收
- 每个 Task 由单一角色完成
- 依赖链不超过 5 层

## 示例：营销活动

```
Objective: 315 促销活动上线
├── KR1: 活动页面 3.10 前发布
│   ├── Epic 1.1: 策划
│   │   ├── T001: 确定主题人群 → 策划员 [无依赖] [25K]
│   │   └── T002: 制定预算分配 → 预算员 [T001] [20K]
│   ├── Epic 1.2: 搭建
│   │   ├── T003: 创建高达活动 → 搭建员 [T001] [30K]
│   │   ├── T004: 配置页面组件 → 搭建员 [T003] [40K]
│   │   └── T005: 配置供给数据 → 供给员 [T003] [30K]
│   └── Epic 1.3: 发布
│       ├── T006: 发布诊断 → 发布员 [T004,T005] [15K]
│       └── T007: 正式发布 → 发布员 [T006] [10K]
└── KR2: ...
```
