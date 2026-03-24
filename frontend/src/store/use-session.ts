/**
 * Session Store using Zustand.
 *
 * P0: Basic chat state management.
 * P1: Context Window state management.
 */
import { create } from 'zustand';

import type { ContextWindowData, StateMessage } from '@/types/context-window';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
import type { TraceEvent } from '@/types/trace';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  tool_calls?: ToolCall[];
}

export interface ToolCall {
  id: string;
  tool_name: string;
  args: Record<string, unknown>;
  result?: string;
  status: 'pending' | 'running' | 'completed' | 'error';
}

export interface SessionState {
  // Messages
  messages: Message[];

  // Token usage
  tokenUsed: number;
  tokenBudget: number;

  // Context Window
  contextWindowData: ContextWindowData;
  slotDetails: Array<{
    name: string;
    display_name: string;
    content: string;
    tokens: number;
    enabled: boolean;
  }>;

  // Turn tracking
  currentTurnId: string | null;
  turnCounter: number;

  // Backend state messages
  stateMessages: StateMessage[];

  // Detailed execution trace
  traceEvents: TraceEvent[];

  // Current session
  sessionId: string;
  userId: string;

  // UI state
  isLoading: boolean;
  error: string | null;

  // Actions
  addMessage: (message: Omit<Message, 'id' | 'timestamp'>) => void;
  updateToolCall: (messageId: string, toolCallId: string, update: Partial<ToolCall>) => void;
  setTokenUsed: (used: number) => void;
  setContextWindowData: (data: ContextWindowData) => void;
  setSlotDetails: (
    slots: Array<{
      name: string;
      display_name: string;
      content: string;
      tokens: number;
      enabled: boolean;
    }>
  ) => void;
  incrementTurn: () => void;
  setStateMessages: (msgs: StateMessage[]) => void;
  addTraceEvent: (event: TraceEvent) => void;
  clearTraceEvents: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setSessionId: (sessionId: string) => void;
  clearMessages: () => void;
}

export const useSession = create<SessionState>((set, _get) => ({
  // Initial state
  messages: [],
  tokenUsed: 0,
  tokenBudget: 32000,
  contextWindowData: EMPTY_CONTEXT_DATA,
  slotDetails: [],
  currentTurnId: null,
  turnCounter: 0,
  stateMessages: [],
  traceEvents: [],
  sessionId: `session_${Date.now()}`,
  userId: 'dev_user',
  isLoading: false,
  error: null,

  // Actions
  addMessage: (message) => {
    const newMessage: Message = {
      ...message,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: Date.now(),
    };
    set((state) => ({
      messages: [...state.messages, newMessage],
    }));
  },

  updateToolCall: (messageId, toolCallId, update) => {
    set((state) => ({
      messages: state.messages.map((msg) => {
        if (msg.id === messageId && msg.tool_calls) {
          return {
            ...msg,
            tool_calls: msg.tool_calls.map((tc) =>
              tc.id === toolCallId ? { ...tc, ...update } : tc
            ),
          };
        }
        return msg;
      }),
    }));
  },

  setTokenUsed: (used) => set({ tokenUsed: used }),

  setContextWindowData: (data) => set({ contextWindowData: data }),

  setSlotDetails: (slots) => set({ slotDetails: slots }),

  incrementTurn: () => {
    set((state) => {
      const turnCounter = state.turnCounter + 1;
      return { turnCounter, currentTurnId: `turn_${turnCounter}` };
    });
  },

  setStateMessages: (msgs) => set({ stateMessages: msgs }),

  addTraceEvent: (event) => {
    set((state) => ({
      // keep only latest 500 to avoid unbounded growth
      traceEvents: [
        ...state.traceEvents,
        { ...event, turnId: state.currentTurnId ?? undefined },
      ].slice(-500),
    }));
  },

  clearTraceEvents: () => set({ traceEvents: [] }),

  setLoading: (loading) => set({ isLoading: loading }),

  setError: (error) => set({ error }),

  setSessionId: (sessionId) => set({ sessionId }),

  clearMessages: () =>
    set({
      messages: [],
      stateMessages: [],
      traceEvents: [],
      tokenUsed: 0,
      contextWindowData: EMPTY_CONTEXT_DATA,
      slotDetails: [],
      currentTurnId: null,
      turnCounter: 0,
    }),
}));
