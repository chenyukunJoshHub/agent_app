# Agent Skill 架构设计文档 v3

> 双层架构：
>
> - **第一层（框架无关）**：核心概念、Skill 数据模型、内容四层结构、Skill Protocol、触发标注原则、生命周期时序、与 Memory/Context 的交互
> - **第二层（LangChain 实现）**：API 映射、可直接复用的内置能力、自行开发部分
>
> 更新历史：
>
> - v2（2026-03）：源码级调研（OpenCode / OpenClaw / Anthropic Agent Skills）
> - v3（2026-03）：基于作者架构图补充三层运行架构、Skill Protocol、Skill 内容四层结构（metadata + instructions + examples + tools）；激活机制从 `activate_skill @tool` 简化为 `read_file`（方案 A，对齐业界实现）

> 实现状态标注：
>
> - `✅ 已实现`：当前项目代码已落地
> - `⬜ 目标态`：架构目标，当前项目尚未完整实现

---

## 第一层：框架无关的 Agent Skill 架构

### 1.1 核心问题：Skill 解决什么？

```
Agent 能力三层模型（互补不互斥）：

┌──────────────────────────────────────────────────────────────┐
│                       Agent 能力层                            │
│                                                              │
│  ┌─────────────────┐  ┌──────────────────┐  ┌────────────┐  │
│  │   工具层（Tool） │  │  技能层（Skill）   │  │  记忆层    │  │
│  │                 │  │                  │  │ (Memory)   │  │
│  │  我能调用什么？  │  │  面对这类任务，   │  │            │  │
│  │  （接口定义）    │  │  该怎么思考和     │  │ 我记得谁？  │  │
│  │                 │  │  行动？           │  │ （个性化）  │  │
│  │  terminal       │  │  （策略指南）     │  │            │  │
│  │  read_file      │  │                  │  │            │  │
│  │  tavily_search  │  │  legal-search    │  │  用户画像   │  │
│  │  ...            │  │  csv-reporter    │  │  交互历史   │  │
│  └────────┬────────┘  └────────┬─────────┘  └─────┬──────┘  │
│           └────────────────────┴──────────────────┘          │
│                              ↓                               │
│                   LLM 的单次 Context Window                   │
└──────────────────────────────────────────────────────────────┘

Skill 的独特价值：
  · Tool 告诉 LLM"可以做什么"（what）
  · Skill 告诉 LLM"应该怎么做"（how）+ "参考什么示例"（few-shot）
  · 同一个 tavily_search 工具 + legal-search Skill
    = 懂得优先搜官方法律数据库、按规范引用法条的 Agent
  · 不同 Skill 激活 → 同一 Agent 具备不同领域专业行为
```

#### Agent Skill 运行时三层架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    技能引导层（Skill Guidance）                    │
│                                                                 │
│  Agent 启动时执行，只运行一次：                                    │
│  1. 扫描 skills/ 目录，提取所有 active skill 的 metadata          │
│  2. 生成 SkillSnapshot（prompt 文本 + skills 元数据列表）          │
│  3. 将 SkillSnapshot.prompt + Skill Protocol（协议）注入 System Prompt  │
│     → 进入 Work Memory（每次 LLM 调用的 Slot ①）                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    核心工具层（Core Tools）                        │
│                                                                 │
│  Agent 可调用的原子工具（LLM 使用 Skill 时依赖这些工具执行）：       │
│                                                                 │
│  1. terminal           执行终端命令                               │
│  2. python_repl        执行 Python 代码                          │
│  3. fetch_url          HTTP 请求                                │
│  4. read_file          读取文件内容（⚠️ Skill 加载的核心工具）      │
│  5. search_knowledge_base  搜索知识库（RAG）                     │
│  6. browser_use        浏览器自动化操作                           │
│  7. tavily_search      网络实时搜索                              │
│                                                                 │
│  ⚠️ read_file 是 Skill 激活的直接手段：                           │
│     LLM 看到 SkillSnapshot 中的 file_path                        │
│     → 调用 read_file(path="~/.../SKILL.md")                     │
│     → 内容以 ToolMessage 进入 Work Memory（Slot ⑨）              │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                    智能体运行时（Agent Runtime）                   │
│                                                                 │
│  每个 ReAct turn 中按需执行：                                     │
│  1. LLM 判断当前任务匹配某个 skill → 调用 read_file 读取 SKILL.md  │
│  2. SKILL.md 完整内容动态注入 Work Memory（Slot ⑨ 历史区）         │
│  3. LLM 按 Skill 中的 instructions + examples 推理执行            │
└─────────────────────────────────────────────────────────────────┘
```

---

### 1.2 Skill 数据模型

```
SkillDefinition（完整定义，运行时解析层）
├── id               string            唯一标识（小写字母+数字+连字符，最长 64 字符）
├── name             string            显示名称
├── version          string            语义版本，如 "1.0.0"
├── metadata         SkillMetadata     触发元数据（注入 System Prompt，约 30~100 字符/个）
├── file_path        string            SKILL.md 绝对路径
│                                      SkillSnapshot 中暴露给 LLM
│                                      LLM 通过 read_file(path) 加载 skill 内容
├── tools            list[string]      本 skill 依赖的 core tools 声明（见 §1.3）
├── invocation       InvocationPolicy  调用策略
└── status           SkillStatus       active / disabled / draft

Skill/Metadata（轻量元数据，常驻 System Prompt Slot ①）
├── description   string        触发描述（最长 1024 字符）
│                               ⚠️ LLM 触发判断的唯一依据
│                               必须包含三项：
│                               · 做什么（what）：skill 的能力范围
│                               · 何时激活（when）：触发条件，尽量具体
│                               · 示例句式（可选）：典型用户说法
├── mutex_group   string | null 互斥组（同组最多同时激活一个）
└── priority      int           多 skill 同时满足时的优先级（越大越优先）

Skill/InvocationPolicy
├── user_invocable           bool   ⚠️ 预留字段（v2 设计），当前架构无实现路径
│                                   待 UI 层 / 命令层设计完成后定义调用机制
└── disable_model_invocation bool   是否从 SkillSnapshot 中隐藏（默认 false）
                                    true = LLM 不自动触发（当前 P0/P1 阶段保持 false 即可）
                                    ⚠️ user_invocable 与此字段的协同机制属 v2 设计范围，暂不定义

