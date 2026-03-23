# Multi-Tool AI Agent - 统一项目任务计划

> **重建日期**: 2026-03-23
> **项目类型**: Full-stack Web Application (Python + Next.js)
> **目标**: 构建企业级 Multi-Tool AI Agent，展示复杂任务编排、可控性与可扩展性

---

## 📋 项目概述

### 核心目标
构建一个支持多工具调用的通用 AI Agent 系统，具备：
- **复杂任务编排能力** - 多步骤推理、工具链组合
- **可控性与可观测性** - 完整的推理链可视化、HIL 人工介入
- **可扩展性** - 灵活的 Skills 插件机制
- **工程化标准** - 完整测试、CI/CD、文档

### 技术栈

| 组件 | 技术选型 | 版本 |
|------|---------|------|
| **后端框架** | FastAPI | 0.115+ |
| **Agent 框架** | LangChain + LangGraph | >=1.2.13, <2.0.0 |
| **LLM Provider** | OpenAI / Anthropic / Ollama | latest |
| **数据库** | PostgreSQL (Supabase) | 16+ |
| **前端框架** | Next.js | 15+ |
| **状态管理** | Zustand | 5.x |
| **样式** | Tailwind CSS | v4 |
| **测试** | Playwright (E2E) / pytest (backend) | latest |

---

## 🎯 阶段映射表

| 阶段 | 计划文件 | 对应代码路径 | 架构文档 | 状态 |
|------|---------|------------|---------|------|
| 01 | plan-phase01-db-setup.md | backend/db/ | Memory v5 §2.3 | ✅ done |
| 02 | plan-phase02-skill-manager.md | backend/skills/ | Skill v3 §1.2-1.10 | ✅ done |
| 03 | plan-phase03-memory.md | backend/memory/ | Memory v5 §2.4-2.9 | ✅ done |
| 04 | plan-phase04-agent-core.md | backend/agent/ | Agent v13 §2.1 | ✅ done |
| 05 | plan-phase05-prompt.md | backend/prompt/ | Prompt v20 §1.3-1.4 | ✅ done |
| 06 | plan-phase06-tools.md | backend/tools/ | Agent v13 §1.12 | ✅ done |
| 07 | plan-phase07-api.md | backend/main.py | Agent v13 §2.4 | ✅ done |
| 08 | plan-phase08-frontend-layout.md | frontend/app/ | — | ✅ done |
| 09 | plan-phase09-react-trace.md | frontend/components/react-trace/ | Agent v13 §1.12 | ✅ done |
| 10 | plan-phase10-context-window.md | frontend/components/context-window/ | Prompt v20 §1.2 | ✅ done |
| 11 | plan-phase11-skills-ui.md | frontend/components/skills/ | Skill v3 §1.6 | ✅ done |
| 12 | plan-phase12-hil.md | frontend/components/hil/ | Agent v13 §1.13 | ✅ done |
| 13 | plan-phase13-e2e-tests.md | tests/e2e/ | — | ✅ done |
| 14 | plan-phase14-slot-token-stats.md | backend/prompt/slot_tracker.py + frontend/ | Prompt v20 §1.2 | ✅ done |

---

## 📊 当前状态

### 已完成阶段 (Phase 01-14)
- ✅ 数据库初始化 (PostgreSQL + LangGraph 存储)
- ✅ SkillManager (扫描、构建快照、3级预算降级、单例模式)
- ✅ MemoryManager (三层记忆架构、Ephemeral 注入、SummarizationMiddleware)
- ✅ Agent 核心 (LangChain Engine、Middleware 集成、Anthropic 支持)
- ✅ Prompt 构建器 (System Prompt + Token 预算)
- ✅ 工具系统 (web_search、send_email、activate_skill 等)
- ✅ FastAPI SSE 流式接口 (GET /skills, GET /session/{id}/context)
- ✅ 前端基础布局 (三栏面板设计)
- ✅ ReAct 链路可视化
- ✅ Context Window Token 面板
- ✅ Skills UI 面板 (SkillPanel, SkillCard, SkillDetail)
- ✅ HIL 人工介入流程
- ✅ E2E 测试套件 (145 个测试)
- ✅ Slot Token 实时统计功能 (63 个测试)

