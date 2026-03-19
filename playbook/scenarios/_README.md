# 项目类型速启模板 — 通用规则

## 设计原则

1. **速启模板是起点，不是约束**
   继承模板后可自由修改任何参数，保留 OPC 的全部灵活性。

2. **critic 角色是强制项**
   任何项目类型都必须包含至少一个 critic 角色，负责内容质量的专家审查。
   critic 在最后执行，接收所有主产出，输出结构化反馈。
   只有 critic 通过（评分 ≥ 3），CEO 才能进入 Phase 4 交付包。

3. **模板结构**
   每个 yaml 包含：
   - `roles`：推荐角色组合（含 critic）
   - `task_graph`：典型依赖图结构
   - `output_contract`：产出协议框架
   - `trigger_keywords`：触发识别词

4. **使用方式**
   ```
   Phase 1 规划时：
     "这是研究项目" → CEO 继承 research-project.yaml
     → 填入 topic / date / path 参数
     → 声明 task-graph
     → spawn
   ```
