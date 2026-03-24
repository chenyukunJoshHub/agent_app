import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 3: 执行链路可视化
 *
 * 验收标准：
 * - 右侧默认展示链路面板
 * - 对话后出现链路事件
 * - 工具调用应出现在追踪面板中
 * - 可切换到 Context 面板
 */
test.describe('Execution Trace', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('默认展示链路面板', async ({ page }) => {
    await expect(page.getByTestId('execution-trace-panel')).toBeVisible();
    await expect(page.getByText('执行链路明细')).toBeVisible();
  });

  test('发送消息后应出现链路事件', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('请总结一下这段需求');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    await expect(page.getByText('事件流水')).toBeVisible();
    const eventRows = page.locator('text=stream');
    await expect(eventRows.first()).toBeVisible({ timeout: 30000 });
  });

  test('工具调用应出现在追踪面板中', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('搜索今日天气');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    await expect(page.getByTestId('tool-call-card')).toBeVisible({ timeout: 30000 });
    await expect(page.getByTestId('tool-call-card')).toContainText('web_search', { timeout: 30000 });
  });

  test('可切换到 Context 面板', async ({ page }) => {
    await page.getByRole('button', { name: /context/i }).click();
    await expect(page.getByTestId('context-window-panel')).toBeVisible();
    await expect(page.getByText('Context Usage')).toBeVisible();
  });
});