### P0/P1/P2 修复完成 ✅
**执行日期**: 2026-03-23

**P0 任务 (3 个)** ✅:
- ✅ Phase 02: 3 级预算降级策略 (Level 1/2/3)
- ✅ Phase 04: Anthropic provider 支持 (Claude 模型)
- ✅ Phase 07: GET /skills 端点

**P1 任务 (5 个)** ✅:
- ✅ Phase 03: SummarizationMiddleware
- ✅ Phase 07: GET /session/{id}/context 端点
- ✅ Phase 10: ContextWindowPanel 组件 (3 个子组件)
- ✅ Phase 11: Skills UI 组件 (3 个子组件)
- ✅ Phase 14: Slot Token 实时统计功能 (10 个 Slot 内容显示)

**P2 任务 (5 个)** ✅:
- ✅ Phase 02: SkillManager 单例模式
- ✅ Phase 02: 文件大小检查 (MAX_SKILL_FILE_BYTES)
- ✅ Phase 02: 空描述优化 (XML 标签省略)
- ✅ Phase 04: Anthropic import 错误测试
- ✅ Phase 10-11: 前端组件测试 (74 个测试)

### 当前阶段
**所有计划阶段已完成！** ✅

**测试统计**:
- 后端单元测试: 119+ 测试 ✅ (+27 Phase 14)
- 前端组件测试: 89+ 测试 ✅ (+15 Phase 14)
- E2E 测试: 156 测试 ✅ (+11 Phase 14)
- **总计**: 374+ 测试 ✅ (+63 Phase 14)

**代码覆盖率**:
- `skills.py`: 90.91%
- `context.py`: 100%
- `summarization.py`: 100%
- `manager.py`: 86.59%
- `slot_tracker.py`: 100% (Phase 14 新增)
- `builder.py`: 100% (Slot 跟踪部分，Phase 14 增强)

---

## 🔴 当前阻塞项

**无阻塞项！** 所有 P0/P1/P2 任务已完成。

**可选优化项**（非阻塞）:
- 前端三栏布局调整（UI 优化）
- Migration 文件编号规范化
- 清理 MemoryManager 中的 legacy 方法

---

## 📝 下一步计划

**所有核心功能已完成！** ✅

### 可选的后续工作

1. **生产准备**
   - 性能优化
   - 安全加固
   - CI/CD 配置

2. **文档完善**
   - API 文档
   - 部署指南
   - 开发者指南

3. **集成测试验证**
   - 端到端流程验证（需要后端 + LLM 运行）
   - SSE 事件流验证
   - HIL 断点恢复验证

4. **UI 优化**
   - 前端三栏布局调整
   - 响应式设计优化
   - 暗色主题完善

---

## 📚 架构文档索引

| 文档 | 路径 | 覆盖范围 |
|------|------|----------|
| Multi-Tool AI Agent v13 | docs/arch/agent-v13.md | 整体架构、HIL、SSE、部署范式 |
| Memory 模块 v5 | docs/arch/memory-v5.md | 三层记忆、Middleware、checkpointer、store API |
| Prompt + Context v20 | docs/arch/prompt-context-v20.md | 10 个 Slot、Token 预算、组装时序 |
| Agent Skill v3 | docs/arch/skill-v3.md | SkillManager、Skill Protocol、激活机制 |

---

## 🔗 相关文件

- **需求文档**: agent claude code prompt.md
- **进度日志**: progress.md
- **技术决策**: findings.md
- **阶段计划索引**: docs/plans/README.md

---

## 2026-03-23 会话同步（项目管理更新）

### 本次状态
- **状态**: ✅ 完成
- **主题**: 全链路可视化加固（初始化 → Context 组装 → ReAct → Memory/HIL）

### 已完成的管理项
- 已在 `progress.md` 记录本次会话目标、完成项、测试结果与遗留风险。
- 已在 `findings.md` 记录本次架构决策（trace_event 统一协议、slot 语义归一化、SSE 收尾事件、resume SSE 一致性）。

### 当前阻塞
- 无新增阻塞项。
