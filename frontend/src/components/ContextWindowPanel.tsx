'use client';

import { motion } from 'framer-motion';
import { Layers, TrendingUp, Activity, BarChart3 } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ContextWindowData, SlotUsage } from '@/types/context-window';
import { SlotBar } from './SlotBar';
import { CompressionLog } from './CompressionLog';

interface ContextWindowPanelProps {
  /** Context window data */
  data: ContextWindowData;
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
export function ContextWindowPanel({ data }: ContextWindowPanelProps) {
  const { budget, slotUsage, compressionEvents } = data;

  // Calculate overall usage
  const totalUsed = budget.usage.total_used;
  const totalBudget = budget.working_budget;
  const usagePercentage =
    totalBudget > 0 ? (totalUsed / totalBudget) * 100 : 0;

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

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border p-4 bg-background-alt">
        <div className="flex items-center gap-2">
          <Layers className="w-5 h-5 text-text-secondary" />
          <h2 className="font-semibold text-text-primary">Context Window</h2>
        </div>
        <p className="mt-1 text-xs text-text-muted">
          Token 预算: {formatNumber(totalBudget)} | 模型上限:{' '}
          {formatNumber(budget.model_context_window)}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Overall Progress Bar */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-text-secondary" />
              <span className="text-sm font-medium text-text-primary">
                总体进度
              </span>
            </div>
            <span
              className={cn("text-xs font-semibold", statusConfig.text)}
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
              transition={{ duration: 0.5, ease: "easeOut" }}
              className={cn("h-full rounded-full relative overflow-hidden", statusConfig.bg)}
              data-testid="overall-progress-fill"
            >
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
            </motion.div>
          </div>

          {/* Percentage and remaining */}
          <div className="mt-2 flex items-center justify-between text-xs">
            <span className="text-text-muted" data-testid="overall-percentage">
              {usagePercentage.toFixed(1)}% 已使用
            </span>
            <span
              className={cn("font-medium tabular-nums", statusConfig.text)}
              data-testid="overall-remaining"
            >
              {formatNumber(budget.usage.total_remaining)} 剩余
            </span>
          </div>
        </div>

        {/* Slot Breakdown */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-text-secondary" />
            <span className="text-sm font-medium text-text-primary">
              Slot 分解
            </span>
            <span className="text-xs text-text-muted">
              ({slotUsage.length} 个 Slot)
            </span>
          </div>

          <div className="space-y-2" data-testid="slot-breakdown">
            {slotUsage.map((slot) => (
              <SlotBar key={slot.name} slot={slot} />
            ))}
          </div>
        </div>

        {/* Statistics Row */}
        <div className="border-b border-border p-4 bg-bg-card">
          <div className="grid grid-cols-2 gap-4">
            {/* Input Budget */}
            <div className="rounded-lg bg-bg-muted border border-border p-3">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="w-4 h-4 text-text-secondary" />
                <span className="text-xs text-text-muted">输入预算</span>
              </div>
              <p
                className="text-lg font-semibold text-text-primary tabular-nums"
                data-testid="stat-input-budget"
              >
                {formatNumber(budget.usage.input_budget)}
              </p>
            </div>

            {/* Output Reserve */}
            <div className="rounded-lg bg-bg-muted border border-border p-3">
              <div className="flex items-center gap-2 mb-1">
                <Layers className="w-4 h-4 text-text-secondary" />
                <span className="text-xs text-text-muted">输出预留</span>
              </div>
              <p
                className="text-lg font-semibold text-text-primary tabular-nums"
                data-testid="stat-output-reserve"
              >
                {formatNumber(budget.usage.output_reserve)}
              </p>
            </div>

            {/* Total Used */}
            <div className="rounded-lg bg-bg-muted border border-border p-3">
              <div className="flex items-center gap-2 mb-1">
                <Activity className="w-4 h-4 text-text-secondary" />
                <span className="text-xs text-text-muted">已使用</span>
              </div>
              <p
                className="text-lg font-semibold text-text-primary tabular-nums"
                data-testid="stat-total-used"
              >
                {formatNumber(totalUsed)}
              </p>
            </div>

            {/* Compression Count */}
            <div className="rounded-lg bg-bg-muted border border-border p-3">
              <div className="flex items-center gap-2 mb-1">
                <BarChart3 className="w-4 h-4 text-text-secondary" />
                <span className="text-xs text-text-muted">压缩次数</span>
              </div>
              <p
                className="text-lg font-semibold text-text-primary tabular-nums"
                data-testid="stat-compression-count"
              >
                {compressionEvents.length}
              </p>
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