Skill/Status 枚举：
  · active   可被 LLM 发现和激活
  · disabled 已禁用（System Prompt 中不可见）
  · draft    草稿（不可见，仅内部编辑）
```

> **SkillDefinition 与 SkillEntry 的关系**
>
> 两者均由 `SkillManager.scan()` 解析同一个 SKILL.md frontmatter 生成，是同一数据源的两种视图：
>
> - `SkillDefinition`：完整版，包含全部字段，供运行时过滤（status 判断、invocation_policy 检查）使用
> - `SkillEntry`：快照投影，只保留 LLM 需要的字段（name + description + file_path + tools），写入 `SkillSnapshot`
>
> 生成关系：`SkillDefinition` → 过滤（status=active，disable_model_invocation=false）→ 投影 → `SkillEntry` → 构建 → `SkillSnapshot`

---

### 1.3 Skill 内容四层结构

> Skill 的正文（SKILL.md frontmatter 之后的内容）由四层组成。
> 这四层是 LLM 读取 skill 后实际使用的内容，缺少任意一层都会影响 skill 的效果。

```
┌──────────────────────────────────────────────────────────────┐
│               Skill 内容四层结构（SKILL.md 正文）              │
│                                                              │
│  ① metadata（元数据）                                         │
│     位置：YAML frontmatter                                    │
│     内容：id / name / version / description / tools /        │
│            mutex_group / priority / status / ...            │
│     作用：注入 System Prompt 供 LLM 判断是否激活               │
│           ⚠️ 不进入 Slot ⑨，只在 Slot ① 以摘要形式存在        │
│                                                              │
│  ② instructions（执行指令）                                   │
│     位置：正文 ## Instructions 节                             │
│     内容：告诉 Agent 如何一步一步执行此类任务的操作指南          │
│     作用：LLM 读取后严格按步骤推理，约束执行路径               │
│     示例：                                                    │
│       Step 1. 先调用 tavily_search 搜索官方法律数据库           │
│       Step 2. 验证来源（必须是 .gov.cn 域名）                  │
│       Step 3. 按《法律名称》第 X 条格式引用                    │
│                                                              │
│  ③ examples（示例）                                           │
│     位置：正文 ## Examples 节                                 │
│     内容：输入输出示例对（few-shot learning）                   │
│     作用：锁定模型行为，防止 Agent 自由发挥                     │
│           ⚠️ 这是 Skill 区别于普通 System Prompt 的关键：      │
│              通过示例约束输出格式和推理风格                     │
│     时序说明：                                                │
│       Examples 在 read_file 之后才进入 LLM 视野（Slot ⑨）。   │
│       因此 Examples 约束的是激活后的执行行为，                  │
│       而非激活决策本身（激活决策依赖 description，见 §1.4）。   │
│       第一次 read_file 调用完成后，后续所有 turn 均可见。       │
│     示例：                                                    │
│       Input:  "《劳动合同法》第 37 条的规定是什么？"             │
│       Output: "根据《劳动合同法》第 37 条（2022年修订版）：..."  │
│                                                              │
│  ④ tools（工具依赖）                                          │
│     位置：YAML frontmatter 的 tools 字段                      │
│     内容：本 skill 运行所需的 core tools 名称列表              │
│     作用：声明式依赖（LLM 知道可以用哪些工具执行此 skill）       │
│           P1 可做强制检查：tools 不满足时 skill 不可激活        │
│     示例：tools: [tavily_search, read_file]                  │
└──────────────────────────────────────────────────────────────┘

四层的 Token 分配：
  ① metadata     → Slot ①（System Prompt，约 30~100 字符，常驻）
  ② instructions → Slot ⑨（历史区，约 300~800 Token，激活后注入）
  ③ examples     → Slot ⑨（历史区，约 200~600 Token，与 instructions 同批注入）
  ④ tools        → Slot ①（元数据摘要中说明，约 20 字符，常驻）

激活前（LLM 只看到）：
  [skill 名称 + description + tools 摘要] ← Slot ① ~100 字符

激活后（LLM 能看到）：
  [instructions + examples 完整内容] ← Slot ⑨ ~500~1400 Token
```

---

### 1.4 Skill Protocol（技能调用协议）

> Skill Protocol 是注入 System Prompt 的一段**行为约定文本**，不是代码模块。
> 它定义 LLM 在 skill 使用过程中的协议约束。
> 与 SkillSnapshot（skill 列表）一起常驻 Slot ①。

```
Skill Protocol 约定（基础 4 条 + 项目扩展 1 条）：

① 识别约定（When — 何时激活）
   当用户请求或上下文匹配某个 skill 的 description 时，
   在本次 ReAct 循环中激活该 skill，再开始主任务执行。
   同一 session 中，若历史消息里已有该 skill 的内容，直接复用，不重复读取。

② 调用约定（How — 如何激活）
   使用 read_file 工具读取 skill 的文件路径：
     read_file(path="<file_path from SkillSnapshot>")
   禁止凭记忆执行 skill，必须先读取文件获得最新内容。
   ⚠️ file_path 以 SkillSnapshot 中提供的路径为准，不得自行猜测路径。

③ 激活后行为约定（What — 如何执行）
   读取 SKILL.md 后：
   - 严格按照 ## Instructions 中的步骤顺序执行，不得跳步或自由发挥
   - 若 skill 提供了 ## Examples，输出格式和推理风格必须与示例保持一致
     ⚠️ Examples 在 read_file 返回后才可见，约束的是本次及后续 turn 的执行行为，
        不约束 read_file 之前的激活决策
   - 若 skill 声明了 tools 依赖，优先使用这些工具完成任务
   - skill 执行完毕后，用自然语言向用户说明执行了哪个 skill

④ 冲突约定（Conflict — 多 skill 竞争）
   若多个 skill 同时匹配：
   - 同一 mutex_group 内优先激活 priority 更高的一个（⚠️ 当前主要依赖 LLM 语义决策，代码层未做硬约束） ⬜
   - 不同 mutex_group 的 skill 可以在同一 session 中先后激活
   - 同一 turn 内只激活一个 skill（避免 Token 爆炸）

