'use client';

import { useCallback, useEffect, useState } from 'react';

import { motion } from 'framer-motion';
import { Activity, Bot, Layers } from 'lucide-react';

import { ChatProvider } from '@/components/assistant/ChatProvider';
import { AssistantComposer } from '@/components/assistant/AssistantComposer';
import { ThemeToggleButton } from '@/components/assistant/ThemeToggleButton';
import { ConfirmModal } from '@/components/ConfirmModal';
import { ContextPanel } from '@/components/ContextPanel';
import { ExecutionTracePanel } from '@/components/ExecutionTracePanel';
import { MessageList } from '@/components/MessageList';
import { SessionGrantStrip } from '@/components/SessionGrantStrip';
import { fetchSessionGrants, postChatResumeDecision, revokeSessionGrant } from '@/lib/hil';
import { cn } from '@/lib/utils';
import { THEME_STORAGE_KEY, applyTheme, resolveInitialTheme, type ThemeMode } from '@/store/theme';
import { useSession } from '@/store/use-session';
import { useSSEHandlers, isTraceEvent, isTraceBlock } from '@/hooks/useSSEHandlers';
import type { InterruptData } from '@/hooks/useSSEHandlers';
import type { StateMessage } from '@/types/context-window';

// ---------------------------------------------------------------------------
// SSE stream consumer (used by HIL confirm/cancel flows)
// ---------------------------------------------------------------------------

interface ParsedSSEEvent {
  event: string;
  data: Record<string, unknown>;
}

