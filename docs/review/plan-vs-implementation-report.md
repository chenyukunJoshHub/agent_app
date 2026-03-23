# 计划 vs 实现对比审查报告

> **审查日期**: 2026-03-23
> **审查范围**: Phase 01-13 全部阶段
> **审查方法**: 对比 `docs/plans/` 中的计划文件与实际代码实现

---

## 审查结果汇总

| 类别 | 数量 | 优先级 |
|------|------|--------|
| ❌ **遗漏功能** | 10 | 高 |
| ⚠️ **临时方案** | 4 | 中 |
| 🔍 **实现差异** | 3 | 低 |
| ✅ **完全符合** | 大部分 | - |

---

## 一、遗漏功能 (需要补充实现)

### Phase 02 - SkillManager
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| 3 级预算降级策略 | ❌ 未实现 - 只有固定 `_build_prompt()` | 当 skill 过多时无法动态降级 |
| 文件大小检查 (MAX_SKILL_FILE_BYTES) | ❌ 未实现 - `scan()` 中没有检查 | 大文件可能导致解析失败 |
| `read_skill_content()` 方法 | ❌ 未实现 | 无法按计划读取 skill 内容 |

### Phase 03 - Memory
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| SummarizationMiddleware | ❌ 未找到此文件 | 无法实现消息压缩功能 |

### Phase 04 - Agent 核心
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| Anthropic provider 支持 | ❌ `llm_factory.py` 只支持 OLLAMA, DEEPSEEK, ZHIPU, OPENAI | 无法使用 Claude 模型 |

### Phase 07 - FastAPI SSE 接口
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| GET /skills | ❌ 未实现 | 无法查询 skills 列表 |
| GET /skills/{skill_id}/content | ❌ 未实现 | 无法获取 skill 内容 |
| GET /session/{session_id}/context | ❌ 未实现 | 无法获取 Token 预算状态 |

### Phase 08 - 前端布局
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| 三栏布局 (Skills | Chat | Context Window) | ⚠️ 两栏布局 - 缺少左栏 Skills 面板 | 与设计不符 |

### Phase 10 - Context Window 面板
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| ContextWindowPanel 组件 | ❌ 未找到 | 无法可视化 10 个 Slot 使用情况 |
| SlotBar 组件 | ❌ 未找到 | 无法显示每个 Slot 的详细使用 |
| CompressionLog 组件 | ❌ 未找到 | 无法查看压缩事件 |

### Phase 11 - Skills UI
| 计划要求 | 实际情况 | 影响 |
|---------|---------|------|
| SkillPanel 组件 | ❌ 未找到 | 无法显示可用 skills |
| SkillCard 组件 | ❌ 未找到 | 无法显示单个 skill 详情 |
| SkillDetail 抽屉 | ❌ 未找到 | 无法查看 skill 完整内容 |

---

## 二、临时方案 (需要后续完善)

### Phase 03 - Memory
| 临时方案 | 计划要求 | 备注 |
|---------|---------|------|
| `MemoryManager.save_episodic()` 为 no-op | P2 阶段实现 | 符合计划，但标记为临时 |
| MemoryManager 中有 legacy 方法 | 清理遗留代码 | `get_user_context()`, `update_context()`, `add_episodic()` |

### Phase 05 - Prompt 构建器
| 临时方案 | 计划要求 | 备注 |
|---------|---------|------|
| Token 预算使用简化版 TokenBudget | 完整 10 个 Slot 分配 | 当前只有部分 Slot |

### Phase 07 - API
| 临时方案 | 计划要求 | 备注 |
|---------|---------|------|
| /chat 使用 GET 方法 | POST 方法 | 代码注释说明 SSE 兼容性 |

---

## 三、实现差异 (需要确认或调整)

### Phase 01 - 数据库
| 计划要求 | 实际情况 | 备注 |
|---------|---------|------|
| Migration 文件连续编号 | 编号不连续 (001, 003, 004, 005) | 缺少 002 |

### Phase 04 - Agent 核心
| 计划要求 | 实际情况 | 备注 |
|---------|---------|------|
| TraceMiddleware 提取 tool_calls | 只提取 reasoning 和 content | 在 `_execute_agent` 中处理 tool_calls |

### Phase 09 - ReAct 链路
| 计划要求 | 实际情况 | 备注 |
|---------|---------|------|
| 颜色编码 (Thought 紫色, Tool Call 蓝色等) | 需要验证 | Timeline/ToolCallTrace 组件存在 |

---

## 四、完全符合的功能 ✅

以下功能按计划正确实现：

- ✅ Phase 01: AsyncPostgresSaver/AsyncPostgresStore 初始化
- ✅ Phase 02: SkillManager.scan() 基础扫描
- ✅ Phase 03: MemoryManager.load_episodic() 和 Ephemeral 注入
- ✅ Phase 03: MemoryMiddleware.abefore_agent/wrap_model_call
- ✅ Phase 04: create_react_agent() 基础创建
- ✅ Phase 05: build_system_prompt() 基础组装
- ✅ Phase 06: web_search, send_email, read_file 工具
- ✅ Phase 07: /chat SSE 流式接口 (GET 方法)
- ✅ Phase 07: /chat/resume HIL 恢复接口
- ✅ Phase 09: Timeline 和 ToolCallTrace 组件
- ✅ Phase 12: HIL ConfirmModal 组件
- ✅ Phase 13: E2E 测试套件

---

## 五、优先级建议

### P0 - 立即修复
1. **Phase 02**: 实现 3 级预算降级策略（核心功能）
2. **Phase 04**: 添加 Anthropic provider 支持（Claude 模型）
3. **Phase 07**: 实现 GET /skills 端点（Skills 功能依赖）

### P1 - 重要补充
1. **Phase 03**: 实现 SummarizationMiddleware（消息压缩）
2. **Phase 07**: 实现 GET /session/{id}/context 端点
3. **Phase 10**: 实现 ContextWindowPanel 组件（可观测性）
4. **Phase 11**: 实现 Skills UI 组件（用户体验）

### P2 - 可选优化
1. **Phase 02**: 添加文件大小检查
2. **Phase 07**: 将 /chat 改为 POST 方法
3. **Phase 08**: 调整为三栏布局

---

## 六、技术债务

1. **Legacy 代码清理**: MemoryManager 中的 deprecated 方法
2. **Migration 文件编号**: 补充或重命名 002 文件
3. **Token 预算**: 完整实现 10 个 Slot 分配机制
4. **文档同步**: 更新 AGENTS.md 和 CLAUDE.md 反映当前实现状态

---

## 七、下一步行动

### 立即执行
1. 决定 P0 问题的修复优先级
2. 创建 Phase 14 修复计划
3. 更新 task_plan.md 反映当前状态

### 讨论确认
1. 前端布局是否需要调整为三栏？
2. Migration 文件编号是否需要修正？
3. Token 预算简化版本是否可接受？

---

**审查完成时间**: 2026-03-23
**下次审查建议**: Phase 14 完成后
