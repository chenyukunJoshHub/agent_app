/**
 * ContextWindowPanel Component Tests
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { ContextWindowPanel } from '../ContextWindowPanel';
import type { ContextWindowData } from '@/types/context-window';

describe('ContextWindowPanel', () => {
  const mockData: ContextWindowData = {
    budget: {
      model_context_window: 200000,
      working_budget: 32768,
      slots: {
        system: 2000,
        active_skill: 0,
        few_shot: 0,
        rag: 0,
        episodic: 500,
        procedural: 0,
        tools: 1200,
        history: 21068,
        output_format: 0,
        user_input: 0,
      },
      usage: {
        total_used: 5000,
        total_remaining: 27768,
        input_budget: 24576,
        output_reserve: 8192,
      },
    },
    slotUsage: [
      {
        name: 'system',
        displayName: '系统提示词',
        allocated: 2000,
        used: 1500,
        color: '#5E6AD2',
      },
      {
        name: 'episodic',
        displayName: '用户画像',
        allocated: 500,
        used: 300,
        color: '#F59E0B',
      },
      {
        name: 'tools',
        displayName: '工具定义',
        allocated: 1200,
        used: 800,
        color: '#3B82F6',
      },
      {
        name: 'history',
        displayName: '会话历史',
        allocated: 21068,
        used: 2400,
        color: '#6366F1',
      },
    ],
    compressionEvents: [],
  };

  describe('Rendering', () => {
    it('should render the header with model specs', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByText('Context Window')).toBeInTheDocument();
      expect(screen.getByText(/Token 预算: 32.8k/)).toBeInTheDocument();
      expect(screen.getByText(/模型上限: 200k/)).toBeInTheDocument();
    });

    it('should render overall progress section', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByText('总体进度')).toBeInTheDocument();
      expect(screen.getByTestId('overall-progress-fill')).toBeInTheDocument();
    });

    it('should render slot breakdown section', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByText('Slot 分解')).toBeInTheDocument();
      expect(screen.getByTestId('slot-breakdown')).toBeInTheDocument();
    });

    it('should render statistics row', async () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByTestId('stat-input-budget')).toBeInTheDocument();
      expect(screen.getByTestId('stat-output-reserve')).toBeInTheDocument();
      expect(screen.getByTestId('stat-total-used')).toBeInTheDocument();
      expect(screen.getByTestId('stat-compression-count')).toBeInTheDocument();
    });

    it('should render compression log section', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByText('压缩事件日志')).toBeInTheDocument();
      expect(screen.getByText('暂无压缩事件')).toBeInTheDocument();
    });
  });

  describe('Usage Calculation', () => {
    it('should display correct usage percentage', () => {
      render(<ContextWindowPanel data={mockData} />);
      // 5000 / 32768 * 100 = 15.26%
      expect(screen.getByTestId('overall-percentage')).toHaveTextContent(/15.3%/);
    });

    it('should display correct remaining tokens', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByTestId('overall-remaining')).toHaveTextContent(/27.8k/);
    });

    it('should show "正常" status when usage < 70%', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByTestId('overall-status')).toHaveTextContent('正常');
    });
  });

  describe('Slot Bars', () => {
    it('should render all slot bars', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByText('系统提示词')).toBeInTheDocument();
      expect(screen.getByText('用户画像')).toBeInTheDocument();
      expect(screen.getByText('工具定义')).toBeInTheDocument();
      expect(screen.getByText('会话历史')).toBeInTheDocument();
    });

    it('should display correct slot usage', () => {
      render(<ContextWindowPanel data={mockData} />);
      expect(screen.getByTestId('slot-used-tokens', { selector: '[data-slot-name="system"]' }))
        ?.toHaveTextContent('1.5k');
    });
  });

  describe('Compression Events', () => {
    it('should display compression events when present', () => {
      const dataWithEvents: ContextWindowData = {
        ...mockData,
        compressionEvents: [
          {
            id: 'compression_1',
            timestamp: Date.now(),
            before_tokens: 5000,
            after_tokens: 2000,
            tokens_saved: 3000,
            method: 'summarization',
            affected_slots: ['history'],
          },
        ],
      };

      render(<ContextWindowPanel data={dataWithEvents} />);
      expect(screen.getByText('摘要压缩')).toBeInTheDocument();
      expect(screen.getByTestId('compression-before')).toHaveTextContent('5.0k');
      expect(screen.getByTestId('compression-after')).toHaveTextContent('2.0k');
      expect(screen.getByTestId('compression-saved')).toHaveTextContent('60.0%');
    });
  });

  describe('Status Colors', () => {
    it('should show warning status when usage >= 70%', () => {
      const highUsageData: ContextWindowData = {
        ...mockData,
        budget: {
          ...mockData.budget,
          usage: {
            ...mockData.budget.usage,
            total_used: 24000, // 73% usage
            total_remaining: 8768,
          },
        },
      };

      render(<ContextWindowPanel data={highUsageData} />);
      expect(screen.getByTestId('overall-status')).toHaveTextContent('使用较多');
    });

    it('should show danger status when usage >= 90%', () => {
      const criticalUsageData: ContextWindowData = {
        ...mockData,
        budget: {
          ...mockData.budget,
          usage: {
            ...mockData.budget.usage,
            total_used: 30000, // 91.5% usage
            total_remaining: 2768,
          },
        },
      };

      render(<ContextWindowPanel data={criticalUsageData} />);
      expect(screen.getByTestId('overall-status')).toHaveTextContent('即将耗尽');
    });
  });
});
