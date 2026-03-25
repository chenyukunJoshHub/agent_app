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
    await expect(page.getByText('Context Usage')).toBeVisible();
  });

  test('shows category usage rows', async ({ page }) => {
    await expect(page.getByTestId('context-row-free-space')).toBeVisible();
    await expect(page.getByTestId('context-row-autocompact-buffer')).toBeVisible();
  });

  test('shows complete slot snapshot section', async ({ page }) => {
    await expect(page.getByText('完整 Slot 快照')).toBeVisible();
    await expect(page.getByTestId('slot-breakdown')).toBeVisible();
  });

  test('shows overall progress and statistics', async ({ page }) => {
    await expect(page.getByTestId('overall-progress-fill')).toBeVisible();
    await expect(page.getByTestId('context-row-autocompact-buffer')).toBeVisible();
    await expect(page.getByTestId('stat-reserved-buffer')).toBeVisible();
    await expect(page.getByTestId('stat-free-space')).toBeVisible();
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
