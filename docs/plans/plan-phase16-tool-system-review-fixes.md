# Phase 16 — 工具系统审查修复（tool-system-review-fixes）

## 目标

根据 `docs/review/tool-system-review-2026-03-24.md` 中的 36 项发现，按优先级修复工具系统的安全、性能、架构和测试问题。

**审查来源**: `docs/review/tool-system-review-2026-03-24.md`
**总发现**: 36 项（0 Critical · 9 High · 17 Medium · 10 Low）

---

## 修复阶段划分

### Phase 16.1 — P0 安全与架构核心修复（High）
> 优先级最高，直接影响安全性和架构正确性

### Phase 16.2 — P1 正确性与可维护性修复（Medium）
> 影响正确性、并发安全和可维护性

### Phase 16.3 — P2 代码质量改善（Low）
> 代码质量、可扩展性和规范化

---

## 架构文档参考

- Agent v13 §1.12 — 工具系统架构（Management Layer、ToolNode）
- Agent v13 §1.13 — HIL 完整设计
- Agent v13 §2.2 — Workflow 映射
- Agent v13 §2.4 — SSE 流式架构
- Skill v3 §1.4 — Skill Protocol
- Skill v3 §2.2 — read_file @tool
- Prompt v20 §1.2 — Token 预算管理

---

## Phase 16.1 — P0 安全与架构核心修复

### Step 1: SEC-005 — fetch_url 添加 SSRF 防护

**位置**: `backend/app/tools/fetch.py:16-54`

**测试用例（TDD 先写）**:
- [ ] 允许正常 http/https URL
- [ ] 拒绝非 http/https 协议（ftp://, file://, gopher://）
- [ ] 拒绝私有 IP 地址（10.x.x.x, 172.16.x.x, 192.168.x.x）
- [ ] 拒绝环回地址（127.0.0.1, ::1）
- [ ] 拒绝 link-local / 云元数据地址（169.254.169.254）
- [ ] DNS 解析后 IP 检查（防止 DNS rebinding）
- [ ] URL 缺少 scheme 时默认拒绝
- [ ] 空 URL 或无效 URL 格式拒绝

**实现步骤**:
1. 新建 `backend/app/tools/_url_safety.py` — SSRF 防护模块
2. 实现 `_is_safe_url(url: str) -> bool`（私有 IP 过滤 + 协议白名单）
3. 修改 `fetch.py` 的 `fetch_url` 工具，调用前检查
4. 将 fetch_url 的 `allowed_decisions` 改为 `["ask"]`（不再自动 allow）
5. 新建 `tests/backend/unit/tools/test_url_safety.py`

**影响文件**:
- `backend/app/tools/fetch.py`（修改）
- `backend/app/tools/_url_safety.py`（新建）
- `backend/app/tools/base.py`（修改 — fetch_url 的 ToolMeta 更新）
- `backend/app/tools/registry.py`（修改 — fetch_url 的 ToolMeta 更新）
- `tests/backend/unit/tools/test_url_safety.py`（新建）

---

### Step 2: SEC-002 — 修复自定义工具默认策略

**位置**: `backend/app/agent/langchain_engine.py:182-184`

**测试用例**:
- [ ] 传入外部工具应被标记为 `effect_class="external_write"`
- [ ] 传入外部工具的 `allowed_decisions` 应为 `["ask", "deny"]`
- [ ] 已知的内置工具不受影响

**实现步骤**:
1. 修改 `langchain_engine.py` 中外部工具的 ToolMeta 赋值逻辑
2. 更新 `tests/backend/unit/tools/test_build_tool_registry.py` 添加外部工具测试

**影响文件**:
- `backend/app/agent/langchain_engine.py`（修改）
- `tests/backend/unit/tools/test_build_tool_registry.py`（修改）

---

### Step 3: SEC-001 — PolicyEngine session grant 添加撤销机制

**位置**: `backend/app/tools/policy.py:34-35`

**测试用例**:
- [x] `grant_session()` 后 `decide()` 应返回 "allow"
- [x] `revoke_session()` 后 `decide()` 应恢复原始决策
- [x] 对 `effect_class="destructive"` 类工具 `grant_session()` 应被拒绝或立即撤销
- [x] `revoke_session()` 对未 grant 的工具不应抛出异常
- [x] `get_granted_tools()` 返回当前会话所有已 grant 的工具列表

