# LangChain 与 LangGraph 代理架构深度解析（全文字版）

## 引言

本文档旨在系统梳理 LangChain 和 LangGraph 中与代理（Agent）相关的核心概念、模式及其最新实现。通过对 AgentExecutor、ReAct、Plan-and-Execute、工具调度器、Orchestrator、SubAgent 等概念的辨析，并结合 v1.0 版本的内置能力，帮助你建立清晰的知识体系，以应对从简单到复杂的各类 LLM 应用场景。

---

## 一、核心概念对比

| 概念 | 本质 | 功能 | 流程特点 | 典型场景 |
|------|------|------|----------|----------|
| **LangChain AgentExecutor** | 执行循环（runtime loop） | 驱动 ReAct 风格代理，串行调用工具 | 推理→行动→观察→循环 | 简单工具调用 |
| **LangGraph ReAct Loop 基础版** | 图结构的 ReAct 循环 | 同 AgentExecutor，但节点可定制 | 串行、单工具/步，但灵活插入逻辑 | 需自定义中间步骤的 ReAct |
| **Plan-and-Execute** | 规划与执行分离的高阶模式 | 规划器生成计划，执行器按计划执行，可动态调整 | 先规划后执行，可能并行 | 复杂任务分解（如旅行规划） |
| **工具调度器** | 工具调用顺序管理组件 | 根据依赖关系（DAG）调度工具执行 | 串行/并行/混合执行 | 需同时调用多个 API 的场景 |
| **SubAgent** | 分层结构中的子代理 | 主代理委托子任务给专用代理 | 主代理调用子代理→子代理独立运行 | 多领域知识整合 |
| **Orchestrator** | 协调多个组件/代理的系统 | 任务解析、分解、分配、调度、监控 | 宏观流程控制 | 多代理协作系统 |

---

## 二、ReAct 与 Plan-and-Execute 的本质区别

### ReAct（Reason + Act）
- **哲学**：边想边做，每一步推理后立即行动。
- **优点**：灵活，能根据实时反馈调整。
- **缺点**：缺乏长远规划，可能陷入局部最优。
- **流程**：

      ┌─────────┐
      │  推理   │
      └────┬────┘
           │ 生成 Action
           ↓
      ┌─────────┐
      │ 执行工具 │
      └────┬────┘
           │ 返回 Observation
           ↓
      ┌─────────┐
      │  推理   │ (基于 Observation)
      └────┬────┘
           │ ...
           ↓
      ┌─────────┐
      │最终答案 │
      └─────────┘

### Plan-and-Execute
- **哲学**：先想后做，按计划执行，必要时重新规划。
- **优点**：有全局视野，适合多步骤、有依赖的任务；可并行执行独立步骤。
- **缺点**：计划可能过时，需重新规划开销。
- **流程**：

      ┌─────────┐
      │  Planner │  (生成计划)
      └────┬────┘
           ↓ 计划 (步骤列表/DAG)
      ┌─────────┐
      │ Executor│  (按计划执行)
      └────┬────┘
           ↓ 执行结果
      ┌─────────┐
      │Replanner│  (检查是否需要调整)
      └────┬────┘
           │ 需要调整 ──→ 更新计划 ──→ Executor
           │ 不需要
           ↓
      ┌─────────┐
      │最终答案 │
      └─────────┘

**核心区别**：决策时机不同——ReAct 是“即时决策”，Plan-and-Execute 是“先规划再行动”。

---

## 三、LangChain 与 LangGraph 最新版本（v1.0+）内置能力

### 1. ReAct 模式
- **LangChain 1.0**：`create_agent` 统一接口，支持中间件（人工审批、摘要、PII 脱敏）和结构化输出 `response_format`。
- **LangGraph**：`create_react_agent` 预构建组件，默认采用 **v2 动态分发**。

#### `create_react_agent` v1 与 v2 流程对比

**v1（旧版）**：单个 tools 节点执行所有工具调用

    Agent节点 (多工具调用)
        │
        ↓
    tools节点 (依次/并行执行所有工具)
        │
        ↓
    Agent节点

