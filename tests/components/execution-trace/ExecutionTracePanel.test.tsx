/**
 * Unit tests for ExecutionTracePanel Turn markers.
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import type { TraceEvent } from '@/types/trace';

const makeEvent = (id: string, turnId?: string): TraceEvent => ({
  id,
  timestamp: new Date().toISOString(),
  stage: 'react',
  step: 'some_step',
  status: 'ok',
  payload: {},
  turnId,
});

describe('ExecutionTracePanel Turn markers', () => {
  it('无事件时不渲染 Turn 分隔线', () => {
    render(<ExecutionTracePanel traceEvents={[]} />);
    expect(screen.queryByTestId('turn-divider')).toBeNull();
  });

  it('有 turnId 的事件渲染 Turn 分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_1')];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(1);
    expect(screen.getByText(/Turn #1/)).toBeInTheDocument();
  });

  it('两个不同 turnId 渲染两条分隔线', () => {
    const events = [makeEvent('e1', 'turn_1'), makeEvent('e2', 'turn_2')];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getAllByTestId('turn-divider')).toHaveLength(2);
  });

  it('turnId 为 undefined 的事件渲染 Pre-session 分隔线', () => {
    const events = [makeEvent('e1', undefined)];
    render(<ExecutionTracePanel traceEvents={events} />);
    expect(screen.getByText(/Pre-session/)).toBeInTheDocument();
  });
});