async function consumeSSEStream(
  response: Response,
  onEvent: (evt: ParsedSSEEvent) => void,
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

// ---------------------------------------------------------------------------
// HomePage
// ---------------------------------------------------------------------------

export default function HomePage() {
  const {
    messages,
    isLoading,
    traceEvents,
    traceBlocks,
    slotDetails,
    contextWindowData,
    stateMessages,
    sessionMeta,
    sessionId,
    userId,
    addTraceEvent,
    addTraceBlock,
    addMessage,
    setLoading,
    setError,
  } = useSession();

  const [turnStatuses, setTurnStatuses] = useState<Record<string, 'done' | 'error'>>({});
  const [lastActivityTime, setLastActivityTime] = useState<number | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [currentInterrupt, setCurrentInterrupt] = useState<InterruptData | null>(null);
  const [sessionGrants, setSessionGrants] = useState<string[]>([]);
  const [activeTab, setActiveTab] = useState<'chain' | 'context'>('chain');
  const [theme, setTheme] = useState<ThemeMode>('light');

  const setTurnStatus = useCallback((turnId: string, status: 'done' | 'error') => {
    setTurnStatuses((prev) => ({ ...prev, [turnId]: status }));
  }, []);

  useEffect(() => {
    const storageTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(resolveInitialTheme(storageTheme, prefersDark));
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    applyTheme(theme, root);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const handleToggleTheme = useCallback(() => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  const handleHILInterrupt = useCallback((data: InterruptData) => {
    setCurrentInterrupt(data);
    setShowConfirmModal(true);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadSessionGrants() {
      try {
        const grants = await fetchSessionGrants(sessionId);
        if (!cancelled) {
          setSessionGrants(grants);
        }
      } catch {
        if (!cancelled) {
          setSessionGrants([]);
        }
      }
    }

    void loadSessionGrants();
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  // SSE handlers are registered here; handleSendMessage is passed to ChatProvider
  const { handleSendMessage } = useSSEHandlers({
    onHILInterrupt: handleHILInterrupt,
    setTurnStatus,
    setLastActivityTime,
  });

  // ---- HIL confirm/cancel (use direct fetch + consumeSSEStream) ----

  const handleConfirm = useCallback(
    async (interruptId: string, grantSession: boolean) => {
      setShowConfirmModal(false);
      setCurrentInterrupt(null);
      setLoading(true);

      try {
        const toolName = currentInterrupt?.tool_name;
        const response = await postChatResumeDecision({
          sessionId,
          userId,
          interruptId,
          approved: true,
          grantSession,
        });

        await consumeSSEStream(response, ({ event, data }) => {
          if (event === 'trace_event' && isTraceEvent(data)) {
            addTraceEvent(data);
            return;
          }
          if (event === 'trace_block' && isTraceBlock(data)) {
            addTraceBlock(data);
            return;
          }
          if (event === 'tool_result') return;
          if (event === 'hil_resolved' && grantSession && toolName) {
            const grantedTools = Array.isArray((data as { granted_tools?: string[] }).granted_tools)
              ? ((data as { granted_tools?: string[] }).granted_tools as string[])
              : null;
            setSessionGrants((prev) =>
              grantedTools ?? (prev.includes(toolName) ? prev : [...prev, toolName])
            );
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
    },
    [addTraceEvent, addTraceBlock, currentInterrupt, sessionId, userId, setLoading, setError],
  );

  const handleCancel = useCallback(
    async (interruptId: string) => {
      setShowConfirmModal(false);
      setCurrentInterrupt(null);
      setLoading(true);

      try {
        const response = await postChatResumeDecision({
          sessionId,
          userId,
          interruptId,
          approved: false,
        });

        await consumeSSEStream(response, ({ event, data }) => {
          if (event === 'trace_event' && isTraceEvent(data)) {
            addTraceEvent(data);
            return;
          }
          if (event === 'trace_block' && isTraceBlock(data)) {
            addTraceBlock(data);
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
    },
    [addTraceEvent, addTraceBlock, addMessage, sessionId, userId, setLoading, setError],
  );

  const handleRevokeGrant = useCallback(
    async (toolName: string) => {
      try {
        const grants = await revokeSessionGrant({
          sessionId,
          userId,
          toolName,
        });
        setSessionGrants(grants);
      } catch (error) {
        setError(error instanceof Error ? error.message : '撤销会话放行失败');
      }
    },
    [sessionId, userId, setError],
  );

  return (
    <main className="gemini-app flex h-screen flex-col text-text-primary">
      {/* Header */}
      <motion.header
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="border-b border-border/40 bg-bg-base/70 px-4 py-4 backdrop-blur-md md:px-8"
      >
        <div className="mx-auto flex w-full max-w-[1700px] items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-primary to-secondary shadow-[0_8px_26px_rgba(66,133,244,0.35)]">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight md:text-lg">Multi-Tool AI Agent</h1>
              {/* <p className="text-xs text-text-muted">Gemini 风格主题 · assistant-ui</p> */}
            </div>
          </div>
          <ThemeToggleButton theme={theme} onToggle={handleToggleTheme} />
        </div>
      </motion.header>

      {/* Main content */}
      <div className="flex flex-1 gap-3 overflow-hidden px-3 pb-3 pt-2 md:gap-4 md:px-6 md:pb-5">
        {/* Chat area — wrapped with ChatProvider for assistant-ui runtime */}
        <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-[30px] border border-border/35 bg-bg-base/80 backdrop-blur-md">
          <SessionGrantStrip
            grants={sessionGrants}
            onRevoke={handleRevokeGrant}
            className="lg:hidden"
          />
          <ChatProvider onSendMessage={handleSendMessage}>
            <MessageList
              messages={messages}
              isLoading={isLoading}
              stateMessages={stateMessages}
              compressionEvents={contextWindowData.compressionEvents}
            />
            <AssistantComposer />
          </ChatProvider>
        </section>

        {/* Sidebar */}
        <aside className="hidden w-[420px] flex-col overflow-hidden rounded-[30px] border border-border/35 bg-bg-card/75 backdrop-blur-md lg:flex">
          <div className="grid grid-cols-2 border-b border-border/60 bg-bg-alt/65">
            <button
              onClick={() => setActiveTab('chain')}
              className={cn(
                'relative flex items-center justify-center gap-1 px-2 py-3 text-xs font-medium transition-all duration-200',
                activeTab === 'chain'
                  ? 'text-primary'
                  : 'text-text-muted hover:text-text-secondary',
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
                activeTab === 'context'
                  ? 'text-primary'
                  : 'text-text-muted hover:text-text-secondary',
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
                <ExecutionTracePanel
                  traceEvents={traceEvents}
                  traceBlocks={traceBlocks}
                  turnStatuses={turnStatuses}
                />
              )}
              {activeTab === 'context' && (
                <ContextPanel
                  sessionMeta={sessionMeta}
                  contextWindowData={contextWindowData}
                  slotDetails={slotDetails}
                  stateMessages={stateMessages}
                  lastActivityTime={lastActivityTime}
                  sessionGrants={sessionGrants}
                  onRevokeTool={handleRevokeGrant}
                />
              )}
            </motion.div>
          </div>
        </aside>
      </div>

      {/* HIL Confirm Modal */}
      <ConfirmModal
        isOpen={showConfirmModal}
        interrupt={currentInterrupt}
        onConfirm={(interruptId, grantSession) => {
          void handleConfirm(interruptId, grantSession);
        }}
        onCancel={(interruptId) => {
          void handleCancel(interruptId);
        }}
      />
    </main>
  );
}
