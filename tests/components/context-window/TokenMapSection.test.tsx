import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TokenMapSection } from '@/components/context/TokenMapSection';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

const mockBudget = {
  model_context_window: 200000,
  working_budget: 32768,
  slots: {
    system: 2048, active_skill: 0, few_shot: 0, rag: 0,
    episodic: 0, procedural: 0, tools: 1800, history: 3200,
    output_format: 0, user_input: 0,
  },
  usage: {
    total_used: 7048,
    total_remaining: 25720,
    input_budget: 24576,
    output_reserve: 8192,
    autocompact_buffer: 5538,
  },
};

const mockSlotUsage = EMPTY_CONTEXT_DATA.slotUsage.map(s => ({
  ...s,
  used: s.name === 'system' ? 2048 : s.name === 'tools' ? 1800 : s.name === 'history' ? 3200 : 0,
}));

describe('TokenMapSection', () => {
  it('应渲染模块二靛色色条 testid', () => {
    render(
      <TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />
    );
    expect(screen.getByTestId('module2-accent')).toBeInTheDocument();
  });

  it('进度条应包含 12 个段', () => {
    const { container } = render(
      <TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />
    );
    const bar = container.querySelector('[data-testid="token-bar"]');
    expect(bar?.children.length).toBe(12);
  });

  it('应显示 working_budget（包含 32）', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/32/)).toBeInTheDocument();
  });

  it('等宽表格应包含系统提示词行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/系统提示词/)).toBeInTheDocument();
  });

  it('等宽表格应包含剩余可用行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/剩余可用/)).toBeInTheDocument();
  });

  it('等宽表格应包含压缩预留行', () => {
    render(<TokenMapSection budget={mockBudget} slotUsage={mockSlotUsage} />);
    expect(screen.getByText(/压缩预留/)).toBeInTheDocument();
  });

  it('全 0 预算时不应崩溃', () => {
    const { container } = render(
      <TokenMapSection budget={EMPTY_CONTEXT_DATA.budget} slotUsage={EMPTY_CONTEXT_DATA.slotUsage} />
    );
    const bar = container.querySelector('[data-testid="token-bar"]');
    expect(bar).not.toBeNull();
  });
});
