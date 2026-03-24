'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, ChevronDown, ChevronRight, Database } from 'lucide-react';

import { cn } from '@/lib/utils';
import type { TraceEvent } from '@/types/trace';
import { ToolCallCard } from '@/components/ToolCallCard';

interface ExecutionTracePanelProps {
  traceEvents: TraceEvent[];
  turnStatuses?: Record<string, 'done' | 'error'>; // turnId -> status
}

const STAGE_LABELS: Record<string, string> = {
  stream: '流式层',
  agent_init: '初始化',
  context: 'Context 组装',
  memory: '记忆层',
  react: 'ReAct 循环',
  tools: '工具层',
  skills: '技能层',
  hil: 'HIL 介入',
};

const STATUS_STYLES: Record<string, string> = {
  start: 'bg-blue-100 text-blue-700',
  ok: 'bg-green-100 text-green-700',
  skip: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
};

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

export function ExecutionTracePanel({ traceEvents, turnStatuses }: ExecutionTracePanelProps) {
  const [openIds, setOpenIds] = useState<Record<string, boolean>>({});

  const stageCount = useMemo(() => {
    const counter: Record<string, number> = {};
    for (const evt of traceEvents) {
      counter[evt.stage] = (counter[evt.stage] || 0) + 1;
    }
    return counter;
  }, [traceEvents]);

  // 按 turnId 分组，保留原始顺序
  const groupedEvents = useMemo(() => {
    const groups: Array<{ turnId: string | undefined; events: TraceEvent[] }> = [];
    for (const evt of traceEvents) {
      const last = groups[groups.length - 1];
      if (!last || last.turnId !== evt.turnId) {
        groups.push({ turnId: evt.turnId, events: [evt] });
      } else {
        last.events.push(evt);
      }
    }
    return groups;
  }, [traceEvents]);

  const toggle = (id: string) => {
    setOpenIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex h-full flex-col" data-testid="execution-trace-panel">
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-primary" />
          <h2 className="font-semibold text-text-primary">执行链路明细</h2>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {traceEvents.length} 个事件 · {Object.keys(stageCount).length} 个阶段
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <section className="rounded-xl border border-border bg-bg-card">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <Database className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-text-primary">事件流水</span>
          </div>

          {traceEvents.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-text-muted">
              暂无链路事件
            </div>
          ) : (
            <div className="divide-y divide-border">
              {groupedEvents.map((group, groupIdx) => {
                const turnNumber = group.turnId
                  ? parseInt(group.turnId.replace('turn_', ''), 10)
                  : null;
                const firstEvent = group.events[0];

                return (
                  <div key={group.turnId ?? `pre_${groupIdx}`}>
                    {/* Turn 分隔线 */}
                    <div
                      data-testid="turn-divider"
                      className="flex items-center gap-2 px-3 py-1.5 bg-primary/5 border-b border-primary/20"
                    >
                      <div className="flex-1 h-px bg-border" />
                      <span className="text-[11px] text-text-muted px-2 shrink-0">
                        {turnNumber !== null
                          ? `Turn #${turnNumber}  ${formatTime(firstEvent?.timestamp ?? '')}`
                          : 'Pre-session'}
                      </span>
                      <div className="flex-1 h-px bg-border" />
                    </div>

                    {/* 该 Turn 的事件列表 */}
                    {group.events.map((evt, idx) => {
                      if (evt.stage === 'tools') {
                        return (
                          <ToolCallCard
                            key={evt.id}
                            toolName={String(evt.payload.tool_name ?? evt.step)}
                            status={evt.status as 'start' | 'ok' | 'error' | 'skip'}
                            args={evt.payload.args as Record<string, unknown> | undefined}
                            contentPreview={evt.payload.content_preview as string | undefined}
                            contentLength={evt.payload.content_length as number | undefined}
                            errorMessage={evt.payload.error as string | undefined}
                            timestamp={evt.timestamp}
                          />
                        );
                      }

                      const expanded = !!openIds[evt.id];
                      return (
                        <motion.div
                          key={evt.id}
                          initial={{ opacity: 0, y: 4 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.12, delay: Math.min(0.3, idx * 0.01) }}
                          className="px-3 py-2"
                        >
                          <button
                            className="w-full text-left"
                            onClick={() => toggle(evt.id)}
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2 min-w-0">
                                {expanded ? (
                                  <ChevronDown className="w-3 h-3 text-text-muted shrink-0" />
                                ) : (
                                  <ChevronRight className="w-3 h-3 text-text-muted shrink-0" />
                                )}
                                <span className="text-xs px-1.5 py-0.5 rounded bg-bg-muted text-text-muted shrink-0">
                                  {STAGE_LABELS[evt.stage] ?? evt.stage}
                                </span>
                                <span className="text-sm text-text-primary truncate">
                                  {evt.step}
                                </span>
                              </div>
                              <div className="flex items-center gap-2 shrink-0">
                                <span
                                  className={cn(
                                    'text-[11px] px-1.5 py-0.5 rounded',
                                    STATUS_STYLES[evt.status] ?? 'bg-bg-muted text-text-muted'
                                  )}
                                >
                                  {evt.status}
                                </span>
                                <span className="text-[11px] text-text-muted">
                                  {formatTime(evt.timestamp)}
                                </span>
                              </div>
                            </div>
                          </button>

                          {expanded && (
                            <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-bg-muted p-2 text-xs text-text-secondary">
                              {prettyJson(evt.payload)}
                            </pre>
                          )}
                        </motion.div>
                      );
                    })}

                    {/* Turn 完成/失败 badge */}
                    {group.turnId && turnStatuses?.[group.turnId] && (
                      <div className={`px-3 py-1 text-xs ${
                        turnStatuses[group.turnId] === 'done'
                          ? 'text-success-text'
                          : 'text-error-text'
                      }`}>
                        {turnStatuses[group.turnId] === 'done'
                          ? `✓ Turn #${turnNumber} 完成 · ${group.events.length} 个事件`
                          : `✗ Turn #${turnNumber} 失败`}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

