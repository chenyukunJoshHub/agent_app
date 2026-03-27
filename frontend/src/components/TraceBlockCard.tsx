'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Play,
  Brain,
  Wrench,
  MessageSquare,
  Database,
  FileText,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { TraceBlock } from '@/types/trace';
import type { TraceEvent } from '@/types/trace';

const BLOCK_CONFIG: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  turn_start: { icon: Play, color: 'text-blue-500', label: '开始处理' },
  planning: { icon: FileText, color: 'text-indigo-500', label: '任务规划' },
  retrieval: { icon: Database, color: 'text-cyan-500', label: '上下文检索' },
  replanning: { icon: AlertCircle, color: 'text-orange-500', label: '失败重规划' },
  thinking: { icon: Brain, color: 'text-purple-500', label: '思考推理' },
  tool_call: { icon: Wrench, color: 'text-amber-500', label: '调用工具' },
  answer: { icon: MessageSquare, color: 'text-green-500', label: '生成回答' },
  memory_load: { icon: Database, color: 'text-blue-400', label: '加载记忆' },
  prompt_build: { icon: FileText, color: 'text-blue-400', label: '组装上下文' },
  hil_pause: { icon: AlertCircle, color: 'text-orange-500', label: '等待确认' },
  error: { icon: AlertTriangle, color: 'text-red-500', label: '出错了' },
  turn_summary: { icon: CheckCircle, color: 'text-green-500', label: '本轮摘要' },
};

