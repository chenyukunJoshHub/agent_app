/**
 * Slot Details E2E Tests
 *
 * Verifies Context Usage panel and Slot snapshot rendering.
 */

import { test, expect } from '@playwright/test';

test.describe('Slot Details E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /context/i }).click();
  });

  test('displays context usage panel', async ({ page }) => {
    await expect(page.getByTestId('context-window-panel')).toBeVisible();
    await expect(page.getByText('会话名称')).toBeVisible();
    await expect(page.getByText('context window Token 占比')).toBeVisible();
  });

  test('shows category usage rows', async ({ page }) => {
    await expect(page.getByTestId('token-bar')).toBeVisible();
    await expect(page.getByTestId('usage-rate')).toBeVisible();
  });

  test('shows complete slot snapshot section', async ({ page }) => {
    // 当前实现是 Slot 卡片区（有数据时显示卡片，空数据时显示占位文案）
    const slotSystemCard = page.getByTestId('slot-card-system');
    if ((await slotSystemCard.count()) > 0) {
      await expect(slotSystemCard.first()).toBeVisible();
    } else {
      await expect(page.getByText('暂无 Slot 数据')).toBeVisible();
    }
  });

  test('shows overall progress and statistics', async ({ page }) => {
    await expect(page.getByTestId('usage-rate')).toBeVisible();
    await expect(page.getByTestId('user-messages-count')).toBeVisible();
    await expect(page.getByTestId('assistant-messages-count')).toBeVisible();
    await expect(page.getByTestId('token-bar')).toBeVisible();
  });
});

test.describe('Slot Details API Integration', () => {
  test('API returns slot details', async ({ request }) => {
    const response = await request.get('/api/session/test-session/slots');
    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('session_id');
    expect(data).toHaveProperty('slots');
    expect(data).toHaveProperty('total_tokens');
    expect(data).toHaveProperty('timestamp');
  });

  test('API returns correct slot structure', async ({ request }) => {
    const response = await request.get('/api/session/test-session/slots');
    const data = await response.json();
    const slots = data.slots;

    expect(slots.length).toBeGreaterThan(0);
    const firstSlot = slots[0];
    expect(firstSlot).toHaveProperty('name');
    expect(firstSlot).toHaveProperty('display_name');
    expect(firstSlot).toHaveProperty('content');
    expect(firstSlot).toHaveProperty('tokens');
    expect(firstSlot).toHaveProperty('enabled');
  });

  test('API calculates total tokens correctly', async ({ request }) => {
    const response = await request.get('/api/session/test-session/slots');
    const data = await response.json();
    const expectedTotal = data.slots
      .filter((slot: { enabled: boolean }) => slot.enabled)
      .reduce((sum: number, slot: { tokens: number }) => sum + slot.tokens, 0);

    expect(data.total_tokens).toBe(expectedTotal);
  });
});