⑤ 手动指定约定（Manual Hint — 用户显式指定）
   当用户消息以 [Skill: <name>] 开头时，视为用户显式要求优先使用该 skill。
   你应优先通过 read_file 加载该 skill 后再执行任务。

System Prompt 中 Skill Protocol 的写入位置：
  Slot ①  System Prompt
          = 角色定义
          + Skill Protocol（基础 4 条 + 手动指定约定，约 200 Token，常驻）   ← 新增
          + SkillSnapshot.prompt（skill 列表，精确字符控制）  ← 已有
          + 静态 Few-shot
          + 用户画像（Ephemeral）
```

#### Skill Protocol 与 SkillSnapshot.prompt 的区别

> **常见混淆：SkillSnapshot.prompt 是 Skill Protocol 吗？答：不是，两者都在 Slot ①，但职责完全不同。**

```
                 ┌─────────────────────────────────────────────────────┐
                 │                 Slot ① System Prompt                │
                 │                                                     │
                 │  ┌────────────────────────────┐                    │
                 │  │      Skill Protocol         │  ← 静态"规则"     │
                 │  │  基础 4 条 + 手动指定约定       │    ~200 Token 固定 │
                 │  │  告诉 LLM：怎么使用 skills  │                    │
                 │  └────────────────────────────┘                    │
                 │  ┌────────────────────────────┐                    │
                 │  │   SkillSnapshot.prompt      │  ← 动态"菜单"     │
                 │  │  当前可用 skill 列表 (XML)  │    字符预算精确控制 │
                 │  │  告诉 LLM：有哪些 skills    │                    │
                 │  └────────────────────────────┘                    │
                 └─────────────────────────────────────────────────────┘

对比维度        Skill Protocol                         SkillSnapshot.prompt
────────────    ────────────────────────    ─────────────────────────────
比喻            餐厅"用餐规则"              餐厅"今日菜单"
内容            协议约束文本（基础 4 条 + 手动指定）  skill 列表（XML，含 file_path）
性质            静态，设计时写定             动态，Agent 启动时重建
变化时机        不变（除非架构调整）         skills 增减 / 热更新时重建
Token 估算      约 200 Token，固定           按 skills 数量精确计算
谁在维护        架构师（写入 system_prompt） SkillManager.build_snapshot()
```

两者协同工作：Protocol 告诉 LLM "你必须用 read_file 激活 skill"，
Snapshot 告诉 LLM "可以激活的 skill 和对应路径在这里"。

---

### 1.5 触发机制

> **设计基准（源码验证）：**
> OpenCode、OpenClaw 均只依赖 `description` 字段的语义触发，无独立的结构化标注层。
> 本设计对齐此基准：**触发逻辑完全写入 description**，LLM 直接语义匹配，无额外标注结构。

#### description 写作规范（触发质量的关键）

```
description 必须包含三项：

① 能力范围（what）
   说明 skill 能处理什么类型的任务
   示例："专业法律法规检索与引用规范，适用合同合规类任务"

② 触发条件（when）— 具体，不模糊
   列举典型触发词汇 / 场景 / 用户说法
   示例："触发条件：用户提到合同/签署/违约/合规/法律条款；
          任务涉及法律文本理解或合规风险评估；
          用户明确要求从法律角度分析"

③ 互斥信息（可选）
   说明同组内互斥的其他 skill
   示例："互斥组：document-analysis"

触发决策逻辑：
  · LLM 语义匹配 description 文本，无结构化规则层
  · 同一 mutex_group 当前为"应优先"而非硬约束：依赖 description + priority 排序的软引导（运行时硬互斥待实现）⬜
  · 历史中已有该 skill 内容时，不重复读取（Protocol 约定 ①）
```

#### SkillSnapshot.prompt 格式（注入 Slot ①）

```
两种格式，根据字符预算自动选择（见 §1.7）：

格式一（完整格式，字符预算充足时）：
<skills>
  以下 skills 提供特定任务的操作指南。
  当任务匹配时，使用 read_file 工具读取对应 file_path 获取完整指南。

  <skill>
    <name>legal-search</name>
    <description>
      专业法律法规检索与引用规范，适用合同合规类任务。
      触发条件：用户提到合同/签署/违约/合规/法律条款；任务涉及法律风险评估。
      依赖工具：tavily_search, read_file
      互斥组：document-analysis
    </description>
    <file_path>~/.../skills/legal-search/SKILL.md</file_path>
  </skill>
</skills>

格式二（紧凑格式，字符超限时降级）：
<skills>
  ⚠️ 技能目录（省略描述，详情通过 read_file 读取）
  <skill>
    <name>legal-search</name>
    <file_path>~/.../skills/legal-search/SKILL.md</file_path>
  </skill>
</skills>

注：路径中 homedir 替换为 ~ 节省 5~6 字符/skill（OpenClaw workspace.ts 优化）
```

---

### 1.6 Skill 生命周期

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Skill 完整生命周期                              │
│                                                                      │
│  ① 定义      ② 注册/快照       ③ 发现            ④ 激活              │
│                                                                      │
│  编写        Agent 启动        LLM 读取           LLM 判断匹配        │
│  SKILL.md    扫描 skills/      Slot ① 中的        → 调用             │
│  四层内容    解析 frontmatter   SkillSnapshot      read_file(         │
│             生成 Snapshot      中的 skill 列表      file_path)        │
│             注入 Slot ①        自主决定是否读取                        │
│                                                                      │
│     │              │                │                 │              │
│     ▼              ▼                ▼                 ▼              │
│  ⑤ 内容加载   ⑥ 注入历史       ⑦ 持久化         ⑧ 复用/过期         │
│                                                                      │
│  read_file    SKILL.md 完整     ToolMessage        同 session 后续   │
│  读取         内容（instructions  随 checkpointer   turn 直接复用      │
│  SKILL.md     + examples）以      自动持久化         同 mutex_group    │
│  正文         ToolMessage 进      到 Short Memory    新 skill 激活时   │
│              Slot ⑨                                 旧 skill 不再是   │
│                                                      当前活跃 skill   │
│                                                                      │
│  ⑨ 热更新（P2）                                                       │
│  文件变更 → SkillManager 重建 Snapshot → 下一 turn 生效               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

SkillSnapshot（会话快照）
├── prompt      string   已生成的 System Prompt 注入文本（完整或紧凑格式）
├── skills      list     [{name, description, file_path, tools}]
├── skill_filter list|None  当前 agent 允许的 skill 白名单
└── version     int      快照版本号（文件变更时递增）
```

