import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ThemeToggleButton } from '@/components/assistant/ThemeToggleButton';

describe('ThemeToggleButton', () => {
  it('shows dark mode affordance when current mode is light', () => {
    render(<ThemeToggleButton theme="light" onToggle={vi.fn()} />);

    expect(screen.getByRole('button', { name: '切换为暗色主题' })).toBeInTheDocument();
    expect(screen.getByText('暗色')).toBeInTheDocument();
  });

  it('shows light mode affordance when current mode is dark', () => {
    render(<ThemeToggleButton theme="dark" onToggle={vi.fn()} />);

    expect(screen.getByRole('button', { name: '切换为亮色主题' })).toBeInTheDocument();
    expect(screen.getByText('亮色')).toBeInTheDocument();
  });

  it('calls onToggle when clicked', async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(<ThemeToggleButton theme="light" onToggle={onToggle} />);

    await user.click(screen.getByRole('button', { name: '切换为暗色主题' }));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
