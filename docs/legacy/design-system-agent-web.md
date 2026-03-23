# Agent Web · 通用前端设计系统（Pencil + 实现）

面向 **开发者向 AI Agent 控制台**（会话、对话、工具、可观测、Context），与 `frontend/pencil-new.pen` 对齐。  
本页融合了 **ui-ux-pro-max** 检索建议，并做了 **产品类型纠偏**（这是 **工具型 / 数据型工作台**，不是营销着陆页）。

---

## 1. 产品类型与应采用的范式

| 自动检索结果 | 是否采用 | 说明 |
|--------------|----------|------|
| Horizontal Scroll Journey / AI Dynamic Landing | **否** | 偏营销与故事线，与常驻三栏控制台冲突 |
| **Swiss Modernism 2.0** / **Minimal & Swiss** | **是** | 网格、单一强调色、高对比、少装饰 → 适合通用 Agent 控制台 |
| **Data-Dense Dashboard**（节制使用） | **部分** | 右栏 Tab2/可观测可略密；**中栏对话须留白**，避免全盘「密」 |
| Vibrant Block-based + 霓虹 | **否** | 易疲劳，与长时间编码场景不符 |

**一句话**：**理性网格 + 单一品牌强调色 + 对话区透气 + 侧栏可信息密度略高**。

---

## 2. 信息架构（与当前画板对应）

| 区域 | 角色（UX） | 设计要点 |
|------|------------|----------|
| **左栏** | 导航 / 会话 / 工具 | 固定宽、可扫读列表；当前项用 **边框或浅底** 区分，不只靠颜色 |
| **中栏** | **主工作区（Dominant region）** | 对话占视觉主导；**行宽 ~65–75 字符** 等效（约 `max-width` 36–42rem 或 Pencil 内固定文本宽） |
| **右栏** | 次要面板（Tab 切换） | 可观测 / Context / Skills；**进度条、时间轴** 等用 **形状+标签**，避免仅靠色相 |

---

## 3. 色彩（实现与 Pencil 变量）

**保持** 当前稿中 **锌灰中性 + 单一靛青强调**（`$accent`）——符合「单一强调色」的 Swiss 思路。  
若实现侧要对照 ui-ux-pro-max 的「code dark + run green」变体：**仅把「成功/完成」交给绿色**（如 `$stepDone`、成功 toast），**不要把整页改成霓虹绿主色**。

- **正文与背景对比**：亮/暗均需满足 **WCAG 4.5:1**（skill：不要用浅灰做正文）。
- **边框**：亮模式边框需 **可见**（`$border` 勿过浅）；暗模式同理。

Pencil 中：**颜色一律走 `variables` + `appearance`**，不要在示意组件上堆大量硬编码 hex（Tab 规范画板除外可逐步收束）。

---

## 4. 字体（可选升级）

当前稿：**Plus Jakarta Sans** — 合理、现代。  
ui-ux-pro-max 检索备选：**DM Sans（正文）+ Space Grotesk（标题/数字）** — 更「工具 / 终端」气质。

| 策略 | 做法 |
|------|------|
| **省改动** | 继续 Plus Jakarta，仅区分 `fontWeight` 与字号阶梯 |
| **对齐检索** | 标题/栏目标题用 Space Grotesk，正文与输入区用 DM Sans（实现时 `font-family`，Pencil 里改 `fontFamily` 字符串即可） |

**不要用 emoji 当图标**（skill 明确要求）；Pencil 里用 **Lucide 类图标字体** 或导出 SVG 块面（若工具支持）。

---

## 5. 间距与网格（8px 基准）

- **基准**：8px；常用 `8 / 12 / 16 / 24 / 32`。
- **中栏**：外留白建议 **16–28**（你已接近）；消息之间 **20–28**。
- **右栏**：卡片内 **8–12**；时间轴节点之间 **2–8** 视密度调整。

---

