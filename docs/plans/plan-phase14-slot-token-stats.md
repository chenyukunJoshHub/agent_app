# Phase 14 — Slot Token 实时统计功能

## 目标

实现前端实时显示 10 个 Slot 的 prompt 内容和对应的 token 消耗统计，帮助用户理解 Context Window 的使用情况。

基于 Prompt v20 §1.2 十大子模块与 Context Window 分区设计。

## 架构文档参考

- Prompt v20 §1.2 十大子模块与 Context Window 分区
- Prompt v20 §1.3 Token 预算管理

## 测试用例清单（TDD 先写）

### 后端：SlotContentTracker 类
- [x] SlotContent 自动计算 token 数量
- [x] SlotContentTracker 添加 Slot
- [x] SlotContentTracker 获取 Slot
- [x] SlotContentTracker 构建 Snapshot
- [x] SlotSnapshot 包含所有 Slot 信息
- [x] SlotSnapshot.to_dict() 导出正确格式
- [x] 空 content 返回 0 tokens
- [x] enabled=false 的 Slot 不计入 total_tokens

### 后端：build_system_prompt Slot 跟踪
- [x] track_slots=True 返回 (prompt, snapshot) 元组
- [x] track_slots=False 仅返回 prompt 字符串
- [x] system Slot 正确跟踪
- [x] tools Slot 正确跟踪
- [x] few_shot Slot 正确跟踪
- [x] episodic Slot 正确跟踪（启用时）
- [x] skill_registry Slot 正确跟踪
- [x] total_tokens 计算正确（仅 enabled Slots）
- [x] snapshot.timestamp 为最近时间

### 后端：GET /session/{id}/slots API
- [x] 返回 200 状态码
- [x] session_id 匹配请求
- [x] 返回预期 Slot 名称
- [x] 每个 Slot 包含必需字段（name, display_name, content, tokens, enabled）
- [x] total_tokens 等于 enabled Slot tokens 之和
- [x] system Slot 有内容
- [x] few_shot Slot 包含示例
- [x] timestamp 在最近一分钟内
- [x] 处理特殊字符 session_id
- [x] 响应格式匹配 schema

### 前端：SlotDetail 组件
- [x] 渲染 Slot 名称和 token 计数
- [x] 显示启用/禁用状态
- [x] 展开时显示完整内容
- [x] 折叠时显示预览（截断）
- [x] 空 content 显示"暂无内容"
- [x] 预览模式不显示展开按钮
- [x] tokens 格式化（带单位）
- [x] 长内容正确截断
- [x] 点击切换展开/折叠
- [x] content 包含换行符时正确显示
- [x] tokens=0 时显示正确
- [x] enabled=false 时显示禁用样式
- [x] display_name 正确显示
- [x] 预览模式下 content 长度限制

### 前端：ContextWindowPanel 增强
- [x] 显示视图切换按钮
- [x] 切换到详情视图时显示 SlotDetailList
- [x] 切换回概览视图时隐藏详情
- [x] 按钮文本随视图状态变化
- [x] 加载 Slot 详情数据
- [x] 显示加载状态

### E2E：Slot 详情功能
- [x] 显示 Context Window 面板
- [x] 默认显示 Slot 分解
- [x] 显示 Slot 数量
- [x] 显示 token 信息
- [x] 可切换概览/详情视图
- [x] 详情视图显示 Slot 内容
- [x] 每个 Slot 显示 token 计数
- [x] 显示总体进度条
- [x] 显示统计行（输入预算、输出预留、已使用）
- [x] 处理空 Slot 状态
- [x] 可展开/折叠 Slot 详情
- [x] API 返回 Slot 详情
- [x] API 返回正确 Slot 结构
- [x] API 正确计算总 tokens

## 实现步骤（TDD 顺序）

### Step 1 — 后端 Slot 跟踪核心
- [x] 创建 `backend/app/prompt/slot_tracker.py`
- [x] 实现 `SlotContent` dataclass（自动 token 计算）
- [x] 实现 `SlotContentTracker` 类
- [x] 实现 `SlotSnapshot` 类
- [x] 实现 `count_tokens()` 函数（基于 tiktoken）
- [x] 编写 14 个单元测试
- [x] 验证 100% 覆盖率

### Step 2 — build_system_prompt 增强
- [x] 修改 `backend/app/prompt/builder.py`
- [x] 添加 `track_slots` 参数（默认 True）
- [x] 在 build 过程中收集 Slot 内容
- [x] 返回 (prompt, snapshot) 元组或单独 prompt
- [x] 保持向后兼容（build_system_prompt_legacy）
- [x] 编写 13 个单元测试
- [x] 验证 Slot 收集正确性

### Step 3 — API 端点实现
- [x] 在 `backend/app/api/context.py` 添加端点
- [x] 实现 `GET /session/{id}/slots`
- [x] 返回 SlotDetailsResponse
- [x] 集成 SkillManager 和 SlotSnapshot
- [x] 编写 10 个 API 集成测试
- [x] 验证响应格式和内容