const STATUS_DOT: Record<string, string> = {
  ok: 'bg-green-400',
  pending: 'bg-amber-400 animate-pulse',
  skip: 'bg-gray-400',
  error: 'bg-red-400',
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
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

function prettyJson(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

interface TraceBlockCardProps {
  block: TraceBlock;
  rawEvents?: TraceEvent[];
}

export function TraceBlockCard({ block, rawEvents = [] }: TraceBlockCardProps) {
  const [expanded, setExpanded] = useState(block.type === 'error');
  const config = BLOCK_CONFIG[block.type] ?? BLOCK_CONFIG.error;
  const Icon = config.icon;
  const isDevOnly = block.type === 'memory_load' || block.type === 'prompt_build';

  const summaryLine = (() => {
    switch (block.type) {
      case 'turn_start':
        return block.detail ?? '';
      case 'planning':
        return block.detail ?? '';
      case 'retrieval':
        return block.detail ?? '';
      case 'replanning':
        return block.detail ?? '';
      case 'thinking':
        return block.thinking?.content_preview
          ? block.thinking.content_preview.slice(0, 120)
          : (block.detail ?? '');
      case 'tool_call':
        return block.tool_call?.name ?? '';
      case 'answer':
        return block.answer?.content_preview
          ? block.answer.content_preview.slice(0, 120) +
              (block.answer.content_preview.length > 120 ? '...' : '')
          : (block.detail ?? '');
      case 'turn_summary':
        return block.detail ?? '';
      case 'error':
        return block.error?.message ?? block.detail ?? 'Unknown error';
      case 'memory_load':
        return block.detail ?? '';
      case 'prompt_build':
        return block.detail ?? '';
      default:
        return '';
    }
  })();

  // Token badges for thinking blocks
  const tokenBadges = block.thinking
    ? (
        [
          block.thinking.input_tokens > 0
            ? { label: `in: ${block.thinking.input_tokens}`, key: 'in' }
            : null,
          block.thinking.output_tokens > 0
            ? { label: `out: ${block.thinking.output_tokens}`, key: 'out' }
            : null,
        ] as Array<{ label: string; key: string } | null>
      ).filter((b): b is { label: string; key: string } => b !== null)
    : [];

  // Result length badge for tool_call blocks
  const resultBadge =
    block.tool_call && block.tool_call.result_length > 0
      ? `${block.tool_call.result_length} 字符`
      : null;

  // Answer char count badge
  const answerBadge = block.answer ? `${block.answer.char_count} 字符` : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
      data-testid="trace-block-card"
      className={cn(
        'rounded-lg border bg-bg-card',
        isDevOnly && 'border-dashed border-blue-300/50',
        block.type === 'error' && 'border-red-300',
        block.type !== 'error' && !isDevOnly && 'border-border'
      )}
    >
      <button
        className="w-full text-left px-3 py-2 flex items-center justify-between gap-2"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className={cn(
              'w-2 h-2 rounded-full shrink-0',
              STATUS_DOT[block.status] ?? STATUS_DOT.ok
            )}
          />
          <Icon className={cn('w-4 h-4 shrink-0', config.color)} />
          <span className="text-sm font-medium text-text-primary truncate">{config.label}</span>
          {block.type === 'tool_call' && block.tool_call && (
            <span className="font-mono text-sm text-text-secondary truncate">
              {block.tool_call.name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {block.duration_ms > 0 && (
            <span className="text-[11px] text-text-muted">{formatDuration(block.duration_ms)}</span>
          )}
          <span className="text-[11px] text-text-muted">{formatTime(block.timestamp)}</span>
        </div>
      </button>

      {/* Summary line + badges (visible when collapsed) */}
      {!expanded && (
        <div className="px-3 pb-2 space-y-1">
          {summaryLine && (
            <div className="text-xs text-text-secondary line-clamp-2">{summaryLine}</div>
          )}
          <div className="flex items-center gap-2 flex-wrap">
            {tokenBadges.map((badge) => (
              <span
                key={badge.key}
                className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600"
              >
                {badge.label}
              </span>
            ))}
            {resultBadge && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-50 text-amber-600">
                {resultBadge}
              </span>
            )}
            {answerBadge && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-50 text-green-600">
                {answerBadge}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Expanded details */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {summaryLine && block.type !== 'error' && (
            <div className="text-xs text-text-secondary">{summaryLine}</div>
          )}

          {/* Token badges (expanded view) */}
          {tokenBadges.length > 0 && (
            <div className="flex items-center gap-2">
              {tokenBadges.map((badge) => (
                <span
                  key={badge.key}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600"
                >
                  {badge.label}
                </span>
              ))}
            </div>
          )}

          {/* Tool call details */}
          {block.tool_call && (
            <>
              {Object.keys(block.tool_call.args).length > 0 && (
                <div>
                  <div className="text-[11px] text-text-muted mb-1">参数</div>
                  <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                    {prettyJson(block.tool_call.args)}
                  </pre>
                </div>
              )}
              {block.tool_call.result_preview && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] text-text-muted">结果预览</span>
                    {block.tool_call.result_length > 0 && (
                      <span className="text-[11px] text-text-muted">
                        {block.tool_call.result_length} 字符
                      </span>
                    )}
                  </div>
                  <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-40">
                    {block.tool_call.result_preview}
                  </pre>
                </div>
              )}
            </>
          )}

          {/* Thinking content — show full preview */}
          {block.thinking?.content_preview && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">推理内容</div>
              <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-60 whitespace-pre-wrap">
                {block.thinking.content_preview}
              </pre>
            </div>
          )}

          {/* Answer content preview */}
          {block.answer?.content_preview && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">回答内容</div>
              <pre className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary overflow-x-auto max-h-60 whitespace-pre-wrap">
                {block.answer.content_preview}
              </pre>
            </div>
          )}

          {/* Error details */}
          {block.error && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">错误详情</div>
              <pre className="rounded-lg bg-red-50 p-2 text-xs text-red-700 overflow-x-auto">
                {block.error.stage}/{block.error.step}: {block.error.message}
              </pre>
            </div>
          )}

          {/* Turn summary details */}
          {block.turn_summary && (
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">
                  {block.turn_summary.think_count}
                </div>
                <div className="text-[11px] text-text-muted">次思考</div>
              </div>
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">
                  {block.turn_summary.tool_count}
                </div>
                <div className="text-[11px] text-text-muted">次工具</div>
              </div>
              <div className="rounded-lg bg-bg-muted p-2">
                <div className="text-lg font-semibold text-text-primary">
                  {block.turn_summary.total_tokens}
                </div>
                <div className="text-[11px] text-text-muted">tokens</div>
              </div>
            </div>
          )}

          {rawEvents.length > 0 && (
            <div>
              <div className="text-[11px] text-text-muted mb-1">原始事件 ({rawEvents.length})</div>
              <div className="rounded-lg bg-bg-muted p-2 text-xs text-text-secondary space-y-1 max-h-48 overflow-y-auto">
                {rawEvents.map((event) => (
                  <div key={event.id} className="font-mono">
                    {event.stage}/{event.step} [{event.status}]
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
