'use client';

import { useRef, useState } from 'react';

import { motion } from 'framer-motion';
import { Activity, Bot, Clock, History, Layers, Wrench } from 'lucide-react';

import { ChatInput } from '@/components/ChatInput';
import { ConfirmModal } from '@/components/ConfirmModal';
import { ContextWindowPanel } from '@/components/ContextWindowPanel';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import { MessageList } from '@/components/MessageList';
import { Timeline } from '@/components/Timeline';
import { TokenBar } from '@/components/TokenBar';
import { ToolCallTrace } from '@/components/ToolCallTrace';
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
    timelineEvents,
    traceEvents,
    slotDetails,
    contextWindowData,
    tokenUsed,
    tokenBudget,
    addMessage,
    addTimelineEvent,
    addTraceEvent,
    setTokenUsed,
    setContextWindowData,
    setSlotDetails,
    setLoading,
    setError,
  } = useSession();

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [currentInterrupt, setCurrentInterrupt] = useState<InterruptData | null>(null);
  const [activeTab, setActiveTab] = useState<'chain' | 'timeline' | 'tools' | 'context'>('chain');
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
      tool_calls: [],
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
          addTimelineEvent({
            type: 'thought',
            content,
          });

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

        sseManager.on('tool_start', ({ data }) => {
          const { tool_name, args } = data as {
            tool_name: string;
            args: Record<string, unknown>;
          };
          addTimelineEvent({
            type: 'tool_start',
            content: `调用工具 ${tool_name}`,
            toolName: tool_name,
          });

          const sessionState = useSession.getState();
          const lastMsg = sessionState.messages[sessionState.messages.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            const newToolCall = {
              id: `tc_${Date.now()}`,
              tool_name,
              args,
              status: 'running' as const,
            };
            useSession.setState({
              messages: [
                ...sessionState.messages.slice(0, -1),
                {
                  ...lastMsg,
                  tool_calls: [...(lastMsg.tool_calls || []), newToolCall],
                },
              ],
            });
          }
        });

        sseManager.on('tool_result', ({ data }) => {
          addTimelineEvent({
            type: 'tool_result',
            content: '工具执行完成',
          });

          const sessionState = useSession.getState();
          const lastMsg = sessionState.messages[sessionState.messages.length - 1];
          if (lastMsg && lastMsg.tool_calls && lastMsg.tool_calls.length > 0) {
            const lastToolCall = lastMsg.tool_calls[lastMsg.tool_calls.length - 1];
            useSession.setState({
              messages: [
                ...sessionState.messages.slice(0, -1),
                {
                  ...lastMsg,
                  tool_calls: [
                    ...lastMsg.tool_calls.slice(0, -1),
                    {
                      ...lastToolCall,
                      status: 'completed' as const,
                      result: JSON.stringify(data),
                    },
                  ],
                },
              ],
            });
          }
        });

        sseManager.on('token_update', ({ data }) => {
          const { current, budget } = data as {
            current: number;
            budget: number;
          };

          setTokenUsed(current);
          if (budget) {
            useSession.setState({ tokenBudget: budget });
          }

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
          addTimelineEvent({
            type: 'hil_interrupt',
            content: `人工介入：${interruptData.tool_name}`,
            toolName: interruptData.tool_name,
          });

          clearLoadTimeout();
          setLoading(false);
          setCurrentInterrupt(interruptData);
          setShowConfirmModal(true);
          sseManager.disconnect();
        });

        sseManager.on('done', ({ data }) => {
          const { answer, token_usage } = data as {
            answer?: string;
            token_usage?: { total: number };
          };

          addTimelineEvent({
            type: 'done',
            content: answer || '任务完成',
          });

          if (token_usage?.total) {
            setTokenUsed(token_usage.total);
          }

          clearLoadTimeout();
          setLoading(false);
          sseManager.disconnect();
        });

        sseManager.on('error', ({ data }) => {
          const { message } = data as { message: string };
          addTimelineEvent({
            type: 'error',
            content: message,
          });

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
          addTimelineEvent({
            type: 'tool_result',
            content: `HIL 执行结果：${String((data as any).tool_name || '')}`,
          });
          return;
        }

        if (event === 'done') {
          addTimelineEvent({
            type: 'done',
            content: String((data as any).answer || '操作已完成'),
          });
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
          addTimelineEvent({
            type: 'done',
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
          <div className="flex items-center gap-4">
            <TokenBar current={tokenUsed} budget={tokenBudget} />
            <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-muted px-3 py-1.5">
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="h-2 w-2 rounded-full bg-accent"
              />
              <span className="text-xs font-medium text-text-secondary" data-testid="connection-status">
                已连接
              </span>
            </div>
          </div>
        </div>
      </motion.header>

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-72 border-r border-border bg-bg-alt">
          <div className="p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
              会话列表
            </h2>
            <div className="space-y-2">
              <motion.button
                whileHover={{ scale: 1.02, x: 4 }}
                whileTap={{ scale: 0.98 }}
                className="w-full rounded-xl border border-border bg-bg-card p-4 text-left shadow-sm transition-all hover:border-border-strong hover:shadow-md"
              >
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                  <div className="font-medium text-sm text-text-primary">当前会话</div>
                </div>
                <div className="mt-2 text-xs text-text-muted flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  刚刚
                </div>
              </motion.button>
            </div>
          </div>
        </aside>

        <section className="flex flex-1 flex-col bg-bg-base">
          <MessageList messages={messages} isLoading={isLoading} />
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
        </section>

        <aside className="flex w-[440px] flex-col border-l border-border bg-bg-card">
          <div className="grid grid-cols-4 border-b border-border bg-bg-alt">
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
              onClick={() => setActiveTab('timeline')}
              className={cn(
                'relative flex items-center justify-center gap-1 px-2 py-3 text-xs font-medium transition-all duration-200',
                activeTab === 'timeline' ? 'text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              <History className="w-4 h-4" />
              时间轴
              {activeTab === 'timeline' && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
            <button
              onClick={() => setActiveTab('tools')}
              className={cn(
                'relative flex items-center justify-center gap-1 px-2 py-3 text-xs font-medium transition-all duration-200',
                activeTab === 'tools' ? 'text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              <Wrench className="w-4 h-4" />
              工具
              {activeTab === 'tools' && (
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
              {activeTab === 'timeline' && <Timeline events={timelineEvents} />}
              {activeTab === 'tools' && <ToolCallTrace messages={messages} />}
              {activeTab === 'context' &&
                (contextWindowData ? (
                  <ContextWindowPanel data={contextWindowData} />
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