**实现步骤**:
1. `PolicyEngine` 添加 `revoke_session(tool_name: str)` 方法
2. `PolicyEngine` 添加 `get_granted_tools() -> set[str]` 方法
3. 修改 `decide()` 方法：destructive 工具不使用 session grant
4. 可选：添加 TTL 支持（grant 时记录时间戳，超时自动撤销）
5. 更新 `tests/backend/unit/tools/test_policy_engine.py`

**当前实现边界（2026-03-30）**:
- `session grant/revoke` 已形成产品闭环，但授权状态仅保存在运行时 `PolicyEngine` 内存
- 不持久化到 PostgreSQL / checkpointer；因此 backend 重启后 grant 会丢失
- 当前阶段接受该边界，后续若要跨重启保留，再单独设计持久化策略

**影响文件**:
- `backend/app/tools/policy.py`（修改）
- `tests/backend/unit/tools/test_policy_engine.py`（修改）

---

### Step 4: ARCH-002 — 删除 ToolRegistry 死代码

**位置**: `backend/app/tools/registry.py:15-126`

**测试用例**:
- [ ] 删除后 `build_tool_registry()` 仍正常工作
- [ ] 删除后所有现有测试通过
- [ ] `__init__.py` 中不再导出 `ToolRegistry`

**实现步骤**:
1. 删除 `registry.py` 中的 `ToolRegistry` 类（保留 `build_tool_registry()`）
2. 从 `backend/app/tools/__init__.py` 移除 `ToolRegistry` 导出
3. 删除所有引用 `ToolRegistry` 的代码（如有）
4. 运行全量测试确认无回归
5. TEST-001 对应的 `test_tool_registry.py` 无需创建（死代码已删除）

**影响文件**:
- `backend/app/tools/registry.py`（修改 — 删除 ToolRegistry 类）
- `backend/app/tools/__init__.py`（修改 — 移除导出）

---

### Step 5: ARCH-005 — PolicyEngine 接入工具执行路径（Management Layer 激活）

**位置**: `backend/app/agent/langchain_engine.py:176-187`

> **设计决策（2026-03-30 更新）**:
> 基于 LangChain 官方 Python middleware / HITL 文档，优先采用 **middleware 接线**，
> 不重写主 `create_agent(...)` 路径，也不自定义替换 LangGraph 默认 ToolNode。
>
> 原因：
> 1. 官方 `AgentMiddleware` 已提供 `after_model` / `wrap_tool_call` 扩展点，足以承载管理层决策与执行层治理
> 2. 官方 `HumanInTheLoopMiddleware` 本身就是在 `after_model` 中基于 `interrupt(...)` 暂停执行
> 3. 当前项目已深度依赖 LangChain `create_agent` + middleware + checkpointer，继续沿这条主路线风险最低
>
> 结论：
> - **PolicyEngine 接入点** = `after_model`
> - **Idempotency / retry / error normalization 接入点** = `awrap_tool_call`
> - **HIL 元数据桥接** = 读取 LangGraph `__interrupt__` payload，不再把自定义 HIL middleware 当作执行拦截器

**推荐设计（严谨版，保持 LangChain 主路线）**:

```text
LLM 产出 AIMessage(tool_calls)
  ↓
PolicyHITLMiddleware.after_model
  · 逐个 tool_call 读取 ToolMeta
  · PolicyEngine.decide(...) → allow / ask / deny
  · deny  : 从 AIMessage.tool_calls 移除，并注入 error ToolMessage
  · ask   : 基于 LangGraph interrupt(...) 触发官方 HIL 暂停
  · allow : 保留 tool_call，进入工具执行节点
  ↓
ToolExecutionMiddleware.awrap_tool_call
  · ToolManager.get_meta(...)
  · idempotent 工具先 check_and_mark()
  · 已执行过 → 返回 skipped ToolMessage
  · 未执行过 → 按 ToolMeta.retry/backoff 调 handler(request)
  · 异常 → 统一归一为 ToolMessage(error)
  ↓
真实 BaseTool 执行
```

**测试用例**:
- [x] deny 决策的工具调用应返回错误消息
- [x] ask 决策的工具调用应触发 LangGraph interrupt，并在 SSE 中带出真实 `tool_name` / `args`
- [x] allow 决策的工具调用应正常执行
- [x] 执行前应检查 `IdempotencyStore`
- [x] 已 revoke 的工具不应被 session grant 缓存影响
- [x] `grant_session()` 后同一工具本轮应立即从 ask 变为 allow（无需重建 agent）
- [x] 多个 tool_call 混合批次中，deny 不应阻断 allow；ask 应只暂停需要审批的调用
- [x] reject 后应注入 error ToolMessage，且写工具副作用不执行
- [x] 多 action HIL interrupt 的 SSE payload 应完整暴露 `action_requests`，前端不可只展示首个工具
- [x] 过期 interrupt 不应继续被 `/chat/resume` 恢复
- [x] `/chat/resume` 执行失败后 interrupt 状态应回滚到 `pending`
- [x] 移动端应有 session grant 撤销入口，不能只依赖右侧 ContextPanel

