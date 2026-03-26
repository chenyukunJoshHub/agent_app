import { defineConfig, devices } from '@playwright/test';
import path from 'path';

/**
 * Playwright E2E 测试配置
 *
 * 关键场景：
 * 1. 用户发送消息并收到回复
 * 2. 多轮对话历史保持
 * 3. 工具调用链路可视化
 * 4. SSE 流式推送实时性
 * 5. HIL 人工介入流程（P1）
 *
 * @see CLAUDE.md 规则二：强制 TDD — E2E 测试强制要求
 * - headless: false（必须有头模式）
 * - slowMo: 300（人眼可跟随）
 * - SSE 相关断言超时 ≥ 15000ms
 * - 失败时保留截图 + 录像
 */
export default defineConfig({
  // 测试目录（指向项目根目录下的 tests/e2e/）
  testDir: path.join(__dirname, '../tests/e2e'),

  // 测试文件匹配模式
  testMatch: '**/*.spec.ts',

  // 超时设置（本地 Ollama 模型响应较慢，延长到 3 分钟）
  timeout: 180 * 1000,
  expect: {
    timeout: 30 * 1000,
  },

  // 失败时重试（本地也重试一次，应对 AI 行为不确定性）
  retries: process.env.CI ? 2 : 1,

  // 并行工作进程数（E2E 与 dev server 同机时单 worker 更稳）
  workers: process.env.CI ? 1 : 1,

  // 报告器
  reporter: [
    ['html', { outputFolder: path.join(__dirname, '../tests/playwright-report') }],
    ['list'],
    ['json', { outputFile: path.join(__dirname, '../tests/test-results/test-results.json') }],
  ],

  // 全局设置
  use: {
    // 基础 URL（可用 PLAYWRIGHT_BASE_URL 覆盖，例如端口冲突时）
    // 与下方 webServer 中 Next 端口一致（避免与本地已占用的 3000 冲突）
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:3010',

    // ✅ 必须有头模式（人眼可跟随）
    headless: false,

    // ✅ 人眼可跟随的延迟（通过 launchOptions 设置）
    launchOptions: {
      slowMo: 300,
    },

    // 追踪（失败时保留）
    trace: 'retain-on-failure',

    // 截图
    screenshot: 'only-on-failure',

    // 视频
    video: 'retain-on-failure',

    // 导航超时（含冷启动 Next）
    navigationTimeout: 60 * 1000,

    // 操作超时（等待 Ollama 响应）
    actionTimeout: 30 * 1000,

    // 视口大小（规范要求）
    viewport: { width: 1440, height: 900 },
  },

  // 项目配置
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },
    // 移动端测试
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
    },
  ],

  // 自动启动后端和前端服务
  // 后端: FastAPI + LangGraph
  // 前端: Next.js dev server
  ...(process.env.SKIP_WEB_SERVER
    ? {}
    : {
        webServer: [
          {
            name: 'backend',
            command:
              'cd ../backend && python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
            url: 'http://127.0.0.1:8000/health',
            timeout: 120 * 1000,
            reuseExistingServer: true,
          },
          {
            name: 'frontend',
            command: 'npx next dev -H 127.0.0.1 -p 3010',
            url: 'http://127.0.0.1:3010',
            reuseExistingServer: true,
            timeout: 180 * 1000,
          },
        ],
      }),
});
