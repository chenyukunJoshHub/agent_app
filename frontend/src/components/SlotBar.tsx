'use client';

import { motion } from 'framer-motion';
import { AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { SlotUsage } from '@/types/context-window';

interface SlotBarProps {
  /** Slot usage data */
  slot: SlotUsage;
}

/**
 * SlotBar Component
 *
 * Visualizes a single slot's token usage with:
 * - Color-coded indicator
 * - Mini progress bar
 * - Used/max token display
 * - Overflow warning
 */
export function SlotBar({ slot }: SlotBarProps) {
  const { displayName, allocated, used, color } = slot;

  // Calculate usage percentage
  const percentage = allocated > 0 ? (used / allocated) * 100 : 0;
  const isOverflow = used > allocated;

  // Format token numbers
  const formatNumber = (num: number) => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex items-center gap-3 rounded-lg border border-border bg-bg-card px-3 py-2",
        "transition-all duration-200 hover:shadow-sm hover:border-border-strong"
      )}
      data-testid="slot-bar"
      data-slot-name={slot.name}
    >
      {/* Color indicator */}
      <div
        className="flex-shrink-0 w-3 h-3 rounded-full"
        style={{ backgroundColor: color }}
        data-testid="slot-color-indicator"
      />

      {/* Slot name */}
      <div className="flex-shrink-0 w-24">
        <span className="text-sm font-medium text-text-primary">
          {displayName}
        </span>
      </div>

      {/* Mini progress bar */}
      <div className="flex-1 min-w-0">
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-bg-muted">
          {/* Background track */}
          <div className="absolute inset-0 rounded-full bg-border-muted" />
          {/* Progress fill */}
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(percentage, 100)}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className={cn(
              "h-full rounded-full relative overflow-hidden",
              isOverflow ? "bg-danger" : "bg-accent"
            )}
            style={!isOverflow ? { backgroundColor: color } : undefined}
            data-testid="slot-progress-fill"
          >
            {/* Shine effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
          </motion.div>
        </div>
      </div>

      {/* Token usage */}
      <div className="flex min-w-[100px] items-center justify-end gap-2">
        <span
          className={cn(
            "text-sm font-medium tabular-nums",
            isOverflow ? "text-error-text" : "text-text-primary"
          )}
          data-testid="slot-used-tokens"
        >
          {formatNumber(used)}
        </span>
        <span className="text-xs text-text-muted">/</span>
        <span
          className="text-sm text-text-secondary tabular-nums"
          data-testid="slot-allocated-tokens"
        >
          {formatNumber(allocated)}
        </span>

        {/* Overflow warning */}
        {isOverflow && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 500, damping: 20 }}
            className="flex-shrink-0"
            data-testid="slot-overflow-warning"
          >
            <AlertTriangle className="w-4 h-4 text-error-text" />
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
