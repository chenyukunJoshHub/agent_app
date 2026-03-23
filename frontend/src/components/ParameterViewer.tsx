"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, Code } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ParameterViewerProps {
  data: Record<string, unknown>;
}

export function ParameterViewer({ data }: ParameterViewerProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className={cn(
        "rounded-lg border border-border bg-bg-muted px-4 py-2.5 text-sm text-text-muted",
        "flex items-center gap-2"
      )}>
        <Code className="w-4 h-4 opacity-50" />
        无参数
      </div>
    );
  }

  return (
    <div className={cn(
      "rounded-lg border border-border bg-bg-card overflow-hidden",
      "transition-all duration-200 hover:border-border-strong"
    )}>
      <motion.button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-text-primary",
          "hover:bg-bg-muted transition-colors duration-150"
        )}
        whileHover={{ x: 2 }}
        whileTap={{ scale: 0.99 }}
      >
        <span className="flex items-center gap-2">
          <Code className="w-4 h-4 text-primary" />
          参数
          <span className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary"
          )}>
            {Object.keys(data).length}
          </span>
        </span>
        <motion.span
          animate={{ rotate: isExpanded ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          className="text-text-muted"
        >
          <ChevronRight className="w-4 h-4" />
        </motion.span>
      </motion.button>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="border-t border-border overflow-hidden"
          >
            <div className="px-4 py-3 bg-bg-muted/50">
              <pre className={cn(
                "overflow-x-auto text-xs text-text-primary font-mono leading-relaxed",
                "bg-bg-base rounded-lg p-3 border border-border-muted"
              )}>
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
