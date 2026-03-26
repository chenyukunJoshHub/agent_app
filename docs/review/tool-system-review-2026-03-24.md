# 工具系统代码审查报告

**目标**：工具系统重构（tool system v12）
**审查维度**：Security · Performance · Architecture · Testing
**日期**：2026-03-24
**总发现**：36 项（0 Critical · 9 High · 17 Medium · 10 Low）

---

## Critical 发现（0 项）

无。

---

## High 发现（9 项）

### [SEC-001] Policy Engine Session Grant 无失效机制，可被永久绕过

**位置**：`backend/app/tools/policy.py:34-35`
**维度**：Security

**描述**：`grant_session()` 对工具的批准永久有效，无 TTL、无撤销方法、无审计记录。一旦 `send_email` 等外部写工具被批准，本次会话内所有后续调用均跳过 HIL 检查。

**影响**：LLM 提示注入攻击可重复触发已批准工具，完全绕过人工审核。

**修复方案**：
1. 添加 `revoke_session(tool_name: str)` 方法
2. 实现单次使用 grant（执行后自动撤销）或加入 TTL
3. 对 `effect_class="destructive"` 类工具禁止 session grant
4. 记录所有 grant/revoke 操作到审计日志

---

### [SEC-002] 自定义工具绕过 PolicyEngine（统一被标记为 read + allow）

**位置**：`backend/app/agent/langchain_engine.py:182-184`
**维度**：Security

**描述**：传入的外部工具被统一赋予 `effect_class="read"`, `allowed_decisions=["allow"]`，无论其实际行为如何。

**影响**：执行写操作或破坏性操作的工具将跳过所有策略检查。

**修复方案**：未知工具应默认采用限制性策略：
```python
tool_metas = {
    t.name: ToolMeta(effect_class="external_write", allowed_decisions=["ask", "deny"])
    for t in tools
}
```
或要求调用方显式提供 `ToolMeta`。

---

### [SEC-005] `fetch_url` 缺乏 SSRF 防护

**位置**：`backend/app/tools/fetch.py:16-54`
**维度**：Security

**描述**：工具接受任意 URL 直接执行 HTTP GET，无私有 IP 过滤、无协议限制，且被分类为 `allowed_decisions=["allow"]` 自动通过策略检查。

**影响**：LLM 可被诱导访问 `169.254.169.254`（云元数据）或内网管理接口，导致凭证泄露。

**修复方案**：
```python
import ipaddress, socket
from urllib.parse import urlparse

BLOCKED_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
]

def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    return not any(ip in r for r in BLOCKED_RANGES)
```

---

### [PERF-003] `IdempotencyStore` 无界增长，构成内存泄漏

**位置**：`backend/app/tools/idempotency.py:4-12`
**维度**：Performance

**描述**：`_executed` set 只增不减，无 TTL 淘汰机制，也无大小上限。

**影响**：长期运行的 Agent Server 中每次工具调用新增一条记录，永不回收，持续消耗内存。

**修复方案**：
```python
from collections import OrderedDict

class IdempotencyStore:
    def __init__(self, max_size: int = 10_000) -> None:
        self._executed: OrderedDict[str, None] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()

    def check_and_mark(self, key: str) -> bool:
        with self._lock:
            if key in self._executed:
                return True
            self._executed[key] = None
            if len(self._executed) > self._max_size:
                self._executed.popitem(last=False)  # LRU eviction
            return False
```

---

### [ARCH-002] `ToolRegistry` 类是死代码

**位置**：`backend/app/tools/registry.py:15-126`
**维度**：Architecture

**描述**：`ToolRegistry` 类（6 个方法）从未被任何消费者使用。`build_tool_registry()` 完全绕过它。

**影响**：增加认知负担，误导开发者认为存在两套工具管理方案。

**修复方案**：删除 `ToolRegistry` 类及其在 `__init__.py` 中的导出；若有保留价值，整合进 `build_tool_registry`。

---

### [ARCH-005] `ToolManager` 和 `PolicyEngine` 未接入执行路径

**位置**：`backend/app/agent/langchain_engine.py:176-187`
**维度**：Architecture

**描述**：`build_tool_registry` 返回的 `tool_manager` 和 `policy_engine` 被赋给局部变量后直接丢弃，从未传递给任何执行组件。整个 Management Layer（架构文档第 3 层）是死代码。

