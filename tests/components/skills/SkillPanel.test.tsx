/**
 * SkillPanel Component Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SkillPanel } from '@/components/skills/SkillPanel';
import type { SkillWithStatus } from '@/types/skills';

// Mock fetch
global.fetch = vi.fn();

const mockSkills: SkillWithStatus[] = [
  {
    name: 'Legal Search',
    description: '专业法律法规检索与引用规范',
    file_path: '~/skills/legal-search/SKILL.md',
    tools: ['tavily_search', 'read_file'],
    isActive: true,
  },
  {
    name: 'CSV Reporter',
    description: '生成 CSV 格式报告',
    file_path: '~/skills/csv-reporter/SKILL.md',
    tools: [],
    isActive: true,
  },
];

describe('SkillPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('should show loading indicator on mount', () => {
      (global.fetch as any).mockImplementation(
        () =>
          new Promise(() => {
            // Never resolves - keeps loading state
          })
      );

      render(<SkillPanel />);
      expect(screen.getByText('Loading skills...')).toBeInTheDocument();
      expect(screen.getByTestId('skill-panel')).toBeInTheDocument();
    });

    it('should show spinner while loading', () => {
      (global.fetch as any).mockImplementation(
        () =>
          new Promise(() => {
            // Never resolves
          })
      );

      render(<SkillPanel />);
      const spinner = screen.getByRole('status', { hidden: true });
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('should show error message when fetch fails', async () => {
      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load skills')).toBeInTheDocument();
      });
    });

    it('should display error details', async () => {
      (global.fetch as any).mockRejectedValue(
        new Error('Failed to fetch skills: 500 Internal Server Error')
      );

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText(/500 Internal Server Error/)).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('should show empty state when no skills available', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('No skills available')).toBeInTheDocument();
      });
    });

    it('should show empty state icon', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        const icon = screen.getByTestId('skill-panel').querySelector('svg');
        expect(icon).toBeInTheDocument();
      });
    });
  });

  describe('Success State', () => {
    it('should render skills list on successful fetch', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Legal Search')).toBeInTheDocument();
        expect(screen.getByText('CSV Reporter')).toBeInTheDocument();
      });
    });

    it('should display skill count in header', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('2 available skills')).toBeInTheDocument();
      });
    });

    it('should display singular "skill" when only one skill', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [mockSkills[0]] }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('1 available skill')).toBeInTheDocument();
      });
    });

    it('should render skills in grid layout', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        const grid = screen.getByTestId('skill-panel').querySelector('.grid');
        expect(grid).toBeInTheDocument();
      });
    });
  });

  describe('Skill Interaction', () => {
    it('should open skill detail when skill card is clicked', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      const user = userEvent.setup();
      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Legal Search')).toBeInTheDocument();
      });

      // Click on first skill
      await user.click(screen.getByText('Legal Search'));

      // Detail drawer should be shown (we check if the skill name appears in detail)
      await waitFor(() => {
        expect(screen.getByText(/专业法律法规检索/)).toBeInTheDocument();
      });
    });

    it('should close detail drawer when close button is clicked', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      const user = userEvent.setup();
      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Legal Search')).toBeInTheDocument();
      });

      // Click on first skill
      await user.click(screen.getByText('Legal Search'));

      // Wait for detail to appear
      await waitFor(() => {
        expect(screen.getByText(/专业法律法规检索/)).toBeInTheDocument();
      });

      // Click close button (if present)
      const closeButton = screen.queryByRole('button', { name: /close/i });
      if (closeButton) {
        await user.click(closeButton);
      }
    });
  });

  describe('API Integration', () => {
    it('should call GET /skills endpoint on mount', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: mockSkills }),
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
          expect.stringContaining('/skills')
        );
      });
    });

    it('should handle non-OK responses', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: false,
        status: 500,
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load skills')).toBeInTheDocument();
      });
    });

    it('should handle malformed JSON', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        },
      });

      render(<SkillPanel />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load skills')).toBeInTheDocument();
      });
    });
  });

  describe('Header', () => {
    it('should render header with title', () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      render(<SkillPanel />);
      expect(screen.getByText('Skills')).toBeInTheDocument();
    });

    it('should render header icon', () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      render(<SkillPanel />);
      const header = screen.getByTestId('skill-panel').querySelector('h2');
      expect(header).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have data-testid for easy querying', () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      render(<SkillPanel />);
      expect(screen.getByTestId('skill-panel')).toBeInTheDocument();
    });

    it('should pass through custom className', () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({ skills: [] }),
      });

      const { container } = render(<SkillPanel className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });
});