---

### 1.6.1 SkillSnapshot 完整示例

> 以下示例展示：3 个 skill 中，1 个因 status=draft 被过滤，最终生成 2-skill 快照的完整过程。

#### 前置条件：skills/ 目录扫描结果

```
skills/
├── legal-search/SKILL.md    → status: active  ✓ 纳入快照
├── csv-reporter/SKILL.md    → status: active  ✓ 纳入快照
└── ppt-generator/SKILL.md   → status: draft   ✗ 过滤
```

#### SkillSnapshot 对象（Python dataclass）

```python
@dataclass
class SkillEntry:
    name: str
    description: str           # 含触发条件 + 互斥组，供 LLM 语义匹配
    file_path: str             # ~ 缩写形式，节省字符
    tools: list[str]           # 依赖工具列表，注入 description 尾部

@dataclass
class SkillSnapshot:
    version: int               # 3（文件变更时递增）
    skill_filter: list[str] | None  # None = 不限制，全部 active skill 可用
    skills: list[SkillEntry]   # 已过滤的可用 skill 列表
    prompt: str                # 最终注入 Slot ① 的 XML 文本

# 具体值
snapshot = SkillSnapshot(
    version=3,
    skill_filter=None,   # 当前 agent 无白名单限制
    skills=[
        SkillEntry(
            name="legal-search",
            description=(
                "专业法律法规检索与引用规范，适用合同合规类任务。\n"
                "触发条件：用户提到合同/签署/违约/合规/法律条款；任务涉及法律风险评估。\n"
                "互斥组：document-analysis | 依赖工具：tavily_search, read_file"
            ),
            file_path="~/.config/agent/skills/legal-search/SKILL.md",
            tools=["tavily_search", "read_file"],
        ),
        SkillEntry(
            name="csv-reporter",
            description=(
                "CSV 数据分析、统计摘要与可视化建议规范。\n"
                "触发条件：上下文存在 CSV 文件或工具返回表格数据；用户要求数据统计或生成报告。\n"
                "互斥组：（无）| 依赖工具：python_repl, read_file"
            ),
            file_path="~/.config/agent/skills/csv-reporter/SKILL.md",
            tools=["python_repl", "read_file"],
        ),
    ],
    prompt="...",   # 见下方 build_snapshot() 生成的 XML 文本
)
```

#### build_snapshot() 生成的 prompt 文本（注入 Slot ①）

```
snapshot.prompt =

<skills>
  以下 skills 提供特定任务的操作指南。
  当任务匹配时，使用 read_file 工具读取对应 file_path 获取完整指南。

  <skill>
    <name>legal-search</name>
    <description>
      专业法律法规检索与引用规范，适用合同合规类任务。
      触发条件：用户提到合同/签署/违约/合规/法律条款；任务涉及法律风险评估。
      互斥组：document-analysis | 依赖工具：tavily_search, read_file
    </description>
    <file_path>~/.config/agent/skills/legal-search/SKILL.md</file_path>
  </skill>

  <skill>
    <name>csv-reporter</name>
    <description>
      CSV 数据分析、统计摘要与可视化建议规范。
      触发条件：上下文存在 CSV 文件或工具返回表格数据；用户要求数据统计或生成报告。
      互斥组：（无）| 依赖工具：python_repl, read_file
    </description>
    <file_path>~/.config/agent/skills/csv-reporter/SKILL.md</file_path>
  </skill>
</skills>

字符统计：
  header 文本：95 字符
  legal-search：253 字符（name 12 + description 110 + file_path 52 + XML 标签 79）
  csv-reporter：241 字符（name 11 + description 98 + file_path 51 + XML 标签 81）
  总计：589 字符 / 30,000 字符上限 → 使用完整格式（格式一）
  ppt-generator 因 status=draft 不计入
```

#### Slot ① 最终注入内容（拼接顺序）

```
┌─────────────────────────────────────────────────────────┐
│  Slot ①  System Prompt 实际写入内容                      │
│                                                         │
│  [角色定义]                                              │
│  你是一个专业的 AI 开发助理…（约 150 字符）               │
│                                                         │
│  [Skill Protocol — 静态规则文本，约 200 Token]           │
│  当用户请求匹配某个 skill 的描述时，在本次 ReAct 循环中…  │
│  read_file(path="<file_path from SkillSnapshot>")       │
│  禁止凭记忆执行 skill，必须先读取文件获得最新内容…        │
│  （协议完整文本）                                        │
│                                                         │
│  [SkillSnapshot.prompt — 动态菜单，589 字符]             │
│  <skills>                                               │
│    <skill>                                              │
│      <name>legal-search</name>                          │
│      <description>…</description>                       │
│      <file_path>~/.config/…/SKILL.md</file_path>        │
│    </skill>                                             │
│    <skill>                                              │
│      <name>csv-reporter</name>                          │
│      …                                                  │
│    </skill>                                             │
│  </skills>                                              │
│                                                         │
│  [静态 Few-shot + 用户画像 Ephemeral]                    │
└─────────────────────────────────────────────────────────┘
```

#### LLM 激活流程验证（以 legal-search 为例）

```
用户输入："帮我检查这份合同有没有违约条款"

LLM 读取 Slot ① →
  1. 匹配 SkillSnapshot：legal-search description 含 "合同/违约条款" → 匹配
  2. 遵守 Skill Protocol 约定 ②：必须先调用 read_file
  3. 发起工具调用：
       read_file(path="~/.config/agent/skills/legal-search/SKILL.md")
  4. ToolMessage 返回 SKILL.md 完整内容 → 写入 state["messages"] → Slot ⑨
  5. 按 ## Instructions 执行合同分析，按 ## Examples 格式输出
  6. 执行完毕告知用户："已使用 legal-search 技能进行合同合规分析"
```

---

### 1.7 与 Memory + Context 模块的交互时序

