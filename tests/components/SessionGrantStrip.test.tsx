import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { SessionGrantStrip } from '@/components/SessionGrantStrip';

describe('SessionGrantStrip', () => {
  it('应展示 grant 列表并支持撤销', async () => {
    const user = userEvent.setup();
    const onRevoke = vi.fn();

    render(<SessionGrantStrip grants={['send_email']} onRevoke={onRevoke} />);

    expect(screen.getByText('本会话已放行')).toBeInTheDocument();
    expect(screen.getByText('send_email')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '撤销 send_email 会话放行' }));
    expect(onRevoke).toHaveBeenCalledWith('send_email');
  });
});
