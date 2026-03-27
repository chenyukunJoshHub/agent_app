/**
 * ContextWindowPanel Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import { ContextWindowPanel } from '@/components/ContextWindowPanel';
import type { ContextWindowData, SlotDetail } from '@/types/context-window';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

describe('ContextWindowPanel', () => {
  const mockData: ContextWindowData = {
    budget: {
      model_context_window: 200000,
      working_budget: 32768,
      slots: {
        system: 2000,
        skill_registry: 600,
        skill_protocol: 200,
        few_shot: 0,
        rag: 0,
        episodic: 500,
        procedural: 0,
        tools: 1200,
        history: 21068,
        output_format: 0,
      },
      usage: {
        total_used: 5000,
        total_remaining: 27768,
        input_budget: 24576,
        output_reserve: 8192,
        autocompact_buffer: 4096,
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

  const mockSlotDetails: SlotDetail[] = [
    {
      name: 'system',
      display_name: '系统提示词（基础）',
      content: '系统角色定义',
      tokens: 1200,
      enabled: true,
    },
    {
      name: 'skill_registry',
      display_name: 'Skill 注册表',
      content: '可用技能列表',
      tokens: 300,
      enabled: true,
    },
    {
      name: 'tools',
      display_name: '工具定义',
      content: 'web_search, send_email, read_file',
      tokens: 800,
      enabled: true,
    },
    {
      name: 'history',
      display_name: '会话历史',
      content: '历史消息内容',
      tokens: 2400,
      enabled: true,
    },
  ];

  describe('Rendering', () => {
    it('should render context usage header', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByText('Context Usage')).toBeInTheDocument();
      expect(screen.getByText(/5.0k\/32.8k tokens/)).toBeInTheDocument();
    });

    it('should render free space and autocompact rows', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('context-row-free-space')).toBeInTheDocument();
      expect(screen.getByTestId('context-row-autocompact-buffer')).toBeInTheDocument();
    });

    it('should render complete slot snapshot section', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByText('完整 Slot 快照')).toBeInTheDocument();
      expect(screen.getByTestId('slot-breakdown')).toBeInTheDocument();
    });

    it('should render statistics row', async () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('context-row-autocompact-buffer')).toBeInTheDocument();
      expect(screen.getByTestId('stat-reserved-buffer')).toBeInTheDocument();
      expect(screen.getByTestId('stat-free-space')).toBeInTheDocument();
    });

    it('should render compression log section', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByText('压缩事件日志')).toBeInTheDocument();
      expect(screen.getByText('暂无压缩事件')).toBeInTheDocument();
    });
  });

  describe('Usage Calculation', () => {
    it('should display correct usage percentage', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      // 5000 / 32768 * 100 = 15.26%
      expect(screen.getByTestId('overall-percentage')).toHaveTextContent(/15\.3%/);
    });

    it('should display correct remaining tokens', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('overall-remaining')).toHaveTextContent(/27\.8k/);
    });

    it('should show "正常" status when usage < 70%', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('overall-status')).toHaveTextContent('正常');
    });
  });

  describe('Category Consistency', () => {
    it.skip('should aggregate category usage from slot snapshot data — superseded by ContextPanel', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('context-row-system')).toBeInTheDocument();
      expect(screen.getByTestId('context-row-tools')).toBeInTheDocument();
      expect(screen.getByTestId('context-row-history')).toBeInTheDocument();
    });

    it('should show slot detail names from the same snapshot source', () => {
      render(<ContextWindowPanel data={mockData} slotDetails={mockSlotDetails} />);
      expect(screen.getByText('系统提示词（基础）')).toBeInTheDocument();
      expect(screen.getByText('Skill 注册表')).toBeInTheDocument();
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
            autocompact_buffer: 4096,
          },
        },
      };

      render(<ContextWindowPanel data={highUsageData} slotDetails={mockSlotDetails} />);
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
            autocompact_buffer: 4096,
          },
        },
      };

      render(<ContextWindowPanel data={criticalUsageData} slotDetails={mockSlotDetails} />);
      expect(screen.getByTestId('overall-status')).toHaveTextContent('即将耗尽');
    });
  });

  describe('with EMPTY_CONTEXT_DATA', () => {
    it('Slot 预算分解区块展示全部 10 行（含 ⑨ 会话历史和 ⑩ 输出格式）', () => {
      render(<ContextWindowPanel data={EMPTY_CONTEXT_DATA} />);
      // 在 slot-breakdown 范围内断言当前 Prompt v20 10-slot 显示名称
      const breakdown = screen.getByTestId('slot-breakdown');
      expect(within(breakdown).getByText(/⑨ 会话历史/)).toBeInTheDocument();
      expect(within(breakdown).getByText(/⑩ 输出格式/)).toBeInTheDocument();
    });

    it.skip('Slot ⑨ 和 ⑩ 出现在 category 汇总中（当 tokens > 0）— superseded by ContextPanel', () => {
      // 给 output_format 和 user_input 注入非零数据以触发 category 显示
      const data = {
        ...EMPTY_CONTEXT_DATA,
        slotUsage: EMPTY_CONTEXT_DATA.slotUsage.map((s: any) =>
          s.name === 'output_format' ? { ...s, used: 100 } :
          s.name === 'user_input' ? { ...s, used: 200 } : s
        ),
        budget: {
          ...EMPTY_CONTEXT_DATA.budget,
          slots: { ...EMPTY_CONTEXT_DATA.budget.slots, output_format: 100, user_input: 200 },
          usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 300 },
        },
      };
      render(<ContextWindowPanel data={data} />);
      // 这两个 data-testid 在 Task 6.3 中新增，此测试在实现前应 FAIL
      expect(screen.getByTestId('context-row-output_format')).toBeInTheDocument();
      expect(screen.getByTestId('context-row-user_input')).toBeInTheDocument();
    });
  });
});