```
─── Agent 启动（初始化阶段，技能引导层执行）────────────────────────

[SkillManager] 扫描 skills/ 目录
      │
      ├─→ 解析每个 SKILL.md 的 frontmatter → 获取 metadata + tools + invocation
      ├─→ 过滤 disabled / draft / disable_model_invocation=true
      ├─→ 构建 SkillSnapshot（prompt + [{name, description, file_path, tools}]）
      ├─→ 将 Skill Protocol + SkillSnapshot.prompt 写入 System Prompt Slot ①
      └─→ 注册 Core Tools（含 read_file）到 Agent 工具列表

─── turn N 开始 ──────────────────────────────────────────────────────

① 加载长期记忆（用户画像）
      → 缓存到 state["memory_ctx"]

② 恢复短期记忆（对话历史）
      checkpointer 恢复 state["messages"]
      ⚠️ 若历史中已有某 skill 的 read_file ToolMessage
         → LLM 下一步直接复用，Protocol ① 约定不重复读取

─── ReAct 循环（每次 LLM 调用，智能体运行时执行）─────────────────

③ 组装 Context Window（工作记忆）
      ┌────────────────────────────────────────────────────────────┐
      │ Slot ①  System Prompt                                     │
      │         = 角色定义                                         │
      │         + Skill Protocol（基础 4 条 + 手动指定约定，约 200 Token，常驻） │
      │         + SkillSnapshot.prompt（skill 列表，精确字符控制）  │
      │         + 静态 Few-shot                                    │
      │         + 用户画像（Ephemeral 注入，不写历史）              │
      ├────────────────────────────────────────────────────────────┤
      │ Slot ⑧  工具 Schema（含 read_file 等 Core Tools）          │
      ├────────────────────────────────────────────────────────────┤
      │ Slot ⑨  对话历史                                           │
      │         = Human 消息 + AI 回复 + 推理轨迹                  │
      │         + 普通工具 ToolMessage                             │
      │         + read_file ToolMessage（已激活 skill 的内容）      │
      ├────────────────────────────────────────────────────────────┤
      │ Slot ⑩  输出格式规范（由 Prompt 模块提供）                  │
      └────────────────────────────────────────────────────────────┘

④ LLM 调用
      │
      ├─→ 路径 A：需要 Skill，历史中无该 skill 内容
      │          ↓
      │     LLM 输出 tool_call:
      │       read_file(path="~/.../skills/legal-search/SKILL.md")
      │          ↓
      │     Tool Executor 执行 read_file
      │          ↓
      │     返回 ToolMessage(content=<SKILL.md 完整内容>)
      │     内容包含：instructions + examples
      │          ↓
      │     追加到 state["messages"]（checkpointer 自动持久化）
      │          ↓
      │     回到 ③，LLM 按 instructions + examples 推理执行
      │
      ├─→ 路径 B：Skill 内容已在历史 Slot ⑨ 中可见
      │          ↓
      │     LLM 直接按已加载 skill 的指南推理（Protocol ① 约定）
      │
      └─→ 路径 C：当前任务无需 Skill
                 ↓
            普通推理 + 工具调用

─── turn N 结束 ──────────────────────────────────────────────────────

⑤ 保存短期记忆
      checkpointer 自动保存（含 skill ToolMessage）
```

---

### 1.8 Skill 互斥与字符预算管理

```
互斥规则（同一 mutex_group 内）：
  ┌──────────────────────────────────────────────────────────┐
  │  turn 3 激活 contract-analyzer（mutex: document-analysis）│
  │       → ToolMessage_A 进入历史                            │
  │                                                          │
  │  turn 5 激活 legal-search（mutex: document-analysis）    │
  │       → ToolMessage_B 进入历史                           │
  │       → ToolMessage_A 仍保留在历史中（消耗 Token 预算），  │
  │         但 legal-search 在语义上应被优先视为当前活跃 skill   │
  │         ⚠️ 当前项目未实现“同组旧 skill 自动清理”硬逻辑（目标态）⬜ │
  └──────────────────────────────────────────────────────────┘

System Prompt 字符预算（精确控制，来源：OpenClaw workspace.ts 源码）：

  预算上限：maxSkillsPromptChars = 30,000 字符
  单个 skill 字符数（完整格式）：
    = 97 + len(name) + len(description) + len(file_path)
  整体：total = 195 + Σ(97 + len(name_i) + len(desc_i) + len(path_i))

三级降级策略：
  ① 完整格式（name + description + tools + file_path）
  ② → 紧凑格式（name + file_path，省略 description）    字符超限时
  ③ → 二分截断（紧凑格式仍超限，保留尽可能多的 skill）   + 截断警告

其他上限（与当前代码一致）：
  maxSkillsInPrompt   = 未设置硬上限（当前由 30,000 字符预算间接约束）✅
  maxSkillFileBytes   = 100,000 bytes（SkillManager.scan 解析上限）✅
  read_file MAX_FILE_BYTES = 256,000 bytes（工具读取上限，独立于 scan）✅
```

---

### 1.9 与 Multi-Agent 架构的边界说明

> Multi-Agent 架构在独立文档讨论，以下仅标注当前 Skill 设计在该场景下会变化的部分。

```
当前设计（单 Agent + tool call）：
  · LLM 用 read_file 读取 SKILL.md → 内容注入当前 Agent 的 Work Memory
  · Skill 的作用 = 告诉当前 LLM"怎么做"（策略 + 示例）

⚠️ Multi-Agent 场景下需要重新讨论：
  · read_file 的语义是否变为"委托给专属 Sub-Agent"
  · SKILL.md 的 instructions 是否升级为"Sub-Agent System Prompt"
  · Skill Protocol 是否需要 per-agent 版本
  · mutex_group 在并发 Sub-Agent 场景下的处理
  · SkillSnapshot 是否按 Sub-Agent 粒度分别构建
  · Sub-Agent 是否共享 Long Memory

⬜ description 触发机制预计保持不变，与架构层升级解耦。
```

---

### 1.10 Skill 加载优先级与目录规范

