'use client';

import { useMemo, useState } from 'react';
import { Activity, Eye, EyeOff } from 'lucide-react';

import type { TraceBlock } from '@/types/trace';
import { USER_VISIBLE_BLOCKS } from '@/types/trace';
import type { TraceEvent } from '@/types/trace';
import { cn } from '@/lib/utils';
import { TraceBlockCard } from '@/components/TraceBlockCard';

interface ExecutionTracePanelProps {
  traceBlocks: TraceBlock[];
  traceEvents: TraceEvent[];
  turnStatuses?: Record<string, 'done' | 'error'>;
}

function formatTime(raw: string): string {
  const date = new Date(raw);
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function groupByTurn(blocks: TraceBlock[]): Array<{ turnId: string | undefined; blocks: TraceBlock[] }> {
  const groups: Array<{ turnId: string | undefined; blocks: TraceBlock[] }> = [];
  for (const block of blocks) {
    const last = groups[groups.length - 1];
    if (!last || last.turnId !== block.turnId) {
      groups.push({ turnId: block.turnId, blocks: [block] });
    } else {
      last.blocks.push(block);
    }
  }
  return groups;
}

function eventMatchesBlock(block: TraceBlock, event: TraceEvent): boolean {
  if (event.status === 'error' && block.type === 'error') return true;
  switch (block.type) {
    case 'turn_start':
      return (
        (event.stage === 'stream' &&
          ['request_received', 'agent_created', 'stream_started'].includes(event.step)) ||
        (event.stage === 'react' && event.step === 'turn_start')
      );
    case 'planning':
      return event.stage === 'planner' && ['plan_created', 'plan_completed'].includes(event.step);
    case 'retrieval':
      return event.stage === 'retrieval' && event.step === 'context_retrieved';
    case 'replanning':
      return event.stage === 'replanner' && ['triggered', 'plan_updated'].includes(event.step);
    case 'thinking':
      return (
        event.stage === 'react' &&
        ['model_call_start', 'model_call_end', 'thought_emitted'].includes(event.step)
      );
    case 'tool_call':
      return event.stage === 'tools' && ['tool_call_planned', 'tool_call_result'].includes(event.step);
    case 'answer':
      return event.stage === 'react' && event.step === 'answer_emitted';
    case 'memory_load':
      return event.stage === 'memory';
    case 'prompt_build':
      return event.stage === 'context' && event.step === 'token_update';
    case 'hil_pause':
      return event.stage === 'hil' && event.step === 'interrupt_emitted';
    case 'turn_summary':
      return event.stage === 'react' && event.step === 'turn_done';
    default:
      return false;
  }
}

export function ExecutionTracePanel({ traceBlocks, traceEvents, turnStatuses }: ExecutionTracePanelProps) {
  const [verboseMode, setVerboseMode] = useState(false);

  const turnGroups = useMemo(() => groupByTurn(traceBlocks), [traceBlocks]);
  const turnEvents = useMemo(() => {
    const grouped = new Map<string, TraceEvent[]>();
    for (const event of traceEvents) {
      const key = event.turnId ?? '__pre__';
      if (!grouped.has(key)) grouped.set(key, []);
      grouped.get(key)!.push(event);
    }
    return grouped;
  }, [traceEvents]);

  const visibleGroups = useMemo(() => {
    if (verboseMode) return turnGroups;
    return turnGroups.map((group) => ({
      ...group,
      blocks: group.blocks.filter((b) => USER_VISIBLE_BLOCKS.has(b.type)),
    }));
  }, [turnGroups, verboseMode]);

  const blockCount = useMemo(() => traceBlocks.length, [traceBlocks]);
  const turnCount = useMemo(() => turnGroups.length, [turnGroups]);

  return (
    <div className="flex h-full flex-col" data-testid="execution-trace-panel">
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            <h2 className="font-semibold text-text-primary">执行链路</h2>
          </div>
          <button
            className="flex items-center gap-1 text-xs text-text-muted hover:text-text-primary transition-colors"
            onClick={() => setVerboseMode(!verboseMode)}
          >
            {verboseMode ? (
              <>
                <EyeOff className="w-3.5 h-3.5" />
                <span>简洁</span>
              </>
            ) : (
              <>
                <Eye className="w-3.5 h-3.5" />
                <span>详细</span>
              </>
            )}
          </button>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {blockCount} 个步骤 · {turnCount} 轮对话
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {traceBlocks.length === 0 ? (
          <div className="px-3 py-8 text-center text-sm text-text-muted">
            暂无链路事件
          </div>
        ) : (
          <div className="space-y-4">
            {visibleGroups.map((group, groupIdx) => {
              const turnNumber = group.turnId
                ? parseInt(group.turnId.replace('turn_', ''), 10)
                : null;
              const firstBlock = group.blocks[0];
              const status = group.turnId && turnStatuses?.[group.turnId]
                ? turnStatuses[group.turnId]
                : null;

              return (
                <div key={group.turnId ?? `pre_${groupIdx}`}>
                  <div
                    data-testid="turn-divider"
                    className="flex items-center gap-2 px-3 py-1.5 bg-primary/5 border border-primary/20 rounded-lg mb-2"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-primary">
                        {turnNumber !== null ? `Turn #${turnNumber}` : 'Pre-session'}
                      </span>
                      <span className="text-[11px] text-text-muted">
                        {formatTime(firstBlock?.timestamp ?? '')}
                      </span>
                    </div>
                    {status && (
                      <span className={cn(
                        'text-[11px] px-1.5 py-0.5 rounded',
                        status === 'done' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700',
                      )}>
                        {status === 'done' ? '完成' : '失败'}
                      </span>
                    )}
                    <div className="flex-1" />
                    <span className="text-[11px] text-text-muted">
                      {group.blocks.length} 个步骤
                    </span>
                  </div>

                  <div className="ml-2 border-l-2 border-border pl-3 space-y-2">
                    {group.blocks.map((block) => {
                      const key = group.turnId ?? '__pre__';
                      const rawEvents = verboseMode
                        ? (turnEvents.get(key) ?? []).filter((event) => eventMatchesBlock(block, event))
                        : undefined;
                      return (
                        <TraceBlockCard
                          key={block.id}
                          block={block}
                          rawEvents={rawEvents}
                        />
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
