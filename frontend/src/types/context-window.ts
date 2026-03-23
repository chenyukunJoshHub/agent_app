/**
 * Context Window Types
 *
 * Types for Token Budget State and Slot Usage visualization.
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */

/**
 * Token slot allocations (10 slots)
 * Based on Prompt v20 §1.2
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
  /** Slot ⑨: Output format (included in system) */
  output_format?: number;
  /** Slot ⑩: User input (real-time) */
  user_input?: number;
}

/**
 * Slot usage with actual consumption
 */
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

/**
 * Token usage metrics
 */
export interface UsageMetrics {
  /** Total tokens used */
  total_used: number;
  /** Total tokens remaining */
  total_remaining: number;
  /** Available input budget */
  input_budget: number;
  /** Output reservation */
  output_reserve: number;
}

/**
 * Token budget state (from backend API)
 * Matches backend/app/api/context.py#TokenBudgetState
 */
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

/**
 * Compression event log
 */
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
}

/**
 * Context window data for display
 */
export interface ContextWindowData {
  /** Token budget state */
  budget: TokenBudgetState;
  /** Slot usage details */
  slotUsage: SlotUsage[];
  /** Compression events */
  compressionEvents: CompressionEvent[];
}

/**
 * SSE event type for context window updates
 */
export interface ContextWindowEvent {
  type: 'context_window';
  data: ContextWindowData;
}

/**
 * Slot color mapping for visualization
 */
export const SLOT_COLORS: Record<keyof SlotAllocation, string> = {
  system: '#5E6AD2',          // Primary - blue
  active_skill: '#8B5CF6',    // Purple - skill activation
  few_shot: '#06B6D4',        // Cyan - examples
  rag: '#10B981',             // Green - knowledge
  episodic: '#F59E0B',        // Orange - user memory
  procedural: '#EF4444',      // Red - patterns
  tools: '#3B82F6',           // Blue - tool schemas
  history: '#6366F1',         // Indigo - conversation
  output_format: '#EC4899',   // Pink - format
  user_input: '#22C55E',      // Green - user input
} as const;

/**
 * Slot display names in Chinese
 */
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