**修复方案**：创建自定义 ToolNode 包装器：
```python
class PolicyEnforcedToolNode:
    def __init__(self, tools, policy_engine, tool_manager, sse_queue):
        self._tool_map = {t.name: t for t in tools}
        self._policy = policy_engine
        self._manager = tool_manager
        self._queue = sse_queue

    async def __call__(self, state):
        for tc in state["messages"][-1].tool_calls:
            meta = self._manager.get_meta(tc["name"])
            decision = self._policy.decide(tc["name"], meta.effect_class, meta.allowed_decisions)
            if decision == "deny":
                # return error message
                ...
            elif decision == "ask":
                # trigger HIL via SSE
                ...
```
若当前阶段不实现，需在架构文档中明确标注为存根。

---

### [TEST-001] `ToolRegistry` 类无专属单元测试

**位置**：`tests/backend/unit/tools/test_build_tool_registry.py`
**维度**：Testing

**描述**：`ToolRegistry` 类的 6 个公开方法（含验证逻辑和错误处理）均无测试覆盖。

**修复方案**：新增 `tests/backend/unit/tools/test_tool_registry.py`，覆盖：
- `register()` 拒绝 None 或非 BaseTool 输入
- `register()` 拒绝重复工具名
- `get_by_name()` 对未知工具抛出 KeyError
- `unregister()` 和 `clear()` 行为
- `__len__` 和 `__contains__` 语义

---

### [TEST-007] E2E 测试使用固定 `waitForTimeout`

**位置**：`tests/e2e/03-tool-trace.spec.ts:25`
**维度**：Testing

**修复方案**：
```typescript
// 删除
await page.waitForTimeout(5000);
// 改为
await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 15000 });
```

---

### [TEST-008] E2E 测试未验证工具追踪事件

**位置**：`tests/e2e/03-tool-trace.spec.ts:11-38`
**维度**：Testing

**描述**：3 个测试仅验证面板可见性，工具追踪渲染完全失效时这些测试仍会通过。

**修复方案**：添加工具调用追踪验证：
```typescript
test('工具调用应出现在追踪面板中', async ({ page }) => {
  await page.fill('[placeholder=/描述任务/i]', '搜索今日天气');
  await page.keyboard.press('Enter');
  // 等待工具调用追踪条目出现
  await expect(page.locator('[data-testid="tool-call-card"]')).toBeVisible({ timeout: 20000 });
  await expect(page.locator('[data-testid="tool-call-card"]')).toContainText('web_search');
});
```

---

## Medium 发现（17 项）

| ID | 位置 | 描述 | 修复方向 |
|----|------|------|---------|
| SEC-003 | `idempotency.py:8-12` | `check_and_mark` 无锁，并发竞态 | 添加 `threading.Lock`（见 PERF-003 修复代码） |
| SEC-004 | `registry.py` + `idempotency.py` | `IdempotencyStore` 未接入执行路径 | 在 ToolNode 执行前调用 `check_and_mark` |
| SEC-006 | `skills/manager.py:522-535` | `read_skill_content` 无路径边界检查 | 添加 `resolved.is_relative_to(skills_dir)` 校验 |
| PERF-001 | `skills/manager.py:336-387` | Level 3 截断路径线性重建 prompt | 将注释中已提到的二分搜索付诸实现 |
| PERF-004 | `skills/manager.py:301` | 每次 `build_snapshot` 都触发全量文件扫描 | 缓存扫描结果，基于文件 mtime 决定是否重新扫描 |
| PERF-006 | `ExecutionTracePanel.tsx:95-97` | `filter/sort/map` 每次渲染重执行 | 用 `useMemo` 缓存；`toggle/toggleSlot` 用 `useCallback` |
| ARCH-001 | `backend/app/tools/` | 目录结构与 `tools-v12.md` 不符 | 将工具文件迁移至 `readonly/`、`write/`、`orchestration/` 或更新文档 |
| ARCH-004 | `registry.py:131-220` | 新增工具必须修改 `build_tool_registry` | 各工具模块导出 `TOOL_SPEC` 常量，注册函数自动发现 |
| ARCH-006 | `idempotency.py` | 纯内存存储，Agent 重启后状态丢失 | 接入 PostgreSQL checkpointer 或明确文档标注为存根 |
| ARCH-007 | `skill_loader.py:27-29` | `activate_skill` 在单例失败时创建游离实例 | `langchain_engine.py` 改用 `SkillManager.get_instance(skills_dir=...)`，删除 fallback 构造 |
| ARCH-008 | `middleware/trace.py:195` | `TraceMiddleware` 直接写入 Agent State；预算值硬编码 | 通过返回值传递状态更新；从 `DEFAULT_BUDGET` 读取预算值 |
| TEST-002 | `test_idempotency.py` | 缺少空 key、Unicode key、并发测试 | 补充边界条件和 `threading` 并发测试 |
| TEST-003 | `test_policy_engine.py:53-63` | 未测试 grant 对 deny 的覆盖；grant 后 `hil_required` 变化 | 补充相关断言，明确语义约束 |
| TEST-004 | `test_tool_manager.py` | `get_meta` 返回直接引用，外部可变 | 添加可变性测试；按需改为返回副本 |
| TEST-005 | `test_activate_skill.py:36-41` | Late import + 手动 singleton reset，隔离脆弱 | 用 fixture 注入预配置 `SkillManager`，通过 monkeypatch mock `get_instance` |
| TEST-006 | `test_activate_skill.py` | 缺少 `scan()` 异常、目录不存在、空 name 测试 | 补充错误路径测试 |
| TEST-010 | `tests/backend/unit/tools/` | 无 PolicyEngine × ToolManager 集成测试 | 遍历所有注册工具，验证 `decide()` 不抛出 ValueError |

