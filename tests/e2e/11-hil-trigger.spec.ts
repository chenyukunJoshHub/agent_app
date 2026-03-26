import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景：HIL（Human-in-the-Loop）触发机制
 *
 * 验收标准：
 * - 不可逆操作自动触发 HIL
 * - HIL 弹窗显示完整信息
 * - 用户批准后继续执行
 * - 用户拒绝后停止执行
 * - HIL 状态正确追踪
 * - 多个不可逆操作依次触发 HIL
 */
test.describe('HIL Trigger Mechanism', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('send_email 工具应该触发 HIL', async ({ page }) => {
    const message = '给 admin@example.com 发送邮件';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证 HIL 弹窗出现
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });
  });

  test('HIL 弹窗应显示工具名称', async ({ page }) => {
    const message = '发送邮件给 user@test.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证显示工具名称
    await expect(hilModal.getByText(/send_email|email|邮件/i)).toBeVisible();
  });

  test('HIL 弹窗应显示工具参数', async ({ page }) => {
    const message = '发送邮件给 test@example.com，主题是测试';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证显示邮箱地址
    await expect(hilModal.getByText(/test@example.com/i)).toBeVisible();
  });

  test('用户批准后应继续执行', async ({ page }) => {
    const message = '发送邮件给 approved@test.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 点击批准按钮
    const approveButton = page.getByRole('button', { name: /批准|确认|允许|approve/i });
    await approveButton.click();

    // 验证弹窗关闭
    await expect(hilModal).toBeHidden({ timeout: 5000 });

    // 等待工具执行完成
    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    // 验证显示执行结果
    const resultText = await page.getByText(/已发送|发送成功|sent/i).textContent({ timeout: 30000 });
    expect(resultText).toBeTruthy();
  });

  test('用户拒绝后应停止执行', async ({ page }) => {
    const message = '发送邮件给 rejected@test.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 点击拒绝按钮
    const rejectButton = page.getByRole('button', { name: /拒绝|取消|deny|reject/i });
    await rejectButton.click();

    // 验证弹窗关闭
    await expect(hilModal).toBeHidden({ timeout: 5000 });

    // 等待处理完成
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 180000 });

    // 验证显示取消消息
    await expect(page.getByText(/已取消|操作已停止|cancelled/i)).toBeVisible();
  });

  test('HIL 状态应正确追踪', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待 HIL 触发
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证追踪面板显示 HIL 状态
    const tracePanel = page.getByTestId('execution-trace-panel');
    await expect(tracePanel).toBeVisible();

    // 验证有 HIL 事件标识
    const hilEvent = tracePanel.locator('[data-testid*="hil"], [data-testid*="interrupt"]');
    await expect(hilEvent.first()).toBeVisible();
  });

  test('多个不可逆操作应依次触发 HIL', async ({ page }) => {
    // 发送需要多个 HIL 确认的任务
    const message = '给 user1@test.com 发送邮件，然后给 user2@test.com 也发送一封';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证第一个 HIL 触发
    const firstHilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(firstHilModal).toBeVisible({ timeout: 15000 });

    // 批准第一个
    const approveButton = page.getByRole('button', { name: /批准|确认|允许/i });
    await approveButton.click();

    // 等待第二个 HIL 触发（如果有）
    await page.waitForTimeout(3000);

    const secondHilVisible = await firstHilModal.isVisible().catch(() => false);

    // 如果第二个 HIL 也触发，验证它
    if (secondHilVisible) {
      await expect(firstHilModal.getByText(/user2/i)).toBeVisible();
      await approveButton.click();
    }

    // 等待完成
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 180000 });
  });

  test('HIL 弹窗应显示风险等级', async ({ page }) => {
    const message = '发送一封重要邮件';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证风险标识显示
    const riskBadge = hilModal.locator('[data-testid*="risk"], [class*="risk"]');
    await expect(riskBadge.first()).toBeVisible();
  });

  test('HIL 弹窗应显示操作说明', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证显示操作说明或提示文字
    const description = hilModal.locator('[data-testid*="description"], [data-testid*="message"]');
    await expect(description.first()).toBeVisible();
  });

  test('HIL 触发时应暂停执行流', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待 HIL 触发
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 验证输入框被禁用（暂停状态）
    await expect(chatInput).toBeDisabled();

    // 验证没有新的工具调用开始
    const toolCallsBefore = await page.getByTestId('tool-call-card').count();
    await page.waitForTimeout(2000);
    const toolCallsAfter = await page.getByTestId('tool-call-card').count();

    expect(toolCallsAfter).toBe(toolCallsBefore);
  });

  test('HIL 恢复后应继续执行流', async ({ page }) => {
    const message = '发送邮件给 test@example.com，然后搜索天气';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待 HIL 触发
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 批准
    const approveButton = page.getByRole('button', { name: /批准|确认|允许/i });
    await approveButton.click();

    // 等待输入框恢复可编辑（恢复执行）
    await expect(chatInput).toBeEnabled({ timeout: 180000 });

    // 验证有多个工具调用（邮件 + 天气搜索）
    const toolCalls = page.getByTestId('tool-call-card');
    await expect(toolCalls).toHaveCount(2, { timeout: 30000 });
  });

  test('HIL 事件应正确记录在追踪历史中', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待 HIL 触发
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 批准
    const approveButton = page.getByRole('button', { name: /批准|确认|允许/i });
    await approveButton.click();

    // 等待完成
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 180000 });

    // 验证追踪历史包含 HIL 事件
    const tracePanel = page.getByTestId('execution-trace-panel');
    const hilEvents = tracePanel.locator('[data-testid*="hil"], [data-testid*="interrupt"]');

    // 应该至少有一个 HIL 事件
    await expect(hilEvents.first()).toBeVisible();
  });

  test('HIL 弹窗应支持键盘操作', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    const chatInput = page.getByPlaceholder(/描述任务/i);
    await chatInput.fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待 HIL 触发
    const hilModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(hilModal).toBeVisible({ timeout: 15000 });

    // 尝试使用键盘操作（ESC 取消，Enter 确认）
    await page.keyboard.press('Escape');

    // 验证弹窗关闭
    await expect(hilModal).toBeHidden({ timeout: 5000 });

    // 验证显示取消消息
    await expect(page.getByText(/已取消|操作已停止/i)).toBeVisible();
  });
});
