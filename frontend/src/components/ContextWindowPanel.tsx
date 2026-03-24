'use client';

import { motion } from 'framer-motion';
import { Layers, TrendingUp, Activity, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ContextWindowData, SlotDetail } from '@/types/context-window';
import { SlotBar } from './SlotBar';
import { CompressionLog } from './CompressionLog';
import { SlotDetailList } from './SlotDetail';

interface ContextWindowPanelProps {
  /** Context window data */
  data: ContextWindowData;
  /** Slot details (optional) */
  slotDetails?: SlotDetail[];
  /** Backend state messages (optional) */
  stateMessages?: import('@/types/context-window').StateMessage[];
}

/**
 * ContextWindowPanel Component
 *
 * Visualizes the 10-slot Context Window with:
 * - Overall progress bar (total budget usage)
 * - Slot breakdown table (SlotBar components)
 * - Compression event log
 * - Statistics row
 *
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */
export function ContextWindowPanel({ data, slotDetails, stateMessages }: ContextWindowPanelProps) {
  const { budget, slotUsage, compressionEvents } = data;

  // Calculate overall usage
  const totalUsed = budget.usage.total_used;
  const totalBudget = budget.working_budget;
  const usagePercentage = totalBudget > 0 ? (totalUsed / totalBudget) * 100 : 0;
  
  // Calculate reserved buffer (预留)
  const reservedBuffer =
    budget.usage.autocompact_buffer ?? Math.max(0, Math.floor(totalBudget * 0.165));
  
  // Calculate actual savings from compression events (实际节省)
  const actualSavings = compressionEvents.reduce((sum, event) => sum + event.tokens_saved, 0);
  
  const freeSpace = Math.max(0, totalBudget - totalUsed - reservedBuffer);

  // Format numbers
  const formatNumber = (num: number) => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  };

  // Get status config based on usage
  const getStatusConfig = () => {
    if (usagePercentage >= 90) {
      return {
        bg: 'bg-danger',
        text: 'text-error-text',
        label: '即将耗尽',
        iconBg: 'bg-error-bg',
      };
    }
    if (usagePercentage >= 70) {
      return {
        bg: 'bg-warning',
        text: 'text-warning-text',
        label: '使用较多',
        iconBg: 'bg-warning-bg',
      };
    }
    return {
      bg: 'bg-accent',
      text: 'text-success-text',
      label: '正常',
      iconBg: 'bg-success-bg',
    };
  };

  const statusConfig = getStatusConfig();

  const rawToCanonical: Record<string, string> = {
    system: 'system',
    skill_registry: 'system',
    skill_protocol: 'system',
    active_skill: 'active_skill',
    few_shot: 'few_shot',
    rag: 'rag',
    episodic: 'episodic',
    procedural: 'procedural',
    tools: 'tools',
    history: 'history',
    output_format: 'output_format',   // 改：原来映射到 'system'
    user_input: 'user_input',         // 改：原来映射到 'history'
  };

  const categoryLabels: Record<string, string> = {
    system: 'System prompt',
    active_skill: 'Active skill',
    few_shot: 'Few-shot',
    rag: 'RAG',
    episodic: 'Episodic memory',
    procedural: 'Procedural memory',
    tools: 'Tools schema',
    history: 'Messages',
    output_format: 'Output format',
    user_input: 'User input',
  };

  const categoryUsage = (() => {
    const aggregate: Record<string, number> = {
      system: 0,
      active_skill: 0,
      few_shot: 0,
      rag: 0,
      episodic: 0,
      procedural: 0,
      tools: 0,
      history: 0,
      output_format: 0,
      user_input: 0,
    };

    if (slotDetails && slotDetails.length > 0) {
      for (const slot of slotDetails) {
        if (!slot.enabled) {
          continue;
        }
        const canonical = rawToCanonical[slot.name];
        if (canonical) {
          aggregate[canonical] += slot.tokens;
        }
      }
    } else {
      for (const slot of slotUsage) {
        aggregate[slot.name] = slot.used;
      }
    }

    return Object.entries(aggregate)
      .map(([name, tokens]) => ({ name, label: categoryLabels[name], tokens }))
      .filter((item) => item.tokens > 0)
      .sort((a, b) => b.tokens - a.tokens);
  })();

  return (
    <div className="flex h-full flex-col" data-testid="context-window-panel">
      {/* Header */}
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-text-secondary" />
          <h2 className="font-semibold text-text-primary">Context Usage</h2>
        </div>
        <p className="mt-1 text-xs text-text-muted">
          {formatNumber(totalUsed)}/{formatNumber(totalBudget)} tokens ({usagePercentage.toFixed(1)}
          %)
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Usage by Category */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-text-secondary" />
            <span className="text-sm font-medium text-text-primary">Estimated usage by category</span>
          </div>
          <div className="space-y-2">
            {categoryUsage.map((item) => {
              const ratio = totalBudget > 0 ? (item.tokens / totalBudget) * 100 : 0;
              return (
                <div
                  key={item.name}
                  className="flex items-center justify-between text-sm"
                  data-testid={`context-row-${item.name}`}
                >
                  <span className="text-text-secondary">{item.label}</span>
                  <span className="text-text-primary tabular-nums">
                    {formatNumber(item.tokens)} ({ratio.toFixed(1)}%)
                  </span>
                </div>
              );
            })}
            <div
              className="flex items-center justify-between text-sm border-t border-border pt-2"
              data-testid="context-row-free-space"
            >
              <span className="text-text-secondary">Free space</span>
              <span className="text-text-primary tabular-nums">
                {formatNumber(freeSpace)} ({(totalBudget > 0 ? (freeSpace / totalBudget) * 100 : 0).toFixed(1)}%)
              </span>
            </div>
            <div
              className="flex items-center justify-between text-sm border-t border-border pt-2"
              data-testid="context-row-reserved-buffer"
            >
              <span className="text-text-secondary">预留 Buffer</span>
              <span className="text-text-primary tabular-nums">
                {formatNumber(reservedBuffer)} ({(totalBudget > 0 ? (reservedBuffer / totalBudget) * 100 : 0).toFixed(1)}%)
              </span>
            </div>
            {actualSavings > 0 && (
              <div
                className="flex items-center justify-between text-sm"
                data-testid="context-row-actual-savings"
              >
                <span className="text-text-secondary">实际节省</span>
                <span className="text-text-primary tabular-nums text-success-text">
                  -{formatNumber(actualSavings)} ({(totalBudget > 0 ? (actualSavings / totalBudget) * 100 : 0).toFixed(1)}%)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Overall Progress Bar */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-text-secondary" />
              <span className="text-sm font-medium text-text-primary">总体进度</span>
            </div>
            <span
              className={cn('text-xs font-semibold', statusConfig.text)}
              data-testid="overall-status"
            >
              {statusConfig.label}
            </span>
          </div>

          {/* Progress bar */}
          <div className="relative h-3 w-full overflow-hidden rounded-full bg-bg-muted">
            <div className="absolute inset-0 rounded-full bg-border-muted" />
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${Math.min(usagePercentage, 100)}%` }}
              transition={{ duration: 0.5, ease: 'easeOut' }}
              className={cn('h-full rounded-full relative overflow-hidden', statusConfig.bg)}
              data-testid="overall-progress-fill"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
            </motion.div>
          </div>

            {/* Percentage and remaining */}
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-text-muted">
                {usagePercentage.toFixed(1)}% 已使用
              </span>
              <span className="text-xs text-text-muted">
                {formatNumber(budget.usage.total_remaining)} 剩余
              </span>
            </div>

            {/* Reserved Buffer */}
            <div
              className="flex items-center justify-between text-sm border-t border-border pt-2"
              data-testid="context-row-reserved-buffer"
            >
              <span className="text-text-secondary">预留 Buffer</span>
              <span className="text-xs text-text-primary tabular-nums">
                {formatNumber(reservedBuffer)} ({totalBudget > 0 ? (reservedBuffer / totalBudget) * 100 : 0).toFixed(1)}%
              </span>
            </div>

            {/* Actual Savings */}
            {actualSavings > 0 && (
              <div
                className="flex items-center justify-between text-sm"
                data-testid="context-row-actual-savings"
              >
                <span className="text-text-secondary">实际节省</span>
                <span className="text-xs text-primary tabular-nums text-success-text">
                  -{formatNumber(actualSavings)} ({compressionEvents.length} 次事件)
                </span>
              </div>
            )}

            {/* Free Space */}
            <div
              className="flex items-center justify-between text-sm border-t border-border pt-2"
              data-testid="context-row-free-space"
            >
              <span className="text-text-secondary">Free space</span>
              <span className="text-xs text-primary tabular-nums">
                {formatNumber(freeSpace)} ({totalBudget > 0 ? (freeSpace / totalBudget) * 100 : 0).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Slot Breakdown */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="mb-3 flex items-center gap-2">
            <Layers className="w-4 h-4 text-text-secondary" />
            <span className="text-sm font-medium text-text-primary">完整 Slot 快照</span>
          </div>
          <div className="space-y-2" data-testid="slot-breakdown">
            {slotDetails && slotDetails.length > 0 ? (
              <SlotDetailList slots={slotDetails} preview />
            ) : (
              slotUsage.map((slot) => <SlotBar key={slot.name} slot={slot} />)
            )}
          </div>
        </div>

        {/* Slot Budget Breakdown */}
        <div className="border-b border-border p-4 bg-bg-card" data-testid="slot-breakdown">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-text-secondary" />
              <span className="text-sm font-medium text-text-primary">Slot 预算分解</span>
              <span className="text-xs text-text-muted">({slotUsage.length} 个 Slot)</span>
            </div>
          </div>

          <div className="space-y-2">
            {slotUsage.map((slot) => (
              <div key={slot.name}>
                <div
                  className="flex items-center justify-between text-sm"
                  data-testid={`context-row-${slot.name}`}
                >
                  <SlotBar slot={slot} />
                </div>
                {/* Slot ⑧ (history) 展开预览 */}
                {slot.name === 'history' && stateMessages && stateMessages.length > 0 && (
                  <details className="mt-1 ml-14">
                    <summary className="text-xs text-text-muted cursor-pointer">
                      展开 {stateMessages.length} 条消息
                    </summary>
                    <div className="mt-1 space-y-0.5 max-h-48 overflow-y-auto">
                      {stateMessages.map((msg, i) => (
                        <div key={i} className="text-[11px] text-text-secondary">
                          <span className="font-mono text-text-muted mr-1">[{msg.role}]</span>
                          {(msg.content || '').slice(0, 80)}{(msg.content || '').length > 80 ? '...' : ''}
                        </div>
                      ))}
                    </div>
                  </details>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Statistics Row */}
          <div className="border-b border-border p-4 bg-bg-card">
            <div className="mb-3 flex items-center justify-between">
              <BarChart3 className="w-4 h-4 text-text-secondary" />
              <span className="text-sm font-medium text-text-primary">统计数据</span>
            </div>
            <div className="space-y-2">
              {/* Reserved Buffer */}
              <div
                className="flex items-center justify-between text-sm"
                data-testid="context-row-autocompact-buffer"
              >
                <span className="text-text-secondary">Autocompact buffer</span>
                <span className="text-xs text-text-muted">
                  {formatNumber(budget.usage.autocompact_buffer ?? 0)}
                </span>
              </div>

              {/* Reserved Buffer (original test name) */}
              <div
                className="flex items-center justify-between text-sm"
                data-testid="context-row-reserved-buffer"
              >
                <span className="text-text-secondary">预留 Buffer</span>
                <span className="text-xs text-text-muted">
                  {formatNumber(Math.floor(totalBudget * 0.165))}
                </span>
              </div>

              {/* Actual Savings */}
              {actualSavings > 0 && (
                <div
                  className="flex items-center justify-between text-sm"
                  data-testid="context-row-actual-savings"
                >
                  <span className="text-text-secondary">实际节省</span>
                  <span className="text-xs text-text-muted">
                    {formatNumber(actualSavings)} tokens ({compressionEvents.length} 次事件)
                  </span>
                </div>
              )}

              {/* Free Space */}
              <div
                className="flex items-center justify-between text-sm"
                data-testid="context-row-free-space"
              >
                <span className="text-text-secondary">Free space</span>
                <span className="text-xs text-text-muted">
                  {formatNumber(freeSpace)} tokens ({((freeSpace / totalBudget) * 100).toFixed(1)}%)
                </span>
              </div>
            </div>
          </div>

        {/* Compression Log */}
        <div className="bg-bg-card">
          <CompressionLog events={compressionEvents} />
        </div>
      </div>
    </div>
  );
}