**实现步骤**:
1. 创建 `backend/app/agent/middleware/tool_policy.py`
   - `PolicyHITLMiddleware(AgentMiddleware)`
   - 在 `after_model()` 中扫描最后一个 `AIMessage.tool_calls`
   - 对每个调用执行 `ToolManager.get_meta()` + `PolicyEngine.decide()`
2. `after_model()` 的具体行为
   - `deny`:
     - 从待执行 `tool_calls` 中移除该调用
     - 追加 `ToolMessage(status="error")`
     - 记录 trace_event：`policy_decision=deny`
   - `ask`:
     - 构造 LangChain HITL request
     - 调用 LangGraph `interrupt(...)`
     - 由 checkpointer 原生持久化断点
   - `allow`:
     - 保留原始 tool_call
3. 创建 `backend/app/agent/middleware/tool_execution.py`
   - `ToolExecutionMiddleware(AgentMiddleware)`
   - 在 `awrap_tool_call()` 中实现：
     - idempotent 工具的 `IdempotencyStore.check_and_mark()`
     - 基于 `ToolMeta.max_retries/backoff` 的有限重试
     - 异常归一为 `ToolMessage(error)`
4. 修改 `backend/app/agent/langchain_engine.py`
   - 不再丢弃 `tool_manager` / `policy_engine`
   - 将两者注入 `PolicyHITLMiddleware` / `ToolExecutionMiddleware`
   - 保持 `create_agent(...)` + middleware 架构不变
5. 调整 HIL 接线
   - 删除旧 `HILMiddleware` 残留实现
   - `/chat/resume` 直接使用 chat 层 helper 处理 interrupt 状态更新与前端事件桥接
   - `/chat` 的 `__interrupt__` 处理改为直接解析 interrupt payload 中的 `action_requests`
   - SSE `hil_interrupt` 事件应包含真实 `tool_name` / `args` / `allowed_decisions`
6. 调整 `/chat/resume`
   - 继续使用 `Command(resume=...)` 恢复
   - 优先从 interrupt payload / checkpoint 恢复工具元数据
   - `send_email` 等非幂等写工具继续保留 resume-time dedupe guard
7. 新建测试
   - `tests/backend/unit/agent/test_tool_policy_middleware.py`
   - `tests/backend/unit/agent/test_tool_execution_middleware.py`
   - 必要时补 `tests/backend/integration/test_chat_hil_policy_path.py`

**影响文件**:
- `backend/app/agent/middleware/tool_policy.py`（新建）
- `backend/app/agent/middleware/tool_execution.py`（新建）
- `backend/app/agent/langchain_engine.py`（修改 — 保留并注入 ToolManager / PolicyEngine）
- `backend/app/api/chat.py`（修改 — 解析真实 interrupt payload，发 enriched HIL SSE）
- `backend/app/agent/middleware/hil.py`（删除 — 旧 HIL 残留逻辑并入 chat 层 helper）
- `backend/app/observability/interrupt_store.py`（修改 — interrupt 过期校验）
- `tests/backend/unit/agent/test_tool_policy_middleware.py`（新建）
- `tests/backend/unit/agent/test_tool_execution_middleware.py`（新建）
- `tests/backend/unit/observability/test_interrupt_store.py`（新建）
- `frontend/src/components/ConfirmModal.tsx`（修改 — 多 action 审批视图 + grant 限制）
- `frontend/src/components/SessionGrantStrip.tsx`（新建 — 移动端 revoke 入口）
- `tests/components/ConfirmModal.test.tsx`（修改）
- `tests/components/SessionGrantStrip.test.tsx`（新建）

**依赖**: Step 2（SEC-002）、Step 3（SEC-001）需先完成

**中间件顺序（建议）**:
1. `MemoryMiddleware`
2. `SummarizationMiddleware`
3. `TraceMiddleware`
4. `PolicyHITLMiddleware`
5. `ToolExecutionMiddleware`

