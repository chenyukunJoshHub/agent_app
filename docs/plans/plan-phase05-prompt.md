# Phase 05 — Prompt 构建器

## 目标

实现 System Prompt 构建器，包含角色定义、能力边界、行为约束、Skill Protocol、SkillSnapshot、静态 Few-shot 和用户画像注入。

## 架构文档参考

- Prompt v20 §1.3 十大子模块职责
- Prompt v20 §1.4 完整组装时序
- Skill v3 §1.4 Skill Protocol

## 测试用例清单（TDD 先写）

### build_system_prompt()
- [ ] 返回完整 System Prompt
- [ ] 包含角色定义
- [ ] 包含能力边界
- [ ] 包含行为约束
- [ ] 包含 Skill Protocol（4 条规则）
- [ ] 包含 SkillSnapshot.prompt
- [ ] 包含静态 Few-shot

### Token 预算管理
- [ ] 10 个 Slot 正确分配
- [ ] 总预算不超过上限
- [ ] 弹性历史区计算正确

## 实现步骤（TDD 顺序）

### Step 1 — Prompt 模板
- 定义基础模板
- 定义 Skill Protocol 文本

### Step 2 — build_system_prompt
- 写测试，确认 RED
- 实现组装逻辑
- 确认 GREEN

### Step 3 — Token 预算
- 写测试，确认 RED
- 实现 10 个 Slot 分配
- 确认 GREEN

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] System Prompt 完整且格式正确
- [ ] Token 预算分配合理
- [ ] Skill Protocol 正确注入
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
