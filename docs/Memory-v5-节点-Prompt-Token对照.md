# Memory v5 · 节点 → 实际 Prompt 片段 → Token 对照

> 依据 [Memory 模块架构设计文档 v5](Memory%20模块架构设计文档%20v5.md) 第一层（框架无关）与第二层（LangChain 映射）整理。  
> **Token 数**：无特别说明时，**设计预算**引用 [Prompt + Context 模块完整设计文档](Prompt%20+%20Context%20模块完整设计文档.md) §1.2「32k turn / 24,576 输入」的 Slot 配额；**200k 模型窗口示例**用于与「Context Usage」类 UI 一致，均为**示意**，线上应以 **Token Counter**（tiktoken / 模型分词器）实测为准。

---

## 1. Turn 生命周期节点（§1.3 ①–⑧）

| 节点 | 存储/控制 | 是否进入「主 LLM 单次请求」的可见文本 | 实际 Prompt / 内容形态（示例） | Token（说明） |
|------|-----------|----------------------------------------|--------------------------------|---------------|
| **① 加载长期记忆** | `AsyncPostgresStore` → `memory_ctx` | 否（仅 state）；**不**整段塞进历史 | 无直接 Prompt；内存中为结构化数据，如 `EpisodicData.preferences` | **0**（主请求） |
| **② 恢复短期记忆** | `AsyncPostgresSaver` / `thread_id` | 是 → 成为 **messages** 一部分 | `HumanMessage` / `AIMessage` / `ToolMessage` 序列（含 ReAct 推理与工具结果） | **弹性 Slot⑧**（见 §4） |
| **③ 组装工作记忆** | 逻辑步骤 | 是（聚合结果） | 见 §3「工作记忆拆解」 | 为下列子块之和 |
| **④ LLM 调用** | — | 消费③ | （模型输入 = 完整 request） | = ③ 合计 |
| **⑤ 工具执行** | 检查点 + 历史 | 工具返回后进 **下轮** 的 messages | `ToolMessage(content=...)` 文本 | 计入 **下一轮 Slot⑧** |
| **⑥ 退出 ReAct** | — | — | — | — |
| **⑦ 保存短期记忆** | checkpointer | 否 | — | **0** |
| **⑧ 写回长期记忆** | `store.aput` | 否（P0 空操作） | — | **0** |

---

## 2. 中间件与压缩（§2.5–2.6）

| 节点 | 作用 | 是否主对话 Context 的一部分 | 实际 Prompt / 内容形态 | Token |
|------|------|------------------------------|------------------------|-------|
| **`abefore_agent`** | 加载画像到 `memory_ctx` | 否 | 无 Prompt 文本 | 0 |
| **`wrap_model_call`** | Ephemeral 注入画像 | 是（**请求级** `SystemMessage`，**不写入**历史） | 在已有 `system_message.content` **末尾追加** `memory_text`（见 §2.4 代码） | **~50–500**（设计 Slot⑤ 上限 500；实际随偏好字段多少变化） |
| **`SummarizationMiddleware` · `before_model`** | 超阈值则压缩历史 | 压缩**后**的旧轮次被 **摘要 SystemMessage** 等替换进 messages | 使用框架**内置** `summary_prompt`（小模型调用），**不是**主 Agent 同一条用户可见长 Prompt；主线程上表现为历史变短 + 可能出现摘要消息 | **摘要产出**通常目标 **&lt;400**（Prompt 文档 §④ 示例）；**触发时**另计一次小模型输入（运维成本，不单列入主 200k 饼图亦可） |
| **`aafter_agent`** | 写回长期记忆 | 否 | — | 0 |

**`wrap_model_call` 拼接后的 System 示例**（与 v5 §2.4 `build_ephemeral_prompt` 一致）：

```text
<原有 create_agent 的 system 全文>

[用户画像]
  domain: legal-tech
  language: zh
  role: 合同管理员
```

若 `preferences` 为空，则 **不追加**，该块 **0 Token**。

---

## 3. 工作记忆（§1.2 / §1.3 ③）拆解 — 对应「真实进模型的文本」

工作记忆 = **单次** LLM 调用的完整输入（v5：静态 System + 画像 + 历史 + 工具定义 + 当前输入）。与 Prompt 文档 **Slot** 对齐如下。

| 块 ID | 名称（v5 用语） | Prompt 文档 Slot | 实际 Prompt 是什么（模板级） | 设计预算 Token（32k turn） |
|-------|-----------------|------------------|------------------------------|---------------------------|
| **W1** | 静态 System Prompt | ① 部分 | `create_agent(..., prompt="你是一个多工具 AI 助手...")` + 角色/能力边界/输出格式 + 静态 few-shot | **~2000**（Slot① 合计，含 Registry 元数据时略增） |
| **W2** | Skill Registry 元数据 | ① | 可用 skill 列表摘要：`name + description + file_path`（**不含** SKILL.md 正文） | **~100**（文档述「约 50」/条累加） |
| **W3** | Active Skill 正文 | ② | `read_file` 读入的 `SKILL.md` → `ToolMessage` 进历史后，出现在 **messages** | **0–1500**（P1，未激活为 0） |
| **W4** | 动态 Few-shot | ③ | 检索到的示例对文本 | **0–800** |
| **W5** | RAG 背景 | ④ | Ephemeral 注入的请求级片段（**不写历史**） | **0–2000**（P2） |
| **W6** | 用户画像 Ephemeral | ⑤ / ① 动态段 | 见 §2 `build_ephemeral_prompt` | **0–500** |
| **W7** | 程序性记忆 | ⑥ | Procedural 文本（P2） | **0–400** |
| **W8** | 工具定义 Schema | ⑦ | 各工具的 JSON Schema / 函数描述（框架注入） | **~1200**（随工具数量变） |
| **W9** | 会话历史（含推理与 Tool） | ⑧ | `messages` 序列明文 | **弹性** = `24576 − 其余固定 Slot`（P0 约 **~20876** 上限量级） |
| **W10** | 本轮用户输入 | ⑩ | 当前 `HumanMessage.content` | **按实算**（高优先级保留） |

