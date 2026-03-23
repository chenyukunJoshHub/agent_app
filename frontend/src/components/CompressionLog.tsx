'use client';

import { motion, AnimatePresence } from 'framer-motion';
import { TrendingDown, Clock, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { CompressionEvent } from '@/types/context-window';

interface CompressionLogProps {
  /** Compression events to display */
  events: CompressionEvent[];
}

/**
 * CompressionLog Component
 *
 * Displays compression event logs with:
 * - Before/after token counts
 * - Tokens saved calculation
 * - Compression method
 * - Affected slots
 * - Timestamp
 */
export function CompressionLog({ events }: CompressionLogProps) {
  const formatTimestamp = (timestamp: number) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const formatNumber = (num: number) => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  };

  const getMethodLabel = (method: CompressionEvent['method']) => {
    switch (method) {
      case 'summarization':
        return '摘要压缩';
      case 'truncation':
        return '截断';
      case 'hybrid':
        return '混合压缩';
      default:
        return method;
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center gap-2">
          <Minimize2 className="w-5 h-5 text-text-secondary" />
          <h2 className="font-semibold text-text-primary">压缩事件日志</h2>
        </div>
        <p className="mt-1 text-xs text-text-muted">
          {events.length} 个压缩事件
        </p>
      </div>

      {/* Event list */}
      <div className="flex-1 overflow-y-auto p-4">
        <AnimatePresence mode="popLayout">
          {events.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex h-full items-center justify-center"
            >
              <p className="text-sm text-text-muted">暂无压缩事件</p>
            </motion.div>
          ) : (
            <div className="space-y-3">
              {events.map((event, index) => {
                const savingsPercentage =
                  event.before_tokens > 0
                    ? ((event.tokens_saved / event.before_tokens) * 100).toFixed(1)
                    : '0.0';

                return (
                  <motion.div
                    key={event.id}
                    initial={{ opacity: 0, y: -20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, x: -100 }}
                    transition={{ duration: 0.3, delay: index * 0.05 }}
                    className={cn(
                      "rounded-lg border border-border bg-bg-card p-3 shadow-sm",
                      "transition-all duration-200 hover:shadow-md hover:border-border-strong"
                    )}
                    data-testid="compression-event"
                    data-event-id={event.id}
                  >
                    {/* Event header */}
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-success-bg">
                          <TrendingDown className="w-4 h-4 text-success-text" />
                        </div>
                        <span className="text-xs font-semibold uppercase text-text-secondary">
                          {getMethodLabel(event.method)}
                        </span>
                      </div>
                      <span
                        className="text-xs text-text-muted flex items-center gap-1"
                        data-testid="compression-timestamp"
                      >
                        <Clock className="w-3 h-3" />
                        {formatTimestamp(event.timestamp)}
                      </span>
                    </div>

                    {/* Token statistics */}
                    <div className="mb-2 grid grid-cols-3 gap-2 text-center">
                      <div className="rounded bg-bg-muted px-2 py-1">
                        <p className="text-[10px] text-text-muted">压缩前</p>
                        <p
                          className="text-sm font-semibold text-text-primary tabular-nums"
                          data-testid="compression-before"
                        >
                          {formatNumber(event.before_tokens)}
                        </p>
                      </div>
                      <div className="rounded bg-bg-muted px-2 py-1">
                        <p className="text-[10px] text-text-muted">压缩后</p>
                        <p
                          className="text-sm font-semibold text-text-primary tabular-nums"
                          data-testid="compression-after"
                        >
                          {formatNumber(event.after_tokens)}
                        </p>
                      </div>
                      <div className="rounded bg-success-bg px-2 py-1">
                        <p className="text-[10px] text-success-text">节省</p>
                        <p
                          className="text-sm font-semibold text-success-text tabular-nums"
                          data-testid="compression-saved"
                        >
                          {savingsPercentage}%
                        </p>
                      </div>
                    </div>

                    {/* Tokens saved detail */}
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-text-muted">节省 Token</span>
                      <span
                        className="font-medium text-success-text tabular-nums"
                        data-testid="compression-tokens-saved"
                      >
                        {formatNumber(event.tokens_saved)} Token
                      </span>
                    </div>

                    {/* Affected slots */}
                    {event.affected_slots.length > 0 && (
                      <div className="mt-2 flex items-center gap-1 flex-wrap">
                        <span className="text-[10px] text-text-muted">影响:</span>
                        {event.affected_slots.map((slotName) => (
                          <span
                            key={slotName}
                            className="inline-flex items-center rounded-full bg-bg-alt px-2 py-0.5 text-[10px] font-medium text-text-secondary border border-border"
                            data-testid="affected-slot"
                          >
                            {slotName}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                );
              })}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
