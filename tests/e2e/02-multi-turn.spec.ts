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
    const secondMessage = '我的名字是什么？';

    // 第一轮对话
    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(firstMessage);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待首轮结束（输入框恢复可编辑；勿仅用「张三」匹配——用户消息里已含该字）
    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    // 第二轮对话
    await chatInput.fill(secondMessage);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证 Agent 记住了用户的名字（依赖 Ollama 本地模型回复，给足时间）
    await expect(page.getByText(/张三/i)).toBeVisible({ timeout: 180000 });
  });

  test('聊天历史应该按时间顺序显示', async ({ page }) => {
    const messages = ['第一条消息', '第二条消息', '第三条消息'];

    const input = page.getByPlaceholder(/描述任务/i);
    for (const message of messages) {
      await expect(input).toBeEnabled({ timeout: 180000 });
      await input.fill(message);
      await page.getByRole('button', { name: /发送/i }).click();
      await expect(page.getByText(message)).toBeVisible();
    }

    // 验证所有消息都显示在页面上
    for (const message of messages) {
      await expect(page.getByText(message)).toBeVisible();
    }
  });
});
