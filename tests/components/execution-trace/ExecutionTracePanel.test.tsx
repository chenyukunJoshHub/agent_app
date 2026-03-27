/**
 * Unit tests for ExecutionTracePanel Turn markers.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import type { TraceBlock, TraceEvent } from '@/types/trace';

const makeEvent = (id: string, turnId?: string): TraceEvent => ({
  id,
  timestamp: new Date().toISOString(),
  stage: 'react',
  step: 'some_step',
  status: 'ok',
  payload: {},
  turnId,
});

const makeBlock = (id: string, type: TraceBlock['type'], turnId?: string): TraceBlock => ({
  id,
  timestamp: new Date().toISOString(),
  type,
  duration_ms: 120,
  status: 'ok',
  detail: 'test',
  turnId,
});

describe('ExecutionTracePanel Turn markers', () => {
  it('无事件时不渲染 Turn 分隔线', () => {
    render(<ExecutionTracePanel traceEvents={[]} traceBlocks={[]} />);
    expect(screen.queryByTestId('turn-divider')).toBeNull();
  });

  it('同一 turn 的 block 渲染一条 Turn 分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_1')];
    const blocks = [makeBlock('b1', 'turn_start', 'turn_1'), makeBlock('b2', 'thinking', 'turn_1')];
    render(<ExecutionTracePanel traceEvents={events} traceBlocks={blocks} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(1);
    expect(screen.getByText(/Turn #1/)).toBeInTheDocument();
  });

  it('两个不同 turnId 的 block 渲染两条分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_2')];
    const blocks = [makeBlock('b1', 'thinking', 'turn_1'), makeBlock('b2', 'thinking', 'turn_2')];
    render(<ExecutionTracePanel traceEvents={events} traceBlocks={blocks} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(2);
  });

  it('turnId 为 undefined 的 block 渲染 Pre-session 分隔线', () => {
    const events = [makeEvent('e1', undefined)];
    const blocks = [makeBlock('b1', 'turn_start', undefined)];
    render(<ExecutionTracePanel traceEvents={events} traceBlocks={blocks} />);
    expect(screen.getByText(/Pre-session/)).toBeInTheDocument();
  });
});
