import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 1: 用户发送消息并收到回复
 *
 * 验收标准：
 * - 输入框可正常输入
 * - 发送按钮可点击
 * - 消息显示在聊天区域
 * - 收到 Agent 回复
 */
test.describe('Chat Basic', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('应该显示聊天界面', async ({ page }) => {
    // 验证页面标题
    await expect(page).toHaveTitle(/Multi-Tool AI Agent/);

    // 验证关键元素存在
    const chatInput = page.getByPlaceholder(/描述任务/i);
    await expect(chatInput).toBeVisible();

    const sendButton = page.getByRole('button', { name: /发送/i });
    await expect(sendButton).toBeVisible();
  });

  test('应该能发送消息并显示在聊天区', async ({ page }) => {
    const testMessage = '你好，请介绍一下你自己';

    // 输入消息
    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(testMessage);

    // 发送消息
    const sendButton = page.getByRole('button', { name: /发送/i });
    await sendButton.click();

    // 验证消息显示在聊天区
    const userMessage = page.getByText(testMessage);
    await expect(userMessage).toBeVisible();
  });

  test('发送消息后输入框应该清空', async ({ page }) => {
    const testMessage = '测试消息';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(testMessage);

    const sendButton = page.getByRole('button', { name: /发送/i });
    await sendButton.click();

    // 验证输入框已清空
    await expect(chatInput).toHaveValue('');
  });

  test('空消息不应该能发送', async ({ page }) => {
    const sendButton = page.getByRole('button', { name: /发送/i });

    // 空消息时发送按钮应该禁用
    await expect(sendButton).toBeDisabled();
  });
});
