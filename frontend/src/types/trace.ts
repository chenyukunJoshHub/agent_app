/**
 * Detailed execution trace event from backend SSE.
 */
export interface TraceEvent {
  id: string;
  timestamp: string;
  stage: string;
  step: string;
  status: 'start' | 'ok' | 'skip' | 'error' | string;
  payload: Record<string, unknown>;
  turnId?: string;  // 新增：前端标注的 turn 归属
}

