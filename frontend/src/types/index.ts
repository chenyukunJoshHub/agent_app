/**
 * TypeScript type definitions
 */

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: ToolCall[];
  tokens_used?: number;
  created_at: string;
}

export interface ToolCall {
  id: string;
  tool_name: string;
  parameters: Record<string, unknown>;
  result?: unknown;
  error?: string;
  duration_ms?: number;
  requires_confirmation?: boolean;
  confirmed_by_user?: boolean;
}

export interface Session {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface TimelineEvent {
  id: string;
  type:
    | 'start'
    | 'thinking'
    | 'tool_call'
    | 'tool_result'
    | 'hil_request'
    | 'response'
    | 'end'
    | 'error';
  data: Record<string, unknown>;
  timestamp: string;
}

export interface Tool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  requires_confirmation: boolean;
  dangerous: boolean;
}
