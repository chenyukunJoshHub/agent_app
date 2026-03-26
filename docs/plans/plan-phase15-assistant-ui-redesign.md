# Phase 15 — assistant-ui 重新设计

## 目标

集成 assistant-ui 组件库，升级 Multi-Tool AI Agent 的用户界面，提升视觉设计、交互体验和可访问性。

## 设计系统

- **风格**: Dark Mode (OLED) + 企业级配色
- **主色**: #3B82F6 (Blue 500)
- **强调色**: #F97316 (Orange 500)
- **背景**: #0A0A0F (近纯黑，OLED 优化)
- **字体**: Inter + JetBrains Mono
- **动画**: Spring 物理动画 (150-300ms)

## 架构文档参考

- [assistant-ui 官方文档](https://assistant-ui.com/)
- [UI/UX Pro Max 设计系统](../design/assistant-ui-redesign.md)
- [快速开始指南](../design/quick-start.md)

## 测试用例清单（TDD 先写）

### 依赖安装
- [ ] assistant-ui 包安装成功
- [ ] Radix UI 依赖安装成功
- [ ] Tailwind 插件配置正确

### 组件集成
- [ ] AssistantProvider 正确包装应用
- [ ] 现有 Zustand 状态正确集成
- [ ] SSE 流式响应正常工作

### 自定义组件
- [ ] AssistantRoot 渲染正确
- [ ] AssistantMessage 样式符合设计系统
- [ ] AssistantComposer 输入体验良好
- [ ] AssistantThread 消息列表正常
- [ ] AssistantThreadWelcome 欢迎界面美观

### 功能保留
- [ ] ReAct 链路可视化正常
- [ ] Context Window 面板正常
- [ ] Skills UI 正常
- [ ] HIL 确认对话框正常

### 样式验证
- [ ] 深色模式配色正确
- [ ] 文本对比度 ≥ 4.5:1
- [ ] 动画流畅（60fps）
- [ ] 响应式布局正常（375px - 1440px）

## 实现步骤（TDD 顺序）

### Step 1 — 依赖安装与配置
```bash
cd frontend
bun add @assistant-ui/react @assistant-ui/shadcn@latest
bun add @radix-ui/react-*相关包
```

### Step 2 — Tailwind 配置更新
- 合并 `tailwind.config.assistant-ui.js`
- 添加 assistant-ui 插件
- 更新 `globals.css` 导入主题变量

### Step 3 — 创建 AssistantProvider
- 集成现有 Zustand store
- 连接 SSE 流式响应
- 保留所有现有功能

### Step 4 — 自定义组件实现
- AssistantRoot.tsx
- AssistantMessage.tsx
- AssistantComposer.tsx
- AssistantThread.tsx
- AssistantThreadWelcome.tsx

### Step 5 — 页面重构
- 更新 `app/page.tsx`
- 保留侧边栏（ExecutionTracePanel + ContextWindowPanel）
- 测试完整功能流程

### Step 6 — 样式优化
- 应用完整设计系统
- 调整动画效果
- 验证可访问性

### Step 7 — E2E 测试更新
- 更新现有 E2E 测试用例
- 添加新 UI 交互测试
- 验证所有关键流程

## 完成标准

- [ ] 所有测试用例实现且通过
- [ ] assistant-ui 成功集成
- [ ] 现有功能完全保留
- [ ] 设计系统完整应用
- [ ] E2E 测试通过
- [ ] 无控制台错误或警告
- [ ] 用户体验显著提升

## 文件变更清单

### 新增文件
- `frontend/src/lib/assistant-ui-theme.ts`
- `frontend/src/app/globals.assistant-ui.css`
- `frontend/src/components/assistant/index.ts`
- `frontend/src/components/assistant/AssistantRoot.tsx`
- `frontend/src/components/assistant/AssistantMessage.tsx`
- `frontend/src/components/assistant/AssistantComposer.tsx`
- `frontend/src/components/assistant/AssistantThread.tsx`
- `frontend/src/components/assistant/AssistantThreadWelcome.tsx`
- `frontend/tailwind.config.assistant-ui.js`
- `docs/design/assistant-ui-redesign.md`
- `docs/design/quick-start.md`

### 修改文件
- `frontend/package.json` - 添加依赖
- `frontend/tailwind.config.js` - 合并配置
- `frontend/src/app/globals.css` - 导入主题
- `frontend/src/app/page.tsx` - 使用新组件
- `tests/e2e/*.spec.ts` - 更新选择器

## 遗留问题

- 附件支持（未来扩展）
- 命令建议（未来扩展）
- 分支管理（未来扩展）
- 移动端优化（后续迭代）
