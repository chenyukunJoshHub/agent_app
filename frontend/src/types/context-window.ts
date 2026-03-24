/**
 * Context Window Types
 *
 * Types for Token Budget State and Slot Usage visualization.
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */

export interface SlotAllocation {
  /** Slot ①: System Prompt + Skill Registry + Few-shot */
  system: number;
  /** Slot ②: Active Skill content */
  active_skill: number;
  /** Slot ③: Dynamic Few-shot */
  few_shot: number;
  /** Slot ④: RAG background knowledge */
  rag: number;
  /** Slot ⑤: Episodic memory (user profile) */
  episodic: number;
  /** Slot ⑥: Procedural memory */
  procedural: number;
  /** Slot ⑦: Tools schema */
  tools: number;
  /** Slot ⑧: Conversation history (elastic) */
  history: number;
  /** Slot ⑨: Output format */
  output_format: number;
  /** Slot ⑩: User input */
  user_input: number;
}

export interface SlotUsage {
  /** Slot name */
  name: keyof SlotAllocation;
  /** Display name in Chinese */
  displayName: string;
  /** Allocated tokens (max) */
  allocated: number;
  /** Actually used tokens */
  used: number;
  /** Color for visualization */
  color: string;
}

export interface UsageMetrics {
  /** Total tokens used */
  total_used: number;
  /** Total tokens remaining */
  total_remaining: number;
  /** Available input budget */
  input_budget: number;
  /** Output reservation */
  output_reserve: number;
  /** Reserved buffer before triggering auto-compaction */
  autocompact_buffer?: number;
}

export interface TokenBudgetState {
  /** Model context window size (e.g., 200,000 for Claude Sonnet 4.6) */
  model_context_window: number;
  /** Agent working budget (e.g., 32,768) */
  working_budget: number;
  /** Slot allocations */
  slots: SlotAllocation;
  /** Usage metrics */
  usage: UsageMetrics;
}

export interface CompressionEvent {
  /** Event ID */
  id: string;
  /** Timestamp */
  timestamp: number;
  /** Tokens before compression */
  before_tokens: number;
  /** Tokens after compression */
  after_tokens: number;
  /** Tokens saved */
  tokens_saved: number;
  /** Compression method */
  method: 'summarization' | 'truncation' | 'hybrid';
  /** Slots affected */
  affected_slots: string[];
  /** 压缩摘要文本（后端可选提供） */
  summary_text?: string;
}

export interface ContextWindowData {
  /** Token budget state */
  budget: TokenBudgetState;
  /** Slot usage details */
  slotUsage: SlotUsage[];
  /** Compression events */
  compressionEvents: CompressionEvent[];
}

export interface ContextWindowEvent {
  type: 'context_window';
  data: ContextWindowData;
}

export interface SlotDetail {
  /** Slot name */
  name: string;
  /** Display name in Chinese */
  display_name: string;
  /** Slot content */
  content: string;
  /** Token count */
  tokens: number;
  /** Whether slot is enabled */
  enabled: boolean;
}

export interface SlotDetailsResponse {
  /** Session ID */
  session_id?: string;
  /** Slot details */
  slots: SlotDetail[];
  /** Total tokens */
  total_tokens: number;
  /** Timestamp */
  timestamp: number;
}

export interface SlotDetailsEvent {
  type: 'slot_details';
  data: SlotDetailsResponse;
}

export const SLOT_COLORS: Record<keyof SlotAllocation, string> = {
  system: '#5E6AD2',
  active_skill: '#8B5CF6',
  few_shot: '#06B6D4',
  rag: '#10B981',
  episodic: '#F59E0B',
  procedural: '#EF4444',
  tools: '#3B82F6',
  history: '#6366F1',
  output_format: '#EC4899',
  user_input: '#22C55E',
} as const;

export const SLOT_DISPLAY_NAMES: Record<keyof SlotAllocation, string> = {
  system: '系统提示词',
  active_skill: '活跃技能',
  few_shot: '动态示例',
  rag: '背景知识',
  episodic: '用户画像',
  procedural: '程序记忆',
  tools: '工具定义',
  history: '会话历史',
  output_format: '输出格式',
  user_input: '用户输入',
} as const;

/** 后端 state["messages"] 中的单条消息 */
export interface StateMessage {
  role: 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: Array<{
    id: string;
    type: 'function';
    function: { name: string; arguments: string };
  }>;
  tool_call_id?: string; // 仅 role=tool 时有值
}

/** 初始空状态 Context 数据，展示全部 10 个 Slot 且 token 均为 0 */
export const EMPTY_CONTEXT_DATA: ContextWindowData = {
  budget: {
    model_context_window: 200000,
    working_budget: 32768,
    slots: {
      system: 0,
      active_skill: 0,
      few_shot: 0,
      rag: 0,
      episodic: 0,
      procedural: 0,
      tools: 0,
      history: 0,
      output_format: 0,
      user_input: 0,
    },
    usage: {
      total_used: 0,
      total_remaining: 32768,
      input_budget: 0,
      output_reserve: 0,
      autocompact_buffer: 0,
    },
  },
  slotUsage: [
    { name: 'system',       displayName: '① System Prompt',   allocated: 0, used: 0, color: '#5E6AD2' },
    { name: 'active_skill', displayName: '② 活跃技能',          allocated: 0, used: 0, color: '#8B5CF6' },
    { name: 'few_shot',     displayName: '③ 动态 Few-shot',    allocated: 0, used: 0, color: '#06B6D4' },
    { name: 'rag',          displayName: '④ RAG 背景知识',      allocated: 0, used: 0, color: '#10B981' },
    { name: 'episodic',     displayName: '⑤ 用户画像',          allocated: 0, used: 0, color: '#F59E0B' },
    { name: 'procedural',   displayName: '⑥ 程序性记忆',        allocated: 0, used: 0, color: '#EF4444' },
    { name: 'tools',        displayName: '⑦ 工具定义',          allocated: 0, used: 0, color: '#3B82F6' },
    { name: 'history',      displayName: '⑧ 会话历史',          allocated: 0, used: 0, color: '#6366F1' },
    { name: 'output_format',displayName: '⑨ 输出格式规范',      allocated: 0, used: 0, color: '#EC4899' },
    { name: 'user_input',   displayName: '⑩ 本轮用户输入',      allocated: 0, used: 0, color: '#22C55E' },
  ],
  compressionEvents: [],
};
