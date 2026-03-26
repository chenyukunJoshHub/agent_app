'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Wrench } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ToolCallCardProps {
  toolName: string;
  status: 'start' | 'ok' | 'error' | 'skip';
  args?: Record<string, unknown>;
  contentPreview?: string;
  contentLength?: number;
  errorMessage?: string;
  timestamp: string;
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  start: { label: '调用中', className: 'bg-blue-100 text-blue-700' },
  ok: { label: '成功', className: 'bg-green-100 text-green-700' },
  error: { label: '失败', className: 'bg-red-100 text-red-700' },
  skip: { label: '跳过', className: 'bg-amber-100 text-amber-700' },
};

const WRITE_TOOLS = new Set(['send_email', 'save_file', 'write_file']);

function prettyJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function formatTime(raw: string): string {
  const date = new Date(raw);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3,
  });
}

export function ToolCallCard({
  toolName,
  status,
  args,
  contentPreview,
  contentLength,
  errorMessage,
  timestamp,
}: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isWrite = WRITE_TOOLS.has(toolName);
  const borderColor = status === 'error' ? 'border-l-red-500' : isWrite ? 'border-l-orange-500' : 'border-l-blue-500';
  const statusCfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.skip;

  const hasArgs = args !== undefined && Object.keys(args).length > 0;
  const hasResult = contentPreview !== undefined && contentPreview !== '';

  return (
    <div className={cn('rounded-lg border border-border border-l-4 bg-bg-card', borderColor)}>
      <button
        className="w-full text-left px-3 py-2 flex items-center justify-between gap-2"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 min-w-0">
          {expanded ? (
            <ChevronDown className="w-3 h-3 text-text-muted shrink-0" />
          ) : (
            <ChevronRight className="w-3 h-3 text-text-muted shrink-0" />
          )}
          <Wrench className="w-3.5 h-3.5 text-text-muted shrink-0" />
          <span className="font-mono text-sm font-semibold text-text-primary truncate">
            {toolName}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn('text-[11px] px-1.5 py-0.5 rounded', statusCfg.className)}>
            {statusCfg.label}
          </span>
          <span className="text-[11px] text-text-muted">{formatTime(timestamp)}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {hasArgs && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">参数</div>
              <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                {prettyJson(args)}
              </pre>
            </div>
          )}

          {hasResult && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] text-text-muted">结果预览</span>
                {contentLength !== undefined && (
                  <span className="text-[11px] text-text-muted">{contentLength} 字符</span>
                )}
              </div>
              <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                {contentPreview}
              </pre>
            </div>
          )}

          {errorMessage && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">错误信息</div>
              <pre className="rounded-lg bg-red-50 p-2 text-xs text-red-700 overflow-x-auto">
                {errorMessage}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
