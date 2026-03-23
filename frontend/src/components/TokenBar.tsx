'use client';

import { motion } from 'framer-motion';
import { TrendingUp, AlertCircle, CheckCircle, MinusCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface TokenBarProps {
  current: number;
  budget: number;
}

export function TokenBar({ current, budget }: TokenBarProps) {
  const percentage = budget > 0 ? (current / budget) * 100 : 0;
  const remaining = budget - current;

  // Color coding based on usage with design system colors
  const getStatusConfig = () => {
    if (percentage >= 90) {
      return {
        bg: 'bg-danger',
        text: 'text-error-text',
        label: '即将耗尽',
        icon: AlertCircle,
        glow: 'glow-danger',
      };
    }
    if (percentage >= 70) {
      return {
        bg: 'bg-warning',
        text: 'text-warning-text',
        label: '使用较多',
        icon: MinusCircle,
        glow: '',
      };
    }
    return {
      bg: 'bg-accent',
      text: 'text-success-text',
      label: '正常',
      icon: CheckCircle,
      glow: 'glow-accent',
    };
  };

  const config = getStatusConfig();
  const StatusIcon = config.icon;

  // Format token numbers
  const formatNumber = (num: number) => {
    if (num >= 1000) {
      return `${(num / 1000).toFixed(1)}k`;
    }
    return num.toString();
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        "flex items-center gap-4 rounded-xl border border-border bg-bg-card px-5 py-3 shadow-sm",
        "transition-all duration-200 hover:shadow-md hover:border-border-strong"
      )}
      data-testid="token-bar"
    >
      {/* Icon + Label */}
      <div className="flex-shrink-0">
        <div className={cn(
          "flex items-center justify-center w-10 h-10 rounded-lg",
          percentage >= 90 ? "bg-error-bg" : percentage >= 70 ? "bg-warning-bg" : "bg-success-bg"
        )}>
          <StatusIcon className={cn(
            "w-5 h-5",
            percentage >= 90 ? "text-error-text" : percentage >= 70 ? "text-warning-text" : "text-success-text"
          )} />
        </div>
      </div>

      {/* Progress bar */}
      <div className="flex-1 min-w-0">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-text-secondary flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5" />
            Token 使用
          </span>
          <span className={cn("text-xs font-semibold flex items-center gap-1", config.text)}>
            {config.label}
          </span>
        </div>
        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-bg-muted">
          {/* Background track */}
          <div className="absolute inset-0 rounded-full bg-border-muted" />
          {/* Progress fill */}
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${Math.min(percentage, 100)}%` }}
            transition={{ duration: 0.5, ease: "easeOut" }}
            className={cn(
              "h-full rounded-full relative overflow-hidden",
              config.bg,
              config.glow
            )}
          >
            {/* Shine effect */}
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
          </motion.div>
        </div>
        {/* Percentage text */}
        <div className="mt-1.5 flex items-center justify-between text-xs">
          <span className="text-text-muted">
            {percentage.toFixed(1)}% 已使用
          </span>
          <span className={cn("font-medium", config.text)}>
            {formatNumber(remaining)} 剩余
          </span>
        </div>
      </div>

      {/* Token numbers */}
      <div className="flex min-w-[100px] flex-col items-end border-l border-border pl-4">
        <span className="text-sm font-semibold text-text-primary tabular-nums">
          {formatNumber(current)}
        </span>
        <span className="text-xs text-text-muted">/ {formatNumber(budget)}</span>
      </div>
    </motion.div>
  );
}
