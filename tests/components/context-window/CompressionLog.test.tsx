/**
 * CompressionLog Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CompressionLog } from '@/components/CompressionLog';
import type { CompressionEvent } from '@/types/context-window';

describe('CompressionLog', () => {
  const mockEvents: CompressionEvent[] = [
    {
      id: 'compression_1',
      timestamp: Date.now(),
      before_tokens: 5000,
      after_tokens: 2000,
      tokens_saved: 3000,
      method: 'summarization',
      affected_slots: ['history'],
    },
    {
      id: 'compression_2',
      timestamp: Date.now() - 1000,
      before_tokens: 8000,
      after_tokens: 3000,
      tokens_saved: 5000,
      method: 'hybrid',
      affected_slots: ['history', 'system'],
    },
  ];

  describe('Rendering', () => {
    it('should render header with event count', () => {
      render(<CompressionLog events={mockEvents} />);
      expect(screen.getByText('压缩事件日志')).toBeInTheDocument();
      expect(screen.getByText('2 个压缩事件')).toBeInTheDocument();
    });

    it('should render empty state when no events', () => {
      render(<CompressionLog events={[]} />);
      expect(screen.getByText('暂无压缩事件')).toBeInTheDocument();
    });

    it('should render all compression events', () => {
      render(<CompressionLog events={mockEvents} />);
      expect(screen.getByText('摘要压缩')).toBeInTheDocument();
      expect(screen.getByText('混合压缩')).toBeInTheDocument();
    });
  });

  describe('Event Display', () => {
    it('should display compression method labels', () => {
      render(<CompressionLog events={mockEvents} />);
      expect(screen.getByText('摘要压缩')).toBeInTheDocument();
      expect(screen.getByText('混合压缩')).toBeInTheDocument();
    });

    it('should display before/after token counts', () => {
      render(<CompressionLog events={mockEvents} />);
      const beforeElements = screen.getAllByTestId('compression-before');
      const afterElements = screen.getAllByTestId('compression-after');

      expect(beforeElements[0]).toHaveTextContent('5.0k');
      expect(afterElements[0]).toHaveTextContent('2.0k');
    });

    it('should display saved percentage', () => {
      render(<CompressionLog events={mockEvents} />);
      const savedElements = screen.getAllByTestId('compression-saved');

      // 3000 / 5000 * 100 = 60%
      expect(savedElements[0]).toHaveTextContent('60.0%');
      // 5000 / 8000 * 100 = 62.5%
      expect(savedElements[1]).toHaveTextContent('62.5%');
    });

    it('should display tokens saved', () => {
      render(<CompressionLog events={mockEvents} />);
      const savedTokensElements = screen.getAllByTestId('compression-tokens-saved');

      expect(savedTokensElements[0]).toHaveTextContent('3.0k Token');
      expect(savedTokensElements[1]).toHaveTextContent('5.0k Token');
    });

    it('should display affected slots', () => {
      render(<CompressionLog events={mockEvents} />);
      const affectedSlots = screen.getAllByTestId('affected-slot');

      expect(affectedSlots[0]).toHaveTextContent('history');
      expect(affectedSlots[1]).toHaveTextContent('history');
      expect(affectedSlots[2]).toHaveTextContent('system');
    });
  });

  describe('Method Labels', () => {
    it('should display correct label for summarization', () => {
      const event: CompressionEvent = {
        id: '1',
        timestamp: Date.now(),
        before_tokens: 1000,
        after_tokens: 500,
        tokens_saved: 500,
        method: 'summarization',
        affected_slots: [],
      };
      render(<CompressionLog events={[event]} />);
      expect(screen.getByText('摘要压缩')).toBeInTheDocument();
    });

    it('should display correct label for truncation', () => {
      const event: CompressionEvent = {
        id: '1',
        timestamp: Date.now(),
        before_tokens: 1000,
        after_tokens: 500,
        tokens_saved: 500,
        method: 'truncation',
        affected_slots: [],
      };
      render(<CompressionLog events={[event]} />);
      expect(screen.getByText('截断')).toBeInTheDocument();
    });

    it('should display correct label for hybrid', () => {
      const event: CompressionEvent = {
        id: '1',
        timestamp: Date.now(),
        before_tokens: 1000,
        after_tokens: 500,
        tokens_saved: 500,
        method: 'hybrid',
        affected_slots: [],
      };
      render(<CompressionLog events={[event]} />);
      expect(screen.getByText('混合压缩')).toBeInTheDocument();
    });
  });

  describe('Number Formatting', () => {
    it('should format large numbers with k suffix', () => {
      const largeEvent: CompressionEvent = {
        id: '1',
        timestamp: Date.now(),
        before_tokens: 15000,
        after_tokens: 5000,
        tokens_saved: 10000,
        method: 'summarization',
        affected_slots: [],
      };
      render(<CompressionLog events={[largeEvent]} />);
      expect(screen.getByTestId('compression-before')).toHaveTextContent('15.0k');
      expect(screen.getByTestId('compression-after')).toHaveTextContent('5.0k');
    });

    it('should display small numbers without suffix', () => {
      const smallEvent: CompressionEvent = {
        id: '1',
        timestamp: Date.now(),
        before_tokens: 500,
        after_tokens: 200,
        tokens_saved: 300,
        method: 'summarization',
        affected_slots: [],
      };
      render(<CompressionLog events={[smallEvent]} />);
      expect(screen.getByTestId('compression-before')).toHaveTextContent('500');
      expect(screen.getByTestId('compression-after')).toHaveTextContent('200');
    });
  });

  describe('Timestamp Display', () => {
    it('should display event timestamps', () => {
      render(<CompressionLog events={mockEvents} />);
      const timestamps = screen.getAllByTestId('compression-timestamp');
      expect(timestamps).toHaveLength(2);
      expect(timestamps[0]).toBeInTheDocument();
    });
  });
});
