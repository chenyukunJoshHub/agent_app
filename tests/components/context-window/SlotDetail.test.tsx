/**
 * SlotDetail Component Tests
 *
 * Tests the SlotDetail and SlotDetailList components for displaying
 * Slot content and token information.
 *
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SlotDetailList } from '@/components/SlotDetail';
import type { SlotDetail as SlotDetailType } from '@/types/context-window';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, onClick, ...props }: any) => (
      <div onClick={onClick} {...props}>
        {children}
      </div>
    ),
    button: ({ children, onClick, ...props }: any) => (
      <button onClick={onClick} {...props}>
        {children}
      </button>
    ),
  },
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  FileText: ({ className }: string) => <svg data-testid="file-text-icon" className={className} />,
  Token: ({ className }: string) => <svg data-testid="token-icon" className={className} />,
  ChevronDown: ({ className }: string) => <svg data-testid="chevron-down-icon" className={className} />,
  ChevronRight: ({ className }: string) => <svg data-testid="chevron-right-icon" className={className} />,
}));

// Import SlotDetail after mocks are set up
import { SlotDetail } from '@/components/SlotDetail';

describe('SlotDetail Component', () => {
  const mockSlot: SlotDetailType = {
    name: 'system',
    display_name: '系统提示词',
    content: 'This is a test system prompt content.',
    tokens: 42,
    enabled: true,
  };

  describe('Rendering', () => {
    it('renders slot display name and name', () => {
      render(<SlotDetail slot={mockSlot} />);

      expect(screen.getByText('系统提示词')).toBeInTheDocument();
      expect(screen.getByText('(system)')).toBeInTheDocument();
    });

    it('renders token count', () => {
      render(<SlotDetail slot={mockSlot} />);

      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('tokens')).toBeInTheDocument();
    });

    it('shows enabled badge when slot is enabled', () => {
      render(<SlotDetail slot={mockSlot} />);

      expect(screen.getByText('启用')).toBeInTheDocument();
    });

    it('shows disabled badge when slot is disabled', () => {
      const disabledSlot = { ...mockSlot, enabled: false };
      render(<SlotDetail slot={disabledSlot} />);

      expect(screen.getByText('未启用')).toBeInTheDocument();
    });

    it('renders content when expanded', () => {
      render(<SlotDetail slot={mockSlot} />);

      // Click to expand
      fireEvent.click(screen.getByText('系统提示词'));

      expect(screen.getByText('This is a test system prompt content.')).toBeInTheDocument();
    });

    it('truncates long content in preview mode', () => {
      const longContent = 'A'.repeat(300);
      const slotWithLongContent: SlotDetailType = {
        ...mockSlot,
        content: longContent,
      };

      const { container } = render(<SlotDetail slot={slotWithLongContent} preview />);

      // Should show truncated content with ...
      expect(container.textContent).toContain('...');
    });

    it('shows character count for long content when expanded', () => {
      const longContent = 'A'.repeat(300);
      const slotWithLongContent: SlotDetailType = {
        ...mockSlot,
        content: longContent,
      };

      render(<SlotDetail slot={slotWithLongContent} />);

      // Click to expand
      fireEvent.click(screen.getByText('系统提示词'));

      expect(screen.getByText('300 字符')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('shows empty state message when content is empty and expanded', () => {
      const emptySlot: SlotDetailType = {
        ...mockSlot,
        content: '',
      };

      render(<SlotDetail slot={emptySlot} />);

      // Click to expand
      fireEvent.click(screen.getByText('系统提示词'));

      expect(screen.getByText('暂无内容')).toBeInTheDocument();
    });

    it('shows disabled message for disabled slot with no content', () => {
      const disabledEmptySlot: SlotDetailType = {
        ...mockSlot,
        content: '',
        enabled: false,
      };

      render(<SlotDetail slot={disabledEmptySlot} />);

      // Click to expand
      fireEvent.click(screen.getByText('系统提示词'));

      expect(screen.getByText('此 Slot 未启用')).toBeInTheDocument();
    });
  });

  describe('Interaction', () => {
    it('toggles content visibility on click when not in preview mode', () => {
      render(<SlotDetail slot={mockSlot} />);

      // Initially collapsed - content not visible
      expect(screen.queryByText('This is a test system prompt content.')).not.toBeInTheDocument();

      // Click to expand
      fireEvent.click(screen.getByText('系统提示词'));

      // Content now visible
      expect(screen.getByText('This is a test system prompt content.')).toBeInTheDocument();

      // Click to collapse
      fireEvent.click(screen.getByText('系统提示词'));

      // Content hidden again
      expect(screen.queryByText('This is a test system prompt content.')).not.toBeInTheDocument();
    });

    it('does not toggle in preview mode', () => {
      const { container } = render(<SlotDetail slot={mockSlot} preview />);

      // Content should be visible in preview mode without clicking
      expect(container.textContent).toContain('This is a test system prompt content.');
    });
  });
});

describe('SlotDetailList Component', () => {
  const mockSlots: SlotDetailType[] = [
    {
      name: 'system',
      display_name: '系统提示词',
      content: 'System content',
      tokens: 100,
      enabled: true,
    },
    {
      name: 'active_skill',
      display_name: '活跃技能',
      content: 'Skill content',
      tokens: 50,
      enabled: true,
    },
    {
      name: 'few_shot',
      display_name: '动态示例',
      content: 'Few-shot content',
      tokens: 75,
      enabled: false,
    },
  ];

  it('renders all slots', () => {
    render(<SlotDetailList slots={mockSlots} />);

    expect(screen.getByText('系统提示词')).toBeInTheDocument();
    expect(screen.getByText('活跃技能')).toBeInTheDocument();
    expect(screen.getByText('动态示例')).toBeInTheDocument();
  });

  it('sorts slots by token count descending', () => {
    const { container } = render(<SlotDetailList slots={mockSlots} />);

    const allText = container.textContent || '';

    // System (100 tokens) should appear first
    const systemIndex = allText.indexOf('系统提示词');
    const fewShotIndex = allText.indexOf('动态示例');
    const activeSkillIndex = allText.indexOf('活跃技能');

    // Verify ordering by token count: system(100) > few_shot(75) > active_skill(50)
    expect(systemIndex).toBeLessThan(fewShotIndex);
    expect(fewShotIndex).toBeLessThan(activeSkillIndex);
  });

  it('passes preview prop to child SlotDetail components', () => {
    render(<SlotDetailList slots={mockSlots} preview />);

    // In preview mode, content should be visible without clicking
    expect(screen.getByText('System content')).toBeInTheDocument();
    expect(screen.getByText('Skill content')).toBeInTheDocument();
  });

  it('renders empty list when no slots provided', () => {
    const { container } = render(<SlotDetailList slots={[]} />);

    expect(container.textContent).toBe('');
  });
});
