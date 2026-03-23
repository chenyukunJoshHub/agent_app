'use client';

import { useRef, useState } from 'react';

import { motion } from 'framer-motion';
import { Activity, Bot, Layers } from 'lucide-react';

import { ChatInput } from '@/components/ChatInput';
import { ConfirmModal } from '@/components/ConfirmModal';
import { ContextWindowPanel } from '@/components/ContextWindowPanel';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import { MessageList } from '@/components/MessageList';
import { getChatResumeUrl, getChatStreamUrl } from '@/lib/api-config';
import { sseManager } from '@/lib/sse-manager';
import { cn } from '@/lib/utils';
import { useSession } from '@/store/use-session';
import type { SlotDetailsResponse } from '@/types/context-window';
import type { TraceEvent } from '@/types/trace';

interface InterruptData {
  interrupt_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  risk_level: 'high' | 'medium' | 'low';
  message: string;
}

interface ParsedSSEEvent {
  event: string;
  data: Record<string, unknown>;
}

function isTraceEvent(data: unknown): data is TraceEvent {
  if (typeof data !== 'object' || data === null) {
    return false;
  }
  const record = data as Record<string, unknown>;
  return (
    typeof record.id === 'string' &&
    typeof record.timestamp === 'string' &&
    typeof record.stage === 'string' &&
    typeof record.step === 'string' &&
    typeof record.status === 'string' &&
    typeof record.payload === 'object' &&
    record.payload !== null
  );
}

async function consumeSSEStream(
  response: Response,
  onEvent: (evt: ParsedSSEEvent) => void
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split('\n\n');
    buffer = blocks.pop() || '';

    for (const block of blocks) {
      const lines = block.split('\n');
      let eventName = 'message';
      let dataLine = '';

      for (const line of lines) {
        if (line.startsWith('event: ')) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith('data: ')) {
          dataLine += line.slice(6);
        }
      }

      if (!dataLine) continue;

      try {
        const data = JSON.parse(dataLine);
        onEvent({ event: eventName, data });
      } catch {
        // ignore malformed payload chunks
      }
    }
  }
}