说明：
- 官方文档说明 `after_model` 按 **逆序** 执行，因此 `TraceMiddleware` 放在 `PolicyHITLMiddleware` 前面，才能看到“策略修正后的 tool_calls”
- `wrap_tool_call` 按 **列表顺序嵌套**，`ToolExecutionMiddleware` 放在最后即可最贴近真实工具执行

**为何不选自定义 ToolNode**:
- 会偏离 LangChain `create_agent` 默认图结构，后续升级 LangChain / LangGraph 时维护成本更高
- 当前需求本质是“治理与拦截”，官方 middleware 已提供一等支持
- 只有在未来确实需要 DAG 批调度 / 跨工具依赖图 / 自定义并发批次时，才值得下沉到 ToolNode / Graph 层

---

### Step 6: TEST-007/008 — 修复 E2E 工具追踪测试

**位置**: `tests/e2e/03-tool-trace.spec.ts:11-38`

**测试用例**:
- [ ] 移除所有 `waitForTimeout()` 固定等待
- [ ] 替换为基于状态的断言（`toBeVisible({ timeout: 15000 })`）
- [ ] 工具调用应验证追踪面板中出现工具调用卡片（`data-testid="tool-call-card"`）
- [ ] 工具调用卡片应包含工具名称文本

**实现步骤**:
1. 修改 `tests/e2e/03-tool-trace.spec.ts`
2. 删除 `waitForTimeout(5000)`
3. 添加工具调用追踪验证断言
4. 运行 E2E 测试确认通过

**影响文件**:
- `tests/e2e/03-tool-trace.spec.ts`（修改）

---

### Step 7: TEST-001 — ToolRegistry 已在 Step 4 删除，无需单独测试

> ARCH-002 删除 ToolRegistry 后，TEST-001 自动解决。

---

## Phase 16.2 — P1 正确性与可维护性修复

### Step 8: SEC-003 + SEC-004 + PERF-003 — IdempotencyStore 加锁、LRU 淘汰、接入执行路径

**位置**: `backend/app/tools/idempotency.py`

**测试用例**:
- [ ] 并发调用 `check_and_mark()` 无竞态条件（threading 测试）
- [ ] 超过 `max_size` 时 LRU 淘汰最旧条目
- [ ] 淘汰后被淘汰的 key 再次调用返回 False（未被标记过）
- [ ] 空 key 处理（拒绝空字符串）
- [ ] Unicode key 处理
- [ ] `check_and_mark()` 在 ToolNode 执行前被调用

**实现步骤**:
1. 重写 `IdempotencyStore`：使用 `OrderedDict` + `threading.Lock`
2. 添加 `max_size` 参数（默认 10,000）
3. 实现 LRU 淘汰逻辑
4. 在 `PolicyEnforcedToolNode`（Step 5 创建）中集成 `check_and_mark()`
5. 更新 `tests/backend/unit/tools/test_idempotency.py`

**影响文件**:
- `backend/app/tools/idempotency.py`（修改）
- `backend/app/agent/policy_tool_node.py`（修改 — Step 5 创建后）
- `tests/backend/unit/tools/test_idempotency.py`（修改）

---

### Step 9: SEC-006 — read_skill_content 添加路径边界检查

**位置**: `backend/app/skills/manager.py:522-535`

**测试用例**:
- [ ] 路径包含 `..` 穿越到 skills_dir 之外应被拒绝
- [ ] 绝对路径指向 skills_dir 之外应被拒绝
- [ ] 路径为 skills_dir 之内的合法路径应通过

**实现步骤**:
1. 在 `read_skill_content()` 中添加 `resolved.is_relative_to(skills_dir)` 校验
2. 更新 `tests/backend/unit/skills/test_manager.py`

**影响文件**:
- `backend/app/skills/manager.py`（修改）
- `tests/backend/unit/skills/test_manager.py`（修改）

---

### Step 10: ARCH-007 — 统一 SkillManager 单例使用方式

**位置**: `backend/app/tools/readonly/skill_loader.py:27-29`

**测试用例**:
- [ ] 单例失败时不应创建游离实例（应抛出明确错误）
- [ ] fixture 注入预配置 SkillManager 测试通过
- [ ] monkeypatch mock `get_instance` 测试通过

**实现步骤**:
1. 修改 `langchain_engine.py` 改用 `SkillManager.get_instance(skills_dir=...)`
2. 删除 `skill_loader.py` 中的 fallback 构造
3. 用 fixture 重构 `test_activate_skill.py` 中的单例 reset
4. 更新 `tests/backend/unit/tools/test_activate_skill.py`