```
加载优先级（来源：OpenClaw workspace.ts 源码，从低到高）：

  ① extra（配置文件 extraDirs）
  ② bundled（内置打包）
  ③ managed（~/.openclaw/skills）
  ④ agents-skills-personal（~/.agents/skills）
  ⑤ agents-skills-project（.agents/skills，当前项目）
  ⑥ workspace（skills/，项目根目录）  ← 最高优先级

  当前项目（P0 简化）：只使用 workspace（skills/）一个层级

目录结构：
  skills/
  ├── legal-search/
  │   └── SKILL.md
  ├── csv-reporter/
  │   └── SKILL.md
  └── contract-analyzer/
      └── SKILL.md

SKILL.md 完整格式（四层结构）：
────────────────────────────────────────────────
---
name: legal-search
description: >
  专业法律法规检索与引用规范，适用合同合规类任务。
  触发条件：用户提到合同/签署/违约/合规/法律条款；
           任务涉及法律文本理解或合规风险评估；
           用户明确要求从法律角度分析。
  互斥组：document-analysis
version: 1.0.0
status: active
mutex_group: document-analysis
priority: 10
disable-model-invocation: false
tools:
  - tavily_search
  - read_file
---

# 法规查询 Skill

## Instructions

Step 1. 使用 tavily_search 搜索关键词，限定域名 site:npc.gov.cn 或 site:court.gov.cn
Step 2. 验证搜索结果来源，非官方网站的内容标注"非官方，仅供参考"
Step 3. 按以下格式引用法条：《法律名称》第 X 条（YYYY 年修订版）
Step 4. 若用户追问，重复 Step 1~3，不得凭记忆给出法条内容

## Examples

Input:  "《劳动合同法》第 37 条是什么规定？"
Output: "根据《劳动合同法》第 37 条（2022 年修订版）：
         劳动者提前三十日以书面形式通知用人单位，可以解除劳动合同。
         来源：全国人民代表大会（npc.gov.cn）"

Input:  "合同违约责任怎么算？"
Output: "合同违约责任的计算需参考以下法条：
         ..."
────────────────────────────────────────────────

字段约束（来源：Anthropic 官方 Agent Skills 规范）：
  name                      小写字母+数字+连字符，最长 64 字符
  description               最长 1024 字符，触发决策完全依赖此字段
                            需包含：能力范围（what）+ 触发条件（when）
  tools                     仅声明 Core Tools 层中已定义的工具名称
  disable-model-invocation  ⚠️ 预留字段，P0/P1 阶段默认 false 即可
```

---

### 1.11 已知陷阱与应对策略

> 以下陷阱来自 Skill 机制的结构性缺陷，不依赖具体实现，任何使用 read_file + System Prompt 注入方案的 Agent 都会遇到。

---

#### 陷阱 1：Examples 过拟合 — 输出"模板化垃圾"

```
现象：
  LLM 激活 skill 后，无论用户输入是什么，
  都输出与 ## Examples 高度相似的模板结构，
  而非真正理解问题后的推理结果。

根因：
  few-shot examples 对 LLM 有强锚定效果。
  复杂任务中，LLM 倾向于"填模板"而非"推理"，
  尤其当 examples 格式固定、字段完整时。

典型场景：
  legal-search 的 example 格式是"第 X 条（YYYY 年修订）"
  → 用户问"违约责任怎么算"（需要推理组合）
  → LLM 仍输出套模板格式，却没有实质推理内容

应对策略：
  · Examples 只写"典型场景"，不写"边界场景"
  · Example 数量控制在 2~3 条，不超过 5 条
  · 在 Instructions 末尾显式声明：
      "Examples 仅供格式参考，不限制推理路径"
  · 复杂开放式任务考虑不提供 Examples，只用 Instructions
```

---

#### 陷阱 2：tools 声明对 LLM 没有约束力

```
现象：
  frontmatter 声明 tools: [tavily_search]
  但 LLM 实际执行时：
  · 可能完全不调用 tavily_search
  · 可能改用 fetch_url 或 python_repl 代替
  · 或直接从训练数据中凭记忆给出答案

根因：
  tools 字段只是注释性声明，不是 API 约束。
  LLM 看到的是自然语言描述，不是强制执行规则。
  没有任何框架机制会因为 tools 声明而拒绝或强制调用某个工具。

应对策略：
  · 在 Instructions 中显式要求：
      "Step 1. 必须调用 tavily_search，禁止凭记忆给出法条内容"
  · 如需强约束，在 SkillManager 层做后处理检查（P1）：
      若 skill 的 ToolMessage 链中缺少声明的 tool 调用，发出警告
  · 接受 LLM 的灵活性：tools 声明主要用于文档说明，
    强制执行靠 Instructions 文本，而非字段本身
```

---

#### 陷阱 3：instructions + examples 累积炸上下文

```
现象：
  同一 session 中激活 2~3 个 skill 后，
  Slot ⑨ 中的 ToolMessage 占用快速膨胀：
    · 每个 SKILL.md 约 500~1,400 Token
    · 3 个 skill = 最多 4,200 Token 只用于 skill 内容
    · 加上对话历史，较短的 Context Window 面临压力

根因：
  read_file 读取的完整 SKILL.md（instructions + examples）
  以 ToolMessage 形式追加到 state["messages"]，对话内不会自动删除。
  没有任何框架内置的针对 skill ToolMessage 的自动清理机制。

  checkpointer 与 thread_id 的关系（精确说明）：
  LangGraph checkpointer 存储的 key 是 thread_id，而非"session"。
  同一 thread_id 的每次调用都会恢复完整 state["messages"]。
  因此：

  · InMemorySaver（仅开发/测试备选形态）：
    → skill ToolMessage 只在当前进程运行期间存在
    → 重启即重置，实际无持久化问题

  · AsyncPostgresSaver（当前项目默认运行形态）+ 永久 thread_id（用户对话历史设计）：
    → 同一用户下次回来时，历史 skill ToolMessage 从数据库恢复
    → skill 内容长期积累，才出现"持久化污染"问题

  ⚠️ 结论：跨会话污染是否成立，取决于 thread_id 管理策略：
    - 每次新对话分配新 thread_id → 不存在跨会话问题
    - 用户共用持久化 thread_id  → 需要重点关注（当前项目即为该形态）

  ⚠️ 行业现状：
  OpenCode / OpenClaw 是 CLI 工具，每次任务执行完即结束，
  不存在持久化 thread_id 的场景，无参考实现。

应对策略（有明确来源的方案）：

  ✅ 源头控制体积（OpenClaw 源码验证）：
     · 单个 SKILL.md 体积上限：maxSkillFileBytes = 100,000 bytes（scan 阶段）
       超过此限制的 SKILL.md 在 SkillManager.scan() 阶段直接跳过
     · read_file 工具读取上限：MAX_FILE_BYTES = 256,000 bytes（工具层独立限制）
     · 编写规范：instructions ≤ 10 步，examples ≤ 3 条，目标 ≤ 600 Token/文件

  ✅ 利用大上下文窗口（现实可行）：
     · Claude / GPT-4o 的 Context Window 为 128K~200K Token
     · 20 个 skill × 1,400 Token = 28,000 Token，在 200K 窗口中只占 14%
     · 对当前规模（≤ 20 个 skill）不是实际瓶颈，无需额外处理

  🔧 P1 可做（自研，无行业参考）：
     · Context Window 压缩时，同 mutex_group 的非活跃 skill ToolMessage 优先清理（当前未实现）⬜
     · 使用 LangGraph 内置的 trim_messages 做通用历史裁剪，
       skill ToolMessage 作为普通消息参与裁剪，不做特殊处理

  ❌ 不建议：对 skill ToolMessage 做"摘要化（500 Token → 50 Token）"
     · OpenCode / OpenClaw 均无此实现
     · 修改已持久化的 ToolMessage 与 checkpointer 有兼容性风险
     · 在 Context Window 够用的前提下，这是过度设计
```

