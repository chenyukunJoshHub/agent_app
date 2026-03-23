# Plans Index

本目录包含 Multi-Tool AI Agent 项目的所有阶段计划文件。

## 阶段映射表

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

## 当前状态

**最后更新**: 2026-03-23

**当前阶段**: Phase 14 - Slot Token 实时统计功能 ✅ **COMPLETED**

**所有核心功能已完成！** ✅

**阻塞项**: 无

**下一阶段**: 生产准备（性能优化、安全加固、CI/CD 配置）

---

## 阶段说明

### Phase 01: 数据库设置
- PostgreSQL 连接池配置
- AsyncPostgresSaver + AsyncPostgresStore 初始化
- 数据库迁移脚本

### Phase 02: SkillManager
- Skill 数据模型
- YAML frontmatter 解析
- 3级预算降级策略
- read_skill_content 错误处理

### Phase 03: Memory 系统
- 三层 Memory 架构
- MemoryMiddleware 实现
- Ephemeral 注入机制
- UserProfile 管理

### Phase 04: Agent 核心
- LangGraph 集成
- Agent Executor
- 中间件系统
- finish_handler 处理

### Phase 05: Prompt 构建
- 静态模板定义
- Token 预算管理
- System Prompt 构建器
- 内部操作 Prompt

### Phase 06: Tools 工具
- read_file 工具
- web_search 工具
- send_email 工具 (HIL)
- activate_skill 工具

### Phase 07: API 路由
- /chat 端点 (SSE)
- /chat/resume 端点 (HIL)
- /skills 端点
- /session/{id}/context 端点

### Phase 08: 前端布局
- 三面板布局实现
- Chat 组件
- 状态管理 (Zustand)
- SSE 连接管理

### Phase 09: ReAct 链路可视化
- ReActPanel 组件
- ThoughtStep 组件
- ToolCallStep 组件
- ObservationStep 组件
- Framer Motion 动画

### Phase 10: Context Window 面板
- ContextWindowPanel 组件
- 10个 Slot 可视化
- SlotBar 组件
- CompressionLog 组件
- 颜色编码系统

### Phase 11: Skills UI
- SkillPanel 组件
- SkillCard 组件
- SkillDetail 抽屉
- ACTIVE badge 显示
- Skill 激活历史

### Phase 12: HIL 人工介入
- HILConfirmDialog 组件
- 全屏模态框
- approve/reject 流程
- 中断状态持久化

### Phase 13: E2E 测试
- chat.spec.ts
- react-trace.spec.ts
- context-window.spec.ts
- skills.spec.ts
- hil.spec.ts
- Playwright headed 模式配置

### Phase 14: Slot Token 实时统计
- SlotContentTracker 类（10 个 Slot 跟踪）
- build_system_prompt Slot 跟踪增强
- GET /session/{id}/slots API 端点
- SlotDetail 前端组件（可展开/折叠）
- ContextWindowPanel 详情视图
- 63 个测试（后端 27 + 前端 15 + API 10 + E2E 11）

---

## 当前状态

**最后更新**: 2026-03-22

**进行中**: Phase 08 - 前端布局重构

**阻塞项**: 无

**下一阶段**: Phase 09 - ReAct 链路可视化

---

## 规范符合性整改

基于 2026-03-22 的项目 review,需要以下整改:

### P0 - 立即整改
- [ ] 调整测试目录结构 (backend/tests/ → tests/backend/)
- [ ] 修复 Playwright 配置 (添加 headless: false, slowMo: 300)
- [ ] 创建缺失的前端组件 (ContextWindowPanel, ReActPanel, SkillsPanel)

### P1 - 重要改进
- [ ] 重组前端组件目录结构
- [ ] 补充 E2E 测试场景 (react-trace, context-window, skills, hil)

### P2 - 文档同步
- [ ] 更新 README.md
- [ ] 同步 task_plan.md 进度

详见 `findings.md` 中的完整 review 报告。
