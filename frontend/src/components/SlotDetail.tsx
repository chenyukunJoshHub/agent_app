'use client';

import { motion } from 'framer-motion';
import { FileText, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import type { SlotDetail } from '@/types/context-window';

interface SlotDetailProps {
  /** Slot detail data */
  slot: SlotDetail;
  /** Whether to show content preview only */
  preview?: boolean;
}

/**
 * SlotDetail Component
 *
 * Displays a single Slot's:
 * - Name and display name
 * - Token count
 * - Content (collapsible)
 * - Enabled status
 *
 * Based on Prompt v20 §1.2 十大子模块与 Context Window 分区
 */
export function SlotDetail({ slot, preview = false }: SlotDetailProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const statusColor = slot.enabled ? 'text-success-text' : 'text-text-muted';

  const bgColor = slot.enabled ? 'bg-bg-card' : 'bg-bg-muted opacity-60';

  // Truncate content for preview
  const displayContent =
    preview && slot.content.length > 200 ? slot.content.slice(0, 200) + '...' : slot.content;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('rounded-lg border border-border p-4', bgColor)}
    >
      {/* Header - Name and Token count */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => !preview && setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3 flex-1">
          {/* Expand/Collapse icon */}
          {!preview && (
            <motion.div animate={{ rotate: isExpanded ? 90 : 0 }} transition={{ duration: 0.2 }}>
              <ChevronRight className="w-4 h-4 text-text-secondary" />
            </motion.div>
          )}

          {/* Slot name */}
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-text-secondary" />
            <span className="font-medium text-text-primary">{slot.display_name}</span>
            <span className="text-xs text-text-muted">({slot.name})</span>
          </div>

          {/* Enabled badge */}
          <div
            className={cn(
              'text-xs px-2 py-0.5 rounded',
              slot.enabled ? 'bg-success-bg text-success-text' : 'bg-bg-muted text-text-muted'
            )}
          >
            {slot.enabled ? '启用' : '未启用'}
          </div>
        </div>

        {/* Token count */}
        <div className="flex items-center gap-1">
          <span className={cn('text-sm font-semibold tabular-nums', statusColor)}>
            {slot.tokens.toLocaleString()}
          </span>
          <span className="text-xs text-text-muted">tokens</span>
        </div>
      </div>

      {/* Content (collapsible) */}
      {(isExpanded || preview) && slot.content && (
        <motion.div
          initial={preview ? undefined : { opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          transition={{ duration: 0.2 }}
          className="mt-3 pt-3 border-t border-border"
        >
          <div className="text-sm text-text-secondary whitespace-pre-wrap break-words font-mono">
            {displayContent}
          </div>
          {!preview && slot.content.length > 200 && (
            <div className="mt-2 text-xs text-text-muted">{slot.content.length} 字符</div>
          )}
        </motion.div>
      )}

      {/* Empty state */}
      {(isExpanded || preview) && !slot.content && (
        <motion.div
          initial={preview ? undefined : { opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          transition={{ duration: 0.2 }}
          className="mt-3 pt-3 border-t border-border"
        >
          <div className="text-sm text-text-muted italic">
            {slot.enabled ? '暂无内容' : '此 Slot 未启用'}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}

/**
 * SlotDetailList Component
 *
 * Displays a list of SlotDetail components.
 */
interface SlotDetailListProps {
  /** Slot details */
  slots: SlotDetail[];
  /** Whether to show preview only */
  preview?: boolean;
}

export function SlotDetailList({ slots, preview = false }: SlotDetailListProps) {
  // Sort by tokens descending
  const sortedSlots = [...slots].sort((a, b) => b.tokens - a.tokens);

  return (
    <div className="space-y-3">
      {sortedSlots.map((slot) => (
        <SlotDetail key={slot.name} slot={slot} preview={preview} />
      ))}
    </div>
  );
}
