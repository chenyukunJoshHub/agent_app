import { test, expect } from '@playwright/test';

/**
 * Serial smoke test:
 * - verify tool trace is visible
 * - verify at least 2 tool-call cards are produced for an explicitly serial request
 */
test.describe('Tool Serial Smoke', () => {
  test('shows serial tool calls in trace panel', async ({ page }) => {
    await page.goto('/');

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill("请严格分两步调用 web_search：先查询'北京天气'，再查询'上海天气'，最后总结。");
    await page.getByRole('button', { name: /发送/i }).click();

    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    await expect(page.getByTestId('execution-trace-panel')).toBeVisible({ timeout: 30000 });
    const toolCalls = page.getByTestId('tool-call-card');
    await expect(toolCalls).toHaveCount(2, { timeout: 30000 });
  });
});
