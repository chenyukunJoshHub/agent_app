# CLAUDE.md — Agent Project Working Rules

> 本文件是 Claude Code 的强制工作规范。每次会话开始前必须读取，每次操作前必须遵守。
> 违反任何规则前，必须先明确说明原因并请求确认。

---

## 核心原则（按优先级排序）

1. **遇到问题，先查架构文档**
2. **所有功能，先写测试**
3. **所有进度，实时更新计划文件**

---

## 规则一：遇到问题必须参考架构文档

### 触发条件

以下任何情况发生时，**立即停止编码**，先查阅对应架构文档：

- 不确定某个模块应该如何设计
- 遇到 API 选型问题（LangChain / LangGraph / psycopg3 等）
- 不确定某个概念的归属（Memory vs Prompt vs Skill）
- 遇到两种实现方案难以抉择
- 发现当前实现与预期行为不符

### 架构文档索引

| 文档 | 路径 | 覆盖范围 |
|------|------|----------|
| Multi-Tool AI Agent v13 | `docs/arch/agent-v13.md` | 整体架构、HIL、SSE、部署范式 |
| Memory 模块 v5 | `docs/arch/memory-v5.md` | 三层记忆、Middleware、checkpointer、store API |
| Prompt + Context v20 | `docs/arch/prompt-context-v20.md` | 10 个 Slot、Token 预算、组装时序 |
| Agent Skill v3 | `docs/arch/skill-v3.md` | SkillManager、Skill Protocol、激活机制 |

### 查阅流程

```
遇到问题
  → 1. 识别问题属于哪个模块（Agent / Memory / Prompt / Skill）
  → 2. 打开对应架构文档的相关章节
  → 3. 找到设计决策和实现约束
  → 4. 按文档设计实现，不自由发挥
  → 5. 在 findings.md 记录查阅结论
```

### 禁止行为

- ❌ 凭直觉或经验猜测 API 用法，必须先查文档
- ❌ 发现架构文档与当前实现冲突时，以"能跑就行"为由跳过
- ❌ 使用架构文档中明确标注 deprecated 的 API（如 asyncpg、create_react_agent）
- ❌ 在未查阅文档的情况下自行设计架构文档已覆盖的模块

---

## 规则二：强制 TDD — 测试驱动开发

### 核心约定：Red → Green → Refactor

**任何功能代码，必须先有测试，后有实现。**

```
Red    写一个会失败的测试
  ↓
Green  写最少的代码让测试通过
  ↓
Refactor  重构代码，保持测试绿色
```

### TDD 执行流程（每个功能单元）

```
Step 1  在 plan-phaseXX-*.md 中写出测试用例列表（伪代码描述）
Step 2  创建测试文件，写第一个 failing test
Step 3  运行测试，确认 RED（失败）
Step 4  写最少的实现代码让测试通过
Step 5  运行测试，确认 GREEN（通过）
Step 6  重构实现代码（不改测试）
Step 7  运行全量测试，确认无回归
Step 8  在 progress.md 记录测试结果
Step 9  重复 Step 2-8，直到所有用例覆盖
```

### 测试分层规范

#### 后端单元测试（pytest）

```
tests/backend/
├── test_skill_manager.py     # SkillManager: scan, build_snapshot, budget降级
├── test_token_budget.py      # TokenBudgetState: slot追踪, 溢出检测
├── test_memory.py            # MemoryManager: load/save episodic
├── test_prompt_builder.py    # build_system_prompt: Skill Protocol注入
└── test_tools.py             # activate_skill, web_search, send_email
```

每个测试文件结构：

```python
# test_skill_manager.py

import pytest
from skills.manager import SkillManager, SkillSnapshot

class TestSkillManagerScan:
    """SkillManager.scan() — 扫描 SKILL.md 文件"""

    def test_scan_loads_active_skills(self, tmp_skills_dir):
        """扫描后应加载 status=active 的 skill"""
        # ARRANGE
        # ACT
        # ASSERT

    def test_scan_ignores_draft_skills(self, tmp_skills_dir):
        """status=draft 的 skill 不应被加载"""

    def test_scan_skips_oversized_files(self, tmp_skills_dir):
        """超过 MAX_SKILL_FILE_BYTES 的文件应被跳过"""


class TestSkillManagerBuildSnapshot:
    """SkillManager.build_snapshot() — 3 级预算降级"""

    def test_full_format_within_budget(self, manager_with_2_skills):
        """字符数在预算内，使用完整格式"""

    def test_compact_format_when_over_budget(self, manager_with_many_skills):
        """字符数超限时，降级为紧凑格式"""

    def test_skills_sorted_by_priority_desc(self, manager):
        """Snapshot 中 skill 按 priority 降序排列"""
```

必须覆盖的测试场景（不可省略）：

| 模块 | 必须覆盖的场景 |
|------|--------------|
| SkillManager | scan 加载/过滤、build_snapshot 3 级降级、read_skill_content 错误处理 |
| TokenBudgetState | 所有 10 个 slot 计算、overflow 检测、compression event 记录 |
| MemoryManager | load 空用户返回默认值、save 正常写入、Ephemeral 不污染历史 |
| Skill Protocol | 4 条规则全部存在于 system prompt 中 |
| activate_skill | 存在 skill 返回内容、不存在 skill 返回错误提示 |

