'use client';

import { Message, ToolCall } from '@/store/use-session';
import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Bot, Wrench, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StateMessage, CompressionEvent } from '@/types/context-window';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  stateMessages?: StateMessage[]; // 新增
  compressionEvents?: CompressionEvent[]; // 新增
}

function MessageBubble({ message, index }: { message: Message; index: number }) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={cn('flex gap-3 mb-6', isUser ? 'justify-end' : 'justify-start')}
    >
      {/* Avatar */}
      {!isUser && (
        <div className="flex-shrink-0">
          <div
            className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary
                          flex items-center justify-center shadow-md"
          >
            <Bot className="w-4 h-4 text-white" />
          </div>
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-3 shadow-sm',
          isUser
            ? 'bg-primary text-white rounded-br-sm'
            : 'bg-bg-card border border-border text-text-primary rounded-bl-sm'
        )}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        ) : (
          <div
            className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed
                          prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1
                          prose-li:my-0 prose-code:text-xs prose-pre:my-2"
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Tool Calls */}
        {message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.tool_calls.map((toolCall) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} />
            ))}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex-shrink-0">
          <div
            className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600
                          flex items-center justify-center shadow-md"
          >
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      )}
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
    <div className="rounded-lg border border-border bg-bg-alt p-3 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Wrench className="w-4 h-4 text-primary" />
          <span className="font-mono text-xs font-semibold text-text-primary">
            {toolCall.tool_name}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('text-[10px] px-1.5 py-0.5 rounded', config.color)}>
            {config.label}
          </span>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="text-text-muted hover:text-text-primary"
          >
            {isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
          </button>
        </div>
      </div>
      {isExpanded && (
        <div className="bg-bg-muted rounded-lg p-2 text-xs font-mono text-text-secondary">
          <pre className="whitespace-pre-wrap break-all">
            {JSON.stringify(toolCall.args, null, 2)}
          </pre>
          {toolCall.result && (
            <div className="mt-2 pt-2 border-t border-border">
              <div className="text-text-muted mb-1">Result:</div>
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
    <div data-testid="tool-message-bubble" className="flex gap-3 mb-3">
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-bg-muted border border-border flex items-center justify-center">
        <Wrench className="w-4 h-4 text-text-muted" />
      </div>
      <div className="max-w-[80%] rounded-xl bg-bg-muted border border-border px-3 py-2">
        <p className="text-[11px] text-text-muted mb-1">工具返回</p>
        <button
          className="text-xs text-text-secondary text-left"
          onClick={() => setExpanded(!expanded)}
        >
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
    <div data-testid="compression-notification" className="flex items-center gap-2 my-3 px-4">
      <div className="flex-1 h-px bg-border" />
      <span className="text-xs text-text-muted shrink-0">
        💾 历史已压缩 · 节省 {event.tokens_saved.toLocaleString()} tokens ({event.method})
      </span>
      <div className="flex-1 h-px bg-border" />
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
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="mx-auto max-w-3xl">
        <AnimatePresence mode="wait">
          {messages.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="flex h-full items-center justify-center min-h-[400px]"
            >
              <div className="text-center">
                <div
                  className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-primary to-secondary
                                flex items-center justify-center shadow-lg"
                >
                  <Bot className="w-8 h-8 text-white" />
                </div>
                <h2 className="text-2xl font-semibold text-text-primary mb-2">开始对话</h2>
                <p className="text-muted-foreground">试试问："帮我查一下茅台今天的股价"</p>
              </div>
            </motion.div>
          ) : (
            messages
              .filter((msg) => msg.content.trim() !== '' || msg.role === 'user')
              .map((message, index) => (
                <MessageBubble key={message.id} message={message} index={index} />
              ))
          )}

          {/* tool role 消息气泡（来自 stateMessages） */}
          {stateMessages
            .filter((m) => m.role === 'tool')
            .map((msg, i) => (
              <ToolMessageBubble key={`tool_${i}`} msg={msg} />
            ))}

          {/* 压缩通知气泡 */}
          {compressionEvents.map((event) => (
            <CompressionNotification key={event.id} event={event} />
          ))}
        </AnimatePresence>

        {isLoading &&
          !(
            messages[messages.length - 1]?.role === 'assistant' &&
            messages[messages.length - 1]?.content.trim() !== ''
          ) && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex gap-3 mb-6"
            >
              <div
                className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary
                            flex items-center justify-center shadow-md"
              >
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="bg-bg-card border border-border rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
                <div className="flex items-center gap-2">
                  <div className="flex space-x-1">
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity }}
                      className="w-2 h-2 rounded-full bg-primary"
                    />
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: 0.1 }}
                      className="w-2 h-2 rounded-full bg-primary"
                    />
                    <motion.div
                      animate={{ scale: [1, 1.2, 1] }}
                      transition={{ duration: 0.6, repeat: Infinity, delay: 0.2 }}
                      className="w-2 h-2 rounded-full bg-primary"
                    />
                  </div>
                  <span className="text-sm text-muted-foreground">思考中...</span>
                </div>
              </div>
            </motion.div>
          )}
      </div>
      <div ref={scrollRef} />
    </div>
  );
}
