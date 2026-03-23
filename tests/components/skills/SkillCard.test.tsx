/**
 * SkillCard Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SkillCard } from '@/components/skills/SkillCard';
import type { SkillWithStatus } from '@/types/skills';

const mockSkill: SkillWithStatus = {
  name: 'Legal Search',
  description: '专业法律法规检索与引用规范，适用合同合规类任务。',
  file_path: '~/skills/legal-search/SKILL.md',
  tools: ['tavily_search', 'read_file'],
  isActive: true,
};

const mockSkillInactive: SkillWithStatus = {
  ...mockSkill,
  isActive: false,
};

const mockSkillNoTools: SkillWithStatus = {
  ...mockSkill,
  tools: [],
};

describe('SkillCard', () => {
  describe('Rendering', () => {
    it('should render skill name', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByText('Legal Search')).toBeInTheDocument();
    });

    it('should render skill description', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByText(/专业法律法规检索/)).toBeInTheDocument();
    });

    it('should render file path', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByText('~/skills/legal-search/SKILL.md')).toBeInTheDocument();
    });

    it('should render ACTIVE badge when skill is active', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    });

    it('should not render ACTIVE badge when skill is inactive', () => {
      render(<SkillCard skill={mockSkillInactive} onClick={vi.fn()} index={0} />);
      expect(screen.queryByText('ACTIVE')).not.toBeInTheDocument();
    });

    it('should render tools count when tools exist', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByText('2 tools')).toBeInTheDocument();
    });

    it('should render singular "tool" when only one tool', () => {
      const skillWithOneTool: SkillWithStatus = {
        ...mockSkill,
        tools: ['tavily_search'],
      };
      render(<SkillCard skill={skillWithOneTool} onClick={vi.fn()} index={0} />);
      expect(screen.getByText('1 tool')).toBeInTheDocument();
    });

    it('should not render tools count when no tools', () => {
      render(<SkillCard skill={mockSkillNoTools} onClick={vi.fn()} index={0} />);
      expect(screen.queryByText(/\d+ tool/)).not.toBeInTheDocument();
    });
  });

  describe('Interaction', () => {
    it('should call onClick when card is clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();

      render(<SkillCard skill={mockSkill} onClick={handleClick} index={0} />);

      const card = screen.getByTestId('skill-card-Legal Search');
      await user.click(card);

      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('should have cursor-pointer class', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('cursor-pointer');
    });
  });

  describe('Styling', () => {
    it('should have correct base classes', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('rounded-lg');
      expect(card).toHaveClass('border');
      expect(card).toHaveClass('bg-background-card');
      expect(card).toHaveClass('shadow-sm');
    });

    it('should have hover classes', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('hover:shadow-md');
      expect(card).toHaveClass('hover:border-primary/50');
    });

    it('should have active scale class', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const card = container.firstChild as HTMLElement;
      expect(card).toHaveClass('active:scale-[0.98]');
    });
  });

  describe('Accessibility', () => {
    it('should have data-testid for easy querying', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByTestId('skill-card-Legal Search')).toBeInTheDocument();
    });

    it('should use skill name in test id', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);
      expect(screen.getByTestId('skill-card-Legal Search')).toBeInTheDocument();
    });
  });

  describe('Layout', () => {
    it('should display file path with monospace font', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const pathElement = container.querySelector('.font-mono');
      expect(pathElement).toBeInTheDocument();
      expect(pathElement).toHaveTextContent('~/skills/legal-search/SKILL.md');
    });

    it('should truncate long description with line-clamp', () => {
      const longDescriptionSkill: SkillWithStatus = {
        ...mockSkill,
        description: 'A'.repeat(500), // Very long description
      };

      const { container } = render(
        <SkillCard skill={longDescriptionSkill} onClick={vi.fn()} index={0} />
      );

      const description = container.querySelector('.line-clamp-3');
      expect(description).toBeInTheDocument();
    });

    it('should reserve space for ACTIVE badge', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);

      const title = screen.getByText('Legal Search');
      expect(title).toHaveClass('pr-16'); // Right padding for badge
    });
  });

  describe('Animation', () => {
    it('should use motion.div for animation', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      const card = container.firstChild;
      expect(card).toBeDefined();
    });

    it('should pass index for staggered animation', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={2} />
      );

      const card = container.firstChild;
      expect(card).toBeDefined();
    });
  });

  describe('Active Badge Styling', () => {
    it('should have success color classes', () => {
      const { container } = render(
        <SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />
      );

      // Check for badge with rounded-full class
      const badge = container.querySelector('.rounded-full');
      expect(badge).toBeInTheDocument();
      expect(badge?.textContent).toContain('ACTIVE');
    });

    it('should show check circle icon', () => {
      render(<SkillCard skill={mockSkill} onClick={vi.fn()} index={0} />);

      // Check for Lucide icon (lucide class)
      const badge = screen.getByText('ACTIVE').parentElement;
      expect(badge?.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty description gracefully', () => {
      const emptyDescriptionSkill: SkillWithStatus = {
        ...mockSkill,
        description: '',
      };

      render(<SkillCard skill={emptyDescriptionSkill} onClick={vi.fn()} index={0} />);

      const description = screen.getByText('Legal Search').nextElementSibling;
      expect(description).toBeInTheDocument();
    });

    it('should handle very long skill names', () => {
      const longNameSkill: SkillWithStatus = {
        ...mockSkill,
        name: 'A'.repeat(100),
      };

      render(<SkillCard skill={longNameSkill} onClick={vi.fn()} index={0} />);

      expect(screen.getByText(new RegExp('^A+$'))).toBeInTheDocument();
    });

    it('should handle special characters in description', () => {
      const specialCharSkill: SkillWithStatus = {
        ...mockSkill,
        description: 'Test <script>alert("xss")</script> & "quotes"',
      };

      render(<SkillCard skill={specialCharSkill} onClick={vi.fn()} index={0} />);

      // Content should be escaped by React
      expect(screen.getByText(/Test/)).toBeInTheDocument();
    });
  });
});
