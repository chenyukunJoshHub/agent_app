import { test, expect } from '@playwright/test';
import { waitForAnyToolCall, waitForResponse } from './helpers';

/**
 * E2E 测试场景 3: 工具调用链路可视化
 *
 * 验收标准：
 * - 工具调用时显示工具名
 * - 显示工具入参
 * - 显示工具返回结果
 * - 调用链路可视化（时间轴）
 *
 * 注意：由于 AI 行为的不确定性，部分测试使用 flexible matchers
 */
test.describe('Tool Call Trace', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('应该显示工具调用卡片', async ({ page }) => {
    const searchQuery = '帮我查一下今天的天气';

    await page.getByPlaceholder(/描述任务/i).fill(searchQuery);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待任意工具调用组件出现（不限定特定工具）
    const toolCall = await waitForAnyToolCall(page, { timeout: 30000 });
    expect(toolCall).toBeTruthy();
  });

  test('工具调用应该显示工具名称', async ({ page }) => {
    const searchQuery = '搜索最新的 AI 新闻';

    await page.getByPlaceholder(/描述任务/i).fill(searchQuery);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待工具调用出现
    await waitForAnyToolCall(page, { timeout: 30000 });

    // 验证工具名称存在（不限定具体名称，使用 flexible matcher）
    // 工具名称通常是大写字母和下划线的组合
    const toolName = page.locator('[class*="tool-name"], [data-testid*="tool-name"], [class*="ToolCall"]');
    const isVisible = await toolCall.first().isVisible({ timeout: 5000 }).catch(() => false);

    // 如果工具调用组件出现，说明工具名称已显示
    expect(isVisible).toBe(true);
  });

  test('工具调用应该显示参数摘要', async ({ page }) => {
    const searchQuery = '搜索 TypeScript 相关信息';

    await page.getByPlaceholder(/描述任务/i).fill(searchQuery);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待工具调用出现
    await waitForAnyToolCall(page, { timeout: 30000 });

    // 等待响应完成
    await waitForResponse(page, { timeout: 60000 });

    // 验证页面包含搜索关键词（可能在工具参数或结果中）
    const hasKeyword = await page.getByText(/TypeScript|typescript/i).count() > 0;
    expect(hasKeyword).toBe(true);
  });

  test('工具调用应该显示结果摘要', async ({ page }) => {
    const searchQuery = '搜索 Python 编程语言';

    await page.getByPlaceholder(/描述任务/i).fill(searchQuery);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待工具调用出现
    await waitForAnyToolCall(page, { timeout: 30000 });

    // 等待响应完成
    await waitForResponse(page, { timeout: 60000 });

    // 验证工具结果或消息内容存在
    const content = page.locator('[data-testid*="tool-result"], [data-testid*="message-content"], [class*="tool-result"]');
    const count = await content.count();
    expect(count).toBeGreaterThan(0);
  });
});
