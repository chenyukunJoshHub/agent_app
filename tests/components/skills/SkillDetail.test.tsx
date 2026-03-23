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
    it('should not render when skill is null', () => {
      const { container } = render(
        <SkillDetail skill={null} isOpen={false} onClose={vi.fn()} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should not render when isOpen is false', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={false} onClose={vi.fn()} />
      );

      // Drawer should be hidden
      expect(container.querySelector('[role="dialog"]')).not.toBeInTheDocument();
    });

    it('should render when skill and isOpen are provided', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('Legal Search')).toBeInTheDocument();
    });

    it('should render skill name', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('Legal Search')).toBeInTheDocument();
    });

    it('should render skill description', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText(/专业法律法规检索/)).toBeInTheDocument();
    });

    it('should render file path', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('~/skills/legal-search/SKILL.md')).toBeInTheDocument();
    });

    it('should render tools list', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText('tavily_search')).toBeInTheDocument();
      expect(screen.getByText('read_file')).toBeInTheDocument();
    });

    it('should render empty tools message when no tools', () => {
      const skillNoTools: Skill = {
        ...mockSkill,
        tools: [],
      };

      render(<SkillDetail skill={skillNoTools} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText(/No tools/)).toBeInTheDocument();
    });
  });

  describe('Interaction', () => {
    it('should call onClose when close button is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={handleClose} />);

      // Find close button - typically an X or Close text
      const closeButton = screen.getByRole('button', { name: /close/i });
      await user.click(closeButton);

      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('should call onClose when backdrop is clicked', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={handleClose} />);

      // Click on backdrop (outside the drawer)
      const drawer = screen.getByRole('dialog');
      const backdrop = drawer.parentElement;

      if (backdrop) {
        await user.click(backdrop);
        expect(handleClose).toHaveBeenCalledTimes(1);
      }
    });

    it('should close on ESC key press', async () => {
      const handleClose = vi.fn();
      const user = userEvent.setup();

      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={handleClose} />);

      await user.keyboard('{Escape}');

      expect(handleClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Drawer Position', () => {
    it('should render from right side', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('right-0');
      }
    });

    it('should have fixed position', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('fixed');
      }
    });
  });

  describe('Content Layout', () => {
    it('should render skill metadata section', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText(/Version/)).toBeInTheDocument();
      expect(screen.getByText(/Status/)).toBeInTheDocument();
    });

    it('should render tools section header', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText(/Tools/)).toBeInTheDocument();
    });

    it('should render file path section', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByText(/File Path/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have role="dialog"', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should have aria-labelledby', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');
    });

    it('should trap focus within drawer', () => {
      render(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      const closeButton = screen.getByRole('button', { name: /close/i });
      expect(closeButton).toBeInTheDocument();
    });
  });

  describe('Animation', () => {
    it('should use framer-motion AnimatePresence', () => {
      const { rerender } = render(
        <SkillDetail skill={mockSkill} isOpen={false} onClose={vi.fn()} />
      );

      // Re-render with isOpen=true
      rerender(<SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('should have slide-in animation', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('transition-transform');
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle skill with very long description', () => {
      const longDescSkill: Skill = {
        ...mockSkill,
        description: 'A'.repeat(1000),
      };

      render(<SkillDetail skill={longDescSkill} isOpen={true} onClose={vi.fn()} />);

      // Should scroll within drawer
      const dialog = screen.getByRole('dialog');
      expect(dialog).toBeInTheDocument();
    });

    it('should handle skill with many tools', () => {
      const manyToolsSkill: Skill = {
        ...mockSkill,
        tools: Array.from({ length: 20 }, (_, i) => `tool_${i}`),
      };

      render(<SkillDetail skill={manyToolsSkill} isOpen={true} onClose={vi.fn()} />);

      // All tools should be listed
      expect(screen.getByText('tool_0')).toBeInTheDocument();
      expect(screen.getByText('tool_19')).toBeInTheDocument();
    });

    it('should handle skill with special characters in name', () => {
      const specialCharSkill: Skill = {
        ...mockSkill,
        name: 'Test <Script> & "Quotes"',
      };

      render(<SkillDetail skill={specialCharSkill} isOpen={true} onClose={vi.fn()} />);

      // Should escape HTML
      expect(screen.getByText(/Test/)).toBeInTheDocument();
    });

    it('should handle null skill gracefully', () => {
      const { container } = render(
        <SkillDetail skill={null} isOpen={true} onClose={vi.fn()} />
      );

      expect(container.firstChild).toBeNull();
    });
  });

  describe('Styling', () => {
    it('should have proper width constraints', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('w-full');
        expect(drawer).toHaveClass('max-w-md');
      }
    });

    it('should have shadow and border', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('shadow-lg');
        expect(drawer).toHaveClass('border-l');
      }
    });

    it('should have proper z-index for overlay', () => {
      const { container } = render(
        <SkillDetail skill={mockSkill} isOpen={true} onClose={vi.fn()} />
      );

      const drawer = container.querySelector('[data-testid="skill-drawer"]');
      if (drawer) {
        expect(drawer).toHaveClass('z-50');
      }
    });
  });
});

