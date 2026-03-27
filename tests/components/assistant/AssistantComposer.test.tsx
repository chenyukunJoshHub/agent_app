import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AssistantComposer } from '@/components/assistant/AssistantComposer';

let mockText = '';
let mockIsRunning = false;

const mockRuntime = {
  setText: vi.fn(),
  send: vi.fn(),
};

const mockThreadRuntime = {
  cancelRun: vi.fn(),
};

const mockSkillCommand = {
  isOpen: false,
  filtered: [] as Array<{ name: string; description: string }>,
  onInputChange: vi.fn(),
  onSelect: vi.fn((skill: { name: string }) => `/${skill.name} `),
  onClose: vi.fn(),
};

vi.mock('@assistant-ui/react', () => ({
  ComposerPrimitive: {
    Root: ({
      children,
      className,
    }: {
      children: React.ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
    Send: ({
      children,
      className,
    }: {
      children: React.ReactNode;
      className?: string;
    }) => <div className={className}>{children}</div>,
  },
  useComposerRuntime: () => mockRuntime,
  useComposer: (selector: (state: { text: string }) => unknown) => selector({ text: mockText }),
  useThread: (selector: (state: { isRunning: boolean }) => unknown) =>
    selector({ isRunning: mockIsRunning }),
  useThreadRuntime: () => mockThreadRuntime,
}));

vi.mock('@/hooks/useSkillCommand', () => ({
  useSkillCommand: () => mockSkillCommand,
}));

describe('AssistantComposer', () => {
  beforeEach(() => {
    mockText = '';
    mockIsRunning = false;
    mockRuntime.setText.mockReset();
    mockRuntime.send.mockReset();
    mockThreadRuntime.cancelRun.mockReset();
    mockSkillCommand.onInputChange.mockReset();
    mockSkillCommand.onSelect.mockReset();
    mockSkillCommand.onClose.mockReset();
  });

  it('hides operation bar and keeps only send button', () => {
    render(<AssistantComposer />);

    expect(screen.getByRole('button', { name: '发送' })).toBeInTheDocument();
    expect(screen.queryByText('Tools')).toBeNull();
    expect(screen.queryByText('Flash')).toBeNull();
    expect(screen.queryByRole('button', { name: '添加附件' })).toBeNull();
    expect(screen.queryByRole('button', { name: '工具' })).toBeNull();
    expect(screen.queryByRole('button', { name: '模型选择' })).toBeNull();
  });

  it('does not show mic icon when input is empty', () => {
    render(<AssistantComposer />);

    const sendButton = screen.getByRole('button', { name: '发送' });
    expect(sendButton.querySelector('.lucide-mic')).toBeNull();
    expect(sendButton.querySelector('.lucide-arrow-up')).toBeInTheDocument();
  });
});
