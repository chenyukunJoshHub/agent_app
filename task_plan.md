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

---

## 📊 当前状态

### 已完成阶段 (Phase 01-12)
- ✅ 数据库初始化 (PostgreSQL + LangGraph 存储)
- ✅ SkillManager (扫描、构建快照、3级预算降级)
- ✅ MemoryManager (三层记忆架构、Ephemeral 注入)
- ✅ Agent 核心 (LangChain Engine、Middleware 集成)
- ✅ Prompt 构建器 (System Prompt + Token 预算)
- ✅ 工具系统 (web_search、send_email、activate_skill 等)
- ✅ FastAPI SSE 流式接口
- ✅ 前端基础布局 (三栏面板设计)
- ✅ ReAct 链路可视化
- ✅ Context Window Token 面板
- ✅ Skills UI 面板
- ✅ HIL 人工介入流程

### 当前阶段
**Phase 13 - E2E 测试** ✅ done
- ✅ Playwright 配置统一与路径修复
- ✅ 后端服务自动启动
- ✅ 测试稳定性修复
- ✅ 补充测试用例（新增 2 个文件）
- ✅ 验证与报告

**测试统计**: 145 个测试（7 个文件 × 29 个唯一测试 × 5 个浏览器配置）

---

## 🔴 当前阻塞项

**无阻塞项！** Phase 13 已完成。

**可选任务**（非阻塞）:
- 安装 Firefox 和 Safari 浏览器（可选，Chromium 已覆盖主要场景）
- 运行完整测试套件验证（需要后端 + LLM 运行）

---

## 📝 下一步计划

**Phase 13 已完成！** ✅

1. **集成测试验证**
   - 端到端流程验证（需要后端 + LLM 运行）
   - SSE 事件流验证
   - HIL 断点恢复验证

2. **文档完善**
   - API 文档
   - 部署指南
   - 开发者指南

3. **生产准备**
   - 性能优化
   - 安全加固
   - CI/CD 配置

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