export default function HomePage() {
  const {
    messages,
    isLoading,
    traceEvents,
    slotDetails,
    contextWindowData,
    addMessage,
    addTraceEvent,
    setContextWindowData,
    setSlotDetails,
    setLoading,
    setError,
  } = useSession();

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [currentInterrupt, setCurrentInterrupt] = useState<InterruptData | null>(null);
  const [activeTab, setActiveTab] = useState<'chain' | 'context'>('chain');
  const sseHandlersRegistered = useRef(false);
  const loadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearLoadTimeout = () => {
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = null;
    }
  };

  const handleSendMessage = async (message: string) => {
    addMessage({ role: 'user', content: message });
    addMessage({
      role: 'assistant',
      content: '',
    });

    setLoading(true);
    setError(null);

    try {
      const sessionId = useSession.getState().sessionId;
      const userId = useSession.getState().userId;

      sseManager.connect(getChatStreamUrl(), {
        message,
        session_id: sessionId,
        user_id: userId,
      });

      clearLoadTimeout();
      loadTimeoutRef.current = setTimeout(() => {
        setError('请求超时，请检查后端与 LLM（如 Ollama）是否可用');
        setLoading(false);
        sseManager.disconnect();
        loadTimeoutRef.current = null;
      }, 120_000);

      if (!sseHandlersRegistered.current) {
        sseHandlersRegistered.current = true;

        sseManager.on('trace_event', ({ data }) => {
          if (isTraceEvent(data)) {
            addTraceEvent(data);
          }
        });

        sseManager.on('slot_details', ({ data }) => {
          const payload = data as SlotDetailsResponse;
          if (payload.slots) {
            setSlotDetails(payload.slots);
          }
        });

        sseManager.on('context_window', ({ data }) => {
          setContextWindowData(data as any);
        });

        sseManager.on('thought', ({ data }) => {
          const { content } = data as { content: string };

          const sessionState = useSession.getState();
          const lastMsg = sessionState.messages[sessionState.messages.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            const text = lastMsg.content ? `${lastMsg.content}\n${content}` : content;
            const updatedMsg = { ...lastMsg, content: text };
            useSession.setState({
              messages: [...sessionState.messages.slice(0, -1), updatedMsg],
            });
          }
        });

        sseManager.on('token_update', ({ data }) => {
          const { current, budget } = data as {
            current: number;
            budget: number;
          };

          const ctx = useSession.getState().contextWindowData;
          if (ctx) {
            const remaining = Math.max(0, ctx.budget.working_budget - current);
            useSession.setState({
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

          clearLoadTimeout();
          setLoading(false);
          setCurrentInterrupt(interruptData);
          setShowConfirmModal(true);
          sseManager.disconnect();
        });

        sseManager.on('done', () => {
          clearLoadTimeout();
          setLoading(false);
          sseManager.disconnect();
        });

        sseManager.on('error', ({ data }) => {
          const { message } = data as { message: string };

          clearLoadTimeout();
          setError(message);
          setLoading(false);
          sseManager.disconnect();
        });
      }
    } catch (error) {
      clearLoadTimeout();
      setError(error instanceof Error ? error.message : '发送消息失败');
      setLoading(false);
    }
  };

  const handleConfirm = async (interruptId: string) => {
    setShowConfirmModal(false);
    setCurrentInterrupt(null);
    setLoading(true);

    try {
      const response = await fetch(getChatResumeUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: useSession.getState().sessionId,
          user_id: useSession.getState().userId,
          interrupt_id: interruptId,
          approved: true,
        }),
      });

      await consumeSSEStream(response, ({ event, data }) => {
        if (event === 'trace_event') {
          if (isTraceEvent(data)) {
            addTraceEvent(data);
          }
          return;
        }

        if (event === 'tool_result') {
          return;
        }

        if (event === 'done') {
          setLoading(false);
        }
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : '确认操作失败');
      setLoading(false);
    }
  };

  const handleCancel = async (interruptId: string) => {
    setShowConfirmModal(false);
    setCurrentInterrupt(null);
    setLoading(true);

    try {
      const response = await fetch(getChatResumeUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: useSession.getState().sessionId,
          user_id: useSession.getState().userId,
          interrupt_id: interruptId,
          approved: false,
        }),
      });

      await consumeSSEStream(response, ({ event, data }) => {
        if (event === 'trace_event') {
          if (isTraceEvent(data)) {
            addTraceEvent(data);
          }
          return;
        }

        if (event === 'done') {
          addMessage({
            role: 'assistant',
            content: String((data as any).answer || '操作已取消'),
          });
          setLoading(false);
        }
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : '取消操作失败');
      setLoading(false);
    }
  };

  return (
    <main className="flex h-screen flex-col bg-bg-base text-text-primary">
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="border-b border-border bg-bg-card px-6 py-4 shadow-sm"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-secondary shadow-lg">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Multi-Tool AI Agent</h1>
              <p className="text-xs text-text-muted">初始化 → Context → ReAct → Memory 全链路可视化</p>
            </div>
          </div>
        </div>
      </motion.header>

      <div className="flex flex-1 overflow-hidden">
        <section className="flex flex-1 flex-col bg-bg-base">
          <MessageList messages={messages} isLoading={isLoading} />
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
        </section>

        <aside className="flex w-[440px] flex-col border-l border-border bg-bg-card">
          <div className="grid grid-cols-2 border-b border-border bg-bg-alt">
            <button
              onClick={() => setActiveTab('chain')}
              className={cn(
                'relative flex items-center justify-center gap-1 px-2 py-3 text-xs font-medium transition-all duration-200',
                activeTab === 'chain' ? 'text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              <Activity className="w-4 h-4" />
              链路
              {activeTab === 'chain' && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
            <button
              onClick={() => setActiveTab('context')}
              className={cn(
                'relative flex items-center justify-center gap-1 px-2 py-3 text-xs font-medium transition-all duration-200',
                activeTab === 'context' ? 'text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              <Layers className="w-4 h-4" />
              Context
              {activeTab === 'context' && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          </div>

          <div className="flex-1 overflow-hidden">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              {activeTab === 'chain' && (
                <ExecutionTracePanel traceEvents={traceEvents} slotDetails={slotDetails} />
              )}
              {activeTab === 'context' &&
                (contextWindowData ? (
                  <ContextWindowPanel data={contextWindowData} slotDetails={slotDetails} />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-text-muted">
                    暂无 Context 数据，请先发起一次请求
                  </div>
                ))}
            </motion.div>
          </div>
        </aside>
      </div>

      <ConfirmModal
        isOpen={showConfirmModal}
        interrupt={currentInterrupt}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </main>
  );
}
