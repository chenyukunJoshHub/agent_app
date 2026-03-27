import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 2: 多轮对话历史保持
 *
 * 验收标准：
 * - 第一轮对话内容保留
 * - 第二轮对话能引用第一轮内容
 * - 聊天历史正确显示
 */
test.describe('Multi-Turn Conversation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('应该保持多轮对话历史', async ({ page }) => {
    const firstMessage = '我叫张三';
    const secondMessage = '请重复我的名字，不要解释，只输出名字。';

    // 第一轮对话
    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(firstMessage);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待首轮结束（输入框恢复可编辑；勿仅用「张三」匹配——用户消息里已含该字）
    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    // 第二轮对话
    await chatInput.fill(secondMessage);
    await page.getByRole('button', { name: /发送/i }).click();
    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    // 验证历史仍在，且助手回复里出现“张三”（限定助手消息区域，避免 strict mode 冲突）
    await expect(page.getByText(firstMessage, { exact: true })).toBeVisible();
    const assistantReplyWithName = page.locator('.prose').filter({ hasText: /张三/i }).first();
    await expect(assistantReplyWithName).toBeVisible({ timeout: 30000 });
  });

  test('聊天历史应该按时间顺序显示', async ({ page }) => {
    // 控制轮数和回复长度，降低本地模型长时间生成导致的随机超时
    const messages = [
      '第一条消息，请只回复：收到1',
      '第二条消息，请只回复：收到2',
    ];

    const input = page.getByPlaceholder(/描述任务/i);
    for (const message of messages) {
      await expect(input).toBeEnabled({ timeout: 180000 });
      await input.fill(message);
      await page.getByRole('button', { name: /发送/i }).click();
      await expect(page.getByText(message, { exact: true })).toBeVisible();
    }

    // 验证用户消息顺序（MessageList 中用户气泡使用 p.whitespace-pre-wrap）
    const userMessages = page.locator('p.whitespace-pre-wrap');
    await expect(userMessages).toHaveCount(messages.length);
    await expect(userMessages.nth(0)).toHaveText(messages[0]);
    await expect(userMessages.nth(1)).toHaveText(messages[1]);
  });
});
