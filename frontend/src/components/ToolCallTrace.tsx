'use client';

import { Message, ToolCall } from '@/store/use-session';
import { useState } from 'react';
import { motion } from 'framer-motion';
import { Wrench, ChevronDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolCallTraceProps {
  messages: Message[];
}

export function ToolCallTrace({ messages }: ToolCallTraceProps) {
  // Collect all tool calls from messages
  const allToolCalls = messages
    .filter((m) => m.tool_calls && m.tool_calls.length > 0)
    .flatMap((m) => m.tool_calls || []);

  return (
    <div className="flex h-full flex-col" data-testid="tool-call-trace">
      <div className="border-b border-border p-4 bg-background-alt">
        <h2 className="font-semibold text-text-primary">工具调用链路</h2>
        <p className="mt-1 text-xs text-muted-foreground">{allToolCalls.length} 个工具调用</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {allToolCalls.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">暂无工具调用</p>
          </div>
        ) : (
          <div className="space-y-3">
            {allToolCalls.map((toolCall, index) => (
              <ToolCallCard key={toolCall.id} toolCall={toolCall} index={index} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ToolCallCard({ toolCall, index }: { toolCall: ToolCall; index: number }) {
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

  const style = statusConfig[toolCall.status] || statusConfig.pending;
  const label = style.label;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.05 }}
      className="relative rounded-lg border border-border bg-background-card p-3 shadow-sm"
    >
      {/* Connector line */}
      {index > 0 && (
        <div className="absolute -left-4 top-0 h-full w-0.5 border-l-2 border-dashed border-border" />
      )}

      {/* Tool Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="rounded bg-primary/10 px-2 py-1 text-xs font-semibold text-primary">
            {index + 1}
          </span>
          <Wrench className="w-4 h-4 text-primary" />
          <span className="font-mono text-sm font-semibold text-text-primary">
            {toolCall.tool_name}
          </span>
        </div>
        <span className={cn('rounded px-2 py-0.5 text-xs font-medium', style.color)}>{label}</span>
      </div>

      {/* Args */}
      {toolCall.args && (
        <div className="mb-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="cursor-pointer text-xs text-muted-foreground
                           hover:text-text-secondary transition-colors flex items-center gap-1"
          >
            {isExpanded ? (
              <ChevronDown className="w-3 h-3" />
            ) : (
              <ChevronRight className="w-3 h-3" />
            )}
            参数
          </button>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              className="mt-2"
            >
              <pre className="overflow-x-auto rounded-lg bg-background p-2 text-xs border border-border">
                {JSON.stringify(toolCall.args, null, 2)}
              </pre>
            </motion.div>
          )}
        </div>
      )}

      {/* Result */}
      {toolCall.result && (
        <div>
          <details open data-testid="tool-result">
            <summary
              className="cursor-pointer text-xs text-muted-foreground
                            hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              <ChevronDown className="w-3 h-3" />
              结果
            </summary>
            <div className="mt-1 max-h-48 overflow-y-auto rounded-lg bg-background p-2 text-xs border border-border">
              {typeof toolCall.result === 'string'
                ? toolCall.result
                : JSON.stringify(toolCall.result, null, 2)}
            </div>
          </details>
        </div>
      )}
    </motion.div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const statusConfig = {
    pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-200',
    running: 'bg-blue-100 text-blue-800 dark:bg-blue-900/20 dark:text-blue-200',
    completed: 'bg-green-100 text-green-800 dark:bg-green-900/20 dark:text-green-200',
    error: 'bg-red-100 text-red-800 dark:bg-red-900/20 dark:text-red-200',
  };

  const labels = {
    pending: '等待中',
    running: '执行中',
    completed: '完成',
    error: '错误',
  };

  const style = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
  const label = labels[status as keyof typeof labels] || status;

  return <span className={cn('rounded px-2 py-0.5 text-xs font-medium', style)}>{label}</span>;
}