#### 前端组件测试（Playwright Component Tests）

```
tests/components/
├── ContextWindowPanel.spec.ts  # slot 渲染、颜色、overflow badge
├── ReActPanel.spec.ts          # 步骤渲染、颜色编码、折叠展开
├── SkillPanel.spec.ts          # skill 卡片、ACTIVE badge、抽屉
└── HILConfirmDialog.spec.ts    # 弹出、approve/reject 流程
```

#### E2E 测试（Playwright headed）

```
tests/e2e/
├── chat.spec.ts            # 基础对话流程
├── react-trace.spec.ts     # ReAct 链路可视化
├── context-window.spec.ts  # Token 上下文面板
├── skills.spec.ts          # Skill 激活全流程
└── hil.spec.ts             # HIL 确认/取消流程
```

**E2E 测试强制要求**：
- `headless: false`（必须有头模式）
- `slowMo: 300`（人眼可跟随）
- 所有 SSE 相关断言设置超时 `≥ 15000ms`
- 失败时保留截图 + 录像

### 代码覆盖率要求

| 层级 | 最低覆盖率 | 目标 |
|------|-----------|------|
| 后端核心模块（skills, memory, context） | 80% | 90% |
| 后端 API 路由 | 70% | 80% |
| 前端组件 | 60% | 75% |
| E2E 关键路径 | 100% | 100% |

### TDD 禁止行为

- ❌ 先写实现，后补测试（事后测试不是 TDD）
- ❌ 为让测试通过而 mock 掉被测核心逻辑
- ❌ 跳过 RED 阶段直接写实现（必须先确认测试失败）
- ❌ 提交未通过测试的代码
- ❌ 修改测试来让实现通过（应该修改实现）

---

## 规则三：两层计划管理结构

### 目录结构

```
/planning-with-files/           ← 项目级（宏观管理）
├── task_plan.md                # 由 /planning-with-files 命令生成和维护
├── findings.md                 # 由 /planning-with-files 命令生成和维护
└── progress.md                 # 由 /planning-with-files 命令生成和维护

/docs/plans/                    ← 阶段级（微观实施，手动维护）
├── README.md                   # 计划索引和映射表
├── plan-phase01-db-setup.md
├── plan-phase02-skill-manager.md
├── plan-phase03-memory.md
├── plan-phase04-agent-core.md
├── plan-phase05-prompt.md
├── plan-phase06-tools.md
├── plan-phase07-api.md
├── plan-phase08-frontend-layout.md
├── plan-phase09-react-trace.md
├── plan-phase10-context-window.md
├── plan-phase11-skills-ui.md
├── plan-phase12-hil.md
└── plan-phase13-e2e-tests.md
```

---

### 3.1 项目级文件 — 由 `/planning-with-files` 管理

`task_plan.md`、`findings.md`、`progress.md` 这三个文件**由 Claude Code 内置的 `/planning-with-files` 命令负责创建和维护**，不要手动重新定义它们的格式或结构。

使用规范：

```
# 项目开始时初始化（只执行一次）
/planning-with-files

# 每次会话开始时，读取这三个文件了解当前状态
# 每次会话结束时，通过 /planning-with-files 更新进度
```

写入这三个文件时的内容约定（在 `/planning-with-files` 生成的结构内填充）：

- `task_plan.md` — 记录本项目的阶段划分、每阶段与 `docs/plans/` 计划文件的映射关系、当前阻塞项
- `findings.md` — 记录查阅架构文档后的技术决策结论，格式：问题 → 查阅章节 → 结论 → 影响文件
- `progress.md` — 记录每次会话的目标、完成项、文件变更列表、测试结果、遗留问题

> ⚠️ 禁止在 CLAUDE.md 或其他地方重新定义这三个文件的格式。
> 格式由 `/planning-with-files` skill 决定，以 skill 的实际输出为准。

---

### 3.2 docs/plans/plan-phaseXX-*.md — 格式规范

每个阶段计划文件必须包含以下章节：

```markdown
# Phase 02 — SkillManager

## 目标

实现 SkillManager 完整功能，包含 scan、build_snapshot（3 级预算降级）、
read_skill_content，并达到 90% 测试覆盖率。

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
```

---

### 3.3 docs/plans/README.md — 计划索引

