# Phase 06 — 工具系统

## 目标

实现核心工具集，包含 web_search、send_email（HIL mock）、activate_skill、read_file、token_counter 等。

## 架构文档参考

- Agent v13 §1.12 工具定义
- Skill v3 §1.5 Skill 激活机制

## 测试用例清单（TDD 先写）

### activate_skill
- [ ] 存在的 skill 返回 SKILL.md 内容
- [ ] 不存在的 skill 返回错误提示

### web_search
- [ ] 调用 Tavily API 成功
- [ ] 返回格式化结果
- [ ] 错误处理正常

### send_email
- [ ] 返回 mock 结果
- [ ] HIL middleware 正确拦截

### read_file
- [ ] 路径白名单检查
- [ ] 路径遍历防护
- [ ] 正确读取文件内容

### token_counter
- [ ] 精确计数
- [ ] 支持多种模型

## 实现步骤（TDD 顺序）

### Step 1 — activate_skill
- 写测试，确认 RED
- 实现 @tool 装饰器
- 确认 GREEN

### Step 2 — web_search
- 写测试，确认 RED
- 集成 Tavily API
- 确认 GREEN

### Step 3 — send_email
- 写测试，确认 RED
- 实现 mock 版本
- 确认 GREEN

### Step 4 — read_file
- 写测试，确认 RED
- 实现路径安全检查
- 确认 GREEN

### Step 5 — token_counter
- 写测试，确认 RED
- 集成 tiktoken
- 确认 GREEN

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] 所有工具正常工作
- [ ] 路径安全检查到位
- [ ] HIL 拦截正常
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done

---

## 2026-03-26 增补：Layer4 执行层（A/B/混合）与 search 契约

### Layer4（执行层）测试补充
- [x] Path A（并行）：同 step 双工具并发执行，验证时间窗重叠
- [x] Path B（串行）：跨 step 依赖执行，验证严格先后顺序
- [x] Path A+B（混合）：先并行读工具，再串行汇总写工具
- [x] Path C（task_dispatch）不纳入本轮范围（按需求排除）
- [x] HIL 幂等缺口已修复：`/chat/resume` 对 `send_email` 增加幂等防重执行（Phase 21）

### `search.py` 契约补充
- [x] 成功与失败返回统一 JSON 契约（可解析）
- [x] 结果字段稳定：`query/answer/results[].title|url|content`
- [x] 大结果截断预算（单条与总量）防止上下文污染
- [x] Tavily 异常分类映射为稳定错误结构（timeout/network/api_error）
