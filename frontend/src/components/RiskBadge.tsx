"use client";

import { motion } from 'framer-motion';
import { AlertTriangle, Shield, CheckCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface RiskBadgeProps {
  level: "high" | "medium" | "low";
}

export function RiskBadge({ level }: RiskBadgeProps) {
  const riskConfig = {
    high: {
      label: "高风险",
      icon: AlertTriangle,
      className: cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold",
        "bg-error-bg text-error-text border-error-text/20",
        "dark:bg-error-bg/10 dark:text-error-text dark:border-error-text/30"
      ),
      iconClass: "text-error-text",
    },
    medium: {
      label: "中风险",
      icon: Shield,
      className: cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold",
        "bg-warning-bg text-warning-text border-warning-text/20",
        "dark:bg-warning-bg/10 dark:text-warning-text dark:border-warning-text/30"
      ),
      iconClass: "text-warning-text",
    },
    low: {
      label: "低风险",
      icon: CheckCircle,
      className: cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold",
        "bg-success-bg text-success-text border-success-text/20",
        "dark:bg-success-bg/10 dark:text-success-text dark:border-success-text/30"
      ),
      iconClass: "text-success-text",
    },
  };

  const config = riskConfig[level];
  const Icon = config.icon;

  return (
    <motion.span
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className={config.className}
    >
      <Icon className={cn("w-3.5 h-3.5", config.iconClass)} />
      {config.label}
    </motion.span>
  );
}
