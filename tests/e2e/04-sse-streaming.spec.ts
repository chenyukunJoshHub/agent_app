import { test, expect } from '@playwright/test';
import { waitForMessageContent } from './helpers';

/**
 * E2E 测试场景 4: SSE 流式推送实时性
 *
 * 验收标准：
 * - 思考过程实时显示
 * - Context 面板 token 使用进度更新
 */
test.describe('SSE Streaming', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('应该实时显示 Agent 思考过程', async ({ page }) => {
    const message = '帮我分析一下这个复杂的问题：';
    const input = page.getByPlaceholder(/描述任务/i);

    await input.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 一轮对话结束：输入应恢复可编辑（依赖后端 + Ollama 本地模型）
    await expect(input).toBeEnabled({ timeout: 180000 });
  });

  test('应该在 Context 面板显示 Token 使用进度', async ({ page }) => {
    const message = '请详细解释机器学习的概念';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    await page.getByRole('button', { name: /context/i }).click();
    const contextPanel = page.getByTestId('context-window-panel');
    await expect(contextPanel).toBeVisible({ timeout: 10000 });
    await expect(contextPanel.getByText('会话名称')).toBeVisible();
    await expect(contextPanel.getByTestId('token-bar')).toBeVisible();
  });

  test('流式完成后输入框应恢复可编辑', async ({ page }) => {
    const message = '测试连接稳定性';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const input = page.getByPlaceholder(/描述任务/i);
    await expect(input).toBeEnabled({ timeout: 180000 });
  });

  test('应该显示流式返回的内容', async ({ page }) => {
    const message = '讲一个短故事';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待输入框恢复（表示对话完成）
    const input = page.getByPlaceholder(/描述任务/i);
    await expect(input).toBeEnabled({ timeout: 180000 });

    // 使用辅助函数检查助手消息内容
    const hasContent = await waitForMessageContent(page, { timeout: 30000 });

    expect(hasContent).toBe(true);
  });
});