**影响文件**:
- `backend/app/tools/readonly/skill_loader.py`（修改）
- `backend/app/agent/langchain_engine.py`（修改）
- `tests/backend/unit/tools/test_activate_skill.py`（修改）

---

### Step 11: ARCH-008 — TraceMiddleware 移除直接状态写入

**位置**: `backend/app/agent/middleware/trace.py:195`

**测试用例**:
- [ ] TraceMiddleware 不再直接修改 state
- [ ] 预算值从 `DEFAULT_BUDGET` 配置读取
- [ ] 状态更新通过返回值传递

**实现步骤**:
1. 修改 `TraceMiddleware` 通过返回值传递状态更新
2. 从配置中读取预算值
3. 更新对应测试

**影响文件**:
- `backend/app/agent/middleware/trace.py`（修改）
- `tests/backend/unit/agent/middleware/test_trace.py`（修改）

---

### Step 12: PERF-004 — build_snapshot 添加文件 mtime 缓存

**位置**: `backend/app/skills/manager.py:301`

**测试用例**:
- [ ] 首次 `build_snapshot` 执行全量扫描
- [ ] 第二次 `build_snapshot`（文件未变）使用缓存
- [ ] 文件修改后 `build_snapshot` 重新扫描
- [ ] 新增文件后 `build_snapshot` 重新扫描

**实现步骤**:
1. 在 `SkillManager` 中添加 `_scan_cache: dict[str, float]`（path → mtime）
2. `scan()` 方法中对比 mtime，未变则跳过
3. 更新 `tests/backend/unit/skills/test_manager.py`

**影响文件**:
- `backend/app/skills/manager.py`（修改）
- `tests/backend/unit/skills/test_manager.py`（修改）

---

### Step 13: TEST-003/004/005/006/010 — 补充测试覆盖

**测试用例清单**:

#### TEST-003 — PolicyEngine 补充测试
- [x] grant 对 deny 的覆盖行为测试
- [x] grant 后 `hil_required` 变化测试
- [x] 多次 grant 同一工具的幂等性

#### TEST-004 — ToolManager get_meta 返回副本
- [x] 修改返回的 ToolMeta 不影响内部存储
- [x] 返回的 ToolMeta 与内部存储值相等

#### TEST-005 — activate_skill 隔离修复
- [x] fixture 注入预配置 SkillManager
- [x] monkeypatch mock `get_instance`

#### TEST-006 — activate_skill 错误路径
- [x] `scan()` 异常时的行为
- [x] 目录不存在时的行为
- [x] 空 name 参数时的行为

#### TEST-010 — PolicyEngine × ToolManager 集成测试
- [x] 遍历所有注册工具，验证 `decide()` 不抛出 ValueError
- [x] 验证每个工具的 `effect_class` 对应正确的默认决策

**影响文件**:
- `tests/backend/unit/tools/test_policy_engine.py`（修改）
- `tests/backend/unit/tools/test_tool_manager.py`（修改）
- `tests/backend/unit/tools/test_activate_skill.py`（修改）
- `tests/backend/unit/tools/test_integration.py`（新建）

---

## Phase 16.3 — P2 代码质量改善

### Step 14: SEC-007 — PII 和工具参数脱敏

**位置**: `backend/app/tools/send_email.py:40`, `backend/app/agent/middleware/trace.py:173`

**实现**:
- [x] 日志中脱敏邮件地址（`u***@example.com`）
- [x] SSE 事件中过滤敏感工具参数

---

### Step 15: SEC-008 — 路径黑名单补充

**位置**: `backend/app/tools/file.py:37`

**实现**:
- [x] 补充 `.env`、`.env.*`、`*.key`、`*.pem` 到黑名单
- 或改为白名单策略

---

### Step 16: SEC-009 — 输入校验

**位置**: `backend/app/tools/send_email.py`, `backend/app/tools/fetch.py`

**实现**:
- 校验邮件格式（防止邮件头注入，过滤 `\n\r`）
- fetch_url scheme 限制（已在 Step 1 的 SSRF 防护中覆盖）

---

### Step 17: PERF-001 — Level 3 截断路径使用二分搜索

**位置**: `backend/app/skills/manager.py:336-387`

**实现**:
- [x] 将线性尝试替换为二分搜索，找到最大可容纳的 skill 数量

---

### Step 18: PERF-002 — import yaml 移至文件顶层

**位置**: `backend/app/skills/manager.py:194`

**实现**:
- [x] `import yaml` 移至文件顶部

---

