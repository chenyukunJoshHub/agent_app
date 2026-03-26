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
  turnId?: string; // 新增：前端标注的 turn 归属
}

/**
 * Semantic execution block — a high-level summary of related trace events.
 */
export interface TraceBlock {
  id: string;
  timestamp: string;
  type:
    | 'turn_start'
    | 'thinking'
    | 'tool_call'
    | 'answer'
    | 'memory_load'
    | 'prompt_build'
    | 'hil_pause'
    | 'error'
    | 'turn_summary';
  duration_ms: number;
  status: 'pending' | 'ok' | 'skip' | 'error';
  detail?: string;

  thinking?: {
    content_preview: string;
    input_tokens: number;
    output_tokens: number;
  };
  tool_call?: {
    name: string;
    args: Record<string, unknown>;
    result_preview: string;
    result_length: number;
    error?: string;
  };
  memory_load?: {
    count: number;
    injected: boolean;
  };
  prompt_build?: {
    messages: number;
    total_tokens: number;
    budget: number;
  };
  turn_summary?: {
    total_duration_ms: number;
    think_count: number;
    tool_count: number;
    total_tokens: number;
    finish_reason: string;
  };
  error?: {
    message: string;
    stage: string;
    step: string;
  };

  turnId?: string;
}

/** Block types visible in simple (user-friendly) mode. */
export const USER_VISIBLE_BLOCKS = new Set<TraceBlock['type']>([
  'turn_start',
  'thinking',
  'tool_call',
  'answer',
  'hil_pause',
  'error',
  'turn_summary',
]);
