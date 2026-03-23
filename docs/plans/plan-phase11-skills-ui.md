# Phase 11 — Skills UI 面板

## 目标

实现 Skills 面板组件，展示所有注册的 skills，支持状态徽章、ACTIVE 指示器和 SkillDetail 抽屉。

## 架构文档参考

- agent claude code prompt.md §components/skills/
- Skill v3 §1.6 Skill 加载与展示

## 测试用例清单（TDD 先写）

### SkillPanel
- [ ] 正确渲染所有 skills
- [ ] status 徽章正确显示
  - [ ] active 显示绿色徽章
  - [ ] disabled 显示灰色徽章
  - [ ] ACTIVE 指示器正确显示

### SkillCard
- [ ] 正确显示 skill 名称
- [ ] 正确显示 description
- [ ] 正确显示 tools
- [ ] 正确显示 priority 和 mutex_group

### SkillDetail
- [ ] 点击 skill 卡片打开抽屉
- [ ] 正确渲染 SKILL.md 内容
- [ ] Token size 徽章正确显示
- [ ] 激活历史正确显示

### API 集成
- [ ] GET /skills 正确调用
- [ ] GET /skills/{id}/content 正确调用

## 实现步骤（TDD 顺序）

### Step 1 — 类型定义
- 定义 SkillDefinition
- 定义 SkillSnapshot

### Step 2 — SkillCard 组件
- 写测试，确认 RED
- 实现 SkillCard
- 确认 GREEN

### Step 3 — SkillDetail 组件
- 写测试，确认 RED
- 实现 SkillDetail 抽屉
- 确认 GREEN

### Step 4 — SkillPanel
- 写测试，确认 RED
- 实现 SkillPanel
- 确认 GREEN

### Step 5 — API 集成
- 集成 /skills 接口
- 集成 /skills/{id}/content 接口

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] Skills 列表正确显示
- [ ] 状态徽章正确
- [ ] SkillDetail 功能完整
- [ ] API 集成正常
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
