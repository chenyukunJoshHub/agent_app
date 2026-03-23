# Agent 网页 UI · Pencil 设计稿说明

**设计系统（tokens、网格、无障碍、在 Pencil 里怎么画）**：见 [design-system-agent-web.md](./design-system-agent-web.md)（含 **ui-ux-pro-max** 检索结论与纠偏）。

## 文件与保存

- **设计稿路径（目标）**：`frontend/pencil-new.pen`（扩展名 `.pen`，非 `.peng`）。
- **如何保存**：在 **Pencil** 应用里打开该文件后，使用 **文件 → 保存** 或 **⌘S**（macOS）。第一次若磁盘上还没有此文件，请用 **另存为** 选到本仓库：`agent_app/pencil-new.pen`。
- **说明**：通过 Cursor 的 Pencil 插件/MCP 修改的是编辑器中的画布；**是否写入磁盘取决于 Pencil 是否对该路径执行了保存**。若你在文件夹里看不到 `.pen`，请在 Pencil 里对该文档执行一次「另存为」到上述路径。

### 为什么「改完又没了」？

常见原因：

1. **两套编辑源不同步**：Cursor 直接改的是仓库里的 `frontend/pencil-new.pen`；Pencil 里若打开的是**未保存的旧缓冲**或**另存过的副本**，重新保存或重开会用旧内容**盖掉**磁盘上的新内容。  
2. **未保存到同一路径**：另存为到了别的目录/文件名，你以为在看同一个稿，实际不是。  
3. **撤销 / 版本回退**：在 Pencil 或编辑器里撤销、或从 Git/备份还原文件，会丢掉之后的修改。

**建议**：以 **Cursor 里打开的 `frontend/pencil-new.pen` 与 Pencil 指向的绝对路径一致** 为准；大改后在 Pencil 里 **先关闭文档再重新打开** 该路径，确认与磁盘一致后再继续画。

## 画板结构（自上而下）

1. **Agent Web · Light**（`appearance: light`）  
   - **左栏**：活动会话列表；底部 **支持的工具**（`read_file`、`tavily_search`、`contract_status`、`send_email`、`python_repl` 等）。  
   - **中栏**：对话区 **整体参考 Claude Code 桌面端**（`NB9Qe` / `DamH6`）：顶栏为会话 id + 模式芯片；**用户**为右侧 **圆角灰底气泡**（无「用户」小标题）；**助手**为全宽 **扁平正文** + 小标题「Claude」；**输入区**为大圆角卡片、主占位文案 + 底行快捷键提示 + **圆形发送（↑）**。  
   - **右栏**：三个 Tab — **可观测**（默认选中）、**Context**、**Skills**；默认可观测区为 **整轮 Turn 步骤时间线**（`before_agent` → … → `after_agent`）。其中 **步骤 5（工具调用）**：文案说明语义；**UI 示意**为 **串行 = 纵向链（工具 A ↓ B ↓ C）**、**并行 = 横向多卡 + ∥ 分隔（同时间段多路并排）**——实现时可换成泳道、分组框或同起点时间条；亮/暗稿中均有 `viz_serial` / `viz_parallel` 小框。

2. **Agent Web · Dark**（`appearance: dark`）  
   - 与亮色版结构相同，根节点 `theme: { appearance: "dark" }`，用于核对 **设计变量** 在暗色下的对比度与层次。  
   - **右栏 Tab1「可观测」**：**亮色 / 暗色结构一致**，均为 **时间轴**——亮色容器 `7qmmC`、暗色 `1wsLH`：左侧竖线 + 圆点 + 右侧步骤卡片；步骤 4 琥珀强调「当前焦点」，步骤 7 `$tabActive` 底区分第二次 LLM，步骤 8 空心点 + 弱化文案；步骤 5 卡片内区分 **串行 / 并行** 两种工具执行说明。

3. **Tab 面板规范**（主画板下方）  
   - **Tab2 Context**（`DDswp`，自上而下）：**Context** 标题 + 总述 → **架构要点** → **当前会话 · 24,576**（Slot ①–⑩ 分行示意 tok + 合计；预算指**本条**拼进单次请求的上限，会话可跨多轮）→ **总窗 200k**（⛶ Free / ⛝ Autocompact）→ **最底部「输入预算可视化」**（`cu9fd0174bf7`）：**一条进度条**表示 *当前会话本条组装已用 / 24,576*，并说明与 **200k 总窗** 不同；**不再**使用 glm 式 10×10 小格。  
   - **Tab3 Skills**：全部 Skill 卡片列表（元数据 + 依赖 tools），供与右栏第三 Tab 对照实现。

## 视觉方向（现代 SaaS）

- **字体**：正文与 UI 统一 **Plus Jakarta Sans**（替代系统感较强的 Inter），层次靠字重与字号区分。  
- **色板**：**锌灰中性** 画布（`$bg` / `$surface` / `$border`）+ **靛青强调**（`$accent` `#4F46E5` 亮 / `#A5B4FC` 暗），避免「默认蓝」观感。  
- **形态**：气泡与卡片 **圆角略加大**（约 16px）、顶栏略增高与内边距，整体更接近当前主流 AI / 控制台产品（Linear、Vercel 一类）的克制层次。

## 亮 / 暗主题（实现要点）

设计稿中为颜色类变量配置了 **`appearance: light | dark`** 两套取值（如 `$bg`、`$surface`、`$text`、`$accent` 等）。前端实现时建议：

- 根节点或 `<html>` 使用 `data-theme="light|dark"` 或 class 切换；  
- CSS / Tailwind 与设计变量对齐，保证与 Pencil 中两套 appearance 一致。

## 与架构文档的对应关系

| UI 区域 | 文档概念 |
|--------|-----------|
| 左栏会话 + 检查点 | Memory 短期记忆 · `thread` / session |
| 左栏底部工具 | Multi-Tool · Tool 模块（原子工具） |
| 中栏对话 | 用户界面层 · 消息与流式输出 |
| 右栏 Tab1 可观测 | Middleware 时序 + SSE · 整 turn |
| 右栏 Tab2 | Prompt+Context · Working Memory + Token Budget |
| 右栏 Tab3 | agent skills · Registry + `read_file` 激活 |
| **Tab2 Context** 底部 **输入预算可视化** | **当前会话本条组装已用 / 24,576** 进度条 + 与 **200k 总窗** 区分的说明；见 [Memory-v5-节点-Prompt-Token对照.md](Memory-v5-节点-Prompt-Token对照.md) |
