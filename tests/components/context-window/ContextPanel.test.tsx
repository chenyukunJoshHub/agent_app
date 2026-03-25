import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ContextPanel } from '@/components/ContextPanel';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
import type { SessionMeta } from '@/types/context-window';

const mockMeta: SessionMeta = {
  session_name: 'Test',
  model: 'claude-sonnet-4-6',
  created_at: '2026-03-25T09:00:00.000Z',
};

describe('ContextPanel', () => {
  it('应渲染模块一、二、三的 section header', () => {
    render(
      <ContextPanel
        sessionMeta={mockMeta}
        contextWindowData={EMPTY_CONTEXT_DATA}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText(/会话元数据/)).toBeInTheDocument();
    expect(screen.getByText(/Token 地图/)).toBeInTheDocument();
    expect(screen.getByText(/Slot 原文/)).toBeInTheDocument();
  });

  it('无压缩事件时不应渲染模块四', () => {
    render(
      <ContextPanel
        sessionMeta={null}
        contextWindowData={EMPTY_CONTEXT_DATA}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.queryByText('④ 压缩日志')).not.toBeInTheDocument();
  });

  it('有压缩事件时应渲染模块四 header', () => {
    const dataWithEvents = {
      ...EMPTY_CONTEXT_DATA,
      compressionEvents: [{
        id: '1',
        timestamp: Date.now(),
        before_tokens: 10000,
        after_tokens: 5000,
        tokens_saved: 5000,
        method: 'summarization' as const,
        affected_slots: ['history'],
      }],
    };
    render(
      <ContextPanel
        sessionMeta={null}
        contextWindowData={dataWithEvents}
        slotDetails={[]}
        stateMessages={[]}
        lastActivityTime={null}
      />
    );
    expect(screen.getByText('④ 压缩日志')).toBeInTheDocument();
  });
});
