import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useSSEHandlers } from '@/hooks/useSSEHandlers';
import { useSession } from '@/store/use-session';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';

type MockHandler = (event: { type: string; data: unknown }) => void;

const {
  eventHandlers,
  mockOn,
  mockOnStateChange,
  mockConnect,
  mockDisconnect,
} = vi.hoisted(() => {
  const handlersMap = new Map<string, MockHandler[]>();
  const on = vi.fn((eventType: string, handler: MockHandler) => {
    const handlers = handlersMap.get(eventType) ?? [];
    handlers.push(handler);
    handlersMap.set(eventType, handlers);
  });

  return {
    eventHandlers: handlersMap,
    mockOn: on,
    mockOnStateChange: vi.fn(),
    mockConnect: vi.fn(),
    mockDisconnect: vi.fn(),
  };
});

vi.mock('@/lib/sse-manager', () => ({
  sseManager: {
    on: mockOn,
    onStateChange: mockOnStateChange,
    connect: mockConnect,
    disconnect: mockDisconnect,
  },
}));

function emit(eventType: string, data: unknown): void {
  const handlers = eventHandlers.get(eventType) ?? [];
  for (const handler of handlers) {
    handler({ type: eventType, data });
  }
}

describe('useSSEHandlers', () => {
  beforeEach(() => {
    eventHandlers.clear();
    vi.clearAllMocks();
    useSession.getState().clearMessages();
    useSession.getState().setContextWindowData(EMPTY_CONTEXT_DATA);
    useSession.getState().setError(null);
    useSession.getState().setLoading(false);
  });

  it('appends compression events into contextWindowData', async () => {
    const { result } = renderHook(() => useSSEHandlers());

    await act(async () => {
      await result.current.handleSendMessage('测试压缩事件');
    });

    expect(mockOn).toHaveBeenCalledWith('compression', expect.any(Function));

    act(() => {
      emit('compression', {
        before_tokens: 1200,
        after_tokens: 700,
        method: 'summarization',
        affected_slots: ['history'],
        summary_text: '压缩摘要',
      });
    });

    const events = useSession.getState().contextWindowData.compressionEvents;
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      before_tokens: 1200,
      after_tokens: 700,
      tokens_saved: 500,
      method: 'summarization',
      affected_slots: ['history'],
      summary_text: '压缩摘要',
    });

    act(() => {
      emit('done', { answer: 'ok', messages: [] });
    });
  });
});
