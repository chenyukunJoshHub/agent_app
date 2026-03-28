/**
 * useSSEHandlers — registers all SSE event handlers on sseManager (once).
 *
 * Extracted from page.tsx to keep the page component focused on layout.
 */
'use client';

import { useRef, useCallback } from 'react';
import { sseManager } from '@/lib/sse-manager';
import { getChatStreamUrl } from '@/lib/api-config';
import { useSession } from '@/store/use-session';
import { EMPTY_CONTEXT_DATA } from '@/types/context-window';
import type { SessionMeta, SlotDetailsResponse, StateMessage } from '@/types/context-window';
import type { TraceEvent } from '@/types/trace';
import type { TraceBlock } from '@/types/trace';

// ---------------------------------------------------------------------------
// Type guards (kept local — only used here and in page.tsx's consumeSSEStream)
// ---------------------------------------------------------------------------

export function isTraceEvent(data: unknown): data is TraceEvent {
  if (typeof data !== 'object' || data === null) return false;
  const r = data as Record<string, unknown>;
  return (
    typeof r.id === 'string' &&
    typeof r.timestamp === 'string' &&
    typeof r.stage === 'string' &&
    typeof r.step === 'string' &&
    typeof r.status === 'string' &&
    typeof r.payload === 'object' &&
    r.payload !== null
  );
}

