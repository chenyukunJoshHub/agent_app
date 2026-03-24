/**
 * Unit tests for MessageList with stateMessages and compression events.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList } from '@/components/MessageList';
import type { CompressionEvent } from '@/types/context-window';
import type { StateMessage } from '@/types/context-window';

const baseMessages = [
  { id: '1', role: 'user' as const, content: '你好', timestamp: Date.now(), tool_calls: [] },
  { id: '2', role: 'assistant' as const, content: '你好！', timestamp: Date.now() },
];

describe('MessageList with stateMessages', () => {
  it('stateMessages 中的 tool role 渲染工具气泡', () => {
    const stateMessages: StateMessage[] = [
      { role: 'tool', content: '搜索结果', tool_call_id: 'tc1' },
    ];
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={stateMessages}
        compressionEvents={[]}
      />
    );
    expect(screen.getByTestId('tool-message-bubble')).toBeInTheDocument();
    expect(screen.getByText('搜索结果')).toBeInTheDocument();
  });
});

describe('MessageList compression notification', () => {
  it('有压缩事件时渲染压缩通知气泡', () => {
    const event: CompressionEvent = {
      id: 'c1',
      timestamp: Date.now(),
      before_tokens: 2000,
      after_tokens: 800,
      tokens_saved: 1200,
      method: 'summarization',
      affected_slots: ['history'],
    };
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={[]}
        compressionEvents={[event]}
      />
    );
    expect(screen.getByTestId('compression-notification')).toBeInTheDocument();
    expect(screen.getByText(/节省 1,200 tokens/)).toBeInTheDocument();
  });

  it('无压缩事件时不渲染压缩通知气泡', () => {
    render(
      <MessageList
        messages={baseMessages}
        isLoading={false}
        stateMessages={[]}
        compressionEvents={[]}
      />
    );
    expect(screen.queryByTestId('compression-notification')).toBeNull();
  });
});
