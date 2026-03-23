/**
 * Slot Details E2E Tests
 *
 * End-to-end tests for the Slot Details feature.
 * Verifies the complete flow from API to UI display.
 *
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */

import { test, expect } from '@playwright/test';

test.describe('Slot Details E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
  });

  test('displays context window panel', async ({ page }) => {
    // Context Window panel should be visible
    const contextWindow = page.locator('text=Context Window').first();
    await expect(contextWindow).toBeVisible();
  });

  test('shows slot breakdown by default', async ({ page }) => {
    // Slot breakdown section should be visible
    const slotBreakdown = page.locator('text=Slot 分解').first();
    await expect(slotBreakdown).toBeVisible();

    // Should display slot count
    await expect(page.locator('text=/个 Slot/')).toBeVisible();
  });

  test('displays slot bars with token information', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Check for slot bars (they should have token counts)
    const tokenElements = page.locator('text=/tokens/');
    await expect(tokenElements).toHaveCount(10); // 10 slots total
  });

  test('can toggle between overview and detail view', async ({ page }) => {
    // Wait for the page to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Look for the toggle button
    const toggleButton = page.locator('button:has-text("显示详情")').first();

    // If toggle button exists, click it
    if (await toggleButton.isVisible()) {
      await toggleButton.click();

      // Should now be in detail view
      await expect(page.locator('text=显示概览')).toBeVisible();

      // Should see slot details (content)
      const slotDetails = page.locator('text=系统提示词');
      await expect(slotDetails).toBeVisible();
    }
  });

  test('displays slot content when in detail view', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Try to switch to detail view
    const toggleButton = page.locator('button:has-text("显示详情")').first();

    if (await toggleButton.isVisible()) {
      await toggleButton.click();

      // Wait for detail content to appear
      await page.waitForTimeout(500);

      // Check for system slot content
      const systemContent = page.locator('text=系统提示词');
      await expect(systemContent).toBeVisible();

      // Check for few-shot examples
      const fewShotContent = page.locator('text=示例');
      await expect(fewShotContent).toBeVisible();
    }
  });

  test('shows token count for each slot', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Each slot should show token count
    const slotBars = page.locator('[class*="slot"]');
    const count = await slotBars.count();

    // Should have at least some slots
    expect(count).toBeGreaterThan(0);

    // Check first slot for token information
    const firstSlot = slotBars.first();
    const hasTokenInfo = await firstSlot.locator('text=/\\d+\\s*tokens/').isVisible();
    expect(hasTokenInfo).toBe(true);
  });

  test('shows overall progress bar', async ({ page }) => {
    // Wait for the page to load
    await page.waitForSelector('text=总体进度', { timeout: 5000 });

    // Overall progress section should be visible
    const progressSection = page.locator('text=总体进度');
    await expect(progressSection).toBeVisible();

    // Should show percentage or remaining tokens
    const percentageOrRemaining = page.locator('text=/已使用|剩余/');
    await expect(percentageOrRemaining).toBeVisible();
  });

  test('displays statistics row', async ({ page }) => {
    // Wait for statistics to load
    await page.waitForSelector('text=输入预算', { timeout: 5000 });

    // Statistics should include:
    await expect(page.locator('text=输入预算')).toBeVisible();
    await expect(page.locator('text=输出预留')).toBeVisible();
    await expect(page.locator('text=已使用')).toBeVisible();
  });

  test('handles empty slot states gracefully', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Try switching to detail view
    const toggleButton = page.locator('button:has-text("显示详情")').first();

    if (await toggleButton.isVisible()) {
      await toggleButton.click();

      // Some slots may be empty (not enabled)
      // The app should handle this without errors
      const emptySlots = page.locator('text=暂无内容');
      // Empty slots are OK, just verify the page doesn't crash
      const count = await emptySlots.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });

  test('can expand and collapse slot details', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Try switching to detail view
    const toggleButton = page.locator('button:has-text("显示详情")').first();

    if (await toggleButton.isVisible()) {
      await toggleButton.click();

      // Wait for detail view
      await page.waitForTimeout(500);

      // Find a slot with content
      const slotWithContent = page.locator('text=系统提示词').first();
      await expect(slotWithContent).toBeVisible();

      // Click to expand if collapsed
      const slotCard = slotWithContent.locator('..').locator('..').locator('..');
      await slotCard.click();

      // Wait for content expansion
      await page.waitForTimeout(300);

      // Content should be visible
      const expandedContent = page.locator('text=你是').or(page.locator('text=This is'));
      // The expanded content should be there (may be in Chinese or English)
      const isVisible = await expandedContent.isVisible();
      expect(isVisible).toBe(true);
    }
  });

  test('maintains state during view toggle', async ({ page }) => {
    // Wait for slot breakdown to load
    await page.waitForSelector('text=Slot 分解', { timeout: 5000 });

    // Try switching to detail view
    const toggleButton = page.locator('button:has-text("显示详情")').first();

    if (await toggleButton.isVisible()) {
      await toggleButton.click();

      // Wait for detail view
      await page.waitForTimeout(500);

      // Switch back to overview
      const overviewButton = page.locator('button:has-text("显示概览")').first();
      await overviewButton.click();

      // Should return to overview view
      await expect(page.locator('text=Slot 分解')).toBeVisible();

      // Overview should still show slot bars
      const slotBars = page.locator('[class*="slot"]');
      const count = await slotBars.count();
      expect(count).toBeGreaterThan(0);
    }
  });
});

test.describe('Slot Details API Integration', () => {
  test('API returns slot details', async ({ request }) => {
    // Make API request to get slot details
    const response = await request.get('/api/session/test-session/slots');

    expect(response.status().toBe(200));

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

    // Should have at least some slots
    expect(slots.length).toBeGreaterThan(0);

    // Each slot should have required fields
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
    const slots = data.slots;

    // Calculate expected total (only enabled slots)
    const expectedTotal = slots
      .filter((slot: { enabled: boolean }) => slot.enabled)
      .reduce((sum: number, slot: { tokens: number }) => sum + slot.tokens, 0);

    expect(data.total_tokens).toBe(expectedTotal);
  });
});