### Step 19: PERF-005 — read_skill_content 使用索引

**位置**: `backend/app/skills/manager.py:522-535`

**实现**:
- [x] `scan()` 时构建 `dict[str, SkillDefinition]` 索引
- [x] `read_skill_content()` 使用索引查找替代线性搜索

---

### Step 20: PERF-006 — ExecutionTracePanel 性能优化

**位置**: `frontend/src/components/ExecutionTracePanel.tsx:95-97`

**实现**:
- `filter/sort/map` 用 `useMemo` 缓存
- `toggle/toggleSlot` 用 `useCallback`

---

### Step 21: PERF-007 — slot_snapshot.to_dict() 调用缓存

**位置**: `backend/app/agent/langchain_engine.py:240,276`

**实现**:
- 缓存到局部变量 `slot_dict = slot_snapshot.to_dict()`

---

### Step 22: ARCH-001 — 目录结构对齐

**位置**: `backend/app/tools/`

**实现**:
- 将工具文件迁移至 `readonly/`、`write/`、`orchestration/` 子目录
- [x] 或更新架构文档以反映当前结构

---

### Step 23: ARCH-003 — PolicyEngine 构造函数添加 store 参数

**位置**: `backend/app/tools/policy.py:13`

**实现**:
- 添加 `store=None` 可选参数保持前向兼容

---

### Step 24: ARCH-006 — IdempotencyStore 持久化标注

**位置**: `backend/app/tools/idempotency.py`

**实现**:
- [x] 在类文档字符串中标注为内存存根
- 或接入 PostgreSQL checkpointer

---

### Step 25: ARCH-009 — 移除顶层无条件导入 send_email

**位置**: `backend/app/tools/__init__.py:14`

**实现**:
- [x] 从 `__init__.py` 移除 `send_email` 导入
- [x] 调用方直接导入

---

### Step 26: ARCH-010 — BackoffConfig 类型定义

**位置**: `backend/app/tools/base.py:16`

**实现**:
- [x] 定义 `BackoffConfig(TypedDict)` 替代裸 `dict`

---

### Step 27: TEST-009 — build_tool_registry 补充测试

**位置**: `tests/backend/unit/tools/test_build_tool_registry.py`

**测试用例**:
- [x] 导入失败时的错误处理
- [x] 多次调用 build_tool_registry 的幂等性
- [x] BaseTool 实例类型验证

---

## 完成标准

### Phase 16.1 完成标准
- [ ] SSRF 防护测试全部通过
- [ ] 自定义工具使用限制性策略
- [ ] Session grant 有撤销机制
- [ ] ToolRegistry 死代码已删除
- [ ] PolicyEngine 接入执行路径（或标注为存根）
- [ ] E2E 测试修复并使用状态断言
- [ ] 全量测试无回归

### Phase 16.2 完成标准
- [ ] IdempotencyStore 线程安全 + LRU 淘汰
- [ ] 路径边界检查生效
- [ ] SkillManager 单例统一
- [ ] TraceMiddleware 不直接写入 state
- [ ] build_snapshot 有 mtime 缓存
- [ ] 所有补充测试通过
- [ ] 覆盖率 ≥ 80%

### Phase 16.3 完成标准
- [x] PII 脱敏实现
- [x] 路径黑名单补充
- [ ] 输入校验实现
- [ ] 所有性能优化完成
- [ ] 架构标注和文档更新

---

## 依赖关系

```
Phase 16.1:
  Step 1 (SSRF) ── 独立
  Step 2 (外部工具策略) ── 独立
  Step 3 (session grant 撤销) ── 独立
  Step 4 (删除 ToolRegistry) ── 独立
  Step 5 (PolicyEnforcedToolNode) ── 依赖 Step 2, Step 3
  Step 6 (E2E 修复) ── 独立

Phase 16.2:
  Step 8 (IdempotencyStore) ── 依赖 Step 5（接入执行路径）
  Step 9-12 ── 独立，可与 Step 8 并行
  Step 13 (测试) ── 依赖 Step 3, Step 8, Step 10

Phase 16.3:
  Step 14-27 ── 全部独立，可按任意顺序执行
```

---

## 预估工作量

| 阶段 | 步骤数 | 预估时间 |
|------|--------|---------|
| Phase 16.1 (P0) | 6 步 | 4-6 小时 |
| Phase 16.2 (P1) | 6 步 | 3-4 小时 |
| Phase 16.3 (P2) | 14 步 | 3-4 小时 |
| **总计** | **26 步** | **10-14 小时** |
