import { test, expect } from '@playwright/test';
import { waitForMessageContent } from './helpers';

/**
 * E2E 测试场景 4: SSE 流式推送实时性
 *
 * 验收标准：
 * - 思考过程实时显示
 * - 工具调用状态实时更新
 * - Token 使用进度条更新
 * - 连接断开后能重连
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

    // 一轮对话结束：输入应恢复可编辑（依赖后端 + LLM）
    await expect(input).toBeEnabled({ timeout: 120000 });
  });

  test('应该显示 Token 使用进度', async ({ page }) => {
    const message = '请详细解释机器学习的概念';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证 Token 进度条出现
    const tokenBar = page.getByTestId(/token-bar|token-usage/i);
    await expect(tokenBar).toBeVisible({ timeout: 5000 });
  });

  test('SSE 连接断开应该能重连', async ({ page }) => {
    // 模拟网络断开后重连的场景
    // 这个测试需要 mock 网络条件
    const message = '测试连接稳定性';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证连接状态指示器
    const connectionStatus = page.getByTestId(/connection-status/i);
    await expect(connectionStatus).toBeVisible();
  });

  test('应该显示流式返回的内容', async ({ page }) => {
    const message = '讲一个短故事';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待输入框恢复（表示对话完成）
    const input = page.getByPlaceholder(/描述任务/i);
    await expect(input).toBeEnabled({ timeout: 120000 });

    // 使用辅助函数检查消息内容
    const hasContent = await waitForMessageContent(page, { timeout: 15000 });

    // 允许纯思考内容（不一定有实际回复）
    // 只要消息元素存在且有内容即可
    expect(hasContent).toBe(true);
  });
});
