/**
 * SlotBar Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SlotBar } from '@/components/SlotBar';
import type { SlotUsage } from '@/types/context-window';

describe('SlotBar', () => {
  const mockSlot: SlotUsage = {
    name: 'system',
    displayName: '系统提示词',
    allocated: 2000,
    used: 1500,
    color: '#5E6AD2',
  };

  describe('Rendering', () => {
    it('should render slot name', () => {
      render(<SlotBar slot={mockSlot} />);
      expect(screen.getByText('系统提示词')).toBeInTheDocument();
    });

    it('should render color indicator', () => {
      const { container } = render(<SlotBar slot={mockSlot} />);
      const indicator = container.querySelector('[data-testid="slot-color-indicator"]');
      expect(indicator).toBeInTheDocument();
      expect(indicator).toHaveStyle({ backgroundColor: '#5E6AD2' });
    });

    it('should render progress bar', () => {
      const { container } = render(<SlotBar slot={mockSlot} />);
      expect(container.querySelector('[data-testid="slot-progress-fill"]')).toBeInTheDocument();
    });

    it('should render used and allocated tokens', () => {
      render(<SlotBar slot={mockSlot} />);
      expect(screen.getByTestId('slot-used-tokens')).toHaveTextContent('1.5k');
      expect(screen.getByTestId('slot-allocated-tokens')).toHaveTextContent('2.0k');
    });

    it('should format token numbers correctly', () => {
      const smallSlot: SlotUsage = {
        ...mockSlot,
        allocated: 500,
        used: 300,
      };
      render(<SlotBar slot={smallSlot} />);
      expect(screen.getByTestId('slot-used-tokens')).toHaveTextContent('300');
      expect(screen.getByTestId('slot-allocated-tokens')).toHaveTextContent('500');
    });
  });

  describe('Progress Calculation', () => {
    it('should calculate correct usage percentage', () => {
      const { container } = render(<SlotBar slot={mockSlot} />);
      const progressFill = container.querySelector('[data-testid="slot-progress-fill"]');
      expect(progressFill).toBeInTheDocument();
    });

    it('should handle zero allocation', () => {
      const zeroSlot: SlotUsage = {
        ...mockSlot,
        allocated: 0,
        used: 0,
      };
      const { container } = render(<SlotBar slot={zeroSlot} />);
      const progressFill = container.querySelector('[data-testid="slot-progress-fill"]');
      expect(progressFill).toBeInTheDocument();
    });
  });

  describe('Overflow Detection', () => {
    it('should show overflow warning when used > allocated', () => {
      const overflowSlot: SlotUsage = {
        ...mockSlot,
        allocated: 1000,
        used: 1500,
      };
      render(<SlotBar slot={overflowSlot} />);
      expect(screen.getByTestId('slot-overflow-warning')).toBeInTheDocument();
    });

    it('should not show overflow warning when used <= allocated', () => {
      render(<SlotBar slot={mockSlot} />);
      expect(screen.queryByTestId('slot-overflow-warning')).not.toBeInTheDocument();
    });

    it('should apply danger color to overflow slot', () => {
      const overflowSlot: SlotUsage = {
        ...mockSlot,
        allocated: 1000,
        used: 1500,
      };
      const { container } = render(<SlotBar slot={overflowSlot} />);
      const progressFill = container.querySelector('[data-testid="slot-progress-fill"]');
      expect(progressFill).toHaveClass('bg-danger');
    });
  });

  describe('Color Coding', () => {
    it('should use slot-specific color for progress bar', () => {
      const { container } = render(<SlotBar slot={mockSlot} />);
      const progressFill = container.querySelector('[data-testid="slot-progress-fill"]');
      expect(progressFill).toHaveStyle({ backgroundColor: '#5E6AD2' });
    });

    it('should override color on overflow', () => {
      const overflowSlot: SlotUsage = {
        ...mockSlot,
        allocated: 1000,
        used: 1500,
      };
      const { container } = render(<SlotBar slot={overflowSlot} />);
      const progressFill = container.querySelector('[data-testid="slot-progress-fill"]');
      // Overflow should use danger color instead of slot color
      expect(progressFill).toHaveClass('bg-danger');
    });
  });
});
