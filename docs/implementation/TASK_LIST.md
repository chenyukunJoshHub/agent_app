# Multi-Tool AI Agent - 统一任务清单

**创建日期**: 2026-03-20
**状态**: 待执行
**版本**: v1.0

---

## 📋 总览

本文档汇总了产品、前端、后端、数据库、部署、测试六个维度的实施任务，形成统一的任务清单。

### 文档来源

| 维度 | 文档 | 作者 |
|-----|------|------|
| 产品 | `docs/implementation/product-requirements.md` | product-planner |
| 前端 | `docs/implementation/frontend-implementation-plan.md` | frontend-planner |
| 后端 | `docs/implementation/backend-implementation-plan.md` | backend-planner |
| 数据库 | `docs/superpowers/database-implementation-plan.md` | database-planner |
| 部署 | `docs/superpowers/deployment/2026-03-20-deployment-implementation-plan.md` | deployment-planner |
| 测试 | `docs/testing-strategy.md` | test-planner |

---

## 🎯 Phase 1: 基础设施 (Week 1-2) 🔴 P0

### 目标
搭建项目基础架构，确保开发环境可用。

### 任务清单

- [ ] **1.1 项目脚手架**
  - [ ] 初始化 git 仓库
  - [ ] 创建后端项目结构
  - [ ] 创建前端项目结构
  - [ ] 配置 .gitignore
  - [ ] 配置代码规范工具

- [ ] **1.2 Docker Compose 配置**
  - [ ] PostgreSQL 服务
  - [ ] Backend 服务
  - [ ] Frontend 服务
  - [ ] Ollama 服务
  - [ ] 健康检查配置

- [ ] **1.3 数据库初始化**
  - [ ] 执行迁移脚本 `002_create_users_and_sessions.sql`
  - [ ] 验证表结构
  - [ ] 测试连接

- [ ] **1.4 LLM Factory**
  - [ ] 实现多 provider 支持
  - [ ] 实现 fallback 机制
  - [ ] 配置 Ollama 连接

- [ ] **1.5 核心 Tools**
  - [ ] `read_file` 工具（带路径安全）
  - [ ] `fetch_url` 工具
  - [ ] `token_counter` 工具（使用 tiktoken）

- [ ] **1.6 前端基础组件**
  - [ ] 配置 Tailwind CSS v4
  - [ ] 配置 Radix UI
  - [ ] 创建基础 UI 组件库
  - [ ] 配置 Plus Jakarta Sans 字体

### 验收标准
- [ ] `docker-compose up -d` 一键启动所有服务
- [ ] 后端 API 健康检查通过
- [ ] 前端页面可访问
- [ ] LLM 可正常调用

---

## 🧠 Phase 2: Memory 系统 (Week 2-3) 🔴 P0

### 目标
实现三层 Memory 架构和中间件机制。

### 任务清单

- [ ] **2.1 数据模型**
  - [ ] Pydantic 模型定义
  - [ ] CRUD 操作封装

- [ ] **2.2 Memory 中间件**
  - [ ] `before_agent` 钩子（加载长期画像）
  - [ ] `wrap_model_call` 钩子（Ephemeral 注入）
  - [ ] `after_agent` 钩子（写回画像）
  - [ ] 中间件集成到 LangGraph

- [ ] **2.3 Token 预算管理**
  - [ ] Token 计数器实现
  - [ ] 预算分配逻辑
  - [ ] 超预算处理

- [ ] **2.4 数据库约束**
  - [ ] 执行 `003_add_constraints.sql`
  - [ ] 执行 `004_add_indexes.sql`
  - [ ] 执行 `005_enable_rls.sql`
  - [ ] 验证约束生效

### 验收标准
- [ ] 用户画像能正确注入到 System Prompt
- [ ] 历史中不包含重复的画像内容
- [ ] Token 使用量能正确统计
- [ ] RLS 策略生效（用户只能访问自己的数据）

---

## 🔧 Phase 3: Skills 系统 (Week 3-4) 🟡 P1

### 目标
实现 Agent Skills 四层结构和加载机制。

### 任务清单

- [ ] **3.1 Skill Manager**
  - [ ] 多层扫描（project/ + ~/.agents/skills/）
  - [ ] 优先级覆盖逻辑
  - [ ] 热重载机制
  - [ ] 并发安全保护

- [ ] **3.2 Skill Protocol**
  - [ ] SKILL.md 解析器
  - [ ] `read_file` 激活机制
  - [ ] 冲突检测与日志

- [ ] **3.3 内置 Skills**
  - [ ] `web_search` Skill (Tavily API)
  - [ ] `browser_use` Skill
  - [ ] 示例 Skill 模板

### 验收标准
- [ ] 能从项目目录和全局目录加载 Skills
- [ ] 项目 Skills 能覆盖全局 Skills
- [ ] LLM 能通过 `read_file` 激活 Skill
- [ ] 热重载不需要重启服务

---

## 📡 Phase 4: 可观测性 (Week 4-5) 🟡 P1

### 目标
实现 SSE 流式推送和前端可视化。

### 任务清单

- [ ] **4.1 后端 SSE**
  - [ ] 实现事件类型定义
  - [ ] 集成 `astream` 到 LangGraph
  - [ ] 实现 `/api/chat/stream` 端点

