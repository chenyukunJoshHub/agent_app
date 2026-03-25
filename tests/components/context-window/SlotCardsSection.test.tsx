import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SlotCardsSection } from '@/components/context/SlotCardsSection';
import type { SlotDetail, StateMessage } from '@/types/context-window';

const mockSlots: SlotDetail[] = [
  { name: 'system', display_name: '① 系统提示词', content: 'You are an AI...', tokens: 2048, enabled: true },
  { name: 'history', display_name: '⑧ 会话历史', content: '', tokens: 3200, enabled: true },
  { name: 'rag', display_name: '④ RAG 背景知识', content: 'doc content', tokens: 0, enabled: false },
];

const mockStateMessages: StateMessage[] = [
  { role: 'user', content: 'hello' },
  { role: 'assistant', content: 'hi there' },
];

describe('SlotCardsSection', () => {
  it('应渲染模块三青绿色色条', () => {
    render(
      <SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />
    );
    expect(screen.getByTestId('module3-accent')).toBeInTheDocument();
  });

  it('应按 token 降序排列：history(3200) 在 system(2048) 前', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    const historyCard = screen.getByTestId('slot-card-history');
    const systemCard = screen.getByTestId('slot-card-system');
    // DOCUMENT_POSITION_FOLLOWING = 4 — historyCard comes before systemCard in DOM
    expect(historyCard.compareDocumentPosition(systemCard) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();
  });

  it('disabled slot 应有 opacity 样式', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    const ragCard = screen.getByTestId('slot-card-rag');
    expect(ragCard.className).toMatch(/opacity/);
  });

  it('点击 enabled slot 应展开内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-system'));
    expect(screen.getByText(/You are an AI/)).toBeInTheDocument();
  });

  it('再次点击应折叠内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-system'));
    fireEvent.click(screen.getByTestId('slot-card-system'));
    expect(screen.queryByText(/You are an AI/)).not.toBeInTheDocument();
  });

  it('⑧ 会话历史展开后应显示 stateMessages 内容', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-history'));
    expect(screen.getByText(/hello/)).toBeInTheDocument();
  });

  it('disabled slot 点击后不应展开', () => {
    render(<SlotCardsSection slotDetails={mockSlots} stateMessages={mockStateMessages} />);
    fireEvent.click(screen.getByTestId('slot-card-rag'));
    expect(screen.queryByText(/doc content/)).not.toBeInTheDocument();
  });

  it('空 slotDetails 不应崩溃', () => {
    render(<SlotCardsSection slotDetails={[]} stateMessages={[]} />);
    expect(document.body).toBeInTheDocument();
  });
});