**P0 固定（文档）**：Slot①2000 + Slot⑤500 + Slot⑦1200 = **3700**（若画像为空则⑤可近 0）。

---

## 4. 三层记忆与「是否像 Prompt」

| 概念 | 持久化 | 在单次请求中的形态 | 典型 Prompt 片段 | Token |
|------|--------|--------------------|------------------|-------|
| **短期记忆** | checkpointer | **messages** | 多轮对话、工具输出、assistant 推理文字 | **Slot⑧** |
| **长期记忆 · profile** | Store | **仅 Ephemeral** 注入 System | `[用户画像]\n  k: v` | **Slot⑤** |
| **长期记忆 · skills/knowledge（P2）** | Store | 检索后多为 Ephemeral 或进 Skill 流程 | 视实现 | 见 Prompt 文档 |
| **工作记忆** | 不单独持久化 | 上述 W1–W10 的并集 | — | **单次请求总输入** |

---

## 5. 内容类型 × 注入策略（§1.4）与 Prompt 关系

| 内容类型 | 注入方式 | 写入历史？ | 实际进入模型的样子 |
|----------|----------|------------|-------------------|
| 用户画像 | Ephemeral | 否 | System 末尾 `[用户画像]` 块 |
| RAG chunk（P2） | Ephemeral | 否 | 请求级 system 或等价附加 |
| Human / AI / 工具结果 | Persistent | 是 | `messages` 中对应 message |

---

## 6. 与「Context Usage」饼图（200k 窗口）的类别映射 — 示例数值

下列对应你提供的 **Context Usage** 式 UI（**glm-4.7 · 49k/200k · 24%** 量级）。**类别名**保留产品化表述，**映射**到上文 W1–W10 / Memory 概念。

| UI 类别 | 架构映射 | 示例 Token（与 Context Usage 参考图一致） | 占 200k |
|---------|----------|---------------------------------------------|---------|
| **System prompt** | W1 中「静态模板」+ 输出格式 + 静态 few-shot（**不含**画像） | 5.2k | 2.6% |
| **System tools** | W8 内置工具 Schema（及运行时等价「系统工具」描述） | 15.9k | 8.0% |
| **MCP tools** | 扩展/MCP 工具 Schema（若有） | 9.7k | 4.9% |
| **Custom agents** | 子任务/多 Agent 指令（若有，P2） | 4.7k | 2.4% |
| **Memory files** | 长期记忆 **读出后**形成的 Ephemeral 块（`[用户画像]` 等） | 2.2k | 1.1% |
| **Skills** | W2 + W3（Registry + Active SKILL.md） | 9.3k | 4.7% |
| **Messages** | W9 + W10（历史 + 当前用户句） | 1.3k | 0.7% |
| **Free space** | 未使用上下文 | 118k | 59.2% |
| **Autocompact buffer** | `SummarizationMiddleware` 等预留缓冲（示意） | 33k | 16.5% |

**校验**：5.2+15.9+9.7+4.7+2.2+9.3+1.3 ≈ **48.3k**；与 UI 展示 **49k/200k** 为同一量级（取整与分词器差异）。

**Tab2 底部预算可视化（`frontend/pencil-new.pen` · `DDswp` · `cu9fd0174bf7`）**：用 **横向进度条** 表示 **当前会话下、本条组装进单次请求的工作记忆已用 tokens / 24,576（设计输入上限）**，并区分 **会话级本条输入预算** 与 **模型总上下文窗口（如 200k）**（⛶ Free、⛝ Autocompact 见上一卡片）。数值以 TokenCounter 实测为准。

---

## 7. 实现清单（前端 / 可观测）

1. **主 LLM 请求**：展示 **合并后** `system` + `messages` 的 Token 分解（W1–W10）。  
2. **Ephemeral**：单独标记「不进 checkpointer」的块（画像、RAG）。  
3. **压缩**：在 UI 上可显示「Autocompact buffer」与是否接近 `trigger` 阈值（v5 §2.6 `fraction 0.75` 等）。  
4. **数值来源**：后端对每个块跑 **同一套** TokenCounter，与 LLM 厂商计费对齐。

---

## 8. 存储粒度 `memory_type`（§1.5）与 Prompt

| `memory_type` | 持久化内容 | 如何变成「模型看见的文本」 | 典型 Token |
|---------------|------------|----------------------------|------------|
| **profile** | 用户画像 / Episodic | `build_ephemeral_prompt` → 追加到 **System**（Ephemeral） | 见 **W6** |
| **skills**（P2） | 技能库条目 | 经 Skill 管线进入 Registry 或检索注入 | 见 Prompt 文档 Skill 相关 Slot |
| **knowledge**（P2） | 向量知识 | 多经 RAG **Ephemeral** 注入 | 见 **W5** |

上述类型**本身**在 Store 中为结构化数据，**不**等于一整段直接进模型的 Prompt；只有经中间件/组装器转换后的文本才计费。

---

## 9. 参考文档位置

- Memory v5：§1.2–1.5、§2.4 `build_ephemeral_prompt`、§2.5 `wrap_model_call`、§2.6 压缩  
- Prompt + Context：§1.2 Slot ①–⑩、§② Token Budget Manager  