- [ ] **4.2 前端 SSE 管理**
  - [ ] 使用 `@microsoft/fetch-event-source`
  - [ ] 实现指数退避重连
  - [ ] 连接状态管理
  - [ ] 事件序列检测

- [ ] **4.3 时间轴组件**
  - [ ] Timeline 容器组件
  - [ ] TimelineEvent 节点组件
  - [ ] TokenBar 进度条
  - [ ] 虚拟滚动优化

- [ ] **4.4 HIL 确认模态框**
  - [ ] ConfirmModal 组件
  - [ ] RiskBadge 组件
  - [ ] ParameterViewer 组件
  - [ ] 前后端集成

### 验收标准
- [ ] 用户能实时看到 Agent 推理过程
- [ ] 工具调用显示参数和结果
- [ ] HIL 介入时弹出确认框
- [ ] SSE 断线能自动重连

---

## 🛡️ Phase 5: 安全加固 (Week 3) 🔴 P0

### 目标
实施关键安全加固措施。

### 任务清单

- [ ] **5.1 路径安全**
  - [ ] `read_file` 白名单限制
  - [ ] 路径遍历防护
  - [ ] 安全测试

- [ ] **5.2 并发安全**
  - [ ] SkillRegistry 加锁保护
  - [ ] 原子替换实现
  - [ ] 并发测试

- [ ] **5.3 Token 精确计数**
  - [ ] 集成 tiktoken
  - [ ] 替代字符估算

- [ ] **5.4 Row Level Security**
  - [ ] 启用 RLS 策略
  - [ ] 应用层上下文设置
  - [ ] 安全测试

### 验收标准
- [ ] `read_file` 无法读取允许目录外的文件
- [ ] 并发加载 Skills 不会导致崩溃
- [ ] Token 计数误差 < 1%
- [ ] 用户无法访问其他用户的数据

---

## 🧪 Phase 6: 测试与优化 (Week 7-8) ⚪ P2

### 目标
达到 80%+ 测试覆盖率并优化性能。

### 任务清单

- [ ] **6.1 单元测试**
  - [ ] 后端 pytest 测试（目标 80%+）
  - [ ] 前端 vitest 测试（目标 80%+）
  - [ ] Mock LLM 响应

- [ ] **6.2 集成测试**
  - [ ] API 端点测试
  - [ ] 数据库集成测试
  - [ ] Agent 执行流程测试

- [ ] **6.3 E2E 测试**
  - [ ] Playwright 配置
  - [ ] 5 个关键场景测试
  - [ ] 回放模式测试

- [ ] **6.4 性能优化**
  - [ ] 数据库查询优化
  - [ ] 前端虚拟滚动
  - [ ] SSE 事件去重

- [ ] **6.5 CI/CD**
  - [ ] GitHub Actions 配置
  - [ ] 自动测试触发
  - [ ] 自动部署流程

### 验收标准
- [ ] 单元测试覆盖率 ≥ 80%
- [ ] 所有 E2E 场景通过
- [ ] P95 响应时间 < 5s
- [ ] CI/CD 流程打通

---

## 📊 优先级矩阵

| 任务 | P0 | P1 | P2 | 依赖 |
|-----|----|----|----|----|
| 项目脚手架 | ✅ | | | |
| Docker Compose | ✅ | | | 项目脚手架 |
| 数据库初始化 | ✅ | | | Docker Compose |
| LLM Factory | ✅ | | | |
| 核心 Tools | ✅ | | | LLM Factory |
| 前端基础组件 | ✅ | | | |
| Memory 系统 | ✅ | | | 数据库初始化 |
| 安全加固 | ✅ | | | Memory 系统 |
| Skills 系统 | | ✅ | | Memory 系统 |
| 可观测性 | | ✅ | | Skills 系统 |
| 测试与优化 | | | ✅ | 可观测性 |

---

## 🎯 成功指标

### 面试成功率
- [ ] 能演示完整的复杂任务处理流程
- [ ] 能展示 HIL 人工介入机制
- [ ] 能解释 Memory 三层架构
- [ ] 能展示 Skills 加载机制

### 功能完整度
- [ ] P0 任务 100% 完成
- [ ] P1 任务 ≥ 80% 完成
- [ ] P2 任务可选

### 代码质量
- [ ] 测试覆盖率 ≥ 80%
- [ ] 无高危安全漏洞
- [ ] 代码规范检查通过

---

## 📅 时间线汇总

| Phase | 周期 | 关键交付物 |
|-------|------|-----------|
| Phase 1: 基础设施 | Week 1-2 | Docker Compose + 骨架代码 |
| Phase 2: Memory 系统 | Week 2-3 | Memory 中间件 + Token 管理 |
| Phase 3: 安全加固 | Week 3 | 安全测试通过 |
| Phase 4: Skills 系统 | Week 3-4 | Skill Manager + 2 个示例 Skill |
| Phase 5: 可观测性 | Week 4-5 | SSE 推送 + 时间轴可视化 |
| Phase 6: HIL 机制 | Week 5-6 | HIL 中断 + 确认模态框 |
| Phase 7: 测试与优化 | Week 7-8 | 测试覆盖率 80%+ |

---

**下一步**: 从 Phase 1 任务 1.1 开始执行。