---

#### 陷阱 4：Skill 常驻 Slot ⑨ — 污染后续推理

```
现象：
  legal-search 激活后，其 instructions + examples 一直在 Slot ⑨。
  后续用户问完全无关的问题时，LLM 仍受 skill 内容影响：
  · 回答中莫名引用法条格式
  · 在不需要的场景中调用 tavily_search
  · 推理风格被 examples 的输出格式污染

根因（精确表述）：
  SKILL.md 内容以 ToolMessage 形式追加到 state["messages"]，
  LLM 每次调用都能看见它，形成持续的 in-context 偏置。
  这是消息列表模型的通用行为，不是 skill 特有的。

  生命周期澄清（checkpointer 与 thread_id 机制）：
  · 对话内（同一 thread_id）：ToolMessage 随 state["messages"] 累积，不自动删除 ← 直接根因
  · 跨会话是否成立，取决于 thread_id 策略：
      每次对话分配新 thread_id → skill ToolMessage 随会话结束消亡，无持久化问题
      用户共用持久化 thread_id → AsyncPostgresSaver 场景下，skill 内容从数据库恢复长期存在
  · InMemorySaver（开发/测试备选）：进程重启即重置，实际无持久化问题

  Protocol 约定"同 session 直接复用"本意是避免重复 read_file，
  但副作用是 skill 内容对当前 session 所有后续 turn 可见。

应对策略：

  ✅ P0（零成本，效果有限）：
     在 Instructions 末尾写入约束文本：
     "本技能仅在用户明确需要法律检索时适用，其他场景请忽略本 skill 的格式要求"
     局限：依赖 LLM 理解和遵守，不是硬约束

  🔧 P1（自研，需单独设计，当前方案不完整）：
     提供"清除当前对话 skill 上下文"的显式命令，
     让用户或 Agent 在切换主题时主动触发
     ⚠️ 以下三个约束在实现前必须先设计，否则会引入 bug：
     · When：何时触发过滤（用户命令 / Agent 判断 / 主题切换检测）
     · Write-back：过滤后必须写回 checkpointer，否则下次 session 恢复时 ToolMessage 重新出现
     · Consistency：LangGraph messages 链中，AIMessage（含 tool_call）与 ToolMessage 必须成对存在，
       单独删除 ToolMessage 会导致消息链断裂，LangGraph 可能报错

  ⚠️ 不建议（高成本，兼容性风险）：
     按 turn 有效期管理 Skill ToolMessage（超出 N turn 后自动移除），
     需要修改 state["messages"] 管理逻辑，与 checkpointer 持久化有兼容性风险，
     且在 Context Window 充足时收益有限
```

---

#### 陷阱 5：skill 数量 > 30 时，LLM 识别能力明显下降

```
现象：
  SkillSnapshot.prompt 中列出 30+ 个 skill 后：
  · LLM 开始漏判（该激活的 skill 没激活）
  · LLM 开始误判（不该激活的 skill 被激活）
  · "注意力稀释"问题：skill 列表过长，LLM 对后半段 skill 识别率显著低于前半段

根因：
  LLM 的注意力在长列表中分布不均，
  越靠近 System Prompt 末尾的内容权重越低。
  当 skill 数量过多时，description 的语义区分度下降，
  LLM 无法精准匹配。

应对策略：
  · P0~P1 阶段：skill 总量控制在 20 个以内，不需要特殊处理
  · P2（skill 数量 > 30 时）：引入候选集检索（Top-K Skills）
    ┌────────────────────────────────────────────────────────┐
    │  用户输入                                               │
    │       ↓                                                │
    │  Embedding 检索（向量相似度）                           │
    │  全量 skill 描述库 → 召回 Top-K 候选（K = 5~10）        │
    │       ↓                                                │
    │  只将 Top-K skill 注入 SkillSnapshot.prompt             │
    │  （替代全量注入）                                       │
    │       ↓                                                │
    │  LLM 在小候选集内做最终判断                              │
    └────────────────────────────────────────────────────────┘
  · 实现依赖：skills/ 目录的 description 向量化 + 轻量向量检索
    可复用项目已有的 RAG / search_knowledge_base 工具
```

---

#### 陷阱 6：纯 LLM 触发不稳定 — 引入 Orchestrator 共治

