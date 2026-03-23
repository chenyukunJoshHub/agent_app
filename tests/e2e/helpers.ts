/**
 * E2E 测试辅助函数
 */

import { Page, Locator, expect } from '@playwright/test';

/**
 * 发送聊天消息
 */
export async function sendMessage(page: Page, message: string) {
  const chatInput = page.getByPlaceholder(/描述任务/i);
  await chatInput.fill(message);

  const sendButton = page.getByRole('button', { name: /发送/i });
  await sendButton.click();
}

/**
 * 等待 Agent 回复
 */
export async function waitForResponse(
  page: Page,
  options: { timeout?: number } = {}
) {
  const { timeout = 15000 } = options;

  // 等待思考状态消失
  const thinkingIndicator = page.getByTestId(/thinking|loading/i).first();
  if (await thinkingIndicator.isVisible({ timeout: 5000 }).catch(() => false)) {
    await thinkingIndicator.waitFor({ state: 'hidden', timeout });
  }

  // 等待消息内容出现
  const messageContent = page.getByTestId(/message-content|ai-response/i).first();
  await expect(messageContent).toBeVisible({ timeout });
}

/**
 * 等待任意工具调用出现（不限定特定工具）
 */
export async function waitForAnyToolCall(
  page: Page,
  options: { timeout?: number } = {}
): Promise<Locator | null> {
  const { timeout = 15000 } = options;

  try {
    // 等待任意工具调用或结果出现
    const toolElement = page.locator(
      '[data-testid*="tool-call"], [data-testid*="tool-result"], [class*="tool-call"], [class*="tool-result"]'
    ).first();

    await expect(toolElement).toBeVisible({ timeout });
    return toolElement;
  } catch {
    return null;
  }
}

/**
 * 等待工具调用完成（指定工具名）
 */
export async function waitForToolCall(
  page: Page,
  toolName: string,
  options: { timeout?: number } = {}
) {
  const { timeout = 10000 } = options;

  const toolTrace = page.getByTestId(/tool-call-trace/i).filter({ hasText: toolName });
  await expect(toolTrace).toBeVisible({ timeout });

  // 等待工具结果出现
  const toolResult = page.getByTestId(/tool-result/i);
  await expect(toolResult).toBeVisible({ timeout });
}

/**
 * 等待消息内容出现（不限定具体内容）
 */
export async function waitForMessageContent(
  page: Page,
  options: { timeout?: number } = {}
): Promise<boolean> {
  const { timeout = 15000 } = options;

  try {
    // 等待输入框恢复启用状态（表示对话完成）
    const chatInput = page.getByPlaceholder(/描述任务/i);
    await expect(chatInput).toBeEnabled({ timeout });

    // 检查是否有 AI 消息内容
    const messages = page.locator('[data-testid*="message"], [role="assistant"], [class*="ai-message"]');
    const count = await messages.count();

    if (count > 0) {
      // 获取最后一条消息
      const lastMessage = messages.last();
      const text = await lastMessage.textContent();
      return (text?.trim().length || 0) > 0;
    }

    return false;
  } catch {
    return false;
  }
}

/**
 * 获取最新的 AI 消息
 */
export async function getLatestAIMessage(page: Page): Promise<string> {
  const messageContent = page.getByTestId(/message-content|ai-response/i).first();
  const text = await messageContent.textContent();
  return text || '';
}

/**
 * 验证 SSE 连接状态
 */
export async function assertConnectionStatus(
  page: Page,
  status: 'connected' | 'disconnected' | 'reconnecting'
) {
  const connectionStatus = page.getByTestId(/connection-status/i);

  const statusText = status === 'connected' ? '已连接' :
                     status === 'disconnected' ? '断开连接' :
                     '重连中';

  await expect(connectionStatus).toContainText(statusText);
}

/**
 * Mock SSE 响应（用于测试）
 */
export function mockSSEResponse(page: Page, events: Array<{ type: string; content?: string }>) {
  return page.route('**/chat', async (route) => {
    const stream = events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('');
    route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: stream,
    });
  });
}