**v2（当前默认）**：每个工具调用独立节点实例（基于 Send API）

    Agent节点 (工具调用 A, B, C)
        ├─(Send)─→ tools节点实例1 (执行 A) ──→ ToolMessage A
        ├─(Send)─→ tools节点实例2 (执行 B) ──→ ToolMessage B
        └─(Send)─→ tools节点实例3 (执行 C) ──→ ToolMessage C
                          ↓
                     汇聚结果
                          ↓
                     Agent节点

**优势**：真正并行、错误隔离、单工具细粒度控制（如可对特定工具调用设置中断）。

### 2. Plan-and-Execute 模式
LangGraph 官方提供三种实现模式作为示例：
- **基础 Plan-and-Execute**：Planner → Executor → Replanner。
- **ReWOO**：通过变量引用上下文，减少重复传递。
- **LLMCompiler**：Planner 生成 DAG，Task Fetching Unit 按依赖并行调度。

**LLMCompiler 流程示意图**：

          ┌─────────┐
          │ Planner │  (生成任务 DAG)
          └────┬────┘
               ↓ DAG
          ┌─────────┐
          │  执行器  │ (Task Fetching Unit)
          └────┬────┘
               │ 按依赖并行执行任务
         ┌─────┴──────┬──────┐
         ↓            ↓      ↓
      工具A        工具B   工具C (无依赖则并行)
         ↓            ↓      ↓
         └──────┬─────┘      │
                ↓ 依赖关系      │
          ┌─────────┐         │
          │ 工具D   │ ←────────┘
          └────┬────┘
               ↓ 结果
          ┌─────────┐
          │ Joiner  │ (汇总/决定是否重新规划)
          └─────────┘

### 3. 工具调度与执行
- **`ToolNode`**：内置工具执行节点，支持：
  - 并行执行多个工具调用。
  - 依赖注入（`InjectedState`, `InjectedStore`）。
  - 可配置错误处理。
  - 拦截器（修改参数、重试、缓存）。

**ToolNode 内部机制**：

    输入: AIMessage 包含 [ToolCall1, ToolCall2, ...]
              ↓
       ToolNode 解析每个 ToolCall
              ↓
       并行执行 (使用依赖注入解析参数)
       ┌─────────────┐
       │ 工具函数实例1 │
       ├─────────────┤
       │ 工具函数实例2 │
       ├─────────────┤
       │ 工具函数实例3 │
       └─────────────┘
              ↓
       收集所有 ToolMessage
              ↓
    输出: List[ToolMessage]

### 4. Orchestrator（多代理协调）
LangGraph 内置多种多代理模式：
- **基础多代理协作**：显式路由。
- **Agent Supervisor**：中央 supervisor 动态分配任务。
- **层次化 Agent 团队**：嵌套 supervisor 结构。

**Agent Supervisor 模式示意图**：

          ┌─────────────┐
          │   用户输入   │
          └──────┬──────┘
                 ↓
          ┌─────────────┐
          │  Supervisor │ (由 create_react_agent 实现)
          │  (团队经理)  │
          └──────┬──────┘
                 │ 使用 handoff 工具路由
         ┌───────┴───────┬─────────┐
         ↓               ↓         ↓
    ┌─────────┐   ┌─────────┐   ┌─────────┐
    │ Agent A │   │ Agent B │   │ Agent C │ (各为 create_react_agent)
    │ (专家1) │   │ (专家2) │   │ (专家3) │
    └────┬────┘   └────┬────┘   └────┬────┘
         │             │             │
         └─────────────┼─────────────┘
                       ↓
                ┌─────────────┐
                │ Supervisor  │ (汇总/继续分配)
                └─────────────┘
                       ↓
                ┌─────────────┐
                │   最终响应   │
                └─────────────┘

### 5. 结构化输出与标准化内容模型
- **`response_format`**：应用层合约，要求最终结果符合 Pydantic 模型。
- **`content_blocks`**：底层数据结构，统一不同模型返回的文本、工具调用、引用等。

    AIMessage.content_blocks = [
        TextBlock(...),
        ToolCallBlock(...),
        CitationBlock(...),
        ...
    ]

---

## 四、重要技术点深度剖析

