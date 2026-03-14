# 成本报告模板

## 模板

```markdown
# 📊 项目成本报告

**项目**：{project_name}
**执行时间**：{start_time} - {end_time}
**总耗时**：{duration}

## 按角色分布

| 角色 | 任务数 | Token | 估算成本 |
|------|--------|-------|---------|
| {role_1} | {n} | {tokens}K | ${cost} |
| {role_2} | {n} | {tokens}K | ${cost} |
| CEO 协调 | - | {tokens}K | ${cost} |
| **总计** | **{total_tasks}** | **{total_tokens}K** | **${total_cost}** |

## 按阶段分布

| 阶段 | Token | 占比 |
|------|-------|------|
| 策划 | {n}K | {p}% |
| 执行 | {n}K | {p}% |
| 发布 | {n}K | {p}% |
| 协调 | {n}K | {p}% |

## 预算执行情况

- 预算：{budget}K tokens
- 实际：{actual}K tokens
- 偏差：{delta}（{percent}%）

## 优化建议
- {suggestion_1}
- {suggestion_2}
```
