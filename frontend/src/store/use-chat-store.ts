/**
 * Chat state management with Zustand
 */

import { create } from 'zustand';
import { SSEManager } from '@/lib/sse';
import type { ChatMessage, Session, TimelineEvent } from '@/types';

interface ChatState {
  // Current session
  currentSession: Session | null;
  sessions: Session[];

  // Messages
  messages: ChatMessage[];

  // Timeline events
  timelineEvents: TimelineEvent[];

  // Connection state
  isConnected: boolean;
  isProcessing: boolean;

  // Actions
  setCurrentSession: (session: Session | null) => void;
  setSessions: (sessions: Session[]) => void;
  addMessage: (message: ChatMessage) => void;
  addTimelineEvent: (event: TimelineEvent) => void;
  clearTimeline: () => void;
  sendMessage: (message: string) => Promise<void>;
  disconnect: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  currentSession: null,
  sessions: [],
  messages: [],
  timelineEvents: [],
  isConnected: false,
  isProcessing: false,

  // Actions
  setCurrentSession: (session) => set({ currentSession: session }),

  setSessions: (sessions) => set({ sessions }),

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),

  addTimelineEvent: (event) =>
    set((state) => ({ timelineEvents: [...state.timelineEvents, event] })),

  clearTimeline: () => set({ timelineEvents: [] }),

  sendMessage: async (message: string) => {
    const { currentSession, isConnected, isProcessing } = get();

    if (isProcessing) {
      console.warn('Already processing a message');
      return;
    }

    set({ isProcessing: true, timelineEvents: [] });

    // Add user message
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: message,
      created_at: new Date().toISOString(),
    };
    get().addMessage(userMessage);

    // Create SSE manager
    const sse = new SSEManager('http://localhost:8000/api/chat/stream', {
      onMessage: (msg) => {
        const event: TimelineEvent = {
          id: crypto.randomUUID(),
          type: msg.type as TimelineEvent['type'],
          data: msg.data as Record<string, unknown>,
          timestamp: new Date().toISOString(),
        };
        get().addTimelineEvent(event);

        // Handle final response
        if (msg.type === 'response') {
          const data = msg.data as { content: string; tokens_used: number };
          const assistantMessage: ChatMessage = {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: data.content,
            tokens_used: data.tokens_used,
            created_at: new Date().toISOString(),
          };
          get().addMessage(assistantMessage);
          set({ isProcessing: false });
        }

        // Handle error
        if (msg.type === 'error') {
          set({ isProcessing: false });
        }
      },

      onError: (error) => {
        console.error('SSE error:', error);
        set({ isProcessing: false, isConnected: false });
      },

      onClose: () => {
        set({ isConnected: false, isProcessing: false });
      },

      reconnectInterval: 1000,
      maxReconnectAttempts: 3,
    });

    set({ isConnected: true });

    try {
      await sse.connect(message, currentSession?.id);
    } catch (error) {
      console.error('Failed to connect:', error);
      set({ isProcessing: false, isConnected: false });
    }
  },

  disconnect: () => {
    set({ isConnected: false, isProcessing: false });
  },
}));
