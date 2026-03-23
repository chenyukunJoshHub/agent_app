# Phase 02 — SkillManager

## 目标

实现完整的 SkillManager 功能，包含 scan、build_snapshot（3 级预算降级）、read_skill_content，并达到 90% 测试覆盖率。

## 架构文档参考

- Agent Skill v3 §1.2 Skill 数据模型
- Agent Skill v3 §1.5 触发机制 — SkillSnapshot.prompt 格式
- Agent Skill v3 §1.8 字符预算管理 — 3 级降级策略
- Agent Skill v3 §1.10 Skill 加载优先级与目录规范

## 测试用例清单（TDD 先写）

### SkillManager.scan()
- [ ] 扫描后应加载 status=active 的 skill
- [ ] status=draft 的 skill 不应被加载
- [ ] status=disabled 的 skill 不应被加载
- [ ] 超过 MAX_SKILL_FILE_BYTES 的文件应被跳过
- [ ] 无效 YAML frontmatter 的文件应被跳过
- [ ] 没有 SKILL.md 的目录应被跳过
- [ ] file_path 应将 home 目录替换为 ~

### SkillManager.build_snapshot()
- [ ] 字符数在预算内，使用完整格式（含 description）
- [ ] 字符数超限，降级为紧凑格式（仅 name + file_path）
- [ ] snapshot.version 每次构建递增
- [ ] skills 按 priority 降序排列
- [ ] disable_model_invocation=true 的 skill 不出现在 snapshot
- [ ] 完整格式包含 Skill Protocol 头部说明文字

### SkillManager.read_skill_content()
- [ ] 存在的 skill 返回 SKILL.md 完整内容
- [ ] 不存在的 skill 返回包含可用列表的错误提示
- [ ] file_path 中的 ~ 应正确展开为 home 目录

## 实现步骤（TDD 顺序）

### Step 1 — 数据结构定义
- 先写 `test_skill_definition_fields` 确认 dataclass 字段
- 实现 `SkillDefinition`, `SkillEntry`, `SkillSnapshot`

### Step 2 — scan()
- 写全部 scan 测试，确认全部 RED
- 实现 scan + _parse_frontmatter
- 确认全部 GREEN

### Step 3 — build_snapshot()
- 写全部 snapshot 测试，确认全部 RED
- 实现 build_snapshot + _build_prompt（完整格式）
- 实现 3 级降级逻辑
- 确认全部 GREEN

### Step 4 — read_skill_content()
- 写测试，实现，GREEN

### Step 5 — 覆盖率检查
```bash
pytest tests/backend/test_skill_manager.py --cov=skills/manager --cov-report=term-missing
```
- 目标：90%+
- 补充遗漏用例

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] 覆盖率 ≥ 90%
- [ ] findings.md 中记录所有技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