```
现象：
  · LLM 对相似 description 的多个 skill 随机选择，触发不稳定
  · 用户同一输入在不同 session 触发不同 skill
  · LLM 有时"太主动"（无关任务也触发 skill），有时"太保守"（明显匹配却不激活）

根因：
  当前架构完全依赖 LLM 语义理解做触发决策（"完全信任 LLM"）。
  LLM 是概率模型，同样输入不保证确定性输出。

应对策略：LLM + Orchestrator 共治
  ┌────────────────────────────────────────────────────────┐
  │  用户输入                                               │
  │       ↓                                                │
  │  [Orchestrator 层]（代码逻辑，确定性）                   │
  │  ① 是否需要 skill？                                     │
  │     · 关键词规则匹配（高精度）                            │
  │     · 或 Embedding 相似度阈值过滤（≥ 0.75 才进候选）     │
  │  ② 候选 skill 是谁？                                    │
  │     · Top-K 召回，传给 LLM                              │
  │       ↓                                                │
  │  [LLM 层]（语义理解，灵活性）                            │
  │  ③ 从候选集中最终决策激活哪个 skill                      │
  │     · 候选集已经很小（≤ 5），LLM 判断精度高              │
  │     · 或当候选集只有 1 个时，直接激活，跳过 LLM 判断      │
  └────────────────────────────────────────────────────────┘

实现成本估算（仅供参考）：
  · P1 简化版：关键词规则 Orchestrator（正则 / 关键词词典）
    成本低，适合 skill 数量少、场景清晰的早期阶段
  · P2 完整版：Embedding 检索 Orchestrator
    成本中，适合 skill 数量 > 10 且需要动态扩展的场景

注意：引入 Orchestrator 后，Skill Protocol 的"识别约定"仍保留，
     作为 Orchestrator 无结果时的 fallback（"兜底靠 LLM"）。
```

---

## 第二层：LangChain 实现映射

> 标注：✅ 框架内置 · 🔧 自行开发 · ⚡ 胶水代码
> 依据：LangChain 官方文档 2026-03（context7 检索）

### 2.1 框架无关概念 → LangChain API 对照

```
框架无关概念                          LangChain 实现                          归属
──────────────────────────────────────────────────────────────────────────────
Core Tools 注册（含 read_file）        @tool 装饰器（langchain_core.tools）     ✅ 框架内置
  read_file 等工具函数                  各 @tool 函数体                         🔧 自行开发

Skill Protocol + SkillSnapshot 注入   create_agent(system_prompt=...)           ⚡ 胶水代码
  SkillManager.build_snapshot()        扫描目录、解析 frontmatter、生成 prompt  🔧 自行开发

工具注册到 Agent                       create_agent(tools=[...])                ✅ 框架内置

read_file ToolMessage 进历史           LangGraph ToolMessage（自动）             ✅ 全自动
  read_file 读取 SKILL.md 内容         → 框架自动封装为 ToolMessage              ✅ 全自动

Skill ToolMessage 持久化               AsyncPostgresSaver（checkpointer）        ✅ 全自动

mutex_group 互斥检测                   当前仅元数据提示 + priority 排序          ⚠️ 软约束
                                        运行时硬性互斥检测（基于消息链）          ⬜ 目标态
```

### 2.2 read_file @tool（Skill 激活的核心工具）

```python
# Skill 激活机制：LLM 通过 read_file 读取 SKILL.md
# 与业界一致：OpenCode / OpenClaw 均使用 read_file 而非独立的 activate_skill tool
# 内容以 ToolMessage 形式自动进入 state["messages"] → checkpointer 持久化

from langchain_core.tools import tool  # ✅ langchain_core.tools

@tool
def read_file(path: str) -> str:
    """
    读取指定文件的完整内容。
    用于加载 Agent Skill 文件（SKILL.md）或其他文档资源。
    path: 文件绝对路径（支持 ~ 展开）
    """
    import os
    expanded = os.path.expanduser(path)
    with open(expanded, "r", encoding="utf-8") as f:
        return f.read()
    # 返回 str → 框架自动封装为 ToolMessage(content=<文件完整内容>)
    # 若读取的是 SKILL.md，内容包含 frontmatter + instructions + examples
    # ToolMessage 追加到 state["messages"] → checkpointer 自动持久化
```

### 2.3 存储层选择

```
短期记忆（Skill ToolMessage 持久化）：
  当前默认 → AsyncPostgresSaver.from_conn_string(DB_URI) ✅
  开发/测试备选 → InMemorySaver（langgraph.checkpoint.memory）✅

Skill 内容存储（SKILL.md 文件）：
  P0/P1 → 本地文件系统（skills/ 目录）                🔧
  P2    → PostgresStore，namespace=("skill_content", id）迁移路径：SkillManager 内部切换 🔧
```

### 2.5 自开发 vs 框架内置

```
✅ 框架内置，零额外代码：
  @tool 装饰器             read_file 等 Core Tools 注册
  ToolMessage 封装         read_file 返回值自动封装
  state["messages"] 追加   框架自动维护
  checkpointer 持久化      Skill ToolMessage 随历史自动保存

🔧 自行开发：
  SkillManager             扫描目录、解析 frontmatter、构建 Snapshot
  build_snapshot()         生成 SkillSnapshot（prompt + metadata 列表）
  Skill Protocol 文本       基础 4 条 + 手动指定约定写入 System Prompt 的自然语言文本
  read_file 函数体          文件读取逻辑（含 ~ 展开、大小校验）
  字符预算三级降级           完整 → 紧凑 → 二分截断
  mutex_group 硬互斥检测      基于消息链的同组冲突裁决（当前未实现）⬜
```

### 2.6 实现优先级

```
🔴 P0（当前阶段，已落地）：
  · read_file @tool（含 ~ 路径展开、路径校验、大小上限）✅
  · SkillManager.scan()：扫描 skills/，解析 frontmatter，过滤 status=active ✅
  · SkillManager.build_snapshot()：包含字符预算三级降级（完整 → 紧凑 → 截断）✅
  · disable_model_invocation 过滤 + priority 排序 ✅
  · Skill Protocol 文本（基础 4 条 + 手动指定约定）✅
  · Protocol + SkillSnapshot.prompt 注入 system_prompt（create_agent）✅
  · Core Tools 注册到 Agent（含 read_file）✅

🟡 P1（部分已落地，部分目标态）：
  · tools 依赖检查（skill 所需 core tool 不存在时给出告警）⬜
  · mutex_group 运行时硬互斥检测（基于消息链冲突裁决）⬜
  · 同组旧 skill 在压缩阶段优先清理 ⬜

⚪ P2：
  · SkillSnapshot 热更新（文件变更自动重建）
  · chain_trigger 链式触发
  · Multi-Agent 场景下的 Skill 设计调整（见 §1.9）
```
