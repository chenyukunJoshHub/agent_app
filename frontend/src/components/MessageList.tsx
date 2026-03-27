'use client';

import { Message, ToolCall } from '@/store/use-session';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Wrench, ChevronDown, ChevronRight, Copy, PencilLine, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StateMessage, CompressionEvent } from '@/types/context-window';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  stateMessages?: StateMessage[];
  compressionEvents?: CompressionEvent[];
}

function AssistantGlyph() {
  return (
    <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center">
      <Sparkles className="h-5 w-5 text-primary drop-shadow-[0_0_14px_rgba(66,133,244,0.45)]" />
    </div>
  );
}

function MessageBubble({ message, index }: { message: Message; index: number }) {
  const isUser = message.role === 'user';

  const copyToClipboard = () => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      void navigator.clipboard.writeText(message.content);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={cn('group mb-8 flex gap-3', isUser ? 'justify-end' : 'justify-start')}
    >
      {!isUser && <AssistantGlyph />}

      {isUser && (
        <div className="hidden items-center gap-2 text-text-muted md:flex">
          <button
            type="button"
            onClick={copyToClipboard}
            className="rounded-full p-1.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 hover:bg-bg-muted hover:text-text-primary"
            aria-label="复制消息"
          >
            <Copy className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded-full p-1.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100 hover:bg-bg-muted hover:text-text-primary"
            aria-label="编辑消息"
          >
            <PencilLine className="h-4 w-4" />
          </button>
        </div>
      )}

      <div
        className={cn(
          'group max-w-[82%]',
          isUser
            ? 'rounded-[30px] border border-border/65 bg-bg-card px-5 py-3 text-text-primary shadow-[0_8px_24px_var(--color-shadow-soft)]'
            : 'pt-0.5',
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{message.content}</p>
        ) : (
          <div
            className={cn(
              'prose prose-sm max-w-none text-[15px] leading-8',
              'prose-p:my-1 prose-headings:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5',
              'prose-p:text-text-primary prose-headings:text-text-primary prose-strong:text-text-primary',
              'prose-a:text-primary hover:prose-a:text-primary-hover',
              'prose-code:rounded-md prose-code:bg-bg-card prose-code:px-1.5 prose-code:py-0.5',
              'prose-code:text-primary prose-code:before:content-none prose-code:after:content-none',
              'prose-pre:my-3 prose-pre:rounded-2xl prose-pre:border prose-pre:border-border/60',
              'prose-pre:bg-bg-card/70 prose-pre:text-text-primary',
            )}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.tool_calls.map((toolCall) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function ToolCallCard({ toolCall }: { toolCall: ToolCall }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const statusConfig = {
    pending: {
      color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200',
      label: '等待中',
    },
    running: {
      color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200',
      label: '执行中',
    },
    completed: {
      color: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200',
      label: '完成',
    },
    error: {
      color: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200',
      label: '错误',
    },
  };

  const config = statusConfig[toolCall.status] || statusConfig.pending;

  return (
    <div className="rounded-2xl border border-border/70 bg-bg-card/75 p-3 shadow-[0_8px_24px_var(--color-shadow-soft)] backdrop-blur-sm">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-primary" />
          <span className="font-mono text-xs font-semibold text-text-primary">{toolCall.tool_name}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('rounded px-1.5 py-0.5 text-[10px]', config.color)}>{config.label}</span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-text-muted hover:text-text-primary"
          >
            {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="rounded-xl bg-bg-muted/75 p-2 font-mono text-xs text-text-secondary">
          <pre className="whitespace-pre-wrap break-all">{JSON.stringify(toolCall.args, null, 2)}</pre>
          {toolCall.result && (
            <div className="mt-2 border-t border-border pt-2">
              <div className="mb-1 text-text-muted">Result:</div>
              <pre className="whitespace-pre-wrap break-all">
                {typeof toolCall.result === 'string'
                  ? toolCall.result
                  : JSON.stringify(toolCall.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolMessageBubble({ msg }: { msg: StateMessage }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div data-testid="tool-message-bubble" className="mb-3 flex gap-3">
      <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-border/60 bg-bg-muted/80">
        <Wrench className="h-4 w-4 text-text-muted" />
      </div>
      <div className="max-w-[80%] rounded-xl border border-border/60 bg-bg-muted/70 px-3 py-2">
        <p className="mb-1 text-[11px] text-text-muted">工具返回</p>
        <button className="text-left text-xs text-text-secondary" onClick={() => setExpanded(!expanded)}>
          {expanded
            ? msg.content
            : (msg.content || '').slice(0, 100) + ((msg.content || '').length > 100 ? '...' : '')}
        </button>
      </div>
    </div>
  );
}

function CompressionNotification({ event }: { event: CompressionEvent }) {
  return (
    <div data-testid="compression-notification" className="my-3 flex items-center gap-2 px-4">
      <div className="h-px flex-1 bg-border" />
      <span className="shrink-0 text-xs text-text-muted">
        历史已压缩 · 节省 {event.tokens_saved.toLocaleString()} tokens ({event.method})
      </span>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}

export function MessageList({
  messages,
  isLoading,
  stateMessages = [],
  compressionEvents = [],
}: MessageListProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto px-4 pb-6 pt-8 md:px-8 md:pb-8">
      <div className="mx-auto max-w-5xl">
        <AnimatePresence mode="wait">
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="min-h-[380px] px-2 pt-10 md:px-6 md:pt-16"
            >
              <div className="w-full max-w-4xl">
                <div className="mb-10 flex justify-end">
                  <div className="rounded-[32px] border border-border/65 bg-bg-card px-7 py-5 text-4xl font-medium text-text-primary shadow-[0_10px_30px_var(--color-shadow-soft)]">
                    你好
                  </div>
                </div>
                <div className="flex items-start gap-3 text-left">
                  <AssistantGlyph />
                  <div className="space-y-1 text-text-primary">
                    <h2 className="text-4xl font-medium tracking-tight">你好！很高兴见到你😊</h2>
                    <p className="text-4xl font-medium tracking-tight text-text-secondary">
                      你想查天气，还是需要其他帮助？
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          ) : (
            messages
              .filter((msg) => msg.content.trim() !== '' || msg.role === 'user')
              .map((message, index) => (
                <MessageBubble key={message.id} message={message} index={index} />
              ))
          )}

          {stateMessages
            .filter((m) => m.role === 'tool')
            .map((msg, i) => (
              <ToolMessageBubble key={`tool_${i}`} msg={msg} />
            ))}

          {compressionEvents.map((event) => (
            <CompressionNotification key={event.id} event={event} />
          ))}
        </AnimatePresence>

        {isLoading &&
          !(
            messages[messages.length - 1]?.role === 'assistant' &&
            messages[messages.length - 1]?.content.trim() !== ''
          ) && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="mb-6 flex gap-3">
              <AssistantGlyph />
              <div className="rounded-[22px] border border-border/70 bg-bg-card/85 px-4 py-3 shadow-[0_8px_24px_var(--color-shadow-soft)]">
                <div className="flex items-center gap-2">
                  <div className="flex space-x-1">
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity }}
                      className="h-2 w-2 rounded-full bg-primary"
                    />
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: 0.1 }}
                      className="h-2 w-2 rounded-full bg-primary"
                    />
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                      className="h-2 w-2 rounded-full bg-primary"
                    />
                  </div>
                  <span className="text-sm text-text-secondary">思考中...</span>
                </div>
              </div>
            </motion.div>
          )}
      </div>
      <div ref={scrollRef} />
    </div>
  );
}
