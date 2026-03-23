# Phase 01 — 数据库初始化

## 目标

搭建 PostgreSQL 数据库层，实现 LangGraph 所需的 checkpoint 和 store 存储机制，确保短期记忆和长期记忆的基础设施就绪。

## 架构文档参考

- Memory v5 §2.3 存储层初始化
- Memory v5 §2.10 存储表设计
- Agent v13 §1.7 存储表设计

## 测试用例清单（TDD 先写）

### db/postgres.py — create_stores()
- [ ] AsyncPostgresSaver 初始化成功
- [ ] AsyncPostgresStore 初始化成功
- [ ] 连接参数正确 (autocommit=True, dict_row, prepare_threshold=0)
- [ ] setup() 方法自动建表

### Migration 文件
- [ ] 001_agent_traces.sql 执行成功
- [ ] agent_traces 表结构正确
- [ ] 索引创建成功

### 连接测试
- [ ] 能成功连接 PostgreSQL
- [ ] 能执行基本 CRUD 操作
- [ ] checkpoint 读写正常
- [ ] store 读写正常

## 实现步骤（TDD 顺序）

### Step 1 — 环境配置
- 配置 .env.example
- 配置 docker-compose.yml (PostgreSQL 服务)
- 验证数据库连接

### Step 2 — Migration 文件
- 创建 001_agent_traces.sql
- 定义 agent_traces 表结构
- 添加索引

### Step 3 — postgres.py 实现
- 写测试，确认 RED
- 实现 create_stores()
- 配置 psycopg3 连接参数
- 确认 GREEN

### Step 4 — 验证
- 运行所有测试
- 验证 checkpoint 功能
- 验证 store 功能

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] AsyncPostgresSaver 正常工作
- [ ] AsyncPostgresStore 正常工作
- [ ] agent_traces 表创建成功
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done
