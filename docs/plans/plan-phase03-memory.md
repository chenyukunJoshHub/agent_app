# Phase 03 — Memory 模块

## 目标

实现三层记忆架构（短期/长期/工作记忆），包含 MemoryManager、MemoryMiddleware，支持 Ephemeral 注入和消息压缩。

## 架构文档参考

- Memory v5 §1.2 三层记忆模型
- Memory v5 §1.4 Ephemeral vs Persistent 注入策略
- Memory v5 §2.4 MemoryManager
- Memory v5 §2.5 MemoryMiddleware

## 测试用例清单（TDD 先写）

### MemoryManager.load_episodic()
- [ ] 空用户返回默认 EpisodicData
- [ ] 存在的用户返回存储的数据
- [ ] namespace 正确隔离 (profile, user_id)

### MemoryManager.save_episodic()
- [ ] 正常写入数据到 store
- [ ] 覆盖已有数据
- [ ] namespace 正确隔离

### MemoryManager.build_ephemeral_prompt()
- [ ] 空 preferences 返回空字符串
- [ ] 有 preferences 返回正确格式
- [ ] 格式符合 "[用户画像]" 前缀规范

### MemoryMiddleware.abefore_agent()
- [ ] 正确加载用户画像到 state
- [ ] 从 runtime.config 获取 user_id
- [ ] 返回 {"memory_ctx": MemoryContext(...)}

### MemoryMiddleware.wrap_model_call()
- [ ] 无 memory_ctx 时直接透传
- [ ] 有 memory_ctx 时注入到 system_message
- [ ] 使用 request.override() 注入

### MemoryMiddleware.aafter_agent()
- [ ] P0 阶段返回 None（空操作）

## 实现步骤（TDD 顺序）

### Step 1 — 数据结构
- 实现 EpisodicData, MemoryContext
- 实现 MemoryState (TypedDict)

### Step 2 — MemoryManager
- 写全部测试，确认 RED
- 实现 load_episodic / save_episodic / build_ephemeral_prompt
- 确认 GREEN

### Step 3 — MemoryMiddleware
- 写全部测试，确认 RED
- 实现 abefore_agent / wrap_model_call / aafter_agent
- 确认 GREEN

### Step 4 — SummarizationMiddleware 集成
- 配置 SummarizationMiddleware
- 验证压缩触发

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] 三层记忆架构完整
- [ ] Ephemeral 注入正常工作
- [ ] SummarizationMiddleware 集成成功
- [ ] findings.md 中记录技术决策
- [ ] progress.md 更新本阶段会话日志
- [ ] task_plan.md 阶段状态更新为 ✅ done

---

## Phase 21 — 记忆写回双策略（B/C）+ Retain 轻量落地

### 测试用例清单（TDD 先写）

#### Settings（新增配置）
- [x] `memory_profile_update_mode` 默认值为 `rule`
- [x] `memory_profile_llm_interval` 默认值为 `10`
- [x] `memory_profile_opinion_min_confidence` 默认值为 `0.9`
- [x] `memory_profile_llm_interval < 1` 时校验失败
- [x] `memory_profile_opinion_min_confidence` 超出 `[0,1]` 时校验失败

#### MemoryManager.save_episodic()
- [x] 调用 `save_episodic` 会真实写入 `store.aput`
- [x] `namespace=("profile", user_id), key="episodic"` 正确
- [x] 重复写入时后写覆盖前写

#### MemoryMiddleware.abefore_agent()
- [x] 返回 `memory_ctx` 同时写入 `memory_ctx_baseline`
- [x] baseline 与加载到的原始 `episodic` 一致

#### MemoryMiddleware.aafter_agent() — rule 模式
- [x] `interaction_count +1`
- [x] 规则提炼 language/domain 生效
- [x] 画像变化时触发 `save_episodic`
- [x] 画像无变化时不写库（dirty flag）

#### MemoryMiddleware.aafter_agent() — llm 模式
- [x] 非第 N 轮跳过 LLM 提炼
- [x] 第 N 轮执行 LLM 提炼并合并 `preferences + summary`
- [x] LLM 异常或解析失败时回退 rule 结果，不抛错

#### Retain 轻量落地（C 模式）
- [x] summary 含 `W/B/O/S` 结构化行
- [x] `O(c=...)` 仅当 `c >= memory_profile_opinion_min_confidence` 才写入 preferences
