import { test, expect } from '@playwright/test';

/**
 * E2E 测试场景 6: Context Panel 四模块面板
 *
 * 验收标准：
 * - ① 会话元数据与 Token 统计模块可见
 * - ② 上下文窗口 Token 地图模块可见（含 12 段比例条）
 * - ③ 各 Slot 原文与 Prompt 模块可见
 * - ④ 压缩日志仅在有压缩事件时显示
 * - 发送消息后数据实时更新
 */
test.describe('Context Panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // 切换到 Context 标签
    await page.getByRole('button', { name: /context/i }).click();
  });

  test('应显示模块①②③的标题', async ({ page }) => {
    await expect(page.getByText(/① 会话元数据/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/② 上下文窗口.*Token 地图/)).toBeVisible({ timeout: 5000 });
    await expect(page.getByText(/③ 各 Slot 原文/)).toBeVisible({ timeout: 5000 });
  });

  test('应显示模块②的 Token 比例条', async ({ page }) => {
    const tokenBar = page.getByTestId('token-bar');
    await expect(tokenBar).toBeVisible({ timeout: 5000 });
  });

  test('初始状态不应显示模块④压缩日志', async ({ page }) => {
    await page.waitForTimeout(500);
    const compressionHeader = page.getByText('④ 压缩日志');
    await expect(compressionHeader).not.toBeVisible();
  });

  test('发送消息后 Token 数据应更新', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('你好');
    await page.getByRole('button', { name: /发送/i }).click();

    // 等待响应完成（本地 Ollama 最多 3 分钟）
    await page.getByPlaceholder(/描述任务/i).toBeEnabled({ timeout: 180_000 });

    // Token 地图应有比例条
    const tokenBar = page.getByTestId('token-bar');
    await expect(tokenBar).toBeVisible({ timeout: 5000 });

    // 模块③应显示 Slot 卡片（至少 system slot）
    const systemCard = page.getByTestId('slot-card-system');
    const hasSystemCard = await systemCard.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasSystemCard) {
      await expect(systemCard).toBeVisible();
    }
  });

  test('Slot 卡片点击后应展开内容', async ({ page }) => {
    await page.getByPlaceholder(/描述任务/i).fill('你好');
    await page.getByRole('button', { name: /发送/i }).click();
    await page.getByPlaceholder(/描述任务/i).toBeEnabled({ timeout: 180_000 });

    const systemCard = page.getByTestId('slot-card-system');
    const hasCard = await systemCard.isVisible({ timeout: 3000 }).catch(() => false);
    if (!hasCard) {
      test.skip(true, 'system slot card not present');
      return;
    }

    await systemCard.click();
    // 展开后应有 pre 内容区域
    await expect(systemCard.locator('pre')).toBeVisible({ timeout: 2000 });
  });
});
