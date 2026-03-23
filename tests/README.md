# 测试目录结构

根据 `CLAUDE.md` 规范，测试文件按照以下结构组织：

```
tests/
├── e2e/                    # E2E 测试（Playwright）
│   ├── 01-chat-basic.spec.ts
│   ├── 02-multi-turn.spec.ts
│   ├── 03-tool-trace.spec.ts
│   ├── 04-sse-streaming.spec.ts
│   ├── 05-hil-interrupt.spec.ts
│   └── helpers.ts
├── components/             # 组件测试（Vitest）
│   ├── components/
│   │   └── ChatInput.test.tsx
│   ├── store/
│   │   └── use-session.test.ts
│   └── lib/
│       └── (其他工具测试)
├── test/                   # 测试配置文件
│   └── setup.ts           # Vitest setup
├── playwright.config.ts    # Playwright 配置
├── vitest.config.ts        # Vitest 配置
└── playwright-report/      # Playwright 报告输出
```

## 运行测试

从项目根目录或 `frontend/` 目录运行：

```bash
# 组件测试（Vitest）
cd frontend
npm test                    # 运行所有组件测试
npm run test:ui            # UI 模式
npm run test:coverage      # 覆盖率报告

# E2E 测试（Playwright）
cd frontend
npm run test:e2e           # 运行所有 E2E 测试
npm run test:e2e:ui        # UI 模式
npm run test:e2e:debug     # 调试模式
npm run test:e2e:report    # 查看报告
```

## 测试规范

### E2E 测试（Playwright）

- **有头模式**：`headless: false`
- **慢动作**：`slowMo: 300`
- **SSE 超时**：≥ 15000ms
- **失败保留**：截图 + 录像

### 组件测试（Vitest）

- **覆盖率目标**：60%
- **测试环境**：jsdom
- **全局变量**：describe, test, expect

## 配置文件

- `playwright.config.ts` - Playwright E2E 测试配置
- `vitest.config.ts` - Vitest 单元测试配置
- `test/setup.ts` - Vitest 测试前置设置

## 注意事项

1. **别名解析**：`@/*` 别名解析到 `frontend/src/`
2. **WebServer**：Playwright 自动启动 Next.js 在 3010 端口
3. **后端依赖**：E2E 测试需要后端服务运行在 8000 端口