```markdown
# Plans Index

## 阶段映射表

| 阶段 | 计划文件 | 对应代码路径 | 架构文档 |
|------|---------|------------|---------|
| 01 | plan-phase01-db-setup.md | backend/db/ | Memory v5 §2.3 |
| 02 | plan-phase02-skill-manager.md | backend/skills/ | Skill v3 §1.2-1.10 |
| 03 | plan-phase03-memory.md | backend/memory/ | Memory v5 §2.4-2.9 |
| 04 | plan-phase04-agent-core.md | backend/agent/ | Agent v13 §2.1 |
| 05 | plan-phase05-prompt.md | backend/prompt/ | Prompt v20 §1.3-1.4 |
| 06 | plan-phase06-tools.md | backend/tools/ | Agent v13 §1.12 |
| 07 | plan-phase07-api.md | backend/main.py | Agent v13 §2.4 |
| 08 | plan-phase08-frontend-layout.md | frontend/app/ | — |
| 09 | plan-phase09-react-trace.md | frontend/components/react-trace/ | Agent v13 §1.12 |
| 10 | plan-phase10-context-window.md | frontend/components/context-window/ | Prompt v20 §1.2 |
| 11 | plan-phase11-skills-ui.md | frontend/components/skills/ | Skill v3 §1.6 |
| 12 | plan-phase12-hil.md | frontend/components/hil/ | Agent v13 §1.13 |
| 13 | plan-phase13-e2e-tests.md | tests/e2e/ | — |
```

---

## 规则四：每次会话的固定开场和收场

### 会话开始时（必须执行）

```
1. 运行 /planning-with-files — 读取 task_plan.md 和 progress.md 了解当前状态
2. 打开当前阶段的 docs/plans/plan-phaseXX-*.md — 确认本次目标
3. 确认下一个要实现的测试用例（从阶段计划的测试用例清单找第一个未勾选的）
4. 报告："当前阶段 XX，上次完成了 XXX，本次目标是 XXX"
```

### 会话结束时（必须执行）

```
1. 运行全量测试，记录测试结果
2. 运行 /planning-with-files — 将以下内容更新到对应文件：
   - task_plan.md：更新阶段状态（⏳ / 🔄 / ✅ / ❌）
   - findings.md：本次查阅架构文档的技术决策结论
   - progress.md：本次会话日志（完成项、文件变更、测试结果、遗留问题）
3. 在阶段计划文件 docs/plans/plan-phaseXX-*.md 勾选已完成的测试用例
4. 确认下次会话的入口点（下一个 failing test）
```

---

## 规则五：文件操作规范

### 创建新文件前

1. 检查 docs/plans/ 中是否有对应阶段计划
2. 确认测试文件已存在（测试先于实现）
3. 通过 `/planning-with-files` 在 progress.md 预登记文件变更

### 修改现有文件前

1. 确认修改不会破坏现有通过的测试
2. 如会影响多个模块，先通过 `/planning-with-files` 更新 task_plan.md 的依赖关系
3. 修改后立即运行相关测试确认无回归

### 绝对禁止

- ❌ 在没有对应测试的情况下创建实现文件
- ❌ 删除测试文件（即使测试暂时 skip）
- ❌ 修改 CLAUDE.md 本身（除非用户明确指示）
- ❌ 在计划文件更新之前开始下一阶段

---

## 规则六：命令规范

### 测试命令（标准化）

```bash
# 后端单元测试
pytest tests/backend/ -v --tb=short

# 后端覆盖率报告
pytest tests/backend/ --cov=backend --cov-report=term-missing --cov-report=html

# 前端组件测试
npx playwright test tests/components/ --headed

# E2E 测试（有头模式，必须）
npx playwright test tests/e2e/ --headed

# 单个 spec 文件
npx playwright test tests/e2e/skills.spec.ts --headed

# 生成 Playwright HTML 报告
npx playwright show-report
```

### 计划文件更新（每次会话结束时）

```bash
# 通过 Claude Code 内置命令更新三个项目级文件
# 在 Claude Code 对话框中执行：
/planning-with-files
```

> 不要用 shell 命令直接写入 task_plan.md / findings.md / progress.md。
> 始终通过 `/planning-with-files` 命令，让 skill 按它自己的格式维护这三个文件。

---

## 快速参考：问题 → 架构文档映射

| 遇到的问题 | 查阅文档 | 具体章节 |
|-----------|---------|---------|
| checkpointer / store 初始化报错 | Memory v5 | §2.3 存储层初始化 |
| middleware 与 state_schema 冲突 | Memory v5 | §2.2 关键约束 |
| wrap_model_call vs before_model 选择 | Memory v5 | §2.5 Middleware 钩子职责 |
| Ephemeral 注入应该怎么做 | Memory v5 | §1.4 Ephemeral vs Persistent |
| SkillSnapshot 格式如何生成 | Skill v3 | §1.5 触发机制 |
| Skill Protocol 4 条规则 | Skill v3 | §1.4 Skill Protocol |
| 字符预算超限如何降级 | Skill v3 | §1.8 字符预算管理 |
| activate_skill 工具如何注册 | Skill v3 | §2.2 read_file @tool |
| 10 个 Slot 如何分配 Token | Prompt v20 | §1.2 子模块与 Context Window 分区 |
| 组装时序不清楚 | Prompt v20 | §1.4 完整组装时序 |
| SSE 事件类型划分 | Agent v13 | §2.4 SSE 流式架构 |
| HIL 拦截如何实现 | Agent v13 | §1.13 HIL 完整设计 |
| ReAct 循环工具并行 | Agent v13 | §2.2 Workflow 映射 |
| 部署架构选择 | Agent v13 | §1.10 部署架构范式对比 |