export function isTraceBlock(data: unknown): data is TraceBlock {
  if (typeof data !== 'object' || data === null) return false;
  const r = data as Record<string, unknown>;
  return (
    typeof r.id === 'string' &&
    typeof r.timestamp === 'string' &&
    typeof r.type === 'string' &&
    typeof r.status === 'string' &&
    typeof r.duration_ms === 'number'
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface InterruptData {
  interrupt_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  risk_level: 'high' | 'medium' | 'low';
  message: string;
}

interface UseSSEHandlersOptions {
  onHILInterrupt?: (data: InterruptData) => void;
  setTurnStatus?: (turnId: string, status: 'done' | 'error') => void;
  setLastActivityTime?: (t: number) => void;
}

export function useSSEHandlers(options: UseSSEHandlersOptions = {}) {
  const {
    onHILInterrupt,
    setTurnStatus = () => {},
    setLastActivityTime = () => {},
  } = options;

  const registered = useRef(false);
  const loadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const streamTerminalReasonRef = useRef<'done' | 'hil_interrupt' | 'error' | 'timeout' | null>(null);

  const clearLoadTimeout = useCallback(() => {
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = null;
    }
  }, []);

  /** Register handlers on sseManager — safe to call repeatedly, only registers once. */
  const ensureRegistered = useCallback(() => {
    if (registered.current) return;
    registered.current = true;

    const store = useSession;

    sseManager.onStateChange((state) => {
      if (state === 'error' && streamTerminalReasonRef.current === null) {
        console.warn('[SSE] connection entered error state before terminal event');
        return;
      }
      if (state !== 'disconnected') return;

      const reason = streamTerminalReasonRef.current;
      if (reason === 'done') {
        console.warn('[SSE] stream ended normally (done)');
      } else if (reason === 'hil_interrupt') {
        console.warn('[SSE] stream ended for HIL interrupt, waiting for resume');
      } else if (reason === 'error') {
        console.warn('[SSE] stream ended due to error event');
      } else if (reason === 'timeout') {
        console.warn('[SSE] stream ended due to client timeout');
      }
      streamTerminalReasonRef.current = null;
    });

    sseManager.on('trace_event', ({ data }) => {
      if (isTraceEvent(data)) store.getState().addTraceEvent(data);
    });

    sseManager.on('trace_block', ({ data }) => {
      if (isTraceBlock(data)) store.getState().addTraceBlock(data);
    });

    sseManager.on('slot_details', ({ data }) => {
      const payload = data as SlotDetailsResponse;
      if (payload.slots) store.getState().setSlotDetails(payload.slots);
    });

    sseManager.on('context_window', ({ data }) => {
      store.getState().setContextWindowData(data as any);
    });

    sseManager.on('compression', ({ data }) => {
      const payload = data as {
        before_tokens?: number;
        after_tokens?: number;
        method?: 'summarization' | 'truncation' | 'hybrid';
        affected_slots?: string[];
        summary_text?: string;
      };

      const beforeTokens = Number(payload.before_tokens ?? 0);
      const afterTokens = Number(payload.after_tokens ?? 0);
      const method =
        payload.method === 'truncation' || payload.method === 'hybrid'
          ? payload.method
          : 'summarization';
      const affectedSlots = Array.isArray(payload.affected_slots)
        ? payload.affected_slots.map((slot) => String(slot))
        : ['history'];
      const summaryText = typeof payload.summary_text === 'string' ? payload.summary_text : undefined;

      const contextData = store.getState().contextWindowData;
      const event = {
        id: `compression_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
        timestamp: Date.now(),
        before_tokens: beforeTokens,
        after_tokens: afterTokens,
        tokens_saved: Math.max(0, beforeTokens - afterTokens),
        method,
        affected_slots: affectedSlots,
        ...(summaryText ? { summary_text: summaryText } : {}),
      };

      store.getState().setContextWindowData({
        ...contextData,
        compressionEvents: [event, ...contextData.compressionEvents],
      });
    });

    sseManager.on('slot_update', ({ data }) => {
      const updated = data as {
        name: string;
        display_name: string;
        tokens: number;
        enabled: boolean;
        content?: string;
      };
      const currentSlots = store.getState().slotDetails;
      const oldTokens = currentSlots.find((s) => s.name === updated.name)?.tokens ?? 0;
      const merged = currentSlots.filter((s) => s.name !== updated.name);
      merged.push({ ...updated, content: updated.content ?? '' });
      store.getState().setSlotDetails(merged);

      const ctx = store.getState().contextWindowData;
      if (ctx) {
        const delta = updated.tokens - oldTokens;
        const updatedSlotUsage = ctx.slotUsage.map((s) =>
          s.name === updated.name ? { ...s, used: updated.tokens } : s,
        );
        store.getState().setContextWindowData({
          ...ctx,
          slotUsage: updatedSlotUsage,
          budget: {
            ...ctx.budget,
            usage: {
              ...ctx.budget.usage,
              total_used: ctx.budget.usage.total_used + delta,
              total_remaining: Math.max(0, ctx.budget.usage.total_remaining - delta),
            },
          },
        });
      }
    });

    sseManager.on('session_metadata', ({ data }) => {
      store.getState().setSessionMeta(data as SessionMeta);
    });

    sseManager.on('thought', ({ data }) => {
      const { content } = data as { content: string };
      const sessionState = store.getState();
      const lastMsg = sessionState.messages[sessionState.messages.length - 1];

      if (lastMsg && lastMsg.role === 'assistant') {
        const text = lastMsg.content ? `${lastMsg.content}${content}` : content;
        store.setState({
          messages: [...sessionState.messages.slice(0, -1), { ...lastMsg, content: text }],
        });
      } else {
        store.getState().addMessage({ role: 'assistant', content });
      }
    });

    sseManager.on('token_update', ({ data }) => {
      const { current } = data as { current: number; budget: number };
      const ctx = store.getState().contextWindowData;
      if (ctx) {
        const remaining = Math.max(0, ctx.budget.working_budget - current);
        store.setState({
          contextWindowData: {
            ...ctx,
            budget: {
              ...ctx.budget,
              usage: {
                ...ctx.budget.usage,
                total_used: current,
                total_remaining: remaining,
              },
            },
          },
        });
      }
    });

    sseManager.on('hil_interrupt', ({ data }) => {
      const interruptData = data as InterruptData;
      streamTerminalReasonRef.current = 'hil_interrupt';
      clearLoadTimeout();
      store.getState().setLoading(false);
      onHILInterrupt?.(interruptData);
      sseManager.disconnect();
    });

    sseManager.on('done', ({ data }) => {
      streamTerminalReasonRef.current = 'done';
      clearLoadTimeout();

      const payload = data as { messages?: StateMessage[]; answer?: string };
      if (payload.messages && payload.messages.length > 0) {
        const frontendMsgs = store.getState().messages;
        if (payload.messages.length >= frontendMsgs.length) {
          store.getState().setStateMessages(payload.messages);
        }
      }

      if (payload.answer) {
        const frontendMsgs = store.getState().messages;
        const lastMsg = frontendMsgs[frontendMsgs.length - 1];
        if (!lastMsg || lastMsg.role !== 'assistant') {
          store.getState().addMessage({ role: 'assistant', content: payload.answer });
        }
      }

      const turnId = store.getState().currentTurnId;
      if (turnId) setTurnStatus(turnId, 'done');

      setLastActivityTime(Date.now());
      store.getState().setLoading(false);
      sseManager.disconnect();
    });

    sseManager.on('error', ({ data }) => {
      const { message } = data as { message: string };
      streamTerminalReasonRef.current = 'error';

      const turnId = store.getState().currentTurnId;
      if (turnId) setTurnStatus(turnId, 'error');

      clearLoadTimeout();
      store.getState().setError(message);
      store.getState().setLoading(false);
      sseManager.disconnect();
    });

    sseManager.on('skill_invoked', ({ data }) => {
      const { skill_id, description } = data as { skill_id: string; description: string };
      const currentSlots = store.getState().slotDetails;
      const updated = currentSlots.map((s) =>
        s.name === 'skill_registry'
          ? { ...s, content: `[手动激活] ${skill_id}: ${description}` }
          : s,
      );
      store.getState().setSlotDetails(updated);
    });
  }, [clearLoadTimeout, onHILInterrupt, setTurnStatus, setLastActivityTime]);

  /**
   * Send a chat message: mutates store, connects SSE, starts timeout.
   */
  const handleSendMessage = useCallback(
    async (message: string, skillId?: string | null, mode?: string | null) => {
      const store = useSession;
      store.getState().addMessage({ role: 'user', content: message });
      store.getState().incrementTurn();
      store.getState().setContextWindowData(EMPTY_CONTEXT_DATA);
      store.getState().setSlotDetails([]);
      store.getState().setStateMessages([]);
      store.getState().setSessionMeta(null);
      store.getState().setLoading(true);
      store.getState().setError(null);

      try {
        const sessionId = store.getState().sessionId;
        const userId = store.getState().userId;

        sseManager.connect(getChatStreamUrl(), {
          message,
          session_id: sessionId,
          user_id: userId,
          ...(skillId ? { skill_id: skillId } : {}),
          ...(mode ? { invocation_mode: mode } : {}),
        });

        clearLoadTimeout();
        loadTimeoutRef.current = setTimeout(() => {
          streamTerminalReasonRef.current = 'timeout';
          store.getState().setError('请求超时，请检查后端与 LLM（如 Ollama）是否可用');
          store.getState().setLoading(false);
          sseManager.disconnect();
          loadTimeoutRef.current = null;
        }, 120_000);

        ensureRegistered();
        streamTerminalReasonRef.current = null;
      } catch (error) {
        clearLoadTimeout();
        store.getState().setError(error instanceof Error ? error.message : '发送消息失败');
        store.getState().setLoading(false);
      }
    },
    [clearLoadTimeout, ensureRegistered],
  );

  return { handleSendMessage };
}