### Step 4 — 前端类型定义
- [x] 更新 `frontend/src/types/context-window.ts`
- [x] 添加 `SlotDetail` 接口
- [x] 添加 `SlotDetailsResponse` 接口
- [x] 添加 `SlotDetailsEvent` SSE 事件类型

### Step 5 — 前端组件实现
- [x] 创建 `frontend/src/components/SlotDetail.tsx`
- [x] 创建 `frontend/src/components/SlotDetailList.tsx`
- [x] 更新 `frontend/src/components/ContextWindowPanel.tsx`
- [x] 添加视图切换逻辑
- [x] 编写 15 个组件测试
- [x] 验证交互和渲染

### Step 6 — 前端状态管理和 API
- [x] 更新 `frontend/src/hooks/use-context-window.ts`
- [x] 添加 `fetchSlotDetails` 方法
- [x] 添加 `slotDetails` 状态
- [x] 更新 `frontend/src/lib/api-config.ts`
- [x] 添加 `getSessionSlotsUrl` 函数

### Step 7 — E2E 测试
- [x] 创建 `tests/e2e/08-slot-details.spec.ts`
- [x] 编写 11 个 E2E 测试
- [x] 验证完整用户流程
- [x] 验证 API 集成

### Step 8 — 覆盖率验证
```bash
# 后端测试
cd tests/backend && pytest --cov=../../app/prompt --cov-report=term-missing

# 前端测试
cd frontend && npm test

# E2E 测试
cd frontend && npx playwright test tests/e2e/08-slot-details.spec.ts --headed
```

## 完成标准

- [x] 所有 63 个测试用例实现且通过
- [x] 覆盖率 ≥ 95%（后端新代码 100%）
- [x] findings.md 中记录所有技术决策
- [x] progress.md 更新本阶段会话日志
- [x] task_plan.md 阶段状态更新为 ✅ done

## 技术决策记录

1. **Slot 跟踪设计**: 使用专门的 SlotContentTracker 类集中管理 Slot 状态
   - **Why**: 解耦 Slot 数据收集逻辑，便于测试和复用
   - **How to apply**: 后续添加新 Slot 时在 Tracker 中注册

2. **向后兼容策略**: build_system_prompt 默认启用跟踪，提供 track_slots 参数控制
   - **Why**: 确保现有代码不受影响，新功能可选启用
   - **How to apply**: 所有调用 build_system_prompt 的地方可平滑升级

3. **视图切换模式**: 前端提供概览/详情两种视图
   - **Why**: 概览用于快速查看状态，详情用于深入调试
   - **How to apply**: 用户可根据需要切换视图

4. **Token 计算时机**: 在 SlotContent 添加时自动计算（__post_init__）
   - **Why**: 确保数据一致性，避免手动计算错误
   - **How to apply**: 所有 Slot content 变更都会重新计算

5. **API 端点设计**: GET /session/{id}/slots 独立于 /context 端点
   - **Why**: 分离关注点，/context 返回预算配置，/slots 返回实际内容
   - **How to apply**: 前端可按需调用，避免不必要的数据传输

## 遗留问题

- P1: SSE 实时推送 Slot 更新（需要 Agent 运行时集成）
- P1: 会话历史 Slot 的实际内容跟踪
- P2: 历史趋势可视化（Slot 使用量变化）

## 创建的文件（10 个）

### 后端（4 个）
1. `backend/app/prompt/slot_tracker.py` - 166 行
2. `tests/backend/unit/prompt/test_slot_tracker.py` - 172 行
3. `tests/backend/unit/prompt/test_builder_slot_tracking.py` - 185 行
4. `tests/backend/unit/api/test_context_slots.py` - 182 行

### 前端（6 个）
1. `frontend/src/components/SlotDetail.tsx` - 175 行
2. `frontend/src/components/SlotDetailList.tsx` - 内联
3. `frontend/src/components/ContextWindowPanel.tsx` - 更新
4. `frontend/src/hooks/use-context-window.ts` - 更新
5. `frontend/src/types/context-window.ts` - 更新
6. `frontend/src/lib/api-config.ts` - 更新

### E2E（1 个）
1. `tests/e2e/08-slot-details.spec.ts` - 252 行

## 修改的文件（6 个）
1. `backend/app/api/context.py` - 新增 GET /session/{id}/slots 端点
2. `backend/app/prompt/builder.py` - 增强 Slot 跟踪功能
3. `frontend/src/lib/api-config.ts` - 新增 getSessionSlotsUrl
4. `frontend/src/components/ContextWindowPanel.tsx` - 集成详情视图
5. `frontend/src/hooks/use-context-window.ts` - 新增 fetchSlotDetails
6. `frontend/src/types/context-window.ts` - 扩展类型定义