## 6. 组件层规则（对话 / 输入 / 按钮）

结合 **ui-ux-pro-max** 与 **Claude Code 类桌面端** 习惯：

1. **对话**  
   - 用户：**右侧**、**圆角块**、**浅底+细边框**，避免与主表面融在一起。  
   - 助手：**全宽阅读列**，小标题 **「Claude」或产品名**，**不要用厚重卡片框住全文**。  

2. **输入区**  
   - **大圆角容器** + 占位说明 + **底行快捷键提示**。  
   - **主发送**：圆形或方形 **≥44×44 等效点击区域**（skill：触摸目标）。  
   - **无障碍**：仅图标按钮时，实现里加 **`aria-label="发送消息"`**。  

3. **焦点与动效**  
   - 实现：`focus-visible` 环、`transition` **150–300ms**；尊重 `prefers-reduced-motion`。  
   - Pencil：静态稿可标注意图「Focus ring / 200ms」。  

---

## 7. 在 Pencil 里「怎么做」——操作步骤

### 7.1 先定「变量」再画组件

1. 打开 `frontend/pencil-new.pen`。  
2. 用 **Variables / 主题**：确保 **`appearance: light | dark`** 下 `$bg`、`$surface`、`$text`、`$textMuted`、`$border`、`$accent`、`$tabActive` 等齐全。  
3. **禁止**：在大量 frame 上写死 `#xxxxxx`（示意 Tab 画板可逐步改为 `$变量`）。

### 7.2 结构顺序（推荐）

1. **画板**：`Agent Web · Light` / `Dark` 各一帧，根上挂 `theme.appearance`。  
2. **body**：`horizontal` → `left` | `center` | `right` 三列。  
3. **center**：`vertical` → `chat_header` → `feed`（`height: fill_container`）→ `comp`（输入区 **fit_content** 高度）。  
4. **feed**：每条消息 **一行 `horizontal`**：`justifyContent: end`（用户）或 `start`（助手）。

### 7.3 文本

- 多行说明必须 **`textGrowth: fixed-width`** 且给 **`width`**（或 `fill_container` 在 flex 子级上）。  
- **行高**：正文约 **1.5–1.6**（skill）。

### 7.4 验证

- 导出或 **截图** Light/Dark 各一帧，检查：对比度、边框是否「消失」、右栏是否过挤。  
- 与实现同事交接时：附上 **`get_variables` 输出**（若用 Pencil MCP）或本文 **§3–§5**。

---

## 8. 预交付检查清单（摘自 ui-ux-pro-max）

- [ ] 无 emoji 充当图标  
- [ ] 可点击区域 ≥ 44px（或等价）  
- [ ] 亮/暗正文对比度 ≥ 4.5:1  
- [ ] 焦点状态在设计说明或实现中有交代  
- [ ] 主栏有 **明确主视觉区**（对话），右栏为从属  
- [ ] 响应式：在文档中约定断点（如 1024 以下右栏变抽屉——可在 `FINDINGS` 里写一句）

---

## 9. 和 `design-pencil-agent-ui.md` 的关系

- **结构、路径、Tab 示意**：见 [design-pencil-agent-ui.md](./design-pencil-agent-ui.md)。  
- **tokens、网格、无障碍、风格决策**：以 **本文为准**；改 Pencil 前先看 **§3–§7**。

---

## 10. 若要「一键复述」给另一个 AI / 同事

可复制下面这段：

> 做通用 Agent Web 前端：三栏工具台，Swiss/极简企业风，单一靛青强调色，锌灰中性底。中栏对话为主（用户右对齐浅底气泡、助手全宽扁平正文+小标题），底栏大圆角输入+快捷键提示+圆形发送。右栏 Tab：可观测时间轴、Context、Skills。全稿用 theme 变量控亮暗，8px 间距体系，禁止 emoji 图标，控件满足 44px 与 WCAG 对比度。文件：`frontend/pencil-new.pen`。
