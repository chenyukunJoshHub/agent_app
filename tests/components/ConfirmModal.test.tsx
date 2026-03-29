import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ConfirmModal } from '@/components/ConfirmModal';

const interrupt = {
  interrupt_id: 'interrupt-123',
  tool_name: 'send_email',
  tool_args: { to: 'user@example.com', subject: 'Hello' },
  risk_level: 'high' as const,
  message: 'Agent 准备执行 send_email 操作，请确认',
  action_requests: [{ name: 'send_email', args: { to: 'user@example.com', subject: 'Hello' } }],
};

describe('ConfirmModal', () => {
  it('确认时可携带本会话总是允许选项', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();

    render(
      <ConfirmModal
        isOpen={true}
        interrupt={interrupt}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />
    );

    await user.click(screen.getByLabelText('本会话内不再询问此工具'));
    await user.click(screen.getByRole('button', { name: /确认执行/i }));

    expect(onConfirm).toHaveBeenCalledWith('interrupt-123', true);
  });

  it('取消时只回传 interrupt id', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();

    render(
      <ConfirmModal
        isOpen={true}
        interrupt={interrupt}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    await user.click(screen.getByRole('button', { name: /取消操作/i }));

    expect(onCancel).toHaveBeenCalledWith('interrupt-123');
  });

  it('多 action 审批时应展示所有操作并禁用会话放行', () => {
    render(
      <ConfirmModal
        isOpen={true}
        interrupt={{
          ...interrupt,
          tool_name: 'fetch_url',
          tool_args: { url: 'https://example.com' },
          message: 'Agent 准备执行 2 个需审批操作，请确认',
          action_requests: [
            { name: 'fetch_url', args: { url: 'https://example.com' } },
            { name: 'send_email', args: { to: 'user@example.com', subject: 'Hello' } },
          ],
        }}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText('需审批操作（2）')).toBeInTheDocument();
    expect(screen.getByText('fetch_url')).toBeInTheDocument();
    expect(screen.getByText('send_email')).toBeInTheDocument();
    expect(screen.queryByLabelText('本会话内不再询问此工具')).not.toBeInTheDocument();
  });
});
