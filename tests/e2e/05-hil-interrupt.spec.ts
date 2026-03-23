import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 5: HIL 人工介入流程（🟡 P1）
 *
 * 验收标准：
 * - 不可逆操作触发确认弹窗
 * - 弹窗显示操作详情
 * - 用户可以批准或拒绝
 * - 批准后继续执行，拒绝后停止
 */
// P1：需后端 HIL + send_email 等完整链路；P0 未实现时跳过整组
test.describe.skip('Human-in-the-Loop Interrupt', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('不可逆操作应该触发确认弹窗', async ({ page }) => {
    // 触发需要人工确认的操作（如发送邮件）
    const message = '请给 admin@example.com 发送邮件';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    // 验证确认弹窗出现
    const confirmModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(confirmModal).toBeVisible({ timeout: 10000 });
  });

  test('确认弹窗应该显示操作详情', async ({ page }) => {
    const message = '发送邮件给 user@test.com';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const confirmModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(confirmModal).toBeVisible({ timeout: 10000 });

    // 验证显示工具名称
    await expect(page.getByText(/send_email|email/i)).toBeVisible();

    // 验证显示目标邮箱
    await expect(page.getByText(/user@test.com/i)).toBeVisible();
  });

  test('用户批准后应该继续执行', async ({ page }) => {
    const message = '发送邮件给 test@example.com';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const confirmModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(confirmModal).toBeVisible({ timeout: 10000 });

    // 点击批准按钮
    const approveButton = page.getByRole('button', { name: /批准|确认|允许/i });
    await approveButton.click();

    // 验证弹窗关闭
    await expect(confirmModal).toBeHidden();

    // 验证显示执行结果
    await expect(page.getByText(/邮件已发送|发送成功/i)).toBeVisible({ timeout: 10000 });
  });

  test('用户拒绝后应该停止执行', async ({ page }) => {
    const message = '发送邮件给 reject@test.com';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const confirmModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(confirmModal).toBeVisible({ timeout: 10000 });

    // 点击拒绝按钮
    const rejectButton = page.getByRole('button', { name: /拒绝|取消/i });
    await rejectButton.click();

    // 验证弹窗关闭
    await expect(confirmModal).toBeHidden();

    // 验证显示取消消息
    await expect(page.getByText(/已取消|操作已停止/i)).toBeVisible();
  });

  test('应该显示风险等级标识', async ({ page }) => {
    const message = '删除所有数据';

    await page.getByPlaceholder(/描述任务/i).fill(message);
    await page.getByRole('button', { name: /发送/i }).click();

    const confirmModal = page.getByTestId(/hil-modal|confirm-modal/i);
    await expect(confirmModal).toBeVisible({ timeout: 10000 });

    // 验证风险标识显示
    const riskBadge = page.getByTestId(/risk-badge|risk-level/i);
    await expect(riskBadge).toBeVisible();
  });
});
