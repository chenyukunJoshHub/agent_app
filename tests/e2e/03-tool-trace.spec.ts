import { test, expect } from '@playwright/test';

test.describe('Execution Trace', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('默认展示链路面板', async ({ page }) => {
    await expect(page.getByTestId('execution-trace-panel')).toBeVisible();
    await expect(page.getByText('执行链路')).toBeVisible();
  });

  test('发送消息后应出现链路步骤', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('请总结一下这段需求');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    // After redesign, we should see TraceBlockCards instead of raw stage labels
    await expect(page.getByTestId('trace-block-card').first()).toBeVisible({ timeout: 120000 });
  });

  test('工具调用应出现在追踪面板中', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('搜索今日天气');
    await page.getByRole('button', { name: /发送/i }).click();
    const textarea = page.getByPlaceholder(/描述任务/i);
    await expect(textarea).toBeEnabled({ timeout: 180000 });
    // Tool call blocks should be visible
    await expect(page.getByTestId('trace-block-card').first()).toBeVisible({ timeout: 120000 });
    await expect(
      page.getByTestId('trace-block-card').filter({ hasText: 'web_search' }).first(),
    ).toBeVisible({ timeout: 120000 });
  });

  test('可切换到 Context 面板', async ({ page }) => {
    await page.getByRole('button', { name: /context/i }).click();
    await expect(page.getByTestId('context-window-panel')).toBeVisible();
    await expect(page.getByText('会话名称')).toBeVisible();
  });

  test('可切换简洁/详细模式', async ({ page }) => {
    const modeBtn = page.getByRole('button', { name: /详细|简洁/i });
    await expect(modeBtn).toBeVisible();
    await expect(modeBtn).toContainText('详细');
    // 切换到详细模式后，按钮文案应变为“简洁”
    await modeBtn.click();
    await expect(modeBtn).toContainText('简洁');
    // 再切回简洁模式后，按钮文案应恢复“详细”
    await modeBtn.click();
    await expect(modeBtn).toContainText('详细');
  });
});