### 1. `response_format` vs `content_blocks`
| 特性 | `response_format` | `content_blocks` |
|------|-------------------|-------------------|
| 层次 | 应用层 | 底层 |
| 目的 | 定义最终输出结构 | 标准化模型原始输出 |
| 使用 | 配置 `create_agent` 等 | 访问 `AIMessage.content_blocks` |
| 典型场景 | 要求返回 JSON 格式报告 | 解析多模态内容（文本+工具调用+引用） |

### 2. 依赖注入：`InjectedState` 与 `InjectedStore`
- **目的**：让工具访问 LLM 无法提供的上下文（如用户 ID、全局存储）。
- **`InjectedState`**：注入图状态中的特定字段。
- **`InjectedStore`**：注入持久化存储对象（用于长期记忆）。
- **用法**：工具参数用 `Annotated[T, InjectedState(...)]` 标记，框架自动填充。

**示例**：

    def get_user_info(query: str,  # 由 LLM 填写
                      current_user_id: Annotated[str, InjectedState("user_id")]  # 自动注入
                     ) -> str:
        return f"查询'{query}'的用户是 {current_user_id}"

### 3. `create_react_agent`、`ToolNode`、Orchestrator、Supervisor 的关系
- **`create_react_agent`**：基础执行单元（一线员工）。
- **`ToolNode`**：`create_react_agent` 内置的工具执行节点。
- **Supervisor**：协调智能体（团队经理），通常由 `create_react_agent` 实现，通过 handoff 工具分配任务。
- **Orchestrator**：包含 Supervisor 和多个 Worker 的整个系统（公司组织结构）。

### 4. 工具调度与 DAG 的支持程度
- **执行层面**：`ToolNode` 已内置并行执行；LangGraph 图引擎支持按依赖调度（需手动构建边）。
- **规划层面**：动态 DAG 生成（如 LLMCompiler 的 Planner）需自行开发 prompt 或微调，框架提供模式示例。

**DAG 示例**：

        工具A
          │
          ↓
        工具B     工具C (无依赖)
          │        │
          └───┬────┘
              ↓
            工具D (依赖 B 和 C)

---

## 五、执行模式支持情况（串行、并行、混合）

| 执行模式 | `create_react_agent` v2 | 实现方式 |
|----------|--------------------------|----------|
| **并行** | ✅ 内置支持 | 同一轮多工具调用 → 动态分发到独立节点 |
| **串行** | ✅ 内置支持 | 多轮 ReAct 循环（依赖由 Agent 推理管理） |
| **混合（部分并行+串行依赖）** | ⚠️ 部分支持 | 需结合多轮循环，或改用自定义 DAG 执行器（如 LLMCompiler） |

对于复杂依赖的混合模式，建议使用 LangGraph 构建自定义图（如 LLMCompiler 模式），由 Planner 生成 DAG，执行器按依赖调度。

---

## 六、总结与选择指南

### 1. 简单任务，顺序调用少量工具
- **选择**：`create_agent`（LangChain）或 `create_react_agent`（LangGraph）。
- **理由**：快速搭建，内置中间件满足常见需求。

### 2. 需要自定义流程（如人工审批、日志）
- **选择**：LangGraph 自定义图，在 `create_react_agent` 基础上增加节点或使用中间件。

### 3. 复杂任务，需先规划后执行
- **选择**：LangGraph 的 Plan-and-Execute 模式（参考官方示例）。
- **子场景**：若需并行执行独立步骤，采用 LLMCompiler 模式。

### 4. 多代理协作，不同领域专家分工
- **选择**：LangGraph 的多代理模式（Supervisor、层次化团队）。

### 5. 追求极致性能，需并行调用多个工具
- **选择**：`create_react_agent` v2 自动并行，或自定义 ToolNode。

### 6. 需动态生成执行 DAG
- **选择**：开发 Planner 节点（基于 LLM），配合执行器（如 ToolNode）实现。

---

## 七、结语

LangChain 和 LangGraph 提供了从高层抽象到低层编排的完整工具链。理解 ReAct、Plan-and-Execute、工具调度、Orchestrator 等概念的本质区别，以及它们在最新版本中的内置实现，能帮助你根据实际需求做出合理的技术选型，并灵活构建从简单到复杂的 LLM 应用。

希望这份文档能成为你后续学习和实践的可靠参考。如有新的问题，欢迎继续探讨！