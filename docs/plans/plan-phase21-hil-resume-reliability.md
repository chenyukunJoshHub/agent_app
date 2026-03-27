# Phase 21 — HIL Resume 可靠性闭环

## 目标

修复 `/chat/resume` 在写工具执行上的可靠性缺口，先完成「同语义请求防重副作用」闭环，并为后续“真实 checkpoint 恢复”留出清晰入口。

## 架构文档参考

- Agent v13 §1.13 HIL 完整交互时序
- Agent v13 §2.4 SSE 流式架构
- Tools v12 §1.3.4 执行层幂等保护（写操作专属）
- Memory v5 §1.2 短期记忆关键要求（支持 HIL 断点恢复）

## 测试用例清单（TDD 先写）

### `/chat/resume` 幂等防重
- [x] 同 session + 同 `send_email` 语义 payload，二次 resume 不应重复执行副作用
- [x] 同 session + 不同 `send_email` payload，应分别执行
- [x] 回放被去重时 SSE `tool_result` 包含 `idempotent_replay` 标记

### `/chat/resume` 恢复语义（下一步）
- [x] approve 分支从 checkpoint 恢复继续执行（`Command(resume={"decisions":[approve]})`）
- [x] reject 分支通过 `Command(resume={"decisions":[reject]})` 恢复，不再直接 synthetic done

## 实现步骤（TDD 顺序）

### Step 1 — 将已固化的 xfail 转为真实 RED
- [x] 移除 `test_execution_layer_ab_mix.py` 中 HIL 幂等 `xfail`
- [x] 修正测试桩（替换整个 tool 对象）并确认 RED

### Step 2 — `/chat/resume` 写工具幂等保护
- [x] 在 `chat.py` 增加 resume 幂等键构建（优先 ToolMeta `idempotency_key_fn`）
- [x] 增加 `IdempotencyStore` 检查与标记
- [x] 工具执行异常时回滚幂等标记（`discard`）
- [x] 二次回放返回去重 `tool_result`，避免重复副作用

### Step 3 — 回归验证
- [x] `tests/backend/integration/tools/test_execution_layer_ab_mix.py`
- [x] `tests/backend/unit/api/test_chat.py`（新增 resume 幂等单测）
- [x] `tests/backend/integration/test_hil_resume_checkpoint_recovery.py`（`requires_db`，真实 checkpointer approve/reject）
- [x] `tests/backend/unit/tools + tests/backend/integration/tools + tests/backend/unit/api/test_chat.py` 回归

## 完成标准

- [x] HIL 幂等缺口不再依赖 `xfail` 固化
- [x] `/chat/resume` 对 `send_email` 可防重复副作用
- [x] 覆盖同 payload 去重与不同 payload 正常执行
- [x] `/chat/resume` 真实 checkpoint 恢复链路（基于 `thread_id + Command(resume=...)`）
- [x] 真实 Postgres checkpointer 回归（approve 不重放前置工具、reject 不执行写副作用）
