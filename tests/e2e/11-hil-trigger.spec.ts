import { test, expect, type Page } from '@playwright/test';

async function mockHilFlow(
  page: Page,
  options: {
    interruptId: string;
    to: string;
    approvedAnswer?: string;
    rejectedAnswer?: string;
    riskLevel?: 'high' | 'medium' | 'low';
    interruptMessage?: string;
  },
) {
  const {
    interruptId,
    to,
    approvedAnswer = '邮件已发送',
    rejectedAnswer = '操作已取消',
    riskLevel = 'high',
    interruptMessage = 'Agent 准备执行 send_email 操作，请确认',
  } = options;

  await page.route('**/chat/resume', async (route) => {
    const body = route.request().postDataJSON() as { approved?: boolean } | null;
    const approved = Boolean(body?.approved);

    const payload = [
      `event: hil_resolved\ndata: ${JSON.stringify({
        success: true,
        message: approved ? '已批准执行 send_email 操作' : '已取消 send_email 操作',
      })}\n\n`,
      `event: done\ndata: ${JSON.stringify({
        answer: approved ? approvedAnswer : rejectedAnswer,
      })}\n\n`,
    ].join('');

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: payload,
    });
  });

  await page.route('**/chat?**', async (route) => {
    const payload = `event: hil_interrupt\ndata: ${JSON.stringify({
      interrupt_id: interruptId,
      tool_name: 'send_email',
      tool_args: { to, subject: '测试主题', body: '测试正文' },
      risk_level: riskLevel,
      message: interruptMessage,
    })}\n\n`;

    await route.fulfill({
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: payload,
    });
  });
}

async function sendAndWaitHil(page: Page, message: string) {
  const input = page.getByPlaceholder(/描述任务/i);
  await input.fill(message);
  await page.getByRole('button', { name: /发送/i }).click();
  await expect(page.getByTestId('confirm-modal')).toBeVisible({ timeout: 15000 });
}

test.describe('HIL Trigger Mechanism', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('send_email 工具应该触发 HIL', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-send-email',
      to: 'admin@example.com',
    });

    await sendAndWaitHil(page, '给 admin@example.com 发送邮件');
  });

  test('HIL 弹窗应显示工具名称', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-tool-name',
      to: 'user@test.com',
    });

    await sendAndWaitHil(page, '发送邮件给 user@test.com');
    await expect(
      page.getByTestId('confirm-modal').getByText('send_email', { exact: true }),
    ).toBeVisible();
  });

  test('HIL 弹窗应显示工具参数', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-tool-args',
      to: 'test@example.com',
    });

    await sendAndWaitHil(page, '发送邮件给 test@example.com，主题是测试');
    await page.getByRole('button', { name: /展开/i }).click();
    await expect(page.getByTestId('confirm-modal').getByText(/test@example\.com/i)).toBeVisible();
  });

  test('用户批准后应继续执行', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-approve',
      to: 'approved@test.com',
      approvedAnswer: '邮件已发送',
    });

    await sendAndWaitHil(page, '发送邮件给 approved@test.com');

    const modal = page.getByTestId('confirm-modal');
    const approveButton = page.getByRole('button', { name: /确认执行|批准|允许|approve/i });
    const resumeRequest = page.waitForRequest('**/chat/resume');
    await approveButton.click();
    await resumeRequest;

    await expect(modal).toBeHidden({ timeout: 5000 });
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 15000 });
  });

  test('用户拒绝后应停止执行', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-reject',
      to: 'rejected@test.com',
      rejectedAnswer: '操作已取消',
    });

    await sendAndWaitHil(page, '发送邮件给 rejected@test.com');

    const rejectButton = page.getByRole('button', { name: /取消操作|拒绝|deny|reject/i });
    const resumeRequest = page.waitForRequest('**/chat/resume');
    await rejectButton.click();
    await resumeRequest;

    await expect(page.getByTestId('confirm-modal')).toBeHidden({ timeout: 5000 });
    await expect(page.getByText(/已取消|操作已停止|cancelled/i)).toBeVisible({ timeout: 10000 });
  });

  test('HIL 状态应正确追踪', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-track',
      to: 'track@test.com',
    });

    await sendAndWaitHil(page, '发送邮件给 track@test.com');
    await expect(page.getByTestId('execution-trace-panel')).toBeVisible();
    await expect(page.getByTestId('confirm-modal')).toBeVisible();
  });

  test('多个不可逆操作应依次触发 HIL', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-multi',
      to: 'user1@test.com',
    });

    await sendAndWaitHil(page, '给 user1@test.com 发送邮件，然后给 user2@test.com 也发送一封');
    await page.getByRole('button', { name: /确认执行|批准|允许/i }).click();
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 15000 });
  });

  test('HIL 弹窗应显示风险等级', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-risk',
      to: 'risk@test.com',
      riskLevel: 'high',
    });

    await sendAndWaitHil(page, '发送一封重要邮件');
    await expect(page.getByTestId('confirm-modal').getByText(/高风险/i)).toBeVisible();
  });

  test('HIL 弹窗应显示操作说明', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-description',
      to: 'desc@test.com',
      interruptMessage: 'Agent 准备执行 send_email 操作，请确认',
    });

    await sendAndWaitHil(page, '发送邮件给 desc@test.com');
    await expect(page.getByTestId('confirm-modal').getByText(/准备执行 send_email 操作/i)).toBeVisible();
  });

  test('HIL 触发时应暂停执行流', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-paused',
      to: 'pause@test.com',
    });

    await sendAndWaitHil(page, '发送邮件给 pause@test.com');

    const autoResume = await page
      .waitForRequest('**/chat/resume', { timeout: 1500 })
      .then(() => true)
      .catch(() => false);

    expect(autoResume).toBe(false);
  });

  test('HIL 恢复后应继续执行流', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-continue',
      to: 'continue@test.com',
      approvedAnswer: '邮件已发送',
    });

    await sendAndWaitHil(page, '发送邮件给 continue@test.com，然后搜索天气');
    const resumeRequest = page.waitForRequest('**/chat/resume');
    await page.getByRole('button', { name: /确认执行|批准|允许/i }).click();
    await resumeRequest;
    await expect(page.getByTestId('confirm-modal')).toBeHidden({ timeout: 5000 });
    await expect(page.getByPlaceholder(/描述任务/i)).toBeEnabled({ timeout: 15000 });
  });

  test('HIL 事件应正确记录在追踪历史中', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-history',
      to: 'history@test.com',
    });

    await sendAndWaitHil(page, '发送邮件给 history@test.com');
    await page.getByRole('button', { name: /确认执行|批准|允许/i }).click();
    await expect(page.getByTestId('execution-trace-panel')).toBeVisible();
  });

  test('HIL 弹窗应支持键盘操作', async ({ page }) => {
    await mockHilFlow(page, {
      interruptId: 'interrupt-keyboard',
      to: 'keyboard@test.com',
      rejectedAnswer: '操作已取消',
    });

    await sendAndWaitHil(page, '发送邮件给 keyboard@test.com');
    const cancelButton = page.getByRole('button', { name: /取消操作|拒绝|cancel/i });
    const resumeRequest = page.waitForRequest('**/chat/resume');
    await cancelButton.focus();
    await page.keyboard.press('Enter');
    await resumeRequest;

    await expect(page.getByTestId('confirm-modal')).toBeHidden({ timeout: 5000 });
    await expect(page.getByText(/已取消|操作已停止/i)).toBeVisible({ timeout: 10000 });
  });
});
