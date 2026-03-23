'use client';

import { useRef, useState } from 'react';

import { motion } from 'framer-motion';
import { Bot, Clock, Wrench, History } from 'lucide-react';

import { ChatInput } from '@/components/ChatInput';
import { ConfirmModal } from '@/components/ConfirmModal';
import { MessageList } from '@/components/MessageList';
import { ToolCallTrace } from '@/components/ToolCallTrace';
import { Timeline } from '@/components/Timeline';
import { TokenBar } from '@/components/TokenBar';
import { cn } from '@/lib/utils';
import { getChatResumeUrl, getChatStreamUrl } from '@/lib/api-config';
import { sseManager } from '@/lib/sse-manager';
import { useSession } from '@/store/use-session';

interface InterruptData {
  interrupt_id: string;
  tool_name: string;
  tool_args: Record<string, unknown>;
  risk_level: 'high' | 'medium' | 'low';
  message: string;
}

export default function HomePage() {
  const {
    messages,
    isLoading,
    timelineEvents,
    tokenUsed,
    tokenBudget,
    addMessage,
    addTimelineEvent,
    setTokenUsed,
    setLoading,
    setError,
  } = useSession();
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [currentInterrupt, setCurrentInterrupt] = useState<InterruptData | null>(null);
  const [activeTab, setActiveTab] = useState<'trace' | 'timeline'>('trace');
  /** Register SSE handlers once — repeating `sseManager.on()` stacks listeners and breaks multi-turn chat. */
  const sseHandlersRegistered = useRef(false);
  const loadTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearLoadTimeout = () => {
    if (loadTimeoutRef.current) {
      clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = null;
    }
  };

  const handleSendMessage = async (message: string) => {
    // Add user message
    addMessage({ role: 'user', content: message });

    // Add placeholder for assistant response
    addMessage({
      role: 'assistant',
      content: '',
      tool_calls: [],
    });

    setLoading(true);
    setError(null);

    try {
      // Connect SSE
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

        // Set up event handlers (once per page lifetime)
        sseManager.on('thought', ({ data }) => {
          const { content } = data as { content: string };

          // Add timeline event
          addTimelineEvent({
            type: 'thought',
            content,
          });

          // Append thought to assistant message
          const messages = useSession.getState().messages;
          const lastMsg = messages[messages.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            const updatedMsg = {
              ...lastMsg,
              content: lastMsg.content + '\n' + content,
            };
            useSession.setState({
              messages: [...messages.slice(0, -1), updatedMsg],
            });
          }
        });

        sseManager.on('tool_start', ({ data }) => {
          const { tool_name, args } = data as {
            tool_name: string;
            args: Record<string, unknown>;
          };

          // Add timeline event
          addTimelineEvent({
            type: 'tool_start',
            content: `调用工具 ${tool_name}`,
            toolName: tool_name,
          });

          // Add tool call to current assistant message
          const messages = useSession.getState().messages;
          const lastMsg = messages[messages.length - 1];
          if (lastMsg && lastMsg.role === 'assistant') {
            const newToolCall = {
              id: `tc_${Date.now()}`,
              tool_name,
              args,
              status: 'running' as const,
            };
            useSession.setState({
              messages: [
                ...messages.slice(0, -1),
                {
                  ...lastMsg,
                  tool_calls: [...(lastMsg.tool_calls || []), newToolCall],
                },
              ],
            });
          }
        });

        sseManager.on('tool_result', ({ data }) => {
          // Add timeline event
          addTimelineEvent({
            type: 'tool_result',
            content: '工具执行完成',
          });

          // Update tool call with result
          const messages = useSession.getState().messages;
          const lastMsg = messages[messages.length - 1];
          if (lastMsg && lastMsg.tool_calls) {
            const lastToolCall = lastMsg.tool_calls[lastMsg.tool_calls.length - 1];
            useSession.setState({
              messages: [
                ...messages.slice(0, -1),
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

          // Update token usage in real-time
          setTokenUsed(current);
          if (budget) {
            useSession.setState({ tokenBudget: budget });
          }
        });

        sseManager.on('hil_interrupt', ({ data }) => {
          const interruptData = data as InterruptData;

          // Add timeline event
          addTimelineEvent({
            type: 'hil_interrupt',
            content: `人工介入：${interruptData.tool_name}`,
            toolName: interruptData.tool_name,
          });

          // Show confirm modal
          clearLoadTimeout();
          setLoading(false);
          setCurrentInterrupt(interruptData);
          setShowConfirmModal(true);

          // Pause SSE connection
          sseManager.disconnect();
        });

        sseManager.on('done', ({ data }) => {
          const { answer, token_usage } = data as {
            answer?: string;
            token_usage?: { total: number };
          };

          // Add timeline event
          addTimelineEvent({
            type: 'done',
            content: answer || '任务完成',
          });

          // Update token usage
          if (token_usage?.total) {
            setTokenUsed(token_usage.total);
          }

          clearLoadTimeout();
          setLoading(false);
          sseManager.disconnect();
        });

        sseManager.on('error', ({ data }) => {
          const { message } = data as { message: string };

          // Add timeline event
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
      console.error('Send message error:', error);
      clearLoadTimeout();
      setError(error instanceof Error ? error.message : '发送消息失败');
      setLoading(false);
    }
  };

  const handleConfirm = async (interruptId: string) => {
    setShowConfirmModal(false);
    setCurrentInterrupt(null);

    try {
      // Call /chat/resume endpoint
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

      // Handle resume response as SSE stream
      const reader = response.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder();
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value);
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = JSON.parse(line.slice(6));
              // Handle SSE events (hil_resolved, tool_result, done, etc.)
              if (data.event === 'hil_resolved') {
                // HIL resolved successfully
              } else if (data.event === 'done') {
                setLoading(false);
                sseManager.disconnect();
              } else if (data.event === 'error') {
                setError(data.data.message);
                setLoading(false);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Confirm error:', error);
      setError(error instanceof Error ? error.message : '确认操作失败');
      setLoading(false);
    }
  };

  const handleCancel = (interruptId: string) => {
    setShowConfirmModal(false);
    setCurrentInterrupt(null);

    // Call /chat/resume endpoint with approved=false
    fetch(getChatResumeUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: useSession.getState().sessionId,
        user_id: useSession.getState().userId,
        interrupt_id: interruptId,
        approved: false,
      }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Add system message about cancellation
        addMessage({
          role: 'assistant',
          content: data.message || '操作已取消',
        });
      })
      .catch((error) => {
        console.error('Cancel error:', error);
        setError('取消操作失败');
      });
  };

  return (
    <main className="flex h-screen flex-col bg-bg-base text-text-primary">
      {/* Header */}
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
              <p className="text-xs text-text-muted">SSE 流式对话 · ReAct 链路追踪</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {/* Token Bar */}
            <TokenBar current={tokenUsed} budget={tokenBudget} />
            {/* Status */}
            <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-muted px-3 py-1.5">
              <motion.div
                animate={{ scale: [1, 1.2, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
                className="h-2 w-2 rounded-full bg-accent"
              />
              <span
                className="text-xs font-medium text-text-secondary"
                data-testid="connection-status"
              >
                已连接
              </span>
            </div>
          </div>
        </div>
      </motion.header>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left Sidebar - Sessions */}
        <aside className="w-72 border-r border-border bg-bg-alt">
          <div className="p-5">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-text-muted">
              会话列表
            </h2>
            <div className="space-y-2">
              <motion.button
                whileHover={{ scale: 1.02, x: 4 }}
                whileTap={{ scale: 0.98 }}
                className="w-full rounded-xl border border-border bg-bg-card p-4 text-left shadow-sm transition-all hover:shadow-md hover:border-border-strong"
              >
                <div className="flex items-center gap-2">
                  <div className="h-2 w-2 rounded-full bg-primary" />
                  <div className="font-medium text-sm text-text-primary">新对话</div>
                </div>
                <div className="mt-2 text-xs text-text-muted flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  刚刚
                </div>
              </motion.button>
            </div>
          </div>
        </aside>

        {/* Center - Chat */}
        <section className="flex flex-1 flex-col bg-bg-base">
          <MessageList messages={messages} isLoading={isLoading} />
          <ChatInput onSend={handleSendMessage} disabled={isLoading} />
        </section>

        {/* Right Sidebar - Tool Trace & Timeline */}
        <aside className="flex w-96 flex-col border-l border-border bg-bg-card">
          {/* Tab Navigation */}
          <div className="flex border-b border-border bg-bg-alt">
            <button
              onClick={() => setActiveTab('timeline')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-all duration-200 relative',
                activeTab === 'timeline'
                  ? 'text-primary'
                  : 'text-text-muted hover:text-text-secondary'
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
              onClick={() => setActiveTab('trace')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 px-4 py-3 text-sm font-medium transition-all duration-200 relative',
                activeTab === 'trace' ? 'text-primary' : 'text-text-muted hover:text-text-secondary'
              )}
            >
              <Wrench className="w-4 h-4" />
              工具链路
              {activeTab === 'trace' && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary"
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              )}
            </button>
          </div>

          {/* Tab Content */}
          <div className="flex-1 overflow-hidden">
            <motion.div
              key={activeTab}
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="h-full"
            >
              {activeTab === 'timeline' ? (
                <Timeline events={timelineEvents} />
              ) : (
                <ToolCallTrace messages={messages} />
              )}
            </motion.div>
          </div>
        </aside>
      </div>

      {/* HIL Confirm Modal */}
      <ConfirmModal
        isOpen={showConfirmModal}
        interrupt={currentInterrupt}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </main>
  );
}