---

## Low 发现（10 项）

| ID | 位置 | 描述 | 修复方向 |
|----|------|------|---------|
| SEC-007 | `send_email.py:40`, `trace.py:173` | PII 和工具参数明文写入日志/SSE | 脱敏处理敏感字段；SSE 事件过滤敏感 args |
| SEC-008 | `tools/file.py:37` | 路径黑名单未覆盖 `.env` 等敏感文件 | 改为白名单策略或补充 `.env` 等规则 |
| SEC-009 | `send_email.py`, `fetch.py` | 无输入校验，邮件头注入和非法 scheme 未拦截 | 校验邮件格式；过滤 `\n\r`；限制 URL scheme |
| PERF-002 | `skills/manager.py:194` | `import yaml` 在方法内部 | 移至文件顶层 |
| PERF-005 | `skills/manager.py:522-535` | `read_skill_content` 线性搜索 | `scan()` 时构建 `dict[str, SkillDefinition]` 索引 |
| PERF-007 | `langchain_engine.py:240,276` | `slot_snapshot.to_dict()` 调用两次 | 缓存到局部变量 `slot_dict = slot_snapshot.to_dict()` |
| ARCH-003 | `policy.py:13` | 构造函数缺少架构文档指定的 `store` 参数 | 添加 `store=None` 可选参数保持前向兼容 |
| ARCH-009 | `tools/__init__.py:14` | 顶层包无条件导入 `send_email` | 从 `__init__.py` 移除；调用方直接导入 |
| ARCH-010 | `tools/base.py:16` | `backoff: dict \| None` 缺乏类型约束 | 定义 `BackoffConfig(TypedDict)` 替代裸 dict |
| TEST-009 | `test_build_tool_registry.py` | 缺少导入失败、多次调用、BaseTool 实例类型验证 | 补充对应测试场景 |

---

## 汇总

| 维度 | Critical | High | Medium | Low | 合计 |
|------|----------|------|--------|-----|------|
| Security | 0 | 3 | 3 | 3 | **9** |
| Performance | 0 | 1 | 3 | 3 | **7** |
| Architecture | 0 | 2 | 5 | 3 | **10** |
| Testing | 0 | 3 | 6 | 1 | **10** |
| **合计** | **0** | **9** | **17** | **10** | **36** |

---

## 修复优先级路线图

### P0 — 立即处理（High，影响安全或架构正确性）

1. **ARCH-005**：将 PolicyEngine 接入工具执行路径（Management Layer 激活）
2. **SEC-002**：修复自定义工具默认策略为限制性策略
3. **SEC-001**：为 session grant 添加撤销机制
4. **SEC-005**：在 `fetch_url` 添加 SSRF 防护
5. **ARCH-002**：删除 `ToolRegistry` 死代码
6. **TEST-007/008**：修复 E2E 测试使其真正验证工具追踪
7. **TEST-001**：补充 `ToolRegistry` 单元测试

### P1 — 计划处理（Medium，影响正确性或可维护性）

1. **SEC-003/004**：`IdempotencyStore` 加锁并接入执行路径
2. **PERF-003**：`IdempotencyStore` LRU 淘汰
3. **ARCH-006**：明确幂等存储的持久化要求或文档标注
4. **ARCH-007**：统一 `SkillManager` 单例使用方式
5. **ARCH-008**：TraceMiddleware 移除直接状态写入
6. **PERF-004**：`build_snapshot` 添加文件 mtime 缓存
7. **TEST-003/004/005/006/010**：补充测试覆盖

### P2 — 长期改善（Low，代码质量和可扩展性）

所有 Low 级别发现按常规迭代处理。
