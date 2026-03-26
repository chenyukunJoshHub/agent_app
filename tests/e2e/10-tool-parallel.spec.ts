import { test, expect } from '@playwright/test';

/**
 * Parallel smoke test:
 * - verify tool trace is visible
 * - verify at least 2 tool-call cards are produced for an explicitly parallel request
 */
test.describe('Tool Parallel Smoke', () => {
  test('shows parallel-intent tool calls in trace panel', async ({ page }) => {
    await page.goto('/');

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill("请在同一轮并行调用两个 web_search：分别查询'北京天气'和'上海天气'，再汇总。");
    await page.getByRole('button', { name: /发送/i }).click();

    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    await expect(page.getByTestId('execution-trace-panel')).toBeVisible({ timeout: 30000 });
    const toolCalls = page.getByTestId('tool-call-card');
    await expect(toolCalls).toHaveCount(2, { timeout: 30000 });
  });
});
