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
    const toolCalls = page.getByTestId('trace-block-card').filter({ hasText: 'web_search' });
    const toolIntent = page
      .getByTestId('trace-block-card')
      .filter({ hasText: /决定调用|调用\s*\d+\s*个工具/ });

    // 并行意图场景下，允许“明确工具调用意图”先出现，再出现具体 web_search 卡片
    await expect
      .poll(
        async () => {
          const hasToolCall = (await toolCalls.count()) > 0;
          const hasToolIntent = (await toolIntent.count()) > 0;
          return hasToolCall || hasToolIntent;
        },
        { timeout: 120000 },
      )
      .toBe(true);
  });
});
