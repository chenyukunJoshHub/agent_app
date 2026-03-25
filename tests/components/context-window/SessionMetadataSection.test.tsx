import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SessionMetadataSection } from '@/components/context/SessionMetadataSection';
import type { SessionMeta, StateMessage } from '@/types/context-window';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

const mockMeta: SessionMeta = {
  session_name: '合同审查',
  model: 'claude-sonnet-4-6',
  created_at: '2026-03-25T09:00:00.000Z',
};

const mockMessages: StateMessage[] = [
  { role: 'user', content: 'hello' },
  { role: 'assistant', content: 'hi' },
  { role: 'user', content: 'world' },
];

describe('SessionMetadataSection', () => {
  it('应渲染模块一蓝色色条', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByTestId('module1-accent')).toBeInTheDocument();
  });

  it('应显示模型名称', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText('claude-sonnet-4-6')).toBeInTheDocument();
  });

  it('应显示上下文限制 200,000', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText(/200,000/)).toBeInTheDocument();
  });

  it('应统计用户消息数量', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={mockMessages}
        lastActivityTime={null}
      />
    );
    expect(screen.getByTestId('user-messages-count')).toHaveTextContent('2');
  });

  it('应统计助手消息数量', () => {
    render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={mockMessages}
        lastActivityTime={null}
      />
    );
    expect(screen.getByTestId('assistant-messages-count')).toHaveTextContent('1');
  });

  it('sessionMeta 为 null 时应渲染占位符而不崩溃', () => {
    render(
      <SessionMetadataSection
        sessionMeta={null}
        budget={EMPTY_CONTEXT_DATA.budget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getAllByText('—').length).toBeGreaterThan(0);
  });

  it('使用率 ≥ 90% 时应用 text-error-text 类', () => {
    const heavyBudget = {
      ...EMPTY_CONTEXT_DATA.budget,
      working_budget: 32768,
      usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 30000 },
    };
    const { container } = render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={heavyBudget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    const usageEl = container.querySelector('[data-testid="usage-rate"]');
    expect(usageEl?.className).toMatch(/text-error-text/);
  });

  it('使用率 70–90% 时应用 text-warning-text 类', () => {
    const medBudget = {
      ...EMPTY_CONTEXT_DATA.budget,
      working_budget: 32768,
      usage: { ...EMPTY_CONTEXT_DATA.budget.usage, total_used: 25000 },
    };
    const { container } = render(
      <SessionMetadataSection
        sessionMeta={mockMeta}
        budget={medBudget}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    const usageEl = container.querySelector('[data-testid="usage-rate"]');
    expect(usageEl?.className).toMatch(/text-warning-text/);
  });
});
