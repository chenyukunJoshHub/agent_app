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
- [ ] `grant_session()` 后 `decide()` 应返回 "allow"
- [ ] `revoke_session()` 后 `decide()` 应恢复原始决策
- [ ] 对 `effect_class="destructive"` 类工具 `grant_session()` 应被拒绝或立即撤销
- [ ] `revoke_session()` 对未 grant 的工具不应抛出异常
- [ ] `get_granted_tools()` 返回当前会话所有已 grant 的工具列表

**实现步骤**:
1. `PolicyEngine` 添加 `revoke_session(tool_name: str)` 方法
2. `PolicyEngine` 添加 `get_granted_tools() -> set[str]` 方法
3. 修改 `decide()` 方法：destructive 工具不使用 session grant
4. 可选：添加 TTL 支持（grant 时记录时间戳，超时自动撤销）
5. 更新 `tests/backend/unit/tools/test_policy_engine.py`

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

> **注意**: 这是架构层面最大的改动，需要自定义 ToolNode 包装器。
> 若当前阶段实现复杂度过高，可先在架构文档中标注为存根，下一迭代实现。

**测试用例**:
- [ ] deny 决策的工具调用应返回错误消息
- [ ] ask 决策的工具调用应触发 HIL（通过 SSE 推送 hil_interrupt 事件）
- [ ] allow 决策的工具调用应正常执行
- [ ] 执行前应检查 `IdempotencyStore`
- [ ] 已 revoke 的工具不应被 session grant 缓存影响

**实现步骤**:
1. 创建 `backend/app/agent/policy_tool_node.py` — PolicyEnforcedToolNode
2. 在 LangGraph workflow 中替换默认 ToolNode
3. 集成 PolicyEngine.decide() + ToolManager.get_meta() + IdempotencyStore.check_and_mark()
4. deny → 返回 ToolMessage(error)
5. ask → 触发 HIL 中断（SSE hil_interrupt 事件）
6. 允许 → 正常执行工具
7. 新建 `tests/backend/unit/agent/test_policy_tool_node.py`

**影响文件**:
- `backend/app/agent/policy_tool_node.py`（新建）
- `backend/app/agent/langchain_engine.py`（修改 — 接入 PolicyEnforcedToolNode）
- `tests/backend/unit/agent/test_policy_tool_node.py`（新建）

**依赖**: Step 2（SEC-002）、Step 3（SEC-001）需先完成

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
- [ ] grant 对 deny 的覆盖行为测试
- [ ] grant 后 `hil_required` 变化测试
- [ ] 多次 grant 同一工具的幂等性

#### TEST-004 — ToolManager get_meta 返回副本
- [ ] 修改返回的 ToolMeta 不影响内部存储
- [ ] 返回的 ToolMeta 与内部存储值相等

#### TEST-005 — activate_skill 隔离修复
- [ ] fixture 注入预配置 SkillManager
- [ ] monkeypatch mock `get_instance`

#### TEST-006 — activate_skill 错误路径
- [ ] `scan()` 异常时的行为
- [ ] 目录不存在时的行为
- [ ] 空 name 参数时的行为

#### TEST-010 — PolicyEngine × ToolManager 集成测试
- [ ] 遍历所有注册工具，验证 `decide()` 不抛出 ValueError
- [ ] 验证每个工具的 `effect_class` 对应正确的默认决策

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
- 日志中脱敏邮件地址（`u***@example.com`）
- SSE 事件中过滤敏感工具参数

---

### Step 15: SEC-008 — 路径黑名单补充

**位置**: `backend/app/tools/file.py:37`

**实现**:
- 补充 `.env`、`.env.*`、`*.key`、`*.pem` 到黑名单
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
- 将线性尝试替换为二分搜索，找到最大可容纳的 skill 数量

---

### Step 18: PERF-002 — import yaml 移至文件顶层

**位置**: `backend/app/skills/manager.py:194`

**实现**:
- `import yaml` 移至文件顶部

---

### Step 19: PERF-005 — read_skill_content 使用索引

**位置**: `backend/app/skills/manager.py:522-535`

**实现**:
- `scan()` 时构建 `dict[str, SkillDefinition]` 索引
- `read_skill_content()` 使用索引查找替代线性搜索

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
- 或更新架构文档以反映当前结构

---

### Step 23: ARCH-003 — PolicyEngine 构造函数添加 store 参数

**位置**: `backend/app/tools/policy.py:13`

**实现**:
- 添加 `store=None` 可选参数保持前向兼容

---

### Step 24: ARCH-006 — IdempotencyStore 持久化标注

**位置**: `backend/app/tools/idempotency.py`

**实现**:
- 在类文档字符串中标注为内存存根
- 或接入 PostgreSQL checkpointer

---

### Step 25: ARCH-009 — 移除顶层无条件导入 send_email

**位置**: `backend/app/tools/__init__.py:14`

**实现**:
- 从 `__init__.py` 移除 `send_email` 导入
- 调用方直接导入

---

### Step 26: ARCH-010 — BackoffConfig 类型定义

**位置**: `backend/app/tools/base.py:16`

**实现**:
- 定义 `BackoffConfig(TypedDict)` 替代裸 `dict`

---

### Step 27: TEST-009 — build_tool_registry 补充测试

**位置**: `tests/backend/unit/tools/test_build_tool_registry.py`

**测试用例**:
- [ ] 导入失败时的错误处理
- [ ] 多次调用 build_tool_registry 的幂等性
- [ ] BaseTool 实例类型验证

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
- [ ] PII 脱敏实现
- [ ] 路径黑名单补充
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
