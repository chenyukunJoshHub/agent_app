/**
 * SkillDetail Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SkillDetail } from '@/components/skills/SkillDetail';
import type { Skill } from '@/types/skills';

const mockSkill: Skill = {
  name: 'Legal Search',
  description: '专业法律法规检索与引用规范，适用合同合规类任务。',
  file_path: '~/skills/legal-search/SKILL.md',
  tools: ['tavily_search', 'read_file'],
};

describe('SkillDetail', () => {
  describe('Rendering', () => {
    it('should not render when isOpen is false', () => {
      render(<SkillDetail skill={mockSkill} isOpen={false} onClose={vi.fn()} />);
      expect(screen.queryByTestId('skill-detail-drawer')).not.toBeInTheDocument();
      expect(screen.queryByTestId('skill-detail-backdrop')).not.toBeInTheDocument();
    });

    it('should render drawer when isOpen is true even if skill is null', () => {
      render(<SkillDetail skill={null} isOpen={true} onClose={vi.fn()} />);
      expect(screen.getByTestId('skill-detail-drawer')).toBeInTheDocument();
      expect(screen.getByTestId('skill-detail-backdrop')).toBeInTheDocument();
    });

    it('should render skill metadata and content sections', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);
      expect(screen.getByText('Legal Search')).toBeInTheDocument();
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getByText('File Path')).toBeInTheDocument();
      expect(screen.getByText('Full Content')).toBeInTheDocument();
      expect(screen.getByText('Required Tools (2)')).toBeInTheDocument();
    });

    it('should render description and file path', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);
      expect(screen.getAllByText(/专业法律法规检索/).length).toBeGreaterThan(0);
      expect(screen.getByText('~/skills/legal-search/SKILL.md')).toBeInTheDocument();
    });

    it('should render tools list when tools exist', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);
      expect(screen.getByText('tavily_search')).toBeInTheDocument();
      expect(screen.getByText('read_file')).toBeInTheDocument();
    });

    it('should hide tools section when tools are empty', () => {
      render(
        <SkillDetail
          skill={{ ...mockSkill, tools: [] }}
          isOpen={true}
          onClose={vi.fn()}
        />
      );
      expect(screen.queryByText(/Required Tools/)).not.toBeInTheDocument();
      expect(screen.getByText(/\*\*Tools:\*\* None/)).toBeInTheDocument();
    });
  });

  describe('Interaction', () => {
    it('should call onClose when header close button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={onClose} />);

      await user.click(screen.getByLabelText('Close'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('should call onClose when footer close button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={onClose} />);

      const closeButtons = screen.getAllByRole('button', { name: /^Close$/ });
      await user.click(closeButtons[closeButtons.length - 1]);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('should call onClose when backdrop is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={onClose} />);

      await user.click(screen.getByTestId('skill-detail-backdrop'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('should call onClose on Escape key', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={onClose} />);

      await user.keyboard('{Escape}');
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Layout and Styling', () => {
    it('should render right-side fixed drawer with expected classes', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);
      const drawer = screen.getByTestId('skill-detail-drawer');
      expect(drawer).toHaveClass('fixed');
      expect(drawer).toHaveClass('right-0');
      expect(drawer).toHaveClass('w-full');
      expect(drawer).toHaveClass('max-w-lg');
      expect(drawer).toHaveClass('shadow-xl');
      expect(drawer).toHaveClass('z-50');
    });

    it('should render backdrop with overlay classes', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);
      const backdrop = screen.getByTestId('skill-detail-backdrop');
      expect(backdrop).toHaveClass('fixed');
      expect(backdrop).toHaveClass('inset-0');
      expect(backdrop).toHaveClass('bg-black/50');
      expect(backdrop).toHaveClass('z-40');
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long description', () => {
      render(
        <SkillDetail
          skill={{ ...mockSkill, description: 'A'.repeat(1000) }}
          isOpen={true}
          onClose={vi.fn()}
        />
      );
      expect(screen.getByText('Description')).toBeInTheDocument();
      expect(screen.getAllByText(/A{50,}/).length).toBeGreaterThan(0);
    });

    it('should handle many tools', () => {
      const manyTools = Array.from({ length: 20 }, (_, i) => `tool_${i}`);
      render(
        <SkillDetail
          skill={{ ...mockSkill, tools: manyTools }}
          isOpen={true}
          onClose={vi.fn()}
        />
      );
      expect(screen.getByText('tool_0')).toBeInTheDocument();
      expect(screen.getByText('tool_19')).toBeInTheDocument();
    });

    it('should handle special characters in skill name', () => {
      render(
        <SkillDetail
          skill={{ ...mockSkill, name: 'Test <Script> & "Quotes"' }}
          isOpen={true}
          onClose={vi.fn()}
        />
      );
      expect(screen.getByText('Test <Script> & "Quotes"')).toBeInTheDocument();
    });
  });
});